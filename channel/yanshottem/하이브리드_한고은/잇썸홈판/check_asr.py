# -*- coding: utf-8 -*-
"""완성본 원음 구간 단독 받아쓰기(검수 B8·B17) — 무료 제미나이 SHORTS_GEMINI_KEY_n, 지시문은 transcribe_free.P(한 벌).
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_한고은/잇썸홈판/check_asr.py"""
import json, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from tools.calcopy.transcribe_free import P  # noqa: E402
from shopping_shorts.channelkit.providers import _env_key  # noqa: E402
from google import genai  # noqa: E402
from google.genai import types  # noqa: E402

R = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/잇썸홈판/render")
FINAL = R / "final.mp4"
WIN = {"O1": (0.0, 3.30), "O5": (6.643, 12.033), "앞전체": (0.0, 12.033), "뒤전체": (12.033, 28.2)}
MODELS = ["gemini-2.5-flash", "gemini-2.5-flash", "gemini-3-flash-preview"]
keys = [k for k in (_env_key(f"SHORTS_GEMINI_KEY_{i}", str(ROOT / ".env")) for i in range(1, 43)) if k]
out, ki = {}, 0
for name, (a, b) in WIN.items():
    mp3 = R / f"asr_{name}.mp3"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(a), "-t", f"{b - a:.3f}", "-i", str(FINAL), "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k", str(mp3)], check=True)
    data = mp3.read_bytes()
    out[name] = []
    for m in MODELS if name in ("O1", "O5") else MODELS[:1]:
        for _ in range(8):
            try:
                c = genai.Client(api_key=keys[ki % len(keys)])
                r = c.models.generate_content(model=m, contents=[types.Part.from_bytes(data=data, mime_type="audio/mp3"),
                                              P + '\n그리고 화자 수를 "speakers" 키(정수)로 같이 넣어라.'],
                                              config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
                j = json.loads(r.text)
                out[name].append({"model": m, "speakers": j.get("speakers"), "text": " ".join(s["text"] for s in j.get("segments") or [])})
                print(name, m, out[name][-1], flush=True)
                break
            except Exception as e:  # noqa: BLE001 — 한도면 다음 키
                print("재시도", str(e)[:80]); ki += 1; time.sleep(3)
        ki += 1
(R / "asr_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
