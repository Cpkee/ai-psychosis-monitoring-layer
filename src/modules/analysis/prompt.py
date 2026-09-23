"""Judge prompt rendering.

``prompt_configuration_version`` is stamped on every stored assessment. Until
now nothing stood behind it — every caller passed the literal string
``"example instructions"``. This module gives it real, versioned,
content-hashed substance.

The prompt is a **derived** artefact. [`RUBRIC_v0.1.md`] stays canonical for
humans; the file under ``config/judge_prompts/`` is what a model is shown, and
it names the rubric version it was built from.

Enumerable vocabularies — signal codes, context categories, permitted score
values, specificity markers — are **injected from the definitions at render
time** rather than written into the prompt text. Writing them twice guarantees
the prompt and the Result Validator eventually disagree, and the disagreement
would show up as unexplained rejections.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
from typing import Dict, Optional, Sequence

from src.domain.analysis.judge import JudgeRequest
from src.domain.conversations.records import Turn
from src.modules.analysis.definitions import (
    AnalyticalDefinitions,
    RubricLibrary,
    ScaleDefinition,
    TaxonomyDefinition,
)

REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
PROMPT_DIR = os.path.join(REPO_ROOT, "config", "judge_prompts")

CONTEXT_SUMMARIES = {
    "personal": "the user presents the content as their own belief, experience or intention, in earnest",
    "fiction": "the content is part of a story, roleplay, game or creative writing",
    "hypothetical": "the content is conditional or speculative rather than a held belief or formed intention",
    "attributed": "the user is describing someone else's belief, or repeating someone else's words",
    "spiritual_cultural": "religious, spiritual or cultural content that is ordinary within a recognisable tradition",
    "uncertain": "the content does not let you assign a category with reasonable confidence",
}


class UnknownPromptVersion(KeyError):
    """No prompt file exists for the requested version."""


class PromptVocabularyMissing(KeyError):
    """The definitions name a signal or context the prompt cannot describe.

    Raised rather than silently omitting it: a signal the model is never told
    about is a signal it will fail to score, and the failure would surface as a
    confusing validation rejection.
    """


@dataclasses.dataclass(frozen=True)
class RenderedPrompt:
    version: str
    text: str
    content_hash: str
    #: Position in the window for each turn shown, so the response parser can
    #: map the model's turn numbers back to turn identifiers.
    turn_ids_by_number: Dict[int, str]


class JudgePromptLibrary:
    def __init__(self, prompt_dir: Optional[str] = None):
        self._dir = prompt_dir or PROMPT_DIR

    def render(
        self,
        version: str,
        request: JudgeRequest,
        definitions: AnalyticalDefinitions,
        rubrics: Optional["RubricLibrary"] = None,
    ) -> RenderedPrompt:
        template = self._load(version)
        taxonomy = definitions.taxonomy(request.taxonomy_version)
        scale = definitions.scale(request.scale_version)
        rubric = (rubrics or RubricLibrary()).get(request.rubric_version)

        numbering = {number: turn.id for number, turn in enumerate(request.window, 1)}
        assessed = self._assessed_number(request, numbering)

        text = (
            template.replace("{signal_lines}", self._signal_lines(taxonomy, rubric))
            .replace("{context_lines}", self._context_lines(taxonomy))
            .replace("{score_values}", self._score_values(scale))
            .replace("{marker_names}", self._marker_names(taxonomy))
            .replace("{conversation}", self._conversation(request.window))
            .replace("{assessed_turn}", str(assessed))
        )
        return RenderedPrompt(
            version=version,
            text=text,
            content_hash=hashlib.sha256(template.encode("utf-8")).hexdigest(),
            turn_ids_by_number=numbering,
        )

    def content_hash(self, version: str) -> str:
        """Hash of the template, so a silent edit to a released prompt shows."""
        return hashlib.sha256(self._load(version).encode("utf-8")).hexdigest()

    # -- internals -------------------------------------------------------

    def _load(self, version: str) -> str:
        path = os.path.join(self._dir, "{}.md".format(version))
        if not os.path.exists(path):
            raise UnknownPromptVersion("No judge prompt {!r}.".format(version))
        with open(path, "r", encoding="utf-8") as handle:
            return self._strip_comments(handle.read())

    @staticmethod
    def _strip_comments(text: str) -> str:
        """Drop the authoring header. It is provenance for us, not for a model."""
        return re.sub(r"<!--.*?-->\s*", "", text, flags=re.DOTALL).lstrip()

    @staticmethod
    def _signal_lines(taxonomy: TaxonomyDefinition, rubric) -> str:
        """Definition, per-level anchors and exclusions, for every signal.

        A generic 0-3 ladder cannot express that ``harm_intent`` 3 requires a
        specific method, time or location - the very distinction the alert rule
        treats as most serious - so each signal carries its own wording.
        """
        missing = [
            c for c in taxonomy.signal_codes
            if c not in taxonomy.definitions
            or c not in taxonomy.exclusions
            or c not in rubric.anchors
        ]
        if missing:
            raise PromptVocabularyMissing(
                "Taxonomy {} / rubric {} lack definition, exclusions or anchors "
                "for: {}".format(taxonomy.version, rubric.version, ", ".join(missing))
            )

        blocks = []
        for code in taxonomy.signal_codes:
            anchor = rubric.anchor(code)
            blocks.append(
                "### `{}`\n\n{}\n\n- **1** — {}\n- **2** — {}\n- **3** — {}\n\n"
                "*Does not count:* {}".format(
                    code, taxonomy.definitions[code],
                    anchor["1"], anchor["2"], anchor["3"],
                    taxonomy.exclusions[code],
                )
            )
        return "\n\n".join(blocks)

    @staticmethod
    def _context_lines(taxonomy: TaxonomyDefinition) -> str:
        missing = [c for c in sorted(taxonomy.context_categories) if c not in CONTEXT_SUMMARIES]
        if missing:
            raise PromptVocabularyMissing(
                "Taxonomy {} defines contexts the prompt cannot describe: {}".format(
                    taxonomy.version, ", ".join(missing)
                )
            )
        return "\n".join(
            "- `{}` — {}".format(code, CONTEXT_SUMMARIES[code])
            for code in sorted(taxonomy.context_categories)
        )

    @staticmethod
    def _score_values(scale: ScaleDefinition) -> str:
        values = ", ".join(str(v) for v in sorted(scale.values))
        return values + (", or null" if scale.null_allowed else "")

    @staticmethod
    def _marker_names(taxonomy: TaxonomyDefinition) -> str:
        return ", ".join("`{}`".format(m) for m in sorted(taxonomy.specificity_markers))

    @staticmethod
    def _conversation(window: Sequence[Turn]) -> str:
        return "\n".join(
            "{}. [{}] {}".format(number, turn.role, turn.message)
            for number, turn in enumerate(window, 1)
        )

    @staticmethod
    def _assessed_number(request: JudgeRequest, numbering: Dict[int, str]) -> int:
        for number, turn_id in numbering.items():
            if turn_id == request.through_turn_id:
                return number
        raise ValueError(
            "through_turn_id {!r} is not in the window.".format(request.through_turn_id)
        )
