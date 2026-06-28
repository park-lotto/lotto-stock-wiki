# tests/studio/test_studio_html.py
from pathlib import Path

HTML = Path("dashboard/studio.html")

def test_html_has_core_structure():
    assert HTML.exists()
    s = HTML.read_text(encoding="utf-8")
    assert "작업목록" in s                       # 좌측 갤러리 제목
    assert "딸깍" in s                            # 생성 버튼(딸깍)
    assert "탑픽" in s                            # 탑픽 산출 단계/버튼
    assert "/studio/generate" in s               # SSE 호출
    assert "/studio/gallery" in s                # 갤러리 로드
    assert "EventSource" in s or "ReadableStream" in s or "getReader" in s  # 스트림 처리
    assert "Instrument Serif" in s               # 디자인 토큰
