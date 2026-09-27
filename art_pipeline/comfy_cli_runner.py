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


def _parse_machine_output(text: str):
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        events = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if not events:
            return {"raw": text}
        final = events[-1]
        if isinstance(final, dict):
            final = dict(final)
            final.setdefault("_events", events)
            return final
        return {"data": final, "_events": events}


class ComfyCli:
    """Thin wrapper around the official Comfy-Org CLI.

    This is the preferred orchestration layer. The direct REST client remains
    available as a fallback and for lightweight health/status checks.
    """

    def __init__(self, command: str | None = None):
        self.command = command or find_comfy_cli()
        if not self.command:
            raise ComfyCliError("comfy-cli is not installed; run PREPARE_LOCAL_AI.bat")

    def run(
        self,
        *args: str,
        timeout: float = 120.0,
        expect_json: bool = False,
        where: str | None = None,
    ):
        command = [self.command]
        if expect_json:
            command.append("--json")
        if where:
            command.extend(["--where", where])
        command.extend(args)
        try:
            result = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ComfyCliError(
                f"Command exceeded local process timeout after {timeout:.0f}s: "
                f"{' '.join(command)}"
            ) from exc
        if result.returncode != 0:
            raise ComfyCliError(
                f"Command failed ({result.returncode}): {' '.join(command)}\n"
                f"{(result.stderr or result.stdout).strip()}"
            )
        text = (result.stdout or "").strip()
        if expect_json:
            return _parse_machine_output(text)
        return text

    def version(self) -> str:
        return self.run("--version")

    def system_stats(self):
        return self.run("system-stats", expect_json=True, where="local")

    def fetch_template(self, name: str, destination: Path):
        destination.parent.mkdir(parents=True, exist_ok=True)
        return self.run(
            "templates", "fetch", name,
            "--out", str(destination),
            expect_json=True,
            where="local",
        )

    def workflow_slots(self, workflow: Path):
        return self.run("workflow", "slots", str(workflow), expect_json=True, where="local")

    def validate_workflow(self, workflow: Path):
        return self.run(
            "workflow", "validate", "--workflow", str(workflow),
            expect_json=True,
            where="local",
        )

    def set_workflow_slots(self, workflow: Path, overrides: dict):
        args = ["workflow", "set-slot", str(workflow)]
        for address, value in overrides.items():
            args.append(f"{address}={json.dumps(value, ensure_ascii=False)}")
        return self.run(*args, expect_json=True, where="local")

    def run_workflow(
        self,
        workflow: Path,
        *,
        timeout: float = 600.0,
        event_timeout: int = 600,
    ):
        # comfy-cli's --timeout is a per-event silence deadline, not a total
        # workflow deadline. Diffusion steps can legitimately emit no websocket
        # event for more than the CLI's 120-second default, especially on local
        # GPU workloads. Keep the outer subprocess timeout slightly longer so
        # the CLI can report its own structured timeout first.
        event_timeout = max(120, int(event_timeout))
        process_timeout = max(float(timeout), float(event_timeout + 30))
        return self.run(
            "run", "--workflow", str(workflow), "--wait",
            "--host", "127.0.0.1", "--port", "8188",
            "--timeout", str(event_timeout),
            expect_json=True,
            where="local",
            timeout=process_timeout,
        )

    def template_check(self):
        return self.run("templates", "check", expect_json=True, where="local")

    def run_template(self, name: str, params: dict, *, timeout: float = 300.0):
        args = ["run-template", name, "--host", "127.0.0.1", "--port", "8188"]
        for key, value in params.items():
            encoded = json.dumps(value, ensure_ascii=False)
            args.append(f"--param={key}={encoded}")
        return self.run(*args, expect_json=True, where="local", timeout=timeout)
