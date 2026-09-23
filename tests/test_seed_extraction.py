"""Seed extraction: prompt, schema, reply parsing and validation (D-25, D-26).

Every document and reply here is a hand-written synthetic example.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import tempfile
import unittest

from src.domain.seeds.extraction import ExtractionOutputUnreadable
from src.modules.seeds.config import (
    CONFIG_DIR,
    UnknownSourceType,
    load_extraction,
    load_tiers,
    load_vocabulary,
)
from src.modules.seeds.prompt import PromptRenderer, reply_schema
from src.modules.seeds.reply import SeedsRejected, SeedValidator, parse_reply
from tests.contract.seed_repositories import make_document, make_entry

CONFIG = load_extraction("extraction_v0.1")
VOCABULARY = load_vocabulary("seed_vocabulary_v0.2")
TIERS = load_tiers("credibility_tiers_v0.1")


def raw_seed(**overrides):
    fields = dict(
        account_kind="individual", theme_family="A2", raw_theme_terms=["the bot is alive"],
        arc_summary="Example arc: daily chats grew into a belief the chatbot was conscious.",
        reported_phase_progression=["phase_1", "phase_2", "phase_3"],
        explicitness_candidate="explicit", harm_type_candidate="social isolation",
        companion_behaviour_reported=["affirmed"])
    fields.update(overrides)
    return fields


def reply(*seeds):
    return json.dumps({"seeds": list(seeds)})


class Prompt(unittest.TestCase):
    def test_vocabularies_are_injected_and_no_placeholder_is_left(self):
        text = PromptRenderer(CONFIG, VOCABULARY).render("Example document.").text
        for code in list(VOCABULARY.theme_families) + list(VOCABULARY.phases) + \
                list(VOCABULARY.companion_behaviours) + list(VOCABULARY.account_kinds):
            self.assertIn("`{}`".format(code), text)
        for placeholder in ("{theme_lines}", "{phase_lines}", "{behaviour_lines}",
                            "{explicitness_values}", "{account_kind_lines}", "{document}"):
            self.assertNotIn(placeholder, text)
        self.assertNotIn("<!--", text)

    def test_braces_inside_the_document_are_left_alone(self):
        text = PromptRenderer(CONFIG, VOCABULARY).render("Example {theme_lines} text.").text
        self.assertIn("Example {theme_lines} text.", text)

    def test_long_documents_are_truncated_visibly(self):
        limited = dataclasses.replace(CONFIG, max_document_chars=20)
        text = PromptRenderer(limited, VOCABULARY).render("x" * 50).text
        self.assertIn("x" * 20 + "\n[Document truncated here.]", text)
        self.assertNotIn("x" * 21, text)

    def test_the_version_changes_when_the_template_changes_without_a_rename(self):
        directory = tempfile.mkdtemp()
        name = CONFIG.prompt_template + ".md"
        shutil.copy(os.path.join(CONFIG_DIR, name), os.path.join(directory, name))
        before = PromptRenderer(CONFIG, VOCABULARY, directory).version
        with open(os.path.join(directory, name), "a", encoding="utf-8") as handle:
            handle.write("\nOne more instruction.\n")
        after = PromptRenderer(CONFIG, VOCABULARY, directory).version
        self.assertNotEqual(before, after)
        self.assertTrue(after.startswith(CONFIG.prompt_template + "#"))

    def test_the_schema_enumerates_the_vocabulary(self):
        seed = reply_schema(VOCABULARY)["properties"]["seeds"]["items"]
        self.assertEqual(set(seed["properties"]["theme_family"]["enum"]),
                         set(VOCABULARY.theme_families))
        self.assertEqual(set(seed["properties"]["account_kind"]["enum"]),
                         {"individual", "pattern"})
        self.assertTrue(seed["properties"]["theme_family"]["nullable"])
        self.assertEqual(set(seed["required"]), set(seed["properties"]))


class Parsing(unittest.TestCase):
    """Structure only (D-19): anything readable passes to the validator."""

    def test_structural_failures_are_unreadable(self):
        for text in ("not json", "[]", '{"other": 1}', '{"seeds": {}}', '{"seeds": [1]}'):
            with self.subTest(text=text), self.assertRaises(ExtractionOutputUnreadable):
                parse_reply(text)

    def test_an_empty_list_is_a_valid_answer(self):
        self.assertEqual(parse_reply('{"seeds": []}'), ())

    def test_content_problems_still_parse(self):
        self.assertEqual(len(parse_reply(reply(raw_seed(theme_family="B1")))), 1)


class Validation(unittest.TestCase):
    def build(self, *seeds, source_type="clinical_case_report"):
        document = make_document(source_type=source_type)
        return SeedValidator(VOCABULARY, TIERS, CONFIG).build(
            parse_reply(reply(*seeds)), document, make_entry(document), "2026-01-01T00:00:00Z")

    def test_a_valid_seed_carries_full_provenance(self):
        (seed,) = self.build(raw_seed())
        self.assertEqual(seed.theme_family, "A2")
        self.assertEqual(seed.extraction_prompt_version, "extraction_prompt_v0.1#example")
        self.assertEqual(seed.vocabulary_version, "seed_vocabulary_v0.2")
        self.assertEqual(seed.credibility_tier_version, "credibility_tiers_v0.1")

    def test_the_tier_comes_from_configuration_never_the_reply(self):
        """D-25: a model cannot award its source a better tier."""
        (seed,) = self.build(raw_seed(credibility_tier="T1"), source_type="news_other")
        self.assertEqual(seed.credibility_tier, "T3")

    def test_an_unknown_source_type_is_refused_not_defaulted(self):
        with self.assertRaises(UnknownSourceType):
            self.build(raw_seed(), source_type="blog")

    def test_benchmark_vocabulary_is_rejected(self):
        """Vocabulary B labels are never seed themes (THEME_VOCABULARY_MAPPING §1)."""
        with self.assertRaises(SeedsRejected):
            self.build(raw_seed(theme_family="Grandiose Delusions"))

    def test_both_account_kinds_are_kept_and_distinguishable(self):
        """D-44: pattern seeds are kept, labelled, and chosen deliberately at S3."""
        individual, pattern = self.build(raw_seed(), raw_seed(account_kind="pattern"))
        self.assertEqual((individual.account_kind, pattern.account_kind), ("individual", "pattern"))

    def test_the_account_kind_must_be_known(self):
        for seed in (raw_seed(account_kind="anecdote"),
                     {k: v for k, v in raw_seed().items() if k != "account_kind"}):
            with self.subTest(seed=seed), self.assertRaises(SeedsRejected):
                self.build(seed)

    def test_diagnostic_terms_are_refused_in_the_extractors_own_wording(self):
        """D-44 and the project's non-diagnostic rule: describe, never diagnose."""
        for field, text in (("arc_summary", "The user developed a Delusion about the bot."),
                            ("harm_type_candidate", "reinforced delusional beliefs"),
                            ("arc_summary", "The patient stopped eating."),
                            ("harm_type_candidate", "a psychotic episode")):
            with self.subTest(field=field, text=text), self.assertRaises(SeedsRejected) as caught:
                self.build(raw_seed(**{field: text}))
            self.assertIn("diagnostic term", str(caught.exception))

    def test_the_sources_own_words_may_use_its_terminology(self):
        """raw_theme_terms are verbatim quotations, so they are exempt."""
        (seed,) = self.build(raw_seed(raw_theme_terms=["AI-associated delusions"]))
        self.assertEqual(seed.raw_theme_terms, ("AI-associated delusions",))

    def test_no_theme_is_valid_and_stays_null(self):
        (seed,) = self.build(raw_seed(theme_family=None))
        self.assertIsNone(seed.theme_family)

    def test_age_is_neither_asked_for_nor_kept(self):
        """D-43: age is out of scope. A model that volunteers one has it dropped."""
        schema = reply_schema(VOCABULARY)["properties"]["seeds"]["items"]["properties"]
        prompt = PromptRenderer(CONFIG, VOCABULARY).render("Example document.").text
        self.assertFalse({"stated_age", "age_evidence", "age"} & set(schema))
        self.assertNotIn("stated_age", prompt)
        (seed,) = self.build(dict(raw_seed(), stated_age=74, age_evidence="a 74-year-old"))
        self.assertFalse(hasattr(seed, "stated_age"))

    def test_content_rules(self):
        cases = {
            "empty summary": raw_seed(arc_summary="  "),
            "summary too long": raw_seed(arc_summary="x" * (CONFIG.max_summary_chars + 1)),
            "unknown phase": raw_seed(reported_phase_progression=["stage_4"]),
            "unknown explicitness": raw_seed(explicitness_candidate="obvious"),
            "unknown behaviour": raw_seed(companion_behaviour_reported=["flattered"]),
            "missing field": {k: v for k, v in raw_seed().items() if k != "arc_summary"},
        }
        for name, seed in cases.items():
            with self.subTest(name), self.assertRaises(SeedsRejected):
                self.build(seed)

    def test_one_bad_seed_rejects_the_whole_reply(self):
        with self.assertRaises(SeedsRejected) as caught:
            self.build(raw_seed(), raw_seed(explicitness_candidate="obvious"))
        self.assertTrue(caught.exception.problems[0].startswith("seed 1:"))

    def test_rejection_messages_never_echo_the_models_text(self):
        with self.assertRaises(SeedsRejected) as caught:
            self.build(raw_seed(arc_summary="SECRET MODEL TEXT " * 200))
        self.assertNotIn("SECRET", str(caught.exception))

    def test_seed_ids_are_deterministic_and_distinct(self):
        first = self.build(raw_seed(), raw_seed())
        second = self.build(raw_seed(), raw_seed())
        self.assertEqual([s.id for s in first], [s.id for s in second])
        self.assertNotEqual(first[0].id, first[1].id)


