"""예열 래치 — 일시 실패는 재시도 기회를 태우지 않는다(2026-08-19).

## 왜

래치(`produce_autoload.attempts`)는 **"이 영상은 아무리 시도해도 안 된다"**를 기억하는
장치지, "지금 서버가 잠깐 못 한다"를 기억하는 장치가 아니다
(store.autoload_rollback_attempt 주석 — 2026-08-07 실사고에서 확립된 원칙).

그런데 그 원칙이 `KeyPoolExhausted` **한 가지에만** 적용돼 있었다. 구글 5xx·타임아웃·
429도 같은 성질인데 `failed_download`/`failed_error`로 attempts를 태워, 3회에 소진되면
**사장님이 다시 담기 전엔 영영 자동추출에서 빠졌다.**

라이브 실측(2026-08-19): 시도소진(attempts>=3) **9건**.

## 판정 원칙

애매하면 **영구(래치)**다 — 진짜 못 받는 영상을 무한 재시도하면 크레딧이 샌다.
'분명히 일시적'이라 말할 수 있는 신호만 재시도로 돌린다.
"""
import pytest

from shopping_shorts.prewarm import _is_transient


@pytest.mark.parametrize("err", [
    # 라이브 produce_autoload.last_error 실제 문구
    "yt-dlp 실패(https://www.douyin.com/video/7642405529943313674): Unsupported URL",
    "전사 결과 없음(음성 없음·자막 불가)",
    "인스타 영상 해석 실패: https://www.instagram.com/popular/x/",
    "This video is private",
    "Video unavailable",
])
def test_영상_자체_문제는_래치한다(err):
    """영구 실패까지 재시도하면 크레딧이 샌다."""
    assert _is_transient(err) is False, f"영구 실패인데 일시로 판정: {err}"


@pytest.mark.parametrize("err", [
    "google api returned 503 Service Unavailable",
    "500 Internal error encountered",
    "502 Bad Gateway",
    "504 Gateway Timeout",
    "429 Too Many Requests",
    "The model is overloaded. Please try again later",
    "Read timed out",
    "Connection reset by peer",
    "rate limit exceeded",
])
def test_서버사정은_재시도한다(err):
    """5xx·429·타임아웃은 KeyPoolExhausted와 같은 성질 — 래치하면 안 된다."""
    assert _is_transient(err) is True, f"일시 실패인데 영구로 판정: {err}"


def test_빈값과_None에도_안전하다():
    """판정기가 예외를 내면 실패 처리 경로가 통째로 죽는다."""
    assert _is_transient(None) is False
    assert _is_transient("") is False
    assert _is_transient(Exception()) is False


def test_예외객체를_그대로_받는다():
    """호출부는 `except Exception as e` 의 e를 그대로 넘긴다."""
    assert _is_transient(RuntimeError("503 Service Unavailable")) is True
    assert _is_transient(RuntimeError("Unsupported URL")) is False


def test_일시실패는_attempts를_안_태운다(monkeypatch, tmp_path):
    """★계약 고정 — 판정만 맞고 배선이 틀리면 소용없다.

    다운로드가 5xx로 죽으면 rollback(카운터 반환)이 불리고, 영구 실패면
    mark_error(카운터 유지)가 불려야 한다.

    ⚠️ prewarm은 download_any를 **함수 안에서** import한다 → 모듈 속성 패치가 아니라
       원본 모듈(media_download)을 패치해야 실제 호출 경로에 닿는다(가짜 green 방지).
    """
    from shopping_shorts import prewarm as pw
    from shopping_shorts import media_download

    calls = {"rollback": 0, "mark_error": 0}

    class FakeStore:
        def get_extract(self, code): return None          # 캐시 없음 → 진행
        def autoload_attempts(self, codes): return {}     # 래치 안 걸림
        def autoload_mark_attempt(self, *a, **k): pass
        def autoload_rollback_attempt(self, code, err=""): calls["rollback"] += 1
        def autoload_mark_error(self, code, err=""): calls["mark_error"] += 1
        def get_setting(self, *a, **k): return ""
        def set_setting(self, *a, **k): pass

    monkeypatch.setattr(pw, "Store", lambda *a, **k: FakeStore())
    # 호출부 형태 그대로 받는다 — run_prewarm은 manual= 키워드로 부른다(2026-08-28).
    monkeypatch.setattr(pw, "_daily_take", lambda s, **kw: True)
    monkeypatch.setattr(pw, "_gate", lambda: (lambda cid, kind: True,
                                              lambda cid, kind: None,
                                              lambda kind: None,
                                              lambda kind: False))
    monkeypatch.setattr(pw, "_work_dir", lambda c: tmp_path)

    monkeypatch.setattr(media_download, "download_any",
                        lambda src, d: (_ for _ in ()).throw(RuntimeError("503 Service Unavailable")))
    r = pw.run_prewarm("SC1", "https://x/1")
    assert r == "deferred_transient", f"일시 실패인데 {r} (rollback={calls})"
    assert calls["rollback"] == 1 and calls["mark_error"] == 0

    calls["rollback"] = calls["mark_error"] = 0
    monkeypatch.setattr(media_download, "download_any",
                        lambda src, d: (_ for _ in ()).throw(RuntimeError("Unsupported URL")))
    r = pw.run_prewarm("SC2", "https://x/2")
    assert r == "failed_download", f"영구 실패인데 {r}"
    assert calls["mark_error"] == 1 and calls["rollback"] == 0
