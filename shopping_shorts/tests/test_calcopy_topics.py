"""칼카피 소재창고(calcopy_topics) — 상태 전이·잠금·끊김·검수 자리·비용 상한·KPI·라우트 (관제 097, 2026-10-16).

사보타주로 확인할 것: ①검수 건너뛰기 허용(plan 이 곧장 producing 으로) ②잠금 무시(다른 워커 claim 통과)
— 둘 다 이 파일의 시험이 빨개져야 한다.
"""
from datetime import timedelta

import pytest

from shopping_shorts import calcopy_topics as CT

SCORE = {"criteria": {k: {"score": 4, "why": f"{k} 근거"} for k in ("공감", "반전", "보여줌", "시의성", "채널맞음")},
         "overlap_penalty": 0, "showable": True}


class Clock:
    def __init__(self):
        self.t = CT.datetime(2026, 10, 16, 9, 0, 0, tzinfo=CT.KST)

    def __call__(self):
        return self.t

    def tick(self, **kw):
        self.t = self.t + timedelta(**kw)


@pytest.fixture
def env(tmp_path, monkeypatch):
    clk = Clock()
    monkeypatch.setattr(CT, "_now", clk)
    return tmp_path, clk


def _do(d, tid, w, step, **kw):
    CT.claim(tid, w, step, data_dir=d)
    return CT.advance(tid, w, data_dir=d, **kw)


def _to_plan_review(d, tid, w="W1"):
    _do(d, tid, w, "bench", data={"bench": {"videos": [{"url": "u", "views": 1}]}}, cost={"gemini": 2})
    _do(d, tid, w, "score", data={"score": SCORE}, cost={"gemini": 1})
    _do(d, tid, w, "assign", data={"assign": {"channel": "sseolpulda", "preset": "p/A"}})
    _do(d, tid, w, "script", outputs={"script": "대본.json"}, files={"대본.json": "{}"}, cost={"gemini": 3})
    _do(d, tid, w, "source", data={"rights": {"컷1.mp4": "자체"}})
    return _do(d, tid, w, "plan", outputs={"plan": "계획.md"}, files={"계획.md": "# 계획"})


def test_full_flow_with_rework(env):
    d, clk = env
    t = CT.add("LED 수도꼭지", "홈템", "discover", source={"via": "douyin", "url": "x"}, data_dir=d)
    assert t["state"] == "found" and t["next_step"] == "bench"
    t = _to_plan_review(d, t["id"])
    assert t["state"] == "plan_review" and t["human_stage"] == "plan_review" and t["next_step"] is None
    # 선검수 반려 → scripted 로 재작업
    t = CT.review(t["id"], "plan_review", "reject", by="페이블", reason="반전 약함", back_to="scripted", data_dir=d)
    assert t["state"] == "rejected" and t["back_to"] == "scripted" and t["next_step"] == "source"
    r = CT.claim(t["id"], "W2", "source", data_dir=d)
    assert r["topic"]["state"] == "scripted" and r["topic"]["rework_n"] == 1
    CT.advance(t["id"], "W2", data={"rights": {"컷1.mp4": "자체"}}, data_dir=d)
    _do(d, t["id"], "W2", "plan", outputs={"plan": "계획.md"}, files={"계획.md": "# 계획 v2"})
    t = CT.review(t["id"], "plan_review", "pass", by="사장님", data_dir=d)
    assert t["state"] == "producing"
    _do(d, t["id"], "W1", "produce", outputs={"final": "완성본.mp4"}, files={"완성본.mp4": "x"}, cost={"typecast": 1})
    t = _do(d, t["id"], "W1", "check", outputs={"verdict": "판정.md"}, files={"판정.md": "ok"})
    assert t["state"] == "final_review"
    clk.tick(hours=5)
    t = CT.review(t["id"], "final_review", "pass", data_dir=d)
    assert t["state"] == "passed" and t["passed_at"]
    det = CT.detail(t["id"], data_dir=d)
    assert {f["name"] for f in det["files"]} >= {"계획.md", "대본.json", "완성본.mp4", "판정.md"}
    assert (CT.topic_dir(t["id"], d) / "계획.md").read_text(encoding="utf-8") == "# 계획 v2"
    kinds = [h["kind"] for h in det["history"]]
    assert kinds[0] == "add" and "rework" in kinds and kinds[-1] == "review"
    assert [v["verdict"] for v in det["reviews"]] == ["reject", "pass", "pass"]
    assert det["topic"]["cost"] == {"gemini": 6, "typecast": 1}


