# -*- coding: utf-8 -*-
"""Vertex 스위치가 붙은 세 호출부 — 켜지면 Vertex 먼저, 실패하면 종전 키풀 그대로(2026-09-25).

★꺼져 있을 때 종전과 같은지는 기존 테스트가 지킨다. 여기서는 켜진 상태만 본다."""
import json
import types as _t

import pytest

from shopping_shorts import vertex_route as vr


class _Resp:
    def __init__(self, obj):
        self.text = json.dumps(obj, ensure_ascii=False)


def _client(answer=None, error=None, name="c"):
    """models.generate_content가 answer(JSON)를 주거나 error를 던지는 가짜 클라이언트."""
    calls = []
    def gen(**kw):
        calls.append(kw)
        if error is not None:
            raise error
        return _Resp(answer)
    cl = _t.SimpleNamespace(name=name, calls=calls, models=_t.SimpleNamespace(generate_content=gen))
    return cl


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    vr.reset_cache()
    monkeypatch.setattr(vr, "on", lambda op, cid=None: True)
    monkeypatch.setattr(vr, "model", lambda: "gemini-3.6-flash")
    yield
    vr.reset_cache()


# ── frame_script._call_with_key_rotation ─────────────────────────────────────
def test_rotation_tries_vertex_first_and_skips_keys_on_success(monkeypatch):
    from shopping_shorts import frame_script, comment_gen
    vcl = _client(name="vertex")
    monkeypatch.setattr(vr, "client", lambda: vcl)
    monkeypatch.setattr(comment_gen, "_current_key_and_idx",
                        lambda: pytest.fail("Vertex 성공인데 키풀을 건드렸다"))
    seen = []
    got = frame_script._call_with_key_rotation(lambda cl, m: seen.append((cl.name, m)) or "ok", what="t")
    assert got == "ok" and seen == [("vertex", "gemini-3.6-flash")]


def test_rotation_falls_back_to_keys_when_vertex_fails(monkeypatch):
    from shopping_shorts import frame_script, comment_gen
    monkeypatch.setattr(vr, "client", lambda: _client(name="vertex"))
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k1", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _client(name="key:" + k))
    def make_call(cl, m):
        if cl.name == "vertex":
            raise RuntimeError("503 UNAVAILABLE")
        return "from-" + cl.name + "/" + m
    got = frame_script._call_with_key_rotation(make_call, what="t")
    assert got == "from-key:k1/" + frame_script.TAG_MODELS[0]


# ── frame_script._gemini_tag_frames ──────────────────────────────────────────
def test_tag_frames_uses_vertex_then_keys_share_same_parser(monkeypatch, tmp_path):
    from shopping_shorts import frame_script, comment_gen
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff")
    segs = [{"start": 0, "end": 2, "text": "a"}, {"start": 2, "end": 4, "text": "b"}]
    tags = {"tags": [{"seg_no": 1, "scene_desc": "손에 제품", "label": "x"},
                     {"seg_no": 2, "scene_desc": "집게질", "label": "y"}]}
    vcl = _client(answer=tags, name="vertex")
    monkeypatch.setattr(vr, "client", lambda: vcl)
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k1", 0))
    kcl = _client(answer=tags, name="key")
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: kcl)
    out = frame_script._gemini_tag_frames([[str(img)], [str(img)]], "cap", segs)
    assert [t.get("scene_desc") for t in out] == ["손에 제품", "집게질"]
    assert len(vcl.calls) == 1 and kcl.calls == [], "Vertex가 답했으면 키풀은 안 부른다"
    assert vcl.calls[0]["model"] == "gemini-3.6-flash"
    # Vertex가 죽으면 같은 해석기로 키풀 결과를 쓴다
    vbad = _client(error=RuntimeError("503 UNAVAILABLE"), name="vertex")
    monkeypatch.setattr(vr, "client", lambda: vbad)
    out2 = frame_script._gemini_tag_frames([[str(img)], [str(img)]], "cap", segs)
    assert [t.get("scene_desc") for t in out2] == ["손에 제품", "집게질"]
    assert len(kcl.calls) == 1


