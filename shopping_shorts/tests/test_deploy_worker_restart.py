# -*- coding: utf-8 -*-
"""auto_deploy 워커 재시작 조건 (2026-08-06).

실사고: 후보 병렬 코드가 01:12에 배포됐는데 워커 3개는 01:08 코드로 계속 돌았다.
배포 로그에 `worker 재시작 연기(작업 진행 중, 360초 경과)`가 3분마다 반복됐다.

원인 둘:
  ① _worker_busy가 **모든** running을 셌다. 좀비 가드(heartbeat 2분)는 '죽은 job'만
     거른다 — 살아있는 배경작업(prewarm·durfill)이 끊임없이 이어지면 busy가 영원히
     참이라 재시작이 무한 연기된다. 라이브 실측: prewarm 1건 때문에 배포가 막혀 있었다.
  ② 워커가 템플릿 인스턴스(worker@1/2/3)로 바뀌었는데 스크립트는 구 이름
     `shopping-shorts-worker`를 재시작하려 했다 — 유닛이 없어져 실패할 운명이었다.
"""
import re
import sqlite3
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "auto_deploy.sh"


def _busy_sql():
    """스크립트에 박힌 _worker_busy 쿼리를 그대로 꺼내 실행 가능한 SQL로 만든다.

    ★소스에서 직접 뽑는 이유: 쿼리를 테스트에 베껴 쓰면 스크립트만 고쳤을 때
      테스트가 옛 쿼리를 통과시켜 **가짜 green**이 된다."""
    src = SCRIPT.read_text(encoding="utf-8")
    body = src.split("_worker_busy()", 1)[1].split("<<'PY'", 1)[1].split("\nPY", 1)[0]
    # con.execute( ... ) 안의 따옴표 문자열만 이어붙인다. 주석줄(#)은 버린다.
    lines = [ln for ln in body.splitlines() if not ln.strip().startswith("#")]
    parts = re.findall(r'"([^"]*)"', "\n".join(lines))
    sql = "".join(p for p in parts if p.strip().upper().startswith(
        ("SELECT", "WHERE", "AND", "OR")) or "job_queue" in p)
    assert "SELECT" in sql, f"쿼리 추출 실패: {sql!r}"
    return sql


_seq = [0]


def _db(tmp_path, rows):
    _seq[0] += 1
    p = tmp_path / f"q{_seq[0]}.db"      # 호출마다 새 파일 — 같은 테스트가 여러 번 부른다
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE job_queue(id INTEGER PRIMARY KEY, task TEXT, "
              "state TEXT, heartbeat_at TEXT)")
    for task, state in rows:
        c.execute("INSERT INTO job_queue(task,state,heartbeat_at) "
                  "VALUES(?,?,datetime('now'))", (task, state))
    c.commit()
    return c


def test_배경작업만_돌면_재시작을_안_미룬다(tmp_path):
    """★이게 실사고 그 자체 — prewarm 하나 때문에 배포가 영원히 막혔다."""
    c = _db(tmp_path, [("prewarm", "running"), ("durfill", "running")])
    assert c.execute(_busy_sql()).fetchone()[0] == 0, "배경작업은 배포를 막으면 안 된다"


def test_고객작업이_돌면_미룬다(tmp_path):
    """재시작하면 사장님이 만들던 영상이 죽는다 — 이건 반드시 기다려야 한다."""
    for task in ("mix", "render", "retype", "preview", "clean"):
        c = _db(tmp_path, [(task, "running")])
        assert c.execute(_busy_sql()).fetchone()[0] >= 1, f"{task}는 미뤄야 한다"


def test_고객작업과_배경작업이_섞이면_미룬다(tmp_path):
    c = _db(tmp_path, [("prewarm", "running"), ("mix", "running")])
    assert c.execute(_busy_sql()).fetchone()[0] == 1


def test_좀비_가드는_그대로(tmp_path):
    """heartbeat가 2분 넘게 안 뛴 죽은 작업은 배포를 막으면 안 된다(기존 보호 유지)."""
    p = tmp_path / "z.db"
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE job_queue(id INTEGER PRIMARY KEY, task TEXT, "
              "state TEXT, heartbeat_at TEXT)")
    c.execute("INSERT INTO job_queue(task,state,heartbeat_at) "
              "VALUES('mix','running',datetime('now','-10 minutes'))")
    c.commit()
    assert c.execute(_busy_sql()).fetchone()[0] == 0, "죽은 job이 배포를 막으면 안 된다"


def test_유닛_이름을_코드에_박지_않는다():
    """워커가 worker@1/2/3로 바뀌었다. 구 이름을 그대로 restart하면 유닛이 없어 실패한다."""
    src = SCRIPT.read_text(encoding="utf-8")
    assert "list-units" in src and "shopping-shorts-worker*" in src, \
        "살아있는 워커 유닛을 systemd에 물어봐야 한다"
    assert "restart $WORKER_UNITS" in src, "탐색한 유닛들을 재시작해야 한다"


def test_재시작_실패시_PENDING을_안_지운다():
    """실패했는데 지우면 다음 크론이 재시도하지 않아 조용히 옛 코드로 남는다."""
    src = SCRIPT.read_text(encoding="utf-8")
    tail = src.split("_pending_has shopping-shorts-worker", 1)[1]
    assert "worker 재시작 실패" in tail, "실패를 로그로 남겨야 한다"
    ok_branch = tail.split("if sudo systemctl restart", 1)[1].split("else", 1)[0]
    assert "_pending_del shopping-shorts-worker" in ok_branch, \
        "성공했을 때만 PENDING을 지워야 한다"
