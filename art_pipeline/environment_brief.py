from __future__ import annotations

from pathlib import Path

try:
    from .environment_catalog import load_environment_contract, resolve_environment_profile
    from .environment_spatial import resolve_spatial_envelope
except ImportError:
    from environment_catalog import load_environment_contract, resolve_environment_profile
    from environment_spatial import resolve_spatial_envelope


def _clean(value) -> str:
    return " ".join(str(value or "").strip().split()).rstrip(".;")


def _first(values, limit: int) -> list[str]:
    return [_clean(item) for item in (values or []) if _clean(item)][:limit]


def _clip_words(value: str, limit: int) -> str:
    words = _clean(value).split()
    if len(words) <= limit:
        return " ".join(words)
    return " ".join(words[:limit]).rstrip(",;:")


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

    shape = _clip_words(envelope.get("plan_shape"), 10)
    proportions = _clip_words(envelope.get("proportions"), 14)
    material = _clip_words(identity.get("material_language"), 14)
    ceiling = _clip_words(envelope.get("ceiling"), 12)
    openings = _clip_words(envelope.get("openings"), 12)
    focal = _clip_words(envelope.get("focal_zone"), 12)
    camera = _clip_words(envelope.get("camera"), 10)

    brief = (
        f"{profile['name']}: {shape}; {proportions}. "
        f"Materials: {material}. "
        f"Overhead: {ceiling}. "
        f"Openings: {openings}. "
        f"Focal organization: {focal}. "
        f"View: {camera}."
    )
    contract = load_environment_contract(root / "config" / "universal_environment_contract.json")
    maximum = int((contract.get("room_brief_engine") or {}).get("max_words") or 95)
    if len(brief.split()) > maximum:
        raise RuntimeError(
            f"ROOM BRIEF for {profile['environment_id']} exceeds {maximum} words"
        )
    return {
        "profile_name": profile["name"],
        "envelope_id": envelope["envelope_id"],
        "brief": brief,
        "proof_cues": list(dict.fromkeys(markers + must_show))[:5],
        "drift_failures": drift,
    }
