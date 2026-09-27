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


def _profile_text(profile: dict) -> str:
    identity = profile.get("resolved_identity") or profile.get("identity") or {}
    return " ".join([
        str(profile.get("environment_id") or ""),
        str(profile.get("name") or ""),
        str(profile.get("description") or ""),
        str(identity.get("spatial_type") or ""),
        str(identity.get("spatial_read") or ""),
    ]).lower()


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
    text = _profile_text(profile)
    ranked = []
    for envelope_id, envelope in (payload.get("envelopes") or {}).items():
        families = [str(item) for item in envelope.get("families") or []]
        if families and family not in families:
            continue
        terms = [str(item).lower() for item in envelope.get("terms") or [] if str(item).strip()]
        hits = sum(1 for term in terms if term in text)
        if not hits:
            continue
        ranked.append((
            int(envelope.get("priority") or 0),
            hits,
            max((len(term) for term in terms if term in text), default=0),
            envelope_id,
            envelope,
        ))

    if not ranked:
        raise RuntimeError(
            f"No spatial envelope matched environment profile {profile.get('environment_id')!r}"
        )

    ranked.sort(reverse=True)
    _, _, _, envelope_id, envelope = ranked[0]
    return {"envelope_id": envelope_id, **envelope}


def spatial_envelope_prompt_rules(envelope: dict) -> list[str]:
    """Translate envelope geometry into explicit image-model composition constraints."""
    envelope_id = str(envelope.get("envelope_id") or "unknown")
    must_show = [str(item).strip() for item in envelope.get("must_show") or [] if str(item).strip()]
    must_not = [str(item).strip() for item in envelope.get("must_not_drift") or [] if str(item).strip()]
    rules = [
        f"Lock the scene to the {envelope_id} spatial envelope before adding props or texture.",
        f"Preserve this plan shape: {envelope.get('plan_shape', '')}.",
        f"Preserve these proportions: {envelope.get('proportions', '')}.",
        f"Preserve this overhead condition: {envelope.get('ceiling', '')}.",
        f"Preserve this opening logic: {envelope.get('openings', '')}.",
        f"Keep the focal zone organized like this: {envelope.get('focal_zone', '')}.",
        f"Use this camera logic: {envelope.get('camera', '')}.",
    ]
    if must_show:
        rules.append("The composition visibly proves the space with: " + "; ".join(must_show) + ".")
    if must_not:
        rules.append("Reject any composition that drifts into: " + "; ".join(must_not) + ".")
    rules.append(
        "Large scenery forms must define the space before torches, traps, furniture, debris, plants, or texture are added."
    )
    return rules


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
