from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_FILE = ROOT / "config" / "universal_story_contract.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_story_contract(root: Path = ROOT) -> dict:
    return _read(root / "config" / "universal_story_contract.json")


def interaction_proof_rules(page: dict) -> list[str]:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    text = " ".join([
        str(page.get("moment") or ""),
        " ".join(str(item) for item in page.get("must_include") or []),
        str(variant.get("interaction") or ""),
        str(physicality.get("mode") or ""),
        str(physicality.get("support") or ""),
        str(physicality.get("motion") or ""),
    ]).lower()

    rules = []
    if "chain" in text and ("drag" in text or "scrap" in text):
        rules.append(
            "CHAIN-DRAG PROOF: the chain must visibly trail from the creature and physically touch the floor or stair treads at multiple points; it may not float, hang decoratively, or stay fully off the ground."
        )
    if "wound" in text and ("close" in text or "regenerat" in text):
        rules.append(
            "REGENERATION PROOF: show one localized non-gory wound whose edges visibly bridge/close with clean contour continuity. Do not depict only a generic scar or open injury."
        )
    if "severed" in text and ("crawl" in text or "drag" in text):
        rules.append(
            "SEVERED-LIMB MOTION PROOF: the severed limb itself is the complete moving subject; its fingers/palm visibly contact the floor and its pose points toward the named target. No torso or extra body parts may appear."
        )
    if ("stirge" in text or "proboscis" in text) and ("feed" in text or "feeding" in text):
        rules.append(
            "FEEDING-CONTACT PROOF: at least two tiny feeders must show their long proboscises visibly contacting the target or bedding immediately around the target; nearby flyers remain secondary and similarly scaled."
        )
    if "nest" in text and ("defend" in text or "defensive" in text):
        rules.append(
            "NEST-DEFENSE PROOF: the nest must be clearly visible under or immediately behind the creature, and the creature's body must interpose itself between the viewer/threat and the nest. Do not substitute eating/scavenging."
        )
    if "well" in text and ("upward" in text or "erupt" in text or "rise" in text):
        rules.append(
            "VERTICAL-ORIGIN PROOF: the well/shaft opening is the unmistakable origin of the movement, with the group visibly emerging from that opening and continuing upward in one readable flow."
        )
    if "gland" in text and ("light" in text or "illumin" in text or "glow" in text):
        rules.append(
            "LINE-ART LIGHT PROOF: luminous gland shapes must be unmistakable and must visibly affect a nearby rock/timber surface using open white halo space and a few sparse radiating contour marks; no grayscale glow wash."
        )
    if "fire" in text and ("glare" in text or "recoil" in text or "distance" in text):
        rules.append(
            "FIRE-REACTION PROOF: the creature's head/eyes visibly orient toward the fire while the torso or stance recoils/keeps distance from it; the fire and reaction must read together at a glance."
        )
    if "web" in text and ("center" in text or "supported" in text):
        rules.append(
            "WEB-SUPPORT PROOF: multiple canonical legs visibly contact tensioned web strands at the body's support points, while surrounding architecture remains readable through the web."
        )
    if "silence" in text and ("finger" in text or "signal" in text):
        rules.append(
            "SILENCE-GESTURE PROOF: one hand must visibly make a finger-to-mouth hush gesture near the face while the other body action remains readable; do not substitute a generic raised hand."
        )
    if "sack" in text and ("drag" in text or "pull" in text):
        rules.append(
            "DRAGGED-SACK PROOF: exactly one sack visibly trails behind or beside the creature, with the sack resting on the floor and a hand/rope contact showing it is being pulled."
        )
    if "ham" in text:
        rules.append(
            "HAM-OBJECT PROOF: the stolen food must read unmistakably as a ham through a large rounded meat shape with one protruding bone end; do not substitute a generic sack, loaf, rock, or unidentified bundle."
        )
    if "shrine" in text and "coin" in text:
        rules.append(
            "SHRINE-OFFERING PROOF: the coin is visibly held or raised between the creature and the shrine/altar, with hand and body orientation making the offering/tending action clear."
        )
    if "map" in text and ("command" in text or "captain" in text or "table" in text):
        rules.append(
            "MAP-COMMAND PROOF: a readable open map lies on the table and the officer's hand/gesture visibly points to or organizes that map; do not substitute a generic table pose."
        )
    if "suspended inside" in text or ("suspended" in text and ("cube" in text or "ooze" in text)):
        rules.append(
            "SUSPENDED-CONTENTS PROOF: every named suspended object must be visibly enclosed within the continuous transparent/translucent body volume, not floating outside, resting on top, or hidden behind it."
        )
    if ("corrod" in text or "acid damage" in text) and ("metal" in text or "bar" in text):
        rules.append(
            "CORROSION-CONTACT PROOF: visible material damage must begin exactly where the creature contacts the metal, with pitting, eaten edges, or broken bar contour at the contact zone; do not show unrelated decorative damage elsewhere."
        )
    if "split" in text and ("half" in text or "halves" in text):
        rules.append(
            "SPLIT-BODY PROOF: show exactly the required separate body masses as independent continuous forms, each visibly supported and moving on its own. Do not reconnect them, add a third mass, or leave one half as a detached decorative blob."
        )
    if "mimic" in text and ("reveal" in text or "mouth" in text or "tongue" in text or "hidden eye" in text):
        rules.append(
            "MIMIC-REVEAL PROOF: the predatory feature must emerge directly from the original object's own lid, seam, panel, handle, hinge, or surface while the object silhouette remains recognizable. No separate creature may appear beside or behind it."
        )
    if "petrif" in text or "turning to stone" in text:
        rules.append(
            "PETRIFICATION PROOF: the affected secondary creature/object must show a readable transition between living form and stone through a clear boundary of stiffened contour, stone cracks/facets, or statue-like texture. Do not substitute a second ordinary statue with no visible transformation."
        )
    if "camouflage" in text or "disguis" in text:
        rules.append(
            "CAMOUFLAGE-BREAK PROOF: surrounding forms must explain the disguise while one or two canonical creature features visibly break that match. The subject may not become so blended that species identity disappears."
        )
    if "lightning" in text or "electrical" in text:
        rules.append(
            "LIGHTNING-CONTACT PROOF: sparse line-art arcs must visibly originate from or travel along the creature and connect toward the named environmental target. Do not use disconnected decorative lightning in empty background space."
        )
    if "shriek" in text or "alarm" in text:
        rules.append(
            "ALARM-VIBRATION PROOF: use a few clean radiating vibration/sound contour lines from the actual opening or vibrating structure while the rooted/supporting body remains still. No text, sound-effect lettering, or dense comic burst."
        )
    if "guard" in text and ("phylactery" in text or "reliquary" in text or "focus object" in text):
        rules.append(
            "GUARDED-FOCUS PROOF: the guarded object must be clearly visible and spatially tied to the creature's stance or gesture; the creature must visibly control/interpose the space around it rather than merely stand elsewhere in the room."
        )
    return rules


