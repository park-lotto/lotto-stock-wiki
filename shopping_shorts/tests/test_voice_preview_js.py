from pathlib import Path
HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")

def test_status_badge_from_cap_durs():
    # 🟢/🟡를 cap_durs 유무로 판정하는 코드가 있다
    assert "cap_durs" in HTML
    assert "🟢" in HTML and "🟡" in HTML

def test_preview_frame_and_caption_elems():
    assert 'id="vpFrame"' in HTML       # 9:16 프레임
    assert 'id="vpCap"' in HTML         # 자막 오버레이
    assert "/api/mix/beatframe/" in HTML

def test_uses_server_cap_segments_not_client_split():
    # 자막 구절은 서버 cap_segments를 쓴다(프론트에서 _caption_segments 재구현 금지)
    assert "cap_segments" in HTML

def test_heard_tracking_exists():
    assert "_vpHeard" in HTML           # 들어본 비트 기록(게이트용)
