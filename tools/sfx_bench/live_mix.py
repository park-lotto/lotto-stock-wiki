# -*- coding: utf-8 -*-
"""라이브 썰 대본 작업 전체에 팩 규칙을 돌려 소리 종류 비율·밀도를 이븐쇼핑과 비교(렌더 없음, 읽기 전용).
서버에서: python3 live_mix.py <패키지경로> <DB>"""
import sys, collections
sys.path.insert(0, sys.argv[1]); sys.path.append("/home/ubuntu/lotto-stock-wiki")
import shopping_shorts.store as ST
from shopping_shorts import sfx_pack, video_assemble as va
s = ST.Store(sys.argv[2])
EVEN = {"pop": 90, "whoosh": 77, "tick": 38, "ding": 28, "dung": 27, "click2": 24}
tot = collections.Counter(); secs = 0.0; n = 0; worst = []; nbeats = []; nev = []
import sqlite3
c = sqlite3.connect(f"file:{sys.argv[2]}?mode=ro", uri=True)
for (j,) in c.execute("select job_id from mix_jobs order by created_at desc limit 400"):
    job = s.get_mix_job(j)
    if not sfx_pack.is_sul_script(s, job):
        continue
    plan = job.get("edit_plan") or {}
    tts = {b["beat_idx"]: b["tts_path"] for b in plan.get("beats", []) if b.get("tts_path")}
    try:
        tl = va._beat_timeline(plan, tts)
    except Exception:
        continue
    ev = sfx_pack.plan_events(tl); k = collections.Counter(e[0] for e in ev if e[0] != "opener")
    nbeats.append(len(tl) - 1); nev.append(sum(k.values()))
    tot += k; d = sum(b["dur"] for b in tl); secs += d; n += 1
    worst.append((max(k.values()) / max(1, sum(k.values())), j))
T = sum(tot.values()); E = sum(EVEN.values())
print(f"문장(제목 제외) {sum(nbeats)}개 · 효과음 {sum(nev)}발 → 문장당 {sum(nev) / max(1, sum(nbeats)):.2f} (이븐쇼핑 1.14) · 초당 {sum(nev) / secs:.2f} (이븐쇼핑 자막 교체 효과음 약 0.54)")
print(f"썰 대본 {n}편 · 효과음 {T + n}발 · 초당 {(T + n) / secs:.2f} (이븐쇼핑 1.1~1.2)")
for k in EVEN:
    print(f"  {k:7s} {tot[k] / T * 100:5.1f}%  (이븐쇼핑 {EVEN[k] / E * 100:5.1f}%)")
worst.sort(reverse=True); print("한 종류 최대 비중 가장 높은 편:", [(round(a, 2), j) for a, j in worst[:3]])
