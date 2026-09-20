# -*- coding: utf-8 -*-
"""🕸 크롤링 관측판 — 매일 도는 크롤이 어떤 상태인지 한눈에 본다(2026-09-01 사장님).

## 왜 만들었나

채널별 결과(`instagram_playwright.LAST_VERDICTS`)와 집계(`LAST_TALLY`)는 이미
잘 만들어져 있다. 문제는 **메모리에만 있다가 프로세스가 끝나면 사라진다**는 것이다.
그래서 "어제 뭐가 죽었나"를 알려면 매번 서버에 SSH로 붙어 journalctl을 뒤져야 했다.

실측 근거(2026-08-31 핸드오프 '남은 잔업'):
    - [ ] 발굴 0건일 때 경고 알림(**오늘 실패를 화면으로는 알 수 없었다**)

그날 인스타 수집은 153채널이 **전부** 실패했는데, 화면에는 아무 표시도 없었다.

## 무엇을 남기나

회차마다 한 줄(`crawl_runs`) + 채널별 결과(`crawl_channel_results`).
표본이 아니라 **결과**라 하루 몇 줄뿐이다(capacity_watch의 5분 표본과 다르다).

## ★대역폭과의 관계 — 이 관측판의 진짜 목적

죽은 채널도 살아있는 채널과 **똑같이 프록시 대역폭을 먹는다**. 하루 3.34GB 중
얼마가 죽은 채널에 낭비되는지는 지금까지 잴 방법이 없었다. `dead_channels()`가
연속 실패 채널을 골라내면 그만큼을 크롤에서 뺄 수 있다.

⚠️ **한 번이라도 살아나면 죽은 채널이 아니다.** 인스타는 일시적으로 로그인벽을
   띄웠다가 푸는 일이 잦아서(실측), 1회 실패로 빼면 멀쩡한 채널을 잃는다.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

# 크롤 축 — 이름은 systemd 서비스명과 맞춘다(로그를 찾아갈 때 헷갈리지 않게).
JOBS = ("instagram_collect", "instagram_discover", "youtube_collect")

# 축마다 "몇 시(KST)에 돌아야 하는가" — systemd 타이머 실측값(2026-09-01).
#   발굴 07:00 / 유튜브 08:10(+5회 재시도) / 인스타 수집 09:00
# ★여기가 신선도 판정의 유일한 기준이다. 타이머를 바꾸면 이 표도 같이 바꿔라
#   (두 곳에 적히는 순간 어긋난다 — 0순위-B).
# (시, 분) — 화면 문구에 그대로 쓰이므로 실제 타이머와 정확히 같아야 한다.
# "예정 08:00"이라고 띄웠는데 실제가 08:10이면 사장님이 타이머를 잘못 찾는다.
DUE_KST = {"instagram_discover": (7, 0), "youtube_collect": (8, 10),
           "instagram_collect": (9, 0)}

# 예정 시각이 지나고 이만큼 더 기다려도 소식이 없으면 "안 돈 것"으로 본다.
# 수집이 37~62분 걸리므로(실측) 넉넉히 잡는다 — 도는 중에 빨강이 뜨면 거짓 경보다.
STALE_GRACE_H = 3

# 심박이 이만큼 끊기면 "돌다가 죽은 것". 채널 하나에 20~40초씩 걸리므로
# 20분이면 확실히 비정상이다(실측: 148채널 37~62분 = 채널당 평균 15~25초).
BEAT_DEAD_MIN = 20

_KST_OFFSET_H = 9

# ok가 아닌 판정 전부를 실패로 본다. classify_channel_result가 주는 값:
#   ok / login_wall / not_found / unknown / error
_OK = "ok"


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS crawl_runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job TEXT NOT NULL,
        ran_at TEXT NOT NULL,
        tally TEXT NOT NULL DEFAULT '{}',
        items INTEGER NOT NULL DEFAULT 0,
        total INTEGER NOT NULL DEFAULT 0,
        failed INTEGER NOT NULL DEFAULT 0,
        seconds REAL NOT NULL DEFAULT 0,
        state TEXT NOT NULL DEFAULT 'done',
        done INTEGER NOT NULL DEFAULT 0,
        beat_at TEXT NOT NULL DEFAULT '')""")
    # 옛 DB에 컬럼을 보탠다(이미 있으면 조용히 넘어간다). 마이그레이션 실패로
    # 관측판이 통째로 죽으면 안 되므로 컬럼 목록을 먼저 보고 없을 때만 더한다.
    have = {r[1] for r in conn.execute("PRAGMA table_info(crawl_runs)")}
    for col, ddl in (("state", "TEXT NOT NULL DEFAULT 'done'"),
                     ("done", "INTEGER NOT NULL DEFAULT 0"),
                     ("beat_at", "TEXT NOT NULL DEFAULT ''")):
        if col not in have:
            conn.execute(f"ALTER TABLE crawl_runs ADD COLUMN {col} {ddl}")
    conn.execute("""CREATE TABLE IF NOT EXISTS crawl_channel_results(
        run_id INTEGER NOT NULL,
        job TEXT NOT NULL,
        ran_at TEXT NOT NULL,
        username TEXT NOT NULL,
        verdict TEXT NOT NULL,
        url TEXT NOT NULL DEFAULT '')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS crawl_alert_state(
        k TEXT PRIMARY KEY, msg TEXT NOT NULL DEFAULT '')""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_cr_job_at ON crawl_runs(job, ran_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_ccr_user ON crawl_channel_results(job, username, ran_at DESC)")


def _conn(db_path):
    c = sqlite3.connect(db_path, timeout=10)
    c.row_factory = sqlite3.Row
    ensure_schema(c)
    return c


def record_run(db_path, job, *, tally=None, verdicts=(), items=0, seconds=0.0,
               ran_at=None) -> int:
    """한 회차의 결과를 남긴다. 크롤이 끝날 때 딱 한 번 부른다.

    ⚠️ 이 함수가 실패해도 크롤은 죽으면 안 된다 — 호출부에서 try로 감싼다.
    """
    tally = dict(tally or {})
    verdicts = list(verdicts or [])
    failed = sum(1 for _u, v, *_ in verdicts if v != _OK)
    now = ran_at or _utcnow()
    with _conn(db_path) as c:
        cur = c.execute(
            "INSERT INTO crawl_runs(job,ran_at,tally,items,total,failed,seconds,"
            "state,done,beat_at) VALUES(?,?,?,?,?,?,?,'done',?,?)",
            (job, now, json.dumps(tally, ensure_ascii=False), int(items),
             len(verdicts), failed, float(seconds), len(verdicts), now))
        run_id = cur.lastrowid
        if verdicts:
            c.executemany(
                "INSERT INTO crawl_channel_results(run_id,job,ran_at,username,verdict,url)"
                " VALUES(?,?,?,?,?,?)",
                [(run_id, job, now, str(u), str(v), str(url or ""))
                 for u, v, *rest in verdicts
                 for url in (rest[0] if rest else "",)])
    return run_id


def _row_to_run(r) -> dict:
    try:
        tally = json.loads(r["tally"])
    except Exception:       # noqa: BLE001 — 깨진 JSON이 화면을 죽이면 안 된다
        tally = {}
    keys = r.keys()
    return {"id": r["id"], "job": r["job"], "ran_at": r["ran_at"], "tally": tally,
            "items": r["items"], "total": r["total"], "failed": r["failed"],
            "seconds": r["seconds"],
            "state": (r["state"] if "state" in keys else "done") or "done",
            "done": (r["done"] if "done" in keys else 0) or 0,
            "beat_at": (r["beat_at"] if "beat_at" in keys else "") or ""}


def latest(db_path, job):
    """가장 최근 회차. 한 번도 안 돌았으면 None(=='모름', '정상' 아님)."""
    with _conn(db_path) as c:
        r = c.execute("SELECT * FROM crawl_runs WHERE job=? ORDER BY ran_at DESC, id DESC"
                      " LIMIT 1", (job,)).fetchone()
    return _row_to_run(r) if r else None


def history(db_path, job, days=14):
    with _conn(db_path) as c:
        rows = c.execute(
            "SELECT * FROM crawl_runs WHERE job=? ORDER BY ran_at DESC, id DESC LIMIT ?",
            (job, max(1, int(days)) * 8)).fetchall()
    return [_row_to_run(r) for r in rows]


def dead_channels(db_path, job, min_fails=2, look=6):
    """최근 `look`회차에서 **연속으로** 실패한 채널. 크롤에서 뺄 후보다.

    ★연속이 핵심이다 — 중간에 한 번이라도 ok면 0으로 리셋한다. 인스타는 로그인벽을
      띄웠다 푸는 일이 잦아 1회 실패로 빼면 멀쩡한 채널을 잃는다(실측).
    """
    with _conn(db_path) as c:
        # ★run_id로도 정렬한다 — ran_at은 초 단위라 같은 초에 두 회차가 들어오면
        #   순서가 뒤집혀 "최근이 성공인데 죽은 채널로" 잘못 잡힌다(실측: 테스트에서
        #   3회차가 같은 초에 기록돼 재현됨). run_id는 단조증가라 흔들리지 않는다.
        rows = c.execute(
            "SELECT username, verdict, ran_at, url FROM crawl_channel_results"
            " WHERE job=? ORDER BY username, ran_at DESC, run_id DESC", (job,)).fetchall()
    # ★rows는 (username, ran_at DESC) 정렬이다 — 각 채널의 **가장 최근 회차부터** 본다.
    #   그래서 "최근부터 연속 몇 번 실패했나"만 세면 되고, 성공을 만나는 순간 멈춘다.
    #   ⚠️ 옛날에 한 번 성공했다고 후보에서 빼면 안 된다(2026-09-01 자체 실측으로 잡은 버그):
    #     실패2→성공1→실패2 인 채널은 **지금 죽어 있는데도** 목록에서 사라졌다.
    #     판단 기준은 '과거에 산 적 있나'가 아니라 '지금 연속으로 죽어 있나'다.
    out, cur_user, streak, last, done = [], None, 0, None, False

    def _flush():
        if cur_user is not None and streak >= min_fails and last is not None:
            out.append({"username": cur_user, "fails": streak,
                        "verdict": last["verdict"], "url": last["url"],
                        "last_at": last["ran_at"]})

    for r in rows:
        u = r["username"]
        if u != cur_user:
            _flush()
            cur_user, streak, last, done = u, 0, None, False
        if done or streak >= look:
            continue
        if r["verdict"] == _OK:
            done = True             # 최근 연속 실패가 여기서 끊긴다
        else:
            streak += 1
            if last is None:
                last = r
    _flush()
    out.sort(key=lambda d: -d["fails"])
    return out


def verdict(db_path, now=None):
    """맨 위 한 줄 — 지금 크롤이 정상인가.

    ★세 가지를 본다. 셋째가 없으면 관측판이 거짓말을 한다(2026-09-01에 실제로 그랬다):
      ① 결과가 나빴나 (전부 실패·0건·절반 실패)
      ② 돌다가 죽었나 (심박이 끊김)
      ③ **아예 안 돌았나** (예정 시각이 지났는데 오늘 기록이 없음)

    ★③이 핵심이다. 어제 성공 기록만 보고 판정하면 **타이머가 통째로 죽어도
      화면은 영원히 초록**이다 — 관측판이 가장 필요한 순간에 침묵한다.
    """
    from datetime import timedelta
    nowdt = _parse(now) if now else _parse(_utcnow())
    if nowdt is None:
        nowdt = _parse(_utcnow())
    kst = nowdt + timedelta(hours=_KST_OFFSET_H)      # 예정 시각은 KST 기준

    bad, warn, unknown = [], [], []
    for job in JOBS:
        r = latest(db_path, job)

        # ② 도는 중 — 심박이 끊겼나
        if r and r.get("state") == "running":
            b = _parse(r.get("beat_at") or r.get("ran_at"))
            if b and (nowdt - b) > timedelta(minutes=BEAT_DEAD_MIN):
                mins = int((nowdt - b).total_seconds() // 60)
                bad.append(f"{job}: 돌다가 멈춘 것 같습니다(심박 {mins}분째 없음)")
            continue                                   # 정상 진행 중이면 판정 보류

        # ③ 예정 시각이 지났는데 오늘 기록이 없나
        due = DUE_KST.get(job)
        due_h, due_m = due if due else (None, 0)
        if due_h is not None and kst.hour >= (due_h + STALE_GRACE_H):
            last = _parse(r["ran_at"]) if r else None
            last_kst = (last + timedelta(hours=_KST_OFFSET_H)) if last else None
            if last_kst is None or last_kst.date() < kst.date():
                since = (f"{int((nowdt - last).total_seconds() // 3600)}시간째"
                         if last else "한 번도")
                bad.append(f"{job}: {since} 소식이 없습니다"
                           f"(예정 {due_h:02d}:{due_m:02d})")
                continue

        if r is None:
            unknown.append(job)
            continue
        # ① 결과가 나빴나
        if r["total"] and r["failed"] >= r["total"]:
            bad.append(f"{job}: {r['total']}채널 전부 실패")
        elif r["total"] and r["items"] == 0:
            bad.append(f"{job}: 0건 수집")
        elif r["total"] and r["failed"] * 2 >= r["total"]:
            warn.append(f"{job}: 절반 이상 실패({r['failed']}/{r['total']})")

    if bad:
        return {"level": "danger", "msg": " · ".join(bad), "unknown": unknown}
    if warn:
        return {"level": "warn", "msg": " · ".join(warn), "unknown": unknown}
    if unknown:
        return {"level": "unknown",
                "msg": "아직 기록이 없습니다: " + ", ".join(unknown)
                       + " — 다음 회차부터 쌓입니다", "unknown": unknown}
    return {"level": "ok", "msg": "최근 회차 모두 정상", "unknown": []}


# ══════════════════════════════════════════════════════════════════════
# 심박 — 도는 중에도 화면이 움직이게 한다
# ★왜: 끝나야만 기록이 남으면 "지금 돌고 있는지"를 알 수 없고, 돌다가 죽으면
#   아무 흔적도 없이 사라진다(2026-09-01 사장님 "살아있는것처럼 계속움직이는").
# ══════════════════════════════════════════════════════════════════════

def start_run(db_path, job, total=0) -> int:
    """회차 시작을 남긴다. 크롤이 **시작할 때** 부른다."""
    now = _utcnow()
    with _conn(db_path) as c:
        cur = c.execute(
            "INSERT INTO crawl_runs(job,ran_at,tally,items,total,failed,seconds,"
            "state,done,beat_at) VALUES(?,?,'{}',0,?,0,0,'running',0,?)",
            (job, now, int(total), now))
        return cur.lastrowid


def beat(db_path, run_id, done=0, items=0, at=None):
    """진행 심박 — 채널 몇 개까지 갔는지. 크롤 루프에서 주기적으로 부른다."""
    with _conn(db_path) as c:
        c.execute("UPDATE crawl_runs SET done=?, items=?, beat_at=? WHERE id=?",
                  (int(done), int(items), at or _utcnow(), int(run_id)))


def finish_run(db_path, run_id, *, tally=None, verdicts=(), items=0, seconds=0.0):
    """회차 종료 — start_run으로 연 줄을 닫는다."""
    tally = dict(tally or {})
    verdicts = list(verdicts or [])
    failed = sum(1 for _u, v, *_ in verdicts if v != _OK)
    now = _utcnow()
    with _conn(db_path) as c:
        c.execute("UPDATE crawl_runs SET tally=?, items=?, total=?, failed=?, seconds=?,"
                  " state='done', done=?, beat_at=? WHERE id=?",
                  (json.dumps(tally, ensure_ascii=False), int(items), len(verdicts),
                   failed, float(seconds), len(verdicts), now, int(run_id)))
        if verdicts:
            row = c.execute("SELECT job, ran_at FROM crawl_runs WHERE id=?",
                            (int(run_id),)).fetchone()
            c.executemany(
                "INSERT INTO crawl_channel_results(run_id,job,ran_at,username,verdict,url)"
                " VALUES(?,?,?,?,?,?)",
                [(int(run_id), row["job"], row["ran_at"], str(u), str(v), str(url or ""))
                 for u, v, *rest in verdicts
                 for url in (rest[0] if rest else "",)])


def _parse(ts):
    from datetime import datetime
    try:
        return datetime.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:      # noqa: BLE001
        return None


def _send_alert(kind, title, detail):
    """실제 발송 — 테스트가 monkeypatch로 갈아끼운다(라이브 쪽지 오염 방지)."""
    try:
        from shopping_shorts import ops_alert
        return ops_alert.raise_alert(kind, title, detail, cooldown_sec=6 * 3600)
    except Exception:      # noqa: BLE001 — 알림이 관측을 죽이면 안 된다
        return False


def check_and_alert(db_path, now=None):
    """판정이 빨강이면 관리자에게 밀어준다(텔레그램·쪽지).

    ★화면을 열어봐야 아는 관측판은 죽은 관측판이다. 같은 사고로 도배하지 않도록
      쿨다운은 ops_alert가 kind 단위로 처리한다.
    """
    v = verdict(db_path, now=now)
    if v["level"] != "danger":
        # 나아졌으면 표시를 지운다 — 안 지우면 다음에 같은 사고가 나도 조용하다.
        with _conn(db_path) as c:
            c.execute("DELETE FROM crawl_alert_state WHERE k='last'")
        return False
    # ★같은 사고로 도배하지 않는다. ops_alert에도 쿨다운이 있지만 거기 기대면
    #   호출부가 바뀔 때 조용히 도배가 된다 — 판단을 여기서 한 번 더 못박는다.
    #   메시지가 **달라지면** 새 사고이므로 다시 알린다.
    with _conn(db_path) as c:
        c.execute("""CREATE TABLE IF NOT EXISTS crawl_alert_state(
            k TEXT PRIMARY KEY, msg TEXT NOT NULL DEFAULT '')""")
        row = c.execute("SELECT msg FROM crawl_alert_state WHERE k='last'").fetchone()
        if row and row["msg"] == v["msg"]:
            return False
        c.execute("INSERT INTO crawl_alert_state(k,msg) VALUES('last',?)"
                  " ON CONFLICT(k) DO UPDATE SET msg=excluded.msg", (v["msg"],))
    return bool(_send_alert("crawl_watch", "🕸 크롤이 멈췄습니다 — " + v["msg"][:60],
                            v["msg"]))
