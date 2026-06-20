"""S07 재전사 → 단어 저장 + 문장경계 청킹 (싱크 드리프트 수정용)"""
import sys, json, os, subprocess, re
sys.stdout.reconfigure(encoding='utf-8')
import whisper

BASE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(BASE, "S07_연동", "S7 녹화+음석.mp4")
WAV = os.path.join(BASE, "_audio", "S07_retx.wav")
WORDS_F = os.path.join(BASE, "_audio", "S07_words.json")
OUT = os.path.join(BASE, "_audio", "S07_subs_chunked.json")
FPS = 30

if os.path.exists(WORDS_F):
    words = json.load(open(WORDS_F, encoding="utf-8"))
    print(f"[S07] 단어 캐시 로드 {len(words)}개")
else:
    subprocess.run(["ffmpeg","-y","-i",SRC,"-vn","-ac","1","-ar","16000","-acodec","pcm_s16le",WAV],
                   capture_output=True, check=False)
    print("[S07] whisper medium + word_timestamps ...")
    model = whisper.load_model("medium")
    r = model.transcribe(WAV, language="ko", word_timestamps=True,
                         initial_prompt="클로드, Play MCP, 커넥터, 코워크, 카카오톡, 네이버 검색")
    os.remove(WAV)
    words = [{"t": w["word"].strip(), "s": w["start"], "e": w["end"]}
             for s in r["segments"] for w in s.get("words", []) if w["word"].strip()]
    json.dump(words, open(WORDS_F,"w",encoding="utf-8"), ensure_ascii=False)
    print(f"[S07] 단어 {len(words)}개 저장")

# 문장경계 청킹: 정지(gap)≥0.24s 우선 분할 / 종결어미 후 분할 / 길이>28 강제
GAP, MAXCH = 0.24, 28
ENDERS = ("다", "요", "고", "죠", "까", "데", "을", "서")  # 한국어 어절 종결 힌트
def is_end(tok):
    t = tok.rstrip(".,?!")
    return t.endswith(("됩니다","습니다","건데요","보세요","해볼게요","보겠습니다","마쳤습니다",
                       "따라오셨습니다","나옵니다","뜹니다","보입니다","겁니다","있네요","있죠",
                       "되고","있고","오시고요","눌러서","눌러주시고","계속하기","중입니다"))

chunks, cur = [], None
for i, w in enumerate(words):
    if cur is None:
        cur = {"text": w["t"], "s": w["s"], "e": w["e"]}; continue
    gap = w["s"] - cur["e"]
    cand = (cur["text"] + " " + w["t"]).strip()
    brk = gap >= GAP or len(cand) > MAXCH or (is_end(cur["text"].split()[-1]) and len(cur["text"]) >= 8)
    if brk:
        chunks.append(cur); cur = {"text": w["t"], "s": w["s"], "e": w["e"]}
    else:
        cur["text"] = cand; cur["e"] = w["e"]
if cur: chunks.append(cur)

out = [{"from": round(c["s"]*FPS), "to": round(c["e"]*FPS),
        "s": round(c["s"],2), "e": round(c["e"],2), "text": c["text"]} for c in chunks]
json.dump({"scene":"S07","fps":FPS,"chunks":out},
          open(OUT,"w",encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"[S07] {len(out)} 청크")
for c in out:
    print(f"  {{ from: {c['from']:4d}, to: {c['to']:4d}, text: '{c['text']}' }},")
