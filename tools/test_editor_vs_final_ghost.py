"""편집 화면 vs 완성본 대조 도구의 잔상 검사(_edge_ghosts) — 컷 가장자리 딴 장면 1~3프레임을 세는지(2026-09-27).

왜: 서버 다섯 job(3a088ce2cfdd·62ed6bf66eb9·d404e8b70f79·1e5914353a26·e6a33782a7bf)에서 편집 화면 미리보기 컷 끝·머리에
  딴 장면 1~3프레임이 끼었는데, 가운데 검사는 0.2초 미만을 건너뛰고 경계 검사는 '9.9'로만 남겨 아무 숫자에도 안 잡혔다.
합성 특징(6x6 z 칸): 장면마다 다른 난수 그림 + 프레임마다 작은 흔들림.
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np

_P = Path(__file__).resolve().parent / "editor_vs_final_video.py"
_spec = importlib.util.spec_from_file_location("editor_vs_final_video", str(_P))
evf = importlib.util.module_from_spec(_spec)
sys.modules["editor_vs_final_video"] = evf
_spec.loader.exec_module(evf)


def _scene(seed):
    return np.random.default_rng(seed).standard_normal((6, 6)).astype(np.float32)


def _video(layout):
    """layout = [(장면 seed, 프레임 수), ...] → (N,6,6) 특징. 같은 장면 안은 흔들림 0.05."""
    out, k = [], 0
    for seed, n in layout:
        base = _scene(seed)
        for _ in range(n):
            out.append(base + _scene(1000 + k) * 0.05)
            k += 1
    return np.stack(out)


def test_tail_ghost_two_frames_counted():
    """62ed 꼴: 컷 끝 2프레임이 앞·뒤 컷 어느 쪽과도 다른 장면(원본의 다음 장면)."""
    fe = _video([(1, 28), (9, 2), (2, 30)])          # 컷0 = 0..29(끝 2장 = 9번 장면), 컷1 = 30..59
    assert evf._edge_ghosts(fe, 0, 29) == (0, 2)
    assert evf._edge_ghosts(fe, 30, 59) == (0, 0)


def test_head_ghost_three_frames_counted():
    """d404 꼴: 컷 머리 3프레임이 원본의 앞 장면."""
    fe = _video([(1, 30), (9, 3), (2, 27)])
    assert evf._edge_ghosts(fe, 30, 59) == (3, 0)


def test_one_frame_ghost_and_first_frame_of_video():
    """3a088 꼴(꼬리 1장) + e6a3 꼴(영상 첫 프레임 1장 — 앞 컷이 없다)."""
    fe = _video([(9, 1), (1, 29), (8, 1), (2, 29)])
    assert evf._edge_ghosts(fe, 0, 29) == (1, 0)
    assert evf._edge_ghosts(fe, 0, 30) == (1, 1)


def test_boundary_shift_is_not_ghost():
    """컷 끝 2장이 **다음 컷 그림**이면 경계가 밀린 것이지 잔상이 아니다(경계 밀림은 따로 잰다)."""
    fe = _video([(1, 28), (2, 32)])                   # 경계가 28에 있는데 컷 표기는 0..29
    assert evf._edge_ghosts(fe, 0, 29) == (0, 0)


def test_clean_cuts_have_no_ghost():
    fe = _video([(1, 30), (2, 30)])
    assert evf._edge_ghosts(fe, 0, 29) == (0, 0)
    assert evf._edge_ghosts(fe, 30, 59) == (0, 0)


def test_short_cut_not_checked():
    """7프레임 이하 컷은 몸통 기준이 없어 보지 않는다(보고서에 '짧은컷'으로 따로 센다)."""
    fe = _video([(1, 30), (9, 1), (3, 5), (2, 30)])
    assert evf._edge_ghosts(fe, 30, 35) == (0, 0)


def test_ghost_in_final_lookup():
    fe = _video([(1, 28), (9, 2), (2, 30)])
    ff_clean = _video([(1, 30), (2, 30)])
    ff_same = fe.copy()
    assert not evf._ghost_in_final(fe, ff_clean, 28, 28)
    assert evf._ghost_in_final(fe, ff_same, 28, 29)


def test_fast_motion_not_ghost():
    """휙 돌리기·흔들림: 몸통 안에서도 프레임마다 크게 변해 3프레임 떨어진 기준과 멀어진다 — 이음매가 뚝 끊기지 않으면 잔상이 아니다
    (서버 실측 2026-09-27: 이 판정이 없을 때 39e55470ebb0 등에서 움직임 오탐 — 눈으로 6곳 확인)."""
    # 한 방향으로 계속 움직이는 몸통: 프레임 간 거리 0.8*s, 3프레임 떨어지면 SCENE_T 를 넘고 2프레임이면 안 넘는다
    #   → 거리 규칙만으로는 꼬리 1장을 잔상으로 잡는다(아래 사보타주로 확인). 이음매 튐 = 몸통 튐이라 걸러야 한다.
    V = _scene(77)
    s_ = 0.25
    fe = np.stack([_scene(1) + i * s_ * V for i in range(30)] + [_scene(2) + _scene(3000 + i) * 0.05 for i in range(30)])
    d3 = float(np.abs(fe[29] - fe[26]).mean()); d2 = float(np.abs(fe[28] - fe[26]).mean())
    assert d3 >= evf.SCENE_T > d2, (d3, d2)          # 합성이 거리 규칙을 실제로 건드리는지(안 건드리면 이 테스트는 아무것도 안 잰다)
    assert evf._edge_ghosts(fe, 0, 29) == (0, 0)
