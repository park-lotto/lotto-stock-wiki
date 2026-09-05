# -*- coding: utf-8 -*-
"""조각 경계를 실제 컷 경계(프레임)로 스냅 — 다음 장면 첫 프레임 딸림 제거.

★왜 필요한가(2026-09-06 실측, 서버 영상 lens_instagram_1844uac 히카마):
  제미니는 조각 경계를 **0.1초 단위로 반올림해서** 답한다. 실제 컷 경계가
  0.967초인데 "1.00초"라고 말한다. 그 +0.033초(1프레임) 안에 **다음 장면의
  첫 프레임**이 들어와 재생하면 툭 튄다(사장님 "꼬다리가 튀는 느낌").
  실측: 조각 17개 중 9개가 +쪽으로 1프레임 넘침. 최대 어긋남도 1프레임이라
  좁은 반경으로 안전하게 붙일 수 있다.
  ⚠️scene_cut 맨 위 경고와 같은 뿌리 — "초로 반올림하지 마라".
"""
import pytest

from shopping_shorts.script_extract import _snap_to_cuts


def _cuts30(*frames):
    """(start,end) 프레임 튜플 목록 — detect_cuts 반환 형태."""
    return [(frames[i], frames[i + 1]) for i in range(len(frames) - 1)]


def test_반올림된_경계가_실제_컷으로_붙는다():
    # 실제 컷: 0.967s(f29) · 2.867s(f86).  제미니는 1.00 / 2.90 이라 답한다.
    cuts = _cuts30(0, 29, 86, 120)
    segs = [{"start": 0.0, "end": 1.00}, {"start": 1.00, "end": 2.90}]
    out = _snap_to_cuts(segs, cuts, 30.0)
    assert out[0]["end"] == pytest.approx(29 / 30.0, abs=1e-6)
    assert out[1]["end"] == pytest.approx(86 / 30.0, abs=1e-6)
    # 시작도 같이 붙어 앞 조각 끝과 이어진다(틈이 생기면 안 된다)
    assert out[1]["start"] == pytest.approx(out[0]["end"], abs=1e-6)


def test_반경_밖은_건드리지_않는다():
    """제미니가 일부러 컷 중간을 가리킨 경우(한 컷 안 두 문장)는 그대로 둔다."""
    cuts = _cuts30(0, 29, 300)
    segs = [{"start": 0.0, "end": 5.00}]      # 가장 가까운 컷과 4초 넘게 차이
    out = _snap_to_cuts(segs, cuts, 30.0)
    assert out[0]["end"] == 5.00


def test_컷이_없으면_원본_그대로():
    segs = [{"start": 0.0, "end": 1.00}]
    assert _snap_to_cuts(segs, [], 30.0)[0]["end"] == 1.00
    assert _snap_to_cuts(segs, None, 0)[0]["end"] == 1.00


def test_붙여도_순서와_길이가_깨지지_않는다():
    """스냅 뒤에도 start < end 이고 앞뒤가 겹치지 않아야 한다."""
    cuts = _cuts30(0, 29, 86, 148, 310)
    segs = [{"start": 0.0, "end": 1.00}, {"start": 1.00, "end": 2.90},
            {"start": 2.90, "end": 4.90}]
    out = _snap_to_cuts(segs, cuts, 30.0)
    for s in out:
        assert s["end"] > s["start"]
    for a, b in zip(out, out[1:]):
        assert b["start"] >= a["end"] - 1e-6


def test_60fps에서도_프레임에_앉는다():
    """fps가 다르면 프레임 간격도 다르다 — 반경은 초가 아니라 프레임 기준이어야 한다."""
    cuts = [(0, 59), (59, 200)]
    segs = [{"start": 0.0, "end": 1.00}]      # 실제 경계 59/60 = 0.9833s
    out = _snap_to_cuts(segs, cuts, 60.0)
    assert out[0]["end"] == pytest.approx(59 / 60.0, abs=1e-6)
