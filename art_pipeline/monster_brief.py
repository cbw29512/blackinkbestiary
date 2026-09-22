from __future__ import annotations

from pathlib import Path

try:
    from .monster_catalog import load_monster_contract
except ImportError:
    from monster_catalog import load_monster_contract


def _clean(value) -> str:
    return " ".join(str(value or "").strip().split()).rstrip(".;")


def _clip(value, words: int) -> str:
    parts = _clean(value).split()
    return " ".join(parts[:words]).rstrip(",;:")


def _limited(values, count: int) -> list[str]:
    return [_clean(item) for item in (values or []) if _clean(item)][:count]


def build_monster_brief(spec: dict, root: Path) -> dict:
    visual = spec.get("visual_identity") or {}
    scene = spec.get("scene_identity") or {}
    contract = load_monster_contract(root / "config" / "universal_monster_contract.json")
    budget = contract.get("prompt_budget") or {}

    core = _clip(visual.get("core_identity"), 22)
    silhouette = _clip(visual.get("silhouette"), 18)
    head = _clip(visual.get("head_features"), 16)
    body = _clip(visual.get("body_shape"), 15)
    limbs = _clip(visual.get("limb_structure"), 15)
    surface = _clip(visual.get("surface"), 12)
    posture = _clip(scene.get("natural_posture"), 14)

    sentences = [f"{spec.get('monster_name', '')}: {core}." if core else str(spec.get("monster_name") or "")]
    for label, value in (
        ("Silhouette", silhouette),
        ("Head", head),
        ("Body", body),
        ("Limbs", limbs),
        ("Surface", surface),
        ("Natural posture", posture),
    ):
        if value:
            sentences.append(f"{label}: {value}.")
    brief = " ".join(item for item in sentences if item)
    maximum = int(budget.get("monster_brief_max_words") or 105)
    if len(brief.split()) > maximum:
        raise RuntimeError(
            f"MONSTER BRIEF for {spec.get('monster_id')} exceeds {maximum} words"
        )

    anchors = _limited(
        visual.get("must_keep"),
        int(budget.get("identity_anchor_limit") or 7),
    )
    avoid = _limited(
        visual.get("must_avoid"),
        int(budget.get("drift_failure_limit") or 6),
    )
    correction_limit = int(budget.get("failure_correction_limit") or 4)
    corrections = []
    for item in spec.get("known_failure_modes") or []:
        symptom = _clean(item.get("symptom"))
        correction = _clean(item.get("correction"))
        if symptom and correction:
            corrections.append(f"{symptom} -> {correction}")
        if len(corrections) >= correction_limit:
            break

    render = spec.get("render_identity") or {}
    anatomy = spec.get("anatomy") or {}
    return {
        "brief": brief,
        "anchors": anchors,
        "avoid": avoid,
        "corrections": corrections,
        "subject_mode": render.get("subject_mode"),
        "expected_count": render.get("expected_count"),
        "body_plan": anatomy.get("body_plan"),
        "support_logic": anatomy.get("support_logic"),
    }
