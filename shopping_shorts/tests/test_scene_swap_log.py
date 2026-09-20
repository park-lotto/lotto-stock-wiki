"""칸 타임라인 ⑧ 교체 로그 — AI 픽을 사람이 뭘로 바꿨는지 기록만 한다(픽 로직 무변경)."""
import json

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_MIX_WORK_DIR", tmp_path)
    return TestClient(appmod.app)


def test_swap_log_appends_jsonl(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    s = appmod.Store(appmod.DB_PATH)
    s.create_mix_job("j", ["u"], 30, "free")
    body = {"beat": 1, "old_seg": "s0_seg3", "new_video": "s1",
            "new_start": 2.0, "new_end": 3.9, "cap_text": "친구가 추천해", "cap_sec": 1.9}
    for _ in range(2):
        r = c.post("/api/mix/scene_lab/j/swap_log", json=body)
        assert r.status_code == 200 and r.json()["ok"]
    lines = (tmp_path / "j" / "swap_log.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    row = json.loads(lines[0])
    assert row["old_seg"] == "s0_seg3" and row["cap_sec"] == 1.9 and row["ts"]


def test_swap_log_unknown_job_404(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/mix/scene_lab/nope/swap_log", json={"beat": 0})
    assert r.status_code == 404
