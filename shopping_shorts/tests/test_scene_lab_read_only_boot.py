"""장면 화면 재진입은 읽기여야 한다 — 여는 것 자체가 최신 MIX를 덮으면 안 된다."""
from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "static" / "scene_lab.html").read_text(encoding="utf-8")


def _between(start, end):
    return HTML.split(start, 1)[1].split(end, 1)[0]


def test_boot_prefers_server_layout_without_timestamp_guess():
    boot = _between("async function boot(){", "function autoOpenRoll()")
    assert "if (hasServerEdit())" in boot
    assert "if (serverEditIsNewer())" not in boot


def test_boot_and_identical_repaint_do_not_save():
    save = _between("function saveWork(){", "// ★[서버에 반영]을")
    guard = "if (_booting || !cur || cur === _lastPersistedWork) return;"
    assert guard in save
    assert save.index(guard) < save.index("localStorage.setItem") < save.index("autoApply()")
    boot = _between("async function boot(){", "function autoOpenRoll()")
    assert boot.index("_lastPersistedWork = JSON.stringify(snapWork())") < boot.index("_booting = false")


def test_client_sends_and_advances_server_revision():
    apply = _between("async function applyServer(opt){", "async function revertServer()")
    assert "base_revision: SCENE_REV" in apply
    assert "SCENE_REV = j.revision" in apply
    assert "_sceneConflict = true" in apply


def test_conflict_blocks_preview_render_instead_of_rendering_different_server_state():
    ask = _between("async function _askRender(){", "function _cfEnable(on)")
    assert "if (_sceneConflict)" in ask
    assert ask.index("if (_sceneConflict)") < ask.index("startPreview")
