# -*- coding: utf-8 -*-
"""숏클 회원 관리 표(관제 329) — 관리자가 계정·PC·접속을 보고 조작하면 회원 PC 가 그대로 막히고 풀린다."""
from shopping_shorts import claude_portal as cp
from shopping_shorts.tests.test_claude_guard import FRIEND, ME, _acquire, _as_admin, _full, _lic, _session, m  # noqa: F401
from shopping_shorts.tests.test_claude_portal import FP1, FP2, FP3, _h, _key, env  # noqa: F401


def _admin(m, method, url, **kw):
    _as_admin(m, True)
    try:
        return getattr(m["client"], method)(url, **kw)
    finally:
        _as_admin(m, False)


def _members(m):
    r = _admin(m, "get", "/api/admin/claude/members")
    assert r.status_code == 200
    return r.json()


def _me(m):
    [row] = [x for x in _members(m)["members"] if x["cid"] == 0]
    return row


def test_표에_계정_PC_사용중_엔진이_보인다(m):
    k = _key(m)
    assert m["client"].get("/api/claude/license", headers={**_h(k, FP1, engine="1.0.90", name="PC-a"), "X-Shortem-Claude": ME}).status_code == 200
    assert m["client"].get("/api/claude/license", headers=_h(k, FP2, engine="1.0.100", name="PC-b")).status_code == 200
    _session(m, k, FP1)
    row = _me(m)
    assert row["account"]["linked"] is True and row["account"]["bound"]
    assert [(d["slot"], d["name"], d["engine"]) for d in row["devices"]] == [(1, "PC-a", "1.0.90"), (2, "PC-b", "1.0.100")]
    assert row["online"]["name"] == "PC-a" and row["making"] is None
    assert ME not in str(_members(m))                                    # 계정 값은 표에도 안 나간다


def test_옛_엔진은_표시된다(m):
    k = _key(m)
    m["client"].get("/api/claude/license", headers=_h(k, FP1, engine="1.0.90", name="PC-a"))
    m["client"].get("/api/claude/license", headers=_h(k, FP2, engine="1.0.100", name="PC-b"))
    assert _admin(m, "post", "/api/admin/claude/guard", json={"min_engine": "1.0.100"}).json()["settings"]["min_engine"] == "1.0.100"
    assert [d["engine_old"] for d in _me(m)["devices"]] == [True, False]
    r = m["client"].get("/api/claude/license", headers=_h(k, FP1, engine="1.0.90", name="PC-a"))
    assert r.status_code == 426 or r.json()["code"] == "engine_old"     # 저장한 최소 엔진이 실제로 막는다


def test_계정_연결_풀면_새_계정으로_다시_묶인다(m):
    k = _key(m)
    assert _lic(m, k, FP1, ME).status_code == 200
    assert _lic(m, k, FP1, FRIEND).json()["code"] == "account_mismatch"
    r = _admin(m, "post", "/api/admin/claude/member/action", json={"cid": 0, "action": "unbind"}).json()
    assert r["ok"] and r["unbound"] is True
    assert cp.list_changes(m["store"]) == []                             # 대기 중이던 계정 변경 요청은 닫힌다
    assert _lic(m, k, FP1, FRIEND).status_code == 200                    # 바꾼 계정으로 바로 쓴다
    assert _lic(m, k, FP1, ME).json()["code"] == "account_mismatch"      # 이제 그 계정에 묶였다


def test_계정_검사를_끄면_다른_계정도_통과(m):
    k = _key(m)
    _lic(m, k, FP1, ME)
    assert _admin(m, "post", "/api/admin/claude/guard", json={"account_check": False}).json()["settings"]["account_check"] is False
    assert _lic(m, k, FP1, FRIEND).status_code == 200
    _admin(m, "post", "/api/admin/claude/guard", json={"account_check": True})
    assert _lic(m, k, FP1, FRIEND).json()["code"] == "account_mismatch"


def test_접속_끊으면_다른_PC가_쓴다(m):
    k = _full(m)
    _session(m, k, FP1)
    assert _session(m, k, FP2).status_code == 409
    r = _admin(m, "post", "/api/admin/claude/member/action", json={"cid": 0, "action": "kick"}).json()
    assert r["ok"] and r["kicked"] is True and r["stopped_job"] is False
    assert _me(m)["online"] is None
    assert _session(m, k, FP1).status_code == 409                        # 끊긴 PC 는 바로 되찾지 못한다
    assert _session(m, k, FP2).json()["ok"]


def test_제작_중_끊으면_제작도_멈춘다(m):
    k = _full(m)
    _session(m, k, FP1)
    assert _acquire(m, k, FP1).json()["ok"]
    assert _me(m)["making"]["name"] == "PC-a"
    r = _admin(m, "post", "/api/admin/claude/member/action", json={"cid": 0, "action": "kick"}).json()
    assert r["stopped_job"] is True
    hb = m["client"].post("/api/claude/lease", headers=_h(k, FP1), json={"action": "heartbeat", "job_id": "job-1"})
    assert hb.json().get("code") in ("lease_lost", "busy_session")
    assert _acquire(m, k, FP2, "job-2").json()["ok"]


def test_PC_한도를_바꾸면_등록이_따른다(m):
    k = _full(m)
    assert _lic(m, k, FP3).json()["code"] == "device_limit"
    assert _admin(m, "post", "/api/admin/claude/guard", json={"devices_max": 3}).json()["settings"]["devices_max"] == 3
    assert _lic(m, k, FP3).json()["device"]["slot"] == 3
    assert _admin(m, "post", "/api/admin/claude/guard", json={"devices_max": 1}).json()["ok"]
    assert len(_me(m)["devices"]) == 3                                   # 줄여도 이미 등록된 PC 는 그대로
    _admin(m, "post", "/api/admin/claude/devices/remove", json={"cid": 0, "device_id": FP3[:12]})
    assert _lic(m, k, FP3).json()["code"] == "device_limit"              # 한도 1 이 새 등록을 막는다


def test_틀린_설정값은_저장하지_않는다(m):
    for bad in ({"devices_max": 0}, {"devices_max": 9}, {"devices_max": "두대"}, {"min_engine": "최신"}):
        r = _admin(m, "post", "/api/admin/claude/guard", json=bad)
        assert r.status_code == 400 and r.json()["ok"] is False, bad
    g = _members(m)["settings"]
    assert (g["devices_max"], g["min_engine"], g["account_check"]) == (cp.DEVICES_MAX, "1.0.0", True)


def test_망가진_설정값은_기본으로(m):
    m["store"].set_setting("claude_devices_max", "많이")
    m["store"].set_setting("claude_min_engine", "x")
    assert cp.guard_settings(m["store"]) == {"devices_max": cp.DEVICES_MAX, "min_engine": "1.0.0", "account_check": True}


def test_회원은_관리자_창구를_못_쓴다(m):
    for method, url, kw in (("get", "/api/admin/claude/members", {}),
                            ("post", "/api/admin/claude/guard", {"json": {"devices_max": 5}}),
                            ("post", "/api/admin/claude/member/action", {"json": {"cid": 0, "action": "unbind"}})):
        assert getattr(m["client"], method)(url, **kw).status_code in (401, 403), url
    assert cp.guard_settings(m["store"])["devices_max"] == cp.DEVICES_MAX
