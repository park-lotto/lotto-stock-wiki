# -*- coding: utf-8 -*-
"""버텍스 전환 결과물 검사(관제 159) — 라이브 DB의 실제 호출 기록으로 잰다. 서버에서 돈다:

  ssh ... "python3 - --db /home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db" < tools/vertex_cutoff_check.py

잰 것(api_events, service=gemini):
  ① 관리자(사장님 cid 0) 1~3단계 호출이 pool=vertex 로 갔나 — 배포 뒤 op별 vertex/키풀 건수
  ② 차단 시각 뒤, 관리자 아닌 고객의 pool=vertex(사장님 프로젝트) 호출이 0건인가
  ③ 차단 시각 뒤, 등록 회원의 분석 op(프레임대본·구조분석)가 pool=vertex-member 로 갔나
★api_events.customer_id 가 비어 있는 행은 주인을 못 가린다 — 따로 세어 보여 준다(숨기지 않는다)."""
import argparse
import sqlite3
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True)
ap.add_argument("--cutoff", default="2026-10-08T13:00:00+09:00")
ap.add_argument("--since", default="", help="①을 이 시각(UTC ISO, 예 2026-10-07T20:00:00)부터 잰다 — 배포 시각")
a = ap.parse_args()

from datetime import datetime, timezone
cut_utc = datetime.fromisoformat(a.cutoff).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
since = a.since or cut_utc
c = sqlite3.connect("file:%s?mode=ro" % a.db, uri=True, timeout=30)
admins = {"0"} | {str(r[0]) for r in c.execute("select id from customers where admin=1")}
members = {str(r[0]) for r in c.execute("select customer_id from customer_keys where service='vertex_sa' and coalesce(status,'ok')!='bad'")}
now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
print("지금(UTC) %s · 차단(UTC) %s · 관리자 %d명 · 등록 회원 %d명" % (now_utc, cut_utc, len(admins), len(members)))

print("\n① 관리자 호출 — %s 이후 op × 경로(gemini_usage: vertex=버텍스 / apikey=무료 키풀)" % since)
# ★api_events 는 0번(사장님)의 customer_id 를 비워 적는다(실측 10-08) — 관리자 몫은 gemini_usage 로 잰다.
q = "select coalesce(op,'(미지정)'), auth, count(*) from gemini_usage where ts>=? and customer_id in (%s) group by 1,2 order by 1,2" % ",".join("?" * len(admins))
for r in c.execute(q, [since] + sorted(admins)):
    print("   %-10s %-8s %d" % (r[0], r[1], r[2]))
print("   (1~3단계 op = 프레임대본·대본추출·구조분석·대본생성·ai_match·제작·장면배치 — 이 줄들이 vertex 여야 한다)")

bad = 0
if now_utc < cut_utc:
    print("\n②③ 아직 차단 시각 전 — 건너뜀")
else:
    print("\n② 차단 뒤 pool=vertex(사장님 프로젝트) 호출 — 고객별")
    for cid, n in c.execute("select coalesce(customer_id,'(주인 비어 있음)'), count(*) from api_events where service='gemini' and pool='vertex' and ts>=? group by 1 order by 2 desc", [cut_utc]):
        who = "관리자" if str(cid) in admins else ("주인 미상" if cid == "(주인 비어 있음)" else "★고객")
        if who == "★고객":
            bad += n
        print("   %-16s %-8s %d" % (cid, who, n))
    print("   → 관리자 아닌 고객의 사장님 프로젝트 호출: %d건 (0이어야 한다)" % bad)
    print("\n③ 차단 뒤 등록 회원 호출 — op × pool")
    if members:
        q = "select op, pool, count(*), count(distinct customer_id) from api_events where service='gemini' and ts>=? and customer_id in (%s) group by 1,2 order by 1,3 desc" % ",".join("?" * len(members))
        for r in c.execute(q, [cut_utc] + sorted(members)):
            print("   %-10s %-14s %d건 %d명" % r)
sys.exit(1 if bad else 0)
