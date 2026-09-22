from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_continue_after_models_launcher_exists_and_avoids_duplicate_install():
    bat = (ROOT / "CONTINUE_AFTER_MODELS.bat").read_text(encoding="utf-8")
    ps = (ROOT / "scripts" / "continue_after_models.ps1").read_text(encoding="utf-8")

    assert "continue_after_models.ps1" in bat
    assert "prepare_local_ai.ps1" in ps
    assert "blackink_doctor.py" in ps
    assert "validate_local_templates.py" in ps
    assert "smoke_test_i01.py" in ps
    assert "install_blackink_ai.ps1" not in ps
