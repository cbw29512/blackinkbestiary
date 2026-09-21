from __future__ import annotations

STYLE_RULES = [
    "professional fantasy coloring-book line art",
    "pure black ink on a clean white background",
    "portrait page composition",
    "one dominant recognizable monster",
    "bold clean outer contour",
    "lighter simpler interior lines",
    "large uninterrupted white regions that are enjoyable to color",
    "medium-low detail density",
    "simple supporting environment that clearly establishes the habitat",
    "no grayscale wash",
    "no painterly shading",
    "almost no crosshatching",
    "minimal solid-black shadow masses",
    "no text, caption, logo, watermark, or decorative border",
    "mature fantasy look; not preschool-cute and not stick-figure simple",
]


def _items(label: str, values) -> str:
    values = [str(v).strip() for v in (values or []) if str(v).strip()]
    if not values:
        return ""
    return f"{label}: " + "; ".join(values) + "."


def build_prompt(page: dict, review_notes: dict | None = None) -> str:
    sections = [
        "Create ONE printable fantasy monster coloring-book page.",
        f"SUBJECT: {page['monster_name']}.",
        f"HABITAT: {page['habitat']}.",
        f"MOMENT: {page['moment']}.",
        _items("MONSTER IDENTITY", page.get("identity_rules")),
        _items("MUST INCLUDE", page.get("must_include")),
        _items("MUST AVOID", page.get("must_avoid")),
        f"COMPOSITION: {page.get('composition', '')}".strip(),
        "HOUSE STYLE: " + "; ".join(STYLE_RULES) + ".",
    ]

    modify = page.get("modify")
    if modify:
        sections.extend([
            _items("PRESERVE", modify.get("preserve")),
            _items("CHANGE", modify.get("change")),
            _items("DO NOT CHANGE / DO NOT INTRODUCE", modify.get("avoid")),
            "This is a targeted refinement. Preserve the successful scene and simplify only the requested areas.",
        ])

    if review_notes:
        tags = review_notes.get("quick_tags") or []
        text = (review_notes.get("text") or "").strip()
        if text:
            sections.append(f"LATEST HUMAN NOTE: {text}")
        if tags:
            sections.append(_items("LATEST HUMAN QUICK CHANGES", tags))

    sections.append(
        "Final test: the creature must be unmistakable at thumbnail size, the habitat must read immediately, "
        "and the finished page must contain generous clean white areas for coloring."
    )
    return "\n\n".join(part for part in sections if part)


def build_supervisor_checklist(page: dict) -> list[str]:
    checks = [
        f"Clearly recognizable as {page['monster_name']}",
        f"Habitat reads as: {page['habitat']}",
        f"Scene moment reads as: {page['moment']}",
        "Monster is the dominant focal subject",
        "Large open white coloring regions",
        "Outer contours stronger than interior detail",
        "No grayscale wash or painterly shading",
        "No dense crosshatching or excessive tiny texture",
        "No text, border, logo, or watermark",
    ]
    for item in page.get("must_include", []):
        checks.append(f"Required element present: {item}")
    return checks
