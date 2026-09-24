from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

from prompt_builder import build_supervisor_checklist


class VisionReviewError(RuntimeError):
    pass


def _request(url: str, payload: dict, timeout: float = 180.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise VisionReviewError(f"Vision reviewer unavailable or invalid: {exc}") from exc


def build_identity_review_prompt(page: dict) -> str:
    checks = build_supervisor_checklist(page)
    identity_prefixes = (
        "Clearly recognizable as ",
        "Canonical scale reads as:",
        "Canonical body plan reads as:",
        "Identity check:",
        "Reject identity drift:",
        "Swarm reads as ",
    )
    identity_checks = [item for item in checks if item.startswith(identity_prefixes)]
    return """You are the Black-Ink Bestiary identity and anatomy gate.
Inspect ONLY the PROVIDED IMAGE. Ignore beauty, style polish, environment quality, and composition except where they prove creature scale.
Your only job is to decide whether the pictured creature is visibly the required species/body plan at the required scale.
FAIL CLOSED: if any required identity trait, scale relationship, body-plan feature, limb topology/count, or anti-drift rule is visibly wrong, pass=false.
Do not give the image the benefit of the doubt because it is attractive or fantasy-themed. Generic dragon-person, demon, orc, furry brute, heroic bodybuilder, or humanoid reinterpretations fail unless explicitly canonical.
For countable anatomy, reject extra, missing, duplicated, merged, branched, or scenery-grown limbs/appendages. Ordinary perspective occlusion is allowed only when the body plan still reads coherently.
For tiny/small creatures, reject adult-human-sized heroic mass even when the face is approximately correct. For swarms, reject an oversized leader.
Return exactly one compact JSON object and nothing else:\n{"pass": true|false, "score": 0-100, "defects": ["specific visible identity defect"], "preserve": ["successful visible identity feature"]}
Report at most 4 defects and at most 3 preserve items, each under 80 characters. A passing identity image should normally score 90-100. Any identity failure should score 49 or lower.
IDENTITY / ANATOMY GATES:
- """ + "\n- ".join(identity_checks)


def build_review_prompt(page: dict) -> str:
    checks = build_supervisor_checklist(page)
    hard_prefixes = ("Clearly recognizable as ", "Habitat reads as:", "Scene moment reads as:", "Canonical scale reads as:", "Canonical body plan reads as:", "Identity check:", "Reject identity drift:", "Required element present:", "Physical state reads as:", "Support/contact is visible and believable:", "Motion/weight reads correctly:", "Swarm reads as ")
    hard_identity = [item for item in checks if item.startswith(hard_prefixes)]
    other_checks = [item for item in checks if item not in hard_identity]
    return """You are the Black-Ink Bestiary visual quality inspector.
Inspect the PROVIDED IMAGE, then compare only what is visibly present with the written requirements below.
HARD RULE: any failed monster-identity gate, canonical scale/proportion gate, canonical body-plan gate, habitat gate, story-moment gate, physical support/interaction gate, known identity-drift condition, missing required element, swarm composition gate, or malformed anatomy forces pass=false. A beautiful image cannot compensate for the wrong creature, wrong environment, wrong story beat, unsupported pose, or unreadable required interaction.
Be strict about extra/missing/duplicated limbs, hands, heads, tails, wings, eyes and other anatomy; malformed attachments;
monster identity; body proportions; signature features; environment identity; story readability; clutter; solid-black masses; grayscale/shading;
large usable coloring regions; and creature/scenery separation.
Do not assume a requested feature exists merely because the text says it should.
Return exactly one compact JSON object and nothing else:\n{"pass": true|false, "score": 0-100, "defects": ["specific visible defect"], "preserve": ["successful visible feature"]}
Report at most 4 defects and at most 3 preserve items. Each item must be a short phrase under 80 characters.
Prioritize only the defects that matter most for the next image edit.
Pass only when there is no meaningful visible defect worth another edit. Inspect silently and emit the JSON verdict immediately. Do not write step-by-step reasoning.
HARD IDENTITY GATES:
- """ + "\n- ".join(hard_identity) + """
OTHER QUALITY REQUIREMENTS:
- """ + "\n- ".join(other_checks)


def _parse_verdict(result: dict, stage: str) -> dict:
    raw = (result.get("response") or "").strip() if isinstance(result, dict) else ""
    if not raw:
        raise VisionReviewError(
            f"{stage} reviewer returned an empty answer"
            f"; done_reason={result.get('done_reason') if isinstance(result, dict) else None}"
            f"; eval_count={result.get('eval_count') if isinstance(result, dict) else None}"
            f"; response_keys={sorted(result.keys()) if isinstance(result, dict) else []}"
        )
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                verdict = json.loads(raw[start:end + 1])
            except json.JSONDecodeError as exc:
                raise VisionReviewError(
                    f"{stage} reviewer returned non-JSON content: {raw[:300]}"
                    f"; done_reason={result.get('done_reason')}; eval_count={result.get('eval_count')}"
                ) from exc
        else:
            raise VisionReviewError(
                f"{stage} reviewer returned non-JSON content: {raw[:300]}"
                f"; done_reason={result.get('done_reason')}; eval_count={result.get('eval_count')}"
            )
    score = verdict.get("score")
    preserve = verdict.get("preserve")
    defects = verdict.get("defects")
    if (
        not isinstance(verdict.get("pass"), bool)
        or not isinstance(score, int)
        or isinstance(score, bool)
        or not 0 <= score <= 100
        or not isinstance(defects, list)
        or not all(isinstance(x, str) for x in defects)
        or not isinstance(preserve, list)
        or not all(isinstance(x, str) for x in preserve)
    ):
        raise VisionReviewError(f"{stage} reviewer returned invalid verdict: {verdict}")
    verdict["defects"] = defects[:4]
    verdict["preserve"] = preserve[:3]
    return verdict


def _vision_payload(settings: dict, prompt: str, encoded: str, max_tokens: int) -> dict:
    return {
        "model": settings.get("model", "qwen3-vl:4b"),
        "stream": False,
        "prompt": prompt,
        "images": [encoded],
        "options": {"temperature": 0, "num_predict": max_tokens},
        "think": False,
    }


def review_image(page: dict, image_path: str | Path, config: dict) -> dict:
    settings = config.get("vision_reviewer") or {}
    if settings.get("provider") != "ollama":
        raise VisionReviewError("Required vision_reviewer.provider must be ollama")
    image_path = Path(image_path)
    try:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise VisionReviewError(f"Could not read image for vision review: {image_path}: {exc}") from exc

    url = settings.get("base_url", "http://127.0.0.1:11434").rstrip("/") + "/api/generate"

    identity_result = _request(
        url,
        _vision_payload(settings, build_identity_review_prompt(page), encoded, 2048),
    )
    identity_verdict = _parse_verdict(identity_result, "Identity")
    if not identity_verdict.get("pass"):
        # Identity failure is terminal for this refinement pass. Keep the score
        # below passing range even if the local model ignored the prompt's cap.
        identity_verdict["score"] = min(int(identity_verdict.get("score") or 0), 49)
        return identity_verdict

    quality_result = _request(
        url,
        _vision_payload(settings, build_review_prompt(page), encoded, 4096),
    )
    return _parse_verdict(quality_result, "Quality")


def review_notes(verdict: dict) -> dict:
    return {
        "text": "Correct these visible defects: " + "; ".join(str(x) for x in verdict.get("defects", [])),
        "failed_dimensions": [str(x) for x in verdict.get("defects", [])],
        "preserve_dimensions": [str(x) for x in verdict.get("preserve", [])],
    }
