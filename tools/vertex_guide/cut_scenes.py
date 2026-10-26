"""안내 영상에서 장면 몇 개를 **프레임 단위로** 빼낸다(관제 255, 2026-10-22 사장님 "1단계는 카드 등록까지, 바로 2단계 셸 열기로").
  py tools/vertex_guide/cut_scenes.py <in.mp4> <out.mp4> <뺄 장면 번호(0부터), 쉼표>
  예) py tools/vertex_guide/cut_scenes.py vertex_guide.mp4 v5.mp4 2,3     # v4 의 2단계 인증 두 장면

시간 상수는 Guide.tsx 와 같다(30fps · INTRO 3.2s=96f · PER 6s=180f · OUTRO 3.5s). 장면은 <Sequence> 로 딱 끊겨
겹침이 없으므로, 장면 구간만 빼고 이으면 그 장면을 빼고 다시 렌더한 것과 같은 그림이다. 무음 영상.
다시 렌더할 때의 장면 목록 주인은 prep_v4.py SCENES — 여기서 뺀 장면은 거기서도 뺀다(둘이 어긋나지 않게).
"""
import subprocess
import sys

FPS, INTRO, PER = 30, 96, 180
src, out, drop = sys.argv[1], sys.argv[2], sorted({int(x) for x in sys.argv[3].split(",") if x.strip()})
keep, prev = [], 0
for i in drop:
    a, b = INTRO + i * PER, INTRO + (i + 1) * PER
    if a > prev:
        keep.append((prev, a))
    prev = b
keep.append((prev, None))
f, parts = [], []
for k, (a, b) in enumerate(keep):
    rng = f"start_frame={a}" + (f":end_frame={b}" if b is not None else "")
    f.append(f"[0:v]trim={rng},setpts=PTS-STARTPTS[p{k}]")
    parts.append(f"[p{k}]")
f.append("".join(parts) + f"concat=n={len(parts)}:v=1:a=0[v]")
subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex", ";".join(f), "-map", "[v]",
                "-c:v", "libx264", "-crf", "26", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-movflags", "+faststart", out], check=True)
print("뺀 장면", drop, "남긴 구간(프레임)", keep, "→", out)
