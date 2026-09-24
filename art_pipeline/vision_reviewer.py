from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from pathlib import Path

from vision_review_prompts import (
    build_identity_review_prompt,
    build_review_prompt,
    build_scene_review_prompt,
)


class VisionReviewError(RuntimeError):
    pass


def _request(url: str, payload: dict, timeout: float = 180.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise VisionReviewError(f"Vision reviewer unavailable or invalid: {exc}") from exc


def _parse_verdict(result: dict, stage: str) -> dict:
    raw = (result.get("response") or "").strip() if isinstance(result, dict) else ""
    if not raw:
        raise VisionReviewError(
            f"{stage} reviewer returned an empty answer"
            f"; done_reason={result.get('done_reason') if isinstance(result, dict) else None}"
            f"; eval_count={result.get('eval_count') if isinstance(result, dict) else None}"
        )
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        diagnostics = (
            f"; done_reason={result.get('done_reason') if isinstance(result, dict) else None}"
            f"; eval_count={result.get('eval_count') if isinstance(result, dict) else None}"
        )
        if start < 0 or end <= start:
            raise VisionReviewError(
                f"{stage} reviewer returned non-JSON content: {raw[:300]}{diagnostics}"
            )
        try:
            verdict = json.loads(raw[start:end + 1])
        except json.JSONDecodeError as exc:
            raise VisionReviewError(
                f"{stage} reviewer returned non-JSON content: {raw[:300]}{diagnostics}"
            ) from exc

    score = verdict.get("score")
    defects = verdict.get("defects")
    preserve = verdict.get("preserve")
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
    if verdict["defects"]:
        verdict["pass"] = False
        verdict["score"] = min(score, 49)
    elif not verdict["pass"]:
        raise VisionReviewError(f"{stage} reviewer failed without a visible defect: {verdict}")
    return verdict


def _payload(settings: dict, prompt: str, encoded: str) -> dict:
    return {
        "model": settings.get("model", "qwen3-vl:4b"),
        "stream": False,
        "prompt": prompt,
        "images": [encoded],
        "options": {"temperature": 0, "num_predict": 2048},
        "think": False,
    }


def _run_gate(url: str, settings: dict, encoded: str, prompt: str, stage: str) -> dict:
    verdict = _parse_verdict(_request(url, _payload(settings, prompt, encoded)), stage)
    if not verdict["pass"]:
        verdict["score"] = min(verdict["score"], 49)
    return verdict


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
    gates = (
        ("Identity", build_identity_review_prompt(page)),
        ("Scene", build_scene_review_prompt(page)),
        ("Quality", build_review_prompt(page)),
    )
    for stage, prompt in gates:
        verdict = _run_gate(url, settings, encoded, prompt, stage)
        if not verdict["pass"]:
            return verdict
    return verdict


def review_notes(verdict: dict) -> dict:
    return {
        "text": "Correct these visible defects: " + "; ".join(str(x) for x in verdict.get("defects", [])),
        "failed_dimensions": [str(x) for x in verdict.get("defects", [])],
        "preserve_dimensions": [str(x) for x in verdict.get("preserve", [])],
    }
