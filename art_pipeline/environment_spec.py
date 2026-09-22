from __future__ import annotations


REQUIRED_ENVIRONMENT_FIELDS = {
    "identity",
    "anchors",
    "interaction",
    "coloring_value",
    "must_avoid",
}


def validate_environment(page: dict) -> list[str]:
    page_id = str(page.get("page_id") or "<missing>")
    environment = page.get("environment")
    if not isinstance(environment, dict):
        return [f"{page_id}: environment must be an object"]

    errors: list[str] = []
    missing = sorted(REQUIRED_ENVIRONMENT_FIELDS.difference(environment))
    if missing:
        errors.append(f"{page_id}: environment missing fields: {', '.join(missing)}")
        return errors

    if not str(environment.get("identity") or "").strip():
        errors.append(f"{page_id}: environment identity cannot be empty")
    if not str(environment.get("interaction") or "").strip():
        errors.append(f"{page_id}: environment interaction cannot be empty")

    anchors = environment.get("anchors")
    if not isinstance(anchors, list) or len([x for x in anchors if str(x).strip()]) < 2:
        errors.append(f"{page_id}: environment needs at least two visual anchors")

    coloring = environment.get("coloring_value")
    if not isinstance(coloring, list) or not any(str(x).strip() for x in coloring):
        errors.append(f"{page_id}: environment coloring_value cannot be empty")

    avoid = environment.get("must_avoid")
    if not isinstance(avoid, list) or not any(str(x).strip() for x in avoid):
        errors.append(f"{page_id}: environment must_avoid cannot be empty")
    return errors


def _items(label: str, values) -> str:
    cleaned = [str(value).strip() for value in (values or []) if str(value).strip()]
    return f"{label}: " + "; ".join(cleaned) + "." if cleaned else ""


def prompt_sections(page: dict) -> list[str]:
    env = page["environment"]
    return [
        "ENVIRONMENT IS A CO-EQUAL STORYTELLING SUBJECT, NOT DECORATIVE BACKGROUND.",
        f"ENVIRONMENT IDENTITY: {env['identity']}.",
        _items("ENVIRONMENT VISUAL ANCHORS", env.get("anchors")),
        f"MONSTER-ENVIRONMENT INTERACTION: {env['interaction']}.",
        _items("ENVIRONMENT COLORING VALUE", env.get("coloring_value")),
        _items("ENVIRONMENT ERRORS TO AVOID", env.get("must_avoid")),
        (
            "BALANCE RULE: the monster must remain clearly readable, while the environment must be "
            "specific enough that the setting is recognizable even if the monster were hidden."
        ),
    ]


def checklist(page: dict) -> list[str]:
    env = page["environment"]
    checks = [
        f"Environment is unmistakably: {env['identity']}",
        f"Monster and environment interact visibly: {env['interaction']}",
        "Environment contributes meaningful coloring areas instead of empty filler",
        "Environment remains specific without becoming clutter",
    ]
    checks.extend(f"Environment anchor present: {item}" for item in env.get("anchors", []))
    return checks
