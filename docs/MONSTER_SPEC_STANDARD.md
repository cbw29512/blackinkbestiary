# Canonical Monster Spec Standard

Black-Ink Bestiary separates **monster identity** from **coloring-book style**.

## Core Rule

> Reference art and canonical monster specs control anatomy, silhouette, creature identity, and signature features.  
> The Black-Ink Style Bible controls rendering, line weight, detail density, negative space, and coloring friendliness.

A reference image is never a composition to copy.

## Required Monster Spec Fields

Each canonical monster variant lives in `data/monsters/<monster_id>.json`. Reusable family identity lives in `data/monster_families/<family>.json`. The resolver merges family rules first, then variant-specific overrides.

Versioned variants may also declare `schema_version`, `identity_version`, and `family_profile`.

Required top-level identity fields:

- `monster_id`
- `monster_name`
- `family`
- `size`
- `creature_type`
- `visual_identity`
- `default_habitats`
- `accuracy_checks`
- `reference`

Required `visual_identity` fields:

- `core_identity`
- `silhouette`
- `head_features`
- `body_shape`
- `surface`
- `signature_gear[]`
- `attitude[]`
- `must_keep[]`
- `must_avoid[]`

Reference contract:

```json
{
  "reference": {
    "image": null,
    "purpose": "identity_and_anatomy_only",
    "notes": "Reference art controls anatomy and silhouette, never Black-Ink rendering style."
  }
}
```

If a reference image is used, store it under the Studio web root with a relative path such as:

```
references/kobold-warrior.png
```

The image must be original, user-owned, public-domain, or otherwise licensed for the intended use.

## Page Integration

A Tome page opts into a canonical monster spec with:

```json
{
  "monster_spec_id": "kobold-warrior"
}
```

The prompt builder then combines, in order:

1. reusable family identity
2. variant-specific creature identity
3. page-specific environment profile and unique background variant
4. page-specific habitat and moment
5. page must-include / must-avoid rules
6. Black-Ink Style Bible and coloring-page scale standard
7. latest human review notes

## Review Rule

The Studio shows the canonical identity brief beside the generated coloring page.

The human reviewer checks two separate questions:

1. **Identity:** Does this unmistakably look like the intended monster?
2. **Coloring page:** Is the page clean, open, printable, and enjoyable to color?

A page can be technically attractive and still fail if monster identity is wrong.

## Tome I Coverage

All 50 Tome I pages must declare a `monster_spec_id` whose JSON file satisfies this contract.

CI enforces:
- exactly 50 ordered Tome I pages
- a resolvable canonical spec for every page
- matching `monster_id` and `monster_name`
- required visual-identity fields
- non-empty identity keep/avoid rules and accuracy checks
- concrete page-specific `must_include` requirements

A missing or malformed canonical spec is a production blocker and must fail tests before merge.
