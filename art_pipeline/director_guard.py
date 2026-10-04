from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

try:
    from .studio_config import load_studio_config, resolve_root_path
except ImportError:
    from studio_config import load_studio_config, resolve_root_path

logger = logging.getLogger(__name__)

LEGACY_DIRECTOR_API_ENV = "BLACKINK_ALLOW_LEGACY_DIRECTOR_API"
ROOT = Path(__file__).resolve().parents[1]


def _norm_subject(value: str) -> str:
    try:
        return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
    except Exception:
        logger.exception("Failed to normalize director subject %r.", value)
        raise


def director_request_errors(
    page: dict,
    root: Path = ROOT,
    environ: dict[str, str] | None = None,
) -> list[str]:
    try:
        errors: list[str] = []
        page_id = str(page.get("page_id") or "").strip()
        subject = str(page.get("subject") or page.get("monster_name") or "").strip()
        env = os.environ if environ is None else environ

        if env.get(LEGACY_DIRECTOR_API_ENV) != "1":
            errors.append(
                f"legacy director API is disabled; set {LEGACY_DIRECTOR_API_ENV}=1 only for an intentional external-API draft"
            )

        studio = load_studio_config(root)
        manifest_path = resolve_root_path(
            root,
            studio["active_book"]["manifest"],
            "active book manifest",
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        canonical = next(
            (item for item in manifest.get("pages") or [] if str(item.get("page_id") or "") == page_id),
            None,
        )
        if canonical is None:
            errors.append(f"{page_id or '<unknown>'}: no canonical Tome I page exists for this director ID")
            return errors

        canonical_subject = str(canonical.get("monster_name") or "").strip()
        if _norm_subject(subject) != _norm_subject(canonical_subject):
            errors.append(
                f"{page_id}: director subject {subject!r} disagrees with canonical Tome I subject {canonical_subject!r}"
            )
        return errors
    except Exception:
        logger.exception(
            "Failed to validate legacy director request for page %s.",
            page.get("page_id") if isinstance(page, dict) else "<invalid>",
        )
        raise


def assert_director_request_allowed(
    page: dict,
    root: Path = ROOT,
    environ: dict[str, str] | None = None,
) -> None:
    try:
        errors = director_request_errors(page, root=root, environ=environ)
        if errors:
            raise RuntimeError("director_request_blocked: " + " | ".join(errors))
    except Exception:
        logger.exception(
            "Legacy director API request rejected for page %s.",
            page.get("page_id") if isinstance(page, dict) else "<invalid>",
        )
        raise
