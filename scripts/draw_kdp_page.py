"""Draw one KDP coloring page from a director JSON file.

Uses FLUX.2 Pro. The key stays in the environment. One page per run.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.bfl.ai/v1/flux-2-pro"
# Portrait near 8.5x11, multiples of 16, under 4 megapixels.
WIDTH = 1680
HEIGHT = 2176
PRINT_WIDTH = 2550
PRINT_HEIGHT = 3300
MARGIN = 112  # 0.375 inch at 300 DPI


def brief(page: dict) -> str:
    rules = page.get("line_rules") or {}
    forbidden = ", ".join(rules.get("forbidden") or [])
    avoid = ", ".join(page.get("must_not_be") or [])
    return "\n".join(
        [
            page.get("picture") or "",
            f"Subject: {page.get('subject', '')}.",
            f"Ink: {rules.get('ink', 'pure black outlines on white')}.",
            f"Shapes: {rules.get('shapes', 'large closed regions')}.",
            f"Do not include: {forbidden}.",
            f"The creature must not be: {avoid}.",
        ]
    )


def post_json(url: str, payload: dict, key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"x-key": key, "Content-Type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, key: str) -> dict:
    request = urllib.request.Request(url, headers={"x-key": key, "accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def to_print_png(source: Path, dest: Path) -> None:
    from PIL import Image

    image = Image.open(source).convert("L")
    image = image.point(lambda pixel: 0 if pixel < 180 else 255, mode="1")
    image = image.convert("L")
    max_w = PRINT_WIDTH - (MARGIN * 2)
    max_h = PRINT_HEIGHT - (MARGIN * 2)
    image.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
    page = Image.new("L", (PRINT_WIDTH, PRINT_HEIGHT), 255)
    left = (PRINT_WIDTH - image.width) // 2
    top = (PRINT_HEIGHT - image.height) // 2
    page.paste(image, (left, top))
    page.save(dest, format="PNG", dpi=(300, 300))


def main() -> int:
    page_id = sys.argv[1] if len(sys.argv) > 1 else "I-04"
    key = os.environ.get("BFL_API_KEY", "").strip()
    if not key:
        print("Set BFL_API_KEY first. No page was requested.", file=sys.stderr)
        return 2
    spec_path = ROOT / "data" / "director" / f"{page_id}.json"
    page = json.loads(spec_path.read_text(encoding="utf-8"))
    prompt = brief(page)
    print(f"Requesting {page_id} at {WIDTH}x{HEIGHT}.")
    job = post_json(API, {"prompt": prompt, "width": WIDTH, "height": HEIGHT}, key)
    polling = job.get("polling_url")
    if not polling:
        print(json.dumps(job), file=sys.stderr)
        return 1
    status = "Pending"
    result = {}
    for _ in range(60):
        time.sleep(2)
        result = get_json(polling, key)
        status = str(result.get("status") or "")
        print(status)
        if status == "Ready":
            break
        if status in {"Error", "Failed", "Request Moderated"}:
            print(json.dumps(result), file=sys.stderr)
            return 1
    else:
        print("Timed out waiting for the image.", file=sys.stderr)
        return 1
    sample = ((result.get("result") or {}).get("sample"))
    if not sample:
        print(json.dumps(result), file=sys.stderr)
        return 1
    out_dir = ROOT / "web" / "kdp-pages"
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = out_dir / f"{page_id}-raw.jpg"
    urllib.request.urlretrieve(sample, raw)
    print(f"Saved {raw}")
    try:
        print_path = out_dir / f"{page_id}.png"
        to_print_png(raw, print_path)
        print(f"Saved {print_path}")
    except ImportError:
        print("Pillow is not installed. The raw image was saved. The 300 DPI page was not.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
