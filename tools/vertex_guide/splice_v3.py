"""새 장면만 렌더한 mp4(인트로+장면들+아웃트로)에서 장면 구간만 떼어 v2 영상의 지정 위치에 끼운다.
  py tools/vertex_guide/splice_v3.py <v2.mp4> <new.mp4> <scenes.json(새 장면, after 포함)> <out.mp4>
시간 상수는 Guide.tsx와 같다(INTRO 3.2s · PER 6s · OUTRO 3.5s). 무음 영상이라 소리는 없다.
"""
import sys, json, subprocess
INTRO, PER = 3.2, 6.0
v2, new, sj, out = sys.argv[1:5]
scenes = json.load(open(sj, encoding="utf-8"))
# v2에서 자를 지점: after=k → v2 시각 INTRO + (k+1)*PER
cuts = [INTRO + (s["after"] + 1) * PER for s in scenes]
assert cuts == sorted(cuts)
parts, prev = [], 0.0
f = []
idx = 0
for i, (s, t) in enumerate(zip(scenes, cuts)):
    f.append(f"[0:v]trim=start={prev}:end={t},setpts=PTS-STARTPTS[a{i}]")
    ns, ne = INTRO + i * PER, INTRO + (i + 1) * PER
    f.append(f"[1:v]trim=start={ns}:end={ne},setpts=PTS-STARTPTS[b{i}]")
    parts += [f"[a{i}]", f"[b{i}]"]; prev = t
f.append(f"[0:v]trim=start={prev},setpts=PTS-STARTPTS[tail]"); parts.append("[tail]")
f.append("".join(parts) + f"concat=n={len(parts)}:v=1:a=0[v]")
cmd = ["ffmpeg", "-y", "-v", "error", "-i", v2, "-i", new, "-filter_complex", ";".join(f), "-map", "[v]",
       "-c:v", "libx264", "-crf", "26", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
subprocess.run(cmd, check=True)
print("spliced →", out, "cuts(v2 s):", cuts)
