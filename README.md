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

## Product North Star

Black-Ink Bestiary is an eight-book line of approximately 50-page, 2024-SRD-monster coloring books. Books are primarily organized by environment/location while retaining monster-family variety.

Every finished page must have:

- one large, accurate, dominant monster
- a distinctive believable habitat, lair, or territory
- a clear story moment readable at thumbnail size
- a stable natural pose appropriate for a static coloring page
- large, clean, satisfying coloring regions
- pure black line art on white
- a composition that preserves 8.5 × 11 KDP-safe output

The universal monster engine supplies reusable creature identity and anti-drift logic. The universal page engine supplies composition, environment, physicality, coloring, and approval rules. Monster and page JSON should contain only the small amount of information that makes that subject or scene unique.

The current production print target is 8.5 × 11 inches, portrait, non-bleed, 300 DPI final raster equivalent (2550 × 3300 px). Working-generation images may be smaller but must preserve that aspect and safe composition.

## Universal Monster Engine

New monster files are intentionally tiny. `config/universal_monster_contract.json` resolves a minimal monster recipe through reusable family DNA.

Typical new monster:

```json
{
  "schema_version": 3,
  "monster_id": "bugbear-scout",
  "monster_name": "Bugbear Scout",
  "family_profile": "bugbear",
  "variant_traits": ["scout", "watchful"]
}
```

The family supplies anatomy, anti-drift rules, locomotion, accuracy checks, and known failure corrections. The page supplies only scene-specific information. Use `python scripts/scaffold_monster.py ...` to create new recipes.

## Universal Page Engine

Every Black-Ink book uses `config/universal_page_contract.json`.

A new page stores only its unique recipe:

- monster spec
- environment profile
- story moment and scene archetype
- unique landmark, framing, and monster/environment interaction
- physical state, support/contact, and motion

Monster name, creature-family anatomy, habitat description, composition, coloring rules, global avoid rules, environment accuracy, and house style are inherited automatically. The current eight books all point at this same contract.

New books can use any page count:

```powershell
python scripts/scaffold_book.py TOME-IX "New Tome" --pages 40 --prefix IX --theme "..." --environment-scope "..."
```

After every page recipe is filled:

```powershell
python scripts/promote_book_plan.py TOME-IX
python scripts/activate_book.py TOME-IX
```

## Production Platform

The Studio is now book-configurable. `data/series.json` registers eight books, while `config/studio.json` selects the active production book. Shared creature identity, environment accuracy, colorability, defect routing, and scene archetypes live in reusable JSON catalogs so fixes improve future books without duplicating Python logic.

Before starting production on any active book:

```powershell
python scripts/audit_active_book.py
```

For a brand-new active book state:

```powershell
python scripts/init_active_book.py
```

See [Production Platform](docs/PRODUCTION_PLATFORM.md) for the data contract and quality-routing rules.

## Product Rules

- One current page at a time.
- Pages stay in strict book order.
- Pure black line art on white.
- Large, bold, simple coloring regions with a substantial monster and 2–4 major environment forms.
- Monster shown in an accurate natural habitat or believable lair selected from a specific environment profile.
- Backgrounds must vary by landmark, framing, depth structure, or monster/environment interaction; broad labels like "cave" or "ocean" are not enough.
- No grayscale wash, painterly shading, decorative border, or text in the artwork.
- Approved pages are immutable until deliberately unlocked.
- AI proposes; the human reviewer makes the final decision.
- Keep the system focused on monster coloring pages only.

## Documentation

- [Production System](docs/MONSTER_COLORING_SYSTEM.md)
- [Canonical Monster Spec Standard](docs/MONSTER_SPEC_STANDARD.md)
- [Environment & Background Standard](docs/ENVIRONMENT_CATALOG.md)
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
