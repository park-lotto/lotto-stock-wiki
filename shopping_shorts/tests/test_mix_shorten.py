"""✂ 대사 줄이기 — 경고만 뜨던 '대사가 영상보다 김' 비트를 화면 예산에 맞게 축약+재TTS
(2026-07-22 사장님: 경고 뜨면 버튼으로 고쳐지게 되야 한다)."""
from fastapi.testclient import TestClient
import shopping_shorts.app as app_mod
import shopping_shorts.mix_pipeline as mp
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_mod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(app_mod, "run_mix_job", lambda *a, **k: None)
    # 재TTS는 파일 합성 없이 통과, probe는 축약분만큼 짧게 흉내.
    monkeypatch.setattr(mp, "synthesize_line", lambda *a, **k: "")
    monkeypatch.setattr(mp, "_probe_duration", lambda p: 2.0)
    monkeypatch.setattr(mp, "_MAX_SLOWMO", 1.0)
    Store(app_mod.DB_PATH)
    return TestClient(app_mod.app), Store(app_mod.DB_PATH)


def _seed(store, gap=1.5):
    store.create_mix_job("j1", ["u0", "u1"], 20, "free")
    plan = {"beats": [{
        "beat_idx": 0, "narration": "이거 정말 너무 아주 완전 길게 늘어지는 대사예요 진짜로요",
        "role": "훅", "sync_gap": gap,
        "primary": {"seg_id": "s0-0", "start": 0.0, "end": 2.0},
        "alternates": []}]}
    store.update_mix_job("j1", edit_plan=plan)


def test_shorten_updates_narration_and_syncgap(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(app_mod._edit_plan, "conform_narration", lambda n, b, **k: "짧은 대사")
    _seed(store)
    r = client.post("/api/produce/mix/j1/shorten", json={"beat_idx": 0})
    d = r.json()
    assert d["ok"] and d["changed"] is True
    beat = store.get_mix_job("j1")["edit_plan"]["beats"][0]
    assert beat["narration"] == "짧은 대사"
    assert beat["sync_gap"] == 0.0            # 2.0 TTS ≤ budget(2.0) → gap 0
    assert beat["caption_lines"] is None       # 대사 바뀌어 자막줄 무효화


def test_shorten_no_change_when_cannot_reduce(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(app_mod._edit_plan, "conform_narration", lambda n, b, **k: None)
    _seed(store)
    r = client.post("/api/produce/mix/j1/shorten", json={"beat_idx": 0})
    assert r.json() == {"ok": True, "changed": False,
                        "narration": "이거 정말 너무 아주 완전 길게 늘어지는 대사예요 진짜로요",
                        "note": "더 줄일 여지가 없어요(뜻 훼손 없이)"}


def test_shorten_blocks_while_rendering(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    _seed(store)
    store.update_mix_job("j1", status="rendering")
    r = client.post("/api/produce/mix/j1/shorten", json={"beat_idx": 0})
    assert r.status_code == 409
