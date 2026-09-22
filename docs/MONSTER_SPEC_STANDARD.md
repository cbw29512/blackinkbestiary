# Universal Monster Recipe Standard

Black-Ink separates **species intelligence** from **monster recipes**.

## Core rule

> Family profiles carry anatomy, silhouette, anti-drift rules, accuracy checks, locomotion, and other reusable species knowledge. Individual monster files should only describe what differs.

The universal resolver is `config/universal_monster_contract.json`.

## New monster recipe

New monsters should normally use schema version 3:

```json
{
  "schema_version": 3,
  "monster_id": "bugbear-stalker",
  "monster_name": "Bugbear Stalker",
  "family_profile": "bugbear",
  "variant_traits": ["stealth-focused", "patient", "watchful"]
}
```

Required recipe fields:
- `monster_id`
- `monster_name`
- `family_profile`

Optional fields exist only for genuine differences:
- `variant_traits[]`
- `locomotion`
- `visual_overrides`
- `default_habitats[]`

Do **not** copy family anatomy into every monster.

## Family profile owns

`data/monster_families/<family>.json` owns taxonomy, normal size, core identity, silhouette, head/body anatomy, surface rules, must-keep features, must-avoid drift, locomotion defaults, accuracy checks, and known failure modes.

Known failure modes are injected into generation and supervisor review automatically. They are active production rules, not documentation.

## Page recipe owns

A coloring-page recipe owns the monster choice, environment profile, story moment, scene archetype, unique landmark/framing/interaction, physical support/motion, and only scene-specific props or exceptions.

Species anatomy should not be repeated in the page.

## Creating monsters

```powershell
python scripts/scaffold_monster.py bugbear-scout "Bugbear Scout" bugbear --traits "scout,watchful,stealth-focused"
```

## Resolution order

1. universal monster defaults
2. family profile
3. minimal monster recipe
4. optional visual overrides
5. universal page engine
6. page-specific scene recipe
7. latest human review corrections

## Validation

CI rejects invalid minimal recipes, missing family profiles, unresolved monster specs, repeated families without reusable family DNA, malformed family identity, and missing family accuracy/failure rules.

Legacy full monster JSON remains supported while older content is migrated, but new content should use minimal recipes.
