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


# ── 10-25 ep12 --plan 멈춤(98 #105): 원음 줄 안 원본 자체 편집점은 양쪽이 길면 통과, 같은 원음을 잘게 나누면 짧은 조각이 생겨 막힌다 ──
SAA = [19.567]                    # saA.mp4 원본 경계(shot_starts 실측) — O2 원음 spans 17.0~21.44 안
AYA = [3.8, 5.433, 7.033]         # ayA.mp4 — O3 원음 3.0~7.03 안


def _gate(cuts, starts, tmp_path, monkeypatch):
    for c in cuts:
        (tmp_path / c["src"]).write_bytes(b"x")
    monkeypatch.setattr(RB, "shot_starts", lambda p: starts)
    return RB.cut_boundary_gate({"cuts": cuts}, {"cand_dir": str(tmp_path)})


def test_원음_한컷_안_원본편집점은_통과(tmp_path, monkeypatch):
    """096d27de 완성본 O2(10.71초)·O3(18.33·19.96초)는 원본 자체 편집 — 양쪽 조각 0.8초 이상, 눈으로 번쩍임 없음."""
    o2 = [{"line": "O2", "src": "saA.mp4", "ss": 17.0, "t0": 8.139, "t1": 12.579, "kind": "orig"}]
    o3 = [{"line": "O3", "src": "ayA.mp4", "ss": 3.0, "t0": 17.53, "t1": 21.56, "kind": "orig"}]
    assert _gate(o2, SAA, tmp_path, monkeypatch) == []
    assert _gate(o3, AYA, tmp_path, monkeypatch) == []


def test_원음을_고르게_나눈_조각은_막힌다(tmp_path, monkeypatch):
    """옛 rhythm_cuts(6c16825e6)가 O2 를 1.11초 4조각으로 나눠 19.22~20.33 조각 안 19.567 경계 → 0.35초 조각(번쩍임) — 관문 ③이 잡는 게 맞다."""
    ps = [{"line": "O2", "src": "saA.mp4", "ss": round(17.0 + 1.11 * k, 3), "t0": round(8.14 + 1.11 * k, 3),
           "t1": round(8.14 + 1.11 * (k + 1), 3), "kind": "orig"} for k in range(4)]
    bad = _gate(ps, SAA, tmp_path, monkeypatch)
    assert len(bad) == 1 and "0.35" in bad[0]
