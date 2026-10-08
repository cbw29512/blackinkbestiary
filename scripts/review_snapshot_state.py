"""Select current gallery records before publishing review snapshots."""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping

LOGGER = logging.getLogger(__name__)
CandidateKey = tuple[str, int]


def latest_candidate_records(state: dict) -> dict[CandidateKey, dict]:
    """The last record for each page/candidate is the only current authority."""
    latest: dict[CandidateKey, dict] = {}
    for index, item in enumerate(state.get("results") or []):
        if not isinstance(item, dict):
            LOGGER.warning("Ignoring non-object gallery record at index %d", index)
            continue
        page_id = str(item.get("page_id") or "").strip()
        try:
            candidate = int(item.get("candidate") or 0)
        except (TypeError, ValueError):
            LOGGER.warning("Ignoring invalid candidate number at index %d", index)
            continue
        if page_id and candidate > 0:
            latest[(page_id, candidate)] = item
    return latest


def reviewable_candidate_records(
    latest: Mapping[CandidateKey, dict], allowed_statuses: Collection[str]
) -> dict[CandidateKey, dict]:
    """Never resurrect an older reviewable record after a later rejection/failure."""
    return {
        key: item
        for key, item in latest.items()
        if str(item.get("status") or "") in allowed_statuses
    }
