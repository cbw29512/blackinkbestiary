from __future__ import annotations

import time
from pathlib import Path

import requests


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def health(self) -> dict:
        try:
            r = self.session.get(f"{self.base_url}/system_stats", timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            raise ComfyError(f"Cannot reach ComfyUI at {self.base_url}: {exc}") from exc

    def object_info(self) -> dict:
        r = self.session.get(f"{self.base_url}/object_info", timeout=self.timeout)
        r.raise_for_status()
        return r.json()

    def validate_nodes(self, required: set[str]) -> None:
        available = set(self.object_info().keys())
        missing = sorted(required - available)
        if missing:
            raise ComfyError(
                "ComfyUI is missing required core nodes: " + ", ".join(missing) +
                ". Update ComfyUI before running the worker."
            )

    def upload_image(self, path: Path, remote_name: str) -> str:
        with path.open("rb") as handle:
            files = {"image": (remote_name, handle, "image/png")}
            data = {"type": "input", "overwrite": "true"}
            r = self.session.post(
                f"{self.base_url}/upload/image",
                files=files,
                data=data,
                timeout=max(self.timeout, 120),
            )
        r.raise_for_status()
        payload = r.json()
        name = payload.get("name") or remote_name
        subfolder = payload.get("subfolder") or ""
        return f"{subfolder}/{name}".strip("/")

    def queue(self, graph: dict) -> str:
        r = self.session.post(
            f"{self.base_url}/prompt",
            json={"prompt": graph},
            timeout=self.timeout,
        )
        if not r.ok:
            raise ComfyError(f"ComfyUI rejected workflow: {r.status_code} {r.text[:1200]}")
        payload = r.json()
        prompt_id = payload.get("prompt_id")
        if not prompt_id:
            raise ComfyError(f"ComfyUI did not return prompt_id: {payload}")
        return prompt_id

    def wait_for_images(self, prompt_id: str, timeout_seconds: int = 600) -> list[dict]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            r = self.session.get(f"{self.base_url}/history/{prompt_id}", timeout=self.timeout)
            r.raise_for_status()
            history = r.json()
            item = history.get(prompt_id)
            if item:
                status = item.get("status") or {}
                if status.get("status_str") == "error":
                    raise ComfyError(f"ComfyUI generation failed: {status}")
                outputs = item.get("outputs") or {}
                images = []
                for node in outputs.values():
                    images.extend(node.get("images") or [])
                if images:
                    return images
            time.sleep(1.0)
        raise ComfyError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    def download_image(self, image_meta: dict, destination: Path) -> Path:
        params = {
            "filename": image_meta["filename"],
            "subfolder": image_meta.get("subfolder", ""),
            "type": image_meta.get("type", "output"),
        }
        r = self.session.get(f"{self.base_url}/view", params=params, timeout=max(self.timeout, 120))
        r.raise_for_status()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(r.content)
        return destination
