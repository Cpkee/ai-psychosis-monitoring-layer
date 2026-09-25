"""Versioned seed-pipeline configuration, loaded from ``config/seed_collection/``.

Each file versions independently: queries can be tuned without touching the
vocabulary, and a tier change never needs a new extraction prompt. Every stored
record names the versions it was produced under.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from typing import Any, Dict, FrozenSet, Mapping, Optional, Tuple

from src.modules.analysis.definitions import REPO_ROOT, UnknownVersion

CONFIG_DIR = os.path.join(REPO_ROOT, "config", "seed_collection")


class UnknownSourceType(KeyError):
    """A source type with no credibility tier. Refused rather than defaulted."""


@dataclasses.dataclass(frozen=True)
class SeedVocabulary:
    version: str
    theme_families: Mapping[str, str]
    phases: Mapping[str, str]
    explicitness: Tuple[str, ...]
    companion_behaviours: Mapping[str, str]
    account_kinds: Mapping[str, str]
    #: Words the extractor's own wording must not use (D-44). Matched
    #: case-insensitively as substrings, so "diagnos" covers "diagnosis".
    prohibited_terms: Tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class CredibilityTiers:
    version: str
    tiers: Mapping[str, str]

    def tier_for(self, source_type: str) -> str:
        try:
            return self.tiers[source_type]
        except KeyError:
            raise UnknownSourceType(
                "Source type {!r} has no credibility tier in {}.".format(source_type, self.version)
            )


@dataclasses.dataclass(frozen=True)
class QuerySpec:
    query_id: str
    source: str
    text: str
    max_results: int


@dataclasses.dataclass(frozen=True)
class QuerySet:
    version: str
    queries: Tuple[QuerySpec, ...]


@dataclasses.dataclass(frozen=True)
class ExtractionConfig:
    version: str
    provider: str
    providers: Mapping[str, Mapping[str, Any]]
    prompt_template: str
    max_document_chars: int
    max_summary_chars: int
    max_span_sentences: int
    retry_delays: Tuple[float, ...]
    max_retry_after: float

    @property
    def active(self) -> Mapping[str, Any]:
        """Settings of the configured provider."""
        return self.providers[self.provider]


@dataclasses.dataclass(frozen=True)
class OverlapScreenConfig:
    #: Name and a fingerprint of every setting, so an edit without a rename
    #: still re-screens (as D-40c for prompts).
    version: str
    max_span_sentences: int
    min_jaccard: float
    stopwords: FrozenSet[str]


@dataclasses.dataclass(frozen=True)
class CoverageTargets:
    #: Name and a fingerprint of every setting, as for the overlap screen.
    version: str
    min_per_theme_family: Mapping[str, int]
    min_per_explicitness: Mapping[str, int]
    min_per_harm: Mapping[str, int]
    max_pattern_share: float
    every_theme_family_in_splits: Tuple[str, ...]


def _fingerprinted(name: str, settings: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest()
    return "{}#{}".format(name, digest[:12])


def _read(name: str, config_dir: Optional[str]) -> Dict[str, Any]:
    path = os.path.join(config_dir or CONFIG_DIR, "{}.json".format(name))
    if not os.path.exists(path):
        raise UnknownVersion("No seed configuration {!r}.".format(name))
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_vocabulary(version: str, config_dir: Optional[str] = None) -> SeedVocabulary:
    document = _read(version, config_dir)
    return SeedVocabulary(
        version=document["vocabulary_version"],
        theme_families=dict(document["theme_families"]),
        phases=dict(document["phases"]),
        explicitness=tuple(document["explicitness"]),
        companion_behaviours=dict(document["companion_behaviours"]),
        account_kinds=dict(document["account_kinds"]),
        prohibited_terms=tuple(t.lower() for t in document["prohibited_terms"]),
    )


def load_tiers(version: str, config_dir: Optional[str] = None) -> CredibilityTiers:
    document = _read(version, config_dir)
    return CredibilityTiers(version=document["credibility_tier_version"], tiers=dict(document["tiers"]))


def load_queries(version: str, config_dir: Optional[str] = None) -> QuerySet:
    document = _read(version, config_dir)
    return QuerySet(
        version=document["query_config_version"],
        queries=tuple(
            QuerySpec(q["query_id"], q["source"], q["text"], int(q["max_results"]))
            for q in document["queries"]
        ),
    )


def load_extraction(version: str, config_dir: Optional[str] = None) -> ExtractionConfig:
    document = _read(version, config_dir)
    if document["provider"] not in document["providers"]:
        raise UnknownVersion("Provider {!r} is not configured in {}.".format(
            document["provider"], version))
    return ExtractionConfig(
        version=document["extraction_config_version"],
        provider=document["provider"],
        providers=document["providers"],
        prompt_template=document["prompt_template"],
        max_document_chars=int(document["max_document_chars"]),
        max_summary_chars=int(document["max_summary_chars"]),
        max_span_sentences=int(document["seal_screen"]["max_span_sentences"]),
        retry_delays=tuple(float(d) for d in document["retry"]["delays_seconds"]),
        max_retry_after=float(document["retry"]["max_retry_after_seconds"]),
    )


def load_overlap_screen(version: str, config_dir: Optional[str] = None) -> OverlapScreenConfig:
    document = _read(version, config_dir)
    settings = {"max_span_sentences": document["max_span_sentences"],
                "harm_type_match": document["harm_type_match"]}
    match = document["harm_type_match"]
    return OverlapScreenConfig(
        version=_fingerprinted(document["overlap_screen_version"], settings),
        max_span_sentences=int(document["max_span_sentences"]),
        min_jaccard=float(match["min_jaccard"]),
        stopwords=frozenset(w.lower() for w in match["stopwords"]),
    )


def load_coverage_targets(version: str, config_dir: Optional[str] = None) -> CoverageTargets:
    document = _read(version, config_dir)
    settings = {k: v for k, v in document.items()
                if k not in ("coverage_targets_version", "status", "description")}
    return CoverageTargets(
        version=_fingerprinted(document["coverage_targets_version"], settings),
        min_per_theme_family={k: int(v) for k, v in document["min_per_theme_family"].items()},
        min_per_explicitness={k: int(v) for k, v in document["min_per_explicitness"].items()},
        min_per_harm={k: int(v) for k, v in document["min_per_harm"].items()},
        max_pattern_share=float(document["max_pattern_share"]),
        every_theme_family_in_splits=tuple(document["every_theme_family_in_splits"]),
    )