def critical_scene_lock(page: dict) -> str:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    return (
        "CRITICAL SCENE LOCK — NON-NEGOTIABLE: "
        f"exact visible action={page.get('moment', '')}; "
        f"environment interaction={variant.get('interaction', '')}; "
        f"landmark={variant.get('landmark', '')}; "
        f"framing={variant.get('framing', '')}; "
        f"support/contact={physicality.get('support', '')}; "
        f"motion/weight={physicality.get('motion', '')}. "
        "Build the pose and environment around this cause-and-effect first. "
        "Do not replace the required action with standing, holding, posing, or merely being near the prop."
    )


def story_sections(page: dict, root: Path = ROOT) -> list[str]:
    contract = load_story_contract(root)
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    return [
        f"STORY BEAT: {page.get('moment', '')}.",
        f"STORY/ENVIRONMENT INTERACTION: {variant.get('interaction', '')}.",
        f"STORY BODY LANGUAGE: {physicality.get('motion', '')}.",
        *interaction_proof_rules(page),
        f"STORY PRIORITY: {contract.get('priority_rule', '')}",
        "STORY RULES: " + "; ".join(contract.get("principles") or []) + ".",
        (
            "STATIC STORY TEST: the page must read as one clear verb/action at thumbnail size, "
            "not as a character portrait or a monster merely holding props. "
            "If extra story detail would reduce coloring space or silhouette clarity, simplify the story."
        ),
    ]


def story_checklist(page: dict, root: Path = ROOT) -> list[str]:
    contract = load_story_contract(root)
    checks = [
        f"One clear story beat reads as: {page.get('moment', '')}",
        f"Environment participates through: {(page.get('environment_variant') or {}).get('interaction', '')}",
        "Body language communicates the action without needing the caption",
        "The page does not read as a neutral portrait or prop-holding pose",
    ]
    checks.extend(f"Interaction proof is visible: {rule}" for rule in interaction_proof_rules(page))
    checks.extend(contract.get("review_questions") or [])
    return checks


def story_errors(page: dict, root: Path = ROOT) -> list[str]:
    contract = load_story_contract(root)
    moment = " ".join(str(page.get("moment") or "").strip().lower().split())
    generic = {
        "standing",
        "posing",
        "waiting",
        "idle",
        "ready",
        "holding something",
        "holding a weapon",
    }
    errors = []
    if moment in generic:
        errors.append(f"{page.get('page_id')}: story moment is too generic for a production page")
    interaction = str((page.get("environment_variant") or {}).get("interaction") or "").strip()
    if not interaction:
        errors.append(f"{page.get('page_id')}: story/environment interaction is required")
    motion = str((page.get("physicality") or {}).get("motion") or "").strip()
    if not motion:
        errors.append(f"{page.get('page_id')}: story body language/physical motion is required")
    return errors
