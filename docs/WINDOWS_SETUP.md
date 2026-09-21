# Windows Local Setup

Black-Ink Bestiary now uses a deliberately controlled local stack.

## Step 1 — Prepare the project tools

Double-click:

`PREPARE_LOCAL_AI.bat`

It:
1. finds Python 3.10+,
2. creates a project-local `.blackink-tools` environment,
3. installs **comfy-cli 1.20.0** there,
4. runs the Black-Ink local AI doctor.

It does not change unrelated Python environments.

## Step 2 — Doctor result

The doctor checks the real machine, not assumptions:

- Python version
- comfy-cli availability
- whether ComfyUI is running at `127.0.0.1:8188`
- ComfyUI version
- PyTorch version
- GPU name and VRAM
- launch arguments
- exact required model filenames

It writes the machine-specific result to:

`data/local-environment.json`

That file is gitignored.

## Step 3 — Local ComfyUI

Use one known-good ComfyUI install for this project.

Do **not** install random custom nodes.

Do **not** update ComfyUI in the middle of a book once we have a verified production combination.

The target machine is an RTX 5060 Ti 16 GB system. Current ComfyUI has had Blackwell/DynamicVRAM regressions reported in 2026, so the first successful production combination will be recorded and pinned.

## Step 4 — Models

The required initial model set is exactly:

- `models/diffusion_models/flux-2-klein-4b-fp8.safetensors`
- `models/text_encoders/qwen_3_4b.safetensors`
- `models/vae/flux2-vae.safetensors`

Do not add Qwen Image Edit, LoRAs, or other models until FLUX.2 Klein has completed the I-01 approval loop.

## Step 5 — Official templates

Once the server and model files are present, run:

`python art_pipeline/validate_local_templates.py`

This fetches and validates:
- `image_flux2_klein_text_to_image`
- `image_flux2_klein_image_edit_4b_distilled`

It also records the live template slots so the worker does not rely on guessed node addresses.

## Production gate

We do not advance to I-02 until I-01 has successfully completed generation, QA, supervised review, human decision, and final lock.
