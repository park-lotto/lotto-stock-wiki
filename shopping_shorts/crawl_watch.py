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
        seconds REAL NOT NULL DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS crawl_channel_results(
        run_id INTEGER NOT NULL,
        job TEXT NOT NULL,
        ran_at TEXT NOT NULL,
        username TEXT NOT NULL,
        verdict TEXT NOT NULL,
        url TEXT NOT NULL DEFAULT '')""")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_cr_job_at ON crawl_runs(job, ran_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_ccr_user ON crawl_channel_results(job, username, ran_at DESC)")


def _conn(db_path):
    c = sqlite3.connect(db_path, timeout=10)
    c.row_factory = sqlite3.Row
    ensure_schema(c)
    return c


def record_run(db_path, job, *, tally=None, verdicts=(), items=0, seconds=0.0) -> int:
    """한 회차의 결과를 남긴다. 크롤이 끝날 때 딱 한 번 부른다.

    ⚠️ 이 함수가 실패해도 크롤은 죽으면 안 된다 — 호출부에서 try로 감싼다.
    """
    tally = dict(tally or {})
    verdicts = list(verdicts or [])
    failed = sum(1 for _u, v, *_ in verdicts if v != _OK)
    now = _utcnow()
    with _conn(db_path) as c:
        cur = c.execute(
            "INSERT INTO crawl_runs(job,ran_at,tally,items,total,failed,seconds)"
            " VALUES(?,?,?,?,?,?,?)",
            (job, now, json.dumps(tally, ensure_ascii=False), int(items),
             len(verdicts), failed, float(seconds)))
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
    return {"id": r["id"], "job": r["job"], "ran_at": r["ran_at"], "tally": tally,
            "items": r["items"], "total": r["total"], "failed": r["failed"],
            "seconds": r["seconds"]}


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


def verdict(db_path):
    """맨 위 한 줄 — 지금 크롤이 정상인가.

    ★'한 번도 안 돌았다'를 '정상'으로 읽으면 안 된다. 조용한 실패가 가장 위험하다.
    """
    bad, warn, unknown = [], [], []
    for job in JOBS:
        r = latest(db_path, job)
        if r is None:
            unknown.append(job)
            continue
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
