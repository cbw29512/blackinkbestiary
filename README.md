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

The Studio drives the local worker directly:
- **Approve & Lock** archives the approved PNG and automatically starts the next canonical page.
- **Modify** stores the review notes and automatically starts a revised attempt.
- **Regenerate** keeps the same page and automatically starts a fresh attempt.
- **Generate Current Page** is the manual retry/fallback control.

Approved pages are copied into strict book order under:

```
web/approved/Tome-I/I-01.png
web/approved/Tome-I/I-02.png
...
```

Candidate attempts remain under `web/candidates/`; only human-approved pages enter the ordered book folder.

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
- [Canonical Monster Spec Standard](docs/MONSTER_SPEC_STANDARD.md)
- [Style Bible](docs/STYLE_BIBLE.md)
- [Tome I Manifest](docs/TOME_I_MANIFEST.md)
- [Logo Brief](docs/LOGO_BRIEF.md)

## Commercial / IP Note

The brand should not use D&D logos, Wizards of the Coast trade dress, or imply affiliation. Before commercial publication, every creature/page should be checked against the intended open-license source list and attribution requirements.

## Current Phase

**Tome I production lane is prepared for all 50 ordered pages.**

Every Tome I page now has:
- a canonical monster identity spec
- concrete page-specific visual requirements
- strict ordered generation/review state
- technical PNG QA including line-art content checks

Production still requires human approval for every final page:

```
spec → generation → technical QA → human review → edit/regenerate as needed → approve & lock → next page
```
