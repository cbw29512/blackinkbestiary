from __future__ import annotations

QA_STALL_LIMIT = 3


def prior_error_text(prior: dict | None) -> str:
    return str((prior or {}).get("error") or "")


def is_safe_margin_failure(prior: dict | None) -> bool:
    return "safe_margin_too_busy" in prior_error_text(prior)


def qa_fail_streak(prior: dict | None) -> int:
    return int((prior or {}).get("qa_fail_streak") or 0)


def margin_recovery_feedback(prior: dict | None) -> dict:
    streak = qa_fail_streak(prior) + 1
    return {
        "stage": "quality",
        "text": (
            "Production QA failed because ink occupied the print-safe page margin. "
            "Keep the outer eight percent of the page empty white. Pull the subject, "
            "wings, tails, weapons, masonry, and flocking fully inside the inner frame. "
            "Do not let architecture or appendages touch or cross the page edge."
        ),
        "routing_recommendation": "regenerate",
        "stagnation_escalation": True,
        "composition_escape_offset": streak,
    }


def generic_qa_recovery_feedback(prior: dict | None) -> dict:
    return {
        "stage": "quality",
        "text": prior_error_text(prior) or "Previous candidate failed production QA.",
        "routing_recommendation": "regenerate",
        "stagnation_escalation": True,
        "composition_escape_offset": qa_fail_streak(prior) + 1,
    }


def same_fingerprint_qa_stall(prior: dict | None, current_fingerprint: str) -> bool:
    if not prior:
        return False
    if str(prior.get("status") or "") not in {"technical_qa_failed", "technical_qa_stalled"}:
        return False
    if str(prior.get("generation_fingerprint") or "") != str(current_fingerprint or ""):
        return False
    return qa_fail_streak(prior) >= QA_STALL_LIMIT or str(prior.get("status") or "") == "technical_qa_stalled"


def next_qa_fail_streak(prior: dict | None, current_fingerprint: str) -> int:
    if (
        prior
        and str(prior.get("generation_fingerprint") or "") == current_fingerprint
        and str(prior.get("status") or "") in {"technical_qa_failed", "technical_qa_stalled"}
    ):
        return qa_fail_streak(prior) + 1
    return 1
