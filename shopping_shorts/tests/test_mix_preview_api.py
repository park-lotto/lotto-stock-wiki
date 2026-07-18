"""1단계 미리보기 라우트 — 예약·서빙·중복방어(스펙 §6.3).

DB 격리는 test_app.py:218의 관례를 따른다: app_module에 바인딩된 DB_PATH를 직접 교체.
(config.DB_PATH만 monkeypatch하면 app.py가 모듈 로드 시 이미 바인딩해둔 이름은 그대로라
 실DB에 계속 쓰게 된다 — 그 파일 주석에 명시돼 있음.)
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _backdate(db, job_id, minutes):
    """updated_at을 과거로 민다 — store.update_mix_job은 항상 now로 덮으므로 생 SQL이어야 한다."""
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    with sqlite3.connect(db) as c:
        c.execute("UPDATE mix_jobs SET updated_at=? WHERE job_id=?", (ts, job_id))


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    Store(db)                                     # 스키마 생성
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", tmp_path / "work")
    return TestClient(app_module.app)


def _job_with_plan(job_id="J1"):
    store = Store(app_module.DB_PATH)
    store.create_mix_job(job_id, ["https://x/1"], 20, "template")
    store.update_mix_job(job_id, edit_plan={"beats": []}, status="ready_for_review")
    return store


def test_preview_requires_edit_plan(client):
    """매칭 전엔 422 — 렌더할 게 없다."""
    Store(app_module.DB_PATH).create_mix_job("J0", ["https://x/1"], 20, "template")
    r = client.post("/api/produce/mix/preview", json={"job_id": "J0"})
    assert r.status_code == 422
    assert "매칭" in r.json()["error"]


def test_preview_schedules_render(client, monkeypatch):
    _job_with_plan()
    called = []
    monkeypatch.setattr(app_module, "run_preview", lambda *a: called.append(a))
    r = client.post("/api/produce/mix/preview", json={"job_id": "J1"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert called, "run_preview가 예약되지 않았다"


# ── 매칭 단계(downloading~tts) staleness 가드 (2026-07-18 실사고) ──────────────
# 사장님이 '영상 매칭 시작' 후 다운로드 도중 배포 재시작으로 BackgroundTask가 죽어, DB엔
# status='downloading'이 영원히 남고 프론트가 10분째 무한 ⏳. 렌더 단계엔 _render_is_stale
# 가드가 있었으나 매칭 단계엔 없었다 → 매칭 단계도 stale이면 응답에서 failed로 알린다(DB 불변).
@pytest.mark.parametrize("stage", ["downloading", "extracting", "planning", "tts"])
def test_stale_matching_stage_reported_as_failed(client, stage):
    store = Store(app_module.DB_PATH)
    store.create_mix_job("JS", ["https://x/1"], 20, "template")
    store.update_mix_job("JS", status=stage)
    _backdate(app_module.DB_PATH, "JS", minutes=11)   # 10분 초과 = 죽은 잔해

    d = client.get("/api/mix/status/JS").json()
    assert d["status"] == "failed", f"{stage} 11분 stale인데 failed로 안 바뀜 — 무한 스피너 재발: {d}"
    assert "다시" in (d.get("error") or ""), f"재시도 안내가 없다: {d}"

    # ★DB는 그대로여야 한다(GET이 쓰면 안 된다). 재실행은 새 job이 유일 복구.
    assert store.get_mix_job("JS")["status"] == stage, "GET이 DB status를 바꿨다"


def test_fresh_matching_stage_not_falsely_failed(client):
    """방금 시작한 다운로드(updated_at=now)는 failed로 오판하면 안 된다 — 정상 진행 중."""
    store = Store(app_module.DB_PATH)
    store.create_mix_job("JF", ["https://x/1"], 20, "template")
    store.update_mix_job("JF", status="downloading")   # updated_at = now
    d = client.get("/api/mix/status/JF").json()
    assert d["status"] == "downloading", f"정상 진행 중인데 failed로 오판: {d}"


def test_stale_does_not_touch_terminal_states(client):
    """이미 끝난(ready_for_review) 오래된 job은 건드리지 않는다 — 매칭 단계만 대상."""
    _job_with_plan("JT")
    _backdate(app_module.DB_PATH, "JT", minutes=30)
    d = client.get("/api/mix/status/JT").json()
    assert d["status"] == "ready_for_review", f"끝난 job을 failed로 바꿨다: {d}"


def test_preview_does_not_double_schedule_while_rendering(client, monkeypatch):
    """★더블클릭 방어 — 이미 렌더 중이면 또 걸지 않는다(ffmpeg 두 번 = CPU 두 배)."""
    store = _job_with_plan()
    store.update_mix_job("J1", preview_status="rendering")
    called = []
    monkeypatch.setattr(app_module, "run_preview", lambda *a: called.append(a))
    r = client.post("/api/produce/mix/preview", json={"job_id": "J1"})
    assert r.status_code == 200
    assert not called, "이미 렌더 중인데 또 예약했다"


def test_preview_claims_rendering_synchronously_before_scheduling(client, monkeypatch):
    """★I-2 TOCTOU — 'rendering'은 **스케줄 전에 라우트가 동기적으로** 써야 한다.

    run_preview 안에서 쓰면 그건 응답을 보낸 뒤에 도는지라, 수십 ms 간격의 POST 2건이 둘 다
    가드를 통과해(둘 다 아직 None을 본다) ffmpeg 두 개가 같은 work/preview.mp4에 쓴다 —
    **잘린 mp4가 'ready'로 게이트를 통과**할 수 있다.

    run_preview를 스텁했으므로 DB에 'rendering'을 쓸 수 있는 건 라우트뿐이다.
    """
    store = _job_with_plan()
    monkeypatch.setattr(app_module, "run_preview", lambda *a: None)
    client.post("/api/produce/mix/preview", json={"job_id": "J1"})
    assert store.get_mix_job("J1")["preview_status"] == "rendering", \
        "라우트가 'rendering'을 동기적으로 쓰지 않았다 — 더블클릭 방어가 TOCTOU로 뚫린다"


def test_preview_second_click_is_rejected_after_first_claimed(client, monkeypatch):
    """위 동기 쓰기의 결과 — 두 번째 클릭은 ffmpeg를 또 돌리지 않는다(실제 더블클릭 흐름)."""
    _job_with_plan()
    called = []
    monkeypatch.setattr(app_module, "run_preview", lambda *a: called.append(a))
    client.post("/api/produce/mix/preview", json={"job_id": "J1"})
    client.post("/api/produce/mix/preview", json={"job_id": "J1"})
    assert len(called) == 1, f"더블클릭에 run_preview가 {len(called)}번 예약됐다 — ffmpeg 두 개가 같은 파일에 쓴다"


def test_stale_rendering_allows_reschedule(client, monkeypatch):
    """★I-1 영구 교착 탈출 — 렌더 중 서버가 재시작되면 'rendering'이 DB에 영원히 남는다.

    (auto_deploy 크론 3분 + shopping_shorts 변경 시 systemd 재시작 = 자주 일어난다.)
    BackgroundTask가 죽어 except가 못 돌아 failed도 안 남으니, 타임아웃이 없으면 다시 눌러도
    중복예약 거부에 걸려 **무한 ⏳ + 다음 버튼 영구 잠김**이 된다(스펙 §7.1 탈출구도 안 열림).
    """
    store = _job_with_plan()
    store.update_mix_job("J1", preview_status="rendering")
    _backdate(app_module.DB_PATH, "J1", 11)        # 10분 타임아웃 초과 = 죽은 렌더의 잔해
    called = []
    monkeypatch.setattr(app_module, "run_preview", lambda *a: called.append(a))
    r = client.post("/api/produce/mix/preview", json={"job_id": "J1"})
    assert r.status_code == 200
    assert called, "죽은 렌더의 'rendering'에 영구히 갇혔다 — 재매칭 말곤 탈출구가 없다"


def test_fresh_rendering_still_blocks_reschedule(client, monkeypatch):
    """회귀 방지 — 타임아웃 안(=진짜 렌더 중)이면 여전히 막아야 한다. 안 그러면 I-1 수정이
    더블클릭 방어(I-2)를 통째로 없애버린 셈이 된다."""
    store = _job_with_plan()
    store.update_mix_job("J1", preview_status="rendering")
    _backdate(app_module.DB_PATH, "J1", 5)         # 아직 도는 중
    called = []
    monkeypatch.setattr(app_module, "run_preview", lambda *a: called.append(a))
    client.post("/api/produce/mix/preview", json={"job_id": "J1"})
    assert not called, "아직 렌더 중인데 또 예약했다 — ffmpeg 두 개가 같은 파일에 쓴다"


def test_serve_preview_404_before_ready(client):
    _job_with_plan()
    assert client.get("/api/produce/mix/preview/J1").status_code == 404


def test_serve_preview_404_while_rerendering_even_if_old_file_exists(client, tmp_path):
    """★재렌더 중엔 옛 영상을 주지 않는다.

    대본을 고쳐 재매칭·재렌더하면 preview_status='rendering'인데 preview_path엔 **직전 렌더의
    경로가 그대로 남아 있다**. ready 검사가 없으면 그 옛 mp4가 서빙되고, 사장님은 바뀐 줄 알고
    **옛 영상을 보고 OK를 누른다** — 게이트가 있으나 마나가 된다.

    (이 테스트가 없으면 'ready 검사 제거' 뮤턴트가 살아남는다 — 실측. 위 404 테스트는
     preview_path가 None이라 다른 가드에 걸려 통과할 뿐 이 가드를 검증하지 못한다.)"""
    store = _job_with_plan()
    old = tmp_path / "preview.mp4"
    old.write_bytes(b"OLD")                                    # 직전 렌더 결과가 남아 있다
    store.update_mix_job("J1", preview_status="ready", preview_path=str(old))
    assert client.get("/api/produce/mix/preview/J1").status_code == 200   # 지금은 유효

    store.update_mix_job("J1", preview_status="rendering")     # 대본 고쳐 재렌더 시작
    r = client.get("/api/produce/mix/preview/J1")
    assert r.status_code == 404, "재렌더 중인데 옛 영상을 줬다 — 사장님이 옛 걸 보고 OK한다"


def test_serve_preview_returns_file(client, tmp_path):
    store = _job_with_plan()
    p = tmp_path / "preview.mp4"
    p.write_bytes(b"\x00\x01")
    store.update_mix_job("J1", preview_status="ready", preview_path=str(p))
    r = client.get("/api/produce/mix/preview/J1")
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert r.content == b"\x00\x01"


def test_status_exposes_preview_fields(client):
    """★프론트 폴링이 이걸 읽는다 — 새 폴링 라우트를 만들지 않는 이유(스펙 §6.3).

    폴러가 둘이 되면 서로를 오인한다."""
    store = _job_with_plan()
    store.update_mix_job("J1", preview_status="ready", preview_path="/srv/secret/preview.mp4")
    d = client.get("/api/mix/status/J1").json()
    assert d["preview_status"] == "ready"
    assert "preview_error" in d
    assert d["status"] == "ready_for_review", "기존 status 필드가 사라졌다(회귀)"
    assert "preview_path" not in d, "서버 내부 경로가 밖으로 샜다"
