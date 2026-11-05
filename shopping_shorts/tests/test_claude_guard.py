# -*- coding: utf-8 -*-
"""숏클 돌려쓰기 차단(관제 296) — Claude 계정 묶기·기기 교체 승인·동시 접속."""
import pytest

from shopping_shorts import app as app_module
from shopping_shorts import claude_portal as cp
from shopping_shorts.tests.test_claude_portal import FP1, FP2, FP3, _h, _key, env  # noqa: F401

FP4 = "d" * 64
ME, FRIEND = "1" * 64, "2" * 64


@pytest.fixture
def m(env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(app_module, "_is_admin", lambda cid: False)
    return env


def _as_admin(m, on):
    m["monkeypatch"].setattr(app_module, "_is_admin", lambda cid: on)


def _lic(m, k, fp, acct=None):
    h = _h(k, fp, name=f"PC-{fp[0]}")
    if acct:
        h["X-Shortem-Claude"] = acct
    return m["client"].get("/api/claude/license", headers=h)


def _full(m):
    k = _key(m)
    assert _lic(m, k, FP1).status_code == 200 and _lic(m, k, FP2).status_code == 200
    return k


def _alerts(m):
    return [a for a in cp.list_alerts(m["store"]) if a["rule"] == "A1"]


def _session(m, k, fp, action="hold"):
    return m["client"].post("/api/claude/session", headers=_h(k, fp), json={"action": action})


# ── 기기 교체 ─────────────────────────────────────────────────────────────
def test_새_PC_요청하고_승인_한번이면_바뀐다(m):
    k = _full(m)
    r = _lic(m, k, FP3)
    assert r.status_code == 403 and r.json()["code"] == "device_limit" and "교체를 요청" in r.json()["msg"]
    assert m["client"].get("/api/claude/me/home").json()["swap"] == {"name": "PC-c", "status": "new"}
    assert cp.list_changes(m["store"]) == []                     # 고르기 전에는 관리자에게 안 뜬다
    assert m["client"].post("/api/claude/me/device/swap", json={"device_id": FP1[:12]}).json()["ok"]
    assert "승인을 기다리는" in _lic(m, k, FP3).json()["msg"]
    [ch] = cp.list_changes(m["store"])
    assert (ch["old_name"], ch["name"], ch["done_30d"]) == ("PC-a", "PC-c", 0)
    _as_admin(m, True)
    assert m["client"].post("/api/admin/claude/changes/decide", json={"id": ch["id"], "approve": True}).json()["ok"]
    _as_admin(m, False)
    assert _lic(m, k, FP3).json()["device"]["slot"] == 1         # 재설치 없이 바로
    assert _lic(m, k, FP1).status_code == 403                    # 뺀 PC 는 막힌다
    assert [d["name"] for d in cp.admin_devices(0, m["store"])] == ["PC-c", "PC-b"]


def test_거절하면_그대로다(m):
    k = _full(m)
    _lic(m, k, FP3)
    cp.request_swap(0, FP1[:12], m["store"])
    [ch] = cp.list_changes(m["store"])
    cp.decide_change(ch["id"], False, m["store"])
    assert _lic(m, k, FP1).status_code == 200 and _lic(m, k, FP3).status_code == 403
    with pytest.raises(cp.PortalError):
        cp.decide_change(ch["id"], True, m["store"])             # 처리한 요청은 다시 못 누른다


def test_회원은_직접_못_뺀다(m):
    _full(m)
    assert m["client"].post("/api/claude/me/device/remove", json={"device_id": FP1[:12]}).status_code in (404, 405)
    r = m["client"].post("/api/claude/me/device/swap", json={"device_id": FP1[:12]})
    assert r.json()["ok"] is False                               # 새 PC 없이 요청만으로는 못 뺀다


def test_교체_대기중인_PC는_정지되지_않는다(m):
    k = _full(m)
    for _ in range(6):
        assert _lic(m, k, FP3).status_code == 403
    assert _alerts(m) == []


def test_대기와_다른_PC가_또_오면_경고_뒤_정지(m):
    k = _full(m)
    _lic(m, k, FP3)
    assert _lic(m, k, FP4).json()["code"] == "device_limit" and len(_alerts(m)) == 1
    assert _lic(m, k, FP3).json()["code"] == "suspended"


def test_승인_횟수가_쌓인다(m):
    k = _full(m)
    for old, new in ((FP1, FP3), (FP2, FP4)):
        _lic(m, k, new)
        cp.request_swap(0, old[:12], m["store"])
        cp.decide_change(cp.list_changes(m["store"])[0]["id"], True, m["store"])
    _lic(m, k, FP1)
    cp.request_swap(0, FP3[:12], m["store"])
    assert cp.list_changes(m["store"])[0]["done_30d"] == 2


def test_관리자는_바로_뺄_수_있다(m):
    k = _full(m)
    _as_admin(m, True)
    assert m["client"].post("/api/admin/claude/devices/remove", json={"cid": 0, "device_id": FP1[:12]}).json()["ok"]
    _as_admin(m, False)
    assert _lic(m, k, FP3).json()["device"]["slot"] == 1


# ── Claude 계정 ───────────────────────────────────────────────────────────
def test_첫_계정에_묶이고_다른_계정은_막힌다(m):
    k = _key(m)
    assert _lic(m, k, FP1, ME).status_code == 200
    r = _lic(m, k, FP1, FRIEND)
    assert r.status_code == 403 and r.json()["code"] == "account_mismatch"
    assert m["client"].get("/api/claude/me/home").json()["account_change"] is True
    [ch] = cp.list_changes(m["store"])
    assert ch["kind"] == "account"
    assert _lic(m, k, FP1, ME).status_code == 200                # 요청 중에도 원래 계정은 쓴다
    cp.decide_change(ch["id"], True, m["store"])
    assert _lic(m, k, FP1, FRIEND).status_code == 200 and _lic(m, k, FP1, ME).status_code == 403


def test_다른_계정의_새_PC는_빈자리도_못_차지한다(m):
    k = _key(m)
    _lic(m, k, FP1, ME)
    assert _lic(m, k, FP2, FRIEND).json()["code"] == "account_mismatch"
    assert len(cp.admin_devices(0, m["store"])) == 1


def test_등록_PC의_다른_길도_계정을_본다(m):
    k = _key(m)
    _lic(m, k, FP1, ME)
    h = _h(k, FP1)
    h["X-Shortem-Claude"] = FRIEND
    r = m["client"].post("/api/claude/lease", headers=h, json={"action": "acquire", "job_id": "job-1"})
    assert r.status_code == 403 and r.json()["code"] == "account_mismatch"


def test_계정값_없는_요청은_통과하고_묶이지_않는다(m):
    k = _key(m)
    assert _lic(m, k, FP1).status_code == 200
    assert _lic(m, k, FP1, ME).status_code == 200 and _lic(m, k, FP1, FRIEND).status_code == 403


def test_이상한_계정값은_없는_것으로_본다(m):
    k = _key(m)
    assert _lic(m, k, FP1, "x@gmail.com").status_code == 200
    assert _lic(m, k, FP1, ME).status_code == 200


def test_페이지에_계정값이_안_나간다(m):
    k = _key(m)
    _lic(m, k, FP1, ME)
    _lic(m, k, FP1, FRIEND)
    assert ME not in m["client"].get("/api/claude/me/home").text
    assert FRIEND not in str(cp.list_changes(m["store"]))


# ── 동시 접속 ─────────────────────────────────────────────────────────────
def _acquire(m, k, fp, job="job-1"):
    return m["client"].post("/api/claude/lease", headers=_h(k, fp), json={"action": "acquire", "job_id": job})


def test_켜져만_있는_PC는_자리를_못_뺏는다(m):
    k = _full(m)
    assert _session(m, k, FP1).json()["ok"]
    r = _session(m, k, FP2)                                      # 노트북에 숏클만 켜져 있다(저절로 나가는 신호)
    assert r.status_code == 409 and r.json()["code"] == "busy_session" and "PC-a" in r.json()["msg"]
    assert m["client"].get("/api/claude/me/home").json()["session"]["device"] == "PC-a"


def test_실제로_쓰면_자리를_가져온다(m):
    k = _full(m)
    _session(m, k, FP1)                                          # 노트북이 자리를 잡고 있어도
    assert _lic(m, k, FP2).status_code == 200                    # 데스크탑에서 실제로 쓰면 바로 된다
    assert _acquire(m, k, FP2).json()["ok"]
    assert _session(m, k, FP1).status_code == 409                # 이제 노트북 신호가 막힌다
    assert m["client"].get("/api/claude/me/home").json()["session"]["device"] == "PC-b"


def test_다른_PC가_만드는_중이면_기다린다(m):
    k = _full(m)
    _session(m, k, FP1)
    assert _acquire(m, k, FP1).json()["ok"]                      # 노트북이 영상을 만드는 중
    r = _lic(m, k, FP2)
    assert r.status_code == 409 and r.json()["code"] == "busy_session" and "만드는 중" in r.json()["msg"]
    assert _acquire(m, k, FP2, "job-2").json()["code"] == "busy_session"


def test_창_하나가_닫혀_자리를_뺏겨도_제작은_이어진다(m):
    """11-04 회원 572 재현: 데스크탑 창 하나가 닫히며 자리가 비자 노트북 신호가 가져가 데스크탑 제작이 3시간 막혔다."""
    k = _full(m)
    _session(m, k, FP1)                                          # 데스크탑(창 여러 개)
    assert _acquire(m, k, FP1).json()["ok"]
    _session(m, k, FP1, "release")                               # 데스크탑 창 하나가 닫힌다
    assert _session(m, k, FP2).json()["ok"]                      # 켜만 둔 노트북 신호가 빈자리를 잡는다
    r = m["client"].post("/api/claude/lease", headers=_h(k, FP1), json={"action": "acquire", "job_id": "job-1"})
    assert r.json()["ok"]                                        # 데스크탑 제작은 막히지 않는다
    assert _session(m, k, FP2).status_code == 409


def test_닫으면_다른_PC가_쓴다(m):
    k = _full(m)
    _session(m, k, FP1)
    assert _session(m, k, FP1, "release").json()["ok"]
    assert _session(m, k, FP2).json()["ok"] and _session(m, k, FP1).status_code == 409


def test_신호가_끊기면_3분_뒤_풀린다(m, monkeypatch):
    k = _full(m)
    _session(m, k, FP1)
    now = cp._now()
    monkeypatch.setattr(cp, "_now", lambda: now + cp.SESSION_TTL - 1)
    assert _session(m, k, FP2).status_code == 409
    monkeypatch.setattr(cp, "_now", lambda: now + cp.SESSION_TTL + 1)
    assert _session(m, k, FP2).status_code == 200


def test_강제_해제로_끊으면_앞_PC가_바로_되찾지_못한다(m):
    k = _full(m)
    _session(m, k, FP1)
    assert m["client"].post("/api/claude/me/lease/force_release").json()["kicked"] is True
    assert m["client"].get("/api/claude/me/home").json()["session"] is None
    assert _session(m, k, FP1).status_code == 409
    assert _session(m, k, FP2).json()["ok"]


def test_작업_중이면_첫_해제는_접속을_끊지_않는다(m):
    k = _full(m)
    _session(m, k, FP1)
    assert m["client"].post("/api/claude/lease", headers=_h(k, FP1), json={"action": "acquire", "job_id": "job-1"}).json()["ok"]
    r = m["client"].post("/api/claude/me/lease/force_release").json()
    assert r["released"] is True and r["kicked"] is False
    assert _session(m, k, FP1).status_code == 200                # 접속 자리는 그대로
    assert _session(m, k, FP2).status_code == 409


def test_막힌_PC도_새_판은_받는다(m):
    k = _full(m)
    _session(m, k, FP1)
    assert m["client"].get("/api/claude/update", headers=_h(k, FP2), params={"have": "1.0.0"}).json().get("code") != "busy_session"


def test_관리자는_묶기와_동시접속_제한을_받지_않는다(env, monkeypatch):  # noqa: F811
    monkeypatch.setattr(app_module, "_is_admin", lambda cid: True)
    k = _full(env)
    _session(env, k, FP1)
    assert _lic(env, k, FP2, ME).status_code == 200
    assert _lic(env, k, FP2, FRIEND).status_code == 200
