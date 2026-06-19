"""인트로/아웃트로 Whisper 추출 → _audio/{INTRO,OUTRO}_timestamps.json"""
import sys, json, os, subprocess, time
sys.stdout.reconfigure(encoding='utf-8')
import whisper

BASE = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE, "_audio")
FPS = 30

TARGETS = [
    ("INTRO", os.path.join(BASE, "01_veo_intro", "intro.mp4")),
    ("OUTRO", os.path.join(BASE, "99_veo_outro", "outro.mp4")),
]

def extract(src, wav):
    subprocess.run(["ffmpeg","-y","-i",src,"-vn","-ac","1","-ar","16000","-acodec","pcm_s16le",wav],
                   capture_output=True, text=True, check=True)

model = whisper.load_model("small")
for name, src in TARGETS:
    if not os.path.exists(src):
        print(f"[{name}] 파일 없음: {src}"); continue
    wav = os.path.join(AUDIO_DIR, f"{name}_temp.wav")
    print(f"[{name}] 추출+분석...")
    extract(src, wav)
    t0 = time.time()
    r = model.transcribe(wav, language="ko", word_timestamps=False)
    segs = r["segments"]
    out = {
        "scene": name, "fps": FPS,
        "total_frames": round(segs[-1]["end"]*FPS) if segs else 0,
        "segments": [
            {"index": i, "text": s["text"].strip(),
             "start_frame": round(s["start"]*FPS), "end_frame": round(s["end"]*FPS),
             "start_sec": round(s["start"],2), "end_sec": round(s["end"],2)}
            for i, s in enumerate(segs)
        ],
    }
    with open(os.path.join(AUDIO_DIR, f"{name}_timestamps.json"), "w", encoding="utf-8") as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    os.remove(wav)
    print(f"[{name}] {len(segs)}세그 / {out['total_frames']}f / {time.time()-t0:.0f}s")
print("완료")
