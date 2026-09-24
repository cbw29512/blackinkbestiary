from __future__ import annotations

from prompt_builder import build_supervisor_checklist


def _checks(page: dict) -> list[str]:
    return build_supervisor_checklist(page)


def build_identity_review_prompt(page: dict) -> str:
    checks = _checks(page)
    prefixes = (
        "Clearly recognizable as ",
        "Canonical scale reads as:",
        "Canonical body plan reads as:",
        "Shape-first body geometry reads as:",
        "Identity check:",
        "Reject identity drift:",
        "Swarm reads as ",
    )
    selected = [item for item in checks if item.startswith(prefixes)]
    return """You are the Black-Ink Bestiary IDENTITY AND ANATOMY GATE.
Inspect only what is visibly present in the image. Do not trust the requested creature name as evidence.

Fail closed. PASS only if every listed identity gate is visibly satisfied.
If the creature could reasonably be mistaken for a forbidden look-alike, fail.
If canonical small/tiny scale is not proved by nearby human-scale architecture/props, fail.
If a small creature has adult-human heroic mass, broad chest, six-pack, thick shoulders, or oversized limbs, fail.
If a bugbear reads gorilla/ape/bodybuilder, fail.
If a bat has separate arms plus wings, fail.
If a centipede lacks one leg pair on every visible trunk segment, fail.
If a swarm has an oversized leader, fail.
If any required limb/body structure is extra, missing, duplicated, merged, branched, or replaced by scenery, fail.

DEFECT WORDING RULE: defects must describe what is visibly wrong or absent. Never copy a positive requirement verbatim into defects. For example, do NOT write "body reads reptilian rather than furry" as a defect; write "body does not read clearly reptilian" or "body reads furry/mammalian". Do NOT write "Canonical scale reads as: small" as a defect; write "creature reads adult-human sized". Negative drift phrases such as "head becomes round and goblin-like" may be reported directly when visibly true.
Do not use the requested label as a preserve item. Preserve items must describe literal visible morphology.
Return exactly one compact JSON object and nothing else:
{"pass": true|false, "score": 0-100, "defects": ["specific visible identity defect"], "preserve": ["specific visible morphology"]}
At most 4 defects and 3 preserve items; each under 80 characters.
Any identity failure must be pass=false and score 49 or lower.

IDENTITY GATES:
- """ + "\n- ".join(selected)


def build_scene_review_prompt(page: dict) -> str:
    checks = _checks(page)
    prefixes = (
        "Habitat reads as:",
        "Scene moment reads as:",
        "Required element present:",
        "Physical state reads as:",
        "Support/contact is visible and believable:",
        "Motion/weight reads correctly:",
        "Environment matches profile:",
        "Spatial type reads without the monster:",
        "Material language is visible:",
        "At least one unmistakable location marker is visible:",
        "Spatial geometry reads correctly:",
        "Space envelope matches:",
        "Space proportions read correctly:",
        "Space overhead/ceiling reads correctly:",
        "Space does not drift into:",
        "Unique landmark is visible:",
        "Framing differs from repeated generic backgrounds:",
        "Monster/environment interaction reads clearly:",
    )
    selected = [item for item in checks if item.startswith(prefixes)]
    return """You are the Black-Ink Bestiary SCENE AND PHYSICALITY GATE.
Inspect the image itself, not the requested caption.

Fail closed. PASS only if the named place, required action, required object relationships, and physical support are visibly present.
Standing near an object is NOT the same as performing the required action.
A normal stair is NOT a cramped spiral stair. A creature standing on stairs is NOT visibly wedged.
A web background is NOT automatically a dungeon hall; required stone architecture must be visible.
A generic corridor is NOT automatically the named habitat.
If a required prop, interaction, spatial relation, support, or cause-and-effect is ambiguous or merely implied, fail.

DEFECT WORDING RULE: defects must describe the visible failure, not copy a required gate. Do NOT return "Habitat reads as: Cramped Spiral Stair"; return "cramped spiral stair is not visible" or "stairs read straight, not spiral". Do NOT return "Scene moment reads as: kicking over a lantern"; return "lantern is not being kicked over".
Preserve items must describe literal visible scene geometry/action, not repeat the requested labels.
Return exactly one compact JSON object and nothing else:
{"pass": true|false, "score": 0-100, "defects": ["specific visible scene defect"], "preserve": ["specific visible scene success"]}
At most 4 defects and 3 preserve items; each under 80 characters.
Any scene failure must be pass=false and score 49 or lower.

SCENE / PHYSICALITY GATES:
- """ + "\n- ".join(selected)


def build_review_prompt(page: dict) -> str:
    checks = _checks(page)
    excluded_prefixes = (
        "Clearly recognizable as ",
        "Canonical scale reads as:",
        "Canonical body plan reads as:",
        "Identity check:",
        "Reject identity drift:",
        "Swarm reads as ",
        "Habitat reads as:",
        "Scene moment reads as:",
        "Required element present:",
        "Physical state reads as:",
        "Support/contact is visible and believable:",
        "Motion/weight reads correctly:",
        "Environment matches profile:",
        "Spatial type reads without the monster:",
        "Material language is visible:",
        "At least one unmistakable location marker is visible:",
        "Spatial geometry reads correctly:",
        "Space envelope matches:",
        "Space proportions read correctly:",
        "Space overhead/ceiling reads correctly:",
        "Space does not drift into:",
        "Unique landmark is visible:",
        "Framing differs from repeated generic backgrounds:",
        "Monster/environment interaction reads clearly:",
    )
    selected = [item for item in checks if not item.startswith(excluded_prefixes)]
    return """You are the Black-Ink Bestiary FINAL COLORING-PAGE GATE.
The candidate has already been checked for species identity and scene requirements.
Now red-team the actual image for any remaining production failure.

Fail closed for: decorative/inset rectangular frames, wallpaper-density swarms, excessive repeated web/rat/detail patterns, clutter, tiny coloring cells, unreadable silhouette, malformed leftover anatomy, large black fills, grayscale/shading, weak negative space, or print-layout problems.
Do not reward an attractive illustration if it would be tedious to color.
For swarm pages, broad white gaps and controlled population are mandatory.
For web pages, webs must not become dense wallpaper that erases the environment.
Pass only when there is no meaningful visible defect worth another edit.
DEFECT WORDING RULE: describe the visible production failure in plain negative language. Never copy a positive quality requirement verbatim into defects.

Return exactly one compact JSON object and nothing else:
{"pass": true|false, "score": 0-100, "defects": ["specific visible production defect"], "preserve": ["specific visible production success"]}
At most 4 defects and 3 preserve items; each under 80 characters.
Any production failure must be pass=false and score 49 or lower.

FINAL QUALITY GATES:
- """ + "\n- ".join(selected)
