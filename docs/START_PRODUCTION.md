# Start Production

For the normal Windows workflow, use one entry point:

`START_BLACKINK.bat`

## First run

It automatically:

1. installs the pinned project-local tools,
2. installs the dedicated pinned ComfyUI workspace if needed,
3. downloads and verifies the exact FLUX.2 Klein model files,
4. starts local ComfyUI,
5. validates the official templates,
6. runs the I-01 calibration generation,
7. runs basic QA,
8. starts the review Studio,
9. registers the candidate,
10. opens the Studio in the browser.

The first run downloads roughly 12.5 GB of model weights.

## Later runs

Verified model files and the dedicated ComfyUI workspace are reused. The installer refuses to silently auto-update the production stack.

## Safety rule

A failed setup, failed generation, failed QA, or failed candidate registration **never advances the Tome**.

I-02 remains locked until I-01 receives an explicit **APPROVE & LOCK** decision.

## RTX 5060 Ti fallback

If generation reports a DynamicVRAM / VBAR / CUDA OOM failure, use:

`RESTART_AI_SAFE_MODE.bat`

Then re-run:

`SMOKE_TEST_I01.bat`

Do not switch models or install random nodes as the first troubleshooting step.
