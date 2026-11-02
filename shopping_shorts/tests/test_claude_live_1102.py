# -*- coding: utf-8 -*-
"""숏클 실시간 연결(관제 304, 2026-11-02) — 회원 Claude ↔ 서버 ↔ 사장님 PC 대기실.
판단 주인 = claude_live.py 한 곳. 실제 텔레그램은 보내지 않는다(claude_live._tg 를 시험이 갈아 끼운다)."""
import types

import pytest

from shopping_shorts import app as app_module
from shopping_shorts import claude_flow as cf
from shopping_shorts import claude_live as live
from shopping_shorts import claude_portal as cp
from shopping_shorts.tests.test_claude_portal import FP1, _h, _key, _w, env  # noqa: F401 — pytest 픽스처


@pytest.fixture
def tg(monkeypatch):
    sent = []
    monkeypatch.setattr(live, "_tg", lambda text: sent.append(text))
    return sent


@pytest.fixture
def admin(monkeypatch):
    monkeypatch.setattr(app_module, "_require_admin", lambda request: None)


def _member(env):
    key = _key(env)
    c = env["client"]
    assert c.get("/api/claude/license", headers=_h(key)).status_code == 200      # 기기 등록
    return c, key


def _report(c, key, **b):
    return c.post("/api/claude/live/report", headers=_h(key), json=b)


# ── 회원 → 서버 ─────────────────────────────────────────────────────────
def test_보고가_사건으로_남고_관리자가_읽는다(env, tg, admin):
    c, key = _member(env)
    assert _report(c, key, kind="message", level="important", text="쿠팡 검색이 막혀요", sid="a" * 12, stage="제품 확인").json()["ok"]
    assert _report(c, key, kind="progress", text="장면 맞추는 중").json()["ok"]
    d = c.get("/api/admin/claude/live/events").json()
    assert [e["kind"] for e in d["events"]] == ["message", "progress"]
    e = d["events"][0]
    assert (e["level"], e["stage"], e["sid"], e["urgent"]) == ("important", "제품 확인", "a" * 12, True)
    assert d["events"][1]["urgent"] is False
    assert d["last_id"] == d["events"][1]["id"]
    # since_id 뒤로만 · urgent 만
    assert c.get(f"/api/admin/claude/live/events?since_id={d['last_id']}").json()["events"] == []
    assert [e["kind"] for e in c.get("/api/admin/claude/live/events?urgent=1").json()["events"]] == ["message"]


def test_보고_모양이_틀리면_거절_조용히_자르지_않는다(env, tg):
    c, key = _member(env)
    assert _report(c, key, kind="엉뚱", text="x").status_code == 400
    assert _report(c, key, kind="code_fix", text="x").status_code == 400          # 회원 경로로는 못 만든다(feedback 길만)
    assert _report(c, key, kind="message", level="엉뚱", text="x").status_code == 400
    assert _report(c, key, kind="message", text=" ").status_code == 400
    assert _report(c, key, kind="message", text="가" * 2001).status_code == 400
    assert _report(c, key, kind="message", text="가" * 2000).status_code == 200


def test_키_경로는_서버에_남지_않는다(env, tg, admin):
    c, key = _member(env)
    _report(c, key, kind="message", text=f"키 {key} 그리고 sk-abcdefghij0123456789xx 경로 C:\\Users\\홍길동\\a.txt 끝")
    t = c.get("/api/admin/claude/live/events").json()["events"][0]["text"]
    assert "SHORTEM-L1" not in t and "sk-abcdefghij" not in t and "홍길동" not in t and "끝" in t


def test_라이선스_없으면_못_쓴다(env, tg):
    c = env["client"]
    assert c.post("/api/claude/live/report", json={"kind": "message", "text": "x"}).status_code == 401
    assert c.post("/api/claude/live/pull", json={}).status_code == 401


