from __future__ import annotations


HOUSE_STYLE = [
    "professional fantasy monster coloring-book line art",
    "pure black ink on a pure white background",
    "portrait composition",
    "strong readable outer silhouette",
    "bold outer contour with lighter interior lines",
    "large uninterrupted white regions that are easy and satisfying to color",
    "medium-low detail density",
    "simple supporting environment that clearly establishes the habitat",
    "mature fantasy tone, not preschool-cute",
    "one dominant monster subject",
]

GLOBAL_AVOID = [
    "gray wash",
    "pencil shading",
    "painterly rendering",
    "dense crosshatching",
    "large solid black shadow masses",
    "micro-texture covering surfaces",
    "decorative border",
    "captions",
    "labels",
    "logos",
    "watermarks",
    "text inside the artwork",
    "extra unrelated creatures",
]


def _join(items):
    return "; ".join(str(x).strip() for x in items or [] if str(x).strip())


def build_generation_prompt(page: dict) -> str:
    parts = [
        "Create ONE printable coloring-book page.",
        f"Main monster: {page['monster_name']}.",
        f"Natural habitat/lair: {page['habitat']}.",
        f"Scene moment: {page['moment']}.",
        f"Monster identity requirements: {_join(page.get('identity_rules'))}.",
        f"Required visible elements: {_join(page.get('must_include'))}.",
        f"Composition: {page.get('composition', '')}.",
        "House style: " + _join(HOUSE_STYLE) + ".",
        "Do not include: " + _join(GLOBAL_AVOID + list(page.get('must_avoid') or [])) + ".",
        "Leave generous blank white coloring space. Use clean line separation rather than shading.",
        "No color. No gray background. No typography. No page border.",
    ]
    return "\n".join(parts)


def build_edit_prompt(page: dict, review_notes: dict | None = None) -> str:
    modify = page.get("modify") or {}
    review_notes = review_notes or {}
    reviewer_text = str(review_notes.get("text") or "").strip()
    quick_tags = review_notes.get("quick_tags") or []

    preserve = list(modify.get("preserve") or [])
    change = list(modify.get("change") or [])
    avoid = list(modify.get("avoid") or [])

    if reviewer_text:
        change.append(reviewer_text)
    change.extend(quick_tags)

    parts = [
        "Edit the supplied reference image into a polished Black-Ink Bestiary coloring-book page.",
        "This is a TARGETED EDIT, not a new composition.",
        f"Monster: {page['monster_name']}.",
        f"Habitat/lair: {page['habitat']}.",
        f"Scene moment: {page['moment']}.",
        "PRESERVE: " + _join(preserve) + ".",
        "CHANGE ONLY AS NEEDED: " + _join(change) + ".",
        "DO NOT CHANGE / DO NOT INTRODUCE: " + _join(avoid + GLOBAL_AVOID + list(page.get('must_avoid') or [])) + ".",
        "Keep the monster identity unmistakable: " + _join(page.get("identity_rules")) + ".",
        "House style: " + _join(HOUSE_STYLE) + ".",
        "Reduce visual noise instead of simplifying the monster into crude or childish art.",
        "Use pure black linework on pure white. No grayscale, color, text, border, or painterly shading.",
        "Preserve the successful pose, perspective, props, and story beat unless explicitly told to change them.",
    ]
    return "\n".join(parts)
