# 대본(md) → 문장 목록(lines.json) → 타입캐스트 TTS(문장별 wav) → 앞뒤 무음 정리
# 사용: python -X utf8 tts.py <대본.md> <출력폴더> [--voice Piljae] [--tempo 1.2] [--only 3,7]
import json, os, re, sys, time, subprocess, urllib.request, concurrent.futures as cf
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT, OUT = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
def opt(name, default):
    return args[args.index(name) + 1] if name in args else default
VOICE = opt("--voice", "Piljae"); TEMPO = float(opt("--tempo", "1.2"))
ONLY = set(int(x) for x in opt("--only", "").split(",") if x)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from textglue import glue
os.makedirs(os.path.join(OUT, "raw"), exist_ok=True); os.makedirs(os.path.join(OUT, "trim"), exist_ok=True)

# 1) 대본 파싱
text = open(SCRIPT, encoding="utf-8").read().split("## 사실 검증")[0]
lines, chapter = [], None
for ln in text.splitlines():
    s = ln.strip()
    m = re.match(r"^## \[(.+)\]$", s)
    if m: chapter = m[1]; continue
    if s == "[범퍼]": lines.append({"type": "bumper", "chapter": chapter}); continue
    if s.startswith("<!--"):  # 뺀 문장: 번호는 그대로 차지(오디오 번호가 밀리지 않게)하되 녹음하지 않음
        lines.append({"type": "skip", "chapter": chapter, "text": ""}); continue
    if not s or s.startswith(("#", "-", "---", "|", ">")): continue
    srcs = re.findall(r"\{([^}]*)\}", s)
    sub = re.sub(r"\s*\{[^}]*\}", "", s).strip()
    lines.append({"type": "line", "chapter": chapter, "text": sub, "src": srcs})
n = 0
for l in lines:
    if l["type"] in ("line", "skip"): n += 1; l["i"] = n

# 2) 읽는 소리로 바꾸기 (TTS 전용 — 자막은 원문)
READ = [
    (r"AA-", "더블에이 마이너스"), (r"A\+", "에이 플러스"), (r"GDP", "지디피"), (r"OECD", "오이시디"),
    (r"IMF", "아이엠에프"), (r"KDI", "케이디아이"), (r"4\.98%", "4.98퍼센트"), (r"1\.12달러", "1.12달러"),
    (r"(\d+(?:\.\d+)?)%", r"\1퍼센트"), (r"1, 2위", "일 위, 이 위"), (r"르코르뉘", "르코르뉘"),
]
def yomi(s):
    for a, b in READ: s = re.sub(a, b, s)
    s = s.replace("'", "").replace("‘", "").replace("’", "")
    return s
_lp = os.path.join(OUT, "lines.json")
_kept = {x["text"]: x["tts"] for x in json.load(open(_lp, encoding="utf-8")) if x.get("tts")} if os.path.exists(_lp) else {}
for l in lines:   # 손으로 바꾼 tts 칸(숫자한글읽기)은 같은 문장이면 그대로 둔다
    if l["type"] == "line": l["tts"] = _kept.get(l["text"]) or yomi(l["text"])
json.dump(lines, open(os.path.join(OUT, "lines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if "--parse-only" in args:  # 일레븐랩스(tts_r7.py)로 녹음할 때: 문장 목록만 만들고 끝
    print(f"문장 목록만 만듦: {os.path.join(OUT, 'lines.json')}"); sys.exit(0)
left = [(l["i"], l["tts"]) for l in lines if l["type"] == "line" and re.search(r"[0-9%~/]", l["tts"])]
if left:  # 숫자·기호는 숫자한글읽기_지침.md 대로 tts 칸을 한글로 먼저 바꿔야 한다
    for i, t in left: print("숫자 남음", i, t)
    sys.exit("tts 칸에 숫자·기호가 남아 있어 멈춤")

# 3) TTS
key = open(os.path.expanduser("~/.volcano/keys/typecast"), encoding="utf-8").read().strip()
vid = {v["voice_name"]: v["voice_id"] for v in json.load(open(os.path.join(HERE, "typecast_voices_v2.json"), encoding="utf-8"))}[VOICE]
def tts(l):
    raw = os.path.join(OUT, "raw", f"{l['i']:03d}.wav")
    if os.path.exists(raw) and not ONLY: return l["i"], "skip"
    body = {"voice_id": vid, "text": glue(l["tts"]), "model": "ssfm-v30", "language": "kor",
            "prompt": {"emotion_preset": "normal", "emotion_intensity": 1.0},
            "output": {"volume": 100, "audio_pitch": 0, "audio_tempo": TEMPO, "audio_format": "wav"}}
    for k in range(3):
        try:
            req = urllib.request.Request("https://api.typecast.ai/v1/text-to-speech", data=json.dumps(body).encode(),
                  headers={"X-API-KEY": key, "Content-Type": "application/json"}, method="POST")
            d = urllib.request.urlopen(req, timeout=180).read()
            open(raw, "wb").write(d); return l["i"], "ok"
        except urllib.error.HTTPError as e:
            msg = f"http {e.code} {e.read()[:150]}"
            if e.code in (400, 401, 402, 403): return l["i"], msg
        except Exception as e:
            msg = str(e)
        time.sleep(2 + k * 3)
    return l["i"], "fail " + msg
todo = [l for l in lines if l["type"] == "line" and (not ONLY or l["i"] in ONLY)]
with cf.ThreadPoolExecutor(4) as ex:
    for i, r in ex.map(tts, todo):
        if r != "skip": print(i, r, flush=True)

# 4) 앞뒤 무음 자르기(-55dB)
for l in todo:
    raw = os.path.join(OUT, "raw", f"{l['i']:03d}.wav"); tr = os.path.join(OUT, "trim", f"{l['i']:03d}.wav")
    if not os.path.exists(raw): continue
    af = ("silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.06,"  # 첫소리 보존(-40dB 는 첫 단어를 뭉갠다)
          "areverse,silenceremove=start_periods=1:start_threshold=-55dB:start_silence=0.08,areverse,"
          "aresample=48000,aformat=channel_layouts=mono")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", af, tr], check=True)
    d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tr],
                             capture_output=True, text=True).stdout)
    l["dur"] = round(d, 3)
# 길이 기록(기존 값 유지)
old = {}
p = os.path.join(OUT, "lines.json")
for l in lines:
    if l["type"] == "line" and "dur" not in l:
        tr = os.path.join(OUT, "trim", f"{l['i']:03d}.wav")
        if os.path.exists(tr):
            l["dur"] = round(float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", tr],
                             capture_output=True, text=True).stdout), 3)
json.dump(lines, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
tot = sum(l.get("dur", 0) for l in lines if l["type"] == "line")
syl = sum(len(re.findall(r"[가-힣0-9]", l["text"])) for l in lines if l["type"] == "line")
print(f"문장 {n} · 말소리 합계 {tot:.1f}초 · 간격 0.1초 포함 약 {(tot + 0.1 * n) / 60:.2f}분 · 분당 {syl / ((tot + 0.1 * n) / 60):.0f}음절")
