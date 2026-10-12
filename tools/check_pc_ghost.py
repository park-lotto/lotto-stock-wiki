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
    return freed, kept


if __name__ == "__main__":
    main()
