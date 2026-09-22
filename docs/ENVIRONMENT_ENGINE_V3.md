# Black-Ink Bestiary — Universal Environment Engine V3

## Purpose

The environment engine must support hundreds of monsters without moving reusable scenery into creature JSON.

The scalable hierarchy is:

**environment family -> named profile -> reusable component library -> reusable overlays -> tiny page recipe**

Monster data may describe habitat compatibility. It does not own reusable walls, floors, ceilings, lighting, hazards, furnishings, ruins, vegetation, reef dressing, burial dressing, lair dressing, or depth cues.

## Authority order

1. selected page environment profile
2. explicit page landmark / framing / interaction
3. compatible environment overlays
4. selected family component palette
5. monster habitat compatibility is planning-only

Once a page selects an environment profile, monster-family environment preferences may not replace or broaden that environment.

## Environment families

The engine currently supports eight reusable families:

- underground
- forest
- wilderness
- ocean
- undead-sites
- giant-territories
- mythic-sites
- dragon-lairs

Each family has its own component catalog under `data/environment_components/`.

## Component groups

Every family must provide at least these twelve reusable groups:

- spatial_archetypes
- primary_surfaces
- ground_planes
- overhead_features
- lighting_features
- structural_features
- landmarks
- secondary_features
- hazards
- depth_features
- atmosphere_features
- interaction_patterns

The engine knows a large library but selects only a small compatible palette for one page.

## Current library size

- 8 family component catalogs
- 816 reusable environment components
- 144 underground / dungeon / cave components
- 96 components in each of the other seven families
- 11 reusable cross-family overlays

Library depth exists to create variety across hundreds of pages. It must never create clutter inside one page.

## Reusable overlays

Overlays add cross-family context without creating monster-specific scenery:

- lair
- trap_zone
- ruin
- sacred
- military
- burial
- treasure
- fungal
- aquatic
- weathered
- settlement

For example, a sacred overlay can improve a dungeon shrine, forest shrine, ruined temple, or dragon relic chamber without duplicating shrine rules in monster files.

## Selection behavior

Environment assembly is deterministic for a page/profile key.

That provides:

- reproducible debugging
- controlled regeneration
- natural rotation across pages
- stable anti-repetition behavior

Context rules filter components to the selected place before choosing the palette.

Examples:

- limestone cave -> natural + cave + limestone
- dungeon corridor -> built + dungeon + corridor
- shipwreck -> wreck + ruin
- graveyard -> graveyard + exterior
- volcanic dragon lair -> volcanic + caldera + lair

## Prompt behavior

Generation receives the selected palette, not the full library.

Typical page palette includes:

- spatial archetype
- primary surface
- ground plane
- overhead feature
- lighting feature
- structural feature
- depth feature
- two compatible accents
- hazard only when appropriate
- one story interaction pattern

Explicit page landmark, framing, and interaction remain authoritative.

## Coloring rule

Every environmental component must earn its place as something enjoyable to color.

Walls, torches, traps, roots, coral, tombs, furniture, ruins, gates, pools, and other features are not filler.

They should provide:

- large or medium coloring regions
- clear silhouettes
- useful scene identity
- believable interaction
- premium visual design

Variation must come from stronger structure and composition, not more tiny detail.

## Scaling rule for new monsters

Adding a new monster should normally require only:

- monster identity / family
- true variant traits
- behavior tendencies
- locomotion
- habitat compatibility

If another monster could use the same scenery element, that element belongs in the environment engine.

## Calibration lesson — Kobold Shrine-Keeper

A visually attractive page can still fail if the chosen environment is wrong.

I-02 is a low limestone cave shrine. A built dungeon corridor is not an acceptable substitute even if the line art is attractive.

Therefore:

- selected profile overrides general kobold habitat preferences
- sacred story objects must read unmistakably
- repeated identical wall bays / sconces / arches should be avoided
- environment identity is judged independently from monster quality

## Production gate

CI and series readiness must fail if:

- any environment family has no component catalog
- any required component group is undersized
- overlays are missing
- component JSON is invalid
- the selected environment profile cannot resolve
- the environment engine becomes dependent on monster-specific scenery JSON


## Spatial envelope grammar

Before the engine chooses walls, torches, traps, vegetation, coral, furniture, ruins, or other scenery, the selected environment profile resolves to one strict spatial envelope.

The order is:

**profile -> spatial envelope -> component palette -> overlays -> page-specific landmark / framing / interaction**

Each envelope defines:

- plan shape
- width/depth or open-space proportions
- ceiling / overhead condition
- allowed openings
- focal-zone organization
- preferred camera / perspective
- forms that must be visible
- spatial drift that automatically fails review

Examples:

- a trapped corridor must remain a narrow linear passage with two readable side boundaries, a floor travel lane, and recession toward a turn/door/gate
- a low crawlway must visibly retain its low overhead boundary
- a compact room must show enough bounding surfaces to read as a room rather than a corridor
- a natural cavern must retain irregular rock geometry and cannot become masonry
- a forest clearing must preserve an open center instead of filling the page with foliage
- a reef shelf must show both solid shelf terrain and open-water negative space

The spatial envelope is environment-owned. Monster habitat preferences and reusable scenery components may decorate it but may not change the fundamental geometry.
