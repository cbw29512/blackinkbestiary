# Black-Ink Bestiary — Engine V2 Tracker

## North Star

Build eight production-quality, approximately 50-page fantasy monster coloring books for KDP using the project's approved 2024 SRD roster.

The system must be universal and reusable:

**universal monster engine → universal environment engine → universal page/coloring engine → tiny unique page recipe → generated page → automated checks → human approval**

New monsters and books should require minimal JSON. Shared intelligence belongs in universal contracts and reusable family/environment profiles.

## Non-Negotiable Page Standard

Every final page must:

- feature one large, dominant, recognizable monster
- keep the monster in a stable, natural, readable pose
- show an unmistakable environment/lair/territory
- make the story moment readable at thumbnail size
- connect the monster to at least one environmental feature
- use pure black line art on white
- preserve large, satisfying coloring regions
- avoid gray wash, dense hatching, clutter, tiny repeated texture, and decorative art borders
- preserve the 8.5 × 11 portrait KDP-safe composition
- feel unique beside the other pages in the book

Approval requires all three thumbnail pillars, but **colorability is the first production constraint**:

1. fun and satisfying to color
2. monster identity
3. environment identity
4. one simple memorable story moment

## Universal Engine Ownership

### Monster engine owns

- family/species anatomy
- silhouette
- head/body/limb structure
- surface treatment
- normal size impression
- locomotion
- must-keep identity
- prohibited look-alikes
- known failure modes and corrections
- family-level behavior tendencies

Individual monster JSON should state only the small number of variant traits that differ.

### Environment engine owns

- spatial type
- material language
- location markers
- spatial geometry/read
- reusable environment variation
- anti-generic-background rules

Page JSON supplies only unique landmark, framing, and interaction.

### Page/coloring engine owns

- one dominant subject
- monster scale and framing
- stable-pose rules
- coloring density
- line hierarchy
- story-beat readability
- monster/environment interaction
- uniqueness
- KDP-safe composition
- approval gates

## Known Failure Patterns

These are engine feedback, not isolated page problems.

- creature drifts into a neighboring species
- bugbear becomes ape/sasquatch
- goblin becomes mascot/cute
- kobold becomes mini-dragon or generic lizard
- non-flyer appears to hover
- monster is too small or loses focal dominance
- environment becomes a generic room/cave/ocean
- setting cannot be identified without caption
- background repeats the same geometry across pages
- monster simply stands and holds props instead of communicating the story beat
- story moment requires a chaotic jump/fall pose that is poor for static coloring
- repeated tiny textures turn coloring into homework
- secondary creatures compete with the primary subject

## Current Engine Status

### Locked foundations

- universal page contract
- universal monster contract
- universal environment contract
- stable natural pose rule
- powered flight gated by monster capability
- environment self-identification rule
- KDP 8.5 × 11 non-bleed production target
- approved project source roster
- environment repetition budget
- page uniqueness fingerprinting
- series-wide readiness audit
- minimal monster recipe support

### Current hardening priorities

1. story-moment engine: one readable static beat instead of portrait/prop posing — **implemented; colorability has priority over story complexity**
2. family DNA audit across every repeated monster family — **implemented; all 14 reusable family profiles pass the expanded DNA contract and catalog audit**
3. environment variation depth across every book family — **implemented; all 8 environment families now inherit geometry, landmark, prop, interaction, and anti-repetition pools**
4. Modify/Regenerate routing based on passed vs failed quality dimensions — **implemented; review state records failed and preserved dimensions**
5. Golden Five reference pages before mass regeneration — **calibration gate implemented; human-approved reference pages still required**

## Working Rule

When a page fails:

1. identify the failed pillar(s)
2. decide whether the failure belongs to universal engine, family/profile, or page-unique recipe
3. fix the highest reusable layer possible
4. add/update a regression test
5. regenerate only after the data/prompt logic is materially improved
6. never approve a page merely because it is better than the previous attempt

## Reset Plan

