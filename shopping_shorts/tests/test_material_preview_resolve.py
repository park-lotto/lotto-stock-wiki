"""제작소 재료 미리보기도 그 자리에서 mp4를 해석한다(2026-07-31).

수집이 직접 mp4(play_url)를 더 이상 담지 않게 되면서(429 회피) 인스타 재료가 전부
"이 영상은 인앱 재생 소스가 없어요"로 떨어졌다. 랭킹 카드와 같은 방식으로 살린다.
"""
import pathlib

from shopping_shorts import media_download

_P = pathlib.Path(media_download.__file__).parent / "static" / "produce.html"


def test_preview_resolves_when_play_url_missing():
    html = _P.read_text(encoding="utf-8")
    assert "_fillMaterialVideo" in html and "matVideoSlot" in html
    assert "/api/media?platform=instagram" in html
    # 해석 중 표시가 있어야 "눌러도 반응 없음"이 안 된다
    assert "영상 불러오는 중" in html


def test_non_instagram_keeps_original_guidance():
    """인스타가 아닌 소스(샤오홍슈 등)는 기존 안내를 그대로 둔다 — 해석 경로가 없다."""
    html = _P.read_text(encoding="utf-8")
    assert "인앱 재생 소스가 없어요" in html
