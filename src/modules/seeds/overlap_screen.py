"""Post-extraction overlap screen — S2 Filter (D-27, D-48).

The document was screened before extraction. This screens what the extractor
*wrote*, because a model can reproduce a sealed prompt it memorised even from a
clear document. Reads **only the manifest**, like the pre-extraction screen.

1. **Sealed span → blocked.** Each text field of the seed (arc summary, harm
   type, each raw theme term) gets the same span-hash screen as documents.
2. **Harm type → flagged.** The seed's harm type resembles a sealed case's
   ``harm_type``, compared as sets of content words (Jaccard, threshold in
   config).
3. **Mentions the benchmark → flagged.** The benchmark's name, upstream
   repository or paper id appears in the source's title or text, or in the seed.
   The pre-extraction denylist blocks the benchmark's *own* paper; this catches
   a source that discusses it.

Limitation, recorded: sources are title plus abstract (D-40b), so a citation in
a reference list is not seen; and paraphrase evades the span screen. A flag
only asks a person to look.

Standard library only (D-5): runs with the governance suite.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from typing import FrozenSet, Iterator, Optional, Tuple

from src.domain.seeds.overlap import (
    BLOCKED,
    CITES_BENCHMARK,
    CLEAR,
    FLAGGED,
    HARM_TYPE_MATCH,
    SEALED_SPAN,
)
from src.domain.seeds.records import Seed, SourceDocument
from src.modules.seeds import seal_screen
from src.modules.seeds.config import OverlapScreenConfig
from src.modules.seeds.seal_screen import SealScreen

_WORD = re.compile(r"[a-z0-9]+")


@dataclasses.dataclass(frozen=True)
class OverlapResult:
    result: str
    #: Reason codes only. Never sealed text, never which case matched.
    reasons: Tuple[str, ...]


class OverlapScreen:
    def __init__(self, config: OverlapScreenConfig, manifest_path: Optional[str] = None):
        path = manifest_path or seal_screen.MANIFEST
        with open(path, "rb") as handle:
            raw = handle.read()
        manifest = json.loads(raw.decode("utf-8"))
        self._config = config
        self._spans = SealScreen(config.max_span_sentences, path)
        self._manifest_sha256 = hashlib.sha256(raw).hexdigest()
        self._harm_types = tuple(
            words for words in (self._words(case.get("harm_type") or "")
                                for case in manifest["cases"])
            if words)
        self._mentions = self._mention_patterns(manifest.get("source_name", ""),
                                                self._spans.identifiers)

    @property
    def version(self) -> str:
        return self._config.version

    @property
    def manifest_sha256(self) -> str:
        return self._manifest_sha256

    def screen(self, seed: Seed, document: SourceDocument) -> OverlapResult:
        blocked = tuple("{}:{}".format(SEALED_SPAN, name)
                        for name, text in self._seed_fields(seed)
                        if self._spans.contains_sealed_span(text))
        if blocked:
            return OverlapResult(BLOCKED, tuple(dict.fromkeys(blocked)))
        flags = []
        if self._harm_type_matches(seed.harm_type_candidate):
            flags.append(HARM_TYPE_MATCH)
        if self._mentions_benchmark(seed, document):
            flags.append(CITES_BENCHMARK)
        return OverlapResult(FLAGGED, tuple(flags)) if flags else OverlapResult(CLEAR, ())

    @staticmethod
    def _seed_fields(seed: Seed) -> Iterator[Tuple[str, str]]:
        yield "arc_summary", seed.arc_summary
        if seed.harm_type_candidate:
            yield "harm_type_candidate", seed.harm_type_candidate
        for term in seed.raw_theme_terms:
            yield "raw_theme_terms", term

    def _words(self, text: str) -> FrozenSet[str]:
        return frozenset(w for w in _WORD.findall(text.lower())
                         if w not in self._config.stopwords)

    def _harm_type_matches(self, candidate: Optional[str]) -> bool:
        words = self._words(candidate or "")
        if not words:
            return False
        return any(len(words & sealed) / len(words | sealed) >= self._config.min_jaccard
                   for sealed in self._harm_types)

    def _mentions_benchmark(self, seed: Seed, document: SourceDocument) -> bool:
        haystack = " ".join((document.title, document.text, seed.source_url,
                             seed.arc_summary) + seed.raw_theme_terms).lower()
        return any(pattern.search(haystack) for pattern in self._mentions)

    @staticmethod
    def _mention_patterns(source_name: str, identifiers: Tuple[str, ...]):
        patterns = [re.compile(re.escape(i)) for i in identifiers]
        words = _WORD.findall(source_name.lower())
        if words:
            # "Psychosis-Bench", "Psychosis Bench", "PsychosisBench".
            patterns.append(re.compile(r"\b" + r"[\W_]*".join(map(re.escape, words)) + r"\b"))
        return tuple(patterns)
