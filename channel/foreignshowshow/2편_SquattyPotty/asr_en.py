# -*- coding: utf-8 -*-
"""샥탬스토리 2편 — 영어 원음 구간 받아쓰기(시각 포함). 서버 키 풀(gemini_server.ask_files) 부르기만, 2모델 교차.
    PYTHONUTF8=1 py channel/foreignshowshow/2편_SquattyPotty/asr_en.py <mp4> <out.json> a-b [a-b …]
결과: 구간마다 모델별 segs[{s,e,who,text}] (s·e 는 구간 안 상대초 → 저장 때 절대초로 바꾼다)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import gemini_server as G

P = ('Transcribe every spoken English word in this audio exactly as heard (skip music/sound effects, do not fix or add). '
     'Split into phrases (pause units) with start/end seconds relative to this clip, and who speaks '
     '(role only, no names: founder-man, founder-woman, investor-man, investor-woman, narrator, other). If no speech, empty list.\n'
     'JSON only: {"segs":[{"s":0.0,"e":0.0,"who":"","text":""}]}')

def main():
    src, out = sys.argv[1], Path(sys.argv[2])
    spans = [tuple(float(x) for x in s.split("-")) for s in sys.argv[3:]]
    r = G.ask_files([(src, a, b) for a, b in spans], P, "audio")
    res = []
    for (a, b), job in zip(spans, r["jobs"]):
        runs = []
        for m in job["runs"]:
            if "why" in m:
                runs.append({"model": m["model"], "why": m["why"]}); continue
            j = m.get("json") or {}
            if isinstance(j, list):
                j = {"segs": j[0].get("segs", j) if len(j) == 1 and isinstance(j[0], dict) and "segs" in j[0] else j}
            segs = [{"s": round(a + float(g.get("s", 0)), 2), "e": round(a + float(g.get("e", 0)), 2), "who": g.get("who", ""), "text": g.get("text", "")}
                    for g in (j.get("segs") or [])]
            runs.append({"model": m["model"], "segs": segs})
        res.append({"span": [a, b], "runs": runs})
    out.write_text(json.dumps({"src": src, "sec": r["sec"], "jobs": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    for j in res:
        for m in j["runs"]:
            print("==", j["span"], m["model"], m.get("why", ""))
            for g in m.get("segs") or []:
                print(f'  {g["s"]:7.2f}-{g["e"]:7.2f} {g["who"]:>14} | {g["text"]}')

if __name__ == "__main__":
    main()
