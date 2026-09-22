# Canonical Monster Spec Standard

Black-Ink Bestiary separates **monster identity** from **coloring-book style**.

## Core Rule

> Reference art and canonical monster specs control anatomy, silhouette, creature identity, and signature features.  
> The Black-Ink Style Bible controls rendering, line weight, detail density, negative space, and coloring friendliness.

A reference image is never a composition to copy.

## Required Monster Spec Fields

Each canonical monster spec lives in `data/monsters/<monster_id>.json`.

Required top-level fields:

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

1. canonical creature identity
2. page-specific habitat and moment
3. page must-include / must-avoid rules
4. Black-Ink Style Bible
5. latest human review notes

## Review Rule

The Studio shows the canonical identity brief beside the generated coloring page.

The human reviewer checks two separate questions:

1. **Identity:** Does this unmistakably look like the intended monster?
2. **Coloring page:** Is the page clean, open, printable, and enjoyable to color?

A page can be technically attractive and still fail if monster identity is wrong.

## Initial Canonical Batch

The first five Tome I pages use:

- I-01 -> `kobold-warrior`
- I-02 -> `kobold-shrine-keeper`
- I-03 -> `goblin-minion`
- I-04 -> `goblin-warrior`
- I-05 -> `goblin-boss`

Do not mass-produce later pages until these prove the identity workflow is reliable.