Old weak artwork may be discarded. Do not delete the engine, catalogs, contracts, tests, or production standards.

The clean rebuild starts only after Engine V2 hardening passes CI.

## Update Discipline

This file is the persistent project checkpoint. Update it whenever:

- a new universal rule is adopted
- a recurring failure mode is discovered
- a major engine blocker is fixed
- the next production priority changes

Do not let chat-only decisions become the sole source of truth.


## Story vs. Coloring Rule

Story helps sell the page, but the product is a coloring book.

Priority:

1. fun and satisfying to color
2. recognizable monster
3. unmistakable environment
4. one simple memorable story beat

If a stronger story requires extra figures, tiny props, dense texture, unstable motion, or more enclosed coloring cells, simplify the story instead.

Preferred story formula:

**one clear verb + simple body language + one environmental interaction**

Do not turn a coloring page into a busy narrative illustration.


## 2026-09-22 Colorability Enforcement Update

The written rule is now being enforced in engine behavior, not just documentation:

- review defects map to explicit quality dimensions
- MODIFY preserves dimensions that passed and targets only failed dimensions
- REGENERATE is used for fundamental failures such as a page that is structurally uncolorable
- generation prompts state that colorability governs monster/environment/story complexity
- environment and archetype rules no longer describe the three visual requirements as co-equal with coloring usability
- new first-class colorability defects include cramped coloring spaces, excessive line density, story-overload, and fundamentally uncolorable composition

**Next hardening priority:** family DNA coverage across every repeated monster family, followed by environment-variation depth and the Golden Five reference pages.


## 2026-09-22 Monster Family DNA Update

The universal monster contract now requires reusable families to define limbs/extremities, size impression, stable natural posture, visual behavior style, and environment fit in addition to anatomy and anti-drift rules.

The catalog audit reads these required paths from the contract itself. This intentionally makes CI fail until every reusable family is upgraded, preventing partial family coverage from being treated as production-ready.

Variant monster JSON remains minimal. A variant may use `scene_overrides` only when its posture, behavior, or environment fit truly differs from the family.

**Validation:** the first complete 14-family state passed Studio checks on the branch.

**Next hardening priority:** Golden Five reference pages, then controlled Tome I regeneration.


## 2026-09-22 Environment Variation Depth Update

Environment variety is now a first-class universal engine layer rather than an informal prompt preference.

- added `data/environment_variation_families.json` covering all 8 environment families
- each family now owns reusable geometry, landmark, prop, interaction, and anti-repetition pools
- the resolved named environment profile and page-specific variant remain authoritative
- generation prompts receive the compatible family palette but are told to vary large geometry before adding detail
- colorability remains the governing constraint: variation may not be created through micro-props, texture, or clutter
- series readiness now fails if an environment family has no valid variation definition
- CI validates the registry and regression tests verify complete family coverage

**Next hardening priority:** build the Golden Five reference pages and use them to calibrate the generation/review loop before mass rebuilding Tome I.


## 2026-09-22 Golden Five Calibration Gate

The Golden Five are now an isolated calibration lane rather than normal Tome I production pages.

Calibration set:

- I-01 Kobold Warrior — small humanoid identity, trap storytelling, dungeon perspective
- I-24 Gelatinous Cube — ooze volume, corridor scale, sparse internal objects
- I-27 Mimic Chest — object-monster identity, vault clarity, subordinate reaching-hand story cue
- I-38 Ankheg — burrower anatomy, earthen setting, dynamic but visibly supported emergence
- I-40 Rust Monster — unusual insectoid identity, armory material interaction without weapon clutter

Rules:

- calibration state is stored separately from `data/production-state.json`
- Golden Five generation cannot advance or lock normal Tome I pages
- all six review dimensions must pass before a calibration page locks
- normal Tome I generation beyond its first page is blocked until all five calibration pages are approved
- series reporting now distinguishes structural `production_ready` from human-validated `mass_generation_ready`
- the stale I-01 `modify_requested` state with no source candidate was reset to a clean `queued` state
- I-38 explicitly requires a half-emerged supported pose; the story may feel dynamic but may not become a midair freeze-frame

