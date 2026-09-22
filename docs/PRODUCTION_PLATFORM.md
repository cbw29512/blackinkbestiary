# Black-Ink Production Platform

Black-Ink is a reusable coloring-book production engine. An active book supplies page data; the same quality engine, generation loop, review workflow, and archive rules apply to every book.

## Core Quality Contract

Every finished page must pass three equal human quality gates:

1. **Monster** — unmistakable identity and believable anatomy.
2. **Environment** — unmistakable, specific setting that is valuable to color.
3. **Story** — an immediately readable moment created by the monster interacting with the environment.

The environment is not decorative background filler.

## Active Book Data Schema

`config/studio.json` selects the active book's:

- manifest
- runtime state
- structured review log

Changing books requires a Studio restart, not Python changes.

## Page Schema

Every page requires:

- `page_id`
- `order`
- `monster_name`
- `monster_spec_id`
- `habitat`
- `moment`
- `archetype`
- `environment`
- `must_include[]`
- `must_avoid[]`

### Environment Schema

Every `environment` object requires:

- `identity` — the specific place the reader should recognize
- `anchors[]` — at least two visible architectural, terrain, or prop cues
- `interaction` — how the monster/story physically uses the setting
- `coloring_value[]` — large setting shapes worth coloring
- `must_avoid[]` — failures that would make the location generic or incorrect

CI rejects pages without a complete environment spec.

## Shared Quality Layers

### Canonical monster identity

`data/monsters/*.json` defines silhouette, anatomy, signature gear, keep/avoid rules, and accuracy checks.

### Environment identity

The page environment spec is injected into both fresh-generation and exact-image edit prompts. Successful habitat anchors are preservation targets during edits.

### Scene archetype

`config/page_archetypes.json` defines reusable composition logic for traps, swarms, stealth, reveals, bosses, lairs, object monsters, large-scale scenes, action scenes, and horror scenes.

Archetypes explicitly describe how the environment participates in the scene.

### Defect remediation

`config/quality_rules.json` maps reviewer tags to a preferred action and exact corrective directive.

Examples:

- local anatomy/detail/environment defects → exact-image **Modify**
- wrong overall composition or wrong environment → fresh **Regenerate**

The Studio records both the requested action and the effective routed action.

### Technical QA

Generated PNGs must satisfy deterministic checks for:

- valid PNG structure
- portrait orientation and expected aspect ratio
- minimum resolution
- reasonable file size
- nonblank line-art content
- no overwhelmingly dark/solid output

Technical failures are retried automatically with a new seed before the page stops.

## Human Quality Gate

Technical QA does not claim to understand semantic image correctness.

The reviewer still decides whether:

- monster identity is correct
- anatomy is believable
- environment identity is correct
- required environmental anchors are visible
- monster/environment interaction makes sense
- required story props are present
- story moment is clear
- the page is enjoyable to color

Only **Approve & Lock** admits artwork into the ordered book folder.

## Review Memory

Each review records:

- book and page
- monster
- environment identity and anchors
- scene archetype
- requested/effective action
- candidate metadata
- free-form notes
- defect tags
- expanded remediation directives

This supports future analysis without silently replacing human approval.

## Starting Another Book

1. Create the manifest and canonical monster specs.
2. Give every page a valid archetype, concrete visual requirements, and structured environment spec.
3. Point `config/studio.json` at the new manifest/state/reviews files.
4. Run `python scripts/init_active_book.py`.
5. Run `python scripts/audit_active_book.py`.
6. Start the Studio only after the audit returns `"pass": true`.

## Production Invariant

`spec → generate → technical QA → human three-gate audit → exact-image modify OR regenerate → approve & lock → next page`

No page advances without human approval.
