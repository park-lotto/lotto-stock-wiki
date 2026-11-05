# -*- coding: utf-8 -*-
"""2판 — 원본 LcQv9yOh3Wc 안의 보관통 화면만으로 뒤 구간을 짜기 위한 '이어 붙인·늦춘 조각' 표(관제 097, 2026-10-17).

왜: 제품 같은 모델을 끝내 못 찾았다(제품확정.md §4) → 다른 회사 사진·남의 방송 짤 금지 → 원본 보관통 화면만 쓴다.
    원본 보관통 화면은 776~809초 안에 몇 초뿐이고, 앞 구간(원음 780.62~783.84 · 788.18~793.66)과 ±3초를 띄워야 해서(B13)
    쓸 수 있는 건 776.20~777.62 · 798.2~808.47 뿐 → 짧은 샷은 늦춰서(움직임 보간) 줄 길이를 채운다.
조각 = (소스 시작, 끝, 늦춤 배수) 이어 붙임. 원본 시각은 B13 검사(check_overlap)에서 이 표로 되돌려 잰다(판단 주인 = DERIVED).
    PYTHONUTF8=1 py channel/yanshottem/하이브리드_한고은/재료/make_derived.py
"""
import os
import subprocess
from pathlib import Path

SRC = Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/src/hge_LcQv9yOh3Wc.mp4")
OUT = {"its": Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/잇썸홈판/src"),
       "jae": Path("C:/숏템_칼카피/yanshottem/하이브리드_한고은/재미썸홈판/src")}
# 이름: (판, [(시작, 끝, 늦춤배수), ...], 화면)
DERIVED = {
    "d_AB.mp4": ("its", [(776.20, 776.68, 1.7), (777.12, 777.62, 1.7)], "빈 스텐 겉통 근접 → 구멍 뚫린 채반을 기울여 보여 줌(사이 흐린 팔 776.70~777.10 뺌)"),
    "d_G.mp4": ("its", [(803.85, 805.05, 1.0)], "수돗물 아래 채반째 씻기(원본 그대로)"),
    "d_H.mp4": ("its", [(805.10, 805.85, 1.6)], "채반을 들자 구멍으로 물이 빠짐(1.6배 늦춤, 805.85 뒤 흐림 뺌)"),
    "d_I.mp4#its": ("its", [(807.05, 808.45, 1.3)], "겉통에 얹은 채반 속 윤기 나는 상추(1.3배 늦춤) — 원본 빨간 꾸밈 글 상자 흐림"),
    "d_FR.mp4#its": ("its", [(738.00, 740.15, 1.15)], "냉장고 문 안 → 채소 봉지를 꺼내 듦(1.15배 늦춤, 740.21 얼굴 샷 전에서 끊음)"),
    "d_A.mp4": ("jae", [(776.20, 776.68, 3.6)], "빈 스텐 겉통 근접(거의 정지 샷)"),
    "d_B.mp4": ("jae", [(776.95, 777.62, 3.0)], "구멍 뚫린 채반을 기울여 보여 주는 손"),
    "d_FR.mp4#jae": ("jae", [(738.30, 740.15, 1.65)], "냉장고 문 안 → 채소 봉지를 꺼내 듦(1.65배 늦춤, 앞 뒷머리·740.21 얼굴 샷 빼고)"),
    "d_GH.mp4#jae": ("jae", [(803.85, 804.55, 1.0), (805.10, 805.85, 1.2)], "수돗물 아래 채반 → 채반을 들자 물이 빠짐"),
    "d_I.mp4": ("jae", [(807.05, 808.45, 1.3)], "겉통에 얹은 채반 속 윤기 나는 상추(위 빨간 꾸밈 글은 크롭 밖)"),
}


def orig_windows(name: str) -> list:
    """B13 검사용 — 조각 이름(같은 이름이 두 판에 있으면 '이름#판') → 원본 구간들."""
    if name in DERIVED:
        return [(a, b) for a, b, _ in DERIVED[name][1]]
    for k, (_, segs, _) in DERIVED.items():
        if k.split("#")[0] == name:
            return [(a, b) for a, b, _ in segs]
    return []


BLUR = {"d_I.mp4#its": (540, 180, 880, 200)}   # 남의 꾸밈 글 '채소에 윤기가 좔좔'+화살표(x,y,w,h) — 9:16 크롭(확대 ≤2.3)으로는 못 빼서, 바로 아래 띠를 뒤집어 흐려 덮는다


def make(name, osegs, out):
    lo = min(a for a, _, _ in osegs) - 1
    segs = [(round(a - lo, 3), round(b - lo, 3), f) for a, b, f in osegs]   # 입력 -ss lo 뒤 시각
    fc, labs = [], []
    for i, (a, b, f) in enumerate(segs):
        v = f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS"
        if f != 1.0:
            v += f",setpts={f}*PTS,minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:vsbmc=1"
        else:
            v += ",fps=30"
        fc.append(v + f",format=yuv420p,setsar=1[v{i}]")
        labs.append(f"[v{i}]")
    if name in BLUR:
        x, y, w, h = BLUR[name]
        fc.append("".join(labs) + f"concat=n={len(segs)}:v=1:a=0[c];[c]split[c1][c2];[c2]crop={w}:{h}:{x}:{y + h},vflip,boxblur=30:2[bl];[c1][bl]overlay={x}:{y}[o]")
    else:
        fc.append("".join(labs) + f"concat=n={len(segs)}:v=1:a=0[o]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{lo:.3f}", "-t", f"{max(b for _, b, _ in segs) + 1:.2f}", "-i", str(SRC),
                    "-filter_complex", ";".join(fc), "-map", "[o]", "-an",
                    "-c:v", "libx264", "-crf", "12", "-preset", "medium", "-r", "30", str(out)], check=True)


def main():
    for d in OUT.values():
        d.mkdir(parents=True, exist_ok=True)
        h = d / SRC.name
        if not h.exists():
            os.link(SRC, h)   # 재료 담당 원본 — 하드링크(읽기만)
    for k, (pan, segs, _) in DERIVED.items():
        out = OUT[pan] / k.split("#")[0]
        make(k, segs, out)
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                                 capture_output=True, text=True).stdout)
        print(pan, out.name, round(d, 3), segs)


if __name__ == "__main__":
    main()
