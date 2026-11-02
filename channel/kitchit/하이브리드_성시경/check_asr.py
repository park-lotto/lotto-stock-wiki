# -*- coding: utf-8 -*-
"""완성(자막 전) 영상 줄별 받아쓰기 — 무료 제미나이 창구(gemini_free.ask, 로컬→서버 자동) 2모델 교차. timeline.json 의 줄 구간.
    PYTHONUTF8=1 py channel/kitchit/하이브리드_성시경/check_asr.py   → render/asr_final_local.json"""
import json, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import gemini_free as G
R = Path("C:/숏템_칼카피/kitchit/sinramen/render"); (R / "asrclip").mkdir(exist_ok=True)
T = json.loads((R / "timeline.json").read_text(encoding="utf-8"))
P = '이 한국어 음성을 들리는 그대로 받아써라. JSON {"text":"...","speakers":화자수}'
def one(r):
    p = R / "asrclip" / f"{r['id']}.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(max(0, r["t0"] - 0.05)), "-to", str(r["t1"] + 0.05), "-i", str(R / "base_nocap.mp4"), "-vn", "-ac", "1", "-b:a", "96k", str(p)])
    out = []
    for m in ("gemini-3-flash-preview", "gemini-3.5-flash"):
        for _ in range(3):
            d, e = G.ask([(p.read_bytes(), "audio/mpeg")], P, "kitchit_asr", models=(m,))
            if d: break
        out.append({"model": m, "text": (d or {}).get("text"), "speakers": (d or {}).get("speakers"), "err": e})
    return {"id": r["id"], "t0": r["t0"], "t1": r["t1"], "runs": out}
with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(one, T["rows"]))
(R / "asr_final_local.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
for x in res:
    print(x["id"], x["t0"], [(y["text"], y["speakers"]) for y in x["runs"]])
