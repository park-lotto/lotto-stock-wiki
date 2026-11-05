# -*- coding: utf-8 -*-
"""숏클 실시간 연결 — 회원 Claude ↔ 서버 ↔ 사장님 PC 대기실 Claude (관제 304, 2026-11-02 사장님
"고객 Claude 가 작업하다 문제 생긴 것·고친 것을 서버에서 봐야 하고, 서버에서 고객 쪽으로 메시지를 띄울 수 있어야 한다").

판단 주인 한 곳: 무엇을 사건으로 남기나(note·from_flow) · 무엇이 긴급인가(is_urgent) · 언제 텔레그램을 보내나(note·check_watch)
              · 메시지 전달 표시(pull). 라우트·화면·회원 프로그램·대기실 도구는 이 판단을 부르거나 결과를 그리기만 한다.
받지 않는 것: 영상·대본 본문·키. 글은 사건 하나에 TEXT_MAX 자까지이고 키·긴 토큰·PC 경로는 저장 전에 지운다(_clean).
서버가 스스로 만드는 사건(from_flow·feedback)이 있어 옛 회원 프로그램도 보인다.
기록 실패는 제작을 깨지 않되 삼키지 않는다(witness·from_flow 가 log.exception).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading

from shopping_shorts import claude_portal as CP

log = logging.getLogger(__name__)

REPORT_KINDS = ("progress", "stuck", "fix", "message", "done", "error")   # 회원 PC 가 보낼 수 있는 종류
ALERT_KINDS = ("stuck", "error", "code_fix")     # level 과 상관없이 바로 알리는 종류
LEVELS = ("info", "important")
TEXT_MAX = 2000
MSG_MAX = 1000                                   # 회원에게 보내는 말 — 회원 프로그램 firewall.TEAM_MAX(머리글 포함 1200자) 안
STAGE_MAX = 60
EVENT_HEAD = 300                                 # 서버가 만드는 사건 글 길이(본문은 원래 표에)
ALERT_COOLDOWN = 300                             # 같은 회원·종류·글은 5분에 한 번
WATCH_GAP = 300                                  # 대기실 신호가 이만큼 끊기면 알린다
REPORT_PER_HOUR = 120                            # 회원 한 명 시간당 사건 상한 — 고리에 빠진 Claude 가 텔레그램을 채우지 않게
ACK_MAX = 100
PULL_MAX = 20

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS claude_live_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, cid INTEGER NOT NULL, sid TEXT NOT NULL DEFAULT '',
        level TEXT NOT NULL, kind TEXT NOT NULL, stage TEXT NOT NULL DEFAULT '', text TEXT NOT NULL,
        ref INTEGER, notified_at INTEGER)""",
    "CREATE INDEX IF NOT EXISTS idx_claude_live_events_cid ON claude_live_events(cid, id)",
    "CREATE INDEX IF NOT EXISTS idx_claude_live_events_sid ON claude_live_events(sid, id)",
    """CREATE TABLE IF NOT EXISTS claude_live_msgs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER NOT NULL, cid INTEGER NOT NULL, sid TEXT NOT NULL DEFAULT '',
        text TEXT NOT NULL, author TEXT NOT NULL DEFAULT '', delivered_at INTEGER, read_at INTEGER)""",
    "CREATE INDEX IF NOT EXISTS idx_claude_live_msgs_cid ON claude_live_msgs(cid, delivered_at)",
    """CREATE TABLE IF NOT EXISTS claude_live_watch (
        id INTEGER PRIMARY KEY CHECK (id = 1), last_ping INTEGER NOT NULL DEFAULT 0, alerted_at INTEGER NOT NULL DEFAULT 0)""",
)
_ready: set = set()
_ready_lock = threading.Lock()

_KEY_LIKE = (re.compile(r"SHORTEM-L1\.[\w.\-]+"), re.compile(r"\b(?:sk|pk|rk)-[\w\-]{12,}"), re.compile(r"\bAIza[\w\-]{20,}"),
             re.compile(r"\bBearer\s+\S+"), re.compile(r"(?<![\w/])[A-Za-z0-9_+/=\-]{40,}"))
_PC_PATH = re.compile(r"(?:\b[A-Za-z]:[\\/]|(?<![\w.])/(?:Users|home)/)[^\s'\"<>|]*")


def _now():
    return CP._now()


def _ensure(store):
    key = str(store.db_path)
    if key in _ready:
        return
    with _ready_lock:
        CP.ensure_schema(store)
        with CP._tx(store) as c:
            for sql in _SCHEMA:
                c.execute(sql)
        _ready.add(key)


