# Local Art Pipeline

This is the only art pipeline used by Black-Ink Bestiary v1.

## Flow

```
current Tome page
→ prompt builder
→ ComfyUI / FLUX.2 [klein] 4B
→ 4 candidates
→ automatic coloring-page QA
→ best technical candidate
→ Studio review
→ APPROVE / MODIFY / REGENERATE
```

The worker never advances the book. Only **Approve & Lock** in the Studio advances to the next page.

## Model Target

The worker is configured for the official ComfyUI FLUX.2 [klein] 4B distilled stack:

- `flux-2-klein-4b-fp8.safetensors`
- `qwen_3_4b.safetensors`
- `flux2-vae.safetensors`

The filenames are centralized in `worker/config.json`.

## Page Modes

### Fresh generation
Used for a queued page or a full REGENERATE.

### Targeted edit
Used for MODIFY when the page has a reference image. The existing composition is supplied to FLUX and the prompt explicitly separates preserve/change/avoid instructions.

I-01 ships with the earlier Kobold reference image so the first production task is a targeted simplification rather than throwing away the composition.

## Automatic QA

QA is deliberately mechanical. It checks:

- portrait aspect
- open white-space ratio
- heavy black coverage
- total ink/detail coverage
- grayscale/midtone density
- accidental color contamination
- near-blank results

The QA layer cannot reliably judge monster anatomy or scene semantics. Those remain part of visual review.

## Safety Rule

If all generated candidates fail QA, nothing is submitted to the Studio and the current page does not advance.

## Local URLs

- Studio: `http://127.0.0.1:8765`
- ComfyUI default: `http://127.0.0.1:8188`

Both can be changed in `worker/config.json`.
