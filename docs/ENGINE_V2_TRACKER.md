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
2. family DNA audit across every repeated monster family
3. environment variation depth across every book family
4. Modify/Regenerate routing based on passed vs failed quality dimensions — **implemented; review state records failed and preserved dimensions**
5. Golden Five reference pages before mass regeneration

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
