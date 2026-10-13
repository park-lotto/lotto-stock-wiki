"""관제 186: 소리만 바꿔도 작업 전체가 잠겨 1단계로 떨어지던 것.

효과음·배경음 변경은 preview_status 를 '' 로 비운다(다시 만들어야 함). 그 값을 1단계 게이트로도 써서
완성한 작업이 통째로 잠겼다(2026-10-12 이성택님 '아이스 칠링볼'). 게이트 통과는 서버
_preview_gate_passed 한 곳이 정하고, 화면 canGoNext 는 그 값을 받는다.
"""
import pathlib
import re

from shopping_shorts import app as A

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_cleared_preview_with_file_still_passes_gate(tmp_path):
    f = tmp_path / "preview.mp4"
    f.write_bytes(b"x")
    assert A._preview_gate_passed({"preview_status": "", "preview_path": str(f)}) is True


def test_never_previewed_job_is_still_locked(tmp_path):
    assert A._preview_gate_passed({"preview_status": None, "preview_path": None}) is False
    assert A._preview_gate_passed({"preview_status": "", "preview_path": str(tmp_path / "없음.mp4")}) is False
    assert A._preview_gate_passed({"preview_status": "rendering"}) is False


def test_ready_and_failed_pass():
    assert A._preview_gate_passed({"preview_status": "ready"}) is True
    assert A._preview_gate_passed({"preview_status": "failed"}) is True


def test_screen_uses_server_flag():
    body = HTML[HTML.index("function canGoNext(){"):HTML.index("function stepLocked(i){")]
    assert "PREVIEW_GATE_PASSED" in body
    assert "s.preview_gate_passed" in HTML


def test_every_preview_reset_also_resets_gate_flag():
    """새 job·재매칭으로 미리보기 상태를 지우는 곳마다 통과값도 지운다 — 안 그러면 옛 통과를 물려받아 유료 자막제거 우회."""
    resets = [l for l in re.findall(r"[^\n]*PREVIEW_STATUS\s*=\s*null;[^\n]*", HTML) if "let PREVIEW_STATUS" not in l]
    assert resets, "초기화 지점을 못 찾았다 — 검사가 아무것도 안 잰다"
    for line in resets:
        assert re.search(r"PREVIEW_GATE_PASSED\s*=\s*false", line), line
