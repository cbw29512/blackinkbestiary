# Start Production

For the normal Windows workflow, use one entry point:

`START_BLACKINK.bat`

## What the one-click launcher does

Every run follows the same safe path.

If the pinned local AI stack has not been verified yet, or its install fingerprint no longer matches the configured stack, the launcher:

1. prepares the project-local Python/comfy-cli tools,
2. installs the dedicated pinned ComfyUI workspace if needed,
3. downloads and SHA-256 verifies the required FLUX.2 Klein model files,
4. starts local ComfyUI,
5. validates the official templates against the live install,
6. runs the local AI doctor,
7. records a verified local-stack fingerprint.

The first successful install may download roughly 12.5 GB of model weights.

If the verified local-stack fingerprint is current, those heavy installation checks are skipped.

Then the launcher always:

1. registers the self-healing watchdog for Windows sign-in,
2. starts the watchdog immediately if it is not already running,
3. starts the local status dashboard,
4. synchronizes production engine code from `main`,
5. imports exact-image review authority from `review-previews-live`,
6. runs non-GPU engine preflight,
7. ensures ComfyUI and the advisory local vision reviewer are available,
8. applies exact-image review decisions,
9. regenerates only Canary Nine pages that truly need new pixels,
10. publishes the latest review/diagnostic snapshot back to the review branch.

## Canary gate

The production calibration gate is the **Canary Nine**, not the legacy single I-01 smoke page.

Full-book generation remains blocked until all nine configured canary pages have exact-image approval under the current engine/review authority.

A rejected canary does not advance the Tome. The engine either:

- starts a fresh text-to-image attempt for identity/body-plan failures, or
- performs a preservation-first targeted edit for action/environment/quality failures.

Repeated failures can escalate to a fresh regeneration when the current pixels are no longer worth preserving.

## Self-healing behavior

The watchdog checks the local worker every five minutes.

- If the autopilot process is missing, it restarts it.
- If all runtime/generation/gallery/heartbeat/preflight activity has been stale for 45 minutes, it restarts the stuck process tree.
- A newly started worker receives a startup grace window.
- Restart reasons are written to `data/autopilot-watchdog.log`.
- A stale heartbeat no longer counts as Foundation Readiness.

## Safety rules

A failed setup, sync, preflight, generation, review, publish, or candidate registration never advances the Tome.

The project does not silently:

- change model families,
- install random custom nodes,
- lower review gates,
- accept stale exact-image reviews,
- accept a stale final-interior PDF as package proof.

The final package reaches full print readiness only when a proof PDF/report pair matches the active fully locked book and its SHA-256.

## Legacy diagnostic tools

`SMOKE_TEST_I01.bat` and the I-01 smoke workflow remain available as diagnostics only. They are no longer the normal production entry point.

If generation reports a DynamicVRAM / VBAR / CUDA OOM condition, use:

`RESTART_AI_SAFE_MODE.bat`

Then restart production with:

`START_BLACKINK.bat`
