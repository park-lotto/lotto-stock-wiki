"""(서버에서 실행) 외국어 말 재료마다 '말하는 사람이 화면에 보이나'를 제미니로 판정 — 원음살리기 조사 1-b.

  python3 on_camera.py census_20261005.json   → /tmp/ov/on_camera.json
입력: speech_census 결과(labels가 '외국어말'인 것만). 원본은 /tmp/ov/manifest.json의 job·slot으로 찾는다.
판정: 말 구간마다 on_camera(입이 보이며 말함) / voiceover(화면 밖 목소리) / unclear, 증언형 여부, 말 밑 음악 여부.
"""
import glob, json, os, sys, time
from google import genai
from google.genai import types

BASE = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/mix_jobs"
keys = [v for k, v in sorted(os.environ.items()) if k.startswith("SHORTS_GEMINI_KEY") and v]
MODELS = ["gemini-3.5-flash", "gemini-3.1-flash-lite"]
src = json.load(open(sys.argv[1], encoding="utf-8"))
man = {m["h"]: m for m in json.load(open("/tmp/ov/manifest.json"))}
OUT = "/tmp/ov/on_camera.json"
out = json.load(open(OUT)) if os.path.exists(OUT) else {}
PROMPT = """이 쇼핑 영상의 말 구간 목록이다(시작초-끝초: 받아쓰기):
%s

각 구간마다 판정해라. 영상과 소리를 함께 보고 판단한다.
- who_speaks: "on_camera"(말하는 사람의 얼굴·입이 화면에 보이고 입 모양이 소리와 맞는다) / "voiceover"(화면엔 손·제품만 보이거나 말하는 입이 안 보인다) / "unclear"
- testimony: 이 말이 "그 사람이 직접 말해야 믿기는 말"(직접 써본 반응·감탄·증언·전문가 설명)이면 true, 광고 문구 읽기·상황 설명이면 false
- music_under: 말 밑에 배경음악이 깔려 있으면 true
- note: 한국어 한 줄(누가 무엇을 하며 말하나)
JSON만 답해라: {"segs":[{"s":0.0,"e":0.0,"who_speaks":"","testimony":false,"music_under":false,"note":""}],"overall":"한국어 한 줄"}"""
ki = 0
for h, lab in src["labels"].items():
    if lab != "외국어말" or h in out:
        continue
    m = man[h]
    f = glob.glob(os.path.join(BASE, m["job"], "s%d" % m["slot"], "*.mp4"))[0]
    segs = src["census"][h]["segs"]
    listing = "\n".join("%.1f-%.1f: %s" % (s["s"], s["e"], s["text"]) for s in segs)
    res = None
    for attempt in range(8):
        key = keys[ki % len(keys)]
        model = MODELS[0] if attempt < 4 else MODELS[1]
        try:
            cl = genai.Client(api_key=key)
            up = cl.files.upload(file=f)
            while up.state.name == "PROCESSING":
                time.sleep(2); up = cl.files.get(name=up.name)
            r = cl.models.generate_content(model=model, contents=[up, PROMPT % listing],
                                           config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            res = json.loads(r.text); res["model"] = model
            break
        except Exception as e:
            print(h, "재시도", attempt, model, repr(e)[:120], flush=True); ki += 1; time.sleep(2)
    out[h] = res or {"error": True}
    n_on = sum(1 for s in (res or {}).get("segs", []) if s.get("who_speaks") == "on_camera")
    print(h, m["plat"], "on_camera %d/%d" % (n_on, len((res or {}).get("segs", []))), (res or {}).get("overall", "")[:60], flush=True)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
