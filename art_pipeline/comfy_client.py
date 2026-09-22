from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path


class ComfyError(RuntimeError):
    pass


class ComfyClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8188", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _request(self, path: str, *, method="GET", payload=None) -> bytes:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ComfyError(f"Cannot reach ComfyUI at {self.base_url}: {exc}") from exc

    def health(self) -> dict:
        raw = self._request("/system_stats")
        return json.loads(raw.decode("utf-8"))


    def upload_image(
        self,
        source: Path,
        *,
        subfolder: str = "blackink",
        overwrite: bool = True,
    ) -> dict:
        """Upload a PNG/JPEG into ComfyUI's input folder using its stable multipart endpoint."""
        source = Path(source)
        if not source.exists() or not source.is_file():
            raise ComfyError(f"Image upload source does not exist: {source}")

        boundary = f"----BlackInk{uuid.uuid4().hex}"
        crlf = b"\r\n"
        body = bytearray()

        def add_field(name: str, value: str) -> None:
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(value.encode("utf-8"))
            body.extend(crlf)

        add_field("type", "input")
        add_field("subfolder", subfolder)
        add_field("overwrite", "true" if overwrite else "false")

        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            (
                f'Content-Disposition: form-data; name="image"; filename="{source.name}"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode()
        )
        body.extend(source.read_bytes())
        body.extend(crlf)
        body.extend(f"--{boundary}--\r\n".encode())

        request = urllib.request.Request(
            f"{self.base_url}/upload/image",
            data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            raise ComfyError(f"Could not upload image to ComfyUI: {exc}") from exc

        name = str(payload.get("name") or "").strip()
        if not name:
            raise ComfyError(f"ComfyUI upload returned no image name: {payload}")
        folder = str(payload.get("subfolder") or "").strip("/")
        payload["load_image_name"] = f"{folder}/{name}" if folder else name
        return payload

    def queue_prompt(self, workflow_api: dict, client_id: str | None = None) -> str:
        payload = {"prompt": workflow_api}
        if client_id:
            payload["client_id"] = client_id
        raw = self._request("/prompt", method="POST", payload=payload)
        response = json.loads(raw.decode("utf-8"))
        prompt_id = response.get("prompt_id")
        if not prompt_id:
            raise ComfyError(f"ComfyUI did not return prompt_id: {response}")
        return prompt_id

    def history(self, prompt_id: str) -> dict:
        raw = self._request(f"/history/{urllib.parse.quote(prompt_id)}")
        return json.loads(raw.decode("utf-8"))

    def wait(self, prompt_id: str, *, timeout_seconds: float = 300, poll_seconds: float = 1.0) -> dict:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self.history(prompt_id)
            if prompt_id in result:
                return result[prompt_id]
            time.sleep(poll_seconds)
        raise ComfyError(f"Timed out waiting for ComfyUI prompt {prompt_id}")

    def output_images(self, history_entry: dict) -> list[dict]:
        images = []
        for node_id, node_output in (history_entry.get("outputs") or {}).items():
            for image in node_output.get("images", []):
                item = dict(image)
                item["node_id"] = node_id
                images.append(item)
        return images

    def download_image(self, image: dict, destination: Path) -> Path:
        query = urllib.parse.urlencode({
            "filename": image["filename"],
            "subfolder": image.get("subfolder", ""),
            "type": image.get("type", "output"),
        })
        raw = self._request(f"/view?{query}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        return destination
