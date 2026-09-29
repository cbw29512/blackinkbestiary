"""Draw one KDP coloring page from a director JSON file.

FLUX.2 [pro] does not support negative prompts. Prompt upsampling is off
so the model draws our brief instead of rewriting it.
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.bfl.ai/v1/flux-2-pro"
WIDTH = 1760
HEIGHT = 2272
PRINT_WIDTH = 2550
PRINT_HEIGHT = 3300
MARGIN = 112
INK_CUTOFF = 90

HUMANOIDS = {
    "I-01", "I-02", "I-03", "I-04", "I-05", "I-06", "I-07", "I-08", "I-09",
    "I-10", "I-11", "I-12", "I-29", "I-32", "I-33", "I-34", "I-46", "I-50",
}

EDIT_PROMPTS = {
    "I-16": (
        "Keep this coloring book page. Keep the cave, doors, stairs, floor, and this same cute giant bat. "
        "Remove the pole attached to the bat. The bat is flying through the cave with wings open. "
        "No hook, no rope, no ceiling pole. Bold black outlines on white."
    ),
    "I-25": (
        "Keep this hanging cloaker and this room. Leave one tail. Remove the extra hanging leg."
    ),
}


def load_page(page_id: str) -> dict:
    spec_path = ROOT / "data" / "director" / f"{page_id}.json"
    if spec_path.exists():
        return json.loads(spec_path.read_text(encoding="utf-8"))
    catalog_path = ROOT / "data" / "director" / "tome-I-briefs.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for item in catalog.get("pages") or []:
        if item.get("page_id") == page_id:
            return dict(item)
    raise FileNotFoundError(f"No director brief for {page_id}")


def brief(page: dict) -> str:
    page_id = str(page.get("page_id") or "")
    payload = {
        "scene": "All-ages fantasy dungeon coloring book page on white paper, portrait sheet filled edge to edge",
        "style": "Bold even black felt-tip outlines, closed white shapes ready to color, flat 2D line art, same look as a printed coloring book",
        "subjects": [
            {
                "description": page.get("picture") or page.get("subject") or "fantasy creature",
                "position": "center of the page",
            }
        ],
        "background": "A complete underground room with stone ceiling, walls, and floor. Closed wooden door or the next room visible as boards and stones.",
        "lighting": "Flat even light, outlines only",
        "color_palette": ["#000000", "#FFFFFF"],
        "composition": "Full page, no caption, no title banner",
        "scale": "Weapons, doors, stairs, and furniture match the creature.",
        "mood": "playful dungeon adventure",
    }
    if page_id in HUMANOIDS:
        payload["subjects"][0]["anatomy"] = (
            "One head, one torso, two arms, two hands, two legs, two feet. "
            "A left hand and a right hand as a matching pair."
        )
    return json.dumps(payload, indent=2)


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def post_json(url: str, payload: dict, key: str) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"x-key": key, "Content-Type": "application/json", "accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def get_json(url: str, key: str) -> dict:
    request = urllib.request.Request(url, headers={"x-key": key, "accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def to_print_png(source: Path, dest: Path) -> None:
    from PIL import Image

    image = Image.open(source).convert("L")
    image = image.point(lambda pixel: 0 if pixel < INK_CUTOFF else 255)
    max_w = PRINT_WIDTH - (MARGIN * 2)
    max_h = PRINT_HEIGHT - (MARGIN * 2)
    scale = min(max_w / image.width, max_h / image.height)
    size = (round(image.width * scale), round(image.height * scale))
    image = image.resize(size, Image.Resampling.LANCZOS)
    image = image.point(lambda pixel: 0 if pixel < INK_CUTOFF else 255)
    page = Image.new("L", (PRINT_WIDTH, PRINT_HEIGHT), 255)
    left = (PRINT_WIDTH - image.width) // 2
    top = (PRINT_HEIGHT - image.height) // 2
    page.paste(image, (left, top))
    page.save(dest, format="PNG", dpi=(300, 300))


def poll_and_save(job: dict, key: str, page_id: str) -> int:
    polling = job.get("polling_url")
    if not polling:
        print(json.dumps(job), file=sys.stderr)
        return 1
    result = {}
    for _ in range(150):
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


def main() -> int:
    args = sys.argv[1:]
    if args and args[0] == "--convert":
        raw = Path(args[1])
        dest = Path(args[2]) if len(args) > 2 else raw.with_suffix(".png")
        to_print_png(raw, dest)
        print(f"Saved {dest}")
        return 0
    key = os.environ.get("BFL_API_KEY", "").strip()
    if not key:
        print("Set BFL_API_KEY first. No page was requested.", file=sys.stderr)
        return 2
    if args and args[0] == "--edit":
        page_id = args[1] if len(args) > 1 else "I-10"
        source = ROOT / "web" / "kdp-pages" / f"{page_id}-raw.jpg"
        if not source.exists():
            source = ROOT / "web" / "kdp-pages" / f"{page_id}.png"
        if not source.exists():
            print(f"No local image for {page_id} to edit.", file=sys.stderr)
            return 2
        custom = " ".join(args[2:]).strip()
        prompt = custom or EDIT_PROMPTS.get(
            page_id,
            "Keep this coloring book page and apply only the requested fix. Bold black outlines on white.",
        )
        print(f"Editing {page_id} from {source}.")
        job = post_json(
            API,
            {
                "prompt": prompt,
                "input_image": encode_image(source),
                "disable_pup": True,
                "safety_tolerance": 4,
                "output_format": "png",
            },
            key,
        )
        return poll_and_save(job, key, page_id)
    page_id = args[0] if args else "I-04"
    if page_id.upper() == "COVER":
        print("Cover is a separate color wrap.", file=sys.stderr)
        return 2
    page = load_page(page_id)
    page["page_id"] = page.get("page_id") or page_id
    prompt = brief(page)
    print(f"Requesting {page_id} at {WIDTH}x{HEIGHT}.")
    job = post_json(
        API,
        {
            "prompt": prompt,
            "width": WIDTH,
            "height": HEIGHT,
            "disable_pup": True,
            "safety_tolerance": 4,
            "output_format": "png",
        },
        key,
    )
    return poll_and_save(job, key, page_id)


if __name__ == "__main__":
    raise SystemExit(main())
