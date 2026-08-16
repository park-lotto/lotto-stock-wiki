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


def test_normalize_keeps_safe_file_untouched(monkeypatch, tmp_path):
    """이미 h264·1920 이하면 변환하지 않는다(쓸데없이 시간·화질을 버리지 않게)."""
    from shopping_shorts import douyin_fetch as df
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x" * 20000)
    calls = []

    class R:
        stdout = "h264,1920\n"

    def fake_run(cmd, **kw):
        calls.append(cmd[0])
        if cmd[0] == "ffprobe":
            return R()
        raise AssertionError("변환이 돌면 안 된다")

    monkeypatch.setattr(df.subprocess, "run", fake_run)
    assert df._normalize(src) == str(src)
    assert calls == ["ffprobe"]


def test_normalize_converts_hevc(monkeypatch, tmp_path):
    """★도우인 최고화질은 hevc 2160x2880이었다(실측). 그대로 두면 크롬이
    재생 못 할 수 있고(고객 환경마다 갈림) 편집 화면이 무거워진다 → h264로 맞춘다."""
    from shopping_shorts import douyin_fetch as df
    src = tmp_path / "b.mp4"
    src.write_bytes(b"x" * 20000)

    class R:
        stdout = "hevc,2880\n"

    def fake_run(cmd, **kw):
        if cmd[0] == "ffprobe":
            return R()
        (tmp_path / "b_h264.mp4").write_bytes(b"y" * 30000)   # ffmpeg가 만든 셈
        return R()

    monkeypatch.setattr(df.subprocess, "run", fake_run)
    out = df._normalize(src)
    assert out.endswith("_h264.mp4")
    assert not src.exists(), "원본은 지워 디스크를 아낀다"


def test_normalize_falls_back_when_ffmpeg_fails(monkeypatch, tmp_path):
    """변환이 깨져도 **받아 온 원본은 잃지 않는다** — 못 쓰는 것보단 낫다."""
    from shopping_shorts import douyin_fetch as df
    src = tmp_path / "c.mp4"
    src.write_bytes(b"x" * 20000)

    class R:
        stdout = "hevc,2880\n"

    def fake_run(cmd, **kw):
        if cmd[0] == "ffprobe":
            return R()
        raise RuntimeError("ffmpeg 없음")

    monkeypatch.setattr(df.subprocess, "run", fake_run)
    assert df._normalize(src) == str(src)
    assert src.exists()
