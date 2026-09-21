# Art Pipeline

This folder is the local generation side of Black-Ink Bestiary.

## Current responsibilities

- read the single current Tome page
- build a stable Black-Ink prompt from the page JSON and latest review notes
- verify whether local ComfyUI is reachable
- submit an approved API-format ComfyUI workflow
- wait for completion and collect image outputs
- perform simple file-level QA before a candidate reaches the Studio

## Commands

From the repository root:

```bash
python art_pipeline/worker.py --check
python art_pipeline/worker.py --prompt
```

Generation is intentionally blocked until `art_pipeline/workflows/flux2_klein_api.json` is installed and validated.

That workflow is the only local-machine-specific piece still required. We do not invent a workflow graph because node/version drift is exactly what this project is designed to avoid.

## Workflow template tokens

The approved API workflow must contain:

- `__BLACKINK_PROMPT__` where the positive prompt text belongs
- `__BLACKINK_SEED__` where the generation seed belongs

The worker replaces those tokens immediately before submission.

## Local API

The worker uses the normal local ComfyUI endpoints:
- `GET /system_stats`
- `POST /prompt`
- `GET /history/{prompt_id}`
- `GET /view`

No cloud service is required for generation.
