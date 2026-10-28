"""편집 화면 vs 완성본 대조 도구의 _match — 정지 컷이 옆 컷 끝 프레임에 붙어 가짜 밀림을 내지 않는지(2026-09-27).

왜: 정지 컷(원본이 모자라 마지막 프레임을 세우는 컷)이 앞 컷과 같은 원본을 읽으면 그 정지 그림 = 앞 컷 끝 프레임이다.
  완성본 정지 몫엔 켄번즈가 얹혀 제 구간의 그림은 조금 다르고, 앞 컷 끝 프레임이 더 닮아 보인다 →
  찾는 범위(±0.6초)가 앞 컷까지 걸치면 거기를 골라 −0.533초 같은 가짜 밀림을 보고했다.
합성: ② 0~29 = 앞 컷(움직이다 29번에서 그림 F), 30~59 = 정지 컷(F + 켄번즈 잡음 0.05), ①도 같은 배치(정지 몫은 F 그대로).
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


def _clips():
    F = _scene(99)
    moving = [_scene(i) * 0.3 + F * 0.7 for i in range(30)]      # 앞 컷: 움직이다
    for j in range(24, 30):                                        # 끝 6프레임은 정지 그림 F 로 수렴(같은 원본을 이어 읽음)
        moving[j] = F.copy()
    kb = _scene(7) * 0.05                                          # 완성본 정지 몫의 켄번즈 확대 차이
    ff = np.stack(moving + [F + kb] * 30)
    fe = np.stack(moving + [F] * 30)
    g = np.zeros((60, 4, 4), np.float32)
    return fe, ff, g


def test_hold_cut_without_span_shows_fake_shift():
    """좁히지 않으면(옛 동작) 앞 컷 끝에 붙는다 — 이 합성이 실제로 그 착시를 재현하는지 먼저 확인."""
    fe, ff, g = _clips()
    d, s, jb, *_ = evf._match(fe, ff, g, g, 40, 40)
    assert jb < 30 and s < -0.15, (jb, s)


def test_hold_cut_span_keeps_search_inside_cut():
    fe, ff, g = _clips()
    d, s, jb, *_ = evf._match(fe, ff, g, g, 40, 40, (30, 59))
    assert 30 <= jb <= 59 and abs(s) < 1e-9, (jb, s)
    assert d < evf.SCENE_T


def test_span_ignored_when_expected_frame_outside():
    """기대 프레임이 구간 밖이면(계산이 어긋난 경우) 좁히지 않는다 — 없는 자리에서 억지로 찾지 않게."""
    fe, ff, g = _clips()
    a = evf._match(fe, ff, g, g, 10, 10, (30, 59))
    b = evf._match(fe, ff, g, g, 10, 10)
    assert a[:3] == b[:3]
