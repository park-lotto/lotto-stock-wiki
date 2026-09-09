# -*- coding: utf-8 -*-
"""타입캐스트 403(2026-09-05 고객 cid 260: 14일간 잡 21건 전부 with-timestamps 403, 등록 검사는 통과).
① 타임스탬프 엔드포인트가 403/404면 일반 엔드포인트로 한 번 더 ② 키 등록 검사는 실제 합성으로 ③ 문구는 요금제·크레딧 안내."""
import base64
import os
import tempfile


class _R:
    def __init__(self, code, js=None, text=""):
        self.status_code = code; self._js = js; self.text = text or ("" if js is None else "{}")

    def json(self):
        return self._js

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"{self.status_code} Client Error: Forbidden for url: x", response=self)


def test_타임스탬프_403이면_일반_엔드포인트로_다시_시도해_영상은_나온다(monkeypatch):
    from shopping_shorts import typecast_tts as T
    calls = []

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append(url)
        if url == T._ENDPOINT_TS:
            return _R(403, text="Forbidden")
        return _R(200, {"audio": base64.b64encode(b"MP3").decode()})
    monkeypatch.setattr(T.requests, "post", fake_post)
    monkeypatch.setattr(T, "api_key", lambda cid=0: "k")
    out = os.path.join(tempfile.mkdtemp(), "a.mp3")
    align = T.synthesize("안녕", out, voice_id="v1")
    assert calls == [T._ENDPOINT_TS, T._ENDPOINT] and open(out, "rb").read() == b"MP3" and align is None


def test_둘_다_거부면_오류를_올린다(monkeypatch):
    import pytest
    from shopping_shorts import typecast_tts as T
    monkeypatch.setattr(T.requests, "post", lambda url, **k: _R(403, text="Forbidden"))
    monkeypatch.setattr(T, "api_key", lambda cid=0: "k")
    with pytest.raises(Exception):
        T.synthesize("안녕", os.path.join(tempfile.mkdtemp(), "a.mp3"), voice_id="v1")


def test_키_등록_검사는_실제_합성으로_403을_잡는다(monkeypatch):
    from shopping_shorts import app as A, keyroute
    monkeypatch.setattr(A.requests, "get", lambda url, headers=None, timeout=None: _R(200, [{"voice_id": "v1", "name": "x"}]))
    monkeypatch.setattr(A.requests, "post", lambda url, headers=None, json=None, timeout=None: _R(403, text="Forbidden"))
    assert A._probe_typecast_synth(keyroute.SVC_TYPECAST, "k") is False
    why = A._take_key_failure()
    assert "요금제" in why and "크레딧" in why and "값을 다시" not in why
    monkeypatch.setattr(A.requests, "post", lambda url, headers=None, json=None, timeout=None: _R(200, {"audio": "QUJD"}))
    assert A._probe_typecast_synth(keyroute.SVC_TYPECAST, "k") is True


def test_고객_화면_문구는_타입캐스트_403을_요금제로_안내한다():
    from shopping_shorts.app import _user_facing_error as f
    m = f("403 Client Error: Forbidden for url: https://api.typecast.ai/v1/text-to-speech/with-timestamps")
    assert "타입캐스트" in m and "요금제" in m and "ElevenLabs" not in m and "오류 신고" in m
