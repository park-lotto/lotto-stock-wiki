# -*- coding: utf-8 -*-
"""대본생성 깔때기(script_generate._call_json)에 Vertex 스위치 — 2026-09-26 사장님
"태깅은 무료로, 대본작성과 장면매칭이 얼마나 잘되는지 해보자".

_call_json은 이야기 작가(특징·본문)·백본·옛 생성기·판정이 전부 지나는 한 곳이라 여기 한 번이면 대본생성 전체가 간다."""
import json
import types as _t

import pytest

from shopping_shorts import script_generate as sg
from shopping_shorts import vertex_route as vr


class _Resp:
    def __init__(self, obj):
        self.text = json.dumps(obj, ensure_ascii=False)


def _client(answer=None, error=None, name="c"):
    calls = []
    def gen(**kw):
        calls.append(kw)
        if error is not None:
            raise error
        return _Resp(answer)
    return _t.SimpleNamespace(name=name, calls=calls, models=_t.SimpleNamespace(generate_content=gen))


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    vr.reset_cache()
    monkeypatch.setattr(vr, "on", lambda op, cid=None: True)
    monkeypatch.setattr(vr, "model", lambda: "gemini-3.6-flash")
    yield
    vr.reset_cache()


SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}


def test_script_generate_is_a_switchable_op():
    assert "script_generate" in vr.OPS


def test_call_json_uses_vertex_first_and_marks_note(monkeypatch):
    vcl = _client(answer={"a": "vertex"}, name="vertex")
    monkeypatch.setattr(vr, "client", lambda: vcl)
    monkeypatch.setattr(sg.keyroute, "gemini_keys", lambda *_a, **_k: pytest.fail("Vertex 성공인데 키풀을 건드렸다"))
    note = {}
    out = sg._call_json("p", SCHEMA, note=note)
    assert out == {"a": "vertex"} and note.get("auth") == "vertex"
    kw = vcl.calls[0]
    assert kw["model"] == "gemini-3.6-flash" and kw["contents"] == "p"
    assert kw["config"].response_schema == SCHEMA and kw["config"].response_mime_type == "application/json"


def test_call_json_falls_back_to_keypool_when_vertex_fails(monkeypatch):
    monkeypatch.setattr(vr, "client", lambda: _client(error=RuntimeError("503 UNAVAILABLE"), name="vertex"))
    monkeypatch.setattr(sg.keyroute, "gemini_keys", lambda *_a, **_k: ["k1"])
    monkeypatch.setattr(sg.key_vault, "pick_paced_key", lambda pool: pool[0])
    kcl = _client(answer={"a": "key"}, name="key")
    monkeypatch.setattr(sg.key_vault, "get_client_for_key", lambda k: kcl)
    note = {}
    assert sg._call_json("p", SCHEMA, note=note) == {"a": "key"}
    assert note.get("auth") != "vertex" and kcl.calls[0]["model"] == sg._MODEL


def test_call_json_vertex_false_skips_vertex(monkeypatch):
    """ai_match처럼 자기 Vertex 시도를 이미 한 호출부는 두 번 두드리지 않는다."""
    monkeypatch.setattr(vr, "client", lambda: pytest.fail("vertex=False인데 Vertex를 불렀다"))
    monkeypatch.setattr(sg.keyroute, "gemini_keys", lambda *_a, **_k: ["k1"])
    monkeypatch.setattr(sg.key_vault, "pick_paced_key", lambda pool: pool[0])
    monkeypatch.setattr(sg.key_vault, "get_client_for_key", lambda k: _client(answer={"a": "key"}))
    assert sg._call_json("p", SCHEMA, vertex=False) == {"a": "key"}
