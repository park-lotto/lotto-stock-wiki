# -*- coding: utf-8 -*-
"""벤치(두유노홈디노) '한 동작 이어서 반복' 실측 — 컷끼리 같은 원본 장면(같은 촬영 줄기)인가를 그림 상관으로 잰다(관제 097, 2026-10-26 잇썸홈판 결정 '가').

    PYTHONUTF8=1 py channel/homedesignnote/preset/repeat_measure.py [--media <media.json>] [--out <json>]

컷 경계 = bench_diff media.json 의 cut_at(kal_analyze.media_of 와 같은 자). 컷마다 프레임 4장(10·35·60·85%)을 회색 36×64 로 줄이고
자막 띠(y 500~1050)·워터마크(y 1400~1500)를 빼서 다른 컷의 프레임과 피어슨 상관 최대값을 잰다.
  같은 줄기(same take) = 상관 ≥ TAKE(같은 방·같은 각도·조금 다른 순간)  · 같은 그림(repeat) = 상관 ≥ SAME(거의 같은 프레임 — 같은 구간을 다시 보여 줌)
문턱은 이 도구가 남기는 짝 시트(<out>_pairs.jpg)를 눈으로 보고 정한다(판정 = Claude 눈).
반환 = 편마다 이웃 컷 짝(k,k+1)·떨어진 짝(사이 컷 ≥1)의 같은 줄기·같은 그림 수와 떨어진 짝의 화면 시간 간격."""
import argparse
import json
import subprocess
from pathlib import Path

import numpy as np

MP4 = Path("C:/숏템_칼카피/homedesignnote/mp4")
IDS = ["DCXQjaWcZ-g", "_QqLEH4qlFQ", "EINoAh8C9rQ", "SU9YofB1IoI", "WTgQPFfdSOQ", "iiBUscncqIk"]
W, H = 36, 64


def frames(mp4: Path, ts: list[float]) -> list[np.ndarray]:
    out = []
    keep = np.ones(H, bool)
    keep[int(500 / 30):int(1050 / 30)] = False
    keep[int(1400 / 30):int(1500 / 30)] = False
    for t in ts:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(mp4), "-frames:v", "1", "-vf", f"scale={W}:{H},format=gray",
                              "-f", "rawvideo", "-"], capture_output=True, stdin=subprocess.DEVNULL).stdout
        a = np.frombuffer(raw[:W * H], np.uint8).reshape(H, W).astype(np.float32)[keep].ravel()
        out.append((a - a.mean()) / (a.std() + 1e-6))
    return out


def corr(A, B) -> float:
    return max(float(np.mean(a * b)) for a in A for b in B)


def measure(vid: str, cut_at: list[float], dur: float) -> dict:
    b = [0.0] + list(cut_at) + [dur]
    spans = [(b[i], b[i + 1]) for i in range(len(b) - 1) if b[i + 1] - b[i] > 0.12]
    F = [frames(MP4 / f"{vid}.mp4", [a + (z - a) * f for f in (0.1, 0.35, 0.6, 0.85)]) for a, z in spans]
    pairs = []
    for i in range(len(spans)):
        for j in range(i + 1, len(spans)):
            pairs.append({"i": i, "j": j, "between": j - i - 1, "gap_s": round(spans[j][0] - spans[i][1], 2), "c": round(corr(F[i], F[j]), 3),
                          "ti": [round(x, 2) for x in spans[i]], "tj": [round(x, 2) for x in spans[j]]})
    return {"id": vid, "n_cuts": len(spans), "pairs": pairs}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    M = json.loads(Path(a.media).read_text(encoding="utf-8"))
    res = [measure(v, M[f"homedesignnote/{v}"]["cut_at"], M[f"homedesignnote/{v}"]["duration"]) for v in IDS]
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in res:
        adj = [p for p in r["pairs"] if p["between"] == 0]
        far = [p for p in r["pairs"] if p["between"] >= 1]
        print(r["id"], "컷", r["n_cuts"], "이웃 상관 분포", sorted(p["c"] for p in adj)[::max(1, len(adj) // 8)],
              "떨어진 짝 상관≥0.8", [(p["i"], p["j"], p["gap_s"], p["c"]) for p in far if p["c"] >= 0.8][:12])
