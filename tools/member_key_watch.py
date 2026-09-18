# -*- coding: utf-8 -*-
"""회원 키 교체 추적 — 안내 쪽지를 보낸 회원이 **읽었나 · 새 키를 넣었나 · 그 뒤 성공했나**를 한 줄로.

2026-09-18 사장님 "임수정님은 바뀌었는지 계속 추적". 서버에서 읽기 전용으로 돈다(DB에 쓰지 않는다).

  python3 member_key_watch.py --cid 572 --service elevenlabs --report 23          # 지금 상태 한 번
  python3 member_key_watch.py --cid 572 --service elevenlabs --report 23 --wait 10800
      # 상태가 바뀔 때까지(최대 3시간) 5분마다 보고, 바뀌면 그 줄을 찍고 끝난다.
"""
import argparse
import datetime
import sqlite3
import time

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
KST = datetime.timezone(datetime.timedelta(hours=9))


def _t(epoch):
    return datetime.datetime.fromtimestamp(epoch, KST).strftime("%m-%d %H:%M") if epoch else None


def snapshot(cid, service, report_id):
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        rep = c.execute("SELECT read_at FROM bug_reports WHERE id=? AND customer_id=?",
                        (report_id, cid)).fetchone() if report_id else None
        keys = c.execute("SELECT id, status, created_at, label FROM customer_keys "
                         "WHERE customer_id=? AND service=? ORDER BY id", (cid, service)).fetchall()
        ev = c.execute("SELECT outcome, COUNT(*), MAX(ts) FROM api_events WHERE service=? AND customer_id=? "
                       "AND ts > datetime('now','-1 day') GROUP BY outcome", (service, str(cid))).fetchall()
        name = (c.execute("SELECT name FROM customers WHERE id=?", (cid,)).fetchone() or ["?"])[0]
    finally:
        c.close()
    return {
        "name": name,
        "read": _t(rep[0]) if rep and rep[0] else ("안 읽음" if report_id else "-"),
        "keys": [(k[0], k[1], _t(k[2]), k[3]) for k in keys],
        "events": {o: (n, (last or "")[5:16]) for o, n, last in ev},
    }


def line(s, cid, service):
    ok = s["events"].get("ok", (0, ""))
    bad = {k: v for k, v in s["events"].items() if k != "ok"}
    return (f"회원 {cid} {s['name']} [{service}] 쪽지 읽음: {s['read']} | 등록 키: "
            f"{[(k[0], k[1], k[2]) for k in s['keys']] or '없음'} | 24h 성공 {ok[0]}건(마지막 {ok[1]} UTC) "
            f"실패 {bad or '없음'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cid", type=int, required=True)
    ap.add_argument("--service", required=True)
    ap.add_argument("--report", type=int, default=0)
    ap.add_argument("--wait", type=int, default=0, help="초. 바뀔 때까지 5분마다 확인")
    a = ap.parse_args()
    first = snapshot(a.cid, a.service, a.report)
    print("[시작]", line(first, a.cid, a.service), flush=True)
    if not a.wait:
        raise SystemExit(0)
    sig0 = (first["read"], [k[:2] for k in first["keys"]], first["events"].get("auth_dead", (0,))[0])
    end = time.time() + a.wait
    while time.time() < end:
        time.sleep(300)
        s = snapshot(a.cid, a.service, a.report)
        sig = (s["read"], [k[:2] for k in s["keys"]], s["events"].get("auth_dead", (0,))[0])
        if sig != sig0:
            print("[변화]", line(s, a.cid, a.service), flush=True)
            raise SystemExit(0)
    print("[시간 끝 — 변화 없음]", line(snapshot(a.cid, a.service, a.report), a.cid, a.service), flush=True)