def test_worker_cannot_pass_review_stages(env):
    d, _ = env
    tid = CT.add("a", "식품", data_dir=d)["id"]
    t = _to_plan_review(d, tid)
    assert t["state"] == "plan_review"
    for step in CT.STEPS:
        with pytest.raises(CT.TopicError) as e:
            CT.claim(tid, "W1", step, data_dir=d)
        assert e.value.code == 409 and "사람 검수" in e.value.msg
    assert CT.claim_next("W1", data_dir=d)["topic"] is None
    with pytest.raises(CT.TopicError) as e:
        CT.advance(tid, "W1", data_dir=d)
    assert "사람 검수" in e.value.msg
    # 검수 자리가 아닌데 review 하면 거절
    tid2 = CT.add("b", "식품", data_dir=d)["id"]
    with pytest.raises(CT.TopicError) as e:
        CT.review(tid2, "plan_review", "pass", data_dir=d)
    assert e.value.code == 409


def test_wrong_step_and_required_outputs(env):
    d, _ = env
    tid = CT.add("a", "식품", data_dir=d)["id"]
    with pytest.raises(CT.TopicError) as e:
        CT.claim(tid, "W1", "score", data_dir=d)
    assert "다음 일은 bench" in e.value.msg
    CT.claim(tid, "W1", "bench", data_dir=d)
    with pytest.raises(CT.TopicError) as e:
        CT.advance(tid, "W1", data_dir=d)
    assert "data.bench" in e.value.msg
    CT.advance(tid, "W1", data={"bench": {"skipped": "새 소재"}}, data_dir=d)
    CT.claim(tid, "W1", "score", data_dir=d)
    bad = {"criteria": dict(list(SCORE["criteria"].items())[:4])}
    with pytest.raises(CT.TopicError) as e:
        CT.advance(tid, "W1", data={"score": bad}, data_dir=d)
    assert "5기준" in e.value.msg
    CT.advance(tid, "W1", data={"score": SCORE}, data_dir=d)
    _do(d, tid, "W1", "assign", data={"assign": {"channel": "c", "preset": "p"}})
    CT.claim(tid, "W1", "script", data_dir=d)
    with pytest.raises(CT.TopicError) as e:                         # 가짜 산출물(폴더에 없음)
        CT.advance(tid, "W1", outputs={"script": "없는.json"}, data_dir=d)
    assert "폴더에 없습니다" in e.value.msg
    with pytest.raises(CT.TopicError):                               # 폴더 밖 이름
        CT.advance(tid, "W1", outputs={"script": "../x"}, data_dir=d)
    assert CT.detail(tid, data_dir=d)["topic"]["state"] == "assigned"   # 거절은 상태를 안 바꾼다


def test_lock_conflict_and_owner_only(env):
    d, _ = env
    tid = CT.add("a", "식품", data_dir=d)["id"]
    CT.claim(tid, "W1", "bench", data_dir=d)
    with pytest.raises(CT.TopicError) as e:
        CT.claim(tid, "W2", "bench", data_dir=d)
    assert e.value.code == 409 and "잠김: W1" in e.value.msg
    assert CT.claim_next("W2", ["bench"], data_dir=d)["topic"] is None
    assert "잠김 1건" in CT.claim_next("W2", ["bench"], data_dir=d)["reasons"]
    for fn in (lambda: CT.advance(tid, "W2", data={"bench": {"a": 1}}, data_dir=d),
               lambda: CT.heartbeat(tid, "W2", data_dir=d),
               lambda: CT.release(tid, "W2", "x", data_dir=d)):
        with pytest.raises(CT.TopicError) as e:
            fn()
        assert e.value.code == 409
    # 같은 워커의 재claim 은 그대로 통과(멱등)
    assert CT.claim(tid, "W1", "bench", data_dir=d)["step"] == "bench"


