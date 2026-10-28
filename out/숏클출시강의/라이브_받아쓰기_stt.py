"""라이브 음성 → 10분 조각 → GROQ whisper-large-v3(verbose_json) → [시작-끝] 줄 단위 전사문."""
import os, sys, json, subprocess, time, requests
sys.path.insert(0, r"C:\Users\TheRose\Desktop\로또의 주식")
from shopping_shorts import config
W = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.join(W, "live.m4a"); CH = 600
dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", SRC], capture_output=True, text=True).stdout)
n = int(dur // CH) + 1
segs = []
for i in range(n):
    out = os.path.join(W, f"c{i:02d}.mp3")
    if not os.path.exists(out):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(i * CH), "-t", str(CH), "-i", SRC, "-ac", "1", "-ar", "16000", "-b:a", "48k", out], check=True)
    cj = out + ".json"
    if not os.path.exists(cj):
        for k in range(4):
            with open(out, "rb") as f:
                r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                                  files={"file": (os.path.basename(out), f, "audio/mpeg")},
                                  data={"model": "whisper-large-v3", "language": "ko", "response_format": "verbose_json"}, timeout=300)
            if r.status_code == 429:
                time.sleep(30 * (k + 1)); continue
            r.raise_for_status(); json.dump(r.json(), open(cj, "w", encoding="utf-8"), ensure_ascii=False); break
    d = json.load(open(cj, encoding="utf-8"))
    for s in d.get("segments", []):
        segs.append((s["start"] + i * CH, s["end"] + i * CH, s["text"].strip()))
    print(f"조각 {i+1}/{n} 완료", flush=True)
fmt = lambda t: f"{int(t//3600)}:{int(t%3600//60):02d}:{int(t%60):02d}"
with open(os.path.join(W, "전사문.txt"), "w", encoding="utf-8") as f:
    for a, b, t in segs:
        f.write(f"[{fmt(a)}] {t}\n")
print("줄", len(segs), "길이", fmt(dur))
