import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from edit_prompt import build_edit_prompt
from prompt_builder import build_prompt, load_monster_spec
from image_edit_profile import prepare_distilled_image_edit
from workflow_adapter import PROMPT_TOKEN, SEED_TOKEN, prepare_workflow, validate_template
from qa import inspect_png


class PromptTests(unittest.TestCase):
    def test_prompt_contains_page_and_style(self):
        page = {
            "page_id": "X-01",
            "order": 1,
            "monster_spec_id": "kobold-warrior",
            "moment": "tripwire triggered",
            "archetype": "trap_scene",
            "must_include": ["pit"],
            "environment_profile_id": "underground.trapped-stone-corridor",
            "environment_variant": {
                "landmark": "open pit beside torch bracket",
                "framing": "tight corridor perspective",
                "interaction": "tripwire triggers the pit",
            },
            "physicality": {
                "mode": "grounded",
                "support": "both feet on the corridor floor",
                "motion": "leaning toward the triggered wire",
            },
        }
        text = build_prompt(page)
        self.assertIn("Kobold Warrior", text)
        self.assertIn("Trapped Stone Corridor", text)
        self.assertIn("large uninterrupted white regions", text)


    def test_edit_prompt_is_preservation_first(self):
        page = {
            "page_id": "X-02",
            "order": 2,
            "monster_spec_id": "goblin-minion",
            "moment": "running away with a stolen ham",
            "archetype": "action_scene",
            "must_include": ["stolen ham"],
            "must_avoid": ["modern kitchen"],
            "environment_profile_id": "underground.rough-stone-pantry",
            "environment_variant": {
                "landmark": "large food shelves",
                "framing": "pantry corner",
                "interaction": "goblin steals food from storage",
            },
            "physicality": {
                "mode": "running",
                "support": "one foot contacts the floor",
                "motion": "forward escape stride",
            },
        }
        text = build_edit_prompt(
            page,
            {"text": "make the ham obvious", "quick_tags": ["more white space"]},
        )
        self.assertIn("EDIT THE PROVIDED CURRENT COLORING PAGE", text)
        self.assertIn("Keep every successful part", text)
        self.assertIn("make the ham obvious", text)
        self.assertIn("stolen ham", text)


    def test_identity_review_uses_structural_rebuild_not_preservation(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-14")
        text = build_edit_prompt(
            page,
            {
                "stage": "identity",
                "text": "dragon head and separate wings are visible",
                "failed_dimensions": ["wrong body plan"],
                "preserve_dimensions": ["stone ceiling"],
            },
            candidate_no=1,
        )
        self.assertIn("IDENTITY REBUILD MODE", text)
        self.assertIn("Rebuild the creature silhouette, scale, proportions, limb topology", text)
        self.assertIn("redrawing most or all of the creature", text)
        self.assertNotIn("Preserve the existing framing, camera angle, pose", text)

    def test_scene_review_can_rebuild_pose_and_environment_geometry(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-10")
        text = build_edit_prompt(
            page,
            {
                "stage": "scene",
                "text": "spiral stair is not visible",
                "failed_dimensions": ["missing stair geometry"],
                "preserve_dimensions": ["ogre anatomy"],
            },
            candidate_no=1,
        )
        self.assertIn("SCENE REBUILD MODE", text)
        self.assertIn("rebuild pose, prop placement, contact geometry, camera/framing", text)
        self.assertIn("moving the creature, props, or camera", text)

    def test_runtime_standards_do_not_reinflate_small_creatures(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-01")
        text = build_prompt(page).lower()
        self.assertIn("canonical scale lock", text)
        self.assertIn("canonical creature scale is immutable", text)
        self.assertIn("first-read focal subject at canonical scale and proportions", text)
        self.assertNotIn("one large centered unmistakable monster", text)
        self.assertNotIn("normally occupying about 60–75% of page height", text)

    def test_fresh_generation_ignores_legacy_modify_preserve_recipe(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-01")
        text = build_prompt(page)
        self.assertNotIn("PRESERVE: kobold pose", text)
        self.assertNotIn("This is a targeted refinement.", text)
        self.assertIn("PAGE RECIPE LOCK", text)

    def test_story_contract_drives_generation_prompt(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-09")
        text = build_prompt(page)
        self.assertIn("STORY BEAT:", text)
        self.assertIn("STORY/ENVIRONMENT INTERACTION:", text)
        self.assertIn("STATIC STORY TEST:", text)
        self.assertIn("not as a character portrait", text)

    def test_first_five_tome_pages_resolve_canonical_specs(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        pages = tome["pages"][:5]
        self.assertEqual(
            [page.get("monster_spec_id") for page in pages],
            [
                "kobold-warrior",
                "kobold-shrine-keeper",
                "goblin-minion",
                "goblin-warrior",
                "goblin-boss",
            ],
        )
        for page in pages:
            spec = load_monster_spec(page)
            self.assertEqual(spec["monster_id"], page["monster_spec_id"])
            self.assertTrue(spec["visual_identity"]["must_keep"])
            self.assertTrue(spec["accuracy_checks"])

    def test_canonical_kobold_identity_enters_generation_prompt(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        text = build_prompt(tome["pages"][0])
        self.assertIn("CANONICAL SILHOUETTE", text)
        self.assertIn("long balancing tail", text)
        self.assertIn("goblin-like round head", text)
        self.assertIn("REFERENCE RULE", text)
        self.assertIn("anatomy, silhouette, and identity only", text)

    def test_generation_prompt_has_hard_anatomy_integrity_lock(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        kobold = next(page for page in tome["pages"] if page["page_id"] == "I-01")
        spider = next(page for page in tome["pages"] if page["page_id"] == "I-22")
        kobold_text = build_prompt(kobold, candidate_no=1)
        spider_text = build_prompt(spider, candidate_no=2)
        for text in (kobold_text, spider_text):
            self.assertIn("ANATOMICAL INTEGRITY LOCK", text)
            self.assertIn("Never invent or duplicate heads", text)
            self.assertIn("may not branch", text)
            self.assertIn("Candidate variation may change pose only", text)
        self.assertIn("visible balancing tail", kobold_text)
        self.assertIn("Exactly eight jointed arachnid legs", spider_text)


    def test_swarm_prompt_uses_collective_subject_not_giant_leader(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        bat_swarm = next(page for page in tome["pages"] if page["page_id"] == "I-17")
        text = build_prompt(bat_swarm, candidate_no=1)
        self.assertIn("SWARM COMPOSITION LOCK", text)
        self.assertIn("no single oversized member may dominate", text)
        self.assertIn("controlled population", text)
        self.assertIn("broad white gaps", text)

    def test_prompt_has_creature_scenery_ownership_firewall(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        text = build_prompt(tome["pages"][0])
        self.assertIn("CREATURE/SCENERY OWNERSHIP FIREWALL", text)
        self.assertIn("may never sprout from, merge into, replace, or duplicate limbs", text)

    def test_centipede_prompt_requires_leg_pair_on_every_visible_segment(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-20")
        text = build_prompt(page)
        self.assertIn("ONE PAIR of slender walking legs attached to EVERY visible trunk segment", text)
        self.assertIn("sparse legs only near the head", text)

    def test_fire_beetle_prompt_requires_three_signature_glands(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-21")
        text = build_prompt(page)
        self.assertIn("three distinct luminous glands", text)
        self.assertIn("two by the eyes and one near the rear abdomen", text)

    def test_giant_bat_prompt_forbids_separate_arms(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-16")
        text = build_prompt(page)
        self.assertIn("two forelimbs that ARE the membrane wings", text)
        self.assertIn("Never add separate humanoid arms", text)

    def test_remaining_tome_i_story_actions_have_literal_visual_proof(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        pages = {page["page_id"]: page for page in tome["pages"]}

        zombie = build_prompt(pages["I-11"])
        self.assertIn("CHAIN-DRAG PROOF", zombie)
        self.assertIn("touch the floor or stair treads", zombie)

        troll = build_prompt(pages["I-12"])
        self.assertIn("REGENERATION PROOF", troll)
        self.assertIn("FIRE-REACTION PROOF", troll)

        limb = build_prompt(pages["I-13"])
        self.assertIn("SEVERED-LIMB MOTION PROOF", limb)
        self.assertIn("complete moving subject", limb)

        stirges = build_prompt(pages["I-15"])
        self.assertIn("FEEDING-CONTACT PROOF", stirges)
        self.assertIn("proboscises visibly contacting", stirges)

        bats = build_prompt(pages["I-17"])
        self.assertIn("VERTICAL-ORIGIN PROOF", bats)
        self.assertIn("well/shaft opening", bats)

        rat = build_prompt(pages["I-18"])
        self.assertIn("NEST-DEFENSE PROOF", rat)
        self.assertIn("interpose itself", rat)

        beetle = build_prompt(pages["I-21"])
        self.assertIn("LINE-ART LIGHT PROOF", beetle)
        self.assertIn("nearby rock/timber surface", beetle)

    def test_new_shape_locks_cover_known_non_canary_failures(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        pages = {page["page_id"]: page for page in tome["pages"]}

        troll = build_prompt(pages["I-12"])
        self.assertIn("very long arms hanging toward the knees", troll)
        self.assertIn("no horns", troll.lower())

        limb = build_prompt(pages["I-13"])
        self.assertIn("exactly one severed troll arm only", limb.lower())

        stirges = build_prompt(pages["I-15"])
        self.assertIn("one long straight needle proboscis", stirges.lower())
        self.assertIn("no giant leader", stirges.lower())

        beetle = build_prompt(pages["I-21"])
        self.assertIn("exactly six walking legs", beetle.lower())
        self.assertIn("three unmistakable outlined luminous gland bulges", beetle.lower())

    def test_modify_notes_enter_prompt(self):
        page = {
            "page_id": "X-03",
            "order": 3,
            "monster_spec_id": "kobold-warrior",
            "moment": "waiting",
            "archetype": "lair_scene",
            "environment_profile_id": "underground.limestone-drip-cave",
            "environment_variant": {
                "landmark": "large flowstone shelf",
                "framing": "low cave chamber",
                "interaction": "kobold waits beside the rock shelf",
            },
            "physicality": {
                "mode": "grounded",
                "support": "feet contact the cave floor",
                "motion": "alert waiting stance",
            },
        }
        text = build_prompt(page, {"text": "simplify walls", "quick_tags": ["more white space"]})
        self.assertIn("simplify walls", text)
        self.assertIn("more white space", text)


class WorkflowTests(unittest.TestCase):
    def test_template_tokens_replace(self):
        template = {"1": {"inputs": {"text": PROMPT_TOKEN, "seed": SEED_TOKEN}}}
        self.assertEqual(validate_template(template), [])
        out = prepare_workflow(template, prompt="hello", seed=123)
        self.assertEqual(out["1"]["inputs"]["text"], "hello")
        self.assertEqual(out["1"]["inputs"]["seed"], 123)


    def test_image_edit_preparation_uses_current_image_and_single_input_branch(self):
        workflow = {
            "nodes": [
                {"id": 76, "type": "LoadImage", "widgets_values": ["old.png", "image"]},
                {
                    "id": 75,
                    "type": "single-def",
                    "mode": 0,
                    "inputs": [
                        {"name": "text", "type": "STRING", "link": None},
                        {"name": "image", "type": "IMAGE", "link": 155},
                    ],
                    "widgets_values": ["old-unet", "old-clip", "old-vae", "old prompt", 1],
                },
                {"id": 9, "type": "SaveImage", "mode": 0, "inputs": []},
                {
                    "id": 92,
                    "type": "multi-def",
                    "mode": 4,
                    "inputs": [
                        {"name": "text", "type": "STRING", "link": None},
                        {"name": "image", "type": "IMAGE", "link": 169},
                        {"name": "image_1", "type": "IMAGE", "link": 172},
                    ],
                    "widgets_values": ["x", "y", "z", "multi", 2],
                },
                {"id": 94, "type": "SaveImage", "mode": 4, "inputs": []},
            ],
            "links": [
                [155, 76, 0, 75, 1, "IMAGE"],
                [154, 75, 0, 9, 0, "IMAGE"],
                [171, 92, 0, 94, 0, "IMAGE"],
            ],
            "definitions": {
                "subgraphs": [
                    {
                        "id": "single-def",
                        "name": "Image Edit (Flux.2 Klein 4B Distilled)",
                        "inputs": [
                            {"name": "text", "type": "STRING"},
                            {"name": "image", "type": "IMAGE"},
                        ],
                        "nodes": [
                            {"id": 70, "type": "UNETLoader", "widgets_values": ["old"]},
                            {"id": 71, "type": "CLIPLoader", "widgets_values": ["old"]},
                            {"id": 72, "type": "VAELoader", "widgets_values": ["old"]},
                        ],
                    },
                    {
                        "id": "multi-def",
                        "name": "Image Edit (Flux.2 Klein 4B Distilled) Multi",
                        "inputs": [
                            {"name": "image", "type": "IMAGE"},
                            {"name": "image_1", "type": "IMAGE"},
                        ],
                        "nodes": [],
                    },
                ]
            },
        }

        class FakeCli:
            def fetch_template(self, name, destination):
                destination.write_text(json.dumps(workflow), encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "edit.json"
            result = prepare_distilled_image_edit(
                FakeCli(),
                "template",
                path,
                prompt="keep pose, add ham",
                seed=42,
                input_image="blackink-edits/source.png",
                model_filename="unet.safetensors",
                clip_filename="clip.safetensors",
                vae_filename="vae.safetensors",
            )
            prepared = json.loads(path.read_text(encoding="utf-8"))

        nodes = {node["id"]: node for node in prepared["nodes"]}
        self.assertEqual(nodes[76]["widgets_values"][0], "blackink-edits/source.png")
        self.assertEqual(nodes[75]["widgets_values"][3], "keep pose, add ham")
        self.assertEqual(nodes[75]["widgets_values"][4], 42)
        self.assertEqual(nodes[75]["mode"], 0)
        self.assertEqual(nodes[92]["mode"], 4)
        self.assertEqual(nodes[9]["mode"], 0)
        self.assertEqual(nodes[94]["mode"], 4)
        self.assertEqual(result["root_id"], "75")

    def test_missing_tokens_rejected(self):
        problems = validate_template({"1": {"inputs": {}}})
        self.assertEqual(len(problems), 2)


class ModelManifestTests(unittest.TestCase):
    def test_v1_model_manifest_is_single_distilled_4b_stack(self):
        manifest_path = ROOT / "art_pipeline" / "model_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        names = [item["filename"] for item in manifest["required_models"]]
        self.assertIn("flux-2-klein-4b-fp8.safetensors", names)
        self.assertIn("qwen_3_4b.safetensors", names)
        self.assertIn("flux2-vae.safetensors", names)
        self.assertFalse(any("9b" in name.lower() for name in names))
        self.assertFalse(any("base-4b" in name.lower() for name in names))
        for item in manifest["required_models"]:
            self.assertTrue(item["url"].startswith("https://huggingface.co/"))


class QATests(unittest.TestCase):
    def test_missing_candidate_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "missing.png"
            from qa import inspect_candidate
            result = inspect_candidate(path)
            self.assertFalse(result["pass"])
            self.assertIn("missing_file", result["reasons"])


    def test_prompt_injects_family_failure_modes_for_minimal_monster(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-09")
        text = build_prompt(page)
        self.assertIn("KNOWN IDENTITY DRIFT TO PREVENT", text)
        self.assertIn("gorilla, ape-man, or primate", text)
        self.assertIn("CORRECTION:", text)

    def test_candidate_prompts_are_materially_distinct_and_colorable(self):
        tome = json.loads((ROOT / "data" / "tome-I.json").read_text(encoding="utf-8"))
        page = next(page for page in tome["pages"] if page["page_id"] == "I-24")
        prompts = [build_prompt(page, candidate_no=n) for n in range(1, 5)]
        self.assertEqual(len(set(prompts)), 4)
        for n, text in enumerate(prompts, 1):
            self.assertIn(f"CANDIDATE {n} COMPOSITION LOCK", text)
            self.assertIn("NEVER fill a creature", text)
            self.assertIn("No large black masses", text)
            self.assertIn("cube with straight readable edges", text)
            self.assertIn("remove humanoid anatomy entirely", text)


if __name__ == "__main__":
    unittest.main()
