"""자동매칭 고급효과 엔진 Task5 — suggest/render/status 라우트.

핵심: mix_jobs는 beats/dur_frames/category를 직접 안 준다(브리프 가정과 다름, 실측).
비트·타이밍은 job["edit_plan"]["beats"](target_seconds 계획값 또는 tts_path 실측)에,
카테고리는 job["script_structure"]["product_category"]에 있다 — 어댑터
_fx_timeline_from_job/_fx_dur_frames가 이 실구조를 흡수한다.
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module, points
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


def _beats(with_tts=False):
    beats = [
        {"beat_idx": 0, "role": "훅", "narration": "5분이면 완성", "target_seconds": 2.0,
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
         "alternates": [], "effect": "cut"},
        {"beat_idx": 1, "role": "본문", "narration": "대박 맛있어요", "target_seconds": 3.0,
         "primary": {"video_id": "s0", "seg_id": "s0-1", "start": 2.0, "end": 5.0},
         "alternates": [], "effect": "cut"},
    ]
    if with_tts:
        for b in beats:
            b["tts_path"] = f"tts_{b['beat_idx']}.mp3"
    return beats


# ── /api/produce/fx/suggest — 어댑터 검증 ──────────────────────────

def test_fx_suggest_falls_back_to_target_seconds_when_no_tts(tmp_path, monkeypatch):
    """tts_path가 없으면(아직 렌더 전 등) target_seconds 누적으로 타이밍을 만든다."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j1", ["u0"], 20, "free")
    store.update_mix_job("j1", status="ready_for_review", video_path="x.mp4",
                          edit_plan={"beats": _beats(with_tts=False)},
                          script_structure={"product_category": "레시피"})
    r = client.post("/api/produce/fx/suggest", json={"job_id": "j1"})
    assert r.status_code == 200
    plan = r.json()["plan"]
    # target_seconds 누적: beat0 [0,2], beat1 [2,5]
    assert [b["s"] for b in plan["beats"]] == [0.0, 2.0]
    assert [b["e"] for b in plan["beats"]] == [2.0, 5.0]
    assert plan["beats"][1]["cap"] == "대박 맛있어요"
    assert plan["themeName"] == "warm"  # 레시피 → warm
    # "대박" impact 규칙이 걸려야 함(match_rules)
    assert any(f["comp"] == "impact" for f in plan["fx"])
    # DB에 기록하지 않는다(무과금 미리보기)
    assert store.get_mix_job("j1")["fx_plan"] is None


def test_fx_suggest_uses_tts_real_timing_when_available(tmp_path, monkeypatch):
    """tts_path가 채워져 있으면(렌더 완료 후) 계획값이 아니라 ffprobe 실측 길이를 쓴다."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j2", ["u0"], 20, "free")
    store.update_mix_job("j2", status="done", video_path="x.mp4",
                          edit_plan={"beats": _beats(with_tts=True)})
    # ffprobe를 실측 대신 스텁: beat0=2.5초, beat1=3.5초(계획값 2.0/3.0과 고의로 다르게)
    monkeypatch.setattr(app_module.video_assemble, "_probe_duration", lambda p: {"x.mp4": 6.0}.get(
        p, 2.5 if "tts_0" in str(p) else 3.5))
    r = client.post("/api/produce/fx/suggest", json={"job_id": "j2"})
    assert r.status_code == 200
    plan = r.json()["plan"]
    assert [b["s"] for b in plan["beats"]] == [0.0, 2.5]
    assert [b["e"] for b in plan["beats"]] == [2.5, 6.0]
    assert plan["durationInFrames"] == 180  # video_path 6.0초 * 30fps


def test_fx_suggest_no_edit_plan_returns_empty_plan(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j3", ["u0"], 20, "free")
    r = client.post("/api/produce/fx/suggest", json={"job_id": "j3"})
    assert r.status_code == 200
    assert r.json()["plan"]["beats"] == []


def test_fx_suggest_returns_balance_and_cost(tmp_path, monkeypatch):
    """추천 응답이 보유 포인트·렌더비를 함께 준다 — 프런트가 렌더 전에 잔액을 보여줘
    포인트 부족(402)을 클릭 전에 막는다."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("jb", ["u0"], 20, "free")
    points.add(store, 0, 25)  # 로그인 폴백 cid=0
    r = client.post("/api/produce/fx/suggest", json={"job_id": "jb"})
    assert r.status_code == 200
    assert r.json()["points"] == 25
    assert r.json()["cost"] == app_module.FX_RENDER_COST


# ── /api/produce/fx/render — 포인트 차감·402·백그라운드 큐잉 ──────────

