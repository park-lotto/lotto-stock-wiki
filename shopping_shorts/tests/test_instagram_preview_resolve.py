"""랭킹 카드 인스타 미리보기 복구(2026-07-30).

수집이 직접 mp4(video_versions)를 더 이상 담지 않으면서(429 회피) 썸네일 클릭 재생이
사라졌다 — 카드가 `video_url`이 있어야 onclick을 붙이는데 그 값이 빈 문자열이 됐다.
이제 누른 순간 /api/media가 mp4를 해석한다.
"""
import pathlib

from shopping_shorts import media_download

_INDEX = pathlib.Path(media_download.__file__).parent / "static" / "index.html"


def test_resolve_media_url_supports_instagram(monkeypatch):
    seen = {}

    class _R:
        returncode = 0
        stdout = "https://cdn.example/reel.mp4\n"

    def fake_run(cmd, **kw):
        seen["page"] = cmd[-1]
        return _R()

    monkeypatch.setattr(media_download.subprocess, "run", fake_run)
    url = media_download.resolve_media_url("instagram", "DbZPKc2TKHC")
    assert url == "https://cdn.example/reel.mp4"
    assert seen["page"] == "https://www.instagram.com/reel/DbZPKc2TKHC/"


def test_unknown_platform_still_returns_empty():
    assert media_download.resolve_media_url("myspace", "x") == ""


def test_card_wires_instagram_click():
    """video_url이 비어도 인스타 카드에 재생 클릭이 붙어야 한다(그게 사라진 게 증상)."""
    html = _INDEX.read_text(encoding="utf-8")
    assert "playInstagram(this," in html, "인스타 썸네일 클릭 배선이 없다"
    assert "function playInstagram" in html
    # 유튜브·틱톡 배선은 그대로 남아 있어야 한다
    assert "playYoutube(this," in html and "playTiktok(this," in html
