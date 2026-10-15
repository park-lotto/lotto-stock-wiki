# -*- coding: utf-8 -*-
"""받아쓰기(단순 작업) — 무료 제미나이 키로. 버텍스 쓰지 않는다(사장님 2026-10-15).
    PYTHONUTF8=1 py tools/calcopy/transcribe_free.py C:/숏템_칼카피/hottemreport
asr/<id>.json 이 없는 편만. 형식은 스피치매틱스와 같은 꼴(results[type=word,start_time,end_time,alternatives]) — 구절 단위.
"""
import json, os, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ["BRAINBULB_VERTEX"] = "0"
from shopping_shorts.channelkit.providers import _env_key
from google import genai
from google.genai import types

base = Path(sys.argv[1]); (base / "asr").mkdir(exist_ok=True)
env = str(ROOT / ".env")
keys = [k for k in (_env_key(n, env) for n in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_BRIEFING_KEY", "GEMINI_BRIEFING_KEY_2", "GEMINI_BRIEFING_KEY_3")) if k]
P = ('이 오디오의 한국어 말소리를 들리는 그대로 받아써라. 구절(쉼 단위)마다 시작·끝 초. 노래 가사·배경음은 빼라. 말이 없으면 빈 목록.\n'
     'JSON만: {"segments":[{"start":0.0,"end":0.0,"text":""}]}')
ki = 0
for mp4 in sorted((base / "mp4").glob("*.mp4")):
    out = base / "asr" / f"{mp4.stem}.json"
    if out.exists():
        continue
    wav = base / "asr" / f"{mp4.stem}.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp4), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", str(wav)], check=True)
    data = wav.read_bytes(); wav.unlink()
    for attempt in range(len(keys) * 2):
        try:
            c = genai.Client(api_key=keys[ki % len(keys)])
            r = c.models.generate_content(model="gemini-2.5-flash", contents=[types.Part.from_bytes(data=data, mime_type="audio/mp3"), P],
                                          config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            seg = json.loads(r.text).get("segments") or []
            res = [{"type": "word", "start_time": s["start"], "end_time": s["end"], "alternatives": [{"content": s["text"]}]} for s in seg]
            out.write_text(json.dumps({"results": res, "engine": "gemini-free"}, ensure_ascii=False), encoding="utf-8")
            print(mp4.stem, len(res)); break
        except Exception as e:  # noqa: BLE001 — 한도면 다음 키
            print(mp4.stem, "재시도", str(e)[:60]); ki += 1; time.sleep(5)
print("끝", len(list((base / "asr").glob("*.json"))))
