# -*- coding: utf-8 -*-
"""샥탬 재료 컷이 원본 샷 경계를 넘나 — 컷 [ss, ss+dur] 안에 샷 경계(scene>0.12 시각)가 들어오면 표시 (관제 097, 2026-10-28, 98 #192).

왜: make_plan·hybrid 는 줄 길이(실제 TTS)에 맞춰 컷을 비례로 늘린다 — 샷 여유를 안 봐서 옆 샷이 몇 프레임 섞이거나(#186 ③·#191 ⑤),
다음 컷과 겹쳐 되감김(#192 ⑦)이 났다. 계획 시트는 추정 길이로 그려 이걸 못 잡는다. render --tts-only 뒤 make_plan 을 다시 돌린 재료.json 으로 잰다.

    PYTHONUTF8=1 py tools/calcopy/shark/shot_overrun.py <재료.json> <scenes.txt> [소스 이름 일부]
    → 넘는 컷 'XX i 줄 소스 시작 끝 [안에 든 경계]' · 넘는 컷이 있으면 rc=1
scenes.txt = 줄마다 경계 초(ffmpeg select='gt(scene,0.12)',showinfo 의 pts_time) 또는 한 줄에 공백으로.
"""
import json
import sys


def main() -> int:
    m = json.load(open(sys.argv[1], encoding="utf-8"))
    sc = [float(x) for x in open(sys.argv[2], encoding="utf-8").read().split()]
    only = sys.argv[3] if len(sys.argv) > 3 else None
    bad = 0
    for s in m["shots"]:
        if only and only not in s["src"]:
            continue
        a = float(s["ss"]); b = a + float(s["dur"])
        inside = [round(x, 2) for x in sc if a + 0.04 < x < b - 0.02]
        bad += bool(inside)
        print(("XX " if inside else "ok "), s.get("i"), s["line"], s["src"], round(a, 2), round(b, 3), inside)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
