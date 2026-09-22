# Black-Ink Production Platform

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
- `must_include[]`
- `must_avoid[]`

The production audit rejects missing fields, duplicate IDs/orders, missing canonical specs, bad archetypes, and malformed identity specs.

## Global Quality Layers

### Canonical identity

`data/monsters/*.json` defines anatomy, silhouette, signature gear, keep/avoid rules, and accuracy checks.

### Scene archetype

`config/page_archetypes.json` defines reusable composition logic such as trap scenes, swarms, reveals, bosses, and object monsters.

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

## Human Quality Gate

Technical QA does not claim to understand visual semantics.

The reviewer still decides whether:

- monster identity is correct
- anatomy is believable
- required props are actually present
- the story beat is readable
- the habitat reads correctly
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

1. Create its manifest and canonical monster specs.
2. Give every page a valid archetype and concrete visual requirements.
3. Point `config/studio.json` at the new manifest/state/reviews files.
4. Run `python scripts/init_active_book.py`.
5. Run `python scripts/audit_active_book.py`.
6. Start the Studio only after the audit returns `"pass": true`.

## Production Invariant

The intended loop for every book is:

`spec → generate → technical QA → human audit → exact-image modify OR regenerate → approve & lock → next page`

No page advances without human approval.
