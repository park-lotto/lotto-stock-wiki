# -*- coding: utf-8 -*-
"""탭 잠금 라이브 검사(관제 134) — 잠근 탭에 '사람이 지정하지 않은' 유튜브 영상이 몇 편 떠 있나.

사장님(2026-10-06): "홈템이랑 썰쇼핑은 다른거 들어오지 못하게 막아놔".
잠금 규칙의 주인은 shopping_shorts/store.py:_apply_overrides 다. 이 도구는 규칙을 다시 계산하지 않고
**라이브 랭킹 응답(고객이 받는 것)** 을 서버의 채널 고정표·영상 지정표와 대조만 한다.

    py tools/check_category_tab_lock.py         # 밖 영상 0편이면 rc=0, 있으면 rc=1
"""
import collections
import json
import subprocess
import sys

sys.path.insert(0, ".")
from tools import live_admin as la  # noqa: E402

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
_Q = ("python3 -c \"import sqlite3,json; c=sqlite3.connect('file:%s?mode=ro',uri=True,timeout=30); "
      "print(json.dumps({'force':dict(c.execute('SELECT username,category FROM channel_category_force')),"
      "'ov':dict(c.execute('SELECT shortcode,category FROM category_overrides')),"
      "'lock':(c.execute(\\\"SELECT value FROM settings WHERE key='yt_category_lock'\\\").fetchone() or [''])[0]}))\"" % DB)
_JS = """async () => (((await (await fetch('/api/reference?platform=youtube')).json()).items)||[])
        .map(i => [i.username, i.name, i.category, i.shortcode])"""


def main():
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", la.KEY, la.HOST, _Q],
                       capture_output=True, text=True, encoding="utf-8", timeout=120)
    if r.returncode:
        print("서버 표를 못 읽었다:", (r.stderr or "")[-300:])
        return 2
    t = json.loads(r.stdout.strip().splitlines()[-1])
    force, ov = t["force"], t["ov"]
    lock = [x.strip() for x in (t["lock"] or "").split(",") if x.strip()]
    with la.admin_page("") as pg:
        items = pg.evaluate(_JS)
    print("잠금 설정:", ",".join(lock) or "(꺼짐)", "| 라이브 유튜브 영상", len(items), "편")
    if not items:
        print("라이브 응답이 비었다 — 검사 불가")
        return 2
    bad = 0
    for cat in lock or ["제품정체형", "오용형", "홈템"]:
        vs = [i for i in items if i[2] == cat]
        out = [i for i in vs if ov.get(i[3]) != cat and force.get((i[0] or "").lower()) != cat]
        chs = collections.Counter(i[1] for i in out)
        print("  %s: 영상 %d편 / 채널 %d개 — 지정 밖 %d편 / %d채널 %s" % (
            cat, len(vs), len({i[0] for i in vs}), len(out), len(chs),
            ("예: " + ", ".join(n for n, _ in chs.most_common(5))) if out else ""))
        bad += len(out)
    print("결과:", "잠김(지정 밖 0편)" if not bad else "지정 밖 영상 %d편" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
