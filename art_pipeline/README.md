# Art Pipeline

This folder is the local generation side of Black-Ink Bestiary.

## Production stack

The researched and locked stack is documented in:
- `docs/LOCAL_AI_STACK.md`
- `config/local_ai_stack.json`

Primary path:
- ComfyUI
- official `comfy-cli==1.20.0`
- official Comfy workflow templates
- FLUX.2 [klein] 4B distilled FP8
- core nodes only

The direct HTTP client in `comfy_client.py` remains as a fallback and for lightweight status calls.

## Current responsibilities

- read the single current Tome page
- build a stable Black-Ink prompt from page JSON + latest human notes
- verify the local ComfyUI server
- verify the exact required model files
- fetch and validate the official FLUX templates against the live install
- inspect current template slots instead of hard-coding stale addresses
- generate only the current ordered page
- collect outputs
- run QA before a candidate reaches the Studio

## One-click preparation

From Windows:

`PREPARE_LOCAL_AI.bat`

This creates a project-local tools environment and installs the pinned official `comfy-cli`. It does **not** silently install a second image-model ecosystem or custom nodes.

## Useful commands

```bash
python art_pipeline/worker.py --check
python art_pipeline/worker.py --prompt
python scripts/blackink_doctor.py
```

After ComfyUI and the required models are present:

```bash
python art_pipeline/validate_local_templates.py
```

That fetches the current official templates, lists their real slots, and validates them against the local ComfyUI installation.

## Templates

New page:
- `image_flux2_klein_text_to_image`

MODIFY:
- `image_flux2_klein_image_edit_4b_distilled`

Template slot addresses are intentionally discovered from the installed template instead of frozen in source code.

## Legacy API-workflow fallback

The earlier tokenized API workflow adapter remains available if an upstream template/CLI regression requires it.

It is a fallback, not the preferred production path.

## No-cloud rule

The Black-Ink production pipeline is local-first. We do not use Comfy partner generation or cloud credits for routine book production.
