# -*- coding: utf-8 -*-
"""Vertex 3.6 스위치(2026-09-25 사장님 "내거로 대본추출과 장면매칭에 3.6 스위치 켜봐").

계약: 꺼져 있으면 종전과 한 글자도 안 다르다 · 켜지면 Vertex 먼저 · Vertex가 죽으면 종전 키풀."""
import types as _t

import pytest

from shopping_shorts import vertex_route as vr


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    vr.reset_cache()
    monkeypatch.setattr(vr, "member_info", lambda cid: None)   # 회원 자격증명 없음이 기본
    yield
    vr.reset_cache()


def _settings(monkeypatch, enabled="", ops="", model=""):
    monkeypatch.setattr(vr, "_read_settings", lambda: {
        vr.SETTING_ENABLED: enabled, vr.SETTING_OPS: ops, vr.SETTING_MODEL: model})


def test_off_by_default_and_unknown_op(monkeypatch):
    _settings(monkeypatch)                      # 설정 없음
    monkeypatch.setattr(vr, "current_cid", lambda: 0)
    assert vr.on("script_extract") is False
    _settings(monkeypatch, enabled="1")
    assert vr.on("no_such_op") is False


def test_admin_gate_and_ops_list(monkeypatch):
    _settings(monkeypatch, enabled="admin", ops="script_extract,ai_match")
    monkeypatch.setattr(vr, "_is_admin", lambda cid: cid == 0)
    assert vr.on("script_extract", cid=0) is True
    assert vr.on("frame_script", cid=0) is False        # 목록에 없음
    assert vr.on("script_extract", cid=77) is False     # 관리자 아님
    _settings(monkeypatch, enabled="1")
    assert vr.on("frame_script", cid=77) is True         # 전체 · 목록 비면 전부
    _settings(monkeypatch, enabled="11,42")
    assert vr.on("ai_match", cid=42) is True and vr.on("ai_match", cid=43) is False


def test_model_default_and_override(monkeypatch):
    _settings(monkeypatch, enabled="1")
    assert vr.model() == "gemini-3.6-flash"
    _settings(monkeypatch, enabled="1", model="gemini-3.5-flash-lite")
    assert vr.model() == "gemini-3.5-flash-lite"


def test_try_call_off_returns_not_tried(monkeypatch):
    _settings(monkeypatch)
    called = []
    ok, got = vr.try_call("script_extract", lambda cl, m: called.append(1) or "x")
    assert (ok, got) == (False, None) and not called


def test_try_call_uses_vertex_client_and_model_then_falls_back_on_error(monkeypatch):
    _settings(monkeypatch, enabled="1", model="gemini-3.6-flash")
    fake = _t.SimpleNamespace(name="vertex-client")
    monkeypatch.setattr(vr, "client", lambda *a, **k: fake)
    seen = {}
    def fn(cl, m):
        seen.update(cl=cl, m=m)
        return {"ok": 1}
    ok, got = vr.try_call("ai_match", fn)
    assert ok is True and got == {"ok": 1}
    assert seen["cl"] is fake and seen["m"] == "gemini-3.6-flash"
    # 예외 → (False, None): 호출부가 키풀로 간다. 예외가 새 나가면 본작업이 죽는다.
    def boom(cl, m):
        raise RuntimeError("503 UNAVAILABLE")
    assert vr.try_call("ai_match", boom) == (False, None)
    # 빈 결과도 실패로 본다(조용한 빈 값 금지)
    assert vr.try_call("ai_match", lambda cl, m: []) == (False, None)


def test_video_part_respects_inline_cap(monkeypatch, tmp_path):
    p = tmp_path / "v.mp4"
    p.write_bytes(b"\x00" * 10)
    monkeypatch.setattr(vr, "INLINE_MAX_BYTES", 5)
    assert vr.video_part(str(p)) is None
    monkeypatch.setattr(vr, "INLINE_MAX_BYTES", 100)
    part = vr.video_part(str(p))
    assert part is not None and part.inline_data.mime_type == "video/mp4"
    assert vr.video_part(str(tmp_path / "missing.mp4")) is None


def test_client_is_vertex_global_and_metered(monkeypatch):
    """클라이언트는 vertexai=True · location=global · 계측 auth=vertex 로만 만든다."""
    made = {}
    class FakeClient:
        def __init__(self, **kw):
            made.update(kw)
    import google.genai as genai
    monkeypatch.setattr(genai, "Client", FakeClient)
    from shopping_shorts import usage_meter
    wrapped = {}
    def fake_wrap(cl, auth="apikey", pool=None, key=None):
        wrapped.update(auth=auth, pool=pool)
        return cl
    monkeypatch.setattr(usage_meter, "wrap", fake_wrap)
    cl = vr.client()
    assert made["vertexai"] is True and made["location"] == "global" and made["project"]
    assert wrapped == {"auth": "vertex", "pool": "vertex"}
    assert vr.client() is cl                     # 캐시
