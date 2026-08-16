"""도우인 다운로드 라우팅·SSR 파싱 테스트 (2026-08-16).

배경: yt-dlp는 도우인에서 전멸("Fresh cookies needed") → download_any가 도우인 URL을
_download_douyin(playwright SSR 경로)으로 먼저 보내고, 실패 시 종전 yt-dlp로 폴백해야 한다.
"""
from shopping_shorts import douyin_fetch as df
from shopping_shorts import media_download as md


def test_route_douyin_first(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(md, "_download_douyin",
                        lambda url, d: called.setdefault("dy", url) and (str(tmp_path / "d.mp4"), ""))
    monkeypatch.setattr(md, "_download_ytdlp",
                        lambda url, d: (_ for _ in ()).throw(AssertionError("ytdlp 먼저 호출됨")))
    path, cap = md.download_any("https://www.douyin.com/video/7657533491349086970", str(tmp_path))
    assert "douyin.com" in called["dy"] and cap == ""


def test_route_douyin_fallback_to_ytdlp(monkeypatch, tmp_path):
    """도우인 경로 실패 시 종전 동작(yt-dlp) 유지 = 회귀 0."""
    called = {}
    monkeypatch.setattr(md, "_download_douyin",
                        lambda url, d: (_ for _ in ()).throw(RuntimeError("SSR 실패")))
    monkeypatch.setattr(md, "_download_ytdlp",
                        lambda url, d: (called.setdefault("yt", url), (str(tmp_path / "y.mp4"), ""))[1])
    path, cap = md.download_any("https://www.iesdouyin.com/share/video/123456789", str(tmp_path))
    assert "iesdouyin.com" in called["yt"]


def test_video_id_from_url():
    assert df.video_id_from_url("https://www.douyin.com/video/7657533491349086970") == "7657533491349086970"
    assert df.video_id_from_url("https://www.iesdouyin.com/share/video/123456789/") == "123456789"
    assert df.video_id_from_url("https://www.douyin.com/jingxuan?modal_id=987654321") == "987654321"
    assert df.video_id_from_url("https://example.com/") == ""


def test_best_play_url_picks_highest_res():
    import urllib.parse
    frag = ('"dataSize":100,"width":576,"height":1024,"playAddr":[{"src":"https://v3-dy-o.zjcdn.com/low"'
            '}] ... "dataSize":900,"width":1080,"height":1920,"playAddr":[{"src":"https://v5.zjcdn.com/hi"}]')
    html = urllib.parse.quote(frag)
    assert df.best_play_url(html) == "https://v5.zjcdn.com/hi"


def test_best_play_url_empty():
    assert df.best_play_url("<html>challenge</html>") == ""
