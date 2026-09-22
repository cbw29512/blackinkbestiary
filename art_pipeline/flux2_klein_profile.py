from __future__ import annotations

import json
from pathlib import Path


def envelope_data(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


def _slot(slots: list[dict], address: str):
    return next((s for s in slots if str(s.get("address")) == address), None)


def _root(address: str) -> str:
    return address.split(".", 1)[0].split("/", 1)[0]


def select_distilled_branch(slots: list[dict]) -> tuple[str, list[str]]:
    unets = [
        s for s in slots
        if s.get("name") == "unet_name" and "." in str(s.get("address", ""))
    ]
    if not unets:
        raise RuntimeError("Official FLUX.2 Klein template exposed no unet_name slots.")

    roots = sorted({_root(str(s["address"])) for s in unets}, key=lambda x: int(x) if x.isdigit() else x)
    scored = []
    for slot in unets:
        root = _root(str(slot["address"]))
        current = str(slot.get("current_value", "")).lower()
        steps = next(
            (s.get("current_value") for s in slots
             if _root(str(s.get("address", ""))) == root and s.get("name") == "steps"),
            None,
        )
        cfg = next(
            (s.get("current_value") for s in slots
             if _root(str(s.get("address", ""))) == root and s.get("name") == "cfg"),
            None,
        )
        score = 0
        if "base" not in current:
            score += 10
        if isinstance(steps, (int, float)) and steps <= 4:
            score += 5
        if isinstance(cfg, (int, float)) and cfg <= 1.5:
            score += 3
        scored.append((score, root, current, steps, cfg))

    scored.sort(reverse=True)
    selected = scored[0]
    if selected[0] < 10:
        raise RuntimeError(f"Could not identify distilled FLUX.2 Klein branch from slots: {scored}")
    return selected[1], roots


def prompt_slot(slots: list[dict]) -> str:
    candidates = [
        str(s["address"]) for s in slots
        if s.get("node_type") == "PrimitiveStringMultiline" and s.get("name") == "value"
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one shared prompt primitive, found: {candidates}")
    return candidates[0]


def build_distilled_overrides(
    slots: list[dict],
    selected_root: str,
    *,
    prompt: str,
    seed: int,
    model_filename: str,
    width: int,
    height: int,
) -> dict:
    overrides = {
        prompt_slot(slots): prompt,
        f"{selected_root}.unet_name": model_filename,
        f"{selected_root}.noise_seed": seed,
    }

    if _slot(slots, f"{selected_root}.value"):
        overrides[f"{selected_root}.value"] = width
    if _slot(slots, f"{selected_root}.value_1"):
        overrides[f"{selected_root}.value_1"] = height

    step_slot = next(
        (s for s in slots if _root(str(s.get("address", ""))) == selected_root and s.get("name") == "steps"),
        None,
    )
    cfg_slot = next(
        (s for s in slots if _root(str(s.get("address", ""))) == selected_root and s.get("name") == "cfg"),
        None,
    )
    if step_slot:
        overrides[str(step_slot["address"])] = 4
    if cfg_slot:
        overrides[str(cfg_slot["address"])] = 1
    return overrides


def activate_branch(workflow_path: Path, selected_root: str, branch_roots: list[str]) -> None:
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))
    nodes = {str(node.get("id")): node for node in workflow.get("nodes", [])}

    for root in branch_roots:
        if root in nodes:
            nodes[root]["mode"] = 0 if root == selected_root else 4

    # SaveImage nodes follow each top-level branch. Mirror the branch mode so
    # conversion has exactly one reachable output.
    for link in workflow.get("links", []):
        if not isinstance(link, list) or len(link) < 4:
            continue
        origin = str(link[1])
        target = str(link[3])
        if origin not in branch_roots:
            continue
        target_node = nodes.get(target)
        if target_node and target_node.get("type") == "SaveImage":
            target_node["mode"] = 0 if origin == selected_root else 4

    workflow_path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")


def prepare_distilled_text_to_image(
    cli,
    template_name: str,
    workflow_path: Path,
    *,
    prompt: str,
    seed: int,
    model_filename: str,
    width: int = 768,
    height: int = 1024,
) -> dict:
    cli.fetch_template(template_name, workflow_path)
    slot_payload = envelope_data(cli.workflow_slots(workflow_path)) or {}
    slots = slot_payload.get("slots")
    if not isinstance(slots, list):
        raise RuntimeError(f"Could not read template slots: {slot_payload}")

    selected_root, roots = select_distilled_branch(slots)
    overrides = build_distilled_overrides(
        slots,
        selected_root,
        prompt=prompt,
        seed=seed,
        model_filename=model_filename,
        width=width,
        height=height,
    )
    cli.set_workflow_slots(workflow_path, overrides)
    activate_branch(workflow_path, selected_root, roots)

    return {
        "selected_root": selected_root,
        "branch_roots": roots,
        "overrides": overrides,
        "workflow": str(workflow_path),
    }