def _clean(text) -> str:
    """사건 글 — 키처럼 생긴 것·PC 경로(회원 이름이 든다)를 지운다."""
    s = str(text or "").strip()
    for rx in _KEY_LIKE:
        s = rx.sub("[가림]", s)
    return _PC_PATH.sub("[경로]", s)


def is_urgent(level, kind) -> bool:
    """긴급 판정 주인 — 텔레그램·대기실·관리자 화면 강조가 전부 이것을 쓴다."""
    return level == "important" or kind in ALERT_KINDS


def _urgent_sql():
    marks = ",".join("?" * len(ALERT_KINDS))
    return f"(level='important' OR kind IN ({marks}))", list(ALERT_KINDS)


def _tg(text):
    """텔레그램 — 요청을 기다리게 하지 않는다(뒤 줄). 실패는 로그로 남긴다. 시험에서는 보내지 않는다."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return

    def _send():
        try:
            from shopping_shorts import notify
            if not notify.send_telegram(str(text)[:1000]):
                log.warning("claude_live: 텔레그램 전송 실패(키 없음·네트워크) — 사건은 표에 남아 있다: %s", str(text)[:200])
        except Exception:      # noqa: BLE001 — 알림 실패가 요청을 깨면 안 된다. 대신 로그
            log.exception("claude_live: 텔레그램 전송 중 예외")
    threading.Thread(target=_send, daemon=True).start()


def _alert_text(store, cid, kind, stage, text) -> str:
    name = CP._member_name(store, cid) or "회원"
    return f"[숏클 {kind}] {name}({cid})" + (f" · {stage}" if stage else "") + f"\n{text[:500]}\n→ /admin '숏클 실시간'"


def note(store, cid, kind, text, level="info", sid="", stage="", ref=None) -> int:
    """사건 하나 남기기(유일한 입구) + 텔레그램 판정. 쿨다운은 DB 로 — 웹 프로세스가 여럿이어도 한 번만."""
    from shopping_shorts.claude_flow import SID_RE
    _ensure(store)
    now = _now()
    sid = str(sid or "")
    sid = sid if SID_RE.match(sid) else ""
    stage, text = _clean(stage)[:STAGE_MAX], _clean(text)[:TEXT_MAX]
    send = False
    with CP._tx(store, write=True) as c:
        eid = c.execute("INSERT INTO claude_live_events(ts, cid, sid, level, kind, stage, text, ref) VALUES(?,?,?,?,?,?,?,?)",
                        (now, cid, sid, level, kind, stage, text, ref)).lastrowid
        if is_urgent(level, kind):
            dup = c.execute("SELECT 1 FROM claude_live_events WHERE cid=? AND kind=? AND text=? AND notified_at>? LIMIT 1",
                            (cid, kind, text, now - ALERT_COOLDOWN)).fetchone()
            if not dup:
                c.execute("UPDATE claude_live_events SET notified_at=? WHERE id=?", (now, eid))
                send = True
    if send:
        _tg(_alert_text(store, cid, kind, stage, text))
    return eid


def witness(store, cid, kind, text, **kw):
    """서버가 스스로 남기는 사건 — 실패해도 제작·피드백을 깨지 않는다. 실패는 로그로."""
    try:
        return note(store, cid, kind, text, **kw)
    except Exception:          # noqa: BLE001 — 기록이 본 일을 막으면 안 된다
        log.exception("claude_live: 실시간 기록 실패 cid=%s kind=%s", cid, kind)
        return None


def report(ctx: dict, body: dict, store=None) -> dict:
    """회원 PC → 서버. 모양이 틀리면 거절한다(조용히 자르지 않는다)."""
    store = CP._store(store)
    _ensure(store)
    cid, _, _ = CP._front(store, ctx, "live_report")
    body = body if isinstance(body, dict) else {}
    kind, level, text = body.get("kind"), body.get("level") or "info", body.get("text")
    if kind not in REPORT_KINDS or level not in LEVELS or not isinstance(text, str) or not text.strip() or len(text) > TEXT_MAX:
        raise CP.PortalError("bad_request", f"kind·level·text(1~{TEXT_MAX}자)를 확인하세요")
    with CP._tx(store) as c:
        n = c.execute("SELECT COUNT(*) FROM claude_live_events WHERE cid=? AND ts>?", (cid, _now() - 3600)).fetchone()[0]
    if n >= REPORT_PER_HOUR:
        raise CP.PortalError("rate_limited", "보고가 너무 많습니다 — 잠시 뒤 다시 시도하세요", 600)
    return {"ok": True, "id": note(store, cid, kind, text, level=level, sid=body.get("sid"), stage=body.get("stage"))}


def from_flow(store, cid, sid, res: dict, state: dict):
    """지시서 응답 하나 → 사건(옛 회원 프로그램도 보이게). 판단 주인 — 어느 응답을 어떤 사건으로 남기나."""
    try:
        _ensure(store)
        status = res.get("status")
        stage = str((res.get("stage") or {}).get("text") or "")
        if status == "stop":
            fix = str(res.get("fix") or "")
            witness(store, cid, "stuck", (str(res.get("why") or res.get("message") or "멈췄습니다")[:EVENT_HEAD] + (f" / 할 일: {fix[:100]}" if fix else "")), sid=sid, stage=stage)
        elif status == "reject":        # 반려 = 평범한 고쳐 쓰기 — 진행판에만
            why = str((res.get("reject") or {}).get("why") or res.get("message") or "")
            witness(store, cid, "progress", f"반려: {why[:EVENT_HEAD]}", sid=sid, stage=stage)
        elif status == "review" and state.get("phase") == "task_got":     # 제작자 과제 = 막힌 순간(회원 Claude 가 푸는 중)
            t = state.get("_task") or {}
            detail = str(t.get("detail") or "")
            witness(store, cid, "stuck", f"제작자 과제 {t.get('id') or ''}: {str(t.get('why') or '')[:EVENT_HEAD]}" + (f" / {detail[:200]}" if detail else ""), sid=sid, stage=stage)
        elif status == "done":
            witness(store, cid, "done", str(res.get("title") or res.get("message") or "완성")[:EVENT_HEAD], sid=sid, stage=stage)
        elif stage:                     # 단계가 바뀔 때만 한 줄
            with CP._tx(store) as c:
                last = c.execute("SELECT stage FROM claude_live_events WHERE sid=? AND kind='progress' ORDER BY id DESC LIMIT 1", (sid,)).fetchone()
            if not last or last[0] != stage:
                witness(store, cid, "progress", str(res.get("message") or stage)[:EVENT_HEAD], sid=sid, stage=stage)
    except Exception:          # noqa: BLE001 — 기록이 제작을 막으면 안 된다
        log.exception("claude_live: 실시간 기록 실패 cid=%s sid=%s", cid, sid)


METRIC_MIN_SEC = 30      # 이보다 짧은 일은 안 적는다


def metrics(store, cid, sid, measure, stage=""):
    """실행기 숫자 → 사건 kind=metric(긴급 아님, 관리자 실시간 표) — 어디서 시간을 쓰는지 회원에게 묻지 않고 본다. 시간·횟수만."""
    try:
        for rid, r in (measure or {}).items():
            if not isinstance(r, dict) or float(r.get("_sec") or 0) < METRIC_MIN_SEC:
                continue
            parts = [f"{rid} {r['_sec']:.0f}초"]
            if isinstance(r.get("cuts"), int):
                parts.append(f"컷 {r['cuts']}")
            if r.get("cores"):
                parts.append(f"코어 {r['cores']}")
            if isinstance(r.get("gate"), dict) and r["gate"]:
                parts.append("글자검사 " + json.dumps(r["gate"], ensure_ascii=False))
            if isinstance(r.get("phases"), list) and r["phases"]:
                parts.append("구간 " + json.dumps(r["phases"], ensure_ascii=False))
            note(store, cid, "metric", _clean(" · ".join(parts)), sid=sid, stage=stage)
    except Exception:          # noqa: BLE001 — 기록이 제작을 막으면 안 된다
        log.exception("claude_live: 측정 기록 실패 cid=%s sid=%s", cid, sid)


def flow_crash(store, cid, sid, error):
    """지시서가 예외로 죽었다 — 회원은 서버 오류만 보니 여기서 남긴다."""
    witness(store, cid, "error", f"지시서 예외: {type(error).__name__}: {str(error)[:EVENT_HEAD]}", sid=sid)


def _ids(v) -> list:
    if not isinstance(v, list):
        return []
    return [i for i in v[:ACK_MAX] if isinstance(i, int) and not isinstance(i, bool)]


def pull(ctx: dict, body: dict, store=None) -> dict:
    """서버 → 회원. got = PC 파일에 저장함(delivered_at), seen = 회원 Claude 맥락에 넣음(read_at).
    got 을 받기 전까지는 다시 준다 — 저장 전에 PC 가 꺼져도 잃지 않는다. 남의 번호는 cid 조건으로 걸러진다."""
    store = CP._store(store)
    _ensure(store)
    cid, _, _ = CP._front(store, ctx, "live_pull")
    body = body if isinstance(body, dict) else {}
    got, seen, now = _ids(body.get("got")), _ids(body.get("seen")), _now()
    with CP._tx(store, write=True) as c:
        if got or seen:
            ids = got + seen
            c.execute(f"UPDATE claude_live_msgs SET delivered_at=? WHERE cid=? AND delivered_at IS NULL AND id IN ({','.join('?' * len(ids))})", [now, cid, *ids])
        if seen:
            c.execute(f"UPDATE claude_live_msgs SET read_at=? WHERE cid=? AND read_at IS NULL AND id IN ({','.join('?' * len(seen))})", [now, cid, *seen])
        rows = c.execute("SELECT id, ts, sid, text, author FROM claude_live_msgs WHERE cid=? AND delivered_at IS NULL ORDER BY id LIMIT ?", (cid, PULL_MAX)).fetchall()
    return {"ok": True, "messages": [dict(zip(("id", "ts", "sid", "text", "author"), r)) for r in rows]}


# ── 관리자 ──────────────────────────────────────────────────────────────
def send(store, cid, text, sid="", author="숏클 팀") -> dict:
    """관리자 → 회원. 회원 프로그램이 다음 신호(1분 안)에 받아 다음 도구 응답·다음 회원 말에 싣는다."""
    from shopping_shorts.claude_flow import SID_RE
    store = CP._store(store)
    _ensure(store)
    try:
        cid = int(cid)
    except (TypeError, ValueError):
        raise CP.PortalError("bad_request", "회원 번호가 올바르지 않습니다") from None
    text = str(text or "").strip()
    if not text or len(text) > MSG_MAX:
        raise CP.PortalError("bad_request", f"메시지는 1~{MSG_MAX}자입니다")
    sid = str(sid or "")
    sid = sid if SID_RE.match(sid) else ""
    with CP._tx(store, write=True) as c:
        if not c.execute("SELECT 1 FROM claude_licenses WHERE cid=? LIMIT 1", (cid,)).fetchone():
            raise CP.PortalError("bad_request", "라이선스가 없는 회원입니다")
        mid = c.execute("INSERT INTO claude_live_msgs(ts, cid, sid, text, author) VALUES(?,?,?,?,?)", (_now(), cid, sid, text, str(author or "")[:40])).lastrowid
    note(store, cid, "reply", text[:EVENT_HEAD], sid=sid, ref=mid)
    return {"ok": True, "id": mid}


def message(store, mid) -> dict | None:
    _ensure(store)
    with CP._tx(store) as c:
        return CP._row(c, "SELECT * FROM claude_live_msgs WHERE id=?", (mid,))


def feedback_detail(store, fid) -> dict | None:
    """code_fix·bug 전문(사건 글은 앞머리만) — 관리자 화면 '내용 보기'."""
    CP.ensure_schema(store)
    with CP._tx(store) as c:
        row = CP._row(c, "SELECT * FROM claude_feedback WHERE id=?", (fid,))
    if row:
        row["member"] = CP._member_name(store, row["cid"])
    return row


def members(store, limit=200) -> list:
    """회원별 진행판 — 지금 접속·최근 단계·마지막 시각·미전달 메시지 수."""
    from shopping_shorts import claude_flow as CF
    CF._ensure(store)
    _ensure(store)
    now = _now()
    out: dict = {}

    def slot(cid):
        return out.setdefault(cid, {"cid": cid, "last_ts": 0, "stage": "", "kind": "", "text": "", "sid": "", "status": "", "online": False, "device": "", "undelivered": 0})

    with CP._tx(store) as c:
        for r in c.execute("SELECT e.cid, e.ts, e.kind, e.text, e.sid FROM claude_live_events e "
                           "JOIN (SELECT cid, MAX(id) m FROM claude_live_events GROUP BY cid) x ON e.id=x.m").fetchall():
            s = slot(r[0])
            s.update(last_ts=r[1], kind=r[2], text=r[3][:200], sid=r[4])
        for r in c.execute("SELECT cid, stage, MAX(id) FROM claude_live_events WHERE stage<>'' GROUP BY cid").fetchall():
            slot(r[0])["stage"] = r[1]
        for r in c.execute("SELECT cid, sid, phase, status, MAX(updated) FROM claude_flow_runs GROUP BY cid").fetchall():
            s = slot(r[0])
            s.update(status=r[3] or "", stage=s["stage"] or (r[2] or ""), sid=s["sid"] or r[1], last_ts=max(s["last_ts"], r[4] or 0))
        for r in c.execute("SELECT cid, device_name, expires FROM claude_sessions WHERE fp_hash<>'' AND expires>?", (now,)).fetchall():
            s = slot(r[0])
            s.update(online=True, device=r[1] or "")
        for r in c.execute("SELECT cid, COUNT(*) FROM claude_live_msgs WHERE delivered_at IS NULL GROUP BY cid").fetchall():
            slot(r[0])["undelivered"] = r[1]
    rows = sorted(out.values(), key=lambda x: (x["online"], x["last_ts"]), reverse=True)[:limit]
    for s in rows:
        s["member"] = CP._member_name(store, s["cid"])
    return rows


def events(store, since_id=0, limit=200, cid=None, urgent=False, with_members=False) -> dict:
    """사건 목록(오래된 → 새). since_id 가 있으면 그 뒤로, 없으면 최근 limit 건. last_id = 다음에 줄 since_id."""
    store = CP._store(store)
    _ensure(store)
    limit = max(1, min(int(limit), 500))
    since_id = max(0, int(since_id))
    where, args = ["1=1"], []
    if since_id:
        where.append("id>?")
        args.append(since_id)
    if cid is not None:
        where.append("cid=?")
        args.append(int(cid))
    if urgent:
        sql, a = _urgent_sql()
        where.append(sql)
        args += a
    q = f"SELECT * FROM claude_live_events WHERE {' AND '.join(where)} ORDER BY id " + ("ASC" if since_id else "DESC") + " LIMIT ?"
    with CP._tx(store) as c:
        top = c.execute("SELECT COALESCE(MAX(id), 0) FROM claude_live_events").fetchone()[0]      # 먼저 재서 그 사이 들어온 것을 건너뛰지 않는다
        rows = CP._rows(c, q, [*args, limit])
    if not since_id:
        rows.reverse()
    names: dict = {}
    for e in rows:
        e["urgent"] = is_urgent(e["level"], e["kind"])
        e["member"] = names.setdefault(e["cid"], CP._member_name(store, e["cid"]))
    last = rows[-1]["id"] if since_id and len(rows) == limit else max(top, rows[-1]["id"] if rows else 0, since_id)
    out = {"ok": True, "events": rows, "last_id": last, "watch": watch_state(store)}
    if with_members:
        out["members"] = members(store)
    return out


# ── 대기실 생존 ─────────────────────────────────────────────────────────
def ping(store, stop=False) -> dict:
    """대기실 신호. stop=True = 일부러 끔(알리지 않는다). 끊겼다 알린 뒤 돌아오면 한 줄 알린다."""
    store = CP._store(store)
    _ensure(store)
    now = _now()
    with CP._tx(store, write=True) as c:
        row = CP._row(c, "SELECT * FROM claude_live_watch WHERE id=1")
        back = bool(row and row["alerted_at"])
        c.execute("INSERT INTO claude_live_watch(id, last_ping, alerted_at) VALUES(1,?,0) "
                  "ON CONFLICT(id) DO UPDATE SET last_ping=excluded.last_ping, alerted_at=0", (0 if stop else now,))
    if back and not stop:
        _tg("[숏클 대기실] 대기실 창이 다시 돌아왔습니다")
    return {"ok": True}


def check_watch(store) -> bool:
    """대기실 신호가 WATCH_GAP 끊겼으면 한 번만 알린다(app 주기 루프가 부른다 · 웹 프로세스가 여럿이어도 UPDATE 로 한 번만)."""
    store = CP._store(store)
    _ensure(store)
    now = _now()
    with CP._tx(store, write=True) as c:
        n = c.execute("UPDATE claude_live_watch SET alerted_at=? WHERE id=1 AND alerted_at=0 AND last_ping>0 AND last_ping<?", (now, now - WATCH_GAP)).rowcount
    if n:
        _tg("[숏클 대기실] 대기실 창 신호가 5분째 끊겼습니다 — PC 의 대기실 Claude 창을 확인하세요")
    return bool(n)


def watch_state(store) -> dict:
    _ensure(store)
    with CP._tx(store) as c:
        row = CP._row(c, "SELECT * FROM claude_live_watch WHERE id=1")
    last = int((row or {}).get("last_ping") or 0)
    return {"last_ping": last, "alive": bool(last) and _now() - last <= WATCH_GAP}
