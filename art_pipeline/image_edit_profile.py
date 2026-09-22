from __future__ import annotations

import json
from pathlib import Path


def _set_widget(node: dict, index: int, value) -> None:
    values = node.get("widgets_values")
    if not isinstance(values, list):
        values = []
        node["widgets_values"] = values
    while len(values) <= index:
        values.append(None)
    values[index] = value


def _edit_definition(workflow: dict) -> dict:
    subgraphs = (workflow.get("definitions") or {}).get("subgraphs") or []
    matches = [
        item for item in subgraphs
        if isinstance(item, dict)
        and "image edit" in str(item.get("name", "")).lower()
        and "flux.2 klein 4b distilled" in str(item.get("name", "")).lower()
    ]
    if len(matches) != 1:
        names = [item.get("name") for item in subgraphs if isinstance(item, dict)]
        raise RuntimeError(f"Expected one distilled FLUX image-edit definition, found: {names}")
    return matches[0]


def _single_image_root(workflow: dict, definition: dict) -> dict:
    definition_id = str(definition.get("id"))
    roots = [
        node for node in workflow.get("nodes", [])
        if isinstance(node, dict) and str(node.get("type")) == definition_id
    ]
    matches = []
    for node in roots:
        names = [str(item.get("name")) for item in node.get("inputs", []) if isinstance(item, dict)]
        if names.count("image") == 1 and "image_1" not in names:
            matches.append(node)
    if len(matches) != 1:
        raise RuntimeError(f"Expected one single-image edit root, found {len(matches)}")
    return matches[0]


def _linked_node(workflow: dict, root: dict, *, input_name: str | None = None, output=False) -> dict:
    nodes = {str(node.get("id")): node for node in workflow.get("nodes", []) if isinstance(node, dict)}
    root_id = str(root.get("id"))
    if input_name is not None:
        item = next((x for x in root.get("inputs", []) if x.get("name") == input_name), None)
        if not item or item.get("link") is None:
            raise RuntimeError(f"Edit root has no linked {input_name!r} input")
        link_id = str(item["link"])
        link = next((x for x in workflow.get("links", []) if str(x[0]) == link_id), None)
        if not link:
            raise RuntimeError(f"Edit input link not found: {link_id}")
        return nodes[str(link[1])]

    if output:
        link = next(
            (x for x in workflow.get("links", []) if str(x[1]) == root_id),
            None,
        )
        if not link:
            raise RuntimeError("Edit root has no output link")
        return nodes[str(link[3])]
    raise RuntimeError("Linked-node direction was not specified")


def _patch_definition_models(definition: dict, model: str, clip: str, vae: str) -> None:
    nodes = definition.get("nodes") or []
    wanted = {"UNETLoader": model, "CLIPLoader": clip, "VAELoader": vae}
    for node_type, filename in wanted.items():
        matches = [node for node in nodes if isinstance(node, dict) and node.get("type") == node_type]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one {node_type} in edit definition, found {len(matches)}")
        _set_widget(matches[0], 0, filename)


def prepare_distilled_image_edit(
    cli,
    template_name: str,
    workflow_path: Path,
    *,
    prompt: str,
    seed: int,
    input_image: str,
    model_filename: str,
    clip_filename: str,
    vae_filename: str,
) -> dict:
    cli.fetch_template(template_name, workflow_path)
    workflow = json.loads(workflow_path.read_text(encoding="utf-8"))

    definition = _edit_definition(workflow)
    root = _single_image_root(workflow, definition)
    loader = _linked_node(workflow, root, input_name="image")
    saver = _linked_node(workflow, root, output=True)

    if loader.get("type") != "LoadImage":
        raise RuntimeError(f"Expected LoadImage feeding edit root, got {loader.get('type')}")
    if saver.get("type") != "SaveImage":
        raise RuntimeError(f"Expected SaveImage after edit root, got {saver.get('type')}")

    _set_widget(loader, 0, input_image)
    _set_widget(loader, 1, "image")
    for index, value in enumerate(
        [model_filename, clip_filename, vae_filename, prompt, seed]
    ):
        _set_widget(root, index, value)
    _patch_definition_models(definition, model_filename, clip_filename, vae_filename)

    edit_types = {
        str(item.get("id"))
        for item in (workflow.get("definitions") or {}).get("subgraphs", [])
        if isinstance(item, dict) and "image edit" in str(item.get("name", "")).lower()
    }
    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        if str(node.get("type")) in edit_types:
            node["mode"] = 0 if str(node.get("id")) == str(root.get("id")) else 4
        if node.get("type") == "SaveImage":
            node["mode"] = 0 if str(node.get("id")) == str(saver.get("id")) else 4

    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(json.dumps(workflow, indent=2) + "\n", encoding="utf-8")
    return {
        "root_id": str(root.get("id")),
        "load_image_id": str(loader.get("id")),
        "save_image_id": str(saver.get("id")),
        "workflow": str(workflow_path),
    }
