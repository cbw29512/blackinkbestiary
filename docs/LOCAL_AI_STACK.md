# Black-Ink Bestiary — Locked Local AI Stack

**Decision date:** 2026-09-21  
**Scope:** Tome I monster coloring-page production only.

This file records the researched production stack so the project does not drift every time a new image model appears.

## Decision

### Primary image model

**FLUX.2 [klein] 4B — distilled, FP8**

Use it for:
- new coloring-page generation
- fast iterations
- targeted image editing / MODIFY passes

Why:
- Black Forest Labs lists the 4B distilled model as supporting text-to-image, single-reference editing, and multi-reference editing.
- The 4B family is Apache 2.0.
- BFL recommends the distilled 4-step variant for production / interactive workflows and the Base model for fine-tuning / maximum flexibility.
- Official Comfy templates exist for both text-to-image and 4B distilled image editing.

We are **not** starting with 9B, FLUX.2 dev, LoRAs, or custom nodes.

## Orchestration

**ComfyUI + official comfy-cli**

Primary orchestration:
- `comfy-cli==1.20.0`
- official ComfyUI workflow templates
- official core nodes only

The repository's direct HTTP Comfy client remains as a fallback and for health/status operations.

Why:
- comfy-cli is maintained by Comfy-Org.
- It can install/launch ComfyUI, inspect system stats, manage model downloads, validate workflows, fetch official templates, run templates/workflows, monitor jobs, and download outputs.
- Using the official CLI reduces custom workflow glue and version drift.

## Official templates

### New page
`image_flux2_klein_text_to_image`

### Targeted MODIFY pass
`image_flux2_klein_image_edit_4b_distilled`

Before running a template on a production machine:
1. check that the local ComfyUI version can validate it;
2. inspect its current slots;
3. set only the required prompt / image / seed / dimension values;
4. smoke-test it on I-01.

Do not hard-code template slot addresses until the installed version has been inspected. Official templates now use subgraphs and promoted widgets, and those addresses can evolve.

## Required model files

### Diffusion model
- folder: `models/diffusion_models`
- file: `flux-2-klein-4b-fp8.safetensors`
- source: Black Forest Labs official Hugging Face repository
- size: about 4.07 GB
- SHA256: `97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6`

### Text encoder
- folder: `models/text_encoders`
- file: `qwen_3_4b.safetensors`
- source: Comfy-Org official Hugging Face repository used by the official template
- size: about 8.04 GB
- SHA256: `6c671498573ac2f7a5501502ccce8d2b08ea6ca2f661c458e708f36b36edfc5a`

### VAE
- folder: `models/vae`
- file: `flux2-vae.safetensors`
- source: Comfy-Org official FLUX.2 model repository
- size: about 336 MB
- SHA256: `d64f3a68e1cc4f9f4e29b6e0da38a0204fe9a49f2d4053f0ec1fa1ca02f9c4b5`

Expected model-weight download is roughly **12.5 GB** before normal filesystem overhead.

## 5060 Ti production policy

The target machine has an NVIDIA RTX 5060 Ti with 16 GB VRAM.

The model itself is a reasonable fit: BFL describes Klein 4B as a consumer-GPU model around the 8 GB VRAM class, and Comfy's published benchmark lists the 4B distilled path at about 8.4 GB VRAM on its test system.

However, ComfyUI has had 2026 Blackwell / DynamicVRAM regressions reported on RTX 5060-family systems. Therefore:

1. **Do not blindly auto-update ComfyUI during a book.**
2. Start with a current stable build that supports the required official templates.
3. Smoke-test I-01 repeatedly.
4. Once stable, record and pin:
   - ComfyUI version
   - comfy-cli version
   - Python version
   - PyTorch version
   - launch arguments
   - GPU name / VRAM
   - exact model filenames and hashes
5. If DynamicVRAM causes VBAR/OOM instability, test the documented workaround on that machine rather than changing models immediately.
6. No custom nodes until the core FLUX workflow is proven stable.

## Coloring-book quality gate

FLUX.2 Klein is a general image model, not a purpose-built coloring-book model. Its official capabilities prove generation/editing support and hardware fit; they do **not** prove that every prompt will naturally produce our exact clean line-art house style.

Therefore I-01 is a real go/no-go art test, not a ceremonial smoke test.

Order of escalation if the first outputs are too photographic or too dense:

1. strengthen the Black-Ink prompt and negative style rules;
2. use the existing strong I-01 artwork as an image-edit reference instead of restarting;
3. once we have approved pages, use them as **style references** while explicitly preserving each new page's independent composition;
4. only if the Golden reference approach still cannot hold the style, evaluate one controlled Black-Ink adaptation/LoRA trained from licensed material.

Do **not** respond to a bad page by installing a pile of community LoRAs or models.

The production target remains: a strong result on pass 1 and an approval-quality targeted correction on pass 2.

## Fallback model

**Qwen-Image-Edit-2511** is reserved only as a later fallback if FLUX.2 Klein cannot preserve approved composition closely enough during MODIFY passes.

It is **not** part of the initial install.

Reasons:
- strong instruction-based editing is attractive;
- its normal local stack is substantially heavier;
- adding a second model before FLUX is proven would complicate a system whose job is intentionally narrow.

## What we are deliberately not doing

- no Stable Diffusion model zoo
- no custom node packs
- no LoRA training yet
- no auto-updating ComfyUI
- no cloud generation dependency
- no second primary model
- no hand-built giant node graph
- no generation beyond the current ordered page

## Production gate

I-02 remains blocked until I-01 proves:

```
page JSON
→ prompt
→ local FLUX generation
→ QA
→ supervisor review
→ human APPROVE / MODIFY / REGENERATE
→ approved master locked
```

## Research sources

Primary sources consulted on 2026-09-21:
- Black Forest Labs official FLUX.2 repository: https://github.com/black-forest-labs/flux2
- BFL FLUX.2 Klein 4B FP8 model: https://huggingface.co/black-forest-labs/FLUX.2-klein-4b-fp8
- Comfy-Org official workflow templates: https://github.com/Comfy-Org/workflow_templates
- Comfy-Org official comfy-cli: https://github.com/Comfy-Org/comfy-cli
- comfy-cli PyPI release: https://pypi.org/project/comfy-cli/
- ComfyUI core server/API: https://github.com/Comfy-Org/ComfyUI
