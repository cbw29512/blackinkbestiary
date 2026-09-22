# Universal Monster Recipe Standard

Black-Ink separates **family DNA**, **variant DNA**, **monster recipes**, and **page recipes**.

## Core architecture

**family profile -> optional variant profile -> tiny monster recipe -> page recipe**

This hierarchy is mandatory for scale.

### Family DNA

`data/monster_families/<family>.json` owns anatomy and behavior shared by the creature family:

- taxonomy and default size
- core identity and silhouette
- head/body/limb structure
- surface treatment
- must-keep / must-avoid rules
- natural posture and size impression
- general behavior style
- habitat compatibility
- accuracy checks
- known drift failures

### Variant DNA

`data/monster_variants/<variant>.json` owns reusable differences that materially change family identity.

Use a variant profile for things such as:

- swarm form
- giant form when proportions/scale matter
- skeletal or zombie form
- detached limb
- ooze geometry
- construct object type
- mimic disguise type
- web-building vs hunting spider form

Examples:

- `ogre -> ogre-zombie`
- `minotaur -> minotaur-skeleton`
- `ooze -> gelatinous-cube`
- `construct -> animated-armor`
- `mimic -> mimic-door`
- `bat -> bat-swarm`

A variant profile must declare the family it belongs to. The resolver rejects mismatches.

### Monster recipe

Every monster in `data/monsters/` uses schema version 3 and stays intentionally small.

Minimum:

```json
{
  "schema_version": 3,
  "monster_id": "bugbear-stalker",
  "monster_name": "Bugbear Stalker",
  "family_profile": "bugbear"
}
```

With reusable variant DNA:

```json
{
  "schema_version": 3,
  "monster_id": "gelatinous-cube",
  "monster_name": "Gelatinous Cube",
  "family_profile": "ooze",
  "variant_profile": "gelatinous-cube"
}
```

Concise `variant_traits[]` may describe role-level differences such as captain, shrine keeper, or skirmisher when anatomy does not need a separate variant profile.

Monster recipes must not copy:

- visual identity blocks
- family accuracy checks
- known failure modes
- size/body anatomy already owned by family/variant DNA
- reusable room/background/scenery data

### Page recipe

The page owns what is unique to that illustration:

- monster selection
- environment profile
- story moment
- physical support/motion
- page-specific landmark
- framing
- interaction
- required page props

The page does not redefine species anatomy.

## Resolution order

1. universal monster defaults
2. family profile
3. optional reusable variant profile
4. tiny monster recipe
5. exceptional one-off overrides only when unavoidable
6. universal page engine
7. page-specific scene recipe
8. latest human review corrections

## Environment ownership

Monster data may describe habitat compatibility for planning.

It does **not** own reusable walls, floors, ceilings, lighting, traps, furniture, ruins, vegetation, reef features, burial dressing, lair dressing, or depth cues.

If another creature could use the same scenery, the universal environment engine owns it.

## Creating monsters

Family-only:

```powershell
python scripts/scaffold_monster.py bugbear-scout "Bugbear Scout" bugbear --traits "scout,watchful"
```

With reusable variant DNA:

```powershell
python scripts/scaffold_monster.py new-cube "New Cube" ooze --variant gelatinous-cube
```

The scaffolder rejects unknown families, unknown variants, and family/variant mismatches.

## Catalog gate

CI must reject:

- schema versions below 3
- missing family profiles
- missing variant profiles
- variant/family mismatches
- monster recipes containing reusable anatomy blocks
- malformed family DNA
- malformed variant DNA
- unresolved monsters

The current production catalog is expected to resolve all 50 Tome I monsters through reusable family DNA, with variant DNA where the family alone is not specific enough.
