# -*- coding: utf-8 -*-
"""자막제거 전/후 비교는 **같은 장면**이어야 한다 (2026-08-27).

★사장님 제보 "이거 자막제거 한건데 영상 좌우가 달라".
  실측 job 16f1b398f7cd — s3은 완성본에 원본 5.4~11.1초만 쓰였는데:
      BEFORE = 원본 파일의 50% 지점 (번호판 걸린 벽)
      AFTER  = 완성본에서 s3이 쓰인 지점 (흰 벽에 도구질)
  전혀 다른 그림이 나란히 떴다.

★왜 생겼나: 옛 방식(소스별 청소본)은 좌우가 **같은 길이의 파일**이라 pos만 맞으면
  대응됐다. 완성본 1편 청소로 바뀌며 좌우 시간축이 갈렸는데 pos는 그대로 썼다.
"""
import pytest

from shopping_shorts import mix_pipeline as mp


def _plan():
    """실측 job 16f1b398f7cd의 편성 모양."""
    return {"beats": [
        {"beat_idx": 0, "target_seconds": 7.0,
         "primary": {"video_id": "s0", "start": 2.6, "end": 3.9},
         "alternates": [{"video_id": "s1", "start": 6.1, "end": 8.8}]},
        {"beat_idx": 1, "target_seconds": 3.0,
         "primary": {"video_id": "s3", "start": 5.4, "end": 11.1}, "alternates": []},
    ]}


def _tl():
    """실제 타임라인 — ★재료 구간(5.4~11.1=5.7초)보다 컷이 짧다(2.69초)."""
    return [{"beat_idx": 0, "t0": 0.0, "dur": 7.01},
            {"beat_idx": 1, "t0": 7.01, "dur": 2.69}]


class Test좌우_같은_장면:
    def test_원본은_실제_컷_길이_안에서(self):
        """★1차 오진 재발 방지 — 재료 구간이 5.7초여도 화면에 나오는 건 앞 2.69초뿐이다."""
        sec, _ = mp.final_pair_for_source(_plan(), "s3", 0.5, timeline=_tl())
        assert sec == pytest.approx(5.4 + 2.69 * 0.5)
        assert sec < 5.4 + 2.69, "안 쓰이는 뒷부분을 가리킨다"

    def test_완성본은_초로_직접_짚는다(self):
        """비율이면 조립본 길이가 계획과 다를 때 어긋난다(실측 24.19 vs 25.4초)."""
        _, fin = mp.final_pair_for_source(_plan(), "s3", 0.5, timeline=_tl())
        assert fin == pytest.approx(7.01 + 2.69 * 0.5)

    def test_좌우가_같은_비율만큼_움직인다(self):
        a_s, a_f = mp.final_pair_for_source(_plan(), "s3", 0.0, timeline=_tl())
        b_s, b_f = mp.final_pair_for_source(_plan(), "s3", 1.0, timeline=_tl())
        assert (b_s - a_s) == pytest.approx(b_f - a_f), "좌우 이동폭이 다르면 다시 어긋난다"

    def test_앞_가운데_뒤(self):
        xs = [mp.final_pair_for_source(_plan(), "s3", p, timeline=_tl())[0]
              for p in (0.0, 0.5, 1.0)]
        assert xs[0] < xs[1] < xs[2]
        assert xs[0] == pytest.approx(5.4)

    def test_타임라인이_없으면_근사로라도_준다(self):
        sec, fin = mp.final_pair_for_source(_plan(), "s3", 0.5)
        assert sec is not None and fin is not None

    def test_alternates로만_쓰인_소스도_찾는다(self):
        sec, _ = mp.final_pair_for_source(_plan(), "s1", 0.5, timeline=_tl())
        assert sec is not None and sec >= 6.1

    def test_안_쓰인_소스는_None(self):
        assert mp.final_pair_for_source(_plan(), "s9", 0.5, timeline=_tl()) == (None, None)

    def test_길이가_0이면_None(self):
        bad = [{"beat_idx": 1, "t0": 7.0, "dur": 0.0}]
        p = {"beats": [_plan()["beats"][1]]}
        assert mp.final_pair_for_source(p, "s3", 0.5, timeline=bad) == (None, None)

    def test_pos가_이상해도_안전(self):
        for b in (-1, 2, None, "x"):
            sec, _ = mp.final_pair_for_source(_plan(), "s3", b, timeline=_tl())
            assert sec is None or 5.4 <= sec <= 5.4 + 2.69
