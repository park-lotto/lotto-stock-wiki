# -*- coding: utf-8 -*-
"""회원 제미니 키 건강 안내 — 2026-09-25 실사고(죽은 키가 회원 화면엔 '● 정상').

지키는 계약:
  ① 회원 화면(설정·사이드바)은 key_vault 판정(정지·영구 사망)과 DB bad를 그대로 옮긴다
  ② 키를 안 낸 회원에겐 '예비 키' 당부를 띄우지 않는다 / 권장 수 미만이면 띄운다
  ③ 등록 확인은 세 갈래 — 살아있음 True / 쓸 수 없음 False(+정지) / 구글 붐빔 None(판정 보류)
     ★붐빔을 bad로 찍으면 공용 풀에서 빠진다(회원 603 실사고)
"""
import importlib

import pytest

from pipeline.atoms import key_vault as kv
from shopping_shorts import keycrypt, keyroute
from shopping_shorts.store import Store

_FERNET = "NZAowCs7o9LHVnJdZbxrVmYI7MHqyPFkydIUd1mc8To="   # 테스트 전용
PREPAY = "402 Payment Required. Your prepayment credits are depleted. RESOURCE_EXHAUSTED"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("BYOK_MASTER_KEY", _FERNET)
    importlib.reload(keycrypt)
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "vault_state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "vault_state.lock")
    monkeypatch.setattr(kv, "_tg_alert", lambda t: None)          # 실제 텔레그램 금지
    kv._SUS_CACHE["t"] = 0.0
    return Store(str(tmp_path / "t.db"))


def _add(store, cid, plain, status=None):
    store.add_customer_key(cid, keyroute.SVC_GEMINI, plain)
    with store._conn() as c:
        kid = c.execute("SELECT MAX(id) FROM customer_keys").fetchone()[0]
        if status:
            c.execute("UPDATE customer_keys SET status=? WHERE id=?", (status, kid))
    return kid


def test_정지된_키와_bad_키가_이유와_함께_나온다(env):
    from shopping_shorts import gemini_keyhealth as gk
    _add(env, 100, "AIzaGOOD-aaaaaaaaaaaaaaaa", "ok")
    k_pre = _add(env, 100, "AIzaPREPAY-bbbbbbbbbbbbbb", "ok")      # DB엔 ok인데 실제론 402
    k_bad = _add(env, 100, "AIzaBAD-cccccccccccccccccc", "bad")
    kv.note_failure("AIzaPREPAY-bbbbbbbbbbbbbb", Exception(PREPAY))
    h = gk.member_key_health(env, 100)
    why = {k["id"]: k["reason"] for k in h["keys"]}
    assert why[k_pre] == kv.UNUSABLE_PREPAY
    assert why[k_bad] == "bad"
    assert h["has_dead"] is True
    assert h["n_bad"] == 2 and h["n_usable"] == 1
    assert h["few_keys"] is True
    pre = [k for k in h["keys"] if k["id"] == k_pre][0]
    assert pre["title"] == gk.REASONS[kv.UNUSABLE_PREPAY]["title"]
    assert "충전" in pre["fix"]


def test_키를_안_낸_회원에겐_당부하지_않는다(env):
    from shopping_shorts import gemini_keyhealth as gk
    h = gk.member_key_health(env, 200)
    assert h["n_total"] == 0 and h["has_dead"] is False and h["few_keys"] is False


def test_권장_수만큼_살아있으면_당부하지_않는다(env):
    from shopping_shorts import gemini_keyhealth as gk
    for i in range(gk.RECOMMENDED_KEYS):
        _add(env, 300, f"AIzaOK{i}-dddddddddddddddd", "ok")
    h = gk.member_key_health(env, 300)
    assert h["has_dead"] is False and h["few_keys"] is False


def test_충전해서_살아나면_회원_화면에서도_사라진다(env):
    from shopping_shorts import gemini_keyhealth as gk
    k = _add(env, 400, "AIzaREVIVE-eeeeeeeeeeeeeeee", "ok")
    kv.note_failure("AIzaREVIVE-eeeeeeeeeeeeeeee", Exception(PREPAY))
    assert gk.member_key_health(env, 400)["has_dead"] is True
    kv._SUS_CACHE["t"] = 0.0
    kv.note_success("AIzaREVIVE-eeeeeeeeeeeeeeee")
    h = gk.member_key_health(env, 400)
    assert h["has_dead"] is False and not [x for x in h["keys"] if x["id"] == k and x["reason"]]


# ── ③ 등록 확인 세 갈래 ───────────────────────────────────────────────────
@pytest.fixture
def app_mod(env, monkeypatch):
    from shopping_shorts import app as app_mod
    return app_mod


def test_등록확인_구글붐빔은_판정보류(app_mod, monkeypatch):
    from shopping_shorts import comment_gen
    monkeypatch.setattr(comment_gen, "_probe_key_result", lambda k, timeout=15: (
        False, 503, '{"error": {"code": 503, "message": "This model is currently experiencing high demand."}}'))
    assert app_mod._probe_user_key(keyroute.SVC_GEMINI, "AIzaBUSY-ffffffffffffffff") is None
    assert app_mod._key_status(keyroute.SVC_GEMINI, "AIzaBUSY-ffffffffffffffff") == "unknown"
    # 붐빔은 키 잘못이 아니다 — 풀에서 빼지도, 정지 표시를 남기지도 않는다
    assert kv.without_dead(["AIzaBUSY-ffffffffffffffff"]) == ["AIzaBUSY-ffffffffffffffff"]
    assert kv._key_fingerprint("AIzaBUSY-ffffffffffffffff") not in kv.suspension_info()


def test_등록확인_선불소진은_bad이고_풀에서도_빠진다(app_mod, monkeypatch):
    from shopping_shorts import comment_gen
    monkeypatch.setattr(comment_gen, "_probe_key_result", lambda k, timeout=15: (
        False, 402, '{"error": {"code": 402, "message": "Your prepayment credits are depleted."}}'))
    assert app_mod._key_status(keyroute.SVC_GEMINI, "AIzaDEAD-gggggggggggggggg") == "bad"
    assert kv.without_dead(["AIzaDEAD-gggggggggggggggg"]) == []
    assert "충전" in (app_mod._take_key_failure() or "")


def test_등록확인_살아있으면_ok(app_mod, monkeypatch):
    from shopping_shorts import comment_gen
    monkeypatch.setattr(comment_gen, "_probe_key_result", lambda k, timeout=15: (True, 200, ""))
    assert app_mod._key_status(keyroute.SVC_GEMINI, "AIzaLIVE-hhhhhhhhhhhhhhhh") == "ok"
