from __future__ import annotations

import json
from pathlib import Path


def envelope_data(payload):
    if isinstance(payload, dict) and "data" in payload:
        return payload.get("data")
    return payload


def _node_by_type(nodes: list[dict], node_type: str) -> dict:
    matches = [n for n in nodes if isinstance(n, dict) and n.get("type") == node_type]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one {node_type} node, found {len(matches)}")
    return matches[0]


def _primitive_by_title(nodes: list[dict], title: str) -> dict:
    matches = [
        n for n in nodes
        if isinstance(n, dict)
        and n.get("type") == "PrimitiveInt"
        and str(n.get("title", "")).lower() == title.lower()
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected exactly one PrimitiveInt titled {title!r}, found {len(matches)}")
    return matches[0]


def _set_widget(node: dict, index: int, value) -> None:
    values = node.get("widgets_values")
    if not isinstance(values, list):
        values = []
        node["widgets_values"] = values
    while len(values) <= index:
        values.append(None)
    values[index] = value


def _find_distilled_definition(workflow: dict) -> dict:
    definitions = workflow.get("definitions")
    subgraphs = definitions.get("subgraphs") if isinstance(definitions, dict) else None
    if not isinstance(subgraphs, list):
        raise RuntimeError("Official FLUX template has no subgraph definitions.")

    matches = [
        sg for sg in subgraphs
        if isinstance(sg, dict)
        and "text to image" in str(sg.get("name", "")).lower()
        and "flux.2 klein 4b" in str(sg.get("name", "")).lower()
        and "distilled" in str(sg.get("name", "")).lower()
    ]
    if len(matches) != 1:
        names = [sg.get("name") for sg in subgraphs if isinstance(sg, dict)]
        raise RuntimeError(f"Could not identify one distilled FLUX.2 Klein text-to-image subgraph: {names}")
    return matches[0]


def _find_branch_instances(workflow: dict, selected_definition: dict) -> tuple[str, list[str]]:
    definitions = workflow.get("definitions", {}).get("subgraphs", [])
    family_ids = {
        str(sg.get("id"))
        for sg in definitions
        if isinstance(sg, dict)
        and "text to image" in str(sg.get("name", "")).lower()
        and "flux.2 klein 4b" in str(sg.get("name", "")).lower()
    }

    selected_type = str(selected_definition.get("id"))
    selected = []
    roots = []
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", ""))
        if node_type in family_ids:
            roots.append(str(node.get("id")))
        if node_type == selected_type:
            selected.append(str(node.get("id")))

    if len(selected) != 1:
        raise RuntimeError(f"Expected one distilled branch instance, found {selected}")
    if len(roots) < 1:
        raise RuntimeError("No FLUX.2 Klein text-to-image branch instances found.")
    return selected[0], sorted(roots, key=lambda x: int(x) if x.isdigit() else x)


def _patch_model_metadata(node: dict, filename: str) -> None:
    properties = node.get("properties")
    models = properties.get("models") if isinstance(properties, dict) else None
    if isinstance(models, list) and models and isinstance(models[0], dict):
        models[0]["name"] = filename


def patch_distilled_definition(
    definition: dict,
    *,
    prompt: str,
    seed: int,
    model_filename: str,
    clip_filename: str,
    vae_filename: str,
    width: int,
    height: int,
) -> None:
    nodes = definition.get("nodes")
    if not isinstance(nodes, list):
        raise RuntimeError("Distilled subgraph has no nodes list.")

    unet = _node_by_type(nodes, "UNETLoader")
    clip = _node_by_type(nodes, "CLIPLoader")
    vae = _node_by_type(nodes, "VAELoader")
    noise = _node_by_type(nodes, "RandomNoise")
    scheduler = _node_by_type(nodes, "Flux2Scheduler")
    cfg = _node_by_type(nodes, "CFGGuider")
    latent = _node_by_type(nodes, "EmptyFlux2LatentImage")
    text = _node_by_type(nodes, "CLIPTextEncode")
    width_node = _primitive_by_title(nodes, "Width")
    height_node = _primitive_by_title(nodes, "Height")

    _set_widget(unet, 0, model_filename)
    _set_widget(clip, 0, clip_filename)
    _set_widget(vae, 0, vae_filename)
    _set_widget(noise, 0, seed)
    _set_widget(noise, 1, "fixed")
    _set_widget(scheduler, 0, 4)
    _set_widget(scheduler, 1, width)
    _set_widget(scheduler, 2, height)
    _set_widget(cfg, 0, 1)
    _set_widget(latent, 0, width)
    _set_widget(latent, 1, height)
    _set_widget(latent, 2, 1)
    _set_widget(text, 0, prompt)
    _set_widget(width_node, 0, width)
    _set_widget(width_node, 1, "fixed")
    _set_widget(height_node, 0, height)
    _set_widget(height_node, 1, "fixed")

    _patch_model_metadata(unet, model_filename)
    _patch_model_metadata(clip, clip_filename)
    _patch_model_metadata(vae, vae_filename)


def patch_shared_prompt(workflow: dict, prompt: str) -> str:
    candidates = [
        node for node in workflow.get("nodes", [])
        if isinstance(node, dict)
        and node.get("type") == "PrimitiveStringMultiline"
        and str(node.get("title", "")).lower() == "prompt"
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one shared Prompt primitive, found {len(candidates)}")
    _set_widget(candidates[0], 0, prompt)
    return str(candidates[0].get("id"))


def activate_branch(workflow: dict, selected_root: str, branch_roots: list[str]) -> None:
    nodes = {str(node.get("id")): node for node in workflow.get("nodes", []) if isinstance(node, dict)}

    for root in branch_roots:
        if root in nodes:
            nodes[root]["mode"] = 0 if root == selected_root else 4

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


def prepare_distilled_text_to_image(
    cli,
    template_name: str,
    workflow_path: Path,
    *,
    prompt: str,
    seed: int,
    model_filename: str,
    clip_filename: str,
    vae_filename: str,
    width: int = 768,
    height: int = 1024,
) -> dict:
    cli.fetch_template(template_name, workflow_path)
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))

    definition = _find_distilled_definition(workflow)
    selected_root, roots = _find_branch_instances(workflow, definition)

    patch_distilled_definition(
        definition,
        prompt=prompt,
        seed=seed,
        model_filename=model_filename,
        clip_filename=clip_filename,
        vae_filename=vae_filename,
        width=width,
        height=height,
    )
    prompt_node = patch_shared_prompt(workflow, prompt)
    activate_branch(workflow, selected_root, roots)

    selected_node = next(
        n for n in workflow.get("nodes", [])
        if isinstance(n, dict) and str(n.get("id")) == selected_root
    )
    selected_node["widgets_values"] = []

    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")

    return {
        "selected_root": selected_root,
        "branch_roots": roots,
        "prompt_node": prompt_node,
        "model_filename": model_filename,
        "clip_filename": clip_filename,
        "vae_filename": vae_filename,
        "workflow": str(workflow_path),
    }
