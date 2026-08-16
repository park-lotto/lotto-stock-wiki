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


def test_timeout_says_why(monkeypatch, tmp_path):
    """★시간 초과는 **이유를 남긴다** — 조용히 죽으면 화면이 영원히 '분석 중'이다.

    2026-08-16 실측: 45초짜리 도우인 영상은 다운로드+변환에 108초가 걸린다(20초짜리는 35초).
    옛 제한(180초)에 긴 영상이 걸려 죽었는데 오류 기록이 없어, 사장님 화면엔
    '분석 중(3번째 시도)'만 떠 있고 실제로는 아무것도 돌지 않았다.
    """
    import subprocess
    from shopping_shorts import media_download as md

    def boom(*a, **k):
        raise subprocess.TimeoutExpired(cmd="x", timeout=600)

    monkeypatch.setattr(md.subprocess, "run", boom)
    try:
        md._download_douyin("https://www.douyin.com/video/1", tmp_path)
    except RuntimeError as e:
        assert "시간 초과" in str(e) and "600" in str(e)
    else:
        raise AssertionError("시간 초과가 조용히 지나갔다")


def test_timeout_is_generous_enough_for_long_clips():
    """제한 시간이 실측(108초)보다 넉넉해야 한다 — 짧은 영상 기준으로 잡으면 긴 것만 죽는다."""
    import inspect
    from shopping_shorts import media_download as md
    sig = inspect.signature(md._download_douyin)
    assert sig.parameters["timeout"].default >= 420


def test_only_two_at_once(monkeypatch, tmp_path):
    """★도우인은 서버 전체에서 동시 2개까지(2026-08-16 사장님 지시).

    도우인만 영상 하나당 헤드리스 크롬+ffmpeg를 돌린다. 서버는 4코어인데 자동적재는
    고객마다 3개씩 던지므로, 고객 5명이 동시에 담으면 크롬 15개가 뜬다 —
    다 같이 기어가다 시간 초과로 **전부** 실패한다(빨리 하려다 하나도 못 얻는다).
    """
    from shopping_shorts import media_download as md

    started, release = [], []

    def slow(url, dest_dir, timeout):
        started.append(url)
        return "x.mp4", ""

    monkeypatch.setattr(md, "_download_douyin_inner", slow)
    # 2개는 자리를 차지한 채로 둔다
    assert md._DOUYIN_SLOTS.acquire(blocking=False)
    assert md._DOUYIN_SLOTS.acquire(blocking=False)
    try:
        try:
            md._download_douyin("https://www.douyin.com/video/3", tmp_path)
        except md.DouyinBusy as e:
            assert "2개" in str(e), "왜 기다리는지 사람 말로 알려야 한다"
        else:
            raise AssertionError("3번째가 통과했다 — 상한이 안 걸린다")
        assert not started, "자리가 없으면 아예 시작하지 않아야 한다"
    finally:
        md._DOUYIN_SLOTS.release()
        md._DOUYIN_SLOTS.release()


def test_busy_is_not_failure(tmp_path):
    """대기는 실패와 다르다 — 자동적재가 시도 횟수를 깎으면 안 된다."""
    import pathlib as _p
    src = (_p.Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    i = src.index("except DouyinBusy")
    win = src[i:i + 400]
    assert '"busy"' in win
    assert "rollback_latch" in win, "래치를 돌려주지 않으면 결국 영영 못 받는다"


def test_busy_passes_through_download_any(monkeypatch, tmp_path):
    """★DouyinBusy는 download_any를 **그대로 통과**해야 한다(2026-08-16 리뷰에서 발견).

    폴백 except가 DouyinBusy까지 삼키면 yt-dlp로 떨어지는데, 도우인은 yt-dlp가
    전멸이라 '자리 없음'이 확정 실패로 둔갑한다 — autoload의 busy 처리(래치 롤백·
    화면 '순서 대기')가 통째로 죽고, 3번 만에 그 영상은 영구 래치된다.
    """
    from shopping_shorts import media_download as md

    def busy(url, dest_dir):
        raise md.DouyinBusy("자리 없음")

    monkeypatch.setattr(md, "_download_douyin", busy)
    monkeypatch.setattr(md, "_download_ytdlp",
                        lambda url, d: (_ for _ in ()).throw(
                            AssertionError("busy가 yt-dlp로 새면 안 된다")))
    try:
        md.download_any("https://www.douyin.com/video/7", str(tmp_path))
    except md.DouyinBusy:
        pass
    else:
        raise AssertionError("DouyinBusy가 삼켜졌다")
