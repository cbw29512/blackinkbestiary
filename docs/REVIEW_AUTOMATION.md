# Review Automation Contract

## Branch ownership

- `feat/environment-spatial-hardening` is the engine-authority branch.
  - Generator code, contracts, monster/family data, environment data, tests, and AI review decisions live here.
- `review-previews-live` is the generated-review snapshot branch.
  - Local ComfyUI publishes `review-previews/manifest.json` and preview JPGs here.
  - This branch is disposable snapshot state and may be force-updated by the local publisher.

Never use the engine branch as the generated-image handoff.

## Operator handoff rule

**GitHub is the handoff. Terminal output is not.** The operator must not be required to copy/paste generation logs, reviewer JSON, image paths, or failure output back into ChatGPT. Local launchers must publish reviewable images, partial results, runtime failures, and diagnostics to `review-previews-live`; ChatGPT reads that branch directly and writes exact-image decisions/fixes back to the engine branch.

If a local run fails before every page completes, publish whatever completed plus diagnostic state. A failure trapped only in the Windows terminal is an automation defect.


## Automated loop

1. The local launcher reads exact-image decisions from the engine branch.
2. `apply_review_decisions.py` marks matching local candidates approved/rejected by content hash.
3. `generate_test_gallery.py --canary-failed --copies 1` reconciles generation/review fingerprints, rechecks existing PNGs when only review authority changed, and renders only missing, failed, assistant-rejected, or generation-stale canary pages.
4. `publish_review_previews.py` builds lightweight JPG previews and a content-hashed manifest.
5. `review_publish_git.py` force-publishes that snapshot to `review-previews-live`.
6. ChatGPT reads the live branch, inspects the actual images, and writes exact-image decisions back to the engine branch.
7. Repeat until the canary genuinely passes direct image inspection.
8. After 9/9 exact-image canary approval, the full-gallery launcher generates/resumes the 50-page candidate set and always publishes completed/diagnostic state back to GitHub.

## Review and refinement authority

The local semantic reviewer is intentionally fail-closed and staged:

1. **Identity / anatomy** — species identity, canonical scale, body plan, limb topology, known drift.
2. **Environment geometry** — named habitat, material language, spatial envelope, architecture/terrain, landmark.
3. **Action / physicality** — required verb, prop relationship, support/contact, motion/weight, story cause-and-effect.
4. **Print / colorability quality** — line density, negative space, borders, black fill, wallpaper repetition, print usability.

A later-stage failure outranks an earlier-stage failure even when its numeric reviewer score is lower. Reaching the environment gate proves identity passed; reaching action proves identity + environment passed; reaching quality proves identity + environment + action passed.

**Identity failures regenerate from text authority immediately.** Do not image-edit a fundamentally wrong body plan and expect it to become canonical. Environment and action failures get one cumulative image-edit repair so successful identity can survive; if the same structural gate fails again, escalate to fresh text-to-image regeneration with an alternate composition. Quality failures remain preservation-first image edits unless an exact-image rejection explicitly routes a fresh quality rebuild.

Exact-image approval is valid only for the current candidate content hash. If candidate bytes change, old approval is stale and the image returns to review.

Review publication is state-authoritative. Orphan historical PNGs on the workstation are never eligible for the live review snapshot unless current gallery state marks that page/candidate reviewable.

The full 50-page / 4-candidate gallery is blocked until all nine canary pages have current exact-image approvals.

## Exact-image decision meanings

`review-previews/decisions.json` is append-only review history keyed by the exact image content hash.

- **reject** — the exact image is unacceptable; remove it from selection and regenerate that candidate when appropriate.
- **approve** — the exact image is acceptable. On the one-candidate canary, this is enough to satisfy the exact-image gate. In a multi-candidate production set, approval does **not** silently choose the final page.
- **select** — the exact image is acceptable **and** is the explicit final candidate for that page.

For four-candidate production pages, exactly one acceptable candidate should receive `select`. Other acceptable alternatives may remain `approve`, and rejected candidates remain `reject`. Decision-file ordering must never determine the final page choice.

## Safety rules

- `review-previews/decisions.json` is engine-owned. The local preview publisher must never overwrite it from stale workstation state.
- Generated `web/test-gallery/*.png` and `data/test-gallery-state.json` stay local/untracked.
- Engine code can advance while ComfyUI is generating; review publication must remain independent of engine branch fast-forward state.
- After publishing, tracked workstation code may resync to the latest engine branch only when no unrelated tracked local edits exist.
- A local vision-model PASS is provisional. Direct review of the published exact image is the final canary gate.
- Full-batch regeneration remains blocked until the canary images pass direct inspection.

## Canary pages

`I-01, I-04, I-08, I-10, I-14, I-16, I-19, I-20, I-22`

These cover small-creature scale, goblinoid anatomy, rangy anatomy, constrained architecture, non-humanoid topology, bat limb topology, swarm composition, repeating-segment anatomy, and web/environment readability.
