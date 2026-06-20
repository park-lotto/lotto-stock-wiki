"""S02 재전사 → 단어 저장 + 문장경계 청킹 + SUBS_final + timestamps 생성"""
import sys, json, os, subprocess, re
sys.stdout.reconfigure(encoding='utf-8')
import whisper

BASE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(BASE, "S02_페인포인트", "s2 녹화+음성.mp4")
WAV  = os.path.join(BASE, "_audio", "S02_retx.wav")
WORDS_F  = os.path.join(BASE, "_audio", "S02_words.json")
SUBS_F   = os.path.join(BASE, "_audio", "S02_SUBS_final.json")
TS_F     = os.path.join(BASE, "_audio", "S02_timestamps.json")
FPS = 30

# ── 1. Whisper 재전사 (캐시 있으면 스킵) ─────────────────────────────────────
if os.path.exists(WORDS_F):
    words = json.load(open(WORDS_F, encoding="utf-8"))
    print(f"[S02] 단어 캐시 로드: {len(words)}개")
else:
    print("[S02] ffmpeg: WAV 추출 중...")
    subprocess.run(
        ["ffmpeg","-y","-i",SRC,"-vn","-ac","1","-ar","16000","-acodec","pcm_s16le",WAV],
        capture_output=True, check=False
    )
    print("[S02] whisper medium + word_timestamps 시작...")
    model = whisper.load_model("medium")
    r = model.transcribe(
        WAV, language="ko", word_timestamps=True,
        initial_prompt="클로드, 주식, 아침 브리핑, 뇌동매매, 정보수집, 카카오톡, 텔레그램, 코스피"
    )
    os.remove(WAV)
    words = [
        {"t": w["word"].strip(), "s": w["start"], "e": w["end"]}
        for s in r["segments"]
        for w in s.get("words", [])
        if w["word"].strip()
    ]
    json.dump(words, open(WORDS_F,"w",encoding="utf-8"), ensure_ascii=False)
    print(f"[S02] 단어 {len(words)}개 저장 → S02_words.json")

# ── 2. 문장경계 청킹 ──────────────────────────────────────────────────────────
GAP   = 0.30   # 정지 기준 (초)
MAXCH = 28     # 최대 자 수

def is_end(tok):
    t = tok.rstrip(".,?!")
    return t.endswith((
        "됩니다","습니다","건데요","보세요","해볼게요","보겠습니다","마쳤습니다",
        "나옵니다","뜹니다","보입니다","겁니다","있네요","있죠","있고","되고",
        "오시고요","중입니다","됩니다","거든요","이에요","이죠","이다","했다",
        "한다","한거다","한거야","그렇다","맞다","없다","된다","간다","온다",
        "이야","거야","거죠","겠죠","이죠","잖아","잖아요","니다","하다",
        "되게","시죠",
    ))

chunks, cur = [], None
for w in words:
    if cur is None:
        cur = {"text": w["t"], "s": w["s"], "e": w["e"]}
        continue
    gap  = w["s"] - cur["e"]
    cand = (cur["text"] + " " + w["t"]).strip()
    last_word = cur["text"].split()[-1]
    brk = (
        gap >= GAP
        or len(cand) > MAXCH
        or (is_end(last_word) and len(cur["text"]) >= 8)
    )
    if brk:
        chunks.append(cur)
        cur = {"text": w["t"], "s": w["s"], "e": w["e"]}
    else:
        cur["text"] = cand
        cur["e"]    = w["e"]
if cur:
    chunks.append(cur)

# ── 3. accent 추출 (핵심 단어 1개) ───────────────────────────────────────────
KEYWORDS = [
    "뇌동매매","코스피","텔레그램","카카오톡","브리핑","정보수집","클로드",
    "주식","시황","선물","시장","매매","공시","뉴스","알림","알람","자동","분석",
    "수익","손실","실시간","정보","데이터","구독","페인포인트","문제","해결",
    "시간","날","하루","아침","저녁","오전","오후","밤","새벽","항상","매일",
]

def pick_accent(text):
    for kw in KEYWORDS:
        if kw in text:
            return kw
    # 4자 이상 단어 중 첫 번째
    tokens = text.split()
    for t in tokens:
        clean = t.rstrip(".,?!은는이가을를의도에서로부터까지")
        if len(clean) >= 4:
            return clean
    return ""

# ── 4. SUBS_final 저장 ────────────────────────────────────────────────────────
subs = []
for c in chunks:
    accent = pick_accent(c["text"])
    subs.append({
        "from":   round(c["s"] * FPS),
        "to":     round(c["e"] * FPS),
        "text":   c["text"],
        "accent": accent,
    })

json.dump(subs, open(SUBS_F,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[S02] SUBS_final: {len(subs)} 라인 → S02_SUBS_final.json")

# ── 5. timestamps.json 저장 ───────────────────────────────────────────────────
last_e      = words[-1]["e"] if words else 0
total_frames = round(last_e * FPS)

segments = []
for i, c in enumerate(chunks):
    segments.append({
        "index":       i + 1,
        "text":        c["text"],
        "start_sec":   round(c["s"], 3),
        "end_sec":     round(c["e"], 3),
        "start_frame": round(c["s"] * FPS),
        "end_frame":   round(c["e"] * FPS),
    })

ts = {
    "scene":       "S02",
    "source_file": "s2 녹화+음성.mp4",
    "total_sec":   round(last_e, 3),
    "total_frames": total_frames,
    "fps":         FPS,
    "segments":    segments,
}
json.dump(ts, open(TS_F,"w",encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"[S02] timestamps: total_frames={total_frames} ({round(last_e,1)}초) → S02_timestamps.json")

# ── 6. TSX 붙여넣기용 출력 ────────────────────────────────────────────────────
print(f"\n총 {len(subs)} 라인 / total_frames = {total_frames}\n")
print("const SUBS = [")
for s in subs:
    acc = s['accent'].replace("'", "\\'")
    txt = s['text'].replace("'", "\\'")
    print(f"  {{ from: {s['from']:4d}, to: {s['to']:4d}, text: '{txt}', accent: '{acc}' }},")
print("];")
