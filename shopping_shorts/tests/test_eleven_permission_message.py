# -*- coding: utf-8 -*-
"""일레븐랩스가 알려준 진짜 사유를 버리지 않는다 (2026-09-02 실사고).

사장님 화면엔 `검색 실패 (HTTP 401)`만 떴고, 서버 안내는 "키를 새로 만들어 다시
넣어주세요"였다. 그런데 응답 본문에는 정확한 사유가 적혀 있었다:

    "The API key you used is missing the permission voices_read to execute this operation."

**키는 멀쩡했고 권한 한 칸이 꺼져 있었다.** 새 키를 만들어도 그 칸을 안 켜면 똑같이
실패한다 — 틀린 안내는 고객을 고칠 수 없는 쳇바퀴에 넣는다.
같은 함정을 2026-08-24에도 밟았다(키 ID를 키로 붙여넣은 고객에게 엉뚱한 안내).
"""
import json

from shopping_shorts import eleven_voices as ev

REAL_401 = json.dumps({"detail": {
    "type": "authentication_error", "code": "unauthorized",
    "message": "The API key you used is missing the permission voices_read "
               "to execute this operation."}})


def test_permission_error_names_the_permission():
    """★권한 이름을 그대로 말해준다 — 뭘 켜야 하는지 모르면 못 고친다."""
    msg = ev.explain_error(401, REAL_401)
    assert "voices_read" in msg
    assert "권한" in msg
    # 키를 새로 만들라는 **틀린** 안내가 섞이면 안 된다(그래봐야 또 실패한다).
    assert "새로 만들어 다시 넣어" not in msg


def test_other_permissions_are_named_too():
    """권한은 여러 가지다 — voices_read만 특별 취급하면 다음 것에서 또 막힌다."""
    msg = ev.explain_error(401, "missing the permission text_to_speech to execute")
    assert "text_to_speech" in msg


def test_plain_401_still_says_remake_the_key():
    """권한 얘기가 없는 진짜 무효 키는 종전 안내 그대로."""
    msg = ev.explain_error(401, '{"detail":"invalid_api_key"}')
    assert "새로 만들어" in msg


def test_key_id_pasted_as_key():
    """2026-08-24 사고 — 키 목록의 ID를 붙여넣은 경우."""
    assert "키 ID" in ev.explain_error(401, "API key ID used as API key")


def test_unknown_returns_empty_so_caller_keeps_its_own_message():
    """모르는 것은 빈 문자열 — 호출부가 자기 문구를 쓰게 둔다(지어내지 않는다)."""
    assert ev.explain_error(200, "ok") == ""


def test_search_surfaces_the_reason_not_just_the_code(monkeypatch):
    """★검색 화면에도 그 사유가 그대로 나와야 한다(여기가 사장님이 본 자리다)."""
    class _R:
        status_code = 401
        text = REAL_401
    monkeypatch.setattr(ev, "requests", type("Q", (), {"get": staticmethod(lambda *a, **k: _R())}))
    from shopping_shorts import tts
    monkeypatch.setattr(tts, "_api_key", lambda cid: "sk_dummy")
    out = ev.search_shared(customer_id=0)
    assert out["ok"] is False
    assert "voices_read" in out["error"]
    assert "HTTP 401" not in out["error"]
