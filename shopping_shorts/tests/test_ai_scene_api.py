# -*- coding: utf-8 -*-
"""AI 장면 생성 API — 스위치(기본 관리자만)·중복·렌더 중 거부·큐잉."""
import json

from shopping_shorts import app as A


class _Req:
    class state:
        customer_id = 0


class _Store:
    def __init__(self, job, setting="", alive=False):
        self.job = job; self.setting = setting; self.alive = alive; self.queued = []; self.saved = []
    def get_mix_job(self, j): return self.job
    def get_setting(self, k, d=None): return self.setting if k == "ai_scene_enabled" else d
    def task_is_alive(self, task, args, stale_minutes=3): return self.alive
    def enqueue(self, task, args, owner=None, prio=None): self.queued.append((task, args)); return 42
    def update_mix_job(self, j, **kw): self.saved.append(kw); self.job.update(kw)


def _job(status="ready_for_review"):
    return {"job_id": "j", "status": status, "customer_id": 0,
            "edit_plan": {"beats": [{"beat_idx": 0, "role": "훅", "narration": "a"}, {"beat_idx": 1, "narration": "b"}]}}


def _body(r):
    return r if isinstance(r, dict) else json.loads(bytes(r.body).decode())


def test_default_setting_means_admin_only(monkeypatch):
    st = _Store(_job(), setting="")
    monkeypatch.setattr(A, "Store", lambda db: st)
    monkeypatch.setattr(A, "_is_admin", lambda cid: cid == 0)
    monkeypatch.setattr(A, "_save_render_inputs", lambda s, j, **kw: st.update_mix_job(j, **kw))
    r = A.api_produce_mix_ai_scene("j", _Req(), {"beat_idx": 0, "style": "impact"})
    assert _body(r)["ok"] is True and st.queued == [("ai_scene", {"job_id": "j", "beat_idx": 0, "style": "impact"})]
    assert st.job["edit_plan"]["beats"][0]["ai_scene"]["state"] == "queued"
    class _Cust(_Req):
        class state: customer_id = 42
    r = A.api_produce_mix_ai_scene("j", _Cust(), {"beat_idx": 0})
    assert getattr(r, "status_code", 200) == 403


def test_refuses_duplicate_and_rendering(monkeypatch):
    st = _Store(_job(), setting="1", alive=True)
    monkeypatch.setattr(A, "Store", lambda db: st)
    r = A.api_produce_mix_ai_scene("j", _Req(), {"beat_idx": 1})
    assert getattr(r, "status_code", 200) == 409 and st.queued == []
    st2 = _Store(_job(status="rendering"), setting="1")
    monkeypatch.setattr(A, "Store", lambda db: st2)
    r = A.api_produce_mix_ai_scene("j", _Req(), {"beat_idx": 1})
    assert getattr(r, "status_code", 200) == 409


def test_bad_beat_and_style_fallback(monkeypatch):
    st = _Store(_job(), setting="1")
    monkeypatch.setattr(A, "Store", lambda db: st)
    monkeypatch.setattr(A, "_save_render_inputs", lambda s, j, **kw: None)
    assert getattr(A.api_produce_mix_ai_scene("j", _Req(), {"beat_idx": 9}), "status_code", 200) == 422
    r = A.api_produce_mix_ai_scene("j", _Req(), {"beat_idx": 1, "style": "weird"})
    assert _body(r)["style"] == "natural"


def test_produce_html_has_button_and_polling():
    from pathlib import Path
    html = Path(A.__file__).parent.joinpath("static", "produce.html").read_text(encoding="utf-8")
    assert "renderAiSceneBtn" in html and "startAiScene(" in html and "pollAiScene(" in html
    assert "/ai_scene'" in html and "AI 장면 만들기" in html and "임팩트로" in html
    assert "MIX_AI_SCENE_ON = !!d.ai_scene_enabled" in html
