"""벤치영상 정답지 재료 뽑기(관제 170) — 쇼츠 URL → 자막 전문 + 1초 장면 시트.
사용: py tools/bench_answers/bench_fetch.py <url> <출력폴더>
나온 sheet.jpg·script.txt 를 보고 정답지(answers.md)에 분석을 적는다. AI 분석 결과를 이 정답지와 대조한다."""
import os, re, subprocess, sys
url, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
env = dict(os.environ, PYTHONIOENCODING="utf-8")
meta = subprocess.run(["yt-dlp", "--encoding", "utf-8", "-f", "mp4[height<=720]/best", "--write-auto-subs", "--write-subs",
                       "--sub-langs", "ko.*", "-o", os.path.join(out, "v.%(ext)s"), "--no-simulate",
                       "--print", "%(title)s|%(view_count)s|%(duration)s|%(channel)s", url],
                      capture_output=True, text=True, encoding="utf-8", env=env).stdout.strip()
vtt = next((os.path.join(out, f) for f in sorted(os.listdir(out)) if f.endswith(".vtt")), None)
lines, seen = [], set()
for ln in open(vtt, encoding="utf-8") if vtt else []:
    ln = re.sub(r"<[^>]+>", "", ln).strip()
    if not ln or "-->" in ln or ln.startswith(("WEBVTT", "Kind", "Language")) or ln in seen:
        continue
    seen.add(ln); lines.append(ln)
open(os.path.join(out, "script.txt"), "w", encoding="utf-8").write(meta + "\n" + " ".join(lines))
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", os.path.join(out, "v.mp4"),
                "-vf", "fps=1,scale=180:-1,tile=10x4", "-frames:v", "1", os.path.join(out, "sheet.jpg")])
print(meta)
