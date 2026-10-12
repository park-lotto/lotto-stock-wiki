# -*- coding: utf-8 -*-
"""썰채널 107곳 채널당 80편으로 목록 확장 → 새로 나온 조회수 1만↑만 자막 수집 → 기존 781편과 합본 (2026-09-18)
이유: 66·67·69·76 스타일 훅 원문이 0~15편(점검기 audit_spines '첫줄겹침·틀부족'). 08-20엔 채널당 25편만 훑었다."""
import io, json, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
PREV = os.path.join(HERE, "..", "썰쇼핑_자막확장_2026-09-18", "hits_subs.json")
print("1) 목록 수집(채널당 80편)", flush=True)
subprocess.run([sys.executable, "-X", "utf8", "collect_ytdlp.py", "80"], check=False)
allv = json.load(io.open("hits.json", encoding="utf-8"))
prev = json.load(io.open(PREV, encoding="utf-8"))
have = {h["video_id"] for h in prev}
new = [v for v in allv if v["views"] >= 10000 and v["video_id"] not in have]
new.sort(key=lambda v: -v["views"])
io.open("hits_all.json", "w", encoding="utf-8").write(json.dumps(allv, ensure_ascii=False))
io.open("hits.json", "w", encoding="utf-8").write(json.dumps(new, ensure_ascii=False))
print("  목록 %d편 · 새로 받을 1만↑ %d편" % (len(allv), len(new)), flush=True)
print("2) 새 자막 수집", flush=True)
subprocess.run([sys.executable, "-X", "utf8", "pull_subs.py", str(len(new))], check=False)
got = json.load(io.open("hits_subs.json", encoding="utf-8")) if os.path.exists("hits_subs.json") else []
merged = prev + [g for g in got if g["video_id"] not in have]
io.open("hits_subs_merged.json", "w", encoding="utf-8").write(json.dumps(merged, ensure_ascii=False))
print("RUN_DONE 새 자막 %d · 합본 %d" % (len(got), len(merged)), flush=True)
