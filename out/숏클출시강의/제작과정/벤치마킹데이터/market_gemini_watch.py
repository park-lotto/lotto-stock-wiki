"""인기 쇼츠 6편을 Gemini 가 소리까지 보고 구조를 받아 적는다(무료 키 순환)."""
import json, os, re, sys, time
from google import genai

HERE = os.path.dirname(os.path.abspath(__file__))
DIRS = ["vid_ko","vid_long","vid_short"]
ENV = r"C:\Users\TheRose\Desktop\로또의 주식\.tracks\유튜브제작\.env"
keys = [l.split("=", 1)[1].strip().strip('"') for l in open(ENV, encoding="utf-8")
        if l.startswith("GEMINI") and "=" in l and l.split("=", 1)[1].strip()]
meta = {d["id"]: d for d in json.load(open(os.path.join(HERE, "top6.json"), encoding="utf-8"))} \
    if os.path.exists(os.path.join(HERE, "top6.json")) else {}

PROMPT = """You are analyzing a YouTube video (Short, or the first 5 minutes of a long video) that explains/sells a shorts-automation / AI video program or side-hustle method. Watch it fully WITH AUDIO.
Answer in Korean, as JSON only:
{"length_sec":..,"hook_first_1s":"첫 1초에 화면·소리로 무엇을 보여/들려 붙잡나",
 "hook_first_3s_words":"첫 3초 대사·화면 글자 원문",
 "format":"세로 구성 방식(가로 영상 크롭/위아래 여백+큰 자막/원래 세로 등)",
 "voice":"나레이션·사람 말·음악만 중 무엇, 말투",
 "beats":[{"t":"0-3","what":"화면","said":"대사/글자","role":"훅/문제/시연/증거/전환/CTA"}],
 "is_cut_from_long":"롱폼에서 잘라낸 것으로 보이는가와 근거",
 "ending_last_3s":"마지막 3초 화면·말",
 "long_form_pointer":"롱폼·전체 영상·링크로 보내는 말/자막/장치가 있나(정확히 인용, 없으면 없음)",
 "captions_style":"자막 크기·위치·색",
 "explain_style":"설명 방식(말·화면 시연·전후 비교·수익 인증·비유·숫자) 구체적으로",
 "trust_devices":"믿게 만드는 장치(실화면·수익화면·솔직 고백·실패담 등) 인용",
 "sales_transition":"판매·강의·프로그램으로 넘어가는 지점과 말(앞 5분 안에 있으면)",
 "pacing":"컷 길이·화면 글자 양·자막 스타일",
 "why_it_works":"이 쇼츠가 조회수를 낸 이유 추정 1~2줄(추정이라고 표시)"}"""

def run(path, ki):
    for attempt in range(len(keys) * 2):
        key = keys[(ki + attempt) % len(keys)]
        try:
            c = genai.Client(api_key=key)
            f = c.files.upload(file=path)
            while f.state.name == "PROCESSING":
                time.sleep(3); f = c.files.get(name=f.name)
            r = c.models.generate_content(model="gemini-2.5-flash", contents=[f, PROMPT])
            txt = r.text
            m = re.search(r"\{.*\}", txt, re.S)
            return json.loads(m.group(0)) if m else {"raw": txt}
        except Exception as e:
            print("  retry", attempt, type(e).__name__, str(e)[:120], flush=True); time.sleep(8)
    return {"error": "all keys failed"}

out = {}
vids = [(d, fn) for d in DIRS for fn in sorted(os.listdir(os.path.join(HERE, d)))]
for i, (d, fn) in enumerate(vids):
    vid = fn.rsplit(".", 1)[0]
    print("watch", d, vid, flush=True)
    res = run(os.path.join(HERE, d, fn), i * 2)
    res["_dir"] = d
    res["_meta"] = meta.get(vid, {})
    out[vid] = res
    json.dump(out, open(os.path.join(HERE, "gemini_market.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", len(out))
