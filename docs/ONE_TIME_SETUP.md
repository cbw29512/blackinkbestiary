# One-Time Local Setup

Black-Ink Bestiary is designed so the daily production loop is simple.

## One-time pieces

1. Python worker environment
2. ComfyUI running locally
3. Three FLUX.2 [klein] 4B model files

The repository provides launchers so you do not need to build ComfyUI workflows manually.

## Worker dependencies

Run:

`SETUP_WORKER.bat`

This creates a local `.venv` and installs only the Python packages used by the worker.

## Model installation

After ComfyUI itself is installed, run:

`INSTALL_COMFY_MODELS.bat`

The script looks for a ComfyUI folder containing `models`. If it cannot find one, it asks for that folder once.

It installs:

- diffusion model → `models/diffusion_models/flux-2-klein-4b-fp8.safetensors`
- text encoder → `models/text_encoders/qwen_3_4b.safetensors`
- VAE → `models/vae/flux2-vae.safetensors`

Restart ComfyUI after model installation.

## Verify

With ComfyUI running:

`CHECK_LOCAL_AI.bat`

The check verifies:
- Studio connection
- ComfyUI connection
- required core workflow nodes

## Daily use

With ComfyUI running, double-click:

`START_PRODUCTION.bat`

It:
1. starts the Studio,
2. checks the local AI,
3. generates candidates for the CURRENT page only,
4. runs coloring-page QA,
5. submits the best passing candidate to the Studio.

Then use the Studio buttons:
- APPROVE & LOCK
- MODIFY
- REGENERATE

Run `START_WORKER.bat` again after MODIFY or REGENERATE to produce the next attempt.

The worker cannot advance to another page. Only approval does that.
