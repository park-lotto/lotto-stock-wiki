"""관측판 — 서버가 얼마나 버티는지 매일 숫자로 남긴다(2026-08-22).

## 왜

1기 100명을 받기 전에 용량을 계산했지만, 계산은 계산이다. **실제 동시 렌더가
몇 개까지 가는지, 디스크가 하루 몇 GB 늘는지, 송신이 6TB 한도에 얼마나 닿는지는
재봐야 안다.** 그 숫자가 없으면 "16코어로 올릴까"를 감으로 정하게 된다.

실측 근거(2026-08-22, 4코어 서버에서 20초 인코딩 동시 실행):

    동시 1개 →  16.2초
    동시 3개 →  55.7초  (3.4배)
    동시 6개 → 158.6초  (9.8배)   ← 코어를 서로 뺏는 손해가 이만큼 크다

즉 **동시 렌더 최대치**가 증설 판단의 핵심 지표다. 나머지(디스크·송신)는
돈이 새는 곳이라 같이 본다.

## 어떻게

5분마다 한 줄씩 표본을 남긴다(`capacity_samples`). 표본은 가볍다 —
지금 도는 렌더 수, 대기 수, 부하, 디스크, 네트워크 누적, 워커 수.
그걸 날짜별로 접어서 **하루의 최대치**를 본다. 평균은 위험을 숨긴다.

⚠️ 표본을 남기는 일이 서버를 무겁게 하면 안 된다 — 파일 하나 읽고 DB 한 줄 쓰는
   수준으로만 만든다(디스크 전체 스캔 같은 건 하지 않는다).
"""

from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import datetime, timezone


