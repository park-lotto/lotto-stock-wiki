# -*- coding: utf-8 -*-
"""단계 배포(관제 304) — 1명 → 10% → 100%, 대상 고정, 사람 승인, 나빠지면 자동 되돌리기.
진짜 라우트 /api/claude/update 와 진짜 claude_flow_runs 행으로 본다. 판단 주인 = claude_portal.update_target·rollout_*.
"""
import json
import re
from pathlib import Path

import pytest

from shopping_shorts import claude_flow as cf
from shopping_shorts import claude_portal as cp
from shopping_shorts.tests.test_claude_portal import _h, _key, env  # noqa: F401 — pytest 픽스처
from tools.claude_portal import publish_update as pu


def _blob(tmp_path, name, data):
    f = tmp_path / name
    f.write_bytes(data)
    return cp.put_blob(f)


def _stage(tmp_path, env):
    """옛 판 1.0.1 이 전체에 깔린 상태 + 후보 1.0.2 묶음."""
    old_sha, old_size = _blob(tmp_path, "old.zip", b"PK-old")
    new_sha, new_size = _blob(tmp_path, "new.zip", b"PK-new")
    cp.update_register("1.0.1", old_sha, old_size, "옛 판")
    return {"old": old_sha, "new": new_sha, "new_size": new_size}


def _runs(store, engine, stop, done, created=None):
    cf._ensure(store)
    now = created or cp._now()
    with cp._tx(store, write=True) as c:
        for i, st in enumerate(["stop"] * stop + ["done"] * done):
            sid = f"{engine or 'x'}-{st}-{i}-{now}"
            c.execute("INSERT INTO claude_flow_runs(sid,cid,preset,version,seq,phase,status,created,updated,engine) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (sid, 1, "p", "판", 1, "x", st, now, now, engine))


def _table():
    return json.loads(cp.update_path().read_text(encoding="utf-8"))


def _cid(key):
    return cp._parse_key(key)[0]


def _mine(c, key, have="1.0.1"):
    assert c.get("/api/claude/license", headers=_h(key)).status_code == 200      # 기기 등록
    return c.get(f"/api/claude/update?have={have}", headers=_h(key)).json()


def test_대상은_cid_해시로_고정되고_퍼센트를_넓히면_앞사람은_그대로다():
    r10 = {"version": "1.0.2", "percent": 10, "cids": []}
    a = [c for c in range(5000) if cp.rollout_includes(r10, c)]
    assert a == [c for c in range(5000) if cp.rollout_includes(dict(r10), c)], "다시 재도 같은 사람"
    assert 400 < len(a) < 600, len(a)
    assert all(cp.rollout_includes({"version": "1.0.2", "percent": 100, "cids": []}, c) for c in a)
    assert not any(cp.rollout_includes({"version": "1.0.2", "percent": 0, "cids": [999999]}, c) for c in range(5000))
    assert cp.rollout_includes({"version": "1.0.2", "percent": 0, "cids": [7]}, 7)
    other = [c for c in range(5000) if cp.rollout_includes({"version": "1.0.3", "percent": 10, "cids": []}, c)]
    assert set(a) != set(other), "판마다 시험대상이 바뀐다(늘 같은 회원이 위험을 지지 않는다)"


def test_1명_단계는_지정_회원만_받고_나머지는_옛_판이다(env, tmp_path):
    c, st = env["client"], env["store"]
    s = _stage(tmp_path, env)
    key = _key(env)
    cid = _cid(key)
    assert _mine(c, key)["update"] is False                                       # 옛 판을 이미 가짐
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [cid + 1], "다른 회원 시험")
    assert _mine(c, key)["update"] is False, "대상이 아니면 후보를 받지 않는다"
    cp.rollout_rollback("시험 끝", by="시험", store=st)
    # 같은 판 번호는 회수됐으니 새 번호로
    cp.rollout_start("1.0.3", s["new"], s["new_size"], [cid], "이 회원 시험")
    got = _mine(c, key)
    assert got["update"] is True and got["version"] == "1.0.3" and got["sha256"] == s["new"], got
    assert _table()["version"] == "1.0.1", "전체 판(미리보기·빠른배포가 읽는 칸)은 그대로"


