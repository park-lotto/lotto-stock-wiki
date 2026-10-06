"""히트 쇼츠 소리에서 목소리 수·두번째 목소리(리액션/인물대사) 위치를 Gemini로 센다."""
import json, os, sys, glob, time
from google import genai
from google.genai import types
env = {}
for line in open(r"C:/Users/TheRose/Desktop/로또의 주식/shopping_shorts/.env", encoding="utf-8"):
    if "=" in line and not line.startswith("#"):
        k, v = line.strip().split("=", 1); env[k] = v.strip().strip('"')
keys = [env[k] for k in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4") if env.get(k)]
MODEL = sys.argv[1] if len(sys.argv) > 1 else "gemini-2.5-flash"
PROMPT = """이 한국어 쇼츠 영상의 소리를 들어라. 배경음악은 무시하고 사람 목소리(성우·TTS·실제 사람)만 본다.
JSON 하나만 답하라:
{"speech": true/false (사람 말소리가 있나),
 "n_voices": 서로 다른 목소리 수(정수),
 "main": "주 목소리 설명(성별·TTS인지 사람인지·톤)",
 "others": [{"t": 초(숫자), "text": "그 목소리가 한 말 그대로", "who": "누구 같은가(등장인물/리액션/시청자 속마음/효과음성 밈/인터뷰 등)", "kind": "인물대사|리액션|밈사운드|대화상대|기타"}],
 "format": "한 줄로 형식 요약(예: 나레이션 단독 / 나레이션+리액션 / 두 사람 대화 상황극 / 실제 인물 영상)"}
others에는 주 목소리가 아닌 목소리가 말하는 순간을 전부 적어라. 확실하지 않으면 지어내지 말고 비워라."""
out = json.load(open("voices_out.json", encoding="utf-8")) if os.path.exists("voices_out.json") else {}
files = sorted(glob.glob("aud/*"))
ki = 0
for f in files:
    sc = os.path.basename(f).rsplit(".", 1)[0]
    if sc in out and "err" not in out[sc]:
        continue
    data = open(f, "rb").read()
    mime = "audio/mp4" if f.endswith(".m4a") else "audio/webm"
    for attempt in range(len(keys) * 2):
        try:
            c = genai.Client(api_key=keys[ki % len(keys)], http_options=types.HttpOptions(timeout=90000))
            r = c.models.generate_content(model=MODEL, contents=[types.Part.from_bytes(data=data, mime_type=mime), PROMPT],
                                          config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
            out[sc] = json.loads(r.text); out[sc]["model"] = MODEL
            break
        except Exception as e:
            out[sc] = {"err": f"{type(e).__name__}: {str(e)[:160]}"}
            ki += 1; time.sleep(2)
    json.dump(out, open("voices_out.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(sc, "ERR" if "err" in out[sc] else out[sc].get("n_voices"), flush=True)
