from __future__ import annotations

from pathlib import Path

try:
    from .environment_catalog import resolve_environment_profile
    from .environment_spatial import resolve_spatial_envelope
except ImportError:
    from environment_catalog import resolve_environment_profile
    from environment_spatial import resolve_spatial_envelope


def _clean(value) -> str:
    return " ".join(str(value or "").strip().split()).rstrip(".;")


def _first(values, limit: int) -> list[str]:
    return [_clean(item) for item in (values or []) if _clean(item)][:limit]


def build_room_brief(page: dict, root: Path) -> dict:
    profile = resolve_environment_profile(
        page.get("environment_profile_id"),
        root / "data" / "environment_families",
    )
    envelope = resolve_spatial_envelope(profile)
    identity = profile.get("resolved_identity") or {}
    markers = _first(identity.get("identity_markers"), 3)
    must_show = _first(envelope.get("must_show"), 3)
    drift = _first(envelope.get("must_not_drift"), 4)

    shape = _clean(envelope.get("plan_shape"))
    proportions = _clean(envelope.get("proportions"))
    material = _clean(identity.get("material_language"))
    ceiling = _clean(envelope.get("ceiling"))
    openings = _clean(envelope.get("openings"))
    focal = _clean(envelope.get("focal_zone"))
    camera = _clean(envelope.get("camera"))

    brief = (
        f"{profile['name']}: {shape}; {proportions}. "
        f"Materials: {material}. "
        f"Overhead: {ceiling}. "
        f"Openings: {openings}. "
        f"Focal organization: {focal}. "
        f"View: {camera}."
    )
    return {
        "profile_name": profile["name"],
        "envelope_id": envelope["envelope_id"],
        "brief": brief,
        "proof_cues": list(dict.fromkeys(markers + must_show))[:5],
        "drift_failures": drift,
    }