# ── ai_match.match ───────────────────────────────────────────────────────────
def test_ai_match_vertex_first_then_call_json(monkeypatch):
    from shopping_shorts import ai_match, script_generate as sg
    seg_index = {"v1-0": {"vid": "v1", "secs": 2.0, "desc": "손에 끼움", "role": "method"}}
    lines = [{"role": "method", "text": "손에 끼우고 집기만 하면 끝."}]
    vcl = _client(answer={"picks": [{"line": 1, "cuts": ["v1-0"], "why": "동작"}]}, name="vertex")
    monkeypatch.setattr(vr, "client", lambda: vcl)
    monkeypatch.setattr(sg, "_call_json", lambda *a, **k: pytest.fail("Vertex 성공인데 키풀을 불렀다"))
    note = {}
    out = ai_match.match(lines, seg_index, "seed", note=note)
    assert out and out[0]["segs"] == ["v1-0"] and note.get("matcher_auth") == "vertex"
    assert vcl.calls[0]["model"] == "gemini-3.6-flash"
    # 실패 → 종전 _call_json
    monkeypatch.setattr(vr, "client", lambda: _client(error=RuntimeError("429"), name="vertex"))
    monkeypatch.setattr(sg, "_call_json", lambda *a, **k: {"picks": [{"line": 1, "cuts": ["v1-0"], "why": "k"}]})
    out2 = ai_match.match(lines, seg_index, "seed", note={})
    assert out2 and out2[0]["segs"] == ["v1-0"]


# ── script_extract.extract_script ────────────────────────────────────────────
def _stub_extract_pipeline(monkeypatch):
    from shopping_shorts import script_extract as se
    monkeypatch.setattr(se, "SHORTS_GEMINI_KEYS", ["k"])
    monkeypatch.setattr(se, "_boundary_hint", lambda p: ("", [], 30.0))
    monkeypatch.setattr(se, "_video_duration", lambda p: 10.0)
    monkeypatch.setattr(se, "_merge_too_short", lambda s: s)
    monkeypatch.setattr(se, "_snap_to_cuts", lambda s, c, f: s)
    monkeypatch.setattr(se, "_compute_motion_map", lambda *a, **k: {})
    monkeypatch.setattr(se, "_assign_seg_ids", lambda vid, s, motion_map=None: s)
    monkeypatch.setattr(se, "_qa_retry_decision", lambda r, d, q: (False, ""))
    monkeypatch.setattr(se, "_attach_qa", lambda r, *a, **k: r)
    monkeypatch.setattr(se, "_wait_until_active", lambda cl, f: f)
    return se


def test_extract_uses_vertex_inline_video_first(monkeypatch, tmp_path):
    se = _stub_extract_pipeline(monkeypatch)
    from shopping_shorts import comment_gen
    vid = tmp_path / "v.mp4"
    vid.write_bytes(b"\x00" * 100)
    answer = {"segments": [{"start": 0, "end": 2, "text": "안녕"}], "full_text": "안녕"}
    vcl = _client(answer=answer, name="vertex")
    monkeypatch.setattr(vr, "client", lambda: vcl)
    monkeypatch.setattr(vr, "video_part", lambda p: _t.SimpleNamespace(kind="inline", path=p))
    monkeypatch.setattr(comment_gen, "_current_key_and_idx",
                        lambda: pytest.fail("Vertex 성공인데 키풀을 건드렸다"))
    out = se.extract_script(str(vid), "vid1", caption="c")
    assert out["full_text"] == "안녕" and len(out["segments"]) == 1
    call = vcl.calls[0]
    assert call["model"] == "gemini-3.6-flash"
    assert getattr(call["contents"][0], "kind", "") == "inline", "Vertex엔 Files API가 없다 — 인라인이어야"


def test_extract_falls_back_to_key_upload_when_vertex_fails(monkeypatch, tmp_path):
    se = _stub_extract_pipeline(monkeypatch)
    from shopping_shorts import comment_gen
    vid = tmp_path / "v.mp4"
    vid.write_bytes(b"\x00" * 100)
    monkeypatch.setattr(vr, "client", lambda: _client(error=RuntimeError("503 UNAVAILABLE"), name="vertex"))
    monkeypatch.setattr(vr, "video_part", lambda p: _t.SimpleNamespace(kind="inline"))
    answer = {"segments": [{"start": 0, "end": 2, "text": "키풀"}], "full_text": "키풀"}
    kcl = _client(answer=answer, name="key")
    uploaded = []
    kcl.files = _t.SimpleNamespace(upload=lambda **kw: uploaded.append(1) or _t.SimpleNamespace(name="f1"),
                                   delete=lambda **kw: None)
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: kcl)
    out = se.extract_script(str(vid), "vid1", caption="c")
    assert out["full_text"] == "키풀" and uploaded == [1]
    assert kcl.calls[0]["model"] == se._MODEL, "Vertex 실패 뒤 모델은 종전 기본으로 돌아가야"