def test_보고_속도_상한(env, tg, monkeypatch):
    c, key = _member(env)
    monkeypatch.setattr(live, "REPORT_PER_HOUR", 2)
    assert _report(c, key, kind="progress", text="1").status_code == 200
    assert _report(c, key, kind="progress", text="2").status_code == 200
    assert _report(c, key, kind="progress", text="3").status_code == 429


# ── 텔레그램 판정 ───────────────────────────────────────────────────────
def test_텔레그램은_중요와_막힘만_같은내용_5분_쿨다운(env, tg, monkeypatch):
    c, key = _member(env)
    now = [1_900_000_000]
    monkeypatch.setattr(live, "_now", lambda: now[0])
    _report(c, key, kind="progress", text="평범")
    _report(c, key, kind="message", text="평범한 말")
    _report(c, key, kind="done", text="완성")
    assert tg == []
    _report(c, key, kind="message", level="important", text="급해요")
    _report(c, key, kind="stuck", text="멈춤")
    _report(c, key, kind="error", text="오류")
    assert len(tg) == 3 and "급해요" in tg[0]
    now[0] += 299
    _report(c, key, kind="stuck", text="멈춤")          # 같은 내용 5분 안 — 사건은 남고 텔레그램은 없다
    _report(c, key, kind="stuck", text="다른 멈춤")      # 내용이 다르면 바로
    assert len(tg) == 4 and "다른 멈춤" in tg[3]
    now[0] += 2
    _report(c, key, kind="stuck", text="멈춤")          # 먼저 보낸 때로부터 301초 — 다시
    assert len(tg) == 5
    assert len(live.events(env["store"])["events"]) == 9


# ── 서버 → 회원 ─────────────────────────────────────────────────────────
def test_보내기_받기_전달표시(env, tg, admin):
    c, key = _member(env)
    r = c.post("/api/admin/claude/live/send", json={"cid": 0, "text": "목소리 키를 다시 넣어 주세요"}).json()
    assert r["ok"]
    mid = r["id"]
    p = c.post("/api/claude/live/pull", headers=_h(key), json={}).json()
    assert [(m["id"], m["text"]) for m in p["messages"]] == [(mid, "목소리 키를 다시 넣어 주세요")]
    # 받았다고 알리기 전에는 다시 준다(저장 전에 PC 가 꺼져도 잃지 않는다)
    assert len(c.post("/api/claude/live/pull", headers=_h(key), json={}).json()["messages"]) == 1
    assert c.post("/api/claude/live/pull", headers=_h(key), json={"got": [mid]}).json()["messages"] == []
    assert live.message(env["store"], mid)["delivered_at"] and not live.message(env["store"], mid)["read_at"]
    c.post("/api/claude/live/pull", headers=_h(key), json={"seen": [mid]})
    assert live.message(env["store"], mid)["read_at"]
    assert not tg                                        # 우리가 보낸 말은 알림이 아니다
    assert [e["kind"] for e in c.get("/api/admin/claude/live/events").json()["events"]] == ["reply"]


def test_남의_메시지는_받지도_표시하지도_못한다(env, tg):
    c, key = _member(env)
    st = env["store"]
    cp.issue_license(55, st)
    mid = live.send(st, 55, "다른 회원에게")["id"]
    assert c.post("/api/claude/live/pull", headers=_h(key), json={"got": [mid], "seen": [mid]}).json()["messages"] == []
    m = live.message(st, mid)
    assert not m["delivered_at"] and not m["read_at"]


def test_보내기_모양_검사(env, tg, admin):
    c, _ = _member(env)
    assert c.post("/api/admin/claude/live/send", json={"cid": 12345, "text": "없는 회원"}).status_code == 400
    assert c.post("/api/admin/claude/live/send", json={"cid": 0, "text": ""}).status_code == 400
    assert c.post("/api/admin/claude/live/send", json={"cid": 0, "text": "가" * (live.MSG_MAX + 1)}).status_code == 400
    assert c.post("/api/admin/claude/live/send", json={"cid": "abc", "text": "x"}).status_code == 400


