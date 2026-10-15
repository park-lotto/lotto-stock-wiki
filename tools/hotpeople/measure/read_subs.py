# -*- coding: utf-8 -*-
"""자막 시트(sub_<id>.png, sheet.py 산출)를 제미니로 읽어 자막 글·강조를 JSON으로.
샘플 폴더에서: PYTHONUTF8=1 py ../measure/read_subs.py   → subs.json
"""
import glob, json, os, sys, time
sys.path.insert(0, r"C:\Users\CH\Desktop\로또의 주식\.tracks\숏템엔진")
from shopping_shorts.channelkit.providers import gemini_reader
from shopping_shorts.channelkit.prompt import parse_any

ENV = r"C:\Users\CH\Desktop\로또의 주식\.tracks\숏템엔진\.env"
readers = [gemini_reader("gemini-3.1-flash-lite", env_file=ENV), gemini_reader("gemini-2.5-flash", env_file=ENV)]
cuts = json.load(open("cuts.json", encoding="utf-8"))
out = json.load(open("subs.json", encoding="utf-8")) if os.path.exists("subs.json") else {}

PROMPT = ("이 그림은 한국어 쇼츠 영상의 자막 시트다. 맨 위 넓은 칸은 헤드라인(제목 2줄), 그 아래 칸들은 자막이고 "
          "각 칸 왼쪽 위 파란 숫자가 자막 번호다. 번호 순서대로 **글자를 그대로** 옮겨라(오타·구두점·따옴표 그대로, 줄바꿈은 ' / ').\n"
          "칸마다: mark = 글자 뒤에 노란 형광펜 띠가 있으면 true, red = 빨간색 글자로 된 단어 목록(없으면 []), lines = 줄 수.\n"
          "빈 칸(자막 없음)은 text를 \"\"로. 번호를 건너뛰거나 지어내지 마라.\n"
          "출력 JSON: {\"headline\": {\"text\": \"…\", \"red\": [...], \"yellow\": [...]}, "
          "\"subs\": [{\"n\": 1, \"text\": \"…\", \"mark\": false, \"red\": [], \"lines\": 1}, …]}")

for png in sorted(glob.glob("sub_*.png")):
    vid = png[4:15]
    if vid in out:
        continue
    n_expect = len(cuts[vid + ".mp4"]["sub_times"]) + 1
    got = None
    for rd in readers:
        for wait in (0, 10, 30):
            if wait: time.sleep(wait)
            try:
                r = parse_any(rd(PROMPT, [png])) or {}
                subs = r.get("subs") if isinstance(r, dict) else None
                if subs and abs(len(subs) - n_expect) <= 2:
                    got = r; break
                print(f"[{vid}] 답 모양/개수 불일치 (기대 {n_expect}, 받음 {len(subs) if subs else None}) — 다시")
            except Exception as e:
                print(f"[{vid}] 실패({wait}s 뒤 재시도): {repr(e)[:120]}")
        if got: break
    if not got:
        print(f"[{vid}] ★실패 — 건너뜀"); continue
    got["n_expect"] = n_expect
    out[vid] = got
    json.dump(out, open("subs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[{vid}] {len(got['subs'])}자막 (기대 {n_expect}) 헤드라인: {got.get('headline', {}).get('text', '')[:40]}")
print("done", len(out))
