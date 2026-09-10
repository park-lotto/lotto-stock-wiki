from pathlib import Path


def test_yt_launcher_uses_repo_relative_path_and_stable_port():
    script = (Path(__file__).parents[1] / "dashboard" / "launch_yt.ps1").read_text(encoding="utf-8")

    assert "Split-Path -Parent $PSScriptRoot" in script
    assert "http://127.0.0.1:8090/yt" in script
    assert "-WindowStyle Hidden" in script
    assert "Get-NetTCPConnection -LocalPort 8090" in script
    assert "로또의 주식" not in script
