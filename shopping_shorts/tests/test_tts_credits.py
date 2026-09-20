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


def _setup(monkeypatch, tmp_path, *, own, owner, admin, exempt):
    """own: {service: [keys]} 내가 등록한 키 / owner: {service: [keys]} 운영자 키."""
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    appmod._TTS_CREDIT_CACHE.clear()
    calls = []
    monkeypatch.setattr(appmod, "_own_keys_plain", lambda store, cid, svc: list(own.get(svc, [])))
    monkeypatch.setattr(appmod, "_is_admin", lambda cid: admin)
    monkeypatch.setattr(appmod.keyroute, "is_block_exempt", lambda cid: exempt)
    monkeypatch.setattr(appmod.keyroute, "_owner_keys", lambda svc: list(owner.get(svc, [])))
    monkeypatch.setattr(appmod.keyroute, "_owner_vmake_key", lambda store: list(owner.get("vmake", [])))

    def fake_probe(service, key):
        calls.append((service, key))
        return {"ok": True, "used": 10, "limit": 100, "remaining": 90, "reset_at": None, "plan": "free"}
    monkeypatch.setattr(appmod, "_tts_credit_probe", fake_probe)
    return calls


def test_route_uses_only_my_keys_and_caches(monkeypatch, tmp_path):
    calls = _setup(monkeypatch, tmp_path, own={"elevenlabs": ["sk_elv_abcd1234"], "vmake": ["vk:1"]},
                   owner={"elevenlabs": ["OWNER_KEY"], "typecast": ["OWNER_TC"]}, admin=False, exempt=False)
    c = TestClient(appmod.app)
    j = c.get("/api/produce/tts/credits").json()
    svcs = {s["service"]: s for s in j["services"]}
    assert svcs["elevenlabs"]["mode"] == "own" and svcs["elevenlabs"]["keys"][0]["key_tail"] == "1234"
    assert svcs["elevenlabs"]["keys"][0]["remaining"] == 90
    # ★일반 고객은 운영자 키(타입캐스트)로 **안 채운다** — 남의 잔액
    assert svcs["typecast"]["mode"] == "none" and not svcs["typecast"]["registered"]
    assert j["subclean"] == {"mode": "own", "show": True}
    assert j["need_own_key"] is True
    # 평문 키가 응답에 새면 안 된다
    assert "sk_elv_abcd1234" not in c.get("/api/produce/tts/credits").text
    # 60초 캐시: 두 번 불러도 업체엔 한 번만
    assert calls == [("elevenlabs", "sk_elv_abcd1234")]
    c.get("/api/produce/tts/credits?refresh=1")
    assert len(calls) == 2
    appmod._TTS_CREDIT_CACHE.clear()


def test_admin_sees_owner_keys(monkeypatch, tmp_path):
    """관리자(사장님)는 등록 키가 없어도 운영자 키(서버 env·전역 설정)로 회사 잔액을 본다."""
    _setup(monkeypatch, tmp_path, own={}, owner={"elevenlabs": ["OWNER_ELV_KEY_9999"], "vmake": ["vk:owner"]},
           admin=True, exempt=True)
    j = TestClient(appmod.app).get("/api/produce/tts/credits").json()
    svcs = {s["service"]: s for s in j["services"]}
    assert svcs["elevenlabs"]["mode"] == "owner" and svcs["elevenlabs"]["registered"]
    assert svcs["elevenlabs"]["keys"][0]["key_tail"] == "9999"
    assert svcs["typecast"]["mode"] == "none"                  # 운영자 타입캐스트 키는 없음
    assert j["subclean"] == {"mode": "owner", "show": True}
    appmod._TTS_CREDIT_CACHE.clear()


def test_owner_typecast_key_comes_from_env(monkeypatch):
    """운영자 타입캐스트 키(env TYPECAST_API_KEY)가 _owner_keys에 잡혀야 관리자 잔액에 뜬다."""
    from shopping_shorts import config, keyroute
    monkeypatch.setattr(config, "TYPECAST_API_KEY", "tc_owner_key_1")
    assert keyroute._owner_keys(keyroute.SVC_TYPECAST) == ["tc_owner_key_1"]
    monkeypatch.setattr(config, "TYPECAST_API_KEY", "")
    assert keyroute._owner_keys(keyroute.SVC_TYPECAST) == []


def test_exempt_customer_using_owner_keys_sees_nothing(monkeypatch, tmp_path):
    """★사장님 키를 빌려 쓰는 고객(면제 명단): 잔액도 버튼도 '키 등록하세요'도 없다."""
    _setup(monkeypatch, tmp_path, own={}, owner={"elevenlabs": ["OWNER_ELV"], "vmake": ["vk:owner"]},
           admin=False, exempt=True)
    j = TestClient(appmod.app).get("/api/produce/tts/credits").json()
    assert all(s["mode"] == "none" and s["keys"] == [] for s in j["services"])
    assert j["subclean"] == {"mode": "none", "show": False}
    assert j["need_own_key"] is False
    assert "OWNER_ELV" not in TestClient(appmod.app).get("/api/produce/tts/credits").text
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
    # 4단계 아이콘 버튼의 노출은 서버 판정(subclean.show)을 따른다 + 페이지 로드 때 한 번 판정
    assert "btn.hidden = !(d.subclean && d.subclean.show)" in HTML
    assert "addEventListener('DOMContentLoaded', () => loadTtsCredits())" in HTML
