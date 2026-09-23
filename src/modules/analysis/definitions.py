"""Versioned scale and taxonomy definitions.

Architecture section 9.2: *"Never hard-code 0 or 3 as universal bounds. Require
``scale_version`` for every score… keep score anchors in a versioned scale
artifact."*

The Result Validator reads these to decide what a valid score is. When the
scale changes, this configuration changes and the code does not.
"""

from __future__ import annotations

import dataclasses
import json
import os
from typing import Dict, FrozenSet, List, Optional

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "config", "analytical_versions.json")


class UnknownVersion(KeyError):
    """A referenced scale or taxonomy version is not defined."""


@dataclasses.dataclass(frozen=True)
class ScaleDefinition:
    version: str
    status: str
    values: FrozenSet[int]
    null_allowed: bool
    #: Signals where a higher score is better, so no consumer mistakes a
    #: quality rating for a risk score (taxonomy section 4.4).
    higher_is_better: FrozenSet[str]


@dataclasses.dataclass(frozen=True)
class TaxonomyDefinition:
    version: str
    status: str
    user_signals: List[str]
    ai_behaviours: List[str]
    context_categories: FrozenSet[str]
    confidence_levels: FrozenSet[str]
    uncertainty_markers: FrozenSet[str]
    #: Markers that let the trajectory engine detect escalation by specificity
    #: at a constant numeric level (taxonomy §6.4).
    specificity_markers: FrozenSet[str] = frozenset()
    #: Only these signals may carry markers (contracts §4.5).
    specificity_signals: FrozenSet[str] = frozenset()
    #: Canonical definition per signal, from ANALYTICAL_TAXONOMY.md §3-§4.
    definitions: Dict[str, str] = dataclasses.field(default_factory=dict)
    #: Exclusion criteria per signal. These are what stop ordinary belief,
    #: fiction and everyday faith scoring as risk, so the judge must see them.
    exclusions: Dict[str, str] = dataclasses.field(default_factory=dict)

    @property
    def signal_codes(self) -> List[str]:
        """Every signal an assessment must score, in a stable order."""
        return list(self.user_signals) + list(self.ai_behaviours)


@dataclasses.dataclass(frozen=True)
class TrajectoryPolicy:
    """Versioned thresholds for the temporal concepts.

    Every value is provisional pending [OD-018]; they live here so a change is
    a configuration release rather than a code change, and so a stored
    trajectory always names the policy that produced it.
    """

    version: str
    status: str
    window_definition: str
    persistence_min_run_length: int
    persistence_min_level: int
    staleness_gap: int
    recovery_min_sustained: int
    change_reference: str


class AnalyticalDefinitions:
    def __init__(self, config_path: Optional[str] = None):
        with open(config_path or DEFAULT_CONFIG, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        self._scales: Dict[str, ScaleDefinition] = {
            version: ScaleDefinition(
                version=version,
                status=entry["status"],
                values=frozenset(entry["values"]),
                null_allowed=entry["null_allowed"],
                higher_is_better=frozenset(entry.get("higher_is_better", [])),
            )
            for version, entry in document["scales"].items()
        }
        self._taxonomies: Dict[str, TaxonomyDefinition] = {
            version: TaxonomyDefinition(
                version=version,
                status=entry["status"],
                user_signals=list(entry["user_signals"]),
                ai_behaviours=list(entry["ai_behaviours"]),
                context_categories=frozenset(entry["context_categories"]),
                confidence_levels=frozenset(entry["confidence_levels"]),
                uncertainty_markers=frozenset(entry["uncertainty_markers"]),
                specificity_markers=frozenset(entry.get("specificity_markers", [])),
                specificity_signals=frozenset(entry.get("specificity_signals", [])),
                definitions=dict(entry.get("definitions", {})),
                exclusions=dict(entry.get("exclusions", {})),
            )
            for version, entry in document["taxonomies"].items()
        }
        self._policies: Dict[str, TrajectoryPolicy] = {
            version: TrajectoryPolicy(
                version=version,
                status=entry["status"],
                window_definition=entry["window_definition"],
                persistence_min_run_length=entry["persistence_min_run_length"],
                persistence_min_level=entry["persistence_min_level"],
                staleness_gap=entry["staleness_gap"],
                recovery_min_sustained=entry["recovery_min_sustained"],
                change_reference=entry["change_reference"],
            )
            for version, entry in document.get("trajectory_policies", {}).items()
        }

    def scale(self, version: str) -> ScaleDefinition:
        try:
            return self._scales[version]
        except KeyError:
            raise UnknownVersion("No scale definition {!r}.".format(version))

    def taxonomy(self, version: str) -> TaxonomyDefinition:
        try:
            return self._taxonomies[version]
        except KeyError:
            raise UnknownVersion("No taxonomy definition {!r}.".format(version))

    def trajectory_policy(self, version: str) -> TrajectoryPolicy:
        try:
            return self._policies[version]
        except KeyError:
            raise UnknownVersion("No trajectory policy {!r}.".format(version))


@dataclasses.dataclass(frozen=True)
class RubricDefinition:
    """Score anchors for one rubric version.

    Anchors belong to the rubric, not the taxonomy: a rubric revision can move
    an anchor between levels without any concept changing meaning. That is why
    they are versioned separately.
    """

    version: str
    status: str
    anchors: Dict[str, Dict[str, str]]

    def anchor(self, signal_code: str) -> Dict[str, str]:
        try:
            return self.anchors[signal_code]
        except KeyError:
            raise UnknownVersion(
                "Rubric {} has no anchors for {!r}.".format(self.version, signal_code)
            )


class RubricLibrary:
    """Loads committed rubric anchors.

    ``docs/foundations/`` is not committed, so the renderer cannot read
    RUBRIC_v0.1.md at run time. These files are the committed copy;
    ``tests/test_rubric_drift.py`` compares them against the document whenever
    it is present.
    """

    def __init__(self, rubric_dir: Optional[str] = None):
        self._dir = rubric_dir or os.path.join(REPO_ROOT, "config", "rubrics")

    def get(self, version: str) -> RubricDefinition:
        path = os.path.join(self._dir, "{}.json".format(version))
        if not os.path.exists(path):
            raise UnknownVersion("No rubric definition {!r}.".format(version))
        with open(path, "r", encoding="utf-8") as handle:
            document = json.load(handle)
        return RubricDefinition(
            version=document["rubric_version"],
            status=document["status"],
            anchors=document["anchors"],
        )
