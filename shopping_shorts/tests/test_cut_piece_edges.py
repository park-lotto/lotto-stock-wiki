# -*- coding: utf-8 -*-
"""컷 처음 몇 프레임 안 장면 경계도 '조각'으로 센다(render_bench.inner_bounds — snap_ss·cut_boundary_gate 공용).

10-25 잇템로그 ep12 N7 ayB: 원본 경계 [0.167, 1.767, 5.733, 8.4, 11.2], 컷 85프레임 ss 8.5 → 끝에 11.2 경계(0.13초 꼬리).
옛 판은 첫 1.5프레임 안 경계를 빼서 snap_ss 가 ss 8.367(= 첫 프레임이 앞 샷, 8.4 부터 새 샷)로 옮겼고,
완성본 27.63초에 앞 샷 얼굴 1프레임이 번쩍였다(눈 확인 · bench_check '컷 끝 번쩍임' ×).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import render_bench as RB  # noqa: E402

FPS = RB.FPS
AYB = [0.167, 1.767, 5.733, 8.4, 11.2]


def test_둘째_프레임_경계는_1프레임_조각이다():
    assert RB.short_pieces(AYB, 8.367, 8.367 + 85 / FPS) == [0.03]


def test_첫_프레임_경계는_조각이_아니다():
    assert RB.short_pieces(AYB, 8.4, 8.4 + 2.0) == []


def test_마지막_프레임_새샷은_조각이다():
    a = 9.0
    b = 11.2 + 1 / FPS          # 마지막 프레임 1장이 새 샷
    assert RB.short_pieces(AYB, a, b) == [0.03]


def test_snap_ss_는_앞샷_1프레임_자리로_가지_않는다(tmp_path, monkeypatch):
    src = tmp_path / "ayB.mp4"
    src.write_bytes(b"x")
    monkeypatch.setattr(RB, "shot_starts", lambda p: AYB)
    monkeypatch.setattr(RB, "src_left", lambda p, s: round(11.962 - s - 1 / FPS, 3))
    n = 85
    s = RB.snap_ss(src, 8.5, n / FPS)
    assert s != 8.367
    assert RB.short_pieces(AYB, s, s + n / FPS) == []