def test_stale_lock_released_after_11min(env):
    d, clk = env
    tid = CT.add("a", "식품", data_dir=d)["id"]
    CT.claim(tid, "W1", "bench", data_dir=d)
    clk.tick(minutes=10)
    CT.heartbeat(tid, "W1", doing="영상 3/10", data_dir=d)
    clk.tick(minutes=10)                                             # 마지막 신호 뒤 10분 — 아직 산다
    with pytest.raises(CT.TopicError):
        CT.claim(tid, "W2", "bench", data_dir=d)
    b = CT.board(data_dir=d)
    assert b["workers"][0]["doing"] == "영상 3/10" and b["workers"][0]["stale"] is False
    clk.tick(minutes=1, seconds=1)                                   # 11분 1초 → 끊김
    r = CT.claim(tid, "W2", "bench", data_dir=d)
    assert r["topic"]["lock"]["owner"] == "W2"
    assert "끊김 해제: W1 bench" in r["topic"]["last_error"]
    with pytest.raises(CT.TopicError) as e:                          # 끊긴 워커는 advance 못 함
        CT.advance(tid, "W1", data={"bench": {"a": 1}}, data_dir=d)
    assert "W2" in e.value.msg
    assert any(h["kind"] == "expire" for h in CT.detail(tid, data_dir=d)["history"])


def test_release_requires_error(env):
    d, _ = env
    tid = CT.add("a", "식품", data_dir=d)["id"]
    CT.claim(tid, "W1", "bench", data_dir=d)
    with pytest.raises(CT.TopicError):
        CT.release(tid, "W1", "", data_dir=d)
    t = CT.release(tid, "W1", "yt-dlp 차단", data_dir=d)
    assert t["lock"]["owner"] is None and "yt-dlp 차단" in t["last_error"]
    assert CT.board(data_dir=d)["errors"][0]["id"] == tid


def test_cost_cap_refuses_claim(env):
    d, clk = env
    CT.set_caps({"typecast": 1, "gemini": 100}, data_dir=d)
    ids = []
    for n in ("a", "b"):
        tid = CT.add(n, "식품", data_dir=d)["id"]
        _to_plan_review(d, tid)
        CT.review(tid, "plan_review", "pass", data_dir=d)
        ids.append(tid)
    _do(d, ids[0], "W1", "produce", outputs={"final": "f.mp4"}, files={"f.mp4": "x"}, cost={"typecast": 1})
    with pytest.raises(CT.TopicError) as e:
        CT.claim(ids[1], "W1", "produce", data_dir=d)
    assert e.value.code == 429 and "typecast 1/1" in e.value.msg
    nxt = CT.claim_next("W1", ["produce"], data_dir=d)
    assert nxt["topic"] is None and any("하루 상한" in x for x in nxt["reasons"])
    caps = CT.board(data_dir=d)["caps"]
    assert caps["blocked"] == ["typecast"] and caps["blocked_steps"] == ["produce"]
    # gemini 를 안 쓰는 일은 그대로 된다 / 다음 날이면 풀린다
    clk.tick(days=1)
    assert CT.claim(ids[1], "W1", "produce", data_dir=d)["step"] == "produce"
    with pytest.raises(CT.TopicError):
        CT.set_caps({"evolink": 3}, data_dir=d)


def test_kpi_and_board(env):
    d, clk = env
    a = CT.add("a", "식품", data_dir=d)["id"]
    b = CT.add("b", "홈템", data_dir=d)["id"]
    CT.add("c", "홈템", data_dir=d)
    with pytest.raises(CT.TopicError) as e:
        CT.add("c", "홈템", data_dir=d)
    assert e.value.code == 409
    _to_plan_review(d, a)
    _to_plan_review(d, b)
    CT.review(a, "plan_review", "pass", data_dir=d)
    CT.review(b, "plan_review", "reject", reason="겹침", back_to=None, data_dir=d)   # 폐기
    clk.tick(hours=4)
    _do(d, a, "W1", "produce", outputs={"final": "f.mp4"}, files={"f.mp4": "x"}, cost={"typecast": 2})
    _do(d, a, "W1", "check", outputs={"verdict": "v.md"}, files={"v.md": "x"})
    CT.review(a, "final_review", "pass", data_dir=d)
    k = CT.board(data_dir=d)["kpi"]
    assert k["candidates_today"] == 3 and k["candidates_7d"][-1] == {"day": "2026-10-16", "n": 3}
    assert k["plan_review"] == {"pass": 1, "reject": 1, "rate": 0.5}
    assert k["final_review"] == {"pass": 1, "reject": 0, "rate": 1.0}
    assert k["hours_per_passed"] == {"n": 1, "avg": 4.0, "median": 4.0}
    assert k["cost_per_passed"] == {"gemini": 6.0, "typecast": 2.0}
    bd = CT.board(data_dir=d)
    assert bd["grid"]["식품"] == {"passed": 1} and bd["grid"]["홈템"] == {"rejected": 1, "found": 1}
    assert CT.next_step("rejected", None) is None                    # 폐기는 다음 일 없음
    with pytest.raises(CT.TopicError):
        CT.claim(b, "W1", "bench", data_dir=d)
    assert [t["id"] for t in CT.board(category="홈템", data_dir=d)["topics"]] == [3, 2]


