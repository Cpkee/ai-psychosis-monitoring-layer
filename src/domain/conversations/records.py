"""Conversation domain records — architecture.md section 7.2.

Fields are exactly those the architecture lists for ``sessions`` and ``turns``.
Nothing is added speculatively: a field appears here only if section 7.2 names it.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

ROLES = ("user", "assistant")


@dataclasses.dataclass(frozen=True)
class Session:
    """A conversation. Immutable except for closure."""

    id: str
    run_id: str
    external_session_id: str
    source_version_id: str
    scenario_id: str
    raw_theme_label: str
    companion_condition: str
    created_at: str
    canonical_theme_label: Optional[str] = None
    theme_mapping_version: Optional[str] = None
    closed_at: Optional[str] = None

    def __post_init__(self) -> None:
        # Section 8.3: a canonical label may only be introduced through a
        # reviewed mapping version, and never replaces the raw label.
        if self.canonical_theme_label and not self.theme_mapping_version:
            raise ValueError(
                "canonical_theme_label requires theme_mapping_version. A "
                "canonical theme may only be assigned through a reviewed "
                "mapping (architecture.md section 8.3)."
            )
        if not self.raw_theme_label:
            raise ValueError("raw_theme_label must be preserved verbatim.")


@dataclasses.dataclass(frozen=True)
class Turn:
    """One message. Immutable once stored."""

    id: str
    session_id: str
    turn_index: int
    role: str
    message: str
    timestamp: str
    idempotency_key: str
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    source_payload_reference: Optional[str] = None

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError("role must be one of {}, got {!r}".format(ROLES, self.role))
        if self.turn_index < 0:
            raise ValueError("turn_index must be non-negative.")
        if not self.idempotency_key:
            raise ValueError("idempotency_key is required for idempotent ingestion.")
