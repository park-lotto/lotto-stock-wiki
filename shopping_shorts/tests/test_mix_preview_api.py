"""1단계 미리보기 라우트 — 예약·서빙·중복방어(스펙 §6.3).

DB 격리는 test_app.py:218의 관례를 따른다: app_module에 바인딩된 DB_PATH를 직접 교체.
(config.DB_PATH만 monkeypatch하면 app.py가 모듈 로드 시 이미 바인딩해둔 이름은 그대로라
 실DB에 계속 쓰게 된다 — 그 파일 주석에 명시돼 있음.)
"""
import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


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


def test_preview_does_not_double_schedule_while_rendering(client, monkeypatch):
    """★더블클릭 방어 — 이미 렌더 중이면 또 걸지 않는다(ffmpeg 두 번 = CPU 두 배)."""
    store = _job_with_plan()
    store.update_mix_job("J1", preview_status="rendering")
    called = []
    monkeypatch.setattr(app_module, "run_preview", lambda *a: called.append(a))
    r = client.post("/api/produce/mix/preview", json={"job_id": "J1"})
    assert r.status_code == 200
    assert not called, "이미 렌더 중인데 또 예약했다"


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
