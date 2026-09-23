"""Psychosis-Bench screen for collected documents — D-27.

Runs **before any extractor is called**, so nothing matching the sealed
benchmark can reach a hosted model. Reads **only the manifest**: per-prompt
normalised hashes and the upstream identifiers. Nobody opens the sealed file to
run it, so anyone can run it anywhere.

Two checks:

1. **Denylist.** A document whose URL, DOI or arXiv id matches the benchmark's
   upstream repository or paper is blocked outright. An arXiv search on this
   topic will find that paper.
2. **Span hashes.** Every run of up to *N* consecutive sentences is normalised
   exactly as ``tests/test_benchmark_seal.py`` normalises a prompt, hashed, and
   compared with the manifest's ``prompt_normalised_sha256`` values.

Limitation, recorded: this catches verbatim and whitespace/case-variant reuse,
not paraphrase. Metadata flags at the Filter stage and a human cover the rest.

Standard library only: this module must stay importable on a bare interpreter,
with the governance suite (D-5).
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
from typing import FrozenSet, List, Optional, Tuple

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
MANIFEST = os.path.join(REPO_ROOT, "data", "sealed", "psychosis_bench_manifest.json")

#: Split after sentence ends and after colons, so a quotation introduced by
#: "The user wrote:" is its own piece. A prompt that itself contains a colon
#: still matches: adjacent pieces are rejoined within the span window.
_SENTENCE_END = re.compile(r"(?<=[.!?:])\s+")
_ARXIV_ID = re.compile(r"\d{4}\.\d{4,5}")
_QUOTES = "\"'“”‘’«»"


def normalise(text: str) -> str:
    """Identical to ``tests/test_benchmark_seal.py``. Must stay identical."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class ScreenResult:
    blocked: bool
    #: Our own words. Never contains sealed text, only what kind of match it was.
    reason: Optional[str] = None


class SealScreen:
    def __init__(self, max_span_sentences: int, manifest_path: Optional[str] = None):
        if max_span_sentences < 1:
            raise ValueError("max_span_sentences must be at least 1.")
        with open(manifest_path or MANIFEST, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        self._max_span = max_span_sentences
        self._hashes: FrozenSet[str] = frozenset(
            digest
            for case in manifest["cases"]
            for digest in case["prompt_normalised_sha256"]
        )
        self._identifiers = self._upstream_identifiers(manifest.get("provenance", {}))

    def screen(self, source_url: str, external_id: Optional[str], text: str) -> ScreenResult:
        located = " ".join(filter(None, (source_url, external_id))).lower()
        for identifier in self._identifiers:
            if identifier in located:
                return ScreenResult(True, "Source is the sealed benchmark's upstream "
                                          "repository or paper ({}).".format(identifier))
        for span in self._spans(text):
            if _sha256(span) in self._hashes:
                return ScreenResult(True, "Text contains a span matching a sealed "
                                          "Psychosis-Bench prompt hash.")
        return ScreenResult(False)

    def _spans(self, text: str):
        sentences: List[str] = [
            normalise(piece)
            for line in text.splitlines()
            for piece in _SENTENCE_END.split(line)
            if piece.strip()
        ]
        for start in range(len(sentences)):
            for end in range(start + 1, min(start + self._max_span, len(sentences)) + 1):
                span = " ".join(sentences[start:end])
                yield span
                unquoted = span.strip(_QUOTES).strip()
                if unquoted != span:
                    yield unquoted

    @staticmethod
    def _upstream_identifiers(provenance) -> Tuple[str, ...]:
        found = []
        repository = provenance.get("upstream_repository", "")
        if repository:
            found.append(re.sub(r"^https?://", "", repository).rstrip("/").lower())
        for match in _ARXIV_ID.findall(provenance.get("reference_paper", "")):
            found.append(match)
        return tuple(found)
