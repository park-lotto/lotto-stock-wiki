# 장면꾸미기 렌더 시간 상한이 프레임 수에 비례하는지(2026-09-17 김성현님 3연속 시간초과 재발 방지)
import subprocess
from shopping_shorts import scene_style


def _run_capture(monkeypatch, scenes):
    seen = {}
    def fake_run(cmd, **kw):
        seen["timeout"] = kw.get("timeout")
        class R: returncode = 1; stderr = "stop"
        return R()
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(scene_style, "validate_snapshot", lambda s: s)
    monkeypatch.setattr(scene_style, "context_for", lambda *a, **k: {"scenes": scenes})
    return seen


def test_timeout_scales_with_frames(tmp_path, monkeypatch):
    scenes = [{"start": i, "end": i + 1} for i in range(28)]      # 28초 = 840프레임
    seen = _run_capture(monkeypatch, scenes)
    try:
        scene_style.render_layers([], {}, tmp_path)
    except RuntimeError:
        pass
    assert seen["timeout"] == 120 + 28 * 10 + int(840 * 0.8)      # 1072초 > 옛 고정 240초


def test_timeout_floor_stays_240(tmp_path, monkeypatch):
    seen = _run_capture(monkeypatch, [{"start": 0, "end": 2}])
    try:
        scene_style.render_layers([], {}, tmp_path)
    except RuntimeError:
        pass
    assert seen["timeout"] == 240
