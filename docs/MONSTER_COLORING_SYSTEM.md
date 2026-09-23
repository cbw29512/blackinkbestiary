# Black-Ink Bestiary — Production System

## Objective

Build a small, reliable publishing studio that does **one task extremely well**:

> Create fantasy monster coloring pages in their natural habitat, one page at a time, in strict book order, with human approval before advancing.

This is not a general art generator, marketplace, collaboration suite, or publishing platform in v1.

---

## Definition of Done for v1

The system is complete when it can:

1. Load an ordered Tome manifest.
2. Identify exactly one current page.
3. Read that page's structured JSON specification.
4. Generate multiple local image candidates.
5. Reject obvious technical failures.
6. Run a supervisor pass against the page spec and style rules.
7. Show one best candidate in a review screen.
8. Accept **Approve & Lock**, **Modify**, or **Regenerate**.
9. Keep the same page active until it is approved.
10. Store the approved master without overwriting it.
11. Advance to the next page only after approval.
12. Keep approved pages in exact book order for later export.

---

## Non-Negotiables

- One active page at a time.
- Strict order: I-01 → I-02 → ... → I-50.
- Human approval required.
- Approved art is locked.
- Never overwrite approved masters.
- Local-first generation.
- Pure black line art on white.
- Large open coloring areas.
- Monster identity must be immediately readable.
- Natural habitat or believable lair is part of every page.
- Do not add features that do not directly improve page production.

---

## System Roles

### 1. Canonical Monster Spec

A reusable JSON identity record for the creature itself.

It defines:
- core creature identity
- silhouette
- head and body anatomy
- surface treatment cues
- signature gear
- must-keep species traits
- prohibited look-alikes
- monster accuracy checks
- optional identity/anatomy reference image

Reference art controls **identity and anatomy only**. It never controls Black-Ink rendering style or composition.

### 2. Page Spec

A small structured JSON recipe for what is unique about one page.

It defines:
- page ID and order
- canonical monster spec ID
- canonical environment profile ID
- one scene moment
- scene archetype
- unique landmark
- unique framing
- monster/environment interaction
- physical state, support, and motion
- optional page-specific negative exceptions

It does **not** own reusable monster anatomy, habitat prose, global composition, global coloring rules, or current review instructions. Those resolve from the universal engines and production-state review memory. Legacy copies may remain during migration but are non-authoritative.

### 3. Production Manager

The state machine and traffic controller.

It decides:
- which page is current
- current attempt number
- whether generation is allowed
- whether the system may advance
- which files are candidate vs approved

### 4. Local Art Generator

The image model running on the local GPU.

Its job:
- read the prepared generation brief
- create several candidates
- refine an existing candidate for MODIFY
- create a fresh candidate for REGENERATE

The generator never approves its own work.

### 5. Automatic QA

Fast mechanical checks before human/LLM review.

Initial checks:
- file loads
- portrait orientation
- expected dimensions/aspect ratio
- mostly black/white
- no obvious grayscale wash
- not blank
- dark coverage not excessive
- open white area not too low
- line density inside an acceptable range

Automatic QA is a garbage filter, not an art critic.

### 6. Supervisor

The supervisory layer compares a candidate against:
- page JSON
- Style Bible
- approved style references
- modification instructions

Outcomes:
- `ready_for_human`
- `needs_refinement`
- `reject`

The supervisor may issue one targeted correction pass before showing the result to the human reviewer.

### 7. Human Reviewer

Final authority.

Available decisions:
- **Approve & Lock**
- **Modify**
- **Regenerate**

No page advances without human approval.

---

## Core Workflow

```
CURRENT PAGE JSON
       ↓
PROMPT / EDIT BRIEF
       ↓
LOCAL IMAGE MODEL
       ↓
3–4 CANDIDATES
       ↓
AUTOMATIC QA
       ↓
SUPERVISOR
       ↓
(optional targeted pass 2)
       ↓
BEST CANDIDATE
       ↓
REVIEW STUDIO
       ↓
APPROVE / MODIFY / REGENERATE
```

### APPROVE & LOCK

- Save candidate as approved master.
- Mark page locked.
- Preserve all attempt history.
- Advance exactly one page.
- If the next page has a canonical monster spec, automatically start its local generation.
- If the next page has no canonical monster spec yet, stop at the identity gate instead of guessing.

### MODIFY

- Stay on the same page.
- Preserve what the reviewer says to keep.
- Apply only requested changes.
- Use the current best image as a reference when appropriate.
- Automatically start a new local attempt after the decision is saved.

