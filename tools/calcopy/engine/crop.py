"""crop — 엔진 크롭 문자열·검사 한 곳(표 #71·#219, Jev 뿌리 0.91·증명 0.81 / 해결 0.81·위험 0.35 · 11-06).

yuv420 영상에 ffmpeg crop 을 exact 없이 걸면 홀수 오프셋·크기를 **오류 없이** 짝수로 내린다.
실측(11-06 스냅봤니 fFhPI-9EmWc, crop=1080:1398:0:521): 그냥 crop = 정답보다 1px 위(밀어 맞추면 오차 0.0) / exact=1 = 오차 0.05.
홀수 크기는 출력 자체가 줄어든다(301x301 → 300x300). 뜯기 창도 실제로 홀수다(스냅봤니 window [0,521,1080,1399]).
bench/probe.frames·grab 은 format=rgb24 를 먼저 걸어 안전하다 — 그 밖에서 crop 을 적을 때 이 함수를 부른다.
"""
from __future__ import annotations

import numpy as np


def crop_vf(box, exact: bool = True) -> str:
    """box = [x, y, w, h] → ffmpeg crop 필터. exact=True 면 홀수 오프셋·크기를 그대로 지킨다."""
    x, y, w, h = (int(v) for v in box)
    return f"crop={w}:{h}:{x}:{y}" + (":exact=1" if exact else "")


def check_crop(box, src_wh=None) -> list[str]:
    """크롭 상자 검사 — 사유 목록(빈 목록 = 문제 없음). exact 없이 걸면 1px 밀리는 홀수 오프셋·줄어드는 홀수 크기·원본 밖."""
    x, y, w, h = (int(v) for v in box)
    why = []
    if x % 2 or y % 2:
        why.append(f"홀수 오프셋 x={x} y={y} — exact 없이 걸면 짝수로 내려 1px 밀림")
    if w % 2 or h % 2:
        why.append(f"홀수 크기 {w}x{h} — exact 없이 걸면 1px 줄어듦")
    if src_wh and (x < 0 or y < 0 or x + w > src_wh[0] or y + h > src_wh[1]):
        why.append(f"원본 {src_wh[0]}x{src_wh[1]} 밖 상자 {box}")
    return why


def row_shift(a: np.ndarray, truth: np.ndarray, span: int = 3) -> int:
    """결과물 검사용 — a 를 몇 줄 밀어야 truth 와 가장 같나(0 이 아니면 밀림 · -1 = a 가 한 줄 위에서 잘렸다). 회색 2차원 배열."""
    best, err = 0, None
    for s in range(-span, span + 1):
        e = float(np.abs(np.roll(a, s, 0)[span:-span] - truth[span:-span]).mean())
        if err is None or e < err:
            best, err = s, e
    return best
