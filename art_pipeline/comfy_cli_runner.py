from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ComfyCliError(RuntimeError):
    pass


def find_comfy_cli() -> str | None:
    local = ROOT / ".blackink-tools" / "Scripts" / "comfy.exe"
    if local.exists():
        return str(local)
    return shutil.which("comfy")


class ComfyCli:
    """Thin wrapper around the official Comfy-Org CLI.

    This is the preferred orchestration layer. The direct REST client remains
    available as a fallback and for lightweight health/status checks.
    """

    def __init__(self, command: str | None = None):
        self.command = command or find_comfy_cli()
        if not self.command:
            raise ComfyCliError("comfy-cli is not installed; run PREPARE_LOCAL_AI.bat")

    def run(self, *args: str, timeout: float = 120.0, expect_json: bool = False):
        command = [self.command, *args]
        if expect_json:
            command.append("--json")
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise ComfyCliError(
                f"Command failed ({result.returncode}): {' '.join(command)}\n"
                f"{(result.stderr or result.stdout).strip()}"
            )
        text = (result.stdout or "").strip()
        if expect_json and text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # Some versions emit NDJSON/envelope lines. Preserve them for
                # the caller rather than guessing at the schema.
                return {"raw": text}
        return text

    def version(self) -> str:
        return self.run("--version")

    def system_stats(self):
        return self.run("system-stats", "--where", "local", expect_json=True)

    def fetch_template(self, name: str, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        return self.run(
            "templates", "fetch", name,
            "--out", str(destination),
            "--where", "local",
            expect_json=True,
        )

    def workflow_slots(self, workflow: Path):
        return self.run("workflow", "slots", str(workflow), expect_json=True)

    def validate_workflow(self, workflow: Path):
        return self.run(
            "validate", "--workflow", str(workflow),
            "--where", "local",
            expect_json=True,
        )

    def template_check(self):
        return self.run("templates", "check", "--where", "local", expect_json=True)