### REGENERATE

- Stay on the same page.
- Treat the current result as fundamentally wrong.
- Automatically create a fresh local attempt from the page spec and approved style references.

---

## Page Lifecycle

Exactly one state per page:

- `planned`
- `queued`
- `generating`
- `qa_review`
- `supervisor_review`
- `awaiting_human`
- `modify_requested`
- `regenerate_requested`
- `approved`
- `locked`

Only one page may occupy an active middle state at a time.

---

## Data Model

### Tome

Fields:
- `tome_id`
- `title`
- `theme`
- `total_pages`
- `current_page_id`
- ordered `pages[]`

### Canonical Monster Recipe

Raw monster recipe fields:
- `schema_version`
- `monster_id`
- `monster_name`
- `family_profile`
- optional true variant fields such as `variant_traits`, locomotion, or narrow overrides

Family anatomy, silhouette, scene behavior, accuracy checks, and known failure modes resolve from `data/monster_families/`.

### Page Spec

Raw page recipe fields:
- `page_id`
- `order`
- `monster_spec_id`
- `moment`
- `archetype`
- `environment_profile_id`
- `environment_variant.landmark`
- `environment_variant.framing`
- `environment_variant.interaction`
- `physicality.mode`
- `physicality.support`
- `physicality.motion`

Tome I contains only these unique fields. Monster name, habitat, identity checks, coloring rules, global avoid rules, and current review corrections are derived at runtime from their universal owners.

### Candidate

Fields:
- `candidate_id`
- `page_id`
- `attempt_number`
- `image_path`
- `created_at`
- `qa_result`
- `supervisor_result`
- `generation_metadata`

### Review

Fields:
- `page_id`
- `candidate_id`
- `decision`
- `keep[]`
- `change[]`
- `avoid[]`
- `timestamp`

### Approved Master

Fields:
- `page_id`
- `approved_candidate_id`
- `approved_image_path`
- `approved_at`
- `locked: true`

---

## Review Studio

The main screen should remain deliberately simple.

### Header
- Tome title
- approved count / total
- current page number
- current monster
- current attempt

### Main Panel
- large candidate preview
- page brief summary
- supervisor status
- optional expandable QA details

### Controls
- **Approve & Lock**
- **Modify**
- **Regenerate**

### Modify Input
A short text box plus optional quick tags:
- more white space
- less texture
- simpler background
- clearer monster anatomy
- stronger outer contour
- lighter interior lines

### Progress
Later pages remain visually locked until the current page is approved.

---

## Attempt History

Never destructively overwrite attempts.

Conceptual layout:

```
pages/I-01/
  spec.json
  attempts/
    001.png
    001.json
    002.png
    002.json
  reviews.json
  approved.png
  approved.json
```

Approved art must remain untouched unless explicitly unlocked.

---

## Golden Style References

Before trusting semi-automatic production, establish a small approved reference set that represents the intended visual language.

Target reference categories:
1. humanoid
2. beast
3. insect/arthropod
4. large creature
5. unusual anatomy

These references guide style only. They should not force unrelated monsters into the same composition.

---

## Supervisor Behavior

The supervisor should produce structured decisions.

Example:

```
decision: needs_refinement

preserve:
- monster pose
- spear
- pit geometry
- corridor perspective

change:
- remove 30% of wall texture
- reduce body hatching
- increase open armor areas

avoid:
- changing the face
- changing the trap
- adding background objects

mode: targeted_edit
```

The second pass must be a correction, not a random restart.

---

## Failure Policy

If a candidate fails badly:
- reject it
- do not publish it
- do not advance
- record the failure reason
- try another candidate or refinement

If the same failure repeats, add the issue to the Style Bible / global negative rules.

---

## Book Assembly

Book assembly is downstream of approved art.

Only `locked` pages are eligible.

Tome I order is fixed:

```
I-01
I-02
...
I-50
```

When all pages are locked, they can be assembled without re-sorting or searching for files.

Potential later outputs:
- print PDF
- digital PDF
- KDP interior
- website preview

These are intentionally out of the v1 critical path.

---

## First Milestone

Do not trust the pipeline on I-02 until I-01 completes the entire loop successfully:

```
I-01 spec
→ generation
→ automatic QA
→ supervisor
→ human review
→ modify/regenerate if needed
→ approve & lock
```

Once I-01 works cleanly, repeat on I-02.

---

## Drift Guard

When considering any feature, ask:

> Does this directly help us make a better fantasy monster coloring page, review it, approve it, or preserve its place in the book?

If not, it does not belong in v1.
