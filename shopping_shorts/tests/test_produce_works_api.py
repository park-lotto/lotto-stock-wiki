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


# ── 고객 격리(2026-07-17 T2 리뷰) ──────────────────────────
# 라우트가 Request를 안 받아 _cid()를 못 써 모든 저장·조회가 customer_id=0으로 떨어지던 결함.
# _cid는 request.state.customer_id를 읽는다(app.py:247) — 이 저장소는 로그인 세션 쿠키로
# 그 값을 채우는데, 세션 없이 두 "고객"을 흉내내는 가장 단순한 방법은 _cid 자체를
# monkeypatch하는 것이다(auth_guard 미들웨어를 실제로 태우지 않고 라우트가 무엇을
# 넘기는지만 검증). scene_asset 테스트(test_app_scene.py)처럼 실 세션을 흉내내려면
# DASH_PASS·쿠키 서명까지 필요해 이 테스트의 목적(라우트가 _cid를 쓰는지)에 비해 과하다.
def test_isolation_customer2_does_not_see_customer1_work(client, monkeypatch):
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "_cid", lambda request: 1)
    client.post("/api/produce/works", json={"state": {"script": "고객1 작업"}})

    monkeypatch.setattr(app_mod, "_cid", lambda request: 2)
    works = client.get("/api/produce/works").json()["works"]
    assert works == []


def test_isolation_save_lands_under_real_customer_id_not_zero(client, monkeypatch, tmp_path):
    from shopping_shorts import app as app_mod
    from shopping_shorts.store import Store

    monkeypatch.setattr(app_mod, "_cid", lambda request: 1)
    client.post("/api/produce/works", json={"state": {"script": "고객1 작업"}})

    rows = Store(app_mod.DB_PATH).list_produce_works(customer_id=1)
    assert len(rows) == 1
    rows0 = Store(app_mod.DB_PATH).list_produce_works(customer_id=0)
    assert rows0 == []


def test_isolation_get_and_delete_are_404_for_other_customer(client, monkeypatch):
    from shopping_shorts import app as app_mod
    monkeypatch.setattr(app_mod, "_cid", lambda request: 1)
    wid = client.post("/api/produce/works", json={"state": {"script": "고객1"}}).json()["work_id"]

    monkeypatch.setattr(app_mod, "_cid", lambda request: 2)
    assert client.get(f"/api/produce/works/{wid}").status_code == 404
    assert client.post(f"/api/produce/works/{wid}/delete").status_code == 404

    # 고객1은 여전히 자기 작업을 볼 수 있어야 한다(지워지지 않았다).
    monkeypatch.setattr(app_mod, "_cid", lambda request: 1)
    assert client.get(f"/api/produce/works/{wid}").status_code == 200


# ── step 타입오류 가드(2026-07-17 T2 리뷰) ──────────────────
def test_step_string_is_preserved_not_rewound(client):
    """step="3"(문자열)을 보내면 파괴되지 않고 기존 값이 그대로 보존된다."""
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "s"}, "step": 5}).json()["work_id"]
    client.post("/api/produce/works",
                json={"work_id": wid, "state": {"script": "s2"}, "step": "3"})
    d = client.get(f"/api/produce/works/{wid}").json()
    assert d["step"] == 5, "문자열 step이 진행 단계를 0으로 되감았다"


def test_step_bool_true_is_preserved_not_saved_as_one(client):
    """step=True는 isinstance(True, int)가 True라 잘못 1로 저장되는 파이썬 함정 — 막혀야 한다."""
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "s"}, "step": 5}).json()["work_id"]
    client.post("/api/produce/works",
                json={"work_id": wid, "state": {"script": "s2"}, "step": True})
    d = client.get(f"/api/produce/works/{wid}").json()
    assert d["step"] == 5, "step=True가 bool 서브클래스 함정으로 1로 저장됐다"