def _utcnow():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ensure_schema(conn):
    """표본 테이블. 이미 있으면 아무 일도 안 한다."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS capacity_samples (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            at           TEXT NOT NULL,      -- UTC
            running      INTEGER,            -- 지금 돌고 있는 작업 수(=동시 렌더)
            queued       INTEGER,            -- 줄 서 있는 작업 수
            workers      INTEGER,            -- 살아있는 워커 수(=동시 상한)
            load1        REAL,               -- 1분 부하
            cores        INTEGER,
            disk_used_gb REAL,
            disk_free_gb REAL,
            net_tx_gb    REAL,               -- 부팅 후 누적 송신(요금이 붙는 쪽)
            net_rx_gb    REAL
        )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_capacity_at ON capacity_samples(at)")


def _net_bytes():
    """부팅 후 누적 (수신, 송신) 바이트. lo·docker는 뺀다(진짜 밖으로 나간 것만)."""
    rx = tx = 0
    try:
        with open("/proc/net/dev", encoding="utf-8") as f:
            for line in f.readlines()[2:]:
                name, _, rest = line.partition(":")
                name = name.strip()
                if name in ("lo",) or name.startswith(("docker", "veth", "br-")):
                    continue
                cols = rest.split()
                rx += int(cols[0])
                tx += int(cols[8])
    except (OSError, ValueError, IndexError):
        pass
    return rx, tx


def sample(db_path):
    """표본 한 줄을 남기고 그 내용을 dict로 돌려준다."""
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        ensure_schema(conn)
        row = conn.execute(
            "SELECT "
            "  SUM(CASE WHEN state='running' THEN 1 ELSE 0 END), "
            "  SUM(CASE WHEN state='queued'  THEN 1 ELSE 0 END), "
            "  COUNT(DISTINCT CASE WHEN state='running' THEN owner END) "
            "FROM job_queue").fetchone()
        # ★워커 수를 systemd에 묻지 않는다 — 5분마다 systemctl을 부르고 싶지 않고
        #   권한도 필요하다. 알고 싶은 건 '상한'이 아니라 **실제 동시 처리량**이므로
        #   큐를 물고 있던 서로 다른 owner 수로 센다.
        running, queued, owners = (row[0] or 0), (row[1] or 0), (row[2] or 0)

        try:
            # ★윈도우에는 getloadavg 자체가 없다(AttributeError). 서버는 리눅스라
            #   실제로는 안 나지만, 개발 PC에서 테스트가 죽으면 아무도 안 돌린다.
            load1 = os.getloadavg()[0]
        except (OSError, AttributeError):
            load1 = None
        cores = os.cpu_count() or 0
        du = shutil.disk_usage("/")
        rx, tx = _net_bytes()
        gb = 1024 ** 3

        data = {
            "at": _utcnow(), "running": running, "queued": queued,
            "workers": owners,                     # 실제로 일하던 워커 수
            "load1": load1, "cores": cores,
            "disk_used_gb": round(du.used / gb, 2),
            "disk_free_gb": round(du.free / gb, 2),
            "net_tx_gb": round(tx / gb, 3), "net_rx_gb": round(rx / gb, 3),
        }
        conn.execute(
            "INSERT INTO capacity_samples (at,running,queued,workers,load1,cores,"
            " disk_used_gb,disk_free_gb,net_tx_gb,net_rx_gb) "
            "VALUES (:at,:running,:queued,:workers,:load1,:cores,"
            " :disk_used_gb,:disk_free_gb,:net_tx_gb,:net_rx_gb)", data)
        conn.commit()
        return data
    finally:
        conn.close()


def daily(db_path, days=14):
    """날짜별 요약 — **최대치**로 본다. 평균은 위험한 순간을 숨긴다.

    송신량은 누적값이라 그대로 쓰면 안 된다(재부팅되면 0으로 돌아간다).
    하루 안에서 (최댓값 − 최솟값)으로 **그날 늘어난 양**을 본다.
    """
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        ensure_schema(conn)
        rows = conn.execute(
            "SELECT substr(at,1,10) d, "
            "       MAX(running), MAX(queued), MAX(workers), MAX(load1), "
            "       MIN(disk_free_gb), MAX(disk_used_gb), "
            "       MAX(net_tx_gb) - MIN(net_tx_gb), COUNT(*) "
            "  FROM capacity_samples "
            " WHERE at >= date('now', ?) "
            " GROUP BY d ORDER BY d DESC", (f"-{int(days)} days",)).fetchall()
        return [{"date": r[0], "max_running": r[1], "max_queued": r[2],
                 "max_workers": r[3], "max_load1": r[4],
                 "min_disk_free_gb": r[5], "max_disk_used_gb": r[6],
                 "tx_gb": round(r[7] or 0, 2), "samples": r[8]} for r in rows]
    finally:
        conn.close()


def verdict(db_path, cores=None):
    """지금 서버를 늘려야 하나 — 숫자로 답한다. 화면 맨 위에 한 줄로 띄운다.

    판단 기준(2026-08-22 실측에서 나온 것)
      · 동시 렌더가 코어 수에 근접 → 서로 뺏기 시작(4코어에서 6개 = 9.8배 지연)
      · 줄이 계속 서 있다 → 상한이 부족하다
      · 디스크 여유 50GB 미만 → 정리로 못 버틴다, 스토리지가 필요하다
      · 월 송신이 6TB(=무료한도)의 80%를 넘본다 → 초과요금이 붙기 시작한다
    """
    d = daily(db_path, days=7)
    cores = cores or (os.cpu_count() or 4)
    if not d:
        return {"level": "unknown", "msg": "아직 표본이 없습니다 — 5분마다 쌓입니다."}
    max_run = max((x["max_running"] or 0) for x in d)
    max_q = max((x["max_queued"] or 0) for x in d)
    min_free = min((x["min_disk_free_gb"] or 9999) for x in d)
    tx_month = sum(x["tx_gb"] for x in d) / max(len(d), 1) * 30

    if min_free < 50:
        return {"level": "danger",
                "msg": f"디스크 여유 {min_free:.0f}GB — 곧 찹니다. 블록스토리지를 붙이세요."}
    if max_run >= cores:
        return {"level": "danger",
                "msg": f"동시 렌더가 {max_run}개까지 갔습니다(코어 {cores}개). "
                       f"서로 뺏어 다 같이 느려지는 구간입니다 — 코어를 늘리세요."}
    if tx_month > 6144 * 0.8:
        return {"level": "warn",
                "msg": f"월 송신 추정 {tx_month / 1024:.1f}TB — 무료 6TB에 근접. "
                       f"초과분은 GB당 $0.09입니다."}
    if max_q >= 3:
        return {"level": "warn",
                "msg": f"대기가 최대 {max_q}개까지 밀렸습니다 — 워커를 늘릴 여지가 있는지 보세요."}
    return {"level": "ok",
            "msg": f"여유 있습니다 (동시 렌더 최대 {max_run}/{cores}코어 · "
                   f"디스크 여유 {min_free:.0f}GB · 월 송신 추정 {tx_month / 1024:.1f}TB)"}


if __name__ == "__main__":      # 크론: */5 * * * * python -m shopping_shorts.capacity_watch
    from shopping_shorts.config import DB_PATH

    print(sample(DB_PATH))
