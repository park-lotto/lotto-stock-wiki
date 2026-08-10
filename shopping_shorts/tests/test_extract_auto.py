"""추출 디스패처 extract_auto (2026-07-29): 플래그(frame_extract_enabled)면 B1 프레임추출,
아니면 기존 영상추출. 1단계 전 호출부가 이걸 써서 한 플래그로 전 경로 B1 전환.
설계: docs/superpowers/specs/2026-07-29-추출속도-3종묶음-design.md
"""
from shopping_shorts import script_extract as se


def test_extract_auto_classic_when_flag_off():
    calls = {}
    out = se.extract_auto("v.mp4", "s1", caption="c", use_frames=False,
                          _frames_fn=lambda *a, **k: calls.update(frames=True) or {"segments": [1]},
                          _classic_fn=lambda *a, **k: calls.update(classic=True) or {"segments": [1]})
    assert "classic" in calls and "frames" not in calls
    assert out == {"segments": [1]}


def test_extract_auto_frames_when_flag_on():
    calls = {}
    out = se.extract_auto("v.mp4", "s1", use_frames=True,
                          _frames_fn=lambda *a, **k: calls.update(frames=True) or {"segments": [1, 2]},
                          _classic_fn=lambda *a, **k: calls.update(classic=True) or {"segments": []})
    assert "frames" in calls and "classic" not in calls
    assert out == {"segments": [1, 2]}


def test_extract_auto_frames_empty_falls_back_to_classic():
    """B1이 빈 결과(컷 감지 실패 등)면 기존 추출로 폴백 — 빈 대본 방지."""
    calls = {}
    out = se.extract_auto("v.mp4", "s1", use_frames=True,
                          _frames_fn=lambda *a, **k: {"segments": []},
                          _classic_fn=lambda *a, **k: calls.update(classic=True) or {"segments": [9]})
    assert "classic" in calls
    assert out == {"segments": [9]}