def test_isolation_upsert_of_someone_elses_work_id_is_404(client, monkeypatch):
    """★남의 work_id를 알아도 POST로 덮어쓸 수 없다 — get/delete는 404인데 upsert만 뚫려
    있었다(T2 재리뷰). 고객1의 내용·job_id·step은 그대로 남아야 한다."""
    from shopping_shorts import app as app_mod

    monkeypatch.setattr(app_mod, "_cid", lambda request: 1)
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "고객1 작업"}, "job_id": "job-1", "step": 3}
                      ).json()["work_id"]

    monkeypatch.setattr(app_mod, "_cid", lambda request: 2)
    r = client.post("/api/produce/works",
                    json={"work_id": wid, "state": {"script": "고객2가 덮어씀"},
                          "job_id": "job-EVIL", "step": 99})
    assert r.status_code == 404
    assert r.json()["ok"] is False

    monkeypatch.setattr(app_mod, "_cid", lambda request: 1)
    d = client.get(f"/api/produce/works/{wid}").json()
    assert d["state"]["script"] == "고객1 작업", "남이 내용을 덮어썼다"
    assert d["job_id"] == "job-1" and d["step"] == 3


def test_step_explicit_zero_still_rewinds(client):
    """step=0(진짜 정수 0)은 여전히 0으로 저장된다 — T1의
    test_explicit_zero_step_really_rewinds와 대칭. 복원이 게이트에 막혀 1단계로
    되돌려질 때 실제로 필요하다."""
    wid = client.post("/api/produce/works",
                      json={"state": {"script": "s"}, "step": 5}).json()["work_id"]
    client.post("/api/produce/works",
                json={"work_id": wid, "state": {"script": "s2"}, "step": 0})
    d = client.get(f"/api/produce/works/{wid}").json()
    assert d["step"] == 0, "명시적 step=0이 무시됐다"


# ── 이름 바꾸기(2026-08-17) ────────────────────────────────────────
# 사장님 "내 작업에 작업명 수정할수있게". 제목 계산은 store._work_title 한 곳뿐 —
# 이 라우트는 이름을 넘기고 확정된 제목을 돌려줄 뿐이다(CLAUDE.md 0순위-B).
def test_rename_sets_title(client):
    wid = client.post("/api/produce/works", json={"state": {"script": "감자 레시피"}}).json()["work_id"]
    r = client.post(f"/api/produce/works/{wid}/rename", json={"name": "감자 A안"})
    assert r.status_code == 200 and r.json() == {"ok": True, "title": "감자 A안"}
    assert client.get("/api/produce/works").json()["works"][0]["title"] == "감자 A안"


def test_rename_survives_later_save(client):
    """★대본을 고쳐 저장해도 지은 이름이 남는다 — 이 기능의 존재 이유."""
    wid = client.post("/api/produce/works", json={"state": {"script": "처음"}}).json()["work_id"]
    client.post(f"/api/produce/works/{wid}/rename", json={"name": "내 이름"})
    state = client.get(f"/api/produce/works/{wid}").json()["state"]
    state["script"] = "고친 대본"
    client.post("/api/produce/works", json={"work_id": wid, "state": state})
    assert client.get("/api/produce/works").json()["works"][0]["title"] == "내 이름"


def test_rename_empty_restores_auto_title(client):
    wid = client.post("/api/produce/works", json={"state": {"script": "감자 레시피"}}).json()["work_id"]
    client.post(f"/api/produce/works/{wid}/rename", json={"name": "감자 A안"})
    r = client.post(f"/api/produce/works/{wid}/rename", json={"name": ""})
    assert r.json()["title"] == "감자 레시피"


def test_rename_rejects_non_string_name(client):
    """★dict가 와도 500이 아니라 422 — 이 앱은 .strip()을 모양 확인 없이 불러 세 번 터졌다."""
    wid = client.post("/api/produce/works", json={"state": {"script": "감자"}}).json()["work_id"]
    assert client.post(f"/api/produce/works/{wid}/rename", json={"name": {"a": 1}}).status_code == 422


def test_rename_missing_work_is_404(client):
    assert client.post("/api/produce/works/없는id/rename", json={"name": "x"}).status_code == 404
