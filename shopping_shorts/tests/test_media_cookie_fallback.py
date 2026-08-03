"""만료 세션 쿠키가 재생을 통째로 죽이던 것 → 무쿠키 재시도 (2026-08-04 실사고).

증상: 레퍼런스랭킹·히트작에서 썸네일(미리보기)을 누르면 인스타로 새탭이 떴다.
원인: 인스타 세션(07-30 발급)이 만료돼 `--cookies`를 붙인 yt-dlp가 **HTTP 404**를 받는다.
      같은 릴스가 **쿠키 없이는 멀쩡히 열린다**.
      라이브 실측 10건: 쿠키 **0/10** 성공 · 무쿠키 **8/10** 성공.
      해석이 실패하면 프런트가 `window.open(원본)`으로 폴백 → 전부 인스타로 튄 것.
판정: 쿠키는 비공개·제한 게시물을 여는 '추가 수단'이지 필수가 아니다. 실패 시 무쿠키가
      항상 더 나은 하한선이므로 **쿠키 실패 → 무쿠키 재시도**를 넣는다(패치 후 8/10 복구).

여기서 못 박는 것:
  1. 쿠키로 성공하면 재시도하지 않는다(비용 0, 세션이 살아 있을 때 회귀 없음).
  2. 쿠키로 실패하면 **쿠키 없이** 한 번 더 부른다 — 그리고 그 결과를 돌려준다.
  3. 애초에 쿠키가 없으면 재시도하지 않는다(같은 호출 두 번 = 낭비).
  4. 둘 다 실패면 "" (프런트가 원본 폴백을 타는 계약 유지).
"""
import pytest

from shopping_shorts import media_download


class _R:
    def __init__(self, rc, out=""):
        self.returncode = rc
        self.stdout = out


@pytest.fixture
def calls(monkeypatch):
    """subprocess.run을 잡아 '쿠키를 넣고 불렀는지'를 호출마다 기록한다."""
    seen = []

    def _mk(results):
        def fake_run(cmd, **kw):
            has_cookie = "--cookies" in cmd
            seen.append(has_cookie)
            return results[len(seen) - 1]
        monkeypatch.setattr(media_download.subprocess, "run", fake_run)
        return seen
    return _mk


@pytest.fixture(autouse=True)
def _force_cookies(monkeypatch):
    """쿠키파일이 있는 서버 상태를 재현(로컬엔 파일이 없어 기본은 무쿠키다)."""
    monkeypatch.setattr(media_download, "_cookies_arg",
                        lambda url: ["--cookies", "/fake/ig.txt"])
    monkeypatch.setattr(media_download, "_proxy_arg", lambda url: [])


def test_cookie_success_does_not_retry(calls):
    """세션이 살아 있으면 한 번에 끝난다 — 재시도가 붙어도 비용이 늘지 않아야 한다."""
    seen = calls([_R(0, "https://cdn/ok.mp4\n")])
    url = media_download.resolve_media_url("instagram", "AAA")
    assert url == "https://cdn/ok.mp4"
    assert seen == [True], "쿠키 성공인데 재시도가 돌았다"


def test_cookie_failure_retries_without_cookies(calls):
    """★핵심: 쿠키가 404를 받으면 무쿠키로 다시 → 그게 살아난 8/10의 경로다."""
    seen = calls([_R(1, ""), _R(0, "https://cdn/rescued.mp4\n")])
    url = media_download.resolve_media_url("instagram", "BBB")
    assert url == "https://cdn/rescued.mp4"
    assert seen == [True, False], "두 번째 호출이 무쿠키가 아니다"


def test_cookie_empty_stdout_also_retries(calls):
    """rc=0인데 stdout이 빈 경우(=해석 실패)도 실패로 보고 재시도해야 한다."""
    seen = calls([_R(0, "   \n"), _R(0, "https://cdn/rescued.mp4\n")])
    assert media_download.resolve_media_url("instagram", "CCC") == "https://cdn/rescued.mp4"
    assert seen == [True, False]


def test_both_fail_returns_empty(calls):
    """진짜 못 여는 게시물(비공개·삭제)은 ""를 준다 — 프런트 원본폴백 계약 유지."""
    seen = calls([_R(1, ""), _R(1, "")])
    assert media_download.resolve_media_url("instagram", "DDD") == ""
    assert seen == [True, False]


def test_no_cookies_configured_does_not_double_call(monkeypatch, calls):
    """쿠키가 애초에 없으면 재시도는 같은 호출 반복일 뿐 — 한 번만 부른다."""
    monkeypatch.setattr(media_download, "_cookies_arg", lambda url: [])
    seen = calls([_R(1, "")])
    assert media_download.resolve_media_url("instagram", "EEE") == ""
    assert seen == [False], "쿠키가 없는데 두 번 불렀다"


def test_timeout_exception_is_swallowed(monkeypatch):
    """yt-dlp가 타임아웃으로 터져도 500이 아니라 ""여야 한다(선존재 계약).

    ⚠️monkeypatch로 갈아야 한다 — 모듈 전역을 직접 대입하면 복원이 안 돼 뒤 테스트가 오염된다."""
    def boom(cmd, **kw):
        raise OSError("timeout")
    monkeypatch.setattr(media_download.subprocess, "run", boom)
    assert media_download.resolve_media_url("instagram", "FFF") == ""


def test_youtube_also_gets_fallback(calls):
    """유튜브 쿠키도 만료되면 같은 함정에 빠진다 — 플랫폼 무관하게 폴백이 돈다."""
    seen = calls([_R(1, ""), _R(0, "https://cdn/yt.mp4\n")])
    assert media_download.resolve_media_url("youtube", "abc123") == "https://cdn/yt.mp4"
    assert seen == [True, False]