**Next action:** generate and ruthlessly review the five calibration pages. Only after all five lock does controlled Tome I mass rebuilding begin.


## 2026-09-22 Golden Five Studio Workflow

The local Studio now exposes the isolated Golden Five calibration lane directly.

- select I-01, I-24, I-27, I-38, or I-40 without changing the normal Tome I queue
- generate a calibration candidate with the same universal monster/environment/story/coloring engines
- open the full-size candidate from the Studio
- approve a page only when all six review dimensions pass
- reject by selecting the failed dimensions; the Studio records the failure and immediately starts a regenerated calibration attempt
- calibration progress is visible as 0/5 through 5/5
- mass-generation readiness unlocks only at 5/5
- Golden Five UI/controller/service code is kept modular under the project's 150-line ceiling for new modules

The production page queue remains independent and cannot be advanced by calibration actions.


## 2026-09-22 Environment Engine V3 — Hundreds-of-Monsters Scale

The environment system has been promoted from broad family variation pools to a component-library architecture intended to support hundreds of monsters without bloating monster JSON.

New hierarchy:

**environment family -> named profile -> reusable component library -> reusable overlays -> tiny page recipe**

Current reusable environment inventory:

- 8 environment-family component catalogs
- 12 required component groups per family
- 816 reusable environment components total
- 144 underground / dungeon / cave components
- 96 components in each of the other seven families
- 11 reusable cross-family overlays

Required component groups now cover spatial archetypes, surfaces, ground, overheads, lighting, structures, landmarks, secondary features, hazards, depth, atmosphere, and interaction patterns.

Generation receives only a selected compatible palette, not the full library. This keeps prompts focused while letting the library become very large.

Cross-family overlays currently include lair, trap zone, ruin, sacred, military, burial, treasure, fungal, aquatic, weathered, and settlement. Scene archetypes may activate overlays automatically.

### Ownership rule

Monster files may describe habitat compatibility, but reusable scenery belongs exclusively to the environment engine.

If another creature could use the same wall, floor, torch, trap, furnishing, ruin, vegetation, reef feature, burial dressing, lair feature, or depth cue, it must not be copied into monster JSON.

### Authority rule

Once a page selects an environment profile, that profile overrides all general monster habitat preferences.

The Kobold Shrine-Keeper calibration exposed this conflict: attractive dungeon-corridor art was still a failure because I-02 requires a low limestone cave shrine with its specific offering story. The prompt no longer injects family environment-fit text as scene-generation authority.

Canonical monster and environment catalog names now override stale display strings left in legacy page recipes.

### Environment quality rule

Walls, floors, ceilings, torches, traps, gates, roots, coral, tombs, furniture, ruins, pools, and other environment elements are premium coloring objects, not filler.

Environment variety must come from stronger structure, material design, fixtures, depth, and composition—not tiny texture.

See `docs/ENVIRONMENT_ENGINE_V3.md` for the persistent architecture specification.


## 2026-09-22 Monster V3 Recipe Enforcement

Schema-v3 monster recipes are now treated as strict recipes rather than permissive resolved documents.

- the universal monster contract remains the schema authority
- the normal catalog audit now executes the recipe-policy audit
- family-owned fields such as `visual_identity`, `scene_identity`, `accuracy_checks`, and `known_failure_modes` are hard failures when copied into schema-v3+ monster files
- unapproved top-level fields and empty override blocks are hard failures
- the audit reports minimal-v3 count, legacy family-backed migration candidates, and standalone legacy monsters
- regression coverage injects forbidden family anatomy into a v3 recipe and requires rejection
- new/modified audit modules remain within the 150-line modularity ceiling

**Validation status:** code-level enforcement is implemented on the branch, but GitHub Actions jobs are currently failing before runner assignment with no executed steps. Do not treat the branch as CI-certified until a complete workflow run executes.
