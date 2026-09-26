# -*- coding: utf-8 -*-
"""장면 골라 지우기 — 프레임 단위 검사 (2026-09-26).

clean_base_lab.py --pick 으로 만든 정본(가짜 업체 = 아래 1/4 검은 띠)을 프레임마다 훑어
"띠가 있는 프레임 = 고른 컷 구간"이 **프레임 하나 어긋남 없이** 맞는지 잰다.
어긋나면 되붙이기가 뒤 장면을 밀었다는 뜻이다(다음 장면 영향).
안 고른 구간은 조립본(mix_raw)과 같은 그림인지도 잰다(평균 절대차).

실행(트랙 폴더):  py shopping_shorts/scripts/partial_clean_frames_check.py --work shopping_shorts/data/mix_jobs/<job>
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import mix_pipeline as mp      # noqa: E402


def _frames_gray(path, w=16, h=16):
    # ★-fps_mode passthrough: 조립본은 시각이 들쭉날쭉해 기본(cfr)으로 뽑으면 프레임이 복제·누락돼
    #   검사기 자신이 1프레임 어긋난다(2026-09-26 실측: 가짜 차이 68). 프레임은 번호 그대로 뽑는다.
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vf", "scale=%d:%d,format=gray" % (w, h),
                          "-fps_mode", "passthrough", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    n = w * h
    return [raw[i:i + n] for i in range(0, len(raw) - n + 1, n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    work = Path(a.work)
    base = json.loads((work / "clean_base.json").read_text(encoding="utf-8"))
    clean = Path(base["path"])
    raw = work / "lab_mix_raw.mp4"      # clean_base_lab.py --pick 이 남긴 되붙이기 전 조립본
    fs, fps, nb = mp._probe_fps_frames(raw)
    nc = mp._probe_fps_frames(clean)[2]
    print("프레임 수: 조립본 %d / 청소본 %d (fps %s)" % (nb, nc, fs))
    want = [False] * nb
    for c in base["cuts"]:
        if c.get("cleaned", True):
            s0 = int(round(float(c["fin"]) * fps)); s1 = min(int(round((float(c["fin"]) + float(c["dur"])) * fps)), nb)
            for i in range(s0, s1):
                want[i] = True
    fc = _frames_gray(clean)
    fr = _frames_gray(raw)
    bad, diff_max, rows, diff_at = 0, 0.0, [], -1
    for i in range(min(len(fc), nb)):
        bottom = fc[i][16 * 12:]                       # 아래 1/4 (16x16 중 4줄)
        band = sum(1 for v in bottom if v < 24) / len(bottom) >= 0.9
        if band != want[i]:
            bad += 1
            rows.append(i)
        if not want[i]:
            d = sum(abs(x - y) for x, y in zip(fc[i], fr[i])) / len(fc[i])
            if d > diff_max:
                diff_at = i
            diff_max = max(diff_max, d)
    print("띠(지움) 기대와 다른 프레임: %d / %d%s" % (bad, nb, (" → 예: %s" % rows[:20]) if rows else ""))
    print("안 고른 프레임의 조립본 대비 최대 평균차(0~255, 재인코딩 잡음 수준이면 정상): %.2f (프레임 %d)" % (diff_max, diff_at))
    print("디코드 프레임 수: 조립본 %d / 청소본 %d" % (len(fr), len(fc)))
    edges = [i for i in range(1, nb) if want[i] != want[i - 1]]
    print("고른 구간 경계 프레임:", edges)


if __name__ == "__main__":
    main()
