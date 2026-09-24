# Black-Ink Production Platform

## Universal Page Contract

`config/universal_page_contract.json` is the single page-construction contract for every tome and any future Black-Ink book.

Resolution order:

1. universal page defaults
2. monster-family identity
3. monster-variant identity
4. environment family/profile
5. scene archetype
6. page-unique recipe fields
7. latest human corrections

A production page does not need to repeat monster name, habitat prose, composition boilerplate, global coloring rules, or global avoid rules. The resolver derives them. The unique recipe keeps only the facts that genuinely make the page different: monster, environment subtype, story moment, landmark, framing, interaction, and physicality.

Book length is a registry setting, not an engine constant. The current eight books use 50 pages, while future books may use any positive page count.


The Studio is a reusable coloring-book production engine. Tome I is the active book, not a special-case implementation.

## Active Book Data Schema

`config/studio.json` points to three book-specific files:

- `manifest` — ordered page specifications
- `state` — runtime production state
- `reviews` — structured reviewer decisions

Changing the active book requires a Studio restart. Python code should not be edited to switch books.

## Page Schema

Every page must define:

- `page_id`
- `order`
- `monster_name`
- `monster_spec_id`
- `habitat`
- `moment`
- `archetype`
- `environment_profile_id`
- `environment_variant.landmark`
- `environment_variant.framing`
- `environment_variant.interaction`
- `must_include[]`
- `must_avoid[]`

The production audit rejects missing fields, duplicate IDs/orders, missing canonical specs, bad archetypes, and malformed identity specs.

## Global Quality Layers

### Canonical identity

`data/monster_families/*.json` defines reusable creature-family anatomy and failure modes. `data/monsters/*.json` adds variant-specific identity, gear, behavior, habitats, and accuracy checks.

### Scene archetype

`config/page_archetypes.json` defines reusable composition logic such as trap scenes, swarms, reveals, bosses, and object monsters.

### Environment standard

`config/environment_standard.json` is global across all books. Colorability is the governing constraint; beneath it, every page must independently satisfy three visual requirements:

- unmistakable monster identity — visually dominant, large, and centered or near-centered
- unmistakable environment identity — supportive framing around the monster
- unmistakable story moment

The environment must use setting-specific, colorable cues and must participate in the scene rather than function as generic background filler. `data/environment_families/*.json` provides concrete habitat profiles such as limestone drip caves, lava tubes, kelp forests, shipwreck fields, deep-sea coral gardens, and hydrothermal vent fields. Each page adds a unique landmark, framing, and interaction fingerprint. Duplicate background fingerprints fail manifest validation.

Simplification removes clutter, not habitat identity.

### Coloring-page scale standard

`config/coloring_page_standard.json` keeps pages easy to color: a large centered monster as the dominant focal form, 2–4 major supporting environmental forms, sparse secondary objects, and broad open white regions. The system explicitly rejects micro-texture, tiny enclosed coloring islands, and monster scaling that erases the environment.

### Defect remediation

`config/quality_rules.json` maps reviewer defect tags to:

- preferred action (`modify` or `regenerate`)
- exact remediation directive injected into the next prompt

Local defects preserve the current image through FLUX image editing. Fundamental composition defects route to fresh regeneration.

### Technical QA

Generated PNGs must satisfy:

- PNG integrity
- portrait orientation
- expected aspect ratio
- minimum resolution
- reasonable file size
- nonblank line-art content
- no overwhelmingly dark/solid output

A technical QA failure is retried automatically with a fresh seed before stopping the page.

## Iterative AI Art-Director Gate

Every independent composition candidate follows the same authority-first loop:

`reread written authority → generate → inspect the rendered image → compare image to authority → refine the existing image → reread authority → reinspect`

The written monster family, monster JSON, environment contract, page recipe, anatomy rules, and coloring-page standard are reloaded before every generation or refinement pass. The previous image is never treated as authority.

A refinement preserves successful composition and artwork while correcting observed defects. It must use image editing rather than silently replacing the candidate with an unrelated text-to-image composition. Each candidate retains its pass history and best-so-far image so a later regression cannot destroy a better earlier result.

The four candidates remain compositionally independent. Refinement may repair anatomy, identity, environment, story readability, colorability, clutter, or malformed structures, but it may not collapse all candidates into the same composition.

The automated loop is bounded: one initial render plus up to four refinement passes per candidate. It may stop early only when the visual quality gate passes. If the configured runtime cannot perform semantic image inspection, it must fail closed and require human review; it must never label technical pixel checks as semantic AI review.

## Human Quality Gate

Technical QA does not claim to understand visual semantics.

The reviewer still decides whether:

- monster identity is correct
- anatomy is believable
- required props are actually present
- the story beat is readable
- the habitat is unmistakable and setting-specific
- monster and environment interact believably
- the environment is worth coloring rather than generic filler
- the page is enjoyable to color

Only `Approve & Lock` admits artwork into the ordered book folder.

## Review Memory

Every decision records:

- book and page
- monster
- scene archetype
- requested and effective action
- candidate metadata
- free-form notes
- defect tags
- expanded remediation directives

This creates structured data for future quality analysis without silently overriding human approval.

## Starting Another Book

1. Fill the registered 50-slot book plan with canonical monster specs, concrete environment profiles, and unique background variants.
2. Give every page a valid archetype and concrete monster, environment, and story requirements.
3. Point `config/studio.json` at the new manifest/state/reviews files.
4. Run `python scripts/init_active_book.py`.
5. Run `python scripts/audit_active_book.py`.
6. Start the Studio only after the audit returns `"pass": true`.

## Production Invariant

The intended loop for every book is:

`spec → generate → technical QA → human audit → exact-image modify OR regenerate → approve & lock → next page`

No page advances without human approval.
