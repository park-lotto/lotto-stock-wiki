"""칼카피 소재창고 — 소재 하나가 한 행, 상태기계·잠금·비용 상한·KPI (관제 097, 2026-10-16).

판단 주인: 이 모듈 하나. 보드 화면·워커(실행기)·사람 검수는 전부 app.py `/api/admin/calcopy/topics*` 를 거쳐
여기 함수를 부른다 — 상태 전이·잠금·끊김·상한·KPI 를 다른 곳에서 계산하지 않는다.
규격(요청·응답 JSON): docs/superpowers/specs/2026-10-16-소재창고-api.md

원장: DATA_DIR/calcopy/topics.db (sqlite, git 밖 — 서버가 git 파일을 쓰면 자동배포가 멈춘다)
산출물: DATA_DIR/calcopy/topics/<id>/
DATA_DIR = 환경변수 CALCOPY_DATA_DIR, 없으면 shopping_shorts/data (calcopy_board 보관함과 같은 곳).

상태기계(볼케이노 next_step 꼴):
  found ─bench→ benched ─score→ scored ─assign→ assigned ─script→ scripted ─source→ sourced
  ─plan→ plan_review(사람) ─통과→ producing ─produce→ produced ─check→ final_review(사람) ─통과→ passed
  검수 반려 / 관리자 반려 → rejected(사유, back_to). back_to 가 있으면 워커가 그 상태의 일로 다시 집는다.

조용한 실패 금지: 거절은 전부 TopicError(한국어 이유, 상태코드). except: pass 없음.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import statistics
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))

STATES = ("found", "benched", "scored", "assigned", "scripted", "sourced", "plan_review",
          "producing", "produced", "final_review", "passed", "rejected")
# 워커 자리: 지금 상태 → (할 일, 끝나면 갈 상태)
FLOW = {
    "found": ("bench", "benched"),
    "benched": ("score", "scored"),
    "scored": ("assign", "assigned"),
    "assigned": ("script", "scripted"),
    "scripted": ("source", "sourced"),
    "sourced": ("plan", "plan_review"),
    "producing": ("produce", "produced"),
    "produced": ("check", "final_review"),
}
# 사람 자리: 검수 단계 → 통과하면 갈 상태. 워커는 여기서 claim·advance 못 한다.
HUMAN = {"plan_review": "producing", "final_review": "passed"}
STEPS = tuple(v[0] for v in FLOW.values())
BACK_TO_OK = tuple(FLOW)          # 반려 뒤 되돌아갈 수 있는 상태 = 워커 일이 있는 상태
TRACKS = ("bench", "discover")
DATA_KEYS = ("source", "bench", "score", "assign", "rights")
SCORE_N = 5                        # 소재 5기준
STALE_SEC = 11 * 60                # 마지막 신호가 11분 넘으면 끊김
COST_KINDS = ("gemini", "typecast", "seconds")   # seconds = 그 단계에 실제로 든 시간(초) — 상한 없음, 편당 시간 KPI
CAP_KINDS = ("gemini", "typecast")               # 하루 상한이 걸리는 것
DEFAULT_CAPS = {"gemini": 500, "typecast": 30}   # 임시 기본값 — caps 로 바꾼다
RETRY_AFTER_MIN = 30               # release·끊김 뒤 claim_next 가 그 행을 다시 주기까지(분)
STALL_AT = 3                       # 실패(release·끊김) 3회면 stalled — 사람이 unstall 해야 다시 돈다
WORKER_SHOW_SEC = 24 * 3600        # 보드에 보일 워커: 마지막 맥박 24시간 안
STEP_USES = {"bench": ("gemini",), "score": ("gemini",), "assign": (), "script": ("gemini",),
             "source": ("gemini",), "plan": (), "produce": ("typecast",), "check": ("gemini",)}
# advance 에 꼭 있어야 하는 산출물(토픽 폴더 안 실제 파일)
STEP_OUTPUT = {"script": "script", "plan": "plan", "produce": "final", "check": "verdict"}


class TopicError(Exception):
    """거절 — 이유(한국어)와 HTTP 상태코드. 400 입력 · 404 없음 · 409 상태/잠금 · 429 비용 상한."""

    def __init__(self, msg: str, code: int = 400):
        super().__init__(msg)
        self.msg, self.code = msg, code


# ── 위치·시각 ──────────────────────────────────────────────────────────────
def base_dir(data_dir=None) -> Path:
    root = Path(data_dir) if data_dir else (
        Path(os.environ["CALCOPY_DATA_DIR"]) if os.environ.get("CALCOPY_DATA_DIR")
        else Path(__file__).resolve().parent / "data")
    return root / "calcopy"


def db_path(data_dir=None) -> Path:
    return base_dir(data_dir) / "topics.db"


def topic_dir(tid: int, data_dir=None) -> Path:
    return base_dir(data_dir) / "topics" / str(int(tid))


def _now() -> datetime:
    """지금(KST). 시험은 이걸 바꿔 끊김·하루 경계를 만든다."""
    return datetime.now(KST)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _parse(s):
    return datetime.fromisoformat(s) if s else None


# ── DB ────────────────────────────────────────────────────────────────────
_SCHEMA = """
CREATE TABLE IF NOT EXISTS topics(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL, track TEXT NOT NULL,
  state TEXT NOT NULL, back_to TEXT,
  source TEXT DEFAULT '{}', bench TEXT DEFAULT '{}', score TEXT DEFAULT '{}', assign TEXT DEFAULT '{}',
  rights TEXT DEFAULT '{}', outputs TEXT DEFAULT '{}',
  cost_gemini INTEGER DEFAULT 0, cost_typecast INTEGER DEFAULT 0,
  lock_owner TEXT, lock_step TEXT, lock_at TEXT, heartbeat_at TEXT, doing TEXT,
  last_error TEXT, rework_n INTEGER DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, passed_at TEXT, by TEXT DEFAULT '', note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER, at TEXT, by TEXT, kind TEXT,
  from_state TEXT, to_state TEXT, step TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER, stage TEXT, verdict TEXT, reason TEXT,
  back_to TEXT, by TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS cost(
  id INTEGER PRIMARY KEY AUTOINCREMENT, topic_id INTEGER, day TEXT, kind TEXT, n INTEGER, step TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS workers(
  worker TEXT PRIMARY KEY, category TEXT, track TEXT, channel TEXT, doing TEXT, idle_reason TEXT,
  last_error TEXT, topic_id INTEGER, step TEXT, seen_at TEXT);
CREATE INDEX IF NOT EXISTS ix_events_topic ON events(topic_id);
CREATE INDEX IF NOT EXISTS ix_cost_day ON cost(day);
"""
# 나중에 붙은 칸 — 옛 DB 에도 ALTER 로 붙인다(한 곳)
_ADDED_COLS = (("cost_seconds", "cost_seconds INTEGER DEFAULT 0"), ("error_count", "error_count INTEGER DEFAULT 0"),
               ("retry_at", "retry_at TEXT"), ("stalled", "stalled INTEGER DEFAULT 0"))


@contextmanager
def _tx(data_dir=None):
    """쓰기 트랜잭션(BEGIN IMMEDIATE) — 잠금 판정·상태 전이가 원자적으로 한 번에 돈다."""
    p = db_path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(p), timeout=30, isolation_level=None)
    c.row_factory = sqlite3.Row
    try:
        c.executescript(_SCHEMA)
        have = {r[1] for r in c.execute("PRAGMA table_info(topics)")}
        for col, ddl in _ADDED_COLS:
            if col not in have:
                c.execute(f"ALTER TABLE topics ADD COLUMN {ddl}")
        c.execute("BEGIN IMMEDIATE")
        try:
            yield c
        except BaseException:
            c.execute("ROLLBACK")
            raise
        c.execute("COMMIT")
    finally:
        c.close()


def _event(c, tid, now, by, kind, frm=None, to=None, step=None, note=""):
    c.execute("INSERT INTO events(topic_id,at,by,kind,from_state,to_state,step,note) VALUES(?,?,?,?,?,?,?,?)",
              (tid, _iso(now), by or "", kind, frm, to, step, (note or "")[:1000]))


def _get(c, tid):
    r = c.execute("SELECT * FROM topics WHERE id=?", (int(tid),)).fetchone()
    if r is None:
        raise TopicError(f"없는 소재: {tid}", 404)
    return r


def next_step(state, back_to=None):
    """워커가 할 다음 일. 사람 검수 자리·passed·폐기(rejected, back_to 없음)는 None."""
    if state in FLOW:
        return FLOW[state][0]
    if state == "rejected" and back_to in FLOW:
        return FLOW[back_to][0]
    return None


def _topic(r, now) -> dict:
    hb = _parse(r["heartbeat_at"])
    age = int((now - hb).total_seconds()) if (r["lock_owner"] and hb) else None
    return {
        "id": r["id"], "name": r["name"], "category": r["category"], "track": r["track"],
        "state": r["state"], "back_to": r["back_to"],
        "next_step": next_step(r["state"], r["back_to"]),
        "human_stage": r["state"] if r["state"] in HUMAN else None,
        **{k: json.loads(r[k] or "{}") for k in DATA_KEYS},
        "outputs": json.loads(r["outputs"] or "{}"),
        "cost": {"gemini": r["cost_gemini"], "typecast": r["cost_typecast"], "seconds": r["cost_seconds"]},
        "error_count": r["error_count"], "retry_at": r["retry_at"], "stalled": bool(r["stalled"]),
        "lock": {"owner": r["lock_owner"], "step": r["lock_step"], "at": r["lock_at"],
                 "heartbeat_at": r["heartbeat_at"], "doing": r["doing"], "age_sec": age,
                 "stale": bool(age is not None and age > STALE_SEC)},
        "last_error": r["last_error"], "rework_n": r["rework_n"],
        "created_at": r["created_at"], "updated_at": r["updated_at"], "passed_at": r["passed_at"],
        "by": r["by"], "note": r["note"],
    }


def _fail(c, r, now, by, kind, msg, retry_min=RETRY_AFTER_MIN, count=True):
    """잠금을 풀고 실패를 센다(끊김·release 공통). STALL_AT 회면 stalled — claim 이 막히고 보드 '멈춘 이유'에 고정.
    count=False = 우리 쪽 한도(시간당 제미나이·429 쉼)로 못 한 것 — 소재 탓이 아니니 실패 횟수에 안 넣는다(대기만)."""
    n = (r["error_count"] or 0) + (1 if count else 0)
    stalled = 1 if (count and n >= STALL_AT) or r["stalled"] else 0
    retry = _iso(now + timedelta(minutes=retry_min))
    c.execute("UPDATE topics SET lock_owner=NULL,lock_step=NULL,lock_at=NULL,heartbeat_at=NULL,doing=NULL,"
              "last_error=?,error_count=?,retry_at=?,stalled=?,updated_at=? WHERE id=?",
              (msg, n, retry, stalled, _iso(now), r["id"]))
    _event(c, r["id"], now, by, kind, r["state"], r["state"], r["lock_step"],
           msg + ((f" — 한도 대기(실패 횟수 안 셈), {retry} 뒤 다시") if not count else
                  (f" — 실패 {n}회, 멈춤(stalled)" if stalled else f" — 실패 {n}회, {retry} 뒤 다시")))


def _touch_worker(c, worker, now, **kw):
    """워커 맥박 표 갱신. 잡기·맥박·끝내기·손떼기·workers/heartbeat 가 모두 여기를 지난다."""
    c.execute("INSERT OR IGNORE INTO workers(worker,seen_at) VALUES(?,?)", (worker, _iso(now)))
    sets, args = ["seen_at=?"], [_iso(now)]
    for k, v in kw.items():
        sets.append(f"{k}=?")
        args.append(v)
    c.execute(f"UPDATE workers SET {','.join(sets)} WHERE worker=?", [*args, worker])


def _expire(c, now) -> int:
    """마지막 신호가 11분 넘은 잠금을 푼다 — 이력(expire)과 last_error 로 드러낸다."""
    cutoff = now - timedelta(seconds=STALE_SEC)
    n = 0
    for r in c.execute("SELECT * FROM topics WHERE lock_owner IS NOT NULL").fetchall():
        hb = _parse(r["heartbeat_at"]) or _parse(r["lock_at"])
        if hb and hb >= cutoff:
            continue
        msg = f"끊김 해제: {r['lock_owner']} {r['lock_step']} 마지막 신호 {r['heartbeat_at']}"
        _fail(c, r, now, "server", "expire", msg, retry_min=0)   # 죽은 워커 몫은 곧바로 다른 워커가 인수(실패로는 센다)
        n += 1
    return n


# ── 비용 상한 ──────────────────────────────────────────────────────────────
def _caps(c) -> dict:
    r = c.execute("SELECT value FROM settings WHERE key='caps'").fetchone()
    caps = dict(DEFAULT_CAPS)
    if r:
        caps.update(json.loads(r["value"]))
    return caps


def _caps_state(c, now) -> dict:
    day = now.strftime("%Y-%m-%d")
    caps = _caps(c)
    used = {k: 0 for k in COST_KINDS}
    for r in c.execute("SELECT kind, SUM(n) s FROM cost WHERE day=? GROUP BY kind", (day,)):
        used[r["kind"]] = r["s"] or 0
    blocked = [k for k in CAP_KINDS if used[k] >= caps[k]]
    steps = [s for s in STEPS if any(k in blocked for k in STEP_USES[s])]
    return {"day": day, "caps": caps, "used": used, "blocked": blocked, "blocked_steps": steps}


def _cap_refusal(cs, step):
    for k in STEP_USES.get(step, ()):
        if k in cs["blocked"]:
            return f"하루 상한: {k} {cs['used'][k]}/{cs['caps'][k]} ({cs['day']}) — {step} 멈춤"
    return None


def set_caps(caps: dict, data_dir=None) -> dict:
    if not isinstance(caps, dict) or not caps:
        raise TopicError("상한 값이 없습니다(gemini·typecast)")
    bad = [k for k in caps if k not in CAP_KINDS]
    if bad:
        raise TopicError(f"상한을 걸 수 없는 종류: {bad} — {list(CAP_KINDS)} 만")
    for k, v in caps.items():
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise TopicError(f"상한은 0 이상 정수: {k}={v!r}")
    with _tx(data_dir) as c:
        cur = _caps(c)
        cur.update(caps)
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('caps',?)", (json.dumps(cur),))
    return cur


# ── 입력 검사 ─────────────────────────────────────────────────────────────
_BAD_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_name(name) -> str:
    """토픽 폴더 안 파일 이름 하나. 폴더 밖(..·/·드라이브)은 거절."""
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise TopicError(f"파일 이름이 비었거나 깁니다: {name!r}")
    if _BAD_NAME.search(name) or name.startswith(".") or name != name.strip():
        raise TopicError(f"쓸 수 없는 파일 이름: {name!r} (/ \\ : .. 앞점 금지)")
    return name


def _write_file(d: Path, name: str, data: bytes):
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / (name + ".part")
    tmp.write_bytes(data)
    tmp.replace(d / name)


# ── 동작 ──────────────────────────────────────────────────────────────────
def add(name, category, track="discover", source=None, by="", note="", data_dir=None) -> dict:
    name = (name or "").strip() if isinstance(name, str) else ""
    category = (category or "").strip() if isinstance(category, str) else ""
    if not name or not category:
        raise TopicError("소재 이름·카테고리가 필요합니다")
    if track not in TRACKS:
        raise TopicError(f"트랙은 {list(TRACKS)} 중 하나: {track!r}")
    if source is not None and not isinstance(source, dict):
        raise TopicError("source 는 객체여야 합니다")
    now = _now()
    with _tx(data_dir) as c:
        dup = c.execute("SELECT id,state FROM topics WHERE name=? AND category=? AND state!='passed' "
                        "AND NOT (state='rejected' AND back_to IS NULL)", (name, category)).fetchone()
        if dup:
            raise TopicError(f"중복 소재: #{dup['id']} ({dup['state']}) 가 이미 진행 중", 409)
        cur = c.execute("INSERT INTO topics(name,category,track,state,source,created_at,updated_at,by,note) "
                        "VALUES(?,?,?,?,?,?,?,?,?)",
                        (name, category, track, "found", json.dumps(source or {}, ensure_ascii=False),
                         _iso(now), _iso(now), by or "", note or ""))
        tid = cur.lastrowid
        _event(c, tid, now, by, "add", None, "found", None, note)
        r = _get(c, tid)
    topic_dir(tid, data_dir).mkdir(parents=True, exist_ok=True)
    return _topic(r, now)


def _claim_row(c, r, worker, step, now, cs):
    """한 행을 잡는다(검사 전부 여기). claim·claim_next 가 같이 쓴다."""
    state = r["state"]
    if state in HUMAN:
        raise TopicError(f"사람 검수 자리({state}) — 워커는 넘지 못합니다", 409)
    if r["stalled"]:
        raise TopicError(f"멈춤(stalled): 실패 {r['error_count']}회 — 사람이 풀어야 합니다(unstall). "
                         f"마지막: {r['last_error']}", 409)
    ns = next_step(state, r["back_to"])
    if ns is None:
        raise TopicError(f"다음 일 없음(상태 {state}{', 폐기' if state == 'rejected' else ''})", 409)
    if step != ns:
        raise TopicError(f"지금 상태({state})의 다음 일은 {ns} 입니다 — {step} 아님", 409)
    if r["lock_owner"]:
        if r["lock_owner"] == worker and r["lock_step"] == step:
            c.execute("UPDATE topics SET heartbeat_at=? WHERE id=?", (_iso(now), r["id"]))
            return
        hb = _parse(r["heartbeat_at"])
        age = int((now - hb).total_seconds()) if hb else None
        raise TopicError(f"잠김: {r['lock_owner']} 가 {r['lock_step']} 중(마지막 신호 {r['heartbeat_at']}, "
                         f"{age}초 전)", 409)
    why = _cap_refusal(cs, step)
    if why:
        raise TopicError(why, 429)
    sets, args = "", []
    if state == "rejected":
        back = r["back_to"]
        sets = ",state=?,back_to=NULL,rework_n=rework_n+1"
        args = [back]
        _event(c, r["id"], now, worker, "rework", "rejected", back, step, "반려 뒤 재작업")
    c.execute(f"UPDATE topics SET lock_owner=?,lock_step=?,lock_at=?,heartbeat_at=?,doing=NULL,updated_at=?{sets} "
              "WHERE id=?", [worker, step, _iso(now), _iso(now), _iso(now), *args, r["id"]])
    _touch_worker(c, worker, now, topic_id=r["id"], step=step, doing=None, idle_reason=None)
    _event(c, r["id"], now, worker, "claim", r["state"] if state != "rejected" else r["back_to"], None, step)


def _need_worker(worker):
    if not isinstance(worker, str) or not worker.strip():
        raise TopicError("worker 이름이 필요합니다")
    return worker.strip()


def claim(tid, worker, step, data_dir=None) -> dict:
    worker = _need_worker(worker)
    if step not in STEPS:
        raise TopicError(f"모르는 일: {step!r} — {list(STEPS)}")
    now = _now()
    with _tx(data_dir) as c:
        _expire(c, now)
        r = _get(c, tid)
        _claim_row(c, r, worker, step, now, _caps_state(c, now))
        return {"topic": _topic(_get(c, tid), now), "step": step}


def _as_set(v, what):
    if v is None or v == "" or v == []:
        return None
    vals = [v] if isinstance(v, str) else v
    if not isinstance(vals, (list, tuple)) or not all(isinstance(x, str) and x for x in vals):
        raise TopicError(f"{what} 는 문자열 또는 문자열 목록이어야 합니다: {v!r}")
    return set(vals)


def claim_next(worker, steps=None, category=None, track=None, channel=None, data_dir=None) -> dict:
    """steps 중 하나를 할 수 있는 가장 오래된 소재를 잡는다. 없으면 왜 없는지(reasons).

    거르기: category·track(소재 칸) · channel(assign.channel — 배정 전 소재는 channel 을 주면 안 잡힌다).
    release·끊김 뒤 retry_at 이 안 지난 행과 stalled 행은 건너뛴다(직접 claim 은 retry_at 무시, stalled 는 막음).
    """
    worker = _need_worker(worker)
    cats, trks, chans = _as_set(category, "category"), _as_set(track, "track"), _as_set(channel, "channel")
    if trks and trks - set(TRACKS):
        raise TopicError(f"트랙은 {list(TRACKS)} 중: {sorted(trks)}")
    steps = list(steps or STEPS)
    bad = [s for s in steps if s not in STEPS]
    if bad:
        raise TopicError(f"모르는 일: {bad}")
    now = _now()
    with _tx(data_dir) as c:
        _expire(c, now)
        cs = _caps_state(c, now)
        locked, capped, waiting, stalled = 0, set(), 0, 0
        for r in c.execute("SELECT * FROM topics ORDER BY id").fetchall():
            ns = next_step(r["state"], r["back_to"])
            if ns not in steps or r["state"] in HUMAN:
                continue
            if (cats and r["category"] not in cats) or (trks and r["track"] not in trks):
                continue
            if chans and (json.loads(r["assign"] or "{}").get("channel") not in chans):
                continue
            if r["stalled"]:
                stalled += 1
                continue
            if r["retry_at"] and _parse(r["retry_at"]) > now:
                waiting += 1
                continue
            if r["lock_owner"] and not (r["lock_owner"] == worker and r["lock_step"] == ns):
                locked += 1
                continue
            why = _cap_refusal(cs, ns)
            if why:
                capped.add(why)
                continue
            _claim_row(c, r, worker, ns, now, cs)
            return {"topic": _topic(_get(c, r["id"]), now), "step": ns}
        reasons = sorted(capped) + ([f"잠김 {locked}건"] if locked else []) + (
            [f"실패 뒤 다시 시도 대기 {waiting}건"] if waiting else []) + (
            [f"멈춤(stalled) {stalled}건 — 사람이 unstall"] if stalled else [])
        filt = {k: sorted(v) for k, v in (("category", cats), ("track", trks), ("channel", chans)) if v}
        _touch_worker(c, worker, now, topic_id=None, step=None)
        return {"topic": None, "step": None,
                "reasons": reasons or [f"{steps}{' ' + json.dumps(filt, ensure_ascii=False) if filt else ''} 할 소재 없음"]}


def _held(c, tid, worker, now):
    r = _get(c, tid)
    if r["state"] in HUMAN:
        raise TopicError(f"사람 검수 자리({r['state']}) — 워커는 넘지 못합니다", 409)
    if not r["lock_owner"]:
        raise TopicError("잠금 없음(claim 안 했거나 11분 끊김으로 풀림) — 다시 claim 하세요", 409)
    if r["lock_owner"] != worker:
        raise TopicError(f"잠근 워커가 아님: 지금 {r['lock_owner']} 가 {r['lock_step']} 중", 409)
    return r


def heartbeat(tid, worker, doing=None, data_dir=None) -> dict:
    worker = _need_worker(worker)
    now = _now()
    with _tx(data_dir) as c:
        _expire(c, now)
        _held(c, tid, worker, now)
        c.execute("UPDATE topics SET heartbeat_at=?,doing=? WHERE id=?",
                  (_iso(now), (doing or "")[:200] or None, int(tid)))
        _touch_worker(c, worker, now, doing=(doing or "")[:200] or None)
    return {"heartbeat_at": _iso(now)}


def _check_data(data):
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise TopicError("data 는 객체여야 합니다")
    bad = [k for k in data if k not in DATA_KEYS]
    if bad:
        raise TopicError(f"모르는 data 칸: {bad} — {list(DATA_KEYS)} 만")
    for k, v in data.items():
        if not isinstance(v, dict):
            raise TopicError(f"data.{k} 는 객체여야 합니다")
    return data


def _check_required(step, merged, outputs, d: Path, pending_files):
    def has(name):
        return name in pending_files or (d / name).is_file()

    if step == "bench" and not merged["bench"]:
        raise TopicError("bench 단계: data.bench 가 비었습니다(새 소재면 {\"skipped\": \"이유\"})")
    if step == "score":
        crit = (merged["score"] or {}).get("criteria")
        if not isinstance(crit, dict) or len(crit) < SCORE_N:
            raise TopicError(f"score 단계: data.score.criteria 에 {SCORE_N}기준이 필요합니다"
                             f"(지금 {len(crit) if isinstance(crit, dict) else 0}개)")
        for k, v in crit.items():
            if not isinstance(v, dict) or not isinstance(v.get("score"), (int, float)) or isinstance(
                    v.get("score"), bool) or not str(v.get("why") or "").strip():
                raise TopicError(f"score 단계: 기준 '{k}' 에 score(숫자)·why(근거)가 필요합니다")
    if step == "assign":
        a = merged["assign"] or {}
        miss = [k for k in ("channel", "preset") if not str(a.get(k) or "").strip()]
        if miss:
            raise TopicError(f"assign 단계: data.assign.{miss} 가 없습니다")
    if step == "source" and not merged["rights"]:
        raise TopicError("source 단계: data.rights(재료별 출처 종류)가 비었습니다")
    key = STEP_OUTPUT.get(step)
    if key:
        name = outputs.get(key)
        if not name:
            raise TopicError(f"{step} 단계: 산출물 '{key}' 가 없습니다(outputs.{key})")
        if not has(name):
            raise TopicError(f"{step} 단계: 산출물 파일이 폴더에 없습니다: {key}={name}")
    for k, name in outputs.items():
        if not has(name):
            raise TopicError(f"산출물 파일이 폴더에 없습니다: {k}={name} (files 로 보내거나 upload 먼저)")


def advance(tid, worker, data=None, outputs=None, files=None, cost=None, note="", data_dir=None) -> dict:
    """잡은 일을 끝냈다 → 다음 상태. 필수 자료·산출물·비용을 검사하고 잠금을 푼다."""
    worker = _need_worker(worker)
    data = _check_data(data)
    if outputs is not None and not isinstance(outputs, dict):
        raise TopicError("outputs 는 객체여야 합니다")
    outputs = {str(k): safe_name(v) for k, v in (outputs or {}).items()}
    if files is not None and not isinstance(files, dict):
        raise TopicError("files 는 {이름: 글} 객체여야 합니다")
    files = files or {}
    for k, v in files.items():
        safe_name(k)
        if not isinstance(v, str):
            raise TopicError(f"files.{k} 는 글(문자열)이어야 합니다 — 큰 파일은 upload")
    cost = cost or {}
    if not isinstance(cost, dict):
        raise TopicError("cost 는 객체여야 합니다")
    for k, v in cost.items():
        if k not in COST_KINDS:
            raise TopicError(f"모르는 비용 종류: {k} — {list(COST_KINDS)} 만")
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            raise TopicError(f"비용은 0 이상 정수: {k}={v!r}")
    now = _now()
    d = topic_dir(tid, data_dir)
    with _tx(data_dir) as c:
        _expire(c, now)
        r = _held(c, tid, worker, now)
        state = r["state"]
        if state not in FLOW or FLOW[state][0] != r["lock_step"]:
            raise TopicError(f"잠근 일({r['lock_step']})과 상태({state})가 맞지 않습니다", 409)
        step, new_state = FLOW[state]
        merged = {k: json.loads(r[k] or "{}") for k in DATA_KEYS}
        merged.update(data)
        all_out = json.loads(r["outputs"] or "{}")
        all_out.update(outputs)
        _check_required(step, merged, all_out, d, files)
        for name, text in files.items():           # 검사를 다 통과한 뒤에만 쓴다
            _write_file(d, name, text.encode("utf-8"))
        c.execute("UPDATE topics SET state=?,source=?,bench=?,score=?,assign=?,rights=?,outputs=?,"
                  "cost_gemini=cost_gemini+?,cost_typecast=cost_typecast+?,cost_seconds=cost_seconds+?,"
                  "lock_owner=NULL,lock_step=NULL,lock_at=NULL,heartbeat_at=NULL,doing=NULL,last_error=NULL,"
                  "error_count=0,retry_at=NULL,updated_at=? WHERE id=?",
                  (new_state, *[json.dumps(merged[k], ensure_ascii=False) for k in DATA_KEYS],
                   json.dumps(all_out, ensure_ascii=False), cost.get("gemini", 0), cost.get("typecast", 0),
                   cost.get("seconds", 0), _iso(now), int(tid)))
        _touch_worker(c, worker, now, topic_id=None, step=None, doing=None, last_error=None)
        day = now.strftime("%Y-%m-%d")
        for k, n in cost.items():
            if n:
                c.execute("INSERT INTO cost(topic_id,day,kind,n,step,at) VALUES(?,?,?,?,?,?)",
                          (int(tid), day, k, n, step, _iso(now)))
        _event(c, tid, now, worker, "advance", state, new_state, step, note)
        return _topic(_get(c, tid), now)


def release(tid, worker, error, retry_after_min=None, count=True, data_dir=None) -> dict:
    """워커가 손을 뗀다(실패 보고). 이유 없이는 못 뗀다 — 조용한 실패 금지.
    retry_after_min(기본 30) 동안 claim_next 가 이 행을 다시 안 준다. 실패 STALL_AT 회면 stalled.
    count=False = 한도 대기(워커 장부 LimitHit·429) — 실패 횟수를 안 올린다(소재가 한도 때문에 멈춤으로 가지 않게, 10-16 실측)."""
    worker = _need_worker(worker)
    if not isinstance(error, str) or not error.strip():
        raise TopicError("release 에는 error(왜 못 했나)가 필요합니다")
    if retry_after_min is None:
        retry_after_min = RETRY_AFTER_MIN
    if isinstance(retry_after_min, bool) or not isinstance(retry_after_min, (int, float)) or retry_after_min < 0:
        raise TopicError(f"retry_after_min 은 0 이상 숫자(분): {retry_after_min!r}")
    now = _now()
    with _tx(data_dir) as c:
        _expire(c, now)
        r = _held(c, tid, worker, now)
        msg = f"{worker} {r['lock_step']}: {error.strip()}"[:500]
        _fail(c, r, now, worker, "release", msg, retry_after_min, count=count is not False)
        _touch_worker(c, worker, now, topic_id=None, step=None, doing=None, last_error=msg)
        return _topic(_get(c, tid), now)


def unstall(tid, by="admin", note="", data_dir=None) -> dict:
    """사람이 멈춘(stalled) 소재를 푼다 — 실패 횟수·대기를 0 으로, last_error 는 이력에 남기고 지운다."""
    now = _now()
    with _tx(data_dir) as c:
        r = _get(c, tid)
        if not r["stalled"] and not r["retry_at"] and not r["error_count"]:
            raise TopicError("멈춘 소재가 아닙니다(실패 기록 없음)", 409)
        c.execute("UPDATE topics SET stalled=0,error_count=0,retry_at=NULL,last_error=NULL,updated_at=? WHERE id=?",
                  (_iso(now), int(tid)))
        _event(c, tid, now, by, "unstall", r["state"], r["state"], None,
               f"{note or '풀기'} (지난 실패 {r['error_count']}회: {r['last_error']})")
        return _topic(_get(c, tid), now)


def worker_heartbeat(worker, category=None, track=None, channel=None, doing=None, idle_reason=None,
                     last_error=None, data_dir=None) -> dict:
    """워커 맥박(잡은 소재와 무관) — 쉬는 워커·find 실패도 보드에 보이게. 끊김 판정은 board 가 한다."""
    worker = _need_worker(worker)
    for k, v in (("category", category), ("track", track), ("channel", channel), ("doing", doing),
                 ("idle_reason", idle_reason), ("last_error", last_error)):
        if v is not None and not isinstance(v, str):
            raise TopicError(f"{k} 는 문자열이어야 합니다")
    now = _now()
    with _tx(data_dir) as c:
        _touch_worker(c, worker, now, category=category, track=track, channel=channel,
                      doing=(doing or "")[:200] or None, idle_reason=(idle_reason or "")[:500] or None,
                      last_error=(last_error or "")[:500] or None)
    return {"worker": worker, "seen_at": _iso(now)}


def _check_back(back_to):
    if back_to is not None and back_to not in BACK_TO_OK:
        raise TopicError(f"되돌아갈 상태는 {list(BACK_TO_OK)} 중 하나(또는 null=폐기): {back_to!r}")


def reject(tid, reason, back_to=None, by="admin", data_dir=None) -> dict:
    """관리자 반려(검수 자리 밖에서도). back_to 없으면 폐기."""
    if not isinstance(reason, str) or not reason.strip():
        raise TopicError("반려 사유(reason)가 필요합니다")
    _check_back(back_to)
    now = _now()
    with _tx(data_dir) as c:
        r = _get(c, tid)
        if r["state"] == "passed":
            raise TopicError("이미 통과(passed)한 소재입니다", 409)
        note = reason.strip() + (f" (잠금 {r['lock_owner']} {r['lock_step']} 풀림)" if r["lock_owner"] else "")
        c.execute("UPDATE topics SET state='rejected',back_to=?,lock_owner=NULL,lock_step=NULL,lock_at=NULL,"
                  "heartbeat_at=NULL,doing=NULL,stalled=0,error_count=0,retry_at=NULL,last_error=?,updated_at=? "
                  "WHERE id=?",
                  (back_to, f"반려: {reason.strip()}"[:500], _iso(now), int(tid)))
        _event(c, tid, now, by, "reject", r["state"], "rejected", None, f"{note} → {back_to or '폐기'}")
        return _topic(_get(c, tid), now)


def review(tid, stage, verdict, by="admin", reason="", back_to=None, data_dir=None) -> dict:
    """사람 검수. 지금 상태가 그 검수 자리여야 한다."""
    if stage not in HUMAN:
        raise TopicError(f"검수 단계는 {list(HUMAN)} 중 하나: {stage!r}")
    if verdict not in ("pass", "reject"):
        raise TopicError(f"verdict 는 pass|reject: {verdict!r}")
    if verdict == "reject" and not (isinstance(reason, str) and reason.strip()):
        raise TopicError("반려에는 사유(reason)가 필요합니다")
    _check_back(back_to)
    now = _now()
    with _tx(data_dir) as c:
        r = _get(c, tid)
        if r["state"] != stage:
            raise TopicError(f"지금 상태는 {r['state']} — {stage} 검수 자리가 아닙니다", 409)
        c.execute("INSERT INTO reviews(topic_id,stage,verdict,reason,back_to,by,at) VALUES(?,?,?,?,?,?,?)",
                  (int(tid), stage, verdict, reason or "", back_to if verdict == "reject" else None,
                   by or "admin", _iso(now)))
        if verdict == "pass":
            to = HUMAN[stage]
            c.execute("UPDATE topics SET state=?,last_error=NULL,updated_at=?,passed_at=? WHERE id=?",
                      (to, _iso(now), _iso(now) if to == "passed" else r["passed_at"], int(tid)))
        else:
            to = "rejected"
            c.execute("UPDATE topics SET state='rejected',back_to=?,last_error=?,updated_at=? WHERE id=?",
                      (back_to, f"{stage} 반려: {reason.strip()}"[:500], _iso(now), int(tid)))
        _event(c, tid, now, by, "review", stage, to, None,
               f"{verdict}" + (f": {reason} → {back_to or '폐기'}" if verdict == "reject" else ""))
        return _topic(_get(c, tid), now)


# ── 보기 ──────────────────────────────────────────────────────────────────
def _files(tid, data_dir=None):
    d = topic_dir(tid, data_dir)
    if not d.is_dir():
        return []
    return [{"name": p.name, "size": p.stat().st_size,
             "url": f"/api/admin/calcopy/topics/{int(tid)}/file/{p.name}"}
            for p in sorted(d.iterdir()) if p.is_file() and not p.name.endswith(".part")]


def detail(tid, data_dir=None) -> dict:
    now = _now()
    with _tx(data_dir) as c:
        _expire(c, now)
        t = _topic(_get(c, tid), now)
        hist = [{"at": e["at"], "by": e["by"], "kind": e["kind"], "from": e["from_state"], "to": e["to_state"],
                 "step": e["step"], "note": e["note"]}
                for e in c.execute("SELECT * FROM events WHERE topic_id=? ORDER BY id", (int(tid),))]
        revs = [dict(stage=v["stage"], verdict=v["verdict"], reason=v["reason"], back_to=v["back_to"],
                     by=v["by"], at=v["at"])
                for v in c.execute("SELECT * FROM reviews WHERE topic_id=? ORDER BY id", (int(tid),))]
        clog = [dict(day=x["day"], kind=x["kind"], n=x["n"], step=x["step"], at=x["at"])
                for x in c.execute("SELECT * FROM cost WHERE topic_id=? ORDER BY id", (int(tid),))]
    return {"topic": t, "files": _files(tid, data_dir), "history": hist, "reviews": revs, "cost_log": clog}


def file_path(tid, name, data_dir=None) -> Path:
    p = topic_dir(tid, data_dir) / safe_name(name)
    if not p.is_file():
        raise TopicError(f"산출물 없음: #{tid} {name}", 404)
    return p


def save_upload(tid, name, data: bytes, data_dir=None) -> dict:
    name = safe_name(name)
    if not data:
        raise TopicError("빈 파일입니다")
    with _tx(data_dir) as c:
        _get(c, tid)
    _write_file(topic_dir(tid, data_dir), name, data)
    return {"name": name, "size": len(data)}


def _rate(p, j):
    return round(p / (p + j), 3) if (p + j) else None


def _minutes(secs):
    secs = [s for s in secs if s]
    return {"n": len(secs), "avg": round(sum(secs) / len(secs) / 60, 1) if secs else None,
            "median": round(statistics.median(secs) / 60, 1) if secs else None}


def _kpi(c, now, rows):
    day = now.strftime("%Y-%m-%d")
    days = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6, -1, -1)]
    created = [r["created_at"][:10] for r in rows]
    rv = {}
    for st in HUMAN:
        p = c.execute("SELECT COUNT(*) FROM reviews WHERE stage=? AND verdict='pass'", (st,)).fetchone()[0]
        j = c.execute("SELECT COUNT(*) FROM reviews WHERE stage=? AND verdict='reject'", (st,)).fetchone()[0]
        rv[st] = {"pass": p, "reject": j, "rate": _rate(p, j)}
    passed = [r for r in rows if r["state"] == "passed" and r["passed_at"]]
    hrs = [(_parse(r["passed_at"]) - _parse(r["created_at"])).total_seconds() / 3600 for r in passed]
    return {
        "day": day,
        "candidates_today": created.count(day),
        "candidates_7d": [{"day": d_, "n": created.count(d_)} for d_ in days],
        "plan_review": rv["plan_review"], "final_review": rv["final_review"],
        "hours_per_passed": {"n": len(hrs), "avg": round(sum(hrs) / len(hrs), 1) if hrs else None,
                             "median": round(statistics.median(hrs), 1) if hrs else None},
        "cost_per_passed": {k: (round(sum(r[f"cost_{k}"] for r in passed) / len(passed), 1) if passed else None)
                            for k in COST_KINDS},
        # 실측 작업 시간(advance 의 cost.seconds 합, 분) — 추가→통과 벽시계(hours_per_passed)와 따로
        "work_min_per_passed": _minutes([r["cost_seconds"] for r in passed]),
    }


def board(state=None, category=None, limit=300, data_dir=None) -> dict:
    """보드 한 장: 상태×카테고리 · 결정할 것 · 워커별 현재 일 · 오류 · 비용 상한 · KPI · 소재 목록."""
    now = _now()
    with _tx(data_dir) as c:
        _expire(c, now)
        rows = c.execute("SELECT * FROM topics ORDER BY id DESC").fetchall()
        cs = _caps_state(c, now)
        kpi = _kpi(c, now, rows)
        wrows = c.execute("SELECT * FROM workers ORDER BY worker").fetchall()
    grid, totals = {}, {}
    for r in rows:
        grid.setdefault(r["category"], {}).setdefault(r["state"], 0)
        grid[r["category"]][r["state"]] += 1
        totals[r["state"]] = totals.get(r["state"], 0) + 1
    topics = [_topic(r, now) for r in rows]
    decide = [{"id": t["id"], "name": t["name"], "state": t["state"], "since": t["updated_at"],
               "files": [f["name"] for f in _files(t["id"], data_dir)]}
              for t in topics if t["state"] in HUMAN]
    wrow = {w["worker"]: dict(w) for w in wrows}
    workers = []
    for t in topics:                                          # 잡은 일이 있는 워커(소재마다 한 줄)
        if t["lock"]["owner"]:
            w = wrow.get(t["lock"]["owner"], {})
            workers.append({"worker": t["lock"]["owner"], "status": "stale" if t["lock"]["stale"] else "working",
                            "topic_id": t["id"], "name": t["name"], "step": t["lock"]["step"],
                            "heartbeat_at": t["lock"]["heartbeat_at"], "age_sec": t["lock"]["age_sec"],
                            "stale": t["lock"]["stale"], "doing": t["lock"]["doing"],
                            "category": w.get("category"), "track": w.get("track"), "channel": w.get("channel"),
                            "idle_reason": None, "last_error": w.get("last_error")})
    holding = {w["worker"] for w in workers}
    for name, w in wrow.items():                              # 쉬는 워커(잡은 것 없음) — find 실패·대기 이유
        seen = _parse(w["seen_at"])
        age = int((now - seen).total_seconds()) if seen else None
        if name in holding or age is None or age > WORKER_SHOW_SEC:
            continue
        workers.append({"worker": name, "status": "stale" if age > STALE_SEC else "idle", "topic_id": None,
                        "name": None, "step": None, "heartbeat_at": w["seen_at"], "age_sec": age,
                        "stale": age > STALE_SEC, "doing": w["doing"], "category": w["category"],
                        "track": w["track"], "channel": w["channel"], "idle_reason": w["idle_reason"],
                        "last_error": w["last_error"]})
    stalled = [{"id": t["id"], "name": t["name"], "state": t["state"], "error_count": t["error_count"],
                "error": t["last_error"]} for t in topics if t["stalled"]]
    errors = [{"id": t["id"], "name": t["name"], "state": t["state"], "error": t["last_error"]}
              for t in topics if t["last_error"]]
    shown = [t for t in topics if (not state or t["state"] == state) and (not category or t["category"] == category)]
    return {"now": _iso(now), "states": list(STATES), "grid": grid, "totals": totals, "decide": decide,
            "workers": workers, "stalled": stalled, "errors": errors, "caps": cs, "kpi": kpi, "topics": shown[:int(limit)]}
