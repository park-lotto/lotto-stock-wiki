# r7 녹음: 일레븐랩스 Chris · 속도 1.2(일레븐랩스 자체만, 뒤에서 빠르게 하지 않음) · 숫자+단위 붙여쓰기 · 첫소리 보존
# narr/lines.json 의 tts → narr/raw_r7/NNN.mp3 → narr/trim/NNN.wav (+ dur 갱신)
# 사용: python -X utf8 tts_elevenlabs.py [--only 3,7]   (작업 폴더에서는 tts_r7.py 라는 이름)
import json, os, re, sys, time, subprocess, urllib.request, urllib.error, concurrent.futures as cf
args = sys.argv[1:]
def opt(n, d): return args[args.index(n) + 1] if n in args else d
ONLY = set(int(x) for x in opt("--only", "").split(",") if x)
VID = opt("--voice", "PDoCXqBQFGsvfO0hNkEs"); SPEED = float(opt("--speed", "1.2"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from textglue import glue
NARR = os.path.join(os.path.abspath(os.environ.get("LONGFORM_WORK") or os.getcwd()), "narr")
RAW = os.path.join(NARR, "raw_r7"); TRIM = os.path.join(NARR, "trim"); os.makedirs(RAW, exist_ok=True); os.makedirs(TRIM, exist_ok=True)
key = open(os.path.expanduser("~/.volcano/keys/elevenlabs"), encoding="utf-8").read().strip()
lines = json.load(open(os.path.join(NARR, "lines.json"), encoding="utf-8"))
L = [l for l in lines if l["type"] == "line"]
SOFT = ("silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.06,"
        "areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.08,areverse,aresample=48000,aformat=channel_layouts=mono")

left = [(l["i"], l["tts"]) for l in L if re.search(r"[0-9%~/]", l["tts"])]
if left:  # 숫자·기호는 숫자한글읽기_지침.md 대로 tts 칸을 한글로 먼저 바꿔야 한다
    for i, s in left: print("숫자 남음", i, s)
    sys.exit("tts 칸에 숫자·기호가 남아 있어 멈춤")

def tts(j):
    l = L[j]; raw = os.path.join(RAW, f"{l['i']:03d}.mp3")
    if os.path.exists(raw) and not ONLY: return l["i"], "skip"
    body = {"text": glue(l["tts"]), "model_id": "eleven_multilingual_v2",
            "previous_text": glue(L[j - 1]["tts"]) if j > 0 else None,
            "next_text": glue(L[j + 1]["tts"]) if j + 1 < len(L) else None,
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.1, "use_speaker_boost": True, "speed": SPEED}}
    msg = ""
    for k in range(4):
        try:
            req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VID}?output_format=mp3_44100_192",
                  data=json.dumps(body).encode(), headers={"xi-api-key": key, "Content-Type": "application/json"}, method="POST")
            open(raw, "wb").write(urllib.request.urlopen(req, timeout=180).read()); return l["i"], "ok"
        except urllib.error.HTTPError as e:
            msg = f"http {e.code} {e.read()[:200]}"
            if e.code in (400, 401, 402, 403): return l["i"], msg
        except Exception as e:
            msg = str(e)
        time.sleep(3 + k * 4)
    return l["i"], "fail " + msg

todo = [j for j, l in enumerate(L) if not ONLY or l["i"] in ONLY]
bad = []
with cf.ThreadPoolExecutor(3) as ex:
    for i, r in ex.map(tts, todo):
        if r not in ("skip", "ok"): bad.append(i); print(i, r, flush=True)
if bad: print("실패:", bad); sys.exit(1)
for j in todo:
    l = L[j]; raw = os.path.join(RAW, f"{l['i']:03d}.mp3"); tr = os.path.join(TRIM, f"{l['i']:03d}.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", SOFT, tr], check=True)
    l["dur"] = round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tr],
                                          capture_output=True, text=True).stdout), 3)
json.dump(lines, open(os.path.join(NARR, "lines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
tot = sum(l.get("dur", 0) for l in L)
syl = sum(len(re.findall(r"[가-힣0-9]", l["text"])) for l in L)
print(f"문장 {len(L)} · 말소리 합계 {tot:.1f}초 ({tot / 60:.2f}분) · 분당 {syl / (tot / 60):.0f}음절")