def test_관리자_경로는_관리자만(env, tg, monkeypatch):
    monkeypatch.setattr(app_module, "_is_admin", lambda cid: False)
    c = env["client"]
    assert c.get("/api/admin/claude/live/events").status_code in (302, 303, 307, 401, 403)
    assert c.post("/api/admin/claude/live/send", json={"cid": 0, "text": "x"}).status_code in (302, 303, 307, 401, 403)
    assert c.post("/api/admin/claude/live/ping", json={}).status_code in (302, 303, 307, 401, 403)


# ── 서버가 스스로 만드는 사건(옛 회원 프로그램도 보인다) ─────────────────
def _flow_setup(env, monkeypatch, script):
    pdir = [p for p in cp.presets(env["store"]) if p["id"] == env["preset"]][0]["dir"]
    _w(pdir / "line.json", {"line": "hybrid", "version": "키치잇판"})
    it = iter(script)

    def step(state, measure, replies, user):
        out = dict(next(it))
        if "boom" in out:
            raise RuntimeError(out["boom"])
        extra = out.pop("state_extra", {})
        state.update(extra)
        return {**out, "state": state}
    fake = types.SimpleNamespace(start=lambda url, version, sid: {"sid": sid, "ref": url, "version": version, "phase": "a"}, step=step)
    monkeypatch.setattr(cf, "_flow", lambda: fake)
    return _member(env)


URL = "https://www.youtube.com/shorts/cNo91ddBwB8"


def _go(c, key, env, res=None):
    if res is None:
        return c.post("/api/claude/step", headers=_h(key), json={"step": "start", "preset": env["preset"], "source": {"url": URL}})
    return c.post("/api/claude/step", headers=_h(key), json={"step": "go", "payload": res["next_payload"]})


def test_지시서_멈춤_반려_과제_완성이_사건이_된다(env, tg, monkeypatch):
    c, key = _flow_setup(env, monkeypatch, [
        {"status": "execute", "message": "시작", "stage": {"no": 1, "total": 13, "text": "준비 확인"}, "do": []},
        {"status": "execute", "message": "그대로", "stage": {"no": 1, "total": 13, "text": "준비 확인"}, "do": []},
        {"status": "reject", "message": "반려", "stage": {"no": 7, "total": 13, "text": "대본 쓰기"}, "reject": {"why": "조사가 모자라요", "fix": "다시"}, "review": []},
        {"status": "review", "message": "과제", "stage": {"no": 8, "total": 13, "text": "장면 맞추기"}, "review": [{"id": "task_1"}],
         "state_extra": {"phase": "task_got", "_task": {"id": "task_1", "why": "재료가 모자라요", "detail": "속사정"}}},
        {"status": "stop", "message": "멈춤", "stage": {"no": 8, "total": 13, "text": "장면 맞추기"}, "why": "만들 수 없어요", "fix": "다른 소재"},
        {"status": "done", "message": "완성", "stage": {"no": 13, "total": 13, "text": "완성"}, "title": "제목", "video": "x.mp4"},
    ])
    res = _go(c, key, env).json()
    for _ in range(5):
        res = _go(c, key, env, res).json()
    ev = live.events(env["store"])["events"]
    assert [(e["kind"], e["stage"]) for e in ev] == [
        ("progress", "준비 확인"),               # 같은 단계 둘째 응답은 안 남긴다
        ("progress", "대본 쓰기"),               # 반려 = 평범한 재시도(텔레그램 없음)
        ("stuck", "장면 맞추기"),                # 제작자 과제
        ("stuck", "장면 맞추기"),                # 멈춤
        ("done", "완성")]
    assert "조사가 모자라요" in ev[1]["text"] and "재료가 모자라요" in ev[2]["text"] and "만들 수 없어요" in ev[3]["text"]
    assert all(e["sid"] == res["sid"] for e in ev)
    assert len(tg) == 2


