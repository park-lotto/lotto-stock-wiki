"""관제263 10-26 잇템로그 회원 실측(98 #158·#159) — 로그인 쿠키·설정 파일 탓 받기 실패면 한 번 더, 실패 이유는 그대로 남긴다.
실측: 공개 쇼츠 NHwcwJCsOps 가 yt3 계정 쿠키로는 'Video unavailable', 쿠키 없이는 정상 · 한글 홈 경로 설정 파일은 cp949 파싱 실패.
판단 주인 = origin_find.yt_retry_args(다시 할 인자) · origin_find.yt_error(이유 한 줄). 받는 길 둘(runner_ops.yt · yt_fetch.ytdlp)이 부른다."""
import subprocess
from pathlib import Path

from tools.calcopy import origin_find as OF
from tools.calcopy.engine import yt_fetch as YF
from tools.calcopy.hybrid import runner_ops as RO

UNAV = "WARNING: x\nERROR: [youtube] NHwcwJCsOps: Video unavailable\n"
CFG = "Usage: yt-dlp [OPTIONS] URL\n\nyt-dlp: error: Unable to parse \"C:/숏템/home/ytdlp\\yt-dlp\\config\": 'cp949' codec can't decode byte 0xec\n"
FF = ["--cookies-from-browser", "firefox:C:/p/2jd9gkqo.yt3", "--js-runtimes", "node"]


def test_cookie_block_retries_without_cookies(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_YOUTUBE", raising=False)
    nxt = OF.yt_retry_args(UNAV, FF)
    assert nxt is not None and "--ignore-config" in nxt
    assert "--cookies-from-browser" not in nxt and "--cookies" not in nxt
    assert "--js-runtimes" in nxt                       # JS 런타임은 그대로


def test_member_config_cookies_count_as_cookies(monkeypatch, tmp_path):
    ck = tmp_path / "cookies.txt"; ck.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setenv("YTDLP_COOKIES_YOUTUBE", str(ck))
    assert OF.yt_retry_args(UNAV, ["--js-runtimes", "node"]) == ["--ignore-config", "--js-runtimes", "node"]


def test_no_cookies_no_retry_and_other_errors_no_retry(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_YOUTUBE", raising=False)
    assert OF.yt_retry_args(UNAV, ["--js-runtimes", "node"]) is None          # 쿠키 없이 막힘 = 다시 해도 같음
    assert OF.yt_retry_args("ERROR: HTTP Error 403: Forbidden", FF) is None   # 계정 탓이 아닌 실패
    assert OF.yt_retry_args(UNAV, ["--ignore-config", "--js-runtimes", "node"]) is None   # 이미 쿠키 없이 한 번 더 했다


def test_config_parse_error_uses_cookie_file_directly(monkeypatch, tmp_path):
    ck = tmp_path / "cookies.txt"; ck.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
    monkeypatch.setenv("YTDLP_COOKIES_YOUTUBE", str(ck))
    nxt = OF.yt_retry_args(CFG, ["--js-runtimes", "node"])
    assert nxt[:3] == ["--ignore-config", "--cookies", str(ck)]
    # 그 받기도 계정 탓으로 막히면 쿠키 없이 한 번 더
    assert OF.yt_retry_args(UNAV, nxt) == ["--ignore-config", "--js-runtimes", "node"]


def test_yt_error_is_last_error_line():
    assert OF.yt_error(UNAV) == "ERROR: [youtube] NHwcwJCsOps: Video unavailable"
    assert OF.yt_error(CFG).startswith("yt-dlp: error: Unable to parse")


def _fake_run(calls, results):
    def run(cmd, **kw):
        calls.append(list(cmd))
        rc, err = results[min(len(calls), len(results)) - 1]
        return subprocess.CompletedProcess(cmd, rc, "", err)
    return run


def test_runner_yt_retries_and_keeps_reason(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_YOUTUBE", raising=False)
    monkeypatch.setattr(RO, "CACHE", "")
    monkeypatch.setattr(RO, "YT_GAP", 0)
    monkeypatch.setattr(OF, "yt_auth", lambda url: list(FF))
    calls = []
    monkeypatch.setattr(RO.subprocess, "run", _fake_run(calls, [(1, UNAV), (0, "")]))
    r = RO.yt(["-o", "x", "https://www.youtube.com/shorts/NHwcwJCsOps"])
    assert r.returncode == 0 and len(calls) == 2
    assert "--cookies-from-browser" in calls[0] and "--cookies-from-browser" not in calls[1] and "--ignore-config" in calls[1]
    # 끝까지 실패면 이유가 남는다(벤치 오류 글에 실림)
    calls.clear()
    monkeypatch.setattr(RO.subprocess, "run", _fake_run(calls, [(1, UNAV), (1, UNAV)]))
    RO.yt(["-o", "x", "https://www.youtube.com/shorts/NHwcwJCsOps"])
    assert len(calls) == 2 and "Video unavailable" in RO.yt_why()


def test_bench_error_carries_reason(monkeypatch, tmp_path):
    monkeypatch.delenv("YTDLP_COOKIES_YOUTUBE", raising=False)
    monkeypatch.setattr(RO, "CACHE", "")
    monkeypatch.setattr(RO, "YT_GAP", 0)
    monkeypatch.setattr(OF, "yt_auth", lambda url: list(FF))
    monkeypatch.setattr(RO.subprocess, "run", _fake_run([], [(1, UNAV)]))
    out = RO.c_bench(Path(tmp_path), {"url": "https://www.youtube.com/shorts/NHwcwJCsOps"})
    assert "Video unavailable" in out["error"]


def test_yt_fetch_retries(monkeypatch):
    monkeypatch.delenv("YTDLP_COOKIES_YOUTUBE", raising=False)
    monkeypatch.setattr(OF, "yt_auth", lambda url: list(FF))
    calls = []

    def once(cmd, timeout, stall_sec, watch, log):
        calls.append(cmd)
        return YF.Result(1 if len(calls) == 1 else 0, "", UNAV if len(calls) == 1 else "", 0.1)
    monkeypatch.setattr(YF, "_ytdlp_once", once)
    r = YF.ytdlp(["-f", "b", "https://www.youtube.com/watch?v=NHwcwJCsOps"])
    assert r.returncode == 0 and len(calls) == 2 and "--ignore-config" in calls[1] and "--cookies-from-browser" not in calls[1]
