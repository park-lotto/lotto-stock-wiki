# -*- coding: utf-8 -*-
"""3단계 통합 속도 API: 저장·완성본 무효화·칸별 음성 설정 보존."""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _seed(store):
    store.create_mix_job("speed-job", ["u0"], 20, "free")
    store.update_mix_job(
        "speed-job", status="ready_for_review", video_path="old-final.mp4",
        voice={"voice_id": "default", "speed": 1.0},
        edit_plan={"beats": [{
            "beat_idx": 3, "role": "본문", "narration": "테스트",
            "target_seconds": 2.0, "sync_speed": 1.2,
            "voice_override": {
                "voice_id": "picked", "settings": {"style": 0.4}, "speed": 1.32,
            },
            "primary": {"video_id": "v", "seg_id": "v-0", "start": 0.0, "end": 3.0},
            "alternates": [],
        }]})


def test_속도_api는_한값을_저장하고_완성본을_무효화하며_톤을_보존한다(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", tmp_path / "work")
    store = Store(db)
    _seed(store)
    called = {}

    def fake_resynth(job_id, beat_idx, voice, db_path, work_root):
        called.update(job_id=job_id, beat_idx=beat_idx, voice=voice)

    monkeypatch.setattr(app_module.mix_pipeline, "resynth_one_beat", fake_resynth)
    result = TestClient(app_module.app).post(
        "/api/mix/scene_lab/speed-job/speed/3", json={"speed": 1.3})

    assert result.status_code == 200 and result.json()["ok"]
    job = store.get_mix_job("speed-job")
    assert job["edit_plan"]["beats"][0]["sync_speed"] == 1.3
    assert job["video_path"] is None
    assert called["job_id"] == "speed-job" and called["beat_idx"] == 3
    assert called["voice"] == {
        "voice_id": "picked", "settings": {"style": 0.4}, "speed": 1.43,
    }


def test_속도_api는_허용범위밖과_렌더중_변경을_막는다(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    store = Store(db)
    _seed(store)
    client = TestClient(app_module.app)
    assert client.post(
        "/api/mix/scene_lab/speed-job/speed/3", json={"speed": 1.7}
    ).status_code == 422
    store.update_mix_job("speed-job", status="rendering")
    assert client.post(
        "/api/mix/scene_lab/speed-job/speed/3", json={"speed": 1.1}
    ).status_code == 409
