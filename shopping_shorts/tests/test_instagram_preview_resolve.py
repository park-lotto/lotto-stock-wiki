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


def test_discover_page_also_wires_instagram_preview():
    """신규채널 픽업(discover.html)은 별도 파일이라 배선이 빠져 있었다(2026-07-31 제보)."""
    d = (pathlib.Path(media_download.__file__).parent / "static" / "discover.html").read_text(encoding="utf-8")
    assert "function playInstagram" in d and "playInstagram(this," in d


def test_both_pages_show_loading_while_resolving():
    """해석에 수 초~수십 초 걸린다 — 표시가 없으면 '눌러도 반응 없음'으로 보인다."""
    for name in ("index.html", "discover.html"):
        html = (pathlib.Path(media_download.__file__).parent / "static" / name).read_text(encoding="utf-8")
        assert "영상 불러오는 중" in html, f"{name}에 로딩 표시가 없다"


def test_play_badge_shown_for_instagram_cards():
    """배지(▶)가 없으면 눌러도 되는 곳인지 몰라 '안 된다'로 보인다(2026-07-31 제보).
    배선 조건과 배지 조건이 어긋나 있었다 — 클릭은 붙는데 표시만 없었다."""
    idx = (pathlib.Path(media_download.__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
    dis = (pathlib.Path(media_download.__file__).parent / "static" / "discover.html").read_text(encoding="utf-8")
    assert "(i.platform||PLATFORM)==='instagram')?'<span class=\"play-badge\">" in idx
    assert "(i.video_url||i.shortcode)?'<span class=\"play-badge\">" in dis
