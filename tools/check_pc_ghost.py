# -*- coding: utf-8 -*-
"""PC 2칸 꽉 찬 회원에게 '새 PC 등록'을 했을 때 누가 풀리나 — 라이브 기록으로 모의 실행(관제 142).

라이브 reference.db 의 customer_devices 를 **읽기만** 해 오고, 로컬 임시 DB 에 그대로 넣어
지금 코드의 Store.device_register 를 돌린다. 라이브 DB 는 건드리지 않는다.

    py tools/check_pc_ghost.py          # 풀리는 회원 / 계속 막히는 회원 목록
"""
import json
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from shopping_shorts.store import Store  # noqa: E402

KEY = r"C:/Users/TheRose/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
HOST = "ubuntu@3.35.251.172"
REMOTE = r'''cd /home/ubuntu/lotto-stock-wiki/shopping_shorts && python3 -c "
import sqlite3,glob,json
db=[p for p in glob.glob('data/*.db') if 'reference' in p][0]
c=sqlite3.connect('file:'+db+'?mode=ro',uri=True)
print(json.dumps(c.execute('select customer_id,slot,device_id,first_seen,last_seen,ua,ip from customer_devices').fetchall()))"'''


def main():
    out = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", KEY, HOST, REMOTE],
                         capture_output=True, text=True, timeout=60)
    rows = json.loads(out.stdout.strip().splitlines()[-1])
    st = Store(str(pathlib.Path(tempfile.mkdtemp()) / "sim.db"))
    st.device_list(1)                                   # 스키마 생성
    with st._conn() as c:
        c.executemany("INSERT INTO customer_devices(customer_id,slot,device_id,first_seen,last_seen,ua,ip) "
                      "VALUES(?,?,?,?,?,?,?)", rows)
    per = {}
    for r in rows:
        per[r[0]] = per.get(r[0], 0) + 1
    full = sorted(cid for cid, n in per.items() if n >= st.PC_SLOTS)
    freed, kept = [], []
    for cid in full:
        before = {d["slot"]: d["device_id"] for d in st.device_list(cid)}
        ok, slot, why = st.device_register(cid, "sim-new-pc-%d" % cid, "sim", "0.0.0.0")
        if ok:
            others_same = all(before[s] == d["device_id"] for d in st.device_list(cid)
                              for s in [d["slot"]] if s != slot)
            freed.append((cid, slot, others_same))
        else:
            kept.append(cid)
    print("등록 회원 %d / 2칸 꽉 참 %d" % (len(per), len(full)))
    print("새 PC 등록 시 풀림(유령 칸 교체) %d: %s" % (len(freed), [(c, "%d번" % s) for c, s, _ in freed]))
    print("  └ 다른 칸(쓰던 PC) 그대로: %s" % all(x[2] for x in freed))
    print("계속 막힘(2칸 다 실사용) %d: %s" % (len(kept), kept))
    # 관제 184: 막힌 회원이 **같은 PC**(가장 최근 칸과 같은 IP·브라우저)에서 쿠키만 날아간 경우
    same_ok, same_no = [], []
    for cid in kept:
        last = max(st.device_list(cid), key=lambda d: d["last_seen"] or 0)
        ok, slot, _ = st.device_register(cid, "sim-same-pc-%d" % cid, last["ua"], last["ip"])
        (same_ok if ok else same_no).append(cid)
    print("  └ 그중 같은 PC 쿠키 손실이면 풀림 %d: %s / 안 풀림 %s" % (len(same_ok), same_ok, same_no))
    # 관제 238: 등록된 **모든 칸**에서 쿠키를 잃고 크롬이 한 단계 올라갔을 때(윤주홍 10-19) 버튼 없이 통과하나
    #   + 같은 칸 수 그대로인가 / 다른 장소(처음 보는 IP)의 새 PC는 여전히 막히나
    import re as _re
    bump = lambda ua: _re.sub(r"Chrome/(\d+)", lambda m: "Chrome/%d" % (int(m.group(1)) + 1), ua or "")
    pass_n, fail = 0, []
    for cid, slot, _d, _f, _l, ua, ip in rows:
        st2 = Store(str(pathlib.Path(tempfile.mkdtemp()) / "re.db"))
        st2.device_list(1)
        with st2._conn() as c:
            c.executemany("INSERT INTO customer_devices(customer_id,slot,device_id,first_seen,last_seen,ua,ip) "
                          "VALUES(?,?,?,?,?,?,?)", [r for r in rows if r[0] == cid])
        ok, got, _n = st2.device_check(cid, "sim-lost-cookie", bump(ua), ip)
        if ok and len(st2.device_list(cid)) == per[cid]:
            pass_n += 1
        else:
            fail.append((cid, slot, got))
    blocked = sum(1 for cid in full
                  if not st.device_check(cid, "sim-elsewhere", "Mozilla/5.0 (Windows NT 10.0) Chrome/999", "203.0.113.9")[0])
    print("쿠키 잃고 크롬 업데이트된 같은 PC(전 칸 %d): 버튼 없이 통과 %d / 실패 %s" % (len(rows), pass_n, fail))
    print("다른 장소 새 PC(꽉 찬 %d명): 막힘 %d" % (len(full), blocked))
    return freed, kept


if __name__ == "__main__":
    main()
