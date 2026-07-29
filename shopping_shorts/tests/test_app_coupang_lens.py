"""'🔍 화면으로 정확히' — 렌즈 역검색 엔드포인트(유료 경로라 캐시·실패처리가 핵심)."""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "run_mix_job", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "run_render", lambda *a, **k: None)
    monkeypatch.setattr(app_module, "retype_mix_job", lambda *a, **k: None)
    app_module._COUPANG_LENS_CACHE.clear()
    return TestClient(app_module.app), Store(db)


def _job(store, jid="j1"):
    store.create_mix_job(jid, ["u0"], 20, "free")
    store.update_mix_job(jid, status="ready_for_review", edit_plan={
        "structure": "free", "detected_type": "product_reveal",
        "affiliate_target": "얼음 슬라임 만들기", "beats": [], "plagiarism_flags": []})
    return jid


def _stub_pipeline(monkeypatch, tmp_path, name="아모스 아이슬라임 액티 2.1L", calls=None):
    monkeypatch.setattr(app_module, "_resolve_sources", lambda job, work: {app_module._source_video_id(0): "v.mp4"})
    frame = tmp_path / "f1.jpg"
    frame.write_bytes(b"x")
    monkeypatch.setattr(app_module.frame_extract, "extract_frames", lambda *a, **k: [frame])

    def _lens(urls):
        if calls is not None:
            calls.append(urls)
        return ["아모스 아이슬라임"]

    monkeypatch.setattr(app_module, "fetch_lens_lines", _lens)
    monkeypatch.setattr(app_module, "identify_product_from_lines", lambda *a, **k: name)


def test_lens_returns_product_name(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    jid = _job(store)
    _stub_pipeline(monkeypatch, tmp_path)
    d = client.post("/api/coupang/lens", json={"job_id": jid}).json()
    assert d["ok"] is True and d["name"] == "아모스 아이슬라임 액티 2.1L"
    assert d["cached"] is False


def test_lens_second_call_is_cached(monkeypatch, tmp_path):
    """★SerpApi는 프레임당 1콜 — 두 번 누르면 두 번 과금된다. 캐시로 막는다."""
    client, store = _client(monkeypatch, tmp_path)
    jid = _job(store)
    calls = []
    _stub_pipeline(monkeypatch, tmp_path, calls=calls)
    client.post("/api/coupang/lens", json={"job_id": jid})
    d = client.post("/api/coupang/lens", json={"job_id": jid}).json()
    assert d["cached"] is True
    assert len(calls) == 1, "두 번째 호출에서 또 과금됐다"


def test_lens_force_bypasses_cache(monkeypatch, tmp_path):
    client, store = _client(monkeypatch, tmp_path)
    jid = _job(store)
    calls = []
    _stub_pipeline(monkeypatch, tmp_path, calls=calls)
    client.post("/api/coupang/lens", json={"job_id": jid})
    client.post("/api/coupang/lens", json={"job_id": jid, "force": True})
    assert len(calls) == 2


def test_lens_unknown_job_is_404(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    assert client.post("/api/coupang/lens", json={"job_id": "nope"}).status_code == 404


def test_lens_failure_is_200_with_reason(monkeypatch, tmp_path):
    """★못 찾아도 500이 아니다 — 화면은 기존 검색결과를 그대로 유지해야 한다."""
    client, store = _client(monkeypatch, tmp_path)
    jid = _job(store)
    _stub_pipeline(monkeypatch, tmp_path, name="")      # 특정 실패
    r = client.post("/api/coupang/lens", json={"job_id": jid})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is False and d["name"] == "" and d["error"]
    assert jid not in app_module._COUPANG_LENS_CACHE   # 실패는 캐시하지 않는다


def test_lens_frames_are_publicly_servable(monkeypatch, tmp_path):
    """렌즈는 SerpApi가 우리 서버로 이미지를 받으러 온다 — /api/find/frame/ 경로여야 한다."""
    client, store = _client(monkeypatch, tmp_path)
    jid = _job(store)
    calls = []
    _stub_pipeline(monkeypatch, tmp_path, calls=calls)
    client.post("/api/coupang/lens", json={"job_id": jid})
    assert calls and all("/api/find/frame/" in u for u in calls[0])
