# -*- coding: utf-8 -*-
"""고객이 실제로 받은 2단계 대본 후보 전수 집계 — 계획을 세우기 전에 **무엇이 얼마나 고장인지** 센다 (2026-09-21).
서버(읽기 전용 mode=ro, 집계 숫자만 — 고객 대본 원문은 안 찍는다):
    python3 /home/ubuntu/patchcheck/draft_census.py [--days 14]"""
import argparse
import collections
import datetime
import json
import re
import sqlite3

DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
ap = argparse.ArgumentParser()
ap.add_argument("--days", type=int, default=14)
a = ap.parse_args()
con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
since = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=a.days)).strftime("%Y-%m-%d")
spine = {r[0]: (r[1] or "", r[2] or "") for r in con.execute("SELECT id, name, fit_categories_json FROM spine")}
MISUSE = re.compile(r"활용법|사용법|용도")            # 이야기 거푸집(오용형) 이름 표지
STORY = re.compile(r"초보들은|중수들은|고수들은|원래는 .{2,30}(이었음|였음|물건|용도)")

works = drafts = 0
keys = collections.Counter(); by_style = collections.Counter(); tries_n = collections.Counter()
fail_names = collections.Counter(); passed = collections.Counter(); kinds = collections.Counter()
misuse_d = misuse_story = 0; custs = set()
for cid, sj in con.execute("SELECT customer_id, state_json FROM produce_works WHERE updated_at >= ? AND customer_id > 0", (since,)):
    try:
        s2 = (json.loads(sj or "{}").get("s2") or {})
    except Exception:      # noqa: BLE001
        continue
    ds = [d for d in (s2.get("drafts") or []) if isinstance(d, dict)]
    if not ds:
        continue
    works += 1; custs.add(cid)
    for d in ds:
        drafts += 1
        for k in d.keys():
            keys[k] += 1
        sid = d.get("style_id")
        name = d.get("style_name") or (spine.get(sid, ("", ""))[0] if sid else "")
        kinds["스타일 경로" if sid else ("픽업/기타" if not d.get("auto") else "자동")] += 1
        by_style[(sid, name[:26])] += 1
        tr = d.get("tries")
        if isinstance(tr, list):
            tries_n[len(tr)] += 1
            for t in tr[:-1] if len(tr) > 1 else []:
                for f in (t.get("fails") or []):
                    fail_names[re.sub(r"\(.*?\)", "", str(f))] += 1
        if "passed" in d:
            passed[bool(d.get("passed"))] += 1
        text = d.get("script") or "\n".join(str((b or {}).get("text") or "") for b in (d.get("beats") or []) if isinstance(b, dict))
        if MISUSE.search(name or ""):
            misuse_d += 1
            if STORY.search(text or ""):
                misuse_story += 1
print("== 최근 %d일 · 고객(cid>0) %d명 · 후보 있는 작업 %d건 · 후보 %d편" % (a.days, len(custs), works, drafts))
print("== 경로:", dict(kinds))
print("== 후보에 저장된 항목(상위):", [k for k, _ in keys.most_common(14)])
print("== 통과 표시:", dict(passed))
print("== 쓰기 시도 횟수 분포(tries 길이):", dict(sorted(tries_n.items())))
print("== 재작성을 부른 게이트 실패(앞선 시도 기준):")
for f, n in fail_names.most_common(10):
    print("     %4d  %s" % (n, f))
print("== 스타일별 후보 수(상위 12):")
for (sid, nm), n in by_style.most_common(12):
    print("     %4d  [%s] %s" % (n, sid, nm))
print("== 오용형(이름에 활용법·사용법·용도) 후보 %d편 = 전체의 %.0f%% · 그중 '초보/고수·원래는' 거푸집 문장이 실제로 들어간 것 %d편"
      % (misuse_d, 100.0 * misuse_d / max(1, drafts), misuse_story))
