"""렌즈 비전 속도 개편 3건이 조용히 되돌아가지 않게 잡아두는 회귀 테스트 (2026-08-16).

배경 — 사장님 제보 "렌즈 개선했는데 바뀐 게 없다". 라이브 실측으로 갈라보니
19:19 커밋(병렬화)은 제대로 배포돼 있었고, 남은 지연은 **비전 호출 자체**였다:

  ① 렌즈가 영상용 무거운 모델(gemini-3.5-flash)을 쓰고 있었다
     → 실측 26.2초 vs lite 3.0초, 결과 품질은 동일, 비용은 정확히 절반,
       무료한도는 하루 20건 vs 500건(25배)
  ② 같은 프레임으로 비전을 **두 번** 불렀다
     (/api/lens/yt → cn_search_keyword_vision, /api/lens/cn/keywords → cn_search_candidates)
  ③ 단일 왕복이 이따금 통째로 멈췄다(85초, 키는 1번만 집음 = 재시도 아님)

★네트워크를 타지 않는다 — 전부 가짜 클라이언트로 검증한다.
"""
import sys
import types as pytypes

import pytest

from shopping_shorts import video_analysis as VA


class _FakeResp:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    """generate_content 호출을 기록하는 가짜. 호출 횟수·모델명·타임아웃을 검사한다."""

    def __init__(self, log, payload, raise_exc=None):
        self._log = log
        self._payload = payload
        self._raise = raise_exc

    def generate_content(self, model=None, contents=None, config=None):
        self._log.append({"model": model, "config": config})
        if self._raise is not None:
            raise self._raise
        return _FakeResp(self._payload)


class _FakeClient:
    def __init__(self, models):
        self.models = models


@pytest.fixture(autouse=True)
def _clean_cache():
    VA._lens_cache.clear()
    yield
    VA._lens_cache.clear()


def _patch(monkeypatch, payload, raise_exc=None):
    """가짜 Gemini 클라이언트를 심고, 호출 로그를 돌려준다."""
    log = []
    fake = _FakeClient(_FakeModels(log, payload, raise_exc))
    monkeypatch.setattr(VA, "_client_for_key", lambda key: fake)
    monkeypatch.setattr(VA.comment_gen, "_next_live_key_and_idx", lambda: ("KEY", 0))
    monkeypatch.setattr(VA, "SHORTS_GEMINI_KEYS", ["KEY"], raising=False)
    monkeypatch.setattr(VA.usage_meter, "record", lambda *a, **k: None, raising=False)
    return log


# ── ① 렌즈는 가벼운 모델을 쓴다 ─────────────────────────────────────────
def test_렌즈는_영상용_무거운_모델을_쓰지_않는다():
    """_LENS_MODEL이 _MODEL(영상 입력용)과 분리돼 있어야 한다.

    같은 값으로 되돌리면 렌즈가 다시 20~50초가 되고 무료한도가 25배 빨리 마른다."""
    assert VA._LENS_MODEL != VA._MODEL
    assert "lite" in VA._LENS_MODEL


@pytest.mark.parametrize("fn,payload", [
    ("cn_search_keyword_vision", '{"product":"감자칩","zh":"薯片"}'),
    ("cn_search_candidates", '{"product":"감자칩","candidates":[{"ko":"감자칩","zh":"薯片"}]}'),
])
def test_렌즈_비전은_LENS_MODEL로_호출한다(monkeypatch, fn, payload):
    log = _patch(monkeypatch, payload)
    getattr(VA, fn)(b"\xff\xd8jpeg", "감자칩 만들기")
    assert log, f"{fn}이 Gemini를 부르지 않았다"
    assert log[0]["model"] == VA._LENS_MODEL


