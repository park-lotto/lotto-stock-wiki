# -*- coding: utf-8 -*-
"""완성본 한 장 번쩍임(다른 자리 그림 1프레임) 찾기 — 관제 099.

왜(2026-10-02 관제 077 실측 2683d3703512): 완성본 6.83초(205번)에 같은 영상 21.23초(637번) 그림이 한 장 끼었다.
  편집 화면 미리보기도 같은 좌표를 써서 둘 다 같은 그림이라, 미리보기 vs 완성본 대조(잔상)는 0으로 통과시켰다.
판정(완성본만 본다): 프레임 i 가 앞·뒤 프레임 둘 다와 크게 다르고(한 장짜리 섬),
  그 그림이 영상의 **다른 자리**(앞뒤 FAR 프레임 밖)에 거의 그대로 있으면 = 다른 자리 그림이 새어 들어온 것.
  빠른 손 움직임(흐린 프레임)은 다른 자리에 같은 그림이 없어서 안 걸린다(e9930b0c053b 실측).

  py tools/flash_frames.py <영상.mp4> ...      → 영상마다 [(프레임, 초, 닮은 프레임, 섬 거리, 닮음 거리)]
"""
import sys
from pathlib import Path

import numpy as np

from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parent))
from editor_vs_final_video import flash_frames, FLASH_JUMP_T, FLASH_MATCH_R, FLASH_FAR   # noqa: E402 — 판정 주인


def main(paths):
    from editor_vs_final_video import _frames, _feats
    for p in paths:
        ff = _feats(_frames(Path(p)))
        hits = flash_frames(ff)
        print(Path(p).parent.name or p, len(ff), "프레임 · 번쩍임", [(i, round(i / 30, 2), j, a, b) for i, j, a, b in hits])


if __name__ == "__main__":
    main(sys.argv[1:])