def test_지시서_예외도_사건이_되고_그대로_터진다(env, tg, monkeypatch):
    c, key = _flow_setup(env, monkeypatch, [{"boom": "지시서 고장"}])
    with pytest.raises(RuntimeError):
        _go(c, key, env)
    ev = live.events(env["store"])["events"]
    assert [e["kind"] for e in ev] == ["error"] and "지시서 고장" in ev[0]["text"] and len(tg) == 1


def test_기록이_실패해도_제작은_안_깨지고_로그가_남는다(env, tg, monkeypatch, caplog):
    c, key = _flow_setup(env, monkeypatch, [{"status": "stop", "message": "멈춤", "why": "x", "fix": "y"}])
    monkeypatch.setattr(live, "note", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("장부 고장")))
    r = _go(c, key, env)
    assert r.status_code == 200 and r.json()["status"] == "stop"
    assert "실시간 기록 실패" in caplog.text


def test_code_fix_와_bug_가_사건이_되고_내용을_본다(env, tg, admin):
    c, key = _member(env)
    diff = "--- a/x.py\n+++ b/x.py\n" + "+줄\n" * 2000
    fid = c.post("/api/claude/feedback", headers=_h(key), json={"kind": "code_fix", "text": diff, "job_id": "a" * 12}).json()["id"]
    c.post("/api/claude/feedback", headers=_h(key), json={"kind": "bug", "text": "렌더가 멈춰요"})
    c.post("/api/claude/feedback", headers=_h(key), json={"kind": "request", "text": "요청이에요"})
    ev = c.get("/api/admin/claude/live/events").json()["events"]
    assert [e["kind"] for e in ev] == ["code_fix", "bug"]
    assert ev[0]["ref"] == fid and ev[0]["sid"] == "a" * 12 and len(ev[0]["text"]) <= 300
    assert ev[1]["urgent"] is True and len(tg) == 2
    d = c.get(f"/api/admin/claude/live/feedback?id={fid}").json()
    assert d["ok"] and d["feedback"]["text"] == diff.strip() and d["feedback"]["kind"] == "code_fix"
    assert c.get("/api/admin/claude/live/feedback?id=99999").status_code == 404


# ── 회원별 진행판 ───────────────────────────────────────────────────────
def test_회원별_진행판(env, tg, admin, monkeypatch):
    c, key = _flow_setup(env, monkeypatch, [{"status": "execute", "message": "시작", "stage": {"no": 3, "total": 13, "text": "원본 찾기"}, "do": []}])
    c.post("/api/claude/session", headers=_h(key), json={"action": "hold"})
    _go(c, key, env)
    _report(c, key, kind="message", text="잘 되고 있어요")
    live.send(env["store"], 0, "확인했어요")
    m = c.get("/api/admin/claude/live/events").json()["members"]
    assert len(m) == 1
    assert (m[0]["cid"], m[0]["online"], m[0]["stage"], m[0]["kind"], m[0]["undelivered"]) == (0, True, "원본 찾기", "reply", 1)
    assert m[0]["last_ts"] > 0


# ── 대기실 생존 ─────────────────────────────────────────────────────────
def test_대기실_5분_끊기면_한_번만_알린다(env, tg, admin, monkeypatch):
    c = env["client"]
    st = env["store"]
    now = [1_900_000_000]
    monkeypatch.setattr(live, "_now", lambda: now[0])
    assert live.check_watch(st) is False                 # 한 번도 안 켠 대기실은 알리지 않는다
    assert c.post("/api/admin/claude/live/ping", json={}).json()["ok"]
    now[0] += 299
    assert live.check_watch(st) is False
    now[0] += 2
    assert live.check_watch(st) is True and len(tg) == 1 and "대기실" in tg[0]
    now[0] += 3000
    assert live.check_watch(st) is False and len(tg) == 1
    c.post("/api/admin/claude/live/ping", json={})        # 돌아오면 다시 지킨다
    assert len(tg) == 2 and "돌아" in tg[1]
    now[0] += 301
    assert live.check_watch(st) is True and len(tg) == 3


