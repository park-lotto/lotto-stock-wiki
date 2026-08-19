"""종목별 일별 수급을 매일 쌓는다.

## 왜 필요한가 (2026-08-15 실측)

종목 단위 수급은 **지금 어디에도 안 남는다**. `/api/stock_supply_batch`는 메모리 10분
캐시뿐이고, `output/flow_history.json`은 시장 레벨·당일 장중만이다. KIS가 한 번에 주는
건 **30거래일**뿐이라, 오늘 안 쌓으면 1년 뒤에도 볼 수 있는 건 30일치다.

차트는 600일인데 수급은 30일 — 이 간극을 메우는 유일한 방법이 매일 적재다.

## 설계

- **매번 30일치를 통째로 덮어쓴다.** 낭비 같지만 결손이 자동 복구된다 —
  하루 걸러도, 서버가 죽었다 살아나도, 다음 실행이 최근 30일을 다시 채운다.
  "어제 것만 가져오기"로 만들면 하루 빠지는 순간 그 구멍은 영영 안 메워진다.
- 조회는 `stock_flow.fetch_investor_daily()` 하나만 쓴다. 화면이 쓰는 함수와 같은 것이라
  두 경로가 어긋날 수 없다(0순위-B).
- DB는 `data/flow.db` — `data/`는 gitignore라 저장소가 무거워지지 않는다.

사용법:
    python scripts/flow_daily.py              # watchlist 전 종목
    python scripts/flow_daily.py 005930 005380  # 지정 종목만
    python scripts/flow_daily.py --limit 20   # 앞 20종목만(시험용)
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import stock_flow

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE, "data", "flow.db")
WATCHLIST = os.path.join(BASE, "watchlist.json")

# KIS 유량 제한을 피하려는 간격. 398종목 × 0.35초 ≈ 2분 20초.
SLEEP = 0.35

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stock_flow_daily (
    code   TEXT NOT NULL,
    date   TEXT NOT NULL,          -- YYYYMMDD (KIS 원본 표기 그대로)
    frgn   INTEGER,                -- 외국인 순매수 (백만원, KIS 원단위)
    orgn   INTEGER,                -- 기관
    prsn   INTEGER,                -- 개인
    close  INTEGER,                -- 종가
    PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_flow_date ON stock_flow_daily(date);
"""


def connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.executescript(_SCHEMA)
    return conn


def watchlist_codes() -> list[str]:
    """watchlist.json 안 어디에 있든 code를 가진 항목을 전부 긁는다."""
    if not os.path.exists(WATCHLIST):
        return []
    out: list[str] = []

    def walk(o):
        if isinstance(o, dict):
            if o.get("code"):
                out.append(str(o["code"]).zfill(6))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    with open(WATCHLIST, encoding="utf-8") as f:
        walk(json.load(f))
    return sorted(set(out))


def _num(v) -> int:
    try:
        return int(float(v or 0))
    except (TypeError, ValueError):
        return 0


def save_one(conn: sqlite3.Connection, code: str) -> int:
    """한 종목의 최근 30거래일을 적재. 저장한 행 수 반환."""
    rows = stock_flow.fetch_investor_daily(code)
    recs = []
    for o in rows:
        d = (o.get("stck_bsop_date") or "").strip()
        if len(d) != 8 or not d.isdigit():
            continue  # 날짜가 깨진 행은 버린다 — 마커·집계가 통째로 틀어진다
        recs.append((
            code, d,
            _num(o.get("frgn_ntby_tr_pbmn")),
            _num(o.get("orgn_ntby_tr_pbmn")),
            _num(o.get("prsn_ntby_tr_pbmn")),
            _num(o.get("stck_clpr")),
        ))
    if recs:
        conn.executemany(
            "INSERT OR REPLACE INTO stock_flow_daily(code,date,frgn,orgn,prsn,close)"
            " VALUES (?,?,?,?,?,?)", recs)
        conn.commit()
    return len(recs)


def main(argv: list[str]) -> int:
    limit = 0
    codes = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--limit" and i + 1 < len(argv):
            limit = int(argv[i + 1]); i += 2; continue
        if not a.startswith("-"):
            codes.append(a.zfill(6))
        i += 1

    if not codes:
        codes = watchlist_codes()
    if limit:
        codes = codes[:limit]
    if not codes:
        print("대상 종목이 없습니다 (watchlist.json 확인)")
        return 1

    conn = connect()
    ok = fail = saved = 0
    t0 = time.time()
    for n, code in enumerate(codes, 1):
        try:
            saved += save_one(conn, code)
            ok += 1
        except Exception as e:
            fail += 1
            print(f"  실패 {code}: {type(e).__name__}: {e}", flush=True)
        if n % 50 == 0:
            print(f"  … {n}/{len(codes)} (성공 {ok} 실패 {fail} 행 {saved})", flush=True)
        time.sleep(SLEEP)

    total = conn.execute("SELECT COUNT(*) FROM stock_flow_daily").fetchone()[0]
    days = conn.execute("SELECT COUNT(DISTINCT date) FROM stock_flow_daily").fetchone()[0]
    rng = conn.execute("SELECT MIN(date), MAX(date) FROM stock_flow_daily").fetchone()
    conn.close()
    print(f"완료 {time.time()-t0:.0f}초 — 종목 {ok}/{len(codes)} (실패 {fail}), "
          f"이번에 {saved}행 / 누적 {total:,}행 · {days}일 ({rng[0]}~{rng[1]})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
