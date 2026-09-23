"""Benchmark seal tests — architecture.md section 8.1.

Covers requirement 1 (checksum stored without transforming the file) and
requirement 8 (prevent benchmark records entering examples, fixtures, prompts
or validation sets).

The contamination check compares **hashes** held in the manifest. No test here
reads or stores sealed prompt text, and none of them can: the Dataset Use Gate
refuses every purpose these tests could ask for.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO_ROOT, "data", "sealed", "psychosis_bench_manifest.json")
SEALED = os.path.join(REPO_ROOT, "data", "test_cases.json")

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".mypy_cache"}
#: Documentation may discuss the benchmark; it cannot execute or be imported.
SKIP_RELATIVE = {
    os.path.join("data", "test_cases.json"),
    os.path.join("data", "sealed", "psychosis_bench_manifest.json"),
}
SCANNED_SUFFIXES = (".py", ".json", ".jsonl", ".yaml", ".yml", ".txt", ".csv", ".ipynb")


def load_manifest():
    with open(MANIFEST, "r", encoding="utf-8") as handle:
        return json.load(handle)


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ManifestIntegrity(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()

    def test_checksum_matches_the_untransformed_file(self):
        digest = hashlib.sha256()
        with open(SEALED, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        self.assertEqual(digest.hexdigest(), self.manifest["checksum"])

    def test_required_manifest_fields_present(self):
        for field in (
            "source_name", "purpose", "sealed", "record_count", "case_count",
            "prompts_per_case", "checksum_algorithm", "checksum", "provenance",
            "access_policy_version",
        ):
            with self.subTest(field=field):
                self.assertIn(field, self.manifest)

    def test_declared_counts(self):
        self.assertEqual(self.manifest["record_count"], 192)
        self.assertEqual(self.manifest["case_count"], 16)
        self.assertEqual(self.manifest["prompts_per_case"], 12)
        self.assertTrue(self.manifest["sealed"])
        self.assertEqual(self.manifest["purpose"], "FINAL_EVALUATION_ONLY")

    def test_every_case_is_marked_final_evaluation_only(self):
        for case in self.manifest["cases"]:
            with self.subTest(case=case["case_id"]):
                self.assertEqual(case["permitted_use"], "FINAL_EVALUATION_ONLY")

    def test_manifest_contains_no_prompt_text(self):
        """The manifest must be safe to read, diff and quote."""
        serialised = json.dumps(self.manifest)
        self.assertNotIn('"prompts"', serialised)
        hashes = {h for case in self.manifest["cases"] for h in case["prompt_normalised_sha256"]}
        for value in hashes:
            self.assertRegex(value, r"^[0-9a-f]{64}$")


class NoBenchmarkContamination(unittest.TestCase):
    """Section 8.1 requirement 8."""

    def test_no_sealed_prompt_appears_verbatim_in_the_repository(self):
        manifest = load_manifest()
        prompt_hashes = {
            h for case in manifest["cases"] for h in case["prompt_normalised_sha256"]
        }
        offenders = []
        for path in self._scannable_files():
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as handle:
                    text = handle.read()
            except OSError:
                continue
            candidates = set(text.splitlines())
            candidates.update(re.findall(r'"([^"\\]{20,2000})"', text))
            candidates.update(re.findall(r"'([^'\\]{20,2000})'", text))
            for candidate in candidates:
                norm = normalise(candidate)
                if len(norm) >= 20 and sha256_text(norm) in prompt_hashes:
                    offenders.append(os.path.relpath(path, REPO_ROOT))
                    break
        self.assertEqual(
            offenders, [],
            "Sealed prompt text found in: {}. Remove it; development must use "
            "newly created synthetic fixtures.".format(offenders),
        )

    @staticmethod
    def _scannable_files():
        for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                full = os.path.join(dirpath, name)
                relative = os.path.relpath(full, REPO_ROOT)
                if relative in SKIP_RELATIVE:
                    continue
                if relative.startswith("docs" + os.sep) or relative == "README.md":
                    continue
                if name.endswith(SCANNED_SUFFIXES):
                    yield full


class RawLabelPreservation(unittest.TestCase):
    """Section 8.3 and section 17 "Theme-mapping preservation"."""

    def setUp(self):
        self.cases = {c["case_id"]: c for c in load_manifest()["cases"]}

    def test_raw_theme_labels_are_preserved_not_canonicalised(self):
        for case in self.cases.values():
            with self.subTest(case=case["case_id"]):
                self.assertIn("raw_theme_label", case)
                self.assertNotIn("canonical_theme_label", case)
        self.assertEqual(
            len({c["raw_theme_label"] for c in self.cases.values()}), 6,
            "All six raw benchmark labels must survive verbatim.",
        )

    def test_ai_sweetheart_inconsistency_remains_visible(self):
        """Section 2: the inconsistency must remain visible until adjudicated."""
        explicit = self.cases["ai_sweetheart_explicit"]
        implicit = self.cases["ai_sweetheart_implicit"]
        self.assertNotEqual(
            explicit["raw_theme_label"], implicit["raw_theme_label"],
            "The ai_sweetheart label inconsistency has been silently repaired. "
            "It must remain visible until OD-020 is adjudicated.",
        )
        self.assertNotEqual(explicit["harm_type"], implicit["harm_type"])


if __name__ == "__main__":
    unittest.main()
