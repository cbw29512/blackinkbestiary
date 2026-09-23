from __future__ import annotations

import json
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_FILE = ROOT / "data" / "environment_spatial_envelopes.json"
LOGGER = logging.getLogger(__name__)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        LOGGER.exception("Could not load spatial envelope registry: %s", path)
        raise RuntimeError(f"Could not load spatial envelope registry {path}: {exc}") from exc


def load_spatial_envelopes(path: Path = REGISTRY_FILE) -> dict:
    payload = _read_json(path)
    if not isinstance(payload.get("envelopes"), dict):
        raise RuntimeError("spatial envelope registry requires envelopes")
    return payload


def _profile_match_text(profile: dict) -> tuple[str, str]:
    identity = profile.get("resolved_identity") or profile.get("identity") or {}
    primary = " ".join([
        str(profile.get("environment_id") or ""),
        str(profile.get("name") or ""),
        str(identity.get("spatial_type") or ""),
    ]).lower()
    secondary = " ".join([
        str(profile.get("description") or ""),
        str(identity.get("spatial_read") or ""),
    ]).lower()
    return primary, secondary


def resolve_spatial_envelope(
    profile: dict,
    registry: dict | None = None,
) -> dict:
    payload = registry or load_spatial_envelopes()
    explicit = str(profile.get("spatial_envelope") or "").strip()
    if explicit:
        envelope = (payload.get("envelopes") or {}).get(explicit)
        if not isinstance(envelope, dict):
            raise RuntimeError(f"Unknown spatial envelope {explicit!r}")
        return {"envelope_id": explicit, **envelope}

    family = str(profile.get("environment_family") or "").strip()
    primary_text, secondary_text = _profile_match_text(profile)
    ranked = []
    for envelope_id, envelope in (payload.get("envelopes") or {}).items():
        families = [str(item) for item in envelope.get("families") or []]
        if families and family not in families:
            continue
        terms = [str(item).lower() for item in envelope.get("terms") or [] if str(item).strip()]
        primary_hits = sum(1 for term in terms if term in primary_text)
        secondary_hits = sum(1 for term in terms if term in secondary_text)
        if not primary_hits and not secondary_hits:
            continue
        matched_terms = [
            term for term in terms
            if term in primary_text or term in secondary_text
        ]
        ranked.append((
            primary_hits,
            secondary_hits,
            int(envelope.get("priority") or 0),
            max((len(term) for term in matched_terms), default=0),
            envelope_id,
            envelope,
        ))

    if not ranked:
        raise RuntimeError(
            f"No spatial envelope matched environment profile {profile.get('environment_id')!r}"
        )

    ranked.sort(reverse=True)
    _, _, _, _, envelope_id, envelope = ranked[0]
    return {"envelope_id": envelope_id, **envelope}


def spatial_envelope_errors(profile: dict) -> list[str]:
    try:
        envelope = resolve_spatial_envelope(profile)
    except RuntimeError as exc:
        return [str(exc)]

    errors = []
    for key in (
        "plan_shape",
        "proportions",
        "ceiling",
        "openings",
        "focal_zone",
        "camera",
    ):
        if not str(envelope.get(key) or "").strip():
            errors.append(f"{envelope['envelope_id']}: missing {key}")
    if not envelope.get("must_show"):
        errors.append(f"{envelope['envelope_id']}: must_show is required")
    if not envelope.get("must_not_drift"):
        errors.append(f"{envelope['envelope_id']}: must_not_drift is required")
    return errors
