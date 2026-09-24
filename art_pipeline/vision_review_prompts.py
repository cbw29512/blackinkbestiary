from __future__ import annotations

from prompt_builder import build_supervisor_checklist


def _checks(page: dict) -> list[str]:
    # Keep the small local VLM focused: universal/page/environment layers may
    # produce the same gate more than once. Exact duplicates add token pressure
    # without adding evidence, so preserve first occurrence only.
    seen = set()
    unique = []
    for item in build_supervisor_checklist(page):
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
    return unique


def _require_selected(page: dict, stage: str, selected: list[str]) -> list[str]:
    if not selected:
        raise RuntimeError(
            f"{page.get('page_id')}: {stage} vision gate has no concrete review checks"
        )
    return selected


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
    selected = _require_selected(
        page,
        "identity",
        [item for item in checks if item.startswith(prefixes)],
    )
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

DEFECT WORDING RULE: defects must describe what is visibly wrong or absent. Never copy a positive requirement verbatim into defects. For example, do NOT write "body reads reptilian rather than furry" as a defect; write "body does not read clearly reptilian" or "body reads furry/mammalian". Do NOT write "Canonical scale reads as: small" as a defect; write "creature reads adult-human sized". Negative drift phrases may be reported directly when visibly true.
Do not use the requested label as a preserve item. Preserve items must describe literal visible morphology.
Return exactly one compact JSON object and nothing else:
{"pass": true|false, "score": 0-100, "defects": ["specific visible identity defect"], "preserve": ["specific visible morphology"]}
At most 4 defects and 3 preserve items; each under 80 characters.
Any identity failure must be pass=false and score 49 or lower.

IDENTITY GATES:
- """ + "\n- ".join(selected)


def build_environment_review_prompt(page: dict) -> str:
    checks = _checks(page)
    prefixes = (
        "Habitat reads as:",
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
        "Environment geometry differs meaningfully from nearby pages",
    )
    selected = _require_selected(
        page,
        "environment",
        [item for item in checks if item.startswith(prefixes)],
    )
    return """You are the Black-Ink Bestiary ENVIRONMENT GEOMETRY GATE.
Inspect only the visible setting. Ignore creature beauty and action quality except where creature scale proves the space.

Fail closed. PASS only if the named habitat, material language, spatial envelope, required architecture/terrain, and unique landmark are visibly readable in the image.
A generic corridor is not a crawlway. Ordinary steps are not a spiral stair. A web field is not automatically a dungeon hall. A flat grate is not a vertical shaft.
If the environment could be mistaken for one of the forbidden drift spaces, fail.
If the creature is correct but the place is generic or spatially wrong, fail.

DEFECT WORDING RULE: describe the visible environmental failure in negative language. Never copy a positive gate verbatim into defects.
Return exactly one compact JSON object and nothing else:
{"pass": true|false, "score": 0-100, "defects": ["specific visible environment defect"], "preserve": ["specific visible environment success"]}
At most 4 defects and 3 preserve items; each under 80 characters.
Any environment failure must be pass=false and score 49 or lower.

ENVIRONMENT GATES:
- """ + "\n- ".join(selected)


def build_action_review_prompt(page: dict) -> str:
    checks = _checks(page)
    prefixes = (
        "Scene moment reads as:",
        "Required element present:",
        "Physical state reads as:",
        "Support/contact is visible and believable:",
        "Motion/weight reads correctly:",
        "Mode-specific contact geometry reads correctly:",
        "Monster/environment interaction reads clearly:",
        "One clear story beat reads as:",
        "Environment participates through:",
        "Interaction proof is visible:",
        "Body language communicates the action without needing the caption",
        "The page does not read as a neutral portrait or prop-holding pose",
        "What single verb describes what the monster is doing?",
        "Can that action be identified without reading the caption?",
        "Does at least one environment feature participate?",
        "Does the pose remain stable and easy to color?",
        "Would removing the prop destroy the entire story read?",
        "Controlled powered flight allowed by monster data:",
        "Pose is stable, natural, and easy to read in a static coloring page",
        "No jumping, falling, dropping, or accidental hovering",
    )
    selected = _require_selected(
        page,
        "action",
        [item for item in checks if item.startswith(prefixes)],
    )
    return """You are the Black-Ink Bestiary ACTION AND PHYSICALITY GATE.
Inspect the visible action, contact, support, and cause-and-effect. The environment has already been checked separately.

Fail closed. PASS only if the required verb/action, prop relationship, support/contact, motion/weight, and story interaction are visibly present.
Standing near an object is not performing the action. Holding a lantern is not kicking it. Standing on stairs is not being wedged. A nearby nest is not nest defense unless the body visibly guards it.
If contact, direction, support, or cause-and-effect is ambiguous or merely implied, fail.

DEFECT WORDING RULE: defects must describe the visible action/physicality failure, not copy a required gate.
Return exactly one compact JSON object and nothing else:
{"pass": true|false, "score": 0-100, "defects": ["specific visible action defect"], "preserve": ["specific visible action success"]}
At most 4 defects and 3 preserve items; each under 80 characters.
Any action failure must be pass=false and score 49 or lower.

ACTION / PHYSICALITY GATES:
- """ + "\n- ".join(selected)


def build_scene_review_prompt(page: dict) -> str:
    """Compatibility helper for callers/tests that still want one scene prompt."""
    return build_environment_review_prompt(page) + "\n\n" + build_action_review_prompt(page)


def build_review_prompt(page: dict) -> str:
    checks = _checks(page)
    excluded_prefixes = (
        "Clearly recognizable as ",
        "Canonical scale reads as:",
        "Canonical body plan reads as:",
        "Shape-first body geometry reads as:",
        "Identity check:",
        "Reject identity drift:",
        "Swarm reads as ",
        "Habitat reads as:",
        "Scene moment reads as:",
        "Required element present:",
        "Physical state reads as:",
        "Support/contact is visible and believable:",
        "Motion/weight reads correctly:",
        "Mode-specific contact geometry reads correctly:",
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
        "Environment geometry differs meaningfully from nearby pages",
        "Environment check:",
        "Monster/environment interaction reads clearly:",
        "One clear story beat reads as:",
        "Environment participates through:",
        "Interaction proof is visible:",
        "Body language communicates the action without needing the caption",
        "The page does not read as a neutral portrait or prop-holding pose",
        "What single verb describes what the monster is doing?",
        "Can that action be identified without reading the caption?",
        "Does at least one environment feature participate?",
        "Does the pose remain stable and easy to color?",
        "Would removing the prop destroy the entire story read?",
        "Controlled powered flight allowed by monster data:",
        "Pose is stable, natural, and easy to read in a static coloring page",
        "No jumping, falling, dropping, or accidental hovering",
    )
    selected = _require_selected(
        page,
        "quality",
        [item for item in checks if not item.startswith(excluded_prefixes)],
    )
    return """You are the Black-Ink Bestiary FINAL COLORING-PAGE GATE.
The candidate has already been checked for species identity, environment geometry, and action/physicality requirements.
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
