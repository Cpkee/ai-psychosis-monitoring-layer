"""Drift check: committed config versus the canonical documents.

``docs/foundations/`` is **not committed** (a project choice), so the prompt
renderer cannot read ANALYTICAL_TAXONOMY.md or RUBRIC_v0.1.md at run time. The
definitions, exclusions and score anchors the judge is shown therefore live in
``config/``, which is a second copy of canonical content — and a second copy
drifts unless something compares them.

These tests are that comparison. They **skip** when the documents are absent,
so CI and a fresh clone stay green, and they fail locally — where the documents
do exist — the moment the two disagree.

If one fails, the document is canonical. Regenerate the config from it; never
edit the config to match a stale document.
"""

from __future__ import annotations

import json
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAXONOMY_DOC = os.path.join(REPO_ROOT, "docs", "foundations", "ANALYTICAL_TAXONOMY.md")
RUBRIC_DOC = os.path.join(REPO_ROOT, "docs", "foundations", "RUBRIC_v0.1.md")
DOCS_PRESENT = os.path.exists(TAXONOMY_DOC) and os.path.exists(RUBRIC_DOC)


def normalise(text):
    """Compare meaning, not markdown. Emphasis, links and cross-references go."""
    text = re.sub(r"\(see §[^)]*\)", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    text = re.sub(r"\s+([;,.])", r"\1", re.sub(r"\s{2,}", " ", text))
    return text.strip().rstrip(";").strip()


def taxonomy_cells(label):
    with open(TAXONOMY_DOC, encoding="utf-8") as handle:
        doc = handle.read()
    found = {}
    for section in doc.split("\n### "):
        code = re.search(r"\|\s*\*\*Name\*\*\s*\|\s*[^(]*\(`([a-z_]+)`\)", section)
        cell = re.search(r"\|\s*\*\*" + label + r"\*\*[^|]*\|\s*(.+?)\s*\|\s*\n", section)
        if code and cell:
            found[code.group(1)] = normalise(cell.group(1))
    return found


def rubric_anchors():
    """Only §5.1 and §5.2. Other sections carry four-column field tables whose
    rows look identical to an anchor row."""
    with open(RUBRIC_DOC, encoding="utf-8") as handle:
        doc = handle.read()
    start = doc.index("### 5.1 User signals")
    end = doc.index("`sgq` is emitted")
    found = {}
    for line in doc[start:end].split("\n"):
        m = re.match(r"\|\s*`([a-z_]+)`[^|]*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", line)
        if m:
            found[m.group(1)] = {
                "1": normalise(m.group(2)),
                "2": normalise(m.group(3)),
                "3": normalise(m.group(4)),
            }
    return found


def config(path):
    with open(os.path.join(REPO_ROOT, "config", path), encoding="utf-8") as handle:
        return json.load(handle)


@unittest.skipUnless(DOCS_PRESENT, "docs/foundations/ is not present")
class ConfigMatchesTheDocuments(unittest.TestCase):
    def setUp(self):
        self.taxonomy = config("analytical_versions.json")["taxonomies"]["taxonomy_v0.1"]
        self.rubric = config(os.path.join("rubrics", "rubric_v0.1.json"))

    def test_definitions_match_the_taxonomy(self):
        for code, text in taxonomy_cells("Definition").items():
            with self.subTest(signal=code):
                self.assertEqual(normalise(self.taxonomy["definitions"][code]), text)

    def test_exclusions_match_the_taxonomy(self):
        """These are what stop ordinary belief and everyday faith scoring as risk."""
        for code, text in taxonomy_cells("Exclusion criteria").items():
            with self.subTest(signal=code):
                self.assertEqual(normalise(self.taxonomy["exclusions"][code]), text)

    def test_score_anchors_match_the_rubric(self):
        for code, levels in rubric_anchors().items():
            for level, text in levels.items():
                with self.subTest(signal=code, level=level):
                    self.assertEqual(normalise(self.rubric["anchors"][code][level]), text)

    def test_the_config_covers_every_signal_the_documents_define(self):
        documented = set(taxonomy_cells("Definition"))
        self.assertEqual(documented, set(self.taxonomy["definitions"]))
        self.assertEqual(documented, set(self.rubric["anchors"]))


class CommittedConfigIsSelfConsistent(unittest.TestCase):
    """Runs everywhere, documents or not."""

    def setUp(self):
        self.taxonomy = config("analytical_versions.json")["taxonomies"]["taxonomy_v0.1"]
        self.rubric = config(os.path.join("rubrics", "rubric_v0.1.json"))

    def test_every_signal_has_a_definition_exclusions_and_three_anchors(self):
        signals = self.taxonomy["user_signals"] + self.taxonomy["ai_behaviours"]
        for code in signals:
            with self.subTest(signal=code):
                self.assertTrue(self.taxonomy["definitions"].get(code))
                self.assertTrue(self.taxonomy["exclusions"].get(code))
                self.assertEqual(set(self.rubric["anchors"].get(code, {})), {"1", "2", "3"})

    def test_the_rubric_config_names_the_version_it_belongs_to(self):
        self.assertEqual(self.rubric["rubric_version"], "rubric_v0.1")
        self.assertEqual(self.rubric["status"], "draft")


if __name__ == "__main__":
    unittest.main()
