from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_powershell_scripts_are_ascii_only_for_windows_powershell_51():
    bad = {}
    for path in sorted((ROOT / "scripts").glob("*.ps1")):
        text = path.read_text(encoding="utf-8")
        chars = sorted({ch for ch in text if ord(ch) > 127})
        if chars:
            bad[str(path.relative_to(ROOT))] = [f"{ch} U+{ord(ch):04X}" for ch in chars]
    assert not bad, f"Non-ASCII PowerShell characters can break Windows PowerShell 5.1: {bad}"
