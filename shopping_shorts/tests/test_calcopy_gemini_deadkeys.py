# -*- coding: utf-8 -*-
"""죽은 키 바로 넘기기(10-18 사장님) — 실제 구글 오류 글로 분류를 고정한다.
실측: 161키 동시 1회 → 151 정상인데 장부는 161 '죽음'(429 를 전부 '오늘 끝'으로 적음). 진짜 고장 = 402 선불 소진 4·400 무효 3·한도 0 1."""
import time

from tools.calcopy.engine import gemini_keys as gk

DAILY_FREE_429 = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'You exceeded your current quota, please check your plan "
                  "and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. "
                  "\n* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, "
                  "model: gemini-3.6-flash\nPlease retry in 6h2m47.896702756s.', 'status': 'RESOURCE_EXHAUSTED'}}")
LIMIT0_429 = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': \"Quota exceeded for quota metric 'API requests' and limit "
              "'Request limit per minute for a region'\", 'details': [{'metadata': {'quota_limit_value': '0', "
              "'quota_limit': 'ApiRequestsPerMinutePerProjectPerRegion'}}]}}")
PREPAID_402 = "402 RESOURCE_EXHAUSTED. {'error': {'code': 402, 'message': 'Your prepayment credits are depleted.'}}"
INVALID_400 = "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'API key not valid. Please pass a valid API key.'}}"
MINUTE_429 = "429 RESOURCE_EXHAUSTED. quota_limit: 'GenerateRequestsPerMinutePerProjectPerModel-FreeTier', quota_limit_value: '10'"


def test_daily_free_quota_is_not_broken_and_uses_google_retry_time():
    assert gk.broken_reason(DAILY_FREE_429) is None          # 'billing' 글자에 속지 않는다(10-18 오판 11키)
    assert 21767 < gk.retry_after_s(DAILY_FREE_429) < 21768


def test_dead_kinds():
    assert gk.broken_reason(LIMIT0_429) == "key"
    assert gk.broken_reason(PREPAID_402) == "key"
    assert gk.broken_reason(INVALID_400) == "key"
    assert gk.broken_reason("404 NOT_FOUND model") == "nomodel"
    assert gk.broken_reason("503 UNAVAILABLE overloaded") is None
    assert gk.rate_scope(MINUTE_429) == "minute"


def test_mark_cooldown_and_success_clears(tmp_path, monkeypatch):
    monkeypatch.setattr(gk, "QUOTA_FILE", tmp_path / "q.json")
    gk.mark("K1", "m", "429", MINUTE_429)                    # 분당 → 65초만
    assert gk.is_dead("K1", "m")
    d = gk._load(); assert isinstance(d["dead"]["K1|m"], float) and d["dead"]["K1|m"] - time.time() < 70
    gk.mark("K2", "m", "429", DAILY_FREE_429)                # 구글이 준 6시간
    assert gk._load()["dead"]["K2|m"] - time.time() > 21000
    gk.mark("K1", "m", "ok")                                 # 성공하면 '죽음' 표시는 틀린 것 → 지움
    assert not gk.is_dead("K1", "m")


def test_broken_ledger_by_fingerprint(tmp_path, monkeypatch):
    monkeypatch.setattr(gk, "BROKEN_FILE", tmp_path / "b.json")
    gk.mark_broken("fake-key-a", "m", "key", PREPAID_402)
    assert gk.is_broken("fake-key-a", "any-model")
    assert not gk.is_broken("fake-key-b", "m")               # 같은 이름에 새 키가 오면 지문이 달라 다시 쓴다
    assert "fake-key-a" not in (tmp_path / "b.json").read_text(encoding="utf-8")   # 키 값은 안 적는다


def test_processes_start_at_different_keys():
    import subprocess, sys
    code = "from tools.calcopy.engine import gemini_free as g; print(g._CURSOR['i'])"
    vals = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip() for _ in range(3)}
    assert len(vals) >= 2                                    # 모든 세션이 0번 키부터 몰리던 것(10-18)
