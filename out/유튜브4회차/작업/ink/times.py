"""장면 음성 → 문장별 시작·끝 시각(무음 실측). usage: py ink/times.py s02 [s03 ...]
문장 수 N 이면 가장 긴 쉼 N-1 개를 문장 경계로 본다(글자 수 비율로 검산해 함께 출력)."""
import sys, re, subprocess
from pathlib import Path
W = Path(__file__).resolve().parents[1]
src = (W / "build.py").read_text(encoding="utf-8")
S = eval(src[src.index("SCENES = ") + 9: src.index("]\n", src.index("SCENES = ")) + 1])
T = {s["id"]: s["text"] for s in S}
def sil(p):
    e = subprocess.run(["ffmpeg", "-v", "info", "-i", str(p), "-af", "silencedetect=n=-30dB:d=0.07", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    st = [float(x) for x in re.findall(r"silence_start: ([0-9.]+)", e)]; en = [float(x) for x in re.findall(r"silence_end: ([0-9.]+)", e)]
    d = float(re.search(r"Duration: (\d+):(\d+):([0-9.]+)", e).group(3)) + 60 * int(re.search(r"Duration: (\d+):(\d+)", e).group(2))
    return list(zip(st, en)), d
for sid in sys.argv[1:]:
    sents = [x.strip() for x in re.split(r"(?<=[.?!])\s+", T[sid]) if x.strip()]
    gaps, D = sil(W / "voice" / f"{sid}.mp3")
    head = gaps[0][1] if gaps and gaps[0][0] < 0.05 else 0.0
    inner = [g for g in gaps if g[0] > 0.05 and g[1] < D - 0.05]
    tot = sum(len(x) for x in sents)
    est = [head + (D - head) * sum(len(x) for x in sents[:i]) / tot for i in range(1, len(sents))]
    # DP: 경계 i 마다 쉼 하나(순서 유지) — 비용 = |쉼 끝 - 글자비 추정| - 1.5*쉼 길이
    G, K = inner, len(est); INF = 1e9
    best = [[INF] * (len(G) + 1) for _ in range(K + 1)]; back = {}
    for j in range(len(G) + 1): best[0][j] = 0
    for i in range(1, K + 1):
        for j in range(i, len(G) + 1):
            g = G[j - 1]; c = abs(g[1] - est[i - 1]) - 1.5 * (g[1] - g[0])
            m = min(range(i - 1, j), key=lambda q: best[i - 1][q]) if i > 1 else 0
            v = (best[i - 1][m] if i > 1 else 0) + c
            if v < best[i][j]: best[i][j] = v; back[(i, j)] = m
            if j > i and best[i][j - 1] < best[i][j]: best[i][j] = best[i][j - 1]; back[(i, j)] = back[(i, j - 1)] if (i, j - 1) in back else m; back[("p", i, j)] = j - 1
    # 되짚기
    cut, i, j = [], K, len(G)
    while i > 0:
        while ("p", i, j) in back: j = back[("p", i, j)]
        cut.append(G[j - 1]); j = back[(i, j)]; i -= 1
    cut = cut[::-1]
    starts = [head] + [g[1] for g in cut]; ends = [g[0] for g in cut] + [D]
    tot = sum(len(s) for s in sents); acc = head
    print(f"== {sid} {D:.2f}초 문장 {len(sents)} 쉼 {len(inner)}")
    for i, s in enumerate(sents):
        est = head + (D - head) * sum(len(x) for x in sents[:i]) / tot
        print(f"{starts[i]:6.2f}~{ends[i]:6.2f} (글자비 {est:5.2f}) {s}")
