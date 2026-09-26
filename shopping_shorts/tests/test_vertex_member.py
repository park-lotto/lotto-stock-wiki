# -*- coding: utf-8 -*-
"""회원 자기 Vertex(서비스계정) — 2026-09-26 사장님 "필요한 사람은 등록하게 / AI 장면생성도".

계약: 등록한 회원은 대본·장면매칭이 **자기 프로젝트**로 · 미등록은 종전(사장님 스위치/무료키) ·
      JSON 검사·실호출 확인 뒤에만 저장 · 비밀값은 화면에 안 나감 · 회원당 1개."""
import json

import pytest

from shopping_shorts import vertex_route as vr

SA = {"type": "service_account", "project_id": "member-proj-1", "private_key_id": "abc123",
      "private_key": "-----BEGIN PRIVATE KEY-----\nMIIE...\n-----END PRIVATE KEY-----\n",
      "client_email": "shorts-bot@member-proj-1.iam.gserviceaccount.com"}


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    vr.reset_cache()
    monkeypatch.setattr(vr, "_read_settings", lambda: {vr.SETTING_ENABLED: "admin",
                                                       vr.SETTING_OPS: "script_generate,ai_match"})
    monkeypatch.setattr(vr, "_is_admin", lambda cid: str(cid) == "0")
    yield
    vr.reset_cache()


def test_validate_sa_accepts_real_shape_and_explains_bad_input():
    info, err = vr.validate_sa(json.dumps(SA))
    assert err == "" and info["project_id"] == "member-proj-1"
    assert "JSON" in vr.validate_sa("not json")[1]
    assert "서비스계정" in vr.validate_sa(json.dumps({"type": "authorized_user"}))[1]
    assert "private_key" in vr.validate_sa(json.dumps(dict(SA, private_key="")))[1]
    assert vr.validate_sa("")[1]


def test_label_never_contains_private_key():
    lab = vr.sa_label(SA)
    assert "member-proj-1" in lab and "BEGIN" not in lab and "abc123" not in lab


def test_member_creds_turn_on_member_ops_only(monkeypatch):
    monkeypatch.setattr(vr, "member_info", lambda cid: SA if str(cid) == "205" else None)
    assert vr.on("script_generate", cid=205) and vr.on("ai_match", cid=205)
    assert not vr.on("frame_script", cid=205), "태깅은 회원 자동 ON 대상이 아니다(무료키 유지)"
    assert not vr.on("script_generate", cid=204), "미등록 회원은 종전 그대로(사장님 스위치=admin만)"
    assert vr.on("script_generate", cid=0)


def test_client_uses_member_project_and_meters_as_member(monkeypatch):
    made = {}

    class FakeClient:
        def __init__(self, **kw):
            made.update(kw)
    import google.genai as genai
    monkeypatch.setattr(genai, "Client", FakeClient)
    from google.oauth2 import service_account
    monkeypatch.setattr(service_account.Credentials, "from_service_account_info",
                        classmethod(lambda cls, info, scopes=None: ("CREDS", info["project_id"], tuple(scopes))))
    from shopping_shorts import usage_meter
    wrapped = {}
    monkeypatch.setattr(usage_meter, "wrap", lambda cl, auth="apikey", pool=None, key=None:
                        wrapped.update(auth=auth, pool=pool, key=key) or cl)
    monkeypatch.setattr(vr, "member_info", lambda cid: SA if str(cid) == "205" else None)
    vr.client(205)
    assert made["project"] == "member-proj-1" and made["location"] == "global" and made["vertexai"] is True
    assert made["credentials"][0] == "CREDS" and "cloud-platform" in made["credentials"][2][0]
    assert wrapped == {"auth": "vertex", "pool": "vertex-member", "key": "member:205"}
    # 미등록은 사장님 프로젝트
    made.clear()
    vr.client(204)
    assert made.get("project") != "member-proj-1" and "credentials" not in made


def test_member_vertex_failure_falls_back_to_keypool_not_owner(monkeypatch):
    """회원 Vertex가 죽으면 **사장님 Vertex로 대신 태우지 않고** 종전 키풀로(try_call이 (False,None))."""
    monkeypatch.setattr(vr, "member_info", lambda cid: SA)
    monkeypatch.setattr(vr, "current_cid", lambda: 205)
    seen = []
    monkeypatch.setattr(vr, "client", lambda cid=None: seen.append(cid) or object())

    def boom(cl, m):
        raise RuntimeError("PERMISSION_DENIED 403")
    assert vr.try_call("script_generate", boom) == (False, None)
    assert seen == [205], "회원 클라이언트 한 번만 — 사장님 클라이언트로 재시도하지 않는다"


