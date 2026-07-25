"""'톤 바꿔 다시'(비트별 재합성)가 실제로 적용되게 하는 두 가지 수정의 회귀 잠금.

버그(2026-07-23 진단): tts를 생성한 뒤 비트별 톤을 바꿔도 적용이 안 됨.
근본원인 ①: regen 엔드포인트가 렌더 단계만 거부해, '이 음성으로 전체 생성'(status="tts")이
  도는 중에도 regen을 허용 → 전체생성 백그라운드가 새 톤 mp3를 job 기본 보이스로 덮어씀.
근본원인 ②: 프론트가 완료 신호 없이 고정 4초 뒤 한 번만 새로고침 → 실제 재합성(>4초)이
  끝나기 전에 옛 mp3를 캐시버스터 새 URL로 물어와 그대로 굳음.
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


def _beat():
    return {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
            "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
            "alternates": [], "effect": "cut"}


# ── 근본원인 ①: 전체생성(active 단계) 중엔 비트 regen을 막는다 ──────────

def test_regen_blocked_while_generating_all(monkeypatch, tmp_path):
    """status="tts"(=이 음성으로 전체 생성 진행 중)일 때 regen은 409 —
    허용하면 전체생성 백그라운드가 새 톤 mp3를 job 기본 보이스로 덮어써 적용이 사라진다."""
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jg", ["u0"], 20, "free")
    store.update_mix_job("jg", status="tts", edit_plan={
        "structure": "free", "beats": [_beat()], "plagiarism_flags": []})
    r = client.post("/api/mix/tts/jg/0/regen",
                    json={"voice_id": "v", "settings": {}, "speed": 1.0})
    assert r.status_code == 409


def test_regen_allowed_when_ready(monkeypatch, tmp_path):
    """ready_for_review일 땐 정상 허용(회귀 방지) — background 작업은 실제로 안 돌지만
    엔드포인트가 200을 돌려주고 큐잉만 확인한다."""
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jr", ["u0"], 20, "free")
    store.update_mix_job("jr", status="ready_for_review", edit_plan={
        "structure": "free", "beats": [_beat()], "plagiarism_flags": []})
    # resynth를 no-op으로 — 엔드포인트 게이트만 검증
    monkeypatch.setattr(app_module, "resynth_one_beat", lambda *a, **k: None)
    r = client.post("/api/mix/tts/jr/0/regen",
                    json={"voice_id": "v", "settings": {}, "speed": 1.0})
    assert r.status_code == 200


# ── 근본원인 ②: 완료 신호(tts_ver) — 프론트가 폴링해 진짜 완료를 안다 ──────────

def test_resynth_one_beat_bumps_tts_ver(monkeypatch, tmp_path):
    """resynth_one_beat 완료 시 그 비트의 tts_ver를 +1 한다 — 프론트가 이 값의 변화로
    '재합성 끝'을 감지해 새로고침(고정 4초 추측 제거)."""
    from shopping_shorts import mix_pipeline
    db = str(tmp_path / "t.db")
    store = Store(db)
    store.create_mix_job("jb", ["u"], 20, "free")
    store.update_mix_job("jb", edit_plan={
        "structure": "free", "beats": [_beat()], "plagiarism_flags": []})
    monkeypatch.setattr(mix_pipeline, "synthesize_line", lambda *a, **k: "n")
    monkeypatch.setattr(mix_pipeline.asr_check, "transcribe_words", lambda p: [])
    mix_pipeline.resynth_one_beat("jb", 0, {"voice_id": "v"}, db, str(tmp_path / "work"))
    beat = store.get_mix_job("jb")["edit_plan"]["beats"][0]
    assert beat.get("tts_ver") == 1
    # 두 번째 재합성이면 2 — 단조 증가로 매번 변화를 만든다(같은 톤 재클릭도 감지)
    mix_pipeline.resynth_one_beat("jb", 0, {"voice_id": "v"}, db, str(tmp_path / "work"))
    beat2 = store.get_mix_job("jb")["edit_plan"]["beats"][0]
    assert beat2.get("tts_ver") == 2


def test_mix_result_exposes_tts_ver(monkeypatch, tmp_path):
    """/api/mix/result가 비트별 tts_ver를 실어야 프론트가 폴링으로 비교할 수 있다."""
    client, store = _client(monkeypatch, tmp_path)
    store.create_mix_job("jv", ["u0"], 20, "free")
    b = _beat(); b["tts_ver"] = 3
    store.update_mix_job("jv", status="ready_for_review", edit_plan={
        "structure": "free", "beats": [b], "plagiarism_flags": []})
    body = client.get("/api/mix/result/jv").json()
    assert body["beats"][0]["tts_ver"] == 3


# ── 프론트: 고정 4초 타이머 제거 + tts_ver 폴링 ──────────

def test_frontend_regen_polls_instead_of_fixed_timeout():
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")
    # 고정 4초 뒤 한 번만 새로고침하던 옛 코드가 사라졌다
    assert "setTimeout(()=>{ renderTtsBeats(); }, 4000)" not in html
    # 대신 tts_ver 변화를 폴링한다
    assert "tts_ver" in html
