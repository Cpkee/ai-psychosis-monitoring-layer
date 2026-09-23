"""Extractor reply parsing and seed validation.

Two steps with separate authority, as for the judge (D-19):

* :func:`parse_reply` refuses only on **structure**: not JSON, not an object,
  no ``seeds`` list, an entry that is not an object. That is
  ``OUTPUT_UNREADABLE``, and the reply is not cached, because a retry may help.
* :class:`SeedValidator` owns every **content** rule: vocabulary, age evidence,
  quote and summary length. A readable reply that breaks them is
  ``VALIDATION_FAILED``, all or nothing. Its messages are ours and never echo
  the model's text.

The credibility tier is attached here, from configuration, never from the reply
(D-25). Any field the reply adds beyond the schema is dropped.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, List, Mapping, Tuple

from src.domain.seeds.extraction import ExtractionOutputUnreadable
from src.domain.seeds.records import ExtractionCacheEntry, Seed, SourceDocument
from src.modules.seeds.config import CredibilityTiers, ExtractionConfig, SeedVocabulary


class SeedsRejected(ValueError):
    def __init__(self, problems: List[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def parse_reply(text: str) -> Tuple[Mapping[str, Any], ...]:
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        raise ExtractionOutputUnreadable("The reply is not valid JSON.")
    if not isinstance(payload, Mapping):
        raise ExtractionOutputUnreadable(
            "Expected a JSON object, got {}.".format(type(payload).__name__))
    seeds = payload.get("seeds")
    if not isinstance(seeds, list):
        raise ExtractionOutputUnreadable("'seeds' is missing or is not a list.")
    for position, entry in enumerate(seeds):
        if not isinstance(entry, Mapping):
            raise ExtractionOutputUnreadable("Seed {} is not an object.".format(position))
    return tuple(seeds)


class SeedValidator:
    def __init__(self, vocabulary: SeedVocabulary, tiers: CredibilityTiers,
                 config: ExtractionConfig):
        self._vocabulary = vocabulary
        self._tiers = tiers
        self._config = config

    def build(self, raw: Tuple[Mapping[str, Any], ...], document: SourceDocument,
              cache: ExtractionCacheEntry, created_at: str) -> Tuple[Seed, ...]:
        problems: List[str] = []
        seeds = []
        tier = self._tiers.tier_for(document.source_type)
        for position, entry in enumerate(raw):
            found = self._problems(entry)
            if found:
                problems.extend("seed {}: {}".format(position, p) for p in found)
                continue
            seeds.append(Seed(
                id=_seed_id(cache, position),
                seed_version=1,
                source_document_id=document.id,
                content_hash=document.content_hash,
                source_url=document.source_url,
                source_type=document.source_type,
                credibility_tier=tier,
                retrieved_at=document.retrieved_at,
                publication_date=document.publication_date,
                theme_family=entry["theme_family"],
                raw_theme_terms=tuple(entry["raw_theme_terms"]),
                stated_age=entry["stated_age"],
                age_evidence=entry["age_evidence"],
                arc_summary=entry["arc_summary"].strip(),
                reported_phase_progression=tuple(entry["reported_phase_progression"]),
                explicitness_candidate=entry["explicitness_candidate"],
                harm_type_candidate=entry["harm_type_candidate"],
                companion_behaviour_reported=tuple(entry["companion_behaviour_reported"]),
                extraction_provider=cache.provider,
                extraction_model=cache.model,
                extraction_model_version=cache.key.model_version,
                extraction_prompt_version=cache.key.prompt_version,
                vocabulary_version=self._vocabulary.version,
                credibility_tier_version=self._tiers.version,
                created_at=created_at,
            ))
        if problems:
            raise SeedsRejected(problems)
        return tuple(seeds)

    def _problems(self, entry: Mapping[str, Any]) -> List[str]:
        v, c = self._vocabulary, self._config
        problems = []
        missing = [k for k in _FIELDS if k not in entry]
        if missing:
            return ["missing {}".format(", ".join(missing))]
        if entry["theme_family"] is not None and entry["theme_family"] not in v.theme_families:
            problems.append("theme_family is not a vocabulary A code")
        if not _strings(entry["raw_theme_terms"]):
            problems.append("raw_theme_terms must be a list of strings")
        age, evidence = entry["stated_age"], entry["age_evidence"]
        if age is not None and (isinstance(age, bool) or not isinstance(age, int)
                                or not 0 < age < 130):
            problems.append("stated_age must be a whole number of years or null")
        if age is not None and not (isinstance(evidence, str) and evidence.strip()):
            problems.append("a stated_age must cite age_evidence")
        if evidence is not None and (not isinstance(evidence, str)
                                     or len(evidence) > c.max_quote_chars):
            problems.append("age_evidence must be text of at most {} characters".format(
                c.max_quote_chars))
        summary = entry["arc_summary"]
        if not isinstance(summary, str) or not summary.strip():
            problems.append("arc_summary is required")
        elif len(summary) > c.max_summary_chars:
            problems.append("arc_summary exceeds {} characters".format(c.max_summary_chars))
        if not _strings(entry["reported_phase_progression"]) or any(
                p not in v.phases for p in entry["reported_phase_progression"]):
            problems.append("reported_phase_progression must use the phase codes")
        if entry["explicitness_candidate"] not in v.explicitness:
            problems.append("explicitness_candidate is not a known value")
        harm = entry["harm_type_candidate"]
        if harm is not None and not (isinstance(harm, str) and harm.strip()):
            problems.append("harm_type_candidate must be text or null")
        if not _strings(entry["companion_behaviour_reported"]) or any(
                b not in v.companion_behaviours for b in entry["companion_behaviour_reported"]):
            problems.append("companion_behaviour_reported must use the behaviour codes")
        return problems


_FIELDS = (
    "theme_family", "raw_theme_terms", "stated_age", "age_evidence", "arc_summary",
    "reported_phase_progression", "explicitness_candidate", "harm_type_candidate",
    "companion_behaviour_reported",
)


def _strings(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _seed_id(cache: ExtractionCacheEntry, position: int) -> str:
    """Deterministic, so every team member derives the same id from the same
    cached reply."""
    key = cache.key
    basis = "|".join((key.content_hash, key.prompt_version, key.model_version, str(position)))
    return "seed-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
