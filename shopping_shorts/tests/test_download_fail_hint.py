"""다운로드 실패를 사람 말로 번역한다 — 2026-08-19 사장님 총점검.

실측: mix_jobs 다운로드 실패 28건의 문구가 전부 기술 용어였다. 대표:
    yt-dlp 실패(rednote.com/search_result/689e…): Unsupported URL:
      https://www.rednote.com/404?source=/404/sec_PukRxsmn&redirectPath=…

★내가 처음엔 이걸 '잘못된 주소를 담은 것'으로 오판하고 담기에서 막으려 했다가
  기존 테스트(test_grab_accepts_rednote_search_result)에 걸려 되돌렸다.
  rednote.com/search_result/<id>는 **정상 담기 경로**다(한국 로그인 도메인).
  진짜 원인은 그 글이 **404로 넘겨진 것**(삭제·로그인벽)이었다.
  → 막지 말고 **왜 안 됐는지 알려주는 것**이 맞다.
"""
import pytest
from shopping_shorts.mix_pipeline import _download_fail_hint


def test_404리다이렉트는_주소탓이_아니라고_말한다():
    """실측 13건. '주소는 정상'을 반드시 밝혀야 사장님이 헛수고를 안 한다."""
    e = ("Unsupported URL: https://www.rednote.com/404?source=/404/sec_PukRxsmn"
         "?redirectPath=http%3A%2F%2Fwww.rednote.com%2Fsearch_result")
    h = _download_fail_hint(e)
    assert h and "주소는 정상" in h
    assert "지워졌거나" in h or "로그인" in h


@pytest.mark.parametrize("err,want", [
    ("from-browser option requires cookies", "쿠키"),
    ("Video unavailable", "삭제"),
    ("HTTP Error 403: Forbidden", "막았"),
    ("Read timed out", "오래"),
    ("This video is private", "비공개"),
])
def test_흔한_실패를_번역한다(err, want):
    assert want in _download_fail_hint(err)


def test_모르는_오류는_지어내지_않는다():
    """엉뚱한 안내는 없는 것만 못하다 — 모르면 빈 문자열."""
    assert _download_fail_hint("무슨 소린지 모를 오류") == ""
    assert _download_fail_hint("") == ""
    assert _download_fail_hint(None) == ""


def test_원문을_대체하지_않는다():
    """힌트는 덧붙이는 것 — 원문을 지우면 디버깅이 막힌다.

    (호출부가 f'· {u}: {hint} ({e})' 로 원문을 괄호에 남긴다)
    """
    e = "Unsupported URL: https://www.rednote.com/404?source=x"
    h = _download_fail_hint(e)
    line = f"· URL: {h} ({e})"
    assert "Unsupported URL" in line and h in line