def test_넓히기는_순서대로_100은_사람_승인이_있어야만_된다(env, tmp_path):
    st = env["store"]
    s = _stage(tmp_path, env)
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [1], "")
    with pytest.raises(cp.PortalError):
        cp.rollout_advance(100, store=st, approved_by="사장님")          # 10% 건너뛰기
    with pytest.raises(cp.PortalError) as e:
        cp.rollout_advance(10, store=st)                                  # 표본 없음
    assert "편" in e.value.msg
    _runs(st, "1.0.2", 0, cp.ROLLOUT_MIN_RUNS)
    _runs(st, "1.0.1", 2, 20)
    assert cp.rollout_advance(10, store=st)["percent"] == 10
    with pytest.raises(cp.PortalError) as e:
        cp.rollout_advance(100, store=st)                                 # 승인자 없음
    assert e.value.code == "approval_required"
    for blank in ("", "   "):
        with pytest.raises(cp.PortalError):
            cp.rollout_advance(100, store=st, approved_by=blank)
    assert _table()["rollout"]["percent"] == 10, "거절되면 그대로"
    for _ in range(3):
        cp.rollout_tick(st, force=True)                                   # 감시는 자기가 넓히지 않는다
    assert _table()["rollout"]["percent"] == 10
    got = cp.rollout_advance(100, store=st, approved_by="사장님")
    assert got["percent"] == 100 and got["approved_by"] == "사장님"
    cp.rollout_finish()
    d = _table()
    assert (d["version"], d["sha256"], d.get("rollout")) == ("1.0.2", s["new"], None)
    assert d["previous"]["version"] == "1.0.1"


def test_실패율이_옛_판보다_나빠지면_자동으로_멈추고_이전_판으로_되돌린다(env, tmp_path):
    c, st = env["client"], env["store"]
    s = _stage(tmp_path, env)
    key = _key(env)
    cid = _cid(key)
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [cid], "")
    assert _mine(c, key)["version"] == "1.0.2"
    _runs(st, "1.0.1", 2, 18)
    _runs(st, "1.0.2", 3, 0)
    h = cp.rollout_tick(st, force=True)
    assert h["verdict"] == "bad" and h["rolled_back"] is True, h
    d = _table()
    assert d.get("rollout") is None and "1.0.2" in d["recalled"], d
    # 새 판을 이미 깐 회원은 옛 판을 받는다 — have 가 더 높아도(진짜 라우트)
    got = _mine(c, key, have="1.0.2")
    assert got["update"] is True and got["version"] == "1.0.1" and got["sha256"] == s["old"] and got["rollback"] is True, got
    assert _mine(c, key, have="1.0.1")["update"] is False, "옛 판 회원은 그대로"
    assert _mine(c, key, have="1.0.9")["update"] is False, "회수되지 않은 더 높은 판(개발본)은 내리지 않는다"
    with cp._tx(st) as x:
        al = cp._rows(x, "SELECT rule, detail FROM claude_alerts WHERE rule='rollout_rollback'")
    assert len(al) == 1 and "1.0.2" in al[0]["detail"], al
    with pytest.raises(cp.PortalError):
        cp.rollout_start("1.0.2", s["new"], s["new_size"], [cid], "")     # 회수된 판 다시 금지


def test_넓히기_직전에_나빠졌으면_넓히지_않고_되돌린다(env, tmp_path):
    st = env["store"]
    s = _stage(tmp_path, env)
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [1], "")
    _runs(st, "1.0.1", 2, 18)
    _runs(st, "1.0.2", 3, 1)
    with pytest.raises(cp.PortalError) as e:
        cp.rollout_advance(10, store=st)
    assert "되돌렸" in e.value.msg
    d = _table()
    assert d.get("rollout") is None and "1.0.2" in d["recalled"]


def test_나빠지지_않았으면_되돌리지_않는다_판정표(env, tmp_path):
    bad = cp.rollout_bad
    assert bad(3, 3, 2, 20) and bad(2, 2, 1, 50) and bad(6, 10, 10, 100)
    assert not bad(1, 10, 10, 100), "1편 막힘은 소음"
    assert not bad(2, 10, 20, 100), "옛 판과 같은 비율"
    assert not bad(0, 0, 10, 100), "표본 없음"
    assert not bad(1, 1, 2, 20), "1편으로 판 내리지 않는다"
    assert bad(3, 4, 0, 0), "옛 판 표본이 없어도 대부분 막히면 멈춘다"
    assert not bad(2, 4, 0, 0)
    st = env["store"]
    s = _stage(tmp_path, env)
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [1], "")
    _runs(st, "1.0.1", 2, 18)
    _runs(st, "1.0.2", 1, 9)
    h = cp.rollout_tick(st, force=True)
    assert h["verdict"] == "ok" and not h.get("rolled_back") and _table()["rollout"]["version"] == "1.0.2", h


