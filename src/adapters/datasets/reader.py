"""Gate-enforced dataset reader — architecture.md section 16 adapters.

The reader accepts an :class:`AuthorizedDataUse` rather than a path, so a
caller cannot reach a registered source without the Dataset Use Gate having
allowed the use first.

There is no per-dataset reader. A dataset's restrictions live in its registry
entry (architecture section 8.2), not in bespoke code.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.domain.provenance.data_sources import AuthorizedDataUse


def read_jsonl(
    authorized: AuthorizedDataUse, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Read a JSONL source, one provenance-enveloped record per line.

    The envelope keeps a record's origin and purpose attached to it, so a
    later refactor cannot detach MindEval-derived rows from the restrictions
    that govern them.
    """
    records: List[Dict[str, Any]] = []
    with open(authorized.absolute_path, "r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records.append(
                {
                    "source_version_id": authorized.source_version_id,
                    "purpose": authorized.purpose.value,
                    "audit_event_id": authorized.audit_event_id,
                    "record": json.loads(line),
                }
            )
            if limit is not None and len(records) >= limit:
                break
    return records
