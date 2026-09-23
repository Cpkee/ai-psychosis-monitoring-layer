"""Seed extraction prompt and reply schema.

Vocabularies are injected at render time from the same configuration the seed
validator enforces, so the prompt, the schema and the validator cannot drift
apart. The rendered version is ``<template>#<hash>``, where the hash covers the
template, the vocabulary, the schema and the limits: edit any of them without
bumping the template name and the cache key still changes.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
from typing import Any, Dict, Mapping

from src.modules.analysis.definitions import UnknownVersion
from src.modules.seeds.config import CONFIG_DIR, ExtractionConfig, SeedVocabulary

_HEADER = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)
TRUNCATED = "\n[Document truncated here.]"


@dataclasses.dataclass(frozen=True)
class RenderedPrompt:
    version: str
    text: str
    schema: Mapping[str, Any]


def reply_schema(vocabulary: SeedVocabulary) -> Dict[str, Any]:
    """The reply shape, in the OpenAPI subset Gemini's responseSchema accepts."""
    nullable_string = {"type": "string", "nullable": True}
    seed = {
        "type": "object",
        "properties": {
            "theme_family": {"type": "string", "enum": sorted(vocabulary.theme_families),
                             "nullable": True},
            "raw_theme_terms": {"type": "array", "items": {"type": "string"}},
            "stated_age": {"type": "integer", "nullable": True},
            "age_evidence": nullable_string,
            "arc_summary": {"type": "string"},
            "reported_phase_progression": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(vocabulary.phases)}},
            "explicitness_candidate": {"type": "string", "enum": list(vocabulary.explicitness)},
            "harm_type_candidate": nullable_string,
            "companion_behaviour_reported": {
                "type": "array",
                "items": {"type": "string", "enum": sorted(vocabulary.companion_behaviours)}},
        },
    }
    seed["required"] = list(seed["properties"])
    return {
        "type": "object",
        "properties": {"seeds": {"type": "array", "items": seed}},
        "required": ["seeds"],
    }


class PromptRenderer:
    def __init__(self, config: ExtractionConfig, vocabulary: SeedVocabulary,
                 config_dir: str = CONFIG_DIR):
        path = os.path.join(config_dir, "{}.md".format(config.prompt_template))
        if not os.path.exists(path):
            raise UnknownVersion("No extraction prompt {!r}.".format(config.prompt_template))
        with open(path, "r", encoding="utf-8") as handle:
            self._template = _HEADER.sub("", handle.read())
        self._config = config
        self._vocabulary = vocabulary
        self._schema = reply_schema(vocabulary)
        fingerprint = json.dumps(
            {
                "template": self._template,
                "vocabulary": dataclasses.asdict(vocabulary),
                "schema": self._schema,
                "limits": [config.max_document_chars, config.max_quote_chars],
            },
            sort_keys=True,
        )
        self._version = "{}#{}".format(
            config.prompt_template, hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:12]
        )

    @property
    def version(self) -> str:
        return self._version

    def render(self, document_text: str) -> RenderedPrompt:
        limit = self._config.max_document_chars
        shown = document_text if len(document_text) <= limit else document_text[:limit] + TRUNCATED
        values = {
            "{theme_lines}": _lines(self._vocabulary.theme_families),
            "{phase_lines}": _lines(self._vocabulary.phases),
            "{explicitness_values}": ", ".join(
                '"{}"'.format(v) for v in self._vocabulary.explicitness),
            "{behaviour_lines}": _lines(self._vocabulary.companion_behaviours),
            "{max_quote_chars}": str(self._config.max_quote_chars),
        }
        text = self._template
        for placeholder, value in values.items():
            text = text.replace(placeholder, value)
        # The document goes in last, so text inside it is never treated as a placeholder.
        text = text.replace("{document}", shown)
        return RenderedPrompt(version=self._version, text=text, schema=self._schema)


def _lines(entries: Mapping[str, str]) -> str:
    return "\n".join("  - `{}`: {}".format(code, meaning) for code, meaning in entries.items())