# ── ② 같은 프레임은 비전을 한 번만 탄다 ──────────────────────────────────
def test_같은_프레임이면_비전을_다시_부르지_않는다(monkeypatch):
    """cn_search_candidates가 채운 결과를 cn_search_keyword_vision이 그대로 쓴다.

    렌즈를 열면 두 엔드포인트가 동시에 오는데 둘 다 같은 프레임을 본다 —
    비전을 두 번 부를 이유가 없다."""
    img, cap = b"\xff\xd8SAMEFRAME", "감자칩 만들기"
    log = _patch(monkeypatch, '{"product":"감자칩","candidates":[{"ko":"감자칩","zh":"薯片"}]}')

    first = VA.cn_search_candidates(img, cap)
    assert first["product"] == "감자칩"
    assert len(log) == 1

    second = VA.cn_search_keyword_vision(img, cap)
    assert second["product"] == "감자칩"      # 값은 나오는데
    assert len(log) == 1                      # ★호출은 안 늘었다


def test_다른_프레임은_캐시를_공유하지_않는다(monkeypatch):
    log = _patch(monkeypatch, '{"product":"감자칩","zh":"薯片"}')
    VA.cn_search_keyword_vision(b"\xff\xd8AAA", "x")
    VA.cn_search_keyword_vision(b"\xff\xd8BBB", "x")
    assert len(log) == 2


def test_다른검색어_재요청은_캐시를_오염시키지_않는다(monkeypatch):
    """'🔄 다른 검색어'(exclude)는 일부러 다른 각도를 뽑는 요청이라 캐시에 넣으면 안 된다."""
    _patch(monkeypatch, '{"product":"감자칩","candidates":[{"ko":"감자칩","zh":"薯片"}]}')
    VA.cn_search_candidates(b"\xff\xd8F", "cap", exclude=["薯片"])
    assert len(VA._lens_cache) == 0


def test_빈_결과는_캐시하지_않는다(monkeypatch):
    """실패를 캐시하면 그 프레임이 TTL 동안 계속 빈 값으로 굳는다."""
    _patch(monkeypatch, '{"product":"","zh":""}')
    VA.cn_search_keyword_vision(b"\xff\xd8F", "cap")
    assert len(VA._lens_cache) == 0


# ── ③ 멈춘 호출은 끊고 다시 시도한다 ─────────────────────────────────────
def test_비전_호출에_타임아웃이_걸려있다(monkeypatch):
    """SDK 기본값은 무한대기다. 실측 85초짜리 호출이 그래서 그대로 흘러갔다."""
    log = _patch(monkeypatch, '{"product":"감자칩","zh":"薯片"}')
    VA.cn_search_keyword_vision(b"\xff\xd8F", "cap")
    cfg = log[0]["config"]
    assert getattr(cfg, "http_options", None) is not None, "http_options가 없다 = 무한대기"
    assert cfg.http_options.timeout == int(VA._LENS_TIMEOUT_S * 1000)  # ★밀리초여야 한다


@pytest.mark.parametrize("exc,expected", [
    (TimeoutError("x"), True),
    (Exception("504 Deadline Exceeded: timed out"), True),
    (Exception("Read timeout"), True),
    (ValueError("bad json"), False),
    (Exception("429 RESOURCE_EXHAUSTED"), False),
])
def test_타임아웃_판정은_오탐없이_동작한다(exc, expected):
    """판정을 여러 곳에 흩뿌리지 않고 이 함수 하나로 본다(CLAUDE.md 0순위-B)."""
    assert VA._is_timeout_error(exc) is expected


def test_타임아웃이_나면_다른_키로_재시도한다(monkeypatch):
    """끊고 끝내면 조용한 빈 값이 된다 — 반드시 다음 키로 다시 시도해야 한다."""
    log = _patch(monkeypatch, "", raise_exc=TimeoutError("timed out"))
    out = VA.cn_search_keyword_vision(b"\xff\xd8F", "cap", max_retries=3)
    assert out == {}
    assert len(log) == 3, f"재시도가 3번 돌아야 하는데 {len(log)}번만 돌았다"
