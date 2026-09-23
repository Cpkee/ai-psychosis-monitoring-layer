"""Minimal HTTP client on the standard library.

Used by the source collectors and the extractor adapters, so the seed pipeline
adds no dependency. Errors are translated into two declared types, and every
caller maps those onto its own seam: *unavailable* (network failure, timeout,
429 or 5xx; retryable) versus *rejected* (any other 4xx; the request itself is
wrong, so retrying cannot help).

A :class:`RetryPolicy` retries *unavailable* failures after increasing delays,
honouring a server's ``Retry-After`` up to a cap, before giving up. Demand
spikes on hosted models are usually brief; without retries a single one would
stop a whole batch. A *rejected* request is never retried.
"""

from __future__ import annotations

import dataclasses
import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping, Optional, Tuple

USER_AGENT = "apml-seed-collector/0.1 (research prototype)"


class HttpUnavailable(RuntimeError):
    """Retryable: the service could not be reached or asked us to back off."""


class HttpRejected(RuntimeError):
    """Not retryable: the service refused this request."""


@dataclasses.dataclass(frozen=True)
class RetryPolicy:
    #: Seconds to wait before each retry. Empty means one attempt only.
    delays: Tuple[float, ...] = ()
    #: A server's Retry-After is honoured, but never beyond this.
    max_retry_after: float = 120.0


NO_RETRY = RetryPolicy()


class _Retryable(Exception):
    def __init__(self, message: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


def _retry_after(exc: urllib.error.HTTPError) -> Optional[float]:
    """Retry-After in seconds, if given as a number (date forms are ignored)."""
    try:
        return float(exc.headers.get("Retry-After"))
    except (TypeError, ValueError, AttributeError):
        return None


def _error_message(exc: urllib.error.HTTPError) -> str:
    """The ``error.message`` of a JSON error body, truncated; empty if none."""
    try:
        body = json.loads(exc.read().decode("utf-8", errors="replace"))
        return ": " + str(body["error"]["message"])[:300]
    except Exception:
        return ""


class HttpClient:
    def __init__(self, timeout: float = 60.0, min_interval: float = 0.0,
                 retry: RetryPolicy = NO_RETRY,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic,
                 opener: Callable[..., Any] = urllib.request.urlopen):
        #: Politeness: NCBI allows about 3 requests a second without a key,
        #: and arXiv asks for one every 3 seconds.
        self._timeout = timeout
        self._min_interval = min_interval
        self._retry = retry
        self._sleep = sleep
        self._monotonic = monotonic
        self._opener = opener
        self._last: Optional[float] = None

    def get(self, url: str, params: Optional[Mapping[str, Any]] = None,
            headers: Optional[Mapping[str, str]] = None) -> bytes:
        if params:
            url = "{}?{}".format(url, urllib.parse.urlencode(params))
        return self._send(urllib.request.Request(url, headers=self._headers(headers)))

    def post_json(self, url: str, body: Any,
                  headers: Optional[Mapping[str, str]] = None) -> Any:
        merged = dict(headers or {})
        merged["Content-Type"] = "application/json"
        request = urllib.request.Request(
            url, data=json.dumps(body).encode("utf-8"), headers=self._headers(merged),
            method="POST")
        raw = self._send(request)
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            raise HttpRejected("The service did not return JSON.")

    def _headers(self, headers: Optional[Mapping[str, str]]) -> Mapping[str, str]:
        merged = {"User-Agent": USER_AGENT}
        merged.update(headers or {})
        return merged

    def _send(self, request: urllib.request.Request) -> bytes:
        delays = list(self._retry.delays)
        attempts = 0
        while True:
            attempts += 1
            try:
                return self._attempt(request)
            except _Retryable as exc:
                if not delays:
                    suffix = " (after {} attempts)".format(attempts) if attempts > 1 else ""
                    raise HttpUnavailable(exc.message + suffix)
                wait = delays.pop(0)
                if exc.retry_after is not None:
                    wait = min(max(wait, exc.retry_after), self._retry.max_retry_after)
                self._sleep(wait)

    def _attempt(self, request: urllib.request.Request) -> bytes:
        self._wait()
        try:
            with self._opener(request, timeout=self._timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            message = "HTTP {} {}".format(exc.code, exc.reason)
            if exc.code == 429 or exc.code >= 500:
                # Retryable messages end up stored on DELAYED documents, so
                # they stay ours alone: no provider text (as D-11).
                raise _Retryable(message, _retry_after(exc))
            # A rejection stops the run and is printed, never stored. The
            # provider's own explanation is often the only useful clue, as
            # with "model ... is no longer available to new users".
            raise HttpRejected(message + _error_message(exc))
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError) as exc:
            raise _Retryable("Could not reach {}: {}".format(
                urllib.parse.urlsplit(request.full_url).netloc, getattr(exc, "reason", exc)))
        finally:
            self._last = self._monotonic()

    def _wait(self) -> None:
        if self._last is None or not self._min_interval:
            return
        remaining = self._min_interval - (self._monotonic() - self._last)
        if remaining > 0:
            self._sleep(remaining)
