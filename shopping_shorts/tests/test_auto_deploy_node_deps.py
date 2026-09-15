from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "auto_deploy.sh"


def test_node_lockfile_change_runs_reproducible_install():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "package.json|package-lock.json" in source
    assert "npm ci --no-audit --no-fund" in source