def test_옛_판_대조는_판_시작_전_실적도_쓰고_후보_판_편은_시작_뒤만_센다(env, tmp_path):
    st = env["store"]
    s = _stage(tmp_path, env)
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [1], "")
    t0 = _table()["rollout"]["started"]
    _runs(st, "1.0.1", 1, 9, created=t0 - 86400)                 # 시작 하루 전 옛 판
    _runs(st, None, 1, 4, created=t0 - 86400)                    # 판 칸 생기기 전 행 = 옛 판
    _runs(st, "1.0.1", 9, 1, created=t0 - 86400 * 40)            # 너무 오래됨 — 안 센다
    _runs(st, "1.0.2", 5, 0, created=t0 - 100)                   # 시작 전 후보 판(개발 시험) — 안 센다
    h = cp.rollout_health(st)
    assert (h["new_stop"], h["new_n"], h["old_stop"], h["old_n"]) == (0, 0, 2, 15), h


def test_감시는_업데이트_창구에서_스스로_돌고_죽어도_업데이트를_막지_않는다(env, tmp_path, monkeypatch, caplog):
    c, st = env["client"], env["store"]
    s = _stage(tmp_path, env)
    key = _key(env)
    cid = _cid(key)
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [cid], "")
    _runs(st, "1.0.1", 2, 18)
    _runs(st, "1.0.2", 3, 0)
    got = _mine(c, key, have="1.0.2")                            # 크론 없이 첫 요청이 감시를 돌린다
    assert got["version"] == "1.0.1" and got["rollback"] is True, got

    cp.rollout_start("1.0.3", s["new"], s["new_size"], [cid], "")
    def boom(*a, **k):
        raise RuntimeError("감시 고장")
    monkeypatch.setattr(cp, "rollout_tick", boom)
    with caplog.at_level("ERROR"):
        got = _mine(c, key)
    assert got["version"] == "1.0.3"
    assert "감시" in caplog.text, "감시가 죽으면 조용히 넘어가지 않고 로그를 남긴다"


def test_감시는_주기마다_한_번만_잰다(env, tmp_path, monkeypatch):
    st = env["store"]
    s = _stage(tmp_path, env)
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [1], "")
    n = []
    real = cp.rollout_health
    monkeypatch.setattr(cp, "rollout_health", lambda *a, **k: n.append(1) or real(*a, **k))
    cp.rollout_tick(st)
    cp.rollout_tick(st)
    assert len(n) == 1


def test_전체_판_등록은_단계_배포를_덮지_않고_회수_기록을_지킨다(env, tmp_path):
    st = env["store"]
    s = _stage(tmp_path, env)
    cp.rollout_start("1.0.2", s["new"], s["new_size"], [1], "")
    with pytest.raises(cp.PortalError) as e:
        cp.update_register("1.0.3", s["new"], s["new_size"])       # 빠른배포가 끼어들면 100% 가 되는 구멍
    assert "단계 배포" in e.value.msg
    cp.rollout_rollback("시험", by="시험", store=st)
    with pytest.raises(cp.PortalError):
        cp.update_register("1.0.2", s["new"], s["new_size"])       # 회수된 번호를 전체 판으로
    cp.update_register("1.0.3", s["new"], s["new_size"], "다음 판")
    assert "1.0.2" in _table()["recalled"], "등록해도 회수 기록은 남는다"


