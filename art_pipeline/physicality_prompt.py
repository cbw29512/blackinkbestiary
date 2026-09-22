from __future__ import annotations


def physicality_sections(page: dict) -> list[str]:
    physicality = page.get("physicality") or {}
    return [
        f"PHYSICAL STATE: {physicality.get('mode', '')}.",
        f"PHYSICAL SUPPORT / CONTACT: {physicality.get('support', '')}.",
        f"PHYSICAL MOTION / WEIGHT: {physicality.get('motion', '')}.",
        (
            "GROUNDING RULE: the creature must visibly contact a believable support surface, "
            "or the image must clearly explain intentional flight, falling, hanging, climbing, "
            "swimming, burrowing, coiling, or other unsupported motion."
        ),
    ]


def physicality_checklist(page: dict) -> list[str]:
    physicality = page.get("physicality") or {}
    return [
        f"Physical state reads as: {physicality.get('mode', '')}",
        f"Support/contact is visible and believable: {physicality.get('support', '')}",
        f"Motion/weight reads correctly: {physicality.get('motion', '')}",
        "No accidental hovering or static standing pose in midair",
    ]
