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


class Test좌우_같은_장면:
    def test_원본_시각은_쓰인_구간_안(self):
        """★핵심 — 원본 전체의 pos가 아니라 5.4~11.1 안이어야 한다."""
        sec, _ = mp.final_pair_for_source(_plan(), "s3", 0.5)
        assert 5.4 <= sec <= 11.1, sec
        assert sec == pytest.approx(5.4 + (11.1 - 5.4) * 0.5)

    def test_앞_가운데_뒤가_구간_안에서_움직인다(self):
        a, _ = mp.final_pair_for_source(_plan(), "s3", 0.0)
        b, _ = mp.final_pair_for_source(_plan(), "s3", 0.5)
        c, _ = mp.final_pair_for_source(_plan(), "s3", 1.0)
        assert a < b < c
        assert a == pytest.approx(5.4) and c == pytest.approx(11.1)

    def test_완성본_비율도_같은_비율로_움직인다(self):
        """좌우가 짝이어야 한다 — 한쪽만 움직이면 다시 어긋난다."""
        _, r0 = mp.final_pair_for_source(_plan(), "s3", 0.0)
        _, r1 = mp.final_pair_for_source(_plan(), "s3", 1.0)
        assert r0 < r1

    def test_두_비트_중_뒤쪽_소스는_완성본_뒤쪽(self):
        _, r_first = mp.final_pair_for_source(_plan(), "s0", 0.5)
        _, r_last = mp.final_pair_for_source(_plan(), "s3", 0.5)
        assert r_first < r_last, "순서가 뒤집혔다"

    def test_alternates로만_쓰인_소스도_찾는다(self):
        """alternates도 실제로 화면에 나온다 — 빼면 그 소스가 '안 쓰임'이 된다."""
        sec, ratio = mp.final_pair_for_source(_plan(), "s1", 0.5)
        assert sec is not None and 6.1 <= sec <= 8.8

    def test_안_쓰인_소스는_None(self):
        assert mp.final_pair_for_source(_plan(), "s9", 0.5) == (None, None)

    def test_뒤집힌_구간은_None(self):
        p = _plan()
        p["beats"][1]["primary"] = {"video_id": "s3", "start": 9.0, "end": 3.0}
        assert mp.final_pair_for_source(p, "s3", 0.5) == (None, None)

    def test_pos가_이상해도_안전(self):
        for bad in (-1, 2, None, "x"):
            sec, _ = mp.final_pair_for_source(_plan(), "s3", bad)
            assert sec is None or 5.4 <= sec <= 11.1
