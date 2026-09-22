from __future__ import annotations

try:
    from .generation_runtime import TechnicalQAError, collect_output, find_prompt_id
except ImportError:
    from generation_runtime import TechnicalQAError, collect_output, find_prompt_id


def execute_candidate(cli, client, workflow, page_id: str, attempt: int, inspector) -> str:
    """Run one prepared ComfyUI workflow and return the accepted web-relative PNG."""
    result = cli.run_workflow(workflow, timeout=600)
    prompt_id = find_prompt_id(result)
    if not prompt_id:
        raise RuntimeError("ComfyUI generation returned no prompt_id")

    history = client.history(prompt_id).get(prompt_id)
    if not history:
        raise RuntimeError(f"ComfyUI has no completed history entry for {prompt_id}")

    images = client.output_images(history)
    if not images:
        raise RuntimeError("Generation completed but no SaveImage output was found")

    return collect_output(client, images, page_id, attempt, inspector)


__all__ = ["TechnicalQAError", "execute_candidate"]
