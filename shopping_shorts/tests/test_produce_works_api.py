"""작업파일 라우트 — 제작소 작업의 저장·목록·복원·삭제(스펙 §4.6)."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "DB_PATH", tmp_path / "t.db")
    return TestClient(app_mod.app)


def test_post_creates_work_and_returns_id(client):
    r = client.post("/api/produce/works", json={"state": {"script": "감자 레시피"}})
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True and d["work_id"]


def test_post_with_id_updates_same_work(client):
    wid = client.post("/api/produce/works", json={"state": {"script": "처음"}}).json()["work_id"]
    r = client.post("/api/produce/works",
                    json={"work_id": wid, "state": {"script": "고침"}, "step": 2})
    assert r.json()["work_id"] == wid
    assert len(client.get("/api/produce/works").json()["works"]) == 1
    got = client.get(f"/api/produce/works/{wid}").json()
    assert got["state"]["script"] == "고침" and got["step"] == 2


def test_post_without_state_is_rejected(client):
    r = client.post("/api/produce/works", json={"step": 1})
    assert r.status_code == 422
    assert r.json()["ok"] is False


def test_get_list_returns_recent_first(client):
    client.post("/api/produce/works", json={"state": {"script": "먼저"}})
    client.post("/api/produce/works", json={"state": {"script": "나중"}})
    works = client.get("/api/produce/works").json()["works"]
    assert works[0]["title"] == "나중"
    assert "state" not in works[0]


def test_get_one_carries_job_bridge(client):
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "대본"}, "job_id": "job-9", "step": 1}
                      ).json()["work_id"]
    d = client.get(f"/api/produce/works/{wid}").json()
    assert d["ok"] is True and d["job_id"] == "job-9" and d["step"] == 1


def test_get_missing_is_404(client):
    r = client.get("/api/produce/works/없는id")
    assert r.status_code == 404
    assert r.json()["ok"] is False


def test_delete_removes_and_missing_is_404(client):
    wid = client.post("/api/produce/works", json={"state": {"script": "지울것"}}).json()["work_id"]
    assert client.post(f"/api/produce/works/{wid}/delete").json()["ok"] is True
    assert client.get(f"/api/produce/works/{wid}").status_code == 404
    assert client.post(f"/api/produce/works/{wid}/delete").status_code == 404


def test_partial_save_does_not_wipe_job_and_step(client):
    """★body에 job_id·step이 없으면 라우트가 기본값을 채우지 말고 **안 넘겨야** 한다.
    채워 넣으면 스토어의 보존 로직이 무의미해져, 대본만 고쳐 저장했을 때 매칭된 job이
    날아가고 진행 단계가 0으로 되감긴다 — 작업 유실을 막으려는 기능이 유실을 만든다."""
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "처음"}, "job_id": "job-9", "step": 2}
                      ).json()["work_id"]
    client.post("/api/produce/works", json={"work_id": wid, "state": {"script": "고침"}})
    d = client.get(f"/api/produce/works/{wid}").json()
    assert d["job_id"] == "job-9", "부분 저장이 job_id를 지웠다"
    assert d["step"] == 2, "부분 저장이 step을 되감았다"


def test_explicit_null_job_clears_it(client):
    """명시적 null은 진짜로 끊는다 — 재매칭으로 job이 무효가 되면 필요하다."""
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "s"}, "job_id": "job-9", "step": 2}
                      ).json()["work_id"]
    client.post("/api/produce/works",
                json={"work_id": wid, "state": {"script": "s"}, "job_id": None})
    d = client.get(f"/api/produce/works/{wid}").json()
    assert d["job_id"] is None
    assert d["step"] == 2   # step은 안 보냈으니 그대로


def test_state_roundtrips_verbatim(client):
    """state_json은 클라이언트 스키마 그대로 오간다 — 서버가 모양을 바꾸면 복원이 깨진다."""
    state = {"handoff": [{"url": "https://x/1", "pickScript": True, "useFootage": False}],
             "script": "본문", "script_src_idx": 0, "script_from_wiki": "ABC123", "step": 1}
    wid = client.post("/api/produce/works", json={"state": state}).json()["work_id"]
    assert client.get(f"/api/produce/works/{wid}").json()["state"] == state
