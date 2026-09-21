# Windows Local Setup

Black-Ink Bestiary uses one controlled local AI stack.

## Normal setup: one file

Double-click:

`INSTALL_BLACKINK_AI.bat`

That script performs the complete initial machine setup:

1. creates a project-local Python tools environment,
2. installs pinned **comfy-cli 1.20.0**,
3. installs pinned **ComfyUI 0.36.0** into `.blackink-comfy`,
4. skips ComfyUI-Manager and all custom nodes,
5. downloads exactly three required FLUX.2 Klein files,
6. verifies every model file by SHA256 before accepting it,
7. launches ComfyUI locally on `127.0.0.1:8188`,
8. fetches the two official FLUX.2 Klein workflow templates,
9. validates them against the live local installation,
10. records the real Python / PyTorch / GPU / VRAM / launch environment.

The model payload is roughly 12.5 GB, so the first run can take a while depending on internet speed.

## Pinned production stack

- ComfyUI: **0.36.0**
- comfy-cli: **1.20.0**
- FLUX.2 [klein] 4B distilled FP8
- official ComfyUI core nodes only
- no custom nodes
- no automatic updates during a book

The exact stack and model hashes are in:

- `docs/LOCAL_AI_STACK.md`
- `config/local_ai_stack.json`

## If the normal 5060 Ti run hits DynamicVRAM trouble

Do not reinstall models or change the image model.

First run:

`RESTART_AI_SAFE_MODE.bat`

That restarts the dedicated Black-Ink ComfyUI workspace with:

`--disable-dynamic-vram`

This exists because recent ComfyUI issue reports include DynamicVRAM/VBAR/OOM failures on RTX 5060-family hardware. We use it only if the actual production machine reproduces the problem.

## Diagnostics

`PREPARE_LOCAL_AI.bat`
: install/check only the project tooling.

`CHECK_LOCAL_SETUP.bat`
: lightweight server/tool check.

`VALIDATE_LOCAL_TEMPLATES.bat`
: re-fetch and validate official templates.

`scripts/blackink_doctor.py`
: writes the machine report to `data/local-environment.json`.

## Production gate

Do not advance to I-02 until I-01 has completed:

```
page JSON
→ FLUX generation
→ QA
→ supervisor
→ human review
→ APPROVE & LOCK
```
