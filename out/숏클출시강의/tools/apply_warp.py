"""조각 tsx 의 장면 시각 숫자를 새 음성 시각으로 옮긴다(splice_tts.py 가 남긴 public/warp1030.json 꺾은선).

쓰기: py apply_warp.py <tsx> <장면번호> [--from 줄] [--to 줄] [--check]
  소수점 있는 숫자(예 26.94)만 바꾼다 — 정수(글자 크기·프레임)는 그대로. 장면이 밀리기 시작한 시각보다 작은 숫자는 그대로라
  0.95·1.25 같은 꾸밈 값은 안 건드린다. --from/--to 로 그 장면을 쓰는 줄 범위만 바꿀 수 있다.
  바뀐 줄을 모두 찍는다(눈으로 확인). 원본은 <tsx>.pre1030 으로 한 번만 남긴다.
"""
import json, os, re, shutil, sys


def warp(k, t):
    for i in range(len(k) - 1, 0, -1):
        (a0, b0), (a1, b1) = k[i - 1], k[i]
        if t >= a0 and (t < a1 or i == len(k) - 1):
            if a1 == a0:
                continue
            return b0 + (t - a0) * (b1 - b0) / (a1 - a0)
    return t


def main():
    p, sid = sys.argv[1], sys.argv[2]
    lo = int(sys.argv[sys.argv.index("--from") + 1]) if "--from" in sys.argv else 1
    hi = int(sys.argv[sys.argv.index("--to") + 1]) if "--to" in sys.argv else 10 ** 9
    W = json.load(open(os.path.join(os.path.dirname(p), "..", "public", "warp1030.json"), encoding="utf-8"))[sid]
    first = next(a for (a, b), (c, d) in zip(W, W[1:]) if abs((d - b) - (c - a)) > 1e-3 or c == a)  # 처음 밀리기 시작한 옛 시각
    if not os.path.exists(p + ".pre1030"):
        shutil.copy(p, p + ".pre1030")
    lines = open(p + ".pre1030", encoding="utf-8").read().split("\n")
    out = []
    for n, line in enumerate(lines, 1):
        if lo <= n <= hi:
            def rep(m):
                v = float(m.group(0))
                return m.group(0) if v < first else f"{warp(W, v):.2f}"
            new = re.sub(r"(?<![\w.])\d+\.\d+(?![\w.])", rep, line)
            if new != line:
                print(f"{n}: {line.strip()[:110]}\n  → {new.strip()[:110]}")
            line = new
        out.append(line)
    if "--check" not in sys.argv:
        open(p, "w", encoding="utf-8").write("\n".join(out))


main()
