# 대본(md) → 문장 목록(lines.json) → 타입캐스트 녹음 → 앞뒤 무음 정리
# 사용: python -X utf8 tts.py <대본.md> <출력폴더> [--voice Piljae] [--tempo 1.2] [--only 3,7] [--parse-only]
import json, os, re, sys, time, subprocess, urllib.request, concurrent.futures as cf
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

if len(sys.argv) < 3 or sys.argv[1].startswith("-") or sys.argv[2].startswith("-"):
    # 출력폴더 자리에 옵션(--parse-only 등)을 넣으면 그 이름의 폴더로 유료 녹음이 돌던 사고(11-07, 347줄)를 막는다
    sys.exit("사용: narrate.py <대본.md> <출력폴더> [옵션] — 대본·출력폴더는 옵션보다 먼저 적는다")
SCRIPT, OUT = sys.argv[1], sys.argv[2]
args = sys.argv[3:]
def opt(name, default):
    return args[args.index(name) + 1] if name in args else default
VOICE = opt("--voice", "Piljae"); TEMPO = float(opt("--tempo", "1.2"))
ONLY = set(int(x) for x in opt("--only", "").split(",") if x)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "steps"))
from textglue import glue
from numread import say as yomi
import keys
# 소리 늘임은 판 칸(voice_stretch)이 정한다. 설정의 주인 load_cfg 를 그대로 부른다(작업 폴더 = 출력폴더의 위, SHORCL_WORK 가 있으면 그것)
os.environ.setdefault("SHORCL_WORK", os.path.dirname(os.path.abspath(OUT)))
sys.path.insert(0, HERE)
from studio.cfg import load_cfg
_CFG = load_cfg(); STRETCH = float(_CFG.get("voice_stretch", 1.0))
print(f"판 {_CFG.get('plate') or '기본'} · voice_stretch {STRETCH}", flush=True)
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
_lp = os.path.join(OUT, "lines.json")
_kept = {x["text"]: x["tts"] for x in json.load(open(_lp, encoding="utf-8")) if x.get("tts")} if os.path.exists(_lp) else {}
for l in lines:   # 손으로 바꾼 tts 칸(숫자한글읽기)은 같은 문장이면 그대로 둔다
    if l["type"] == "line": l["tts"] = _kept.get(l["text"]) or yomi(l["text"])
json.dump(lines, open(os.path.join(OUT, "lines.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if "--parse-only" in args:
    print(f"문장 목록만 만듦: {os.path.join(OUT, 'lines.json')}"); sys.exit(0)
left = [(l["i"], l["tts"]) for l in lines if l["type"] == "line" and re.search(r"[0-9%~/A-Za-z]", l["tts"])]
if left:  # 숫자·기호는 숫자한글읽기_지침.md 대로 tts 칸을 한글로 먼저 바꿔야 한다
    for i, t in left: print("숫자 남음", i, t)
    sys.exit("tts 칸에 숫자·기호가 남아 있어 멈춤")

# 3) TTS
key = keys.get("typecast")
vid = {v["voice_name"]: v["voice_id"] for v in json.load(open(os.path.join(HERE, "voices.json"), encoding="utf-8"))}[VOICE]
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
          + (f"atempo={STRETCH}," if STRETCH != 1.0 else "") +   # 판의 말속도 맞춤(1.0 이면 필터가 예전과 같다)
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
