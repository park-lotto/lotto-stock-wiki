# -*- coding: utf-8 -*-
"""문장 칸 삭제 (2026-09-03 고객 이유준 "음성이 두 번 되어서 마지막 것을 삭제해야 한다").

여태 칸은 고치거나 다시 뽑을 수만 있었다. 대본이 중복 생성돼 같은 말이 두 번 들어가면
글자를 지우려 해도 저장 API가 "대본이 비었어요"로 막아 앱 안에 빠져나갈 구멍이 없었다.

여기서 못 박는 것:
1. 지운 칸만 빠지고 **남은 칸의 beat_idx는 그대로**다 — mp3 이름(beat_{idx}_*.mp3)과
   tts_paths가 전부 beat_idx로 짝을 찾으므로, 번호를 당기면 남의 음성을 물고 간다.
2. 생성·렌더 중에는 못 지운다(narration 저장과 같은 가드).
3. 마지막 한 칸은 못 지운다(빈 영상이 된다).
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    return TestClient(app_module.app), Store(db)


def _beat(i, text):
    return {"beat_idx": i, "role": "훅", "narration": text, "target_seconds": 2,
            "primary": {"video_id": "s0", "seg_id": f"s0-{i}", "start": 0.0, "end": 2.0},
            "alternates": [], "effect": "cut"}


def _seed(store, status="ready_for_review", n=3):
    store.create_mix_job("j1", ["u0"], 20, "free")
    store.update_mix_job("j1", status=status, edit_plan={
        "structure": "free",
        "beats": [_beat(i, f"문장{i}") for i in range(n)],
        "plagiarism_flags": []})


def test_지운_칸만_빠지고_남은_번호는_그대로다(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    r = client.post("/api/mix/scene_lab/j1/beat/1/delete")
    assert r.status_code == 200, r.text
    assert r.json()["ok"] and r.json()["left"] == 2
    beats = store.get_mix_job("j1")["edit_plan"]["beats"]
    assert [b["beat_idx"] for b in beats] == [0, 2], "번호를 당기면 남은 칸이 남의 음성을 문다"
    assert [b["narration"] for b in beats] == ["문장0", "문장2"]


def test_없는_칸은_404(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    assert client.post("/api/mix/scene_lab/j1/beat/9/delete").status_code == 404


def test_마지막_한_칸은_못_지운다(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store, n=1)
    r = client.post("/api/mix/scene_lab/j1/beat/0/delete")
    assert r.status_code == 422
    assert len(store.get_mix_job("j1")["edit_plan"]["beats"]) == 1


def test_생성중에는_못_지운다(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    _seed(store, status=app_module._MIX_ACTIVE_STAGES[0])
    r = client.post("/api/mix/scene_lab/j1/beat/1/delete")
    assert r.status_code == 409
    assert len(store.get_mix_job("j1")["edit_plan"]["beats"]) == 3


def test_뒷단계_완성본이_무효화된다(monkeypatch, tmp_path):
    """지운 칸이 든 옛 mp4를 그대로 쓰면 9단계 완성본이 지운 문장을 계속 말하고,
    캡컷은 그 옛 완성본을 새 타임라인으로 잘라(split_final_into_beat_clips) 어긋난다."""
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    store.update_mix_job("j1", video_path="/w/final.mp4", clean_video_path="/w/clean.mp4",
                         fx_path="/w/fx.mp4", fx_status="done")
    r = client.post("/api/mix/scene_lab/j1/beat/1/delete")
    assert r.status_code == 200, r.text
    job = store.get_mix_job("j1")
    assert not job.get("video_path"), "옛 완성본이 남으면 지운 문장이 계속 나온다"
    assert not job.get("clean_video_path"), "옛 청소 조립본을 새 타임라인으로 자르면 캡컷이 어긋난다"
    assert not job.get("fx_path") and not job.get("fx_status")


def test_소스별_청소본은_안_건드린다(monkeypatch, tmp_path):
    """clean_sources는 소스 영상 기준이라 칸과 무관 — 지우면 VMake를 다시 태워 돈이 나간다."""
    client, store = _client(monkeypatch, tmp_path)
    _seed(store)
    store.update_mix_job("j1", clean_status="ready")
    before = store.get_mix_job("j1").get("clean_sources")
    client.post("/api/mix/scene_lab/j1/beat/1/delete")
    after = store.get_mix_job("j1")
    assert after.get("clean_sources") == before
    assert after.get("clean_status") == "ready", "clean_status를 지우면 자막제거를 다시 돌리게 된다"