# ── 라우트(관리자 전용) ────────────────────────────────────────────────────
def test_routes_roundtrip(env, monkeypatch):
    d, _ = env
    from fastapi.testclient import TestClient
    from shopping_shorts import app as A
    monkeypatch.setenv("CALCOPY_DATA_DIR", str(d))
    monkeypatch.setattr(A, "_require_admin", lambda request: None)
    cl = TestClient(A.app)
    r = cl.post("/api/admin/calcopy/topics", json={"name": "x", "category": "식품", "track": "bench"})
    assert r.status_code == 200, r.text
    tid = r.json()["topic"]["id"]
    assert cl.post(f"/api/admin/calcopy/topics/{tid}/claim", json={"worker": "W", "step": "score"}).status_code == 409
    assert cl.post("/api/admin/calcopy/topics/claim_next", json={"worker": "W"}).json()["step"] == "bench"
    assert cl.post(f"/api/admin/calcopy/topics/{tid}/heartbeat", json={"worker": "W", "doing": "1/3"}).status_code == 200
    up = cl.post(f"/api/admin/calcopy/topics/{tid}/upload/벤치.json", content=b'{"a":1}')
    assert up.json() == {"ok": True, "name": "벤치.json", "size": 7}
    r = cl.post(f"/api/admin/calcopy/topics/{tid}/advance",
                json={"worker": "W", "data": {"bench": {"v": 1}}, "outputs": {"bench": "벤치.json"}})
    assert r.json()["topic"]["state"] == "benched"
    det = cl.get(f"/api/admin/calcopy/topics/{tid}").json()
    url = det["files"][0]["url"]
    f = cl.get(url)
    assert f.status_code == 200 and f.content == b'{"a":1}'
    assert cl.get(f"/api/admin/calcopy/topics/{tid}/file/없음.md").status_code == 404
    assert cl.get("/api/admin/calcopy/topics/999").status_code == 404
    assert cl.post(f"/api/admin/calcopy/topics/{tid}/review", json={"stage": "plan_review", "verdict": "pass"}).status_code == 409
    assert cl.post(f"/api/admin/calcopy/topics/{tid}/reject", json={"reason": "", "back_to": "found"}).status_code == 400
    assert cl.post(f"/api/admin/calcopy/topics/{tid}/reject", json={"reason": "다시", "back_to": "found"}).json()["topic"]["state"] == "rejected"
    assert cl.post("/api/admin/calcopy/topics/caps", json={"gemini": 9}).json()["caps"]["gemini"] == 9
    assert cl.get("/api/admin/calcopy/topics").json()["caps"]["caps"]["gemini"] == 9


def test_routes_admin_only(env, monkeypatch):
    d, _ = env
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient
    from shopping_shorts import app as A
    monkeypatch.setenv("CALCOPY_DATA_DIR", str(d))
    monkeypatch.setattr(A, "_require_admin", lambda request: JSONResponse({"error": "관리자 전용"}, status_code=403))
    cl = TestClient(A.app)
    assert cl.get("/api/admin/calcopy/topics").status_code == 403
    assert cl.post("/api/admin/calcopy/topics", json={"name": "x", "category": "y"}).status_code == 403
    assert cl.post("/api/admin/calcopy/topics/1/upload/a.txt", content=b"x").status_code == 403
    assert not CT.db_path(d).exists() or CT.board(data_dir=d)["topics"] == []
