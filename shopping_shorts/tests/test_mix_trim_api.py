import shopping_shorts.app as appmod
from fastapi.testclient import TestClient


def _seed(monkeypatch, status="ready_for_review", beat=None):
    beat = beat or {"beat_idx": 0, "narration": "가", "tts_path": "a.mp3"}
    job = {"status": status, "edit_plan": {"beats": [beat]}}
    saved = {}

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, jid): return job
        def update_mix_job(self, jid, **f): saved.update(f)

    monkeypatch.setattr(appmod, "Store", FakeStore)
    monkeypatch.setattr(appmod, "_probe_duration", lambda p: 5.0, raising=False)
    return job, saved


def test_trim_nudge_accumulates(monkeypatch):
    job, saved = _seed(monkeypatch)
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim",
               json={"beat_idx": 0, "edge": "tail", "mode": "nudge", "step": 0.3})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert abs(r.json()["tail_trim"] - 0.3) < 1e-6


def test_trim_reset_zeroes_edge(monkeypatch):
    job, saved = _seed(monkeypatch, beat={"beat_idx": 0, "narration": "가",
                                          "tts_path": "a.mp3", "tail_trim": 1.2})
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim",
               json={"beat_idx": 0, "edge": "tail", "mode": "reset"})
    assert r.json()["tail_trim"] == 0.0


def test_trim_blocked_while_rendering(monkeypatch):
    _seed(monkeypatch, status="rendering")
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim",
               json={"beat_idx": 0, "edge": "tail", "mode": "nudge"})
    assert r.status_code == 409


def test_trim_auto_uses_silence(monkeypatch):
    _seed(monkeypatch)
    monkeypatch.setattr(appmod, "detect_edge_silence", lambda p, e: 0.8, raising=False)
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim",
               json={"beat_idx": 0, "edge": "tail", "mode": "auto"})
    assert abs(r.json()["tail_trim"] - 0.8) < 1e-6
