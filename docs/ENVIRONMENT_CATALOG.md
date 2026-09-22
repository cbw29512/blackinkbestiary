# Environment & Background Catalog Standard

Black-Ink treats the environment as a reusable data asset, not prompt filler.

## Three-Layer Environment Model

Every production page resolves:

1. **Environment family** — underground, forest, ocean, undead sites, wilderness, dragon lairs, mythic sites, or giant territories.
2. **Environment profile** — a concrete subtype such as limestone drip cave, basalt lava tube, talus boulder cave, kelp forest, deep-sea coral garden, shipwreck field, or hydrothermal vent field.
3. **Page variant** — a unique landmark, framing choice, and monster/environment interaction.

The page fingerprint is derived from the profile plus those three variant fields. Exact duplicate fingerprints are rejected by manifest validation.

## Accuracy Rule

Broad labels alone do not enter production.

Bad:
- cave
- ocean
- forest
- crypt
- ruin

Good:
- limestone drip cave with flowstone shelf
- basalt lava tube with collapsed skylight
- kelp forest with rocky holdfast shelf
- deep-sea coral garden on a seamount ledge
- catacomb niche passage with stone coffin bay

Environment catalogs are grounded in recognizable real habitat/geology distinctions where applicable. Fantasy architecture may be invented, but it must still be internally coherent and appropriate to the creature and story moment.

## Coloring-Book Rule

Environment accuracy does not justify clutter.

Use:
- 2–4 major environmental forms
- broad contiguous coloring regions
- clear overlaps and perspective
- one strong landmark
- one readable monster/environment interaction
- sparse secondary detail

Avoid:
- pebble, leaf, bubble, scale, brick, crack, coin, coral, mushroom, or rubble wallpaper
- dozens of tiny enclosed coloring cells
- giant foreground props that hide the monster
- monster scaling that erases the habitat
- empty background caused by over-simplification

## Current Benchmark Direction

The production target borrows the accessibility principles common to successful bold-and-easy coloring books: large simple designs, strong outlines, and easy-to-color spaces. Black-Ink adds more specific fantasy creature identity and environment storytelling while retaining that colorability.

## Book Planning Rule

All future 50-page book plans include:
- `monster_spec_id`
- `environment_profile_id`
- `environment_variant.landmark`
- `environment_variant.framing`
- `environment_variant.interaction`
- `habitat`
- `moment`
- `archetype`

A future book is only promoted from setup planning into production after every slot is populated and the production audit passes.
