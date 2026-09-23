"""HTTP client retries — no network, no real waiting.

A fake opener plays back a scripted sequence of responses, and ``sleep`` is
recorded rather than performed, so each test can check exactly how long the
client would have waited.
"""

from __future__ import annotations

import io
import json
import unittest
import urllib.error

from src.adapters.http import HttpClient, HttpRejected, HttpUnavailable, RetryPolicy

URL = "https://example.org/api"


def http_error(code, headers=None, body=b""):
    return urllib.error.HTTPError(URL, code, "Example reason", headers or {}, io.BytesIO(body))


class _Response:
    def __init__(self, body):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._body


class ScriptedOpener:
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, request, timeout):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return _Response(outcome)


class Retries(unittest.TestCase):
    def client(self, opener, delays=(5.0, 15.0, 45.0), max_retry_after=120.0):
        self.slept = []
        return HttpClient(retry=RetryPolicy(delays, max_retry_after), sleep=self.slept.append,
                          monotonic=lambda: 0.0, opener=opener)

    def test_a_demand_spike_is_retried_with_increasing_delays(self):
        opener = ScriptedOpener(http_error(503), http_error(503), b"ok")
        self.assertEqual(self.client(opener).get(URL), b"ok")
        self.assertEqual((opener.calls, self.slept), (3, [5.0, 15.0]))

    def test_it_gives_up_after_the_last_delay_and_says_how_often_it_tried(self):
        opener = ScriptedOpener(*[http_error(503)] * 4)
        with self.assertRaises(HttpUnavailable) as caught:
            self.client(opener).get(URL)
        self.assertEqual((opener.calls, self.slept), (4, [5.0, 15.0, 45.0]))
        self.assertIn("after 4 attempts", str(caught.exception))

    def test_rate_limits_and_network_failures_are_retried_too(self):
        opener = ScriptedOpener(http_error(429), urllib.error.URLError("example refusal"), b"ok")
        self.assertEqual(self.client(opener).get(URL), b"ok")

    def test_retry_after_is_honoured_but_capped(self):
        opener = ScriptedOpener(http_error(429, {"Retry-After": "30"}),
                                http_error(429, {"Retry-After": "999"}), b"ok")
        self.client(opener, max_retry_after=60.0).get(URL)
        self.assertEqual(self.slept, [30.0, 60.0])

    def test_a_rejected_request_is_never_retried_and_keeps_the_providers_reason(self):
        body = json.dumps({"error": {"message": "Example: model is not available."}}).encode()
        opener = ScriptedOpener(http_error(404, body=body))
        with self.assertRaises(HttpRejected) as caught:
            self.client(opener).get(URL)
        self.assertEqual((opener.calls, self.slept), (1, []))
        self.assertIn("model is not available", str(caught.exception))

    def test_a_retryable_failure_never_carries_provider_text(self):
        """Its message is stored on DELAYED documents (as D-11)."""
        body = json.dumps({"error": {"message": "PROVIDER TEXT"}}).encode()
        opener = ScriptedOpener(http_error(503, body=body))
        with self.assertRaises(HttpUnavailable) as caught:
            self.client(opener, delays=()).get(URL)
        self.assertNotIn("PROVIDER TEXT", str(caught.exception))

    def test_without_a_policy_there_is_one_attempt(self):
        opener = ScriptedOpener(http_error(503))
        with self.assertRaises(HttpUnavailable) as caught:
            HttpClient(sleep=self.fail, opener=opener).get(URL)
        self.assertNotIn("attempts", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
