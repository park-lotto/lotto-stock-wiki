"""음성(TTS) 키 잔액 조회(2026-09-04 사장님 "tts에도 api연동해서 본인크레딧 나오게").

업체 응답 → 화면 dict 파싱(순수), 라우트(내 키만·캐시), 화면 배선(위젯 id·로더 호출).
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_parse_elevenlabs_ok():
    r = appmod._tts_credit_parse("elevenlabs", 200, {
        "character_count": 87655, "character_limit": 100000,
        "next_character_count_reset_unix": 1790000000, "tier": "creator"})
    assert r["ok"] and r["remaining"] == 12345 and r["used"] == 87655 and r["limit"] == 100000
    assert r["reset_at"] == 1790000000 and r["plan"] == "creator"


def test_parse_typecast_ok_has_no_reset():
    r = appmod._tts_credit_parse("typecast", 200, {
        "plan": "lite", "credits": {"plan_credits": 200000, "used_credits": 157300}})
    assert r["ok"] and r["remaining"] == 42700 and r["plan"] == "lite" and r["reset_at"] is None


def test_parse_elevenlabs_restricted_key_is_not_bad_key():
    """★제한키는 user_read가 없어 401 — 키가 틀린 게 아니다(2026-08-24 실측). 갈라야 한다."""
    r = appmod._tts_credit_parse("elevenlabs", 401, {"detail": {"status": "missing_permissions",
                                                                "message": "missing the permission user_read"}})
    assert r == {"ok": False, "error_kind": "no_permission"}
    r2 = appmod._tts_credit_parse("elevenlabs", 401, {"detail": "Invalid API key"})
    assert r2["error_kind"] == "bad_key"
    assert appmod._tts_credit_parse("typecast", 429, "Too many requests")["error_kind"] == "rate_limited"


def test_route_uses_only_my_keys_and_caches(monkeypatch):
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    appmod._TTS_CREDIT_CACHE.clear()
    calls = []

    def fake_keys(store, cid, service):
        return ["sk_elv_abcd1234"] if service == "elevenlabs" else []

    def fake_probe(service, key):
        calls.append((service, key))
        return {"ok": True, "used": 10, "limit": 100, "remaining": 90, "reset_at": None, "plan": "free"}

    monkeypatch.setattr(appmod, "_own_keys_plain", fake_keys)
    monkeypatch.setattr(appmod, "_tts_credit_probe", fake_probe)
    c = TestClient(appmod.app)
    j = c.get("/api/produce/tts/credits").json()
    svcs = {s["service"]: s for s in j["services"]}
    assert svcs["elevenlabs"]["registered"] and svcs["elevenlabs"]["keys"][0]["key_tail"] == "1234"
    assert svcs["elevenlabs"]["keys"][0]["remaining"] == 90
    assert not svcs["typecast"]["registered"] and svcs["typecast"]["keys"] == []
    assert svcs["elevenlabs"]["dashboard"].startswith("https://")
    # 평문 키가 응답에 새면 안 된다
    assert "sk_elv_abcd1234" not in c.get("/api/produce/tts/credits").text
    # 60초 캐시: 두 번 불러도 업체엔 한 번만
    assert calls == [("elevenlabs", "sk_elv_abcd1234")]
    c.get("/api/produce/tts/credits?refresh=1")
    assert len(calls) == 2
    appmod._TTS_CREDIT_CACHE.clear()


def test_widget_wired_in_tts_panel():
    assert 'id="ttsCredits"' in HTML
    assert "function loadTtsCredits(" in HTML
    assert "/api/produce/tts/credits" in HTML
    # 5단계로 들어올 때 잔액 로더가 돈다(loadTtsBeats 안, 프리셋 로드보다 먼저)
    m = re.search(r"async function loadTtsBeats\(\)\{(.*?)loadPresets\(\)", HTML, re.S)
    assert m and "loadTtsCredits()" in m.group(1)
    # 제한키 안내 문구(키가 틀린 게 아니라는 것)가 화면에 있다
    assert "잔액 조회 권한이 없어요" in HTML
