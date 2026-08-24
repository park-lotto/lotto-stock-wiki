# -*- coding: utf-8 -*-
"""일레븐랩스 키 확인이 **권한 좁은 키**를 죽었다고 오진하지 않는가 (2026-08-24 실사고).

## 무엇이 있었나

고객이 키를 등록했는데 화면에 **"● 키가 틀렸습니다"**가 떴다.
라이브 실측(cid 184) 결과 키는 **멀쩡했다**:

    GET /v1/user   → 401  "missing the permission user_read"
    GET /v1/voices → 200
    POST TTS       → 200  (음성 16,762바이트 정상 생성)

일레븐랩스 키는 **권한(scope)을 좁게 만들 수 있다.** 고객이 그렇게 만들면 TTS는 되는데
`/v1/user`만 막힌다. 그런데 확인 로직이 `/v1/user` 하나만 봐서 "틀렸다"고 단정했다.

★돈 내고 키까지 등록한 고객이 **자기 키가 죽은 줄 안다** — 제일 나쁜 오진이다.
★판정은 "우리가 실제로 쓰는 기능이 되는가"로 해야 한다
  (CLAUDE.md 0순위-B: "진짜 판정은 실제로 데이터가 나오는가로 하라").
"""
import pytest

import shopping_shorts.app as app
from shopping_shorts import keyroute


# 라이브에서 실제로 돌아온 응답(2026-08-24). 문구를 바꾸지 마라 — 이게 증거다.
LIVE_401_USER = (
    '{"detail":{"type":"authentication_error","code":"unauthorized",'
    '"message":"The API key you used is missing the permission user_read '
    'to execute this operation.","status":"missing_permissions"}}'
)


class _Resp:
    def __init__(self, code, text=""):
        self.status_code = code
        self.text = text


def _fake_get(routes):
    """URL별 응답을 흉내낸다. 어느 주소를 찌르는지가 이 테스트의 요점이다."""
    def _get(url, **kw):
        for frag, resp in routes.items():
            if frag in url:
                return resp
        raise AssertionError("예상 못 한 주소를 찔렀다: %s" % url)
    return _get


def test_권한_좁은_키를_살아있다고_본다(monkeypatch):
    """★핵심 회귀. /v1/user는 401인데 /v1/voices는 200인 실제 고객 키 상황."""
    monkeypatch.setattr(app.requests, "get", _fake_get({
        "/v1/user": _Resp(401, LIVE_401_USER),
        "/v1/voices": _Resp(200),
    }))
    assert app._probe_user_key(keyroute.SVC_ELEVENLABS, "sk_test") is True


def test_진짜_죽은_키는_죽었다고_본다(monkeypatch):
    """오진을 고치려다 **아무 키나 통과**시키면 그게 더 나쁘다."""
    monkeypatch.setattr(app.requests, "get", _fake_get({
        "/v1/voices": _Resp(401, '{"detail":{"status":"invalid_api_key"}}'),
    }))
    assert app._probe_user_key(keyroute.SVC_ELEVENLABS, "sk_dead") is False


def test_user_엔드포인트를_안_찌른다(monkeypatch):
    """/v1/user를 계속 보면 권한 좁은 키가 또 걸린다 — 주소 자체를 바꿔야 한다."""
    called = []

    def _get(url, **kw):
        called.append(url)
        return _Resp(200)

    monkeypatch.setattr(app.requests, "get", _get)
    app._probe_user_key(keyroute.SVC_ELEVENLABS, "sk_test")
    assert called and "/v1/user" not in called[0], "아직 /v1/user를 본다: %s" % called
    assert "/v1/voices" in called[0]


def test_확인_버튼이_크레딧을_안_쓴다(monkeypatch):
    """★목록 조회여야 한다. 실제 합성(text-to-speech)을 부르면 확인 한 번이 돈을 쓴다."""
    called = []

    def _get(url, **kw):
        called.append(url)
        return _Resp(200)

    monkeypatch.setattr(app.requests, "get", _get)
    app._probe_user_key(keyroute.SVC_ELEVENLABS, "sk_test")
    assert not any("text-to-speech" in u for u in called)


def test_상태문자열도_ok가_된다(monkeypatch):
    """화면에 박히는 값은 _key_status다 — 여기까지 통과해야 '정상'으로 보인다."""
    monkeypatch.setattr(app.requests, "get", _fake_get({
        "/v1/voices": _Resp(200),
    }))
    assert app._key_status(keyroute.SVC_ELEVENLABS, "sk_test") == "ok"
