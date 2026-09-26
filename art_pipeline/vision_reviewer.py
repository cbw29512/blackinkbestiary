from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from vision_review_prompts import (
    build_action_review_prompt,
    build_environment_review_prompt,
    build_identity_review_prompt,
    build_review_prompt,
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


POSITIVE_GATE_PREFIXES = (
    "Identity check:",
    "Canonical scale reads as:",
    "Canonical body plan reads as:",
    "Shape-first body geometry reads as:",
    "Habitat reads as:",
    "Scene moment reads as:",
    "Required element present:",
    "Physical state reads as:",
    "Support/contact is visible and believable:",
    "Motion/weight reads correctly:",
    "Mode-specific contact geometry reads correctly:",
    "Environment matches profile:",
    "Spatial type reads without the monster:",
    "Material language is visible:",
    "At least one unmistakable location marker is visible:",
    "Spatial geometry reads correctly:",
    "Space envelope matches:",
    "Space proportions read correctly:",
    "Space overhead/ceiling reads correctly:",
    "Space does not drift into:",
    "Unique landmark is visible:",
    "Monster/environment interaction reads clearly:",
    "One clear story beat reads as:",
    "Environment participates through:",
    "Interaction proof is visible:",
    "Body language communicates the action without needing the caption",
    "The page does not read as a neutral portrait or prop-holding pose",
    "What single verb describes what the monster is doing?",
    "Can that action be identified without reading the caption?",
    "Does at least one environment feature participate?",
    "Does the pose remain stable and easy to color?",
    "Would removing the prop destroy the entire story read?",
    "Controlled powered flight allowed by monster data:",
    "Pose is stable, natural, and easy to read in a static coloring page",
    "No jumping, falling, dropping, or accidental hovering",
)


def _positive_gate_values(prompt: str) -> set[str]:
    values = set()
    for raw in prompt.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            line = line[2:].strip()
        for prefix in POSITIVE_GATE_PREFIXES:
            if line.startswith(prefix):
                values.add(line)
                tail = line[len(prefix):].strip()
                if tail:
                    values.add(tail)
                break
    return values


def _semantic_tokens(text: str) -> set[str]:
    stop = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "have", "in", "is", "it", "of", "on", "or", "the", "to",
        "with", "without", "reads", "read", "visible", "appears", "exist",
        "exists", "clearly", "must", "remain", "stays", "stay",
    }
    return {
        token for token in re.findall(r"[a-z0-9]+", str(text or "").lower())
        if len(token) > 1 and token not in stop
    }


