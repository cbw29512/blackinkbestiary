# Windows Local Setup

The repository is designed so the human setup work stays small.

## One-click check

Double-click:

`CHECK_LOCAL_SETUP.bat`

It checks:
1. Python is available.
2. ComfyUI is running locally at `127.0.0.1:8188`.
3. The Black-Ink worker files are present.

The Studio itself also shows **Local artist connected/offline** in the header.

## Important

Do **not** install random custom nodes or alternate workflows for this project.

Black-Ink Bestiary will use one approved FLUX.2 Klein workflow and one controlled model set. This keeps generations reproducible and prevents the local art stack from drifting.

## What is intentionally not automated yet

The large model download and final ComfyUI API workflow are not installed by this script yet.

Those are the last machine-specific pieces. They will be added only against the actual ComfyUI installation on the production PC so we do not guess its folders or version.