def test_전체_판_등록은_서버_판보다_낮거나_같은_번호를_거절한다(env, tmp_path):
    """관제 330 — 다른 PC 가 먼저 낸 판(1.0.105)을 모르고 같은 번호로 덮으면 그 판을 받은 회원이 새 내용을 못 받는다."""
    s = _stage(tmp_path, env)                                     # 서버 판 1.0.1
    for bad in ("1.0.1", "1.0.0", "0.9.9", "1.0", "x"):
        with pytest.raises(cp.PortalError) as e:
            cp.update_register(bad, s["new"], s["new_size"])
        assert "높아야" in e.value.msg or "꼴" in e.value.msg
    assert _table()["version"] == "1.0.1", "거절되면 표는 그대로"
    cp.update_register("1.0.2", s["new"], s["new_size"], "다음 판")
    assert _table()["version"] == "1.0.2"
    cp.update_register("1.1.0", s["new"], s["new_size"])           # 기능 추가 칸 올림도 된다(숫자 비교)
    assert _table()["version"] == "1.1.0"


def test_판_표를_직접_쓰는_길이_도구에_남아_있지_않다():
    root = Path(__file__).resolve().parents[2]
    for f in ("publish_update.py", "upload_release.py", "fast_release.py"):
        src = (root / "tools" / "claude_portal" / f).read_text(encoding="utf-8")
        assert not re.search(r"update_path\(\)\.write_text", src), f"{f} 가 표를 직접 쓴다 — cp.update_register 한 곳으로"


def test_publish_update_명령으로_단계_배포를_끝까지(env, tmp_path, capsys):
    st = env["store"]
    db = str(tmp_path / "t.db")
    stage = tmp_path / "stage"
    for rel in ("server/index.js", "engine/tools/calcopy/make.py"):
        (stage / rel).parent.mkdir(parents=True, exist_ok=True)
        (stage / rel).write_text("x", encoding="utf-8")
    assert pu.main(["--stage", str(stage), "--version", "1.0.1", "--notes", "첫 판"]) == 0
    (stage / "server/index.js").write_text("y", encoding="utf-8")
    assert pu.main(["--stage", str(stage), "--version", "1.0.2", "--rollout-cid", "5", "--db", db]) == 0
    d = _table()
    assert d["version"] == "1.0.1" and d["rollout"]["version"] == "1.0.2" and d["rollout"]["cids"] == [5] and d["rollout"]["percent"] == 0
    assert d["rollout"]["started"] > 0
    capsys.readouterr()
    assert pu.main(["--rollout-status", "--db", db]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["rollout"]["version"] == "1.0.2" and out["health"]["new_n"] == 0
    _runs(st, "1.0.2", 0, cp.ROLLOUT_MIN_RUNS)
    _runs(st, "1.0.1", 1, 20)
    assert pu.main(["--rollout-advance", "10", "--db", db]) == 0
    with pytest.raises(SystemExit):
        pu.main(["--rollout-advance", "100", "--db", db])           # 승인자 없이
    assert _table()["rollout"]["percent"] == 10
    assert pu.main(["--rollout-advance", "100", "--approved-by", "사장님", "--db", db]) == 0
    assert pu.main(["--rollout-finish", "--db", db]) == 0
    assert _table()["version"] == "1.0.2"


def test_편을_시작하면_앱_판이_engine_칸에_남는다(env, monkeypatch):
    from shopping_shorts.tests.test_claude_flow import URL, _setup
    c, key, _ = _setup(env, monkeypatch)
    r = c.post("/api/claude/step", headers=_h(key, engine="1.0.7"), json={"step": "start", "preset": env["preset"], "source": {"url": URL}})
    assert r.status_code == 200, r.text
    with cp._tx(env["store"]) as x:
        row = cp._row(x, "SELECT engine, version FROM claude_flow_runs WHERE sid=?", (r.json()["sid"],))
    assert row == {"engine": "1.0.7", "version": "키치잇판"}, row       # version 칸은 프리셋 판


def test_라이브_표에_engine_칸이_붙는다(env):
    st = env["store"]
    cp.ensure_schema(st)
    c = st._conn()
    c.execute("DROP TABLE IF EXISTS claude_flow_runs")
    c.execute("CREATE TABLE claude_flow_runs (sid TEXT PRIMARY KEY, cid INTEGER NOT NULL, preset TEXT, version TEXT, seq INTEGER NOT NULL DEFAULT 0, "
              "phase TEXT, status TEXT, created INTEGER, updated INTEGER, summary_json TEXT)")
    c.commit()
    c.close()
    cf._ensure(st)                                                   # 라이브 표(칸 없음)에 붙는다
    c = st._conn()
    cols = [r[1] for r in c.execute("PRAGMA table_info(claude_flow_runs)").fetchall()]
    c.close()
    assert "engine" in cols
