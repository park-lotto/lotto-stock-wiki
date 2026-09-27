# -*- coding: utf-8 -*-
"""채널 단위(C)·터지는 지점(V) 통계 — yt-dlp *.info.json(--skip-download --write-info-json) 폴더에서.
사용: PYTHONUTF8=1 py channel_stats.py <info.json 폴더> → rows_scored.json + 콘솔.
잰 것: 편수·기간·업로드 주기·조회 분포·조회/구독 배수·이상치(조회÷중앙)·상위10 vs 하위10(길이·제목 글자수·해시태그·
       좋아요/조회·댓글/조회)·시기별 조회 중앙. ★조회는 시간이 지나야 안정된다 — 최근 편은 하위로 오판될 수 있다(--min-age 로 제외).
"""
import json, glob, os, re, sys, statistics as st, datetime as dt

d = sys.argv[1] if len(sys.argv) > 1 else "."
min_age = int(sys.argv[2]) if len(sys.argv) > 2 else 0    # 며칠 미만 편은 상·하위 비교에서 뺀다
rows = []
for f in glob.glob(os.path.join(d, "*.info.json")):
    j = json.load(open(f, encoding="utf-8"))
    if not j.get("upload_date"):
        continue
    rows.append({k: j.get(k) for k in ["id", "title", "upload_date", "duration", "view_count", "like_count", "comment_count", "channel_follower_count"]})
rows.sort(key=lambda r: r["upload_date"])
n = len(rows); v = [r["view_count"] or 0 for r in rows]; med = st.median(v)
def q(a, p): a = sorted(a); return a[int(len(a) * p)]
d0, d1 = (dt.datetime.strptime(rows[i]["upload_date"], "%Y%m%d") for i in (0, -1))
days = max((d1 - d0).days, 1)
print(f"편수 {n} / 기간 {rows[0]['upload_date']}~{rows[-1]['upload_date']} / 구독 {rows[-1]['channel_follower_count']}")
print(f"업로드 주기 {n / days:.2f}편/일 (같은 날 2편↑ {sum(1 for k in set(r['upload_date'] for r in rows) if sum(1 for r in rows if r['upload_date'] == k) > 1)}일)")
print(f"조회 중앙 {med:.0f} p25 {q(v, .25)} p75 {q(v, .75)} max {max(v)} / 10만↑ {sum(1 for x in v if x >= 1e5)}/{n} / 100만↑ {sum(1 for x in v if x >= 1e6)}")
print(f"조회/구독 배수 중앙 {med / rows[-1]['channel_follower_count']:.1f}x")
today = dt.datetime.now()
for r in rows:
    r["outlier"] = r["view_count"] / med; r["lv"] = (r["like_count"] or 0) / max(r["view_count"], 1) * 100
    r["cv"] = (r["comment_count"] or 0) / max(r["view_count"], 1) * 1000; r["tl"] = len(r["title"]); r["ht"] = len(re.findall(r"#\S+", r["title"]))
    r["age"] = (today - dt.datetime.strptime(r["upload_date"], "%Y%m%d")).days
aged = [r for r in rows if r["age"] >= min_age]
top = sorted(aged, key=lambda r: -r["view_count"])[:10]; bot = sorted(aged, key=lambda r: r["view_count"])[:10]
def g(rs, k): a = [r[k] for r in rs]; return f"{st.median(a):.2f} ({min(a):.2f}~{max(a):.2f})"
print(f"\n(상·하위 비교: {min_age}일 이상 된 {len(aged)}편)\n| 지표 | 상위10 | 하위10 | 전체 |")
for k, lab in [("duration", "길이 초"), ("tl", "제목 글자수"), ("ht", "해시태그 수"), ("lv", "좋아요/조회 %"), ("cv", "댓글/조회 ‰"), ("outlier", "이상치(조회÷중앙)")]:
    print(f"| {lab} | {g(top, k)} | {g(bot, k)} | {g(rows, k)} |")
print("\n상위10:"); [print(f"  {r['view_count']:>9,} {r['duration']}s {r['upload_date']} {r['title']}") for r in top]
print("하위10:"); [print(f"  {r['view_count']:>9,} {r['duration']}s {r['upload_date']} {r['title']}") for r in bot]
if n >= 40:
    print(f"\n시기별 조회 중앙: 첫20 {st.median([r['view_count'] for r in rows[:20]]):.0f} / 중간 {st.median([r['view_count'] for r in rows[20:-20]] or [0]):.0f} / 최근20 {st.median([r['view_count'] for r in rows[-20:]]):.0f}")
json.dump(rows, open(os.path.join(d, "rows_scored.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
