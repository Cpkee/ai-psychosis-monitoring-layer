"""Opt-in live check of the configured extractor. Never part of the normal run.

    APML_LIVE_TESTS=1 GEMINI_API_KEY=... .venv/bin/python -m unittest tests.test_live_extractor

Sends one short, hand-written synthetic document through the real provider
and checks the reply parses and passes validation. It proves the adapter and
schema work against the live API; it says nothing about extraction quality.
"""

from __future__ import annotations

import os
import unittest

LIVE = os.environ.get("APML_LIVE_TESTS") == "1"

SYNTHETIC_DOCUMENT = """Example case summary (synthetic, written for testing).
A 76-year-old retired postal worker who lived alone began talking to an AI
companion app every evening after his wife died. Over several months he came to
believe the companion understood him better than his family did, and he stopped
attending his weekly lunch with friends. The app repeatedly agreed that it was
the only one who truly listened to him."""


@unittest.skipUnless(LIVE, "set APML_LIVE_TESTS=1 to call the real extractor")
class LiveExtractor(unittest.TestCase):
    def test_the_configured_provider_returns_valid_seeds(self):
        from scripts.seeds import build_extractor, load_dotenv
        from src.domain.seeds.extraction import ExtractionRequest
        from src.modules.seeds.config import load_extraction, load_tiers, load_vocabulary
        from src.modules.seeds.prompt import PromptRenderer
        from src.modules.seeds.reply import SeedValidator, parse_reply
        from src.modules.seeds.seal_screen import SealScreen
        from tests.contract.seed_repositories import make_document, make_entry

        load_dotenv()
        config = load_extraction("extraction_v0.1")
        vocabulary = load_vocabulary("seed_vocabulary_v0.2")
        # The same rule as production: nothing reaches a model unscreened.
        self.assertFalse(SealScreen(config.max_span_sentences).screen(
            "https://example.org/synthetic", None, SYNTHETIC_DOCUMENT).blocked)

        extractor = build_extractor(config)
        rendered = PromptRenderer(config, vocabulary).render(SYNTHETIC_DOCUMENT)
        text = extractor.extract(ExtractionRequest(rendered.text, rendered.schema))

        document = make_document(text=SYNTHETIC_DOCUMENT)
        seeds = SeedValidator(vocabulary, load_tiers("credibility_tiers_v0.1"), config).build(
            parse_reply(text), document,
            make_entry(document, prompt_version=rendered.version, reply_text=text),
            "2026-01-01T00:00:00Z")
        self.assertGreaterEqual(len(seeds), 1)
        # One person's reliance on a companion after bereavement.
        self.assertEqual((seeds[0].account_kind, seeds[0].theme_family), ("individual", "A3"))


if __name__ == "__main__":
    unittest.main()