def test_대기실을_일부러_끄면_알리지_않는다(env, tg, admin, monkeypatch):
    c = env["client"]
    now = [1_900_000_000]
    monkeypatch.setattr(live, "_now", lambda: now[0])
    c.post("/api/admin/claude/live/ping", json={})
    c.post("/api/admin/claude/live/ping", json={"stop": True})
    now[0] += 3000
    assert live.check_watch(env["store"]) is False and tg == []


# ── 대기실 도구 ─────────────────────────────────────────────────────────
class _Resp:
    def __init__(self, code, body):
        self.status_code, self._b = code, body

    def json(self):
        return self._b


class _Sess:
    def __init__(self, gets):
        self.gets, self.posts, self.cookies_seen = list(gets), [], []

    def get(self, url, **kw):
        self.cookies_seen.append(kw["headers"]["Cookie"])
        r = self.gets.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def post(self, url, **kw):
        self.posts.append((url, kw.get("json")))
        return _Resp(200, {"ok": True})


def test_대기실_한줄_출력과_쿠키_갱신_재시도(tmp_path):
    from tools import shortcl_watch as w
    ev = {"id": 7, "ts": 1_900_000_000, "cid": 12, "member": "홍길동", "sid": "a" * 12, "level": "important", "kind": "stuck",
          "stage": "제품\n확인", "text": "첫 줄\n둘째 줄"}
    line = w.line(ev)
    assert "\n" not in line and "홍길동(12)" in line and "첫 줄 둘째 줄" in line and "#7" in line
    out, mints = [], []
    s = _Sess([_Resp(403, {}), _Resp(200, {"ok": True, "events": [ev], "last_id": 7}), OSError("끊김"), OSError("끊김"),
               _Resp(200, {"ok": True, "events": [], "last_id": 7})])
    wt = w.Watcher(session=s, mint=lambda: mints.append(1) or f"ck{len(mints)}", emit=out.append, state_file=tmp_path / "last", base="http://x")
    wt.last = 6
    assert wt.tick() is False and len(mints) == 2 and out == []     # 403 → 쿠키 새로
    assert wt.tick() is True and wt.last == 7 and "#7" in out[0]
    assert (tmp_path / "last").read_text() == "7"
    assert wt.tick() is False and "끊겼" in out[1]
    assert wt.tick() is False and len(out) == 2                     # 끊김 알림은 한 줄만
    assert wt.tick() is True and "돌아" in out[2]
    assert s.cookies_seen[0] != s.cookies_seen[1]
    wt.ping()
    assert s.posts[-1][0].endswith("/api/admin/claude/live/ping")


def test_대기실_첫_시작은_옛_사건을_쏟지_않는다(tmp_path):
    from tools import shortcl_watch as w
    s = _Sess([_Resp(200, {"ok": True, "events": [], "last_id": 90})])
    out = []
    wt = w.Watcher(session=s, mint=lambda: "ck", emit=out.append, state_file=tmp_path / "last", base="http://x")
    assert wt.last is None
    wt.tick()
    assert wt.last == 90 and out == []


def test_metrics_records_numbers_only_for_long_steps(tmp_path):
    from shopping_shorts import claude_live as LIVE
    from shopping_shorts.store import Store
    st = Store(str(tmp_path / "m.db"))
    LIVE.metrics(st, 7, "s1", {"plan": {"_sec": 780.4, "cuts": 60, "cores": 8, "gate": {"sec": 500}, "phases": [["흐림", 400.0]], "sheet": "비밀 경로"},
                               "save": {"_sec": 1.0}}, "장면 맞추기")
    rows = LIVE.events(st, limit=10)["events"]
    assert len(rows) == 1 and rows[0]["kind"] == "metric" and rows[0]["urgent"] is False
    assert "plan 780초" in rows[0]["text"] and "코어 8" in rows[0]["text"] and "비밀" not in rows[0]["text"]
