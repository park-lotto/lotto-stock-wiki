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
    """auto는 무음 전체가 아니라 **여백(_TRIM_SAFETY_PAD)을 남기고** 자른다.
    ★2026-09-22 변경: 전부 자르면 첫/끝 음절 앞의 자연스러운 들숨이 사라져 말이 튄다."""
    _seed(monkeypatch)
    monkeypatch.setattr(appmod, "detect_edge_silence", lambda p, e: 0.8, raising=False)
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim",
               json={"beat_idx": 0, "edge": "tail", "mode": "auto"})
    assert abs(r.json()["tail_trim"] - (0.8 - appmod._TRIM_SAFETY_PAD)) < 1e-6


def test_trim_auto_never_negative_on_short_silence(monkeypatch):
    """무음이 여백보다 짧으면 0 — 음수 트림으로 소리를 늘리면 안 된다."""
    _seed(monkeypatch)
    monkeypatch.setattr(appmod, "detect_edge_silence", lambda p, e: 0.03, raising=False)
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim",
               json={"beat_idx": 0, "edge": "tail", "mode": "auto"})
    assert r.json()["tail_trim"] == 0.0


def test_trim_set_stores_absolute_value(monkeypatch):
    """파형 드래그 → mode=set은 끈 위치를 그대로 저장한다(누적 아님)."""
    _seed(monkeypatch, beat={"beat_idx": 0, "narration": "가",
                             "tts_path": "a.mp3", "head_trim": 0.9})
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim",
               json={"beat_idx": 0, "edge": "head", "mode": "set", "value": 0.25})
    assert abs(r.json()["head_trim"] - 0.25) < 1e-6


def test_trim_set_clamped_by_floor(monkeypatch):
    """probe 5.0초 · floor 0.4초 → head+tail이 4.6초를 넘게 끌면 가드가 막는다."""
    _seed(monkeypatch, beat={"beat_idx": 0, "narration": "가",
                             "tts_path": "a.mp3", "tail_trim": 0.0})
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim",
               json={"beat_idx": 0, "edge": "head", "mode": "set", "value": 99.0})
    assert r.json()["head_trim"] <= 5.0 - appmod._TRIM_FLOOR + 1e-6
    assert r.json()["head_trim"] > 0


def test_trim_all_trims_every_beat(monkeypatch):
    """전 칸 한 번에 — 호출 1회로 모든 비트의 앞·뒤가 잘린다."""
    beats = [{"beat_idx": i, "narration": "가", "tts_path": f"{i}.mp3"} for i in range(3)]
    job = {"status": "ready_for_review", "edit_plan": {"beats": beats}}

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, jid): return job
        def update_mix_job(self, jid, **f): pass

    monkeypatch.setattr(appmod, "Store", FakeStore)
    monkeypatch.setattr(appmod, "_probe_duration", lambda p: 5.0, raising=False)
    monkeypatch.setattr(appmod, "detect_edge_silence", lambda p, e: 0.5, raising=False)
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim_all", json={"mode": "auto"})
    assert r.status_code == 200 and r.json()["changed"] == 3
    for b in beats:
        assert abs(b["head_trim"] - (0.5 - appmod._TRIM_SAFETY_PAD)) < 1e-6
        assert abs(b["tail_trim"] - (0.5 - appmod._TRIM_SAFETY_PAD)) < 1e-6


def test_trim_all_reset_zeroes_everything(monkeypatch):
    beats = [{"beat_idx": i, "narration": "가", "tts_path": f"{i}.mp3",
              "head_trim": 0.4, "tail_trim": 0.6} for i in range(2)]
    job = {"status": "ready_for_review", "edit_plan": {"beats": beats}}

    class FakeStore:
        def __init__(self, *a, **k): pass
        def get_mix_job(self, jid): return job
        def update_mix_job(self, jid, **f): pass

    monkeypatch.setattr(appmod, "Store", FakeStore)
    monkeypatch.setattr(appmod, "_probe_duration", lambda p: 5.0, raising=False)
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim_all", json={"mode": "reset"})
    assert r.json()["changed"] == 2
    for b in beats:
        assert b["head_trim"] == 0.0 and b["tail_trim"] == 0.0


def test_trim_all_blocked_while_rendering(monkeypatch):
    _seed(monkeypatch, status="rendering")
    c = TestClient(appmod.app)
    r = c.post("/api/produce/mix/J/trim_all", json={"mode": "auto"})
    assert r.status_code == 409


def test_wave_returns_peaks_and_silence(monkeypatch):
    """파형 API는 막대·길이·앞뒤 무음·현재 트림을 한 번에 준다."""
    _seed(monkeypatch, beat={"beat_idx": 0, "narration": "가",
                             "tts_path": "a.mp3", "head_trim": 0.2})
    monkeypatch.setattr(appmod.os.path, "exists", lambda p: True)
    monkeypatch.setattr(appmod, "extract_peaks", lambda p: [0.1, 0.9, 0.1], raising=False)
    monkeypatch.setattr(appmod, "detect_edge_silence",
                        lambda p, e: 0.3 if e == "head" else 0.7, raising=False)
    c = TestClient(appmod.app)
    r = c.get("/api/produce/mix/J/wave/0")
    d = r.json()
    assert d["peaks"] == [0.1, 0.9, 0.1]
    assert d["dur"] == 5.0 and d["head_sil"] == 0.3 and d["tail_sil"] == 0.7
    assert d["head_trim"] == 0.2


def test_wave_missing_audio_is_not_an_error(monkeypatch):
    """음성 파일이 없어도 500이 아니라 빈 파형 — 화면은 트림 버튼만 보여주면 된다."""
    _seed(monkeypatch, beat={"beat_idx": 0, "narration": "가", "tts_path": None})
    c = TestClient(appmod.app)
    r = c.get("/api/produce/mix/J/wave/0")
    assert r.status_code == 200 and r.json()["peaks"] == []
