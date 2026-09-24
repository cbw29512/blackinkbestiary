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


def build_review_prompt(page: dict) -> str:
    checks = build_supervisor_checklist(page)
    return """You are the Black-Ink Bestiary visual quality inspector.
Inspect the PROVIDED IMAGE, then compare only what is visibly present with the written requirements below.
Be strict about extra/missing/duplicated limbs, hands, heads, tails, wings, eyes and other anatomy; malformed attachments;
monster identity; signature features; environment identity; story readability; clutter; solid-black masses; grayscale/shading;
large usable coloring regions; and creature/scenery separation.
Do not assume a requested feature exists merely because the text says it should.
Return JSON only:
{"pass": true|false, "score": 0-100, "defects": ["specific visible defect"], "preserve": ["successful visible feature"]}
Pass only when there is no meaningful visible defect worth another edit.
REQUIREMENTS:
- """ + "\n- ".join(checks)


def review_image(page: dict, image_path: str | Path, config: dict) -> dict:
    settings = config.get("vision_reviewer") or {}
    if settings.get("provider") != "ollama":
        raise VisionReviewError("Required vision_reviewer.provider must be ollama")
    image_path = Path(image_path)
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": settings.get("model", "qwen3-vl:4b"),
        "stream": False,
        "format": {"type": "object", "properties": {"pass": {"type": "boolean"}, "score": {"type": "integer"}, "defects": {"type": "array", "items": {"type": "string"}}, "preserve": {"type": "array", "items": {"type": "string"}}}, "required": ["pass", "score", "defects", "preserve"]},
        "messages": [{"role": "user", "content": build_review_prompt(page), "images": [encoded]}],
        "options": {"temperature": 0},
    }
    result = _request(settings.get("base_url", "http://127.0.0.1:11434").rstrip("/") + "/api/chat", payload)
    message = result.get("message") or {}
    raw = (message.get("content") or "").strip()
    if not raw:
        thinking = (message.get("thinking") or "").strip()
        raise VisionReviewError("Vision reviewer returned an empty answer" + (f"; thinking={thinking[:500]}" if thinking else "") + f"; response_keys={sorted(result.keys())}")
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise VisionReviewError(f"Vision reviewer returned non-JSON content: {raw[:200]}") from exc
    if not isinstance(verdict.get("pass"), bool) or not isinstance(verdict.get("defects"), list):
        raise VisionReviewError(f"Vision reviewer returned invalid verdict: {verdict}")
    verdict.setdefault("score", 0)
    verdict.setdefault("preserve", [])
    return verdict


def review_notes(verdict: dict) -> dict:
    return {
        "text": "Correct these visible defects: " + "; ".join(str(x) for x in verdict.get("defects", [])),
        "failed_dimensions": [str(x) for x in verdict.get("defects", [])],
        "preserve_dimensions": [str(x) for x in verdict.get("preserve", [])],
    }
