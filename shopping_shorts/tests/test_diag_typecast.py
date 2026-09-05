# -*- coding: utf-8 -*-
"""타입캐스트 진단(2026-09-05 cid 260: 키·요금제·크레딧 정상인데 403) — 업체 본문을 잡 오류·관리자 진단에 싣는다."""
import os
import tempfile


class _R:
    def __init__(self, code, js=None, text="", url="u"):
        self.status_code = code; self._js = js; self.text = text or ("" if js is None else "{}")
        self.reason = "Forbidden" if code == 403 else ""; self.url = url

    def json(self):
        return self._js


def test_잡_오류에_업체_본문이_실린다(monkeypatch):
    import pytest
    from shopping_shorts import typecast_tts as T
    monkeypatch.setattr(T.requests, "post", lambda url, **k: _R(403, text='{"detail":"voice not accessible"}', url=url))
    monkeypatch.setattr(T, "api_key", lambda cid=0: "k")
    with pytest.raises(T.requests.HTTPError) as ei:
        T.synthesize("안녕", os.path.join(tempfile.mkdtemp(), "a.mp3"), voice_id="uc_1")
    assert "403" in str(ei.value) and "voice not accessible" in str(ei.value)


def test_관리자_진단은_회원키로_세_단계를_치고_키값은_안_싣는다(monkeypatch):
    from shopping_shorts import app as A, keyroute
    monkeypatch.setattr(keyroute, "keys_for", lambda store, cid, svc: (["SECRETKEY123"], True))
    calls = []

    def fake_get(url, headers=None, timeout=None):
        calls.append(("get", url, headers["X-API-KEY"]))
        return _R(200, [{"voice_id": "tc_a"}, {"voice_id": "tc_b"}])

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(("post", url, json["voice_id"]))
        return _R(403, text="Forbidden: custom voice")
    out = A.diag_typecast(object(), 260, voice_id="uc_zzz", get=fake_get, post=fake_post)
    assert out["ok"] and out["own_key"] is True and out["key_len"] == 12
    assert "SECRETKEY123" not in repr(out)
    assert out["voices_count"] == 2 and out["voice_in_list"] is False
    steps = {s["step"]: s for s in out["steps"]}
    assert steps["voices"]["status"] == 200
    assert steps["with_timestamps"]["status"] == 403 and "custom voice" in steps["with_timestamps"]["body"]
    assert steps["plain"]["status"] == 403
    assert [c[2] for c in calls if c[0] == "post"] == ["uc_zzz", "uc_zzz"]


def test_진단은_키_없으면_그_사실을_돌려준다(monkeypatch):
    from shopping_shorts import app as A, keyroute
    monkeypatch.setattr(keyroute, "keys_for", lambda store, cid, svc: ([], False))
    out = A.diag_typecast(object(), 1)
    assert out["ok"] is False and "키 없음" in out["error"]


def test_diag_work가_목소리_스냅샷을_요약한다():
    from shopping_shorts.app import _diag_voice
    v = _diag_voice({"voice_id": "uc_abc", "model_id": "ssfm-v30", "preset_id": "p1", "settings": {"x": 1}})
    assert v == {"voice_id": "uc_abc", "model_id": "ssfm-v30", "preset_id": "p1", "engine": "typecast", "voice_kind": "custom(uc_)"}
    assert _diag_voice({"voice_id": "abc", "model_id": "eleven_v3"})["engine"] == "elevenlabs"
    assert _diag_voice(None) is None
