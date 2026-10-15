"""목소리 미리듣기 — 음성 업체가 거절하면 500 대신 원인 안내(2026-10-04 관제 113).

실측: cid 364 가 본인 타입캐스트 키로 미리듣기를 눌렀는데 타입캐스트가 403 UNUSUAL_ACTIVITY_DETECTED(계정 차단)를 줬고,
예외가 그대로 올라가 500 이 났다. 사장님: "미리듣기 500 오류나면 타입캐스트에 확인해 봐야 된다는 문구도 넣고".
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_mod

BODY = ('403 Forbidden https://api.typecast.ai/v1/text-to-speech | 본문: {"error_code":"UNUSUAL_ACTIVITY_DETECTED",'
        '"message":"Unusual account activity has been detected. If this activity is determined to be"}')


def test_타입캐스트_계정_차단은_타입캐스트에_확인하라고_말한다():
    msg = app_mod._user_facing_error(BODY)
    assert "타입캐스트" in msg and "확인" in msg and "비정상 활동" in msg
    assert "요금제" not in msg      # 일반 403 안내(요금제·목소리 확인)로 떨어지면 틀린 안내다


def test_타입캐스트_일반_403은_종전_안내_그대로():
    msg = app_mod._user_facing_error("403 Client Error: Forbidden for url: https://api.typecast.ai/v1/text-to-speech")
    assert "음성 합성을 거부" in msg and "요금제" in msg


def test_미리듣기_합성이_거절되면_500이_아니라_안내를_돌려준다(monkeypatch):
    class _Store:
        def __init__(self, *a, **k):
            pass

        def get_mix_job(self, job_id):
            return {"customer_id": 0, "voice": None,
                    "edit_plan": {"beats": [{"narration": "안녕하세요", "role": "hook"}, {"narration": "반갑습니다"}]}}

    def _boom(*a, **k):
        raise RuntimeError(BODY)

    monkeypatch.setattr(app_mod, "Store", _Store)
    monkeypatch.setattr(app_mod, "_need_own_key_or_402", lambda *a, **k: None)
    monkeypatch.setattr(app_mod, "_voice_snapshot", lambda *a, **k: {})
    monkeypatch.setattr(app_mod.mix_pipeline, "synthesize_line", _boom)
    monkeypatch.setattr(app_mod, "_AUTH_ON", False)
    r = TestClient(app_mod.app).post("/api/mix/voice/preview", json={"job_id": "t_preview_vendor"})
    assert r.status_code == 502, r.text
    data = r.json()
    assert data["ok"] is False and "타입캐스트" in data["error"] and "확인" in data["error"]


def test_키_검사도_계정_차단이면_같은_안내를_한다():
    blocked = app_mod._explain_key_failure(app_mod.keyroute.SVC_TYPECAST, 403, '{"error_code":"UNUSUAL_ACTIVITY_DETECTED","message":"Unusual account activity has been detected."}')
    assert blocked == app_mod._TYPECAST_BLOCKED_MSG and "요금제" not in blocked
    plain = app_mod._explain_key_failure(app_mod.keyroute.SVC_TYPECAST, 403, '{"message":"forbidden"}')
    assert "요금제" in plain      # 일반 403 은 종전 안내 그대로
