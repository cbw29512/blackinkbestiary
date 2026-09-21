# Black-Ink Bestiary

**Fantasy Monsters in Their Natural Habitat**

Black-Ink Bestiary is a focused production system for creating consistent, print-ready fantasy monster coloring pages one page at a time.

## v1 Goal

Produce **Tome I — Caves & Dungeons**, 50 pages in strict order.

The workflow is intentionally simple:

```
PAGE SPEC → LOCAL AI → QA → SUPERVISOR → HUMAN REVIEW
                                      ↓
                        APPROVE / MODIFY / REGENERATE
```

A page cannot advance until it is approved and locked.

## Product Rules

- One current page at a time.
- Pages stay in strict book order.
- Pure black line art on white.
- Large open spaces to color.
- Monster shown in a natural habitat or believable lair.
- No grayscale wash, painterly shading, decorative border, or text in the artwork.
- Approved pages are immutable until deliberately unlocked.
- AI proposes; the human reviewer makes the final decision.
- Keep the system focused on monster coloring pages only.

## Documentation

- [Production System](docs/MONSTER_COLORING_SYSTEM.md)
- [Style Bible](docs/STYLE_BIBLE.md)
- [Tome I Manifest](docs/TOME_I_MANIFEST.md)
- [Logo Brief](docs/LOGO_BRIEF.md)

## Commercial / IP Note

The brand should not use D&D logos, Wizards of the Coast trade dress, or imply affiliation. Before commercial publication, every creature/page should be checked against the intended open-license source list and attribution requirements.

## Local Production

The focused v1 production loop now lives in this repository.

### One-time setup
- `SETUP_WORKER.bat`
- install/run ComfyUI
- `INSTALL_COMFY_MODELS.bat`
- `CHECK_LOCAL_AI.bat`

See [One-Time Local Setup](docs/ONE_TIME_SETUP.md).

### Produce the current page
With ComfyUI running, use:

`START_PRODUCTION.bat`

The worker generates candidates only for the current page, runs coloring-page QA, and sends the best passing result to the local review Studio.

## Current Phase

**I-01 is the only active production page.**

The system is not trusted on later pages until I-01 can complete the full loop:

```
spec → generation → QA → supervised review → approve/modify/regenerate → locked final
```
