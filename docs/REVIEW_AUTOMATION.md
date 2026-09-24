# Review Automation Contract

## Branch ownership

- `feat/environment-spatial-hardening` is the engine-authority branch.
  - Generator code, contracts, monster/family data, environment data, tests, and AI review decisions live here.
- `review-previews-live` is the generated-review snapshot branch.
  - Local ComfyUI publishes `review-previews/manifest.json` and preview JPGs here.
  - This branch is disposable snapshot state and may be force-updated by the local publisher.

Never use the engine branch as the generated-image handoff.

## Automated loop

1. The local launcher reads exact-image decisions from the engine branch.
2. `apply_review_decisions.py` marks matching local candidates approved/rejected by content hash.
3. `generate_test_gallery.py --canary-failed --copies 1` retries only missing, failed, or assistant-rejected canary pages.
4. `publish_review_previews.py` builds lightweight JPG previews and a content-hashed manifest.
5. `review_publish_git.py` force-publishes that snapshot to `review-previews-live`.
6. ChatGPT reads the live branch, inspects the actual images, and writes exact-image decisions back to the engine branch.
7. Repeat until the canary genuinely passes direct image inspection.

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