def _semantic_overlap(left: str, right: str) -> float:
    a = _semantic_tokens(left)
    b = _semantic_tokens(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _negative_polarity(text: str) -> bool:
    value = str(text or "").lower()
    return bool(re.search(
        r"\b(?:no|not|without|missing|absent|lack|lacks|lacking|never|cannot|can't|doesn't|does not|isn't|is not|aren't|are not)\b",
        value,
    ))


def _positive_gate_echoes(verdict: dict, prompt: str) -> list[dict]:
    positive = sorted(_positive_gate_values(prompt))
    issues = []
    for defect in verdict.get("defects") or []:
        defect_text = str(defect).strip()
        if not defect_text:
            continue
        best_gate = None
        best_score = 0.0
        for gate in positive:
            score = _semantic_overlap(defect_text, gate)
            if score > best_score:
                best_score = score
                best_gate = gate
        if (
            best_gate
            and best_score >= 0.72
            and _negative_polarity(defect_text) == _negative_polarity(best_gate)
        ):
            issues.append({
                "kind": "positive_gate_echo",
                "defect": defect_text,
                "gate": best_gate,
                "overlap": round(best_score, 3),
            })
    return issues


def _defect_preserve_conflicts(verdict: dict) -> list[dict]:
    issues = []
    for defect in verdict.get("defects") or []:
        for preserve in verdict.get("preserve") or []:
            score = _semantic_overlap(str(defect), str(preserve))
            if score >= 0.82:
                issues.append({
                    "kind": "defect_preserve_conflict",
                    "defect": str(defect),
                    "preserve": str(preserve),
                    "overlap": round(score, 3),
                })
    return issues


def _verdict_consistency_issues(verdict: dict, prompt: str) -> list[dict]:
    return _positive_gate_echoes(verdict, prompt) + _defect_preserve_conflicts(verdict)


def _consistency_retry_prompt(prompt: str, issues: list[dict]) -> str:
    details = []
    for issue in issues[:4]:
        if issue["kind"] == "positive_gate_echo":
            details.append(
                f'Defect "{issue["defect"]}" closely echoes positive requirement '
                f'"{issue["gate"]}".'
            )
        else:
            details.append(
                f'Defect "{issue["defect"]}" conflicts with preserve '
                f'"{issue["preserve"]}".'
            )
    return (
        prompt
        + "\n\nREVIEW CONSISTENCY RETRY — REINSPECT THE IMAGE.\n"
        + "Your prior verdict contained wording that may describe a satisfied "
          "requirement instead of a visible failure, or it contradicted a preserve item.\n"
        + "If the condition is visibly satisfied, REMOVE it from defects and place it "
          "in preserve if useful. If it is violated, rewrite the defect in explicit "
          "negative observable language describing what is wrong, missing, extra, "
          "incorrect, oversized, undersized, or unclear. Re-evaluate pass/fail from "
          "the image. Return a fresh JSON object only.\n"
        + "Consistency issues:\n- "
        + "\n- ".join(details)
    )


def _normalize_gate_echoes(verdict: dict, prompt: str) -> dict:
    positive = _positive_gate_values(prompt)
    normalized = []
    for defect in verdict.get("defects") or []:
        defect_text = str(defect).strip()
        if defect_text in positive:
            normalized.append(f"Required condition not visibly satisfied: {defect_text}")
        else:
            normalized.append(defect_text)
    verdict["defects"] = normalized
    return verdict


def _stage_required_evidence(page: dict, stage: str) -> list[str]:
    variant = page.get("environment_variant") or {}
    physicality = page.get("physicality") or {}
    if stage == "environment":
        return [
            value for value in (
                str(page.get("habitat") or "").strip(),
                str(variant.get("landmark") or "").strip(),
                str(variant.get("framing") or "").strip(),
            )
            if value
        ]
    if stage == "action":
        return [
            value for value in (
                str(page.get("moment") or "").strip(),
                str(variant.get("interaction") or "").strip(),
                str(physicality.get("support") or "").strip(),
                str(physicality.get("motion") or "").strip(),
            )
            if value
        ]
    return []


def _stage_pass_evidence_issues(page: dict, stage: str, verdict: dict) -> list[str]:
    if not verdict.get("pass"):
        return []
    required = _stage_required_evidence(page, stage)
    if len(required) < 2:
        return []

    preserve = [str(item).strip() for item in verdict.get("preserve") or [] if str(item).strip()]
    matched = []
    for requirement in required:
        if any(_semantic_overlap(requirement, evidence) >= 0.25 for evidence in preserve):
            matched.append(requirement)

    if len(matched) >= 2:
        return []
    missing = [item for item in required if item not in matched]
    return missing[:2]


def _evidence_retry_prompt(prompt: str, stage: str, missing: list[str]) -> str:
    return (
        prompt
        + "\n\nPASS EVIDENCE RETRY — REINSPECT THE IMAGE.\n"
        + f"Your prior {stage} PASS did not provide concrete visible evidence for enough page-specific gates. "
          "Do not assume the requested recipe is present. Either name literal visible proof in preserve or FAIL with a visible defect.\n"
        + "Unverified required facts:\n- "
        + "\n- ".join(missing)
    )


def _fail_unverified_pass(verdict: dict, stage: str, missing: list[str]) -> dict:
    failed = dict(verdict)
    failed["pass"] = False
    failed["score"] = min(int(failed.get("score") or 49), 49)
    failed["stage"] = stage
    label = stage.capitalize()
    failed["defects"] = [
        f"{label} proof not explicitly verified: {item}"[:80]
        for item in missing[:2]
    ]
    return failed


def _run_gate(url: str, settings: dict, encoded: str, prompt: str, stage: str) -> dict:
    verdict = _parse_verdict(_request(url, _payload(settings, prompt, encoded)), stage)
    issues = _verdict_consistency_issues(verdict, prompt)
    if issues:
        retry_prompt = _consistency_retry_prompt(prompt, issues)
        verdict = _parse_verdict(
            _request(url, _payload(settings, retry_prompt, encoded)),
            stage,
        )
        retry_issues = _verdict_consistency_issues(verdict, prompt)
        if retry_issues:
            raise VisionReviewError(
                f"{stage} reviewer remained self-contradictory after consistency retry: "
                f"{retry_issues[:2]}"
            )

    verdict = _normalize_gate_echoes(verdict, prompt)
    verdict["stage"] = stage.lower()
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
        ("Environment", build_environment_review_prompt(page)),
        ("Action", build_action_review_prompt(page)),
        ("Quality", build_review_prompt(page)),
    )
    for stage, prompt in gates:
        verdict = _run_gate(url, settings, encoded, prompt, stage)
        stage_id = stage.lower()
        missing = _stage_pass_evidence_issues(page, stage_id, verdict)
        if missing:
            verdict = _run_gate(
                url,
                settings,
                encoded,
                _evidence_retry_prompt(prompt, stage_id, missing),
                stage,
            )
            missing = _stage_pass_evidence_issues(page, stage_id, verdict)
            if missing:
                verdict = _fail_unverified_pass(verdict, stage_id, missing)
        if not verdict["pass"]:
            return verdict
    return verdict


def review_notes(verdict: dict) -> dict:
    return {
        "text": "Correct these visible defects: " + "; ".join(str(x) for x in verdict.get("defects", [])),
        "stage": str(verdict.get("stage") or "").strip().lower(),
        "failed_dimensions": [str(x) for x in verdict.get("defects", [])],
        "preserve_dimensions": [str(x) for x in verdict.get("preserve", [])],
    }
