"""손그림 장면(out.mp4) 위에 실제 완성 영상을 칸에 끼운다 → <장면>/<음성>_av.mp4
usage: py ink/ov.py S07 s07
칸 목록 = <장면>/tiles.json : [[소스, x, y, w, h, 시작초, 끝초, 소스 시작초], ...]  (소스 = build.py SRC 이름, 위 띠 crop 비율 적용)
칸 좌표는 scene.js 의 폰 테두리 안쪽과 같아야 한다(scene.js 가 같은 숫자를 쓴다)."""
import sys, json, subprocess
from pathlib import Path
H = Path(__file__).resolve().parent; W = H.parent
src = (W / "build.py").read_text(encoding="utf-8")
SRC = eval(src[src.index("SRC = {") + 6: src.index("}\n", src.index("SRC = {")) + 1])
D, V = sys.argv[1], sys.argv[2]
tiles = json.loads((H / D / "tiles.json").read_text(encoding="utf-8"))
inp = ["-i", str(H / D / "out.mp4")]; fc = []; last = "0:v"
for k, (name, x, y, w, h, a, b, ss) in enumerate(tiles):
    crop = SRC[name][1]
    inp += ["-ss", str(ss), "-t", str(b - a + 0.5), "-i", str(W / "src" / f"{name}.mp4")]
    i = k + 1
    fc.append(f"[{i}:v]crop=iw:ih*{1 - crop:.3f}:0:ih*{crop:.3f},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30,setpts=PTS-STARTPTS+{a}/TB[t{i}]")
    fc.append(f"[{last}][t{i}]overlay={x}:{y}:enable='between(t,{a},{b})':eof_action=pass[o{i}]"); last = f"o{i}"
out = H / D / f"{V}_av.mp4"
cmd = ["ffmpeg", "-v", "error", "-y", *inp, "-i", str(W / "voice" / f"{V}.mp3"), "-filter_complex", ";".join(fc),
       "-map", f"[{last}]", "-map", f"{len(tiles) + 1}:a", "-c:v", "libx264", "-threads", "4", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", str(out)]
subprocess.run(cmd, check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out), "-vf", "fps=1,scale=480:-1,tile=6x7", "-frames:v", "1", str(H / D / "sheet.jpg")], check=True)
print(D, "끝", out)
