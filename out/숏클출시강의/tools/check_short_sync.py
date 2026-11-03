"""쇼츠 완성본에서 말 시작 시각 vs 자막 조각 시작 시각 대조(10-30 쇼츠A "자막이랑 영상 안 맞는 구간").
쓰기: py check_short_sync.py <shortX.tsx> <완성본.mp4>   → 0.25초 넘게 어긋난 자막이 있으면 rc=1
tsx 의 LN = [[파일 길이, 뒤 쉼, [[파일 안 시각, 글], ...]], ...] 을 읽어 자막 시작을 계산하고,
완성본 소리의 silencedetect 끝(=말 시작)과 가장 가까운 것을 짝짓는다."""
import re, subprocess, sys

src = open(sys.argv[1], encoding="utf-8").read()
body = src[src.index("const LN"):src.index("];", src.index("const LN"))]
caps, t = [], 0.0
for m in re.finditer(r"\[\s*([\d.]+),\s*([\d.]+),\s*\[(.*?)\]\],", body, re.S):
    d, g = float(m.group(1)), float(m.group(2))
    for tt, txt in re.findall(r"\[([\d.]+),\s*\"((?:[^\"\\]|\\.)*)\"\]", m.group(3)):
        caps.append((t + float(tt), txt))
    t += d + g
log = subprocess.run(["ffmpeg", "-v", "info", "-i", sys.argv[2], "-vn", "-af", "silencedetect=n=-40dB:d=0.1", "-f", "null", "-"],
                     capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
ons = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
bad = 0
for c, txt in caps:
    near = min(ons, key=lambda o: abs(o - c)) if ons else -9
    off = c - near
    mark = "OK" if abs(off) <= 0.25 else "★어긋남"
    bad += mark != "OK"
    print(f"{mark} 자막 {c:6.2f}  말 {near:6.2f}  ({off:+.2f})  {txt}")
print(f"자막 {len(caps)}개 중 어긋남 {bad}")
sys.exit(1 if bad else 0)
