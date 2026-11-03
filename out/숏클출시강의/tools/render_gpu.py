"""리모션 렌더를 GPU 인코딩으로(10-30 사장님 "지피유를 놀리고 있는데" — 리모션 내장 ffmpeg 엔 nvenc 가 없다).
쓰기: py render_gpu.py <가편집 폴더> <src/X.tsx> <컴포지션ID> <out.mp4> [--concurrency 6]
1) 리모션 → ProRes HQ 중간본(--gl=angle: 크롬 그리기를 GPU 로) 2) 시스템 ffmpeg h264_nvenc 로 최종 인코딩.
단계별 걸린 초를 찍는다(다음 렌더와 비교용)."""
import os, subprocess, sys, time

W, src, cid, out = sys.argv[1:5]
conc = sys.argv[sys.argv.index("--concurrency") + 1] if "--concurrency" in sys.argv else "6"
mid = os.path.splitext(out)[0] + "_mid.mov"
t0 = time.time()
subprocess.run(["npx", "remotion", "render", src, cid, mid, "--codec=prores", "--prores-profile=hq", "--gl=angle",
                f"--concurrency={conc}", "--log=error"], cwd=W, check=True, shell=True)
t1 = time.time()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", mid, "-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out], cwd=W, check=True)
t2 = time.time()
os.remove(os.path.join(W, mid) if not os.path.isabs(mid) else mid)
print(f"렌더(그리기) {t1 - t0:.0f}초 · GPU 인코딩 {t2 - t1:.0f}초 · {out}")
