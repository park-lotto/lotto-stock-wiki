"""영상별 "훅에만 속삭이기" 선택 — job voice 스냅샷에 whisper role 오버레이(2026-07-17).

배경: whisper 톤은 성우 프리셋(naturalize_profile.whisper.roles)으로만 굴러갔다(기본 ["반전"]).
설계 문서(2026-07-16-보이스-속삭임톤-design.md §6)는 "영상별로 고르려면 새 저장층이 필요하다"고
적었지만 틀렸다 — job.voice 스냅샷(_voice_snapshot)이 이미 영상(job)마다 저장되는 층이다.
이 테스트는 body의 whisper_roles 오버라이드가 그 스냅샷의 naturalize_profile.whisper.roles에만
얹히고(다른 스테이지 불변, 프리셋 원본 dict 불변), 오버라이드가 없으면 프리셋 값을 그대로
쓰는(하위호환) 배선을 잠근다. 미리듣기(/api/mix/voice/preview)·렌더(/api/mix/voice) 양쪽이
같은 _voice_snapshot을 타므로 한쪽만 반영되는 결함(2026-07-15 seam 패턴)도 여기서 막는다.
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store


class _FakeStore:
    """store.get_voice_preset이 항상 같은 dict 레퍼런스를 돌려주는(캐시 흉내) 스텁.

    _voice_snapshot이 프리셋 dict를 제자리에서 수정하면 여기서 잡힌다 — 실제 Store는
    매번 새 dict를 json.loads로 만들어서(store.py _row_to_preset) 그 버그를 숨길 수 있다.
    """

    def __init__(self, preset):
        self._preset = preset

    def get_voice_preset(self, preset_id):
        return self._preset


def _preset_with_whisper():
    return {
        "preset_id": "p1", "base_voice_id": "v1", "voice_settings": {"stability": 0.5},
        "model_id": "eleven_v3",
        "naturalize_profile": {
            "whisper": {"on": True, "roles": ["반전"]},
            "pronunciation": {"on": True, "dict": {"a": "b"}},
        },
    }


def test_override_present_replaces_whisper_roles_only():
    preset = _preset_with_whisper()
    store = _FakeStore(preset)
    snap = appmod._voice_snapshot(store, {"preset_id": "p1", "whisper_roles": ["훅"]})
    assert snap["naturalize_profile"]["whisper"]["roles"] == ["훅"]
    # 다른 스테이지는 프리셋 값 그대로
    assert snap["naturalize_profile"]["pronunciation"] == {"on": True, "dict": {"a": "b"}}
    # whisper.on은 유지(오버라이드가 roles만 건드림)
    assert snap["naturalize_profile"]["whisper"]["on"] is True


def test_override_absent_keeps_preset_profile_unchanged():
    preset = _preset_with_whisper()
    store = _FakeStore(preset)
    snap = appmod._voice_snapshot(store, {"preset_id": "p1"})
    assert snap["naturalize_profile"]["whisper"]["roles"] == ["반전"]
    assert snap["naturalize_profile"] == preset["naturalize_profile"]


def test_override_does_not_mutate_original_preset_dict():
    preset = _preset_with_whisper()
    store = _FakeStore(preset)
    appmod._voice_snapshot(store, {"preset_id": "p1", "whisper_roles": ["훅", "CTA"]})
    # 원본 프리셋 dict는 그대로 — 다음 호출(다른 영상)이 오염된 값을 보면 안 된다
    assert preset["naturalize_profile"]["whisper"]["roles"] == ["반전"]
    assert preset["naturalize_profile"]["pronunciation"]["dict"] == {"a": "b"}


def test_override_works_when_preset_has_no_naturalize_profile():
    preset = {"preset_id": "p2", "base_voice_id": "v2", "voice_settings": {},
              "model_id": "eleven_v3", "naturalize_profile": None}
    store = _FakeStore(preset)
    snap = appmod._voice_snapshot(store, {"preset_id": "p2", "whisper_roles": ["훅", "CTA"]})
    assert snap["naturalize_profile"]["whisper"]["roles"] == ["훅", "CTA"]
    # 원본은 여전히 None
    assert preset["naturalize_profile"] is None


def test_no_override_and_no_profile_stays_none():
    preset = {"preset_id": "p2", "base_voice_id": "v2", "voice_settings": {},
              "model_id": "eleven_v3", "naturalize_profile": None}
    store = _FakeStore(preset)
    snap = appmod._voice_snapshot(store, {"preset_id": "p2"})
    assert snap["naturalize_profile"] is None


# ── 엔드포인트 배선: 미리듣기·렌더 양쪽 파리티 ──────────────

def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(appmod, "DB_PATH", db)
    return TestClient(appmod.app), Store(db)


def test_mix_voice_endpoint_stores_override_in_job_snapshot(monkeypatch, tmp_path):
    """렌더 경로: /api/mix/voice가 job.voice에 오버라이드 반영된 스냅샷을 저장한다.
    (background task 실행과 무관 — store.update_mix_job은 add_task 이전에 동기 실행됨)"""
    client, store = _client(monkeypatch, tmp_path)
    store.upsert_voice_preset({
        "preset_id": "kr-whisper-test", "name": "W", "lang": "KR", "base_voice_id": "v",
        "voice_settings": {}, "model_id": "eleven_v3",
        "naturalize_profile": {"whisper": {"on": True, "roles": ["반전"]}},
    })
    store.create_mix_job("jw1", ["u0"], 20, "free")
    store.update_mix_job("jw1", edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
         "primary": {}, "alternates": [], "effect": "cut"}], "plagiarism_flags": []})

    r = client.post("/api/mix/voice", json={
        "job_id": "jw1", "preset_id": "kr-whisper-test", "whisper_roles": ["훅"]})
    assert r.status_code == 200
    voice = store.get_mix_job("jw1")["voice"]
    assert voice["naturalize_profile"]["whisper"]["roles"] == ["훅"]


def test_mix_voice_preview_and_render_see_same_whisper_override(monkeypatch, tmp_path):
    """미리듣기·렌더 양쪽이 같은 whisper 오버라이드를 본다 — 한쪽만 반영되면 리뷰가
    잡았던 '미리듣기≠영상 소리' seam이 재발하므로 여기서 직접 비교한다."""
    client, store = _client(monkeypatch, tmp_path)
    store.upsert_voice_preset({
        "preset_id": "kr-whisper-test2", "name": "W2", "lang": "KR", "base_voice_id": "v",
        "voice_settings": {}, "model_id": "eleven_v3",
        "naturalize_profile": {"whisper": {"on": True, "roles": ["반전"]}},
    })
    store.create_mix_job("jw2", ["u0"], 20, "free")
    store.update_mix_job("jw2", edit_plan={"structure": "free", "beats": [
        {"beat_idx": 0, "role": "훅", "narration": "안녕하세요", "target_seconds": 2,
         "primary": {}, "alternates": [], "effect": "cut"}], "plagiarism_flags": []})

    body = {"job_id": "jw2", "preset_id": "kr-whisper-test2", "whisper_roles": ["훅"]}

    # 미리듣기: synthesize_line에 실제로 전달되는 voice 스냅샷을 가로챈다.
    captured = {}
    def fake_synth(narration, out_path, *, voice=None, **kw):
        captured["preview_voice"] = voice
        open(out_path, "wb").write(b"x")
        return narration
    monkeypatch.setattr(appmod.mix_pipeline, "synthesize_line", fake_synth)
    # /api/mix/voice의 background_tasks(resynth_tts_job)도 같은 patched synthesize_line을
    # 타므로(TestClient가 background task를 동기 실행) 그대로 두면 아래 r2 호출이 captured를
    # 렌더 쪽 값으로 덮어써 "미리듣기 값을 보는 척하며 실은 렌더 값을 보는" 거짓양성이 된다.
    # 렌더 경로의 실제 검증은 job.voice 스냅샷(동기 저장, background 이전)만으로 충분하므로
    # background task 자체는 no-op으로 끊는다.
    monkeypatch.setattr(appmod, "resynth_tts_job", lambda *a, **k: None)
    r1 = client.post("/api/mix/voice/preview", json=body)
    assert r1.status_code == 200
    preview_voice = captured["preview_voice"]   # r2 이전에 확정 — 이후 덮어써질 일 없음

    # 렌더: /api/mix/voice가 job.voice에 저장하는 스냅샷(= resynth_tts_job이 읽는 값)
    r2 = client.post("/api/mix/voice", json=body)
    assert r2.status_code == 200
    render_voice = store.get_mix_job("jw2")["voice"]

    assert preview_voice["naturalize_profile"]["whisper"]["roles"] == ["훅"]
    assert render_voice["naturalize_profile"]["whisper"]["roles"] == ["훅"]
    assert preview_voice["naturalize_profile"] == render_voice["naturalize_profile"]
