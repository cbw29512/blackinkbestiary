from __future__ import annotations

from pathlib import Path

try:
    from .page_contract import load_page_contract
except ImportError:
    from page_contract import load_page_contract


def page_recipe_errors(page: dict, root: Path) -> list[str]:
    contract = load_page_contract(root / "config" / "universal_page_contract.json")
    page_id = str(page.get("page_id") or "<missing>")
    allowed = set(contract.get("allowed_source_fields") or [])
    forbidden = set(contract.get("forbidden_source_fields") or [])
    errors: list[str] = []

    unknown = sorted(set(page) - allowed)
    if unknown:
        errors.append(f"{page_id}: page recipe has unsupported fields: {', '.join(unknown)}")

    present_forbidden = sorted(forbidden.intersection(page))
    if present_forbidden:
        errors.append(f"{page_id}: legacy derived fields must not be stored in the page recipe: {', '.join(present_forbidden)}")

    exceptions = page.get("page_exceptions")
    if exceptions is None:
        return errors
    if not isinstance(exceptions, dict):
        errors.append(f"{page_id}: page_exceptions must be an object")
        return errors

    exception_contract = contract.get("page_exceptions") or {}
    allowed_exception_fields = set(exception_contract.get("allowed_fields") or [])
    unknown_exception_fields = sorted(set(exceptions) - allowed_exception_fields)
    if unknown_exception_fields:
        errors.append(
            f"{page_id}: page_exceptions has unsupported fields: {', '.join(unknown_exception_fields)}"
        )

    for key, value in exceptions.items():
        if value in (None, "", [], {}):
            errors.append(f"{page_id}: page_exceptions.{key} cannot be empty")

    return errors