def test_verify_sa_translates_google_errors(monkeypatch):
    import google.genai as genai
    from google.oauth2 import service_account
    monkeypatch.setattr(service_account.Credentials, "from_service_account_info",
                        classmethod(lambda cls, info, scopes=None: "CREDS"))
    cases = {"403 PERMISSION_DENIED": "Vertex AI 사용자", "SERVICE_DISABLED: aiplatform has not been used": "API가 꺼져",
             "BILLING_DISABLED": "결제", "invalid_grant: bad key": "폐기"}
    for err, want in cases.items():
        class C:
            def __init__(self, **kw):
                def gen(**k):
                    raise RuntimeError(err)
                self.models = type("M", (), {"generate_content": staticmethod(gen)})()
        monkeypatch.setattr(genai, "Client", C)
        ok, msg = vr.verify_sa(SA)
        assert ok is False and want in msg, (err, msg)


def test_veo_uses_member_project_admin_owner_and_blocks_others(monkeypatch):
    """Veo는 비싸다 — 회원은 자기 프로젝트, 관리자는 사장님 프로젝트, 나머지는 **안 만든다**(사장님 크레딧 대납 금지)."""
    monkeypatch.setattr(vr, "member_info", lambda cid: SA if str(cid) == "205" else None)
    monkeypatch.setattr(vr, "_member_client", lambda cid, info: ("MEMBER", cid, info["project_id"]))
    monkeypatch.setattr(vr, "client", lambda cid=None: ("OWNER", cid))
    assert vr.veo_client(205) == ("MEMBER", 205, "member-proj-1")
    assert vr.veo_client(0) == ("OWNER", 0)
    assert vr.veo_client(204) is None
    assert vr.veo_allowed(205) == (True, "") and vr.veo_allowed(0) == (True, "")
    ok, why = vr.veo_allowed(204)
    assert ok is False and "Vertex를 등록" in why


def test_run_ai_scene_refuses_without_member_vertex(monkeypatch, tmp_path):
    """워커도 같은 판정 — 등록 안 한 회원 작업이면 Veo를 안 부르고 실패 상태에 이유를 남긴다."""
    from shopping_shorts import ai_scene
    states = {}
    job = {"customer_id": 204, "status": "done", "extract": {},
           "edit_plan": {"beats": [{"beat_idx": 0, "narration": "리모컨", "target_seconds": 4}]}}

    class St:
        def __init__(self, *_a):
            pass

        def get_mix_job(self, _j):
            return job

        def update_mix_job(self, _j, edit_plan=None):
            states["plan"] = edit_plan
    import shopping_shorts.store as store_mod
    monkeypatch.setattr(store_mod, "Store", St)
    monkeypatch.setattr(ai_scene, "base_frame_path", lambda *a, **k: str(tmp_path / "b.png"))
    monkeypatch.setattr(ai_scene, "motion_request", lambda *a, **k: "move")
    called = []
    monkeypatch.setattr(ai_scene, "generate", lambda *a, **k: called.append(1))
    monkeypatch.setattr(vr, "member_info", lambda cid: None)
    import shopping_shorts.app as app_mod
    monkeypatch.setattr(app_mod, "_SCENE_ASSETS_DIR", tmp_path)
    assert ai_scene.run_ai_scene("j1", 0, "natural", "db", str(tmp_path)) is None
    assert not called, "등록 안 한 회원인데 Veo를 불렀다"
    st = states["plan"]["beats"][0]["ai_scene"]
    assert st["state"] == "failed" and "Vertex를 등록" in st["error"]


def test_ai_scene_button_only_for_registered_members_when_switch_open(monkeypatch):
    """스위치 ai_scene_enabled=1(전체)이어도 버튼·API는 자기 Vertex 등록 회원(+관리자)에게만."""
    import shopping_shorts.app as app_mod

    class St:
        def __init__(self, *_a):
            pass

        def get_setting(self, k, d=""):
            return "1" if k == "ai_scene_enabled" else d
    monkeypatch.setattr(app_mod, "Store", St)
    monkeypatch.setattr(vr, "member_info", lambda cid: SA if str(cid) == "205" else None)
    monkeypatch.setattr(vr, "_is_admin", lambda cid: str(cid) == "0")
    assert app_mod._ai_scene_on(205) is True
    assert app_mod._ai_scene_on(204) is False
    assert app_mod._ai_scene_on(0) is True