def test_render_deducts_points_and_queues(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j4", ["u0"], 20, "free")
    store.update_mix_job("j4", status="done", video_path="x.mp4")
    points.add(store, 0, 100)
    called = {}
    monkeypatch.setattr(app_module.remotion_render, "render",
                        lambda plan, vp, out: called.setdefault("ok", (plan, vp, out)) or out)
    r = client.post("/api/produce/fx/render", json={"job_id": "j4", "plan": {"videoSrc": "x.mp4", "fx": []}})
    assert r.status_code == 200
    assert r.json()["status"] == "queued"
    assert points.balance(store, 0) == 100 - app_module.FX_RENDER_COST
    # TestClient는 background_tasks를 응답 반환 전에 동기 실행한다 — 그래서 이 시점엔
    # 이미 "queued"를 지나 "done"까지 가 있다(큐잉 자체의 fx_plan 저장은 별도 확인).
    job = store.get_mix_job("j4")
    assert job["fx_plan"] == {"videoSrc": "x.mp4", "fx": []}
    assert called["ok"][1] == "x.mp4"
    assert job["fx_status"] == "done"
    assert job["fx_path"]


def test_render_insufficient_points_402(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)  # 잔액 0
    store.create_mix_job("j5", ["u0"], 20, "free")
    r = client.post("/api/produce/fx/render", json={"job_id": "j5", "plan": {"videoSrc": "x.mp4", "fx": []}})
    assert r.status_code == 402
    assert store.get_mix_job("j5")["fx_status"] is None  # 차감 실패 시 아무것도 건드리지 않음


def test_render_failure_refunds_points(tmp_path, monkeypatch):
    """렌더 실패(remotion_render.render 예외) 시 차감된 포인트를 환불하고 fx_status=failed."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j6", ["u0"], 20, "free")
    store.update_mix_job("j6", status="done", video_path="x.mp4")
    points.add(store, 0, 100)
    monkeypatch.setattr(app_module.remotion_render, "render",
                        lambda plan, vp, out: (_ for _ in ()).throw(RuntimeError("렌더 실패")))
    r = client.post("/api/produce/fx/render", json={"job_id": "j6", "plan": {"videoSrc": "x.mp4", "fx": []}})
    assert r.status_code == 200  # 큐잉 자체는 성공(실패는 백그라운드에서 드러남)
    assert points.balance(store, 0) == 100  # 환불되어 원상복구
    assert store.get_mix_job("j6")["fx_status"] == "failed"


def test_render_falls_back_to_preview_when_no_video_path(tmp_path, monkeypatch):
    """고급효과는 꾸미기(4단계)에서 건다 — video_path(최종 조립본)는 맨 마지막에야
    채워지므로 이 시점엔 None이다. 배경은 preview_path(조립 프리뷰)로 폴백해야 한다.
    이 폴백이 없으면 render(plan, None, out)이 되어 항상 실패한다(실사고 2026-07-17)."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j8", ["u0"], 20, "free")
    # 꾸미기 단계의 실제 상태: video_path·clean_video_path는 아직 None, preview_path만 있다.
    store.update_mix_job("j8", preview_path="/data/j8/preview.mp4")
    points.add(store, 0, 100)
    called = {}
    monkeypatch.setattr(app_module.remotion_render, "render",
                        lambda plan, vp, out: called.setdefault("bg", vp) or out)
    r = client.post("/api/produce/fx/render", json={"job_id": "j8", "plan": {"fx": []}})
    assert r.status_code == 200
    assert called["bg"] == "/data/j8/preview.mp4"   # None이 아니라 프리뷰가 배경으로 감
    assert store.get_mix_job("j8")["fx_status"] == "done"


def test_render_no_background_fails_and_refunds(tmp_path, monkeypatch):
    """세 영상 필드가 전부 비어 있으면 배경이 없으니 렌더를 시도하지 말고
    깨끗이 실패+환불한다(render를 None으로 부르지 않는다)."""
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j9", ["u0"], 20, "free")  # 어떤 path도 없음
    points.add(store, 0, 100)
    called = {}
    monkeypatch.setattr(app_module.remotion_render, "render",
                        lambda plan, vp, out: called.setdefault("hit", True) or out)
    r = client.post("/api/produce/fx/render", json={"job_id": "j9", "plan": {"fx": []}})
    assert r.status_code == 200
    assert "hit" not in called  # 배경 없음 → render 자체를 안 부른다
    assert points.balance(store, 0) == 100  # 환불
    assert store.get_mix_job("j9")["fx_status"] == "failed"


# ── /api/produce/fx/status ──────────────────────────────────────────

def test_fx_status_reports_queued_then_done_with_url(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    store.create_mix_job("j7", ["u0"], 20, "free")
    store.update_mix_job("j7", fx_status="queued")
    r = client.get("/api/produce/fx/status/j7")
    assert r.json() == {"fx_status": "queued"}
    store.update_mix_job("j7", fx_status="done", fx_path="/tmp/fx_j7.mp4")
    r2 = client.get("/api/produce/fx/status/j7")
    assert r2.json()["fx_status"] == "done"
    assert r2.json()["fx_url"] == "/api/produce/fx/file/j7"


def test_fx_status_unknown_job(tmp_path, monkeypatch):
    client, store = _client(tmp_path, monkeypatch)
    r = client.get("/api/produce/fx/status/nope")
    assert r.json() == {"fx_status": None}
