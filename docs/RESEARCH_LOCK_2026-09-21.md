# Black-Ink Bestiary — Verified Local AI Stack

**Verified:** 2026-09-21

This file locks the current v1 generation stack so the project does not drift.

## Decision

Use **ComfyUI + FLUX.2 [klein] 4B distilled FP8** as the primary local model for both:
- text-to-image generation
- fast image editing / targeted MODIFY passes

Do not add a second generation model to v1 unless real I-01 testing proves it is necessary.

## Why This Stack

Black Forest Labs' official model documentation confirms FLUX.2 [klein] 4B:
- supports text-to-image
- supports image editing
- supports multiple reference images
- is intended for consumer GPUs
- is Apache 2.0 licensed
- is recommended in distilled form for production and interactive use

ComfyUI publishes official Flux.2 Klein 4B workflows, including:
- text-to-image
- Base image edit
- distilled fast image edit

The distilled ComfyUI workflow uses the same main FP8 diffusion model we need for generation, so v1 can stay on one model set.

## Locked v1 Model Files

### Text Encoder
`qwen_3_4b.safetensors`

Location:
`ComfyUI/models/text_encoders/`

Official workflow source:
`https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b.safetensors`

### Diffusion Model
`flux-2-klein-4b-fp8.safetensors`

Location:
`ComfyUI/models/diffusion_models/`

Official BFL workflow source:
`https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8/resolve/main/flux-2-klein-4b-fp8.safetensors`

### VAE
`flux2-vae.safetensors`

Location:
`ComfyUI/models/vae/`

Official ComfyUI workflow source:
`https://huggingface.co/Comfy-Org/flux2-dev/resolve/main/split_files/vae/flux2-vae.safetensors`

## Hardware Fit

BFL documents the full 4B model at roughly 13 GB VRAM.

ComfyUI's official FP8 workflow documentation reports lower runtime VRAM than that full-precision reference implementation.

The production machine has 16 GB dedicated NVIDIA VRAM, so the 4B path is the correct first target.

Do not move to the 9B model for v1:
- it adds unnecessary memory pressure
- its license differs from the Apache-2.0 4B release
- it does not solve a proven Black-Ink requirement yet

## Generation Strategy

### New Page
Use distilled 4B text-to-image.

Generate several candidates from the page JSON.

### MODIFY
Prefer distilled 4B image editing using the selected current candidate as the reference.

The modification prompt must contain:
- PRESERVE
- CHANGE
- AVOID

### REGENERATE
Return to fresh text-to-image using the page JSON and approved style references.

## ComfyUI API

The official ComfyUI examples use:
- `POST /prompt`
- `GET /history/{prompt_id}`
- `GET /view`
- optional WebSocket execution monitoring

Black-Ink may poll history in v1 because only one page is active at a time. WebSocket monitoring is an optimization, not a requirement for correctness.

## Workflow Rule

Use an official ComfyUI Flux.2 Klein workflow as the source of truth.

Do not invent a graph from memory.

The Black-Ink worker consumes an API-format workflow with controlled prompt and seed injection.

## Commercial / Licensing

The BFL FLUX.2 [klein] 4B model is published under Apache 2.0 and its model card explicitly identifies commercial use.

The 9B models use a different non-commercial license and are not part of the v1 production stack.

For fantasy game compatibility, use only monster/content names that are:
- original/generic fantasy, or
- confirmed in the chosen SRD release.

Wizards' SRD 5.2.1 is available under CC-BY-4.0. Its official guidance permits creators to publish and sell compatible works with attribution and permits descriptions such as "5E compatible." It also explicitly notes that some D&D-branded monsters are omitted for IP reasons.

Therefore:
- do not use D&D logos
- do not imply Wizards affiliation
- do not assume every famous D&D monster name is commercially reusable
- maintain an SRD provenance check on the manifest before publication

## v1 Success Criterion

Do not judge the technology stack from synthetic benchmarks.

The actual gate is I-01:

```
I-01 JSON
→ distilled FLUX.2 Klein 4B
→ multiple candidates
→ QA
→ supervised selection/refinement
→ human APPROVE / MODIFY / REGENERATE
→ approved master locked
```

If I-01 can complete this loop at the target quality, the stack is admitted for Tome I.