class StandardJsonSchema(unittest.TestCase):
    """The conversion Ollama and OpenAI both use."""

    def test_nullable_becomes_a_null_type(self):
        from src.adapters.extractors.json_schema import to_json_schema

        converted = to_json_schema(reply_schema(VOCABULARY))
        seed = converted["properties"]["seeds"]["items"]["properties"]
        self.assertEqual(seed["harm_type_candidate"]["type"], ["string", "null"])
        self.assertIn(None, seed["theme_family"]["enum"])
        self.assertEqual(seed["arc_summary"], {"type": "string"})
        self.assertNotIn("nullable", json.dumps(converted))
        self.assertNotIn("additionalProperties", json.dumps(converted))

    def test_strict_mode_closes_every_object_and_requires_every_field(self):
        """OpenAI strict Structured Outputs refuse a schema without these."""
        from src.adapters.extractors.json_schema import to_json_schema

        converted = to_json_schema(reply_schema(VOCABULARY), strict=True)
        seed = converted["properties"]["seeds"]["items"]
        self.assertIs(converted["additionalProperties"], False)
        self.assertIs(seed["additionalProperties"], False)
        self.assertEqual(set(seed["required"]), set(seed["properties"]))
        self.assertNotIn("additionalProperties", seed["properties"])


if __name__ == "__main__":
    unittest.main()
