from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "art_pipeline"))

from human_review import append_human_decision, current_canary_items, current_image_path
from page_contract import resolve_page_spec
from studio_config import active_book_paths


def load_page_contexts():
    manifest = json.loads(
        active_book_paths(ROOT)["manifest"].read_text(encoding="utf-8")
    )
    return {
        str(page.get("page_id") or ""): resolve_page_spec(page, ROOT)
        for page in manifest.get("pages", [])
        if page.get("page_id")
    }


class ReviewApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.items = current_canary_items(ROOT)
        self.page_contexts = load_page_contexts()
        self.index = 0
        self.photo = None
        root.title("Black Ink Bestiary - Human Canary Review")
        root.geometry("1040x1080")

        self.heading = ttk.Label(root, font=("Segoe UI", 14, "bold"))
        self.heading.pack(pady=(10, 4))
        self.image_label = ttk.Label(root)
        self.image_label.pack(padx=12, pady=8)

        self.context = tk.Text(root, height=8, wrap="word")
        self.context.pack(fill="x", padx=18, pady=(0, 8))
        self.context.configure(state="disabled")

        form = ttk.Frame(root)
        form.pack(fill="x", padx=18)
        ttk.Label(form, text="Reject stage:").grid(row=0, column=0, sticky="w")
        self.stage = ttk.Combobox(
            form,
            state="readonly",
            values=("identity", "environment", "action", "completeness", "quality"),
            width=18,
        )
        self.stage.grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.stage.set("quality")
        ttk.Label(form, text="Reason (required for reject):").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 2)
        )
        self.notes = tk.Text(form, height=5, wrap="word")
        self.notes.grid(row=2, column=0, columnspan=3, sticky="ew")
        form.columnconfigure(2, weight=1)

        buttons = ttk.Frame(root)
        buttons.pack(pady=12)
        ttk.Button(buttons, text="Approve", command=self.approve).pack(side="left", padx=6)
        ttk.Button(buttons, text="Reject + Regenerate", command=self.reject).pack(side="left", padx=6)
        ttk.Button(buttons, text="Skip for now", command=self.next_item).pack(side="left", padx=6)
        self.status = ttk.Label(root)
        self.status.pack(pady=(0, 10))
        self.show_item()

    def show_item(self):
        if not self.items or self.index >= len(self.items):
            self.heading.config(text="No more current canary images awaiting your review.")
            self.image_label.config(image="")
            self.context.configure(state="normal")
            self.context.delete("1.0", "end")
            self.context.configure(state="disabled")
            self.status.config(text="Close this window. Rejected pages will regenerate on the next autopilot cycle.")
            return
        item = self.items[self.index]
        page_id = str(item.get("page_id") or "")
        page = self.page_contexts.get(page_id) or {}
        monster = str(item.get("monster_name") or page.get("monster_name") or "")
        self.heading.config(text=f"{self.index + 1}/{len(self.items)} - {page_id} - {monster}")
        path = current_image_path(ROOT, item)
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((780, 650))
            self.photo = ImageTk.PhotoImage(image)
        self.image_label.config(image=self.photo)

        advisory = item.get("visual_review") or {}
        defects = [str(x).strip() for x in advisory.get("defects") or [] if str(x).strip()]
        context_lines = [
            f"HABITAT: {page.get('habitat', '')}",
            f"STORY MOMENT: {page.get('moment', '')}",
            "MUST INCLUDE: " + "; ".join(str(x) for x in page.get("must_include") or []),
            (
                "LOCAL AI ADVISORY (not authoritative): "
                + (f"stage={advisory.get('stage')} score={advisory.get('score')} defects=" + "; ".join(defects)
                   if advisory else "no advisory verdict")
            ),
        ]
        self.context.configure(state="normal")
        self.context.delete("1.0", "end")
        self.context.insert("1.0", "\n".join(context_lines))
        self.context.configure(state="disabled")

        local_stage = str(advisory.get("stage") or "").lower()
        if local_stage in {"identity", "environment", "action", "completeness", "quality"}:
            self.stage.set(local_stage)
        self.notes.delete("1.0", "end")
        self.status.config(text="Approve only if this exact image is premium-production ready.")

    def record(self, decision: str):
        if not self.items or self.index >= len(self.items):
            return
        item = self.items[self.index]
        notes = self.notes.get("1.0", "end").strip()
        try:
            row = append_human_decision(
                ROOT,
                item,
                decision=decision,
                notes=notes,
                stage=self.stage.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Review not saved", str(exc))
            return

        subprocess.run([sys.executable, str(ROOT / "scripts" / "apply_review_decisions.py")], cwd=ROOT, check=True)
        subprocess.run([sys.executable, str(ROOT / "scripts" / "publish_review_previews.py")], cwd=ROOT, check=True)
        self.status.config(text=f"Saved {row['decision']} for {row['review_id']}")
        self.index += 1
        self.show_item()

    def approve(self):
        self.record("approve")

    def reject(self):
        self.record("reject")

    def next_item(self):
        if self.items and self.index < len(self.items):
            self.index += 1
            self.show_item()


def main() -> int:
    root = tk.Tk()
    ReviewApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
