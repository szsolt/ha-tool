from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class BulkRenameResult:
    from_id: str
    to_id: str
    status: str  # "ok" | "collision" | "noop" | "cross-domain"


def analyze_bulk_rename(
    entity_ids: list[str], pattern: str, replacement: str
) -> list[BulkRenameResult]:
    """Match entity_ids against a regex (fullmatch) and compute new ids.

    Returns one result per MATCHING id (non-matches are excluded). Status:
      - noop: new id equals old id
      - cross-domain: new id's domain differs from old id's domain (HA rejects)
      - collision: target already exists, or two sources map to the same target
      - ok: otherwise

    Raises re.error if the pattern is invalid or the replacement has a bad backref.
    """
    rx = re.compile(pattern)
    existing = set(entity_ids)

    raw: list[tuple[str, str]] = []
    for eid in entity_ids:
        if rx.fullmatch(eid):
            new_id = rx.sub(
                replacement, eid, count=1
            )  # validates backrefs; one-shot (fullmatch guaranteed)
            raw.append((eid, new_id))

    target_counts: dict[str, int] = {}
    for _, new_id in raw:
        target_counts[new_id] = target_counts.get(new_id, 0) + 1

    results: list[BulkRenameResult] = []
    for old_id, new_id in raw:
        if new_id == old_id:
            status = "noop"
        elif old_id.split(".", 1)[0] != new_id.split(".", 1)[0]:
            status = "cross-domain"
        elif new_id in existing or target_counts[new_id] > 1:
            status = "collision"
        else:
            status = "ok"
        results.append(BulkRenameResult(from_id=old_id, to_id=new_id, status=status))

    return results
