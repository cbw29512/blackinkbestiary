from __future__ import annotations


def _allowed(contract: dict, key: str) -> set[str]:
    return {str(item) for item in contract.get(key) or []}


def page_recipe_errors(page: dict, contract: dict) -> list[str]:
    page_id = str(page.get("page_id") or "<missing>")
    errors: list[str] = []

    allowed_top = _allowed(contract, "allowed_recipe_fields")
    unknown = sorted(set(page) - allowed_top)
    for field in unknown:
        errors.append(f"{page_id}: page recipe field {field!r} is not allowed by the page contract")

    legacy = _allowed(contract, "legacy_forbidden_fields")
    for field in sorted(set(page).intersection(legacy)):
        errors.append(f"{page_id}: legacy page field {field!r} must be derived or removed")

    nested_specs = {
        "environment_variant": _allowed(contract, "allowed_environment_variant_fields"),
        "physicality": _allowed(contract, "allowed_physicality_fields"),
        "page_exceptions": _allowed(contract, "allowed_page_exception_fields"),
    }
    for field, allowed_fields in nested_specs.items():
        payload = page.get(field)
        if payload is None:
            continue
        if not isinstance(payload, dict):
            errors.append(f"{page_id}: {field} must be an object")
            continue
        for child in sorted(set(payload) - allowed_fields):
            errors.append(f"{page_id}: {field}.{child} is not allowed by the page contract")

    exceptions = page.get("page_exceptions") or {}
    if isinstance(exceptions, dict):
        for field in ("must_include", "must_avoid"):
            value = exceptions.get(field)
            if value is not None and (
                not isinstance(value, list)
                or any(not str(item).strip() for item in value)
            ):
                errors.append(f"{page_id}: page_exceptions.{field} must be a list of non-empty strings")

    return errors
