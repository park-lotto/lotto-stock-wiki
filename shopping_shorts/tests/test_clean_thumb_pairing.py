# -*- coding: utf-8 -*-
"""자막제거 전/후 비교는 **같은 장면**이어야 한다 — 컷(clip) 단위로 짝을 맞춘다.

★2026-08-27, 사장님 제보 "영상 좌우가 달라"를 **세 번 틀리고 네 번째에** 잡았다.
  기록으로 남긴다 — 같은 함정을 또 밟지 않기 위해:

  1) pos = 소스 파일 전체의 비율
       → 원본 60초의 50%는 완성본에 안 쓰인 딴 장면.
  2) pos = 재료 구간(start~end) 안의 비율
       → 실측 job 16f1b398f7cd: 구간 5.4~11.1(5.7초)인데 **실제 컷은 2.69초**.
         컷은 구간 앞에서 dur만큼만 쓴다 → 뒷부분을 짚었다.
  3) pos = 비트(beat) 전체 안의 비율
       → 실측 job 9a3ff19fbceb beat9: [s0, s4, s0, s4] **4조각이 시간을 나눠 갖는다**.
         비트 한가운데는 s4가 아니라 s0 자리였다.
  4) **컷 단위** — 화면에 실제로 나가는 최소 단위. 이제야 맞는다.

★계획은 video_assemble.plan_beat_clips_for 한 곳에서 온다(렌더·캡컷·ZIP이 쓰는 그것).
  여기서 따로 계산하면 또 어긋난다(0순위-B).
"""
import pytest

from shopping_shorts import mix_pipeline as mp


def _beat(idx, secs, mats):
    """mats = [(vid, start, end), ...]"""
    m = [{"video_id": v, "seg_id": f"{v}-{i}", "start": s, "end": e}
         for i, (v, s, e) in enumerate(mats)]
    return {"beat_idx": idx, "target_seconds": secs,
            "primary": m[0], "alternates": m[1:]}


def _plan():
    """실측 job 9a3ff19fbceb의 모양 — 마지막 비트에 재료 4개가 섞인다."""
    return {"beats": [
        _beat(0, 6.0, [("s0", 1.0, 3.0), ("s1", 0.0, 12.9)]),
        _beat(1, 8.0, [("s0", 17.0, 19.0), ("s4", 5.7, 8.2),
                       ("s0", 0.0, 1.0), ("s4", 1.1, 2.8)]),
    ]}


_SD = {"s0": 20.0, "s1": 13.0, "s4": 10.0}


class Test컷단위_짝맞춤:
    def test_섞인_비트에서_그_소스의_컷을_짚는다(self):
        """★3차 오진 재발 방지 — 비트 한가운데는 s0 자리다. s4를 물으면 s4 컷이어야 한다."""
        src, fin = mp.final_pair_for_source(_plan(), "s4", 0.5, src_durs=_SD)
        assert src is not None
        assert 5.7 <= src <= 8.2, f"s4 재료 구간 밖을 짚었다: {src}"

    def test_좌우가_같은_컷_안에서_같은_비율(self):
        a = mp.final_pair_for_source(_plan(), "s4", 0.0, src_durs=_SD)
        b = mp.final_pair_for_source(_plan(), "s4", 1.0, src_durs=_SD)
        assert (b[0] - a[0]) == pytest.approx(b[1] - a[1]), "좌우 이동폭이 다르면 어긋난다"

    def test_컷_목록이_시간순(self):
        cl = mp.final_clip_pairs(_plan(), {}, _SD)
        assert cl, "컷이 하나도 안 나왔다"
        fins = [c["fin"] for c in cl]
        assert fins == sorted(fins)

    def test_컷_길이_합이_비트_길이_합과_맞는다(self):
        cl = mp.final_clip_pairs(_plan(), {}, _SD)
        total = sum(c["dur"] for c in cl)
        assert total == pytest.approx(6.0 + 8.0, abs=0.2)

    def test_각_컷은_자기_재료_구간에서_시작(self):
        """컷이 남의 구간을 읽으면 화면이 튄다."""
        ranges = {}
        for b in _plan()["beats"]:
            for m in mp._beat_materials(b):
                ranges.setdefault(m["video_id"], []).append((m["start"], m["end"]))
        for c in mp.final_clip_pairs(_plan(), {}, _SD):
            assert any(lo - 0.01 <= c["src"] <= hi + 0.01
                       for lo, hi in ranges[c["video_id"]]), c

    def test_안_쓰인_소스는_None(self):
        assert mp.final_pair_for_source(_plan(), "s9", 0.5, src_durs=_SD) == (None, None)

    def test_소스길이를_모르면_비트기준으로_물러선다(self):
        """★목록(비트 기준)보다 엄격하면 '목록엔 있는데 404'가 난다."""
        src, fin = mp.final_pair_for_source(_plan(), "s4", 0.5)
        assert src is not None and fin is not None

    def test_pos가_이상해도_안전(self):
        for bad in (-1, 2, None, "x"):
            src, _ = mp.final_pair_for_source(_plan(), "s4", bad, src_durs=_SD)
            assert src is None or 5.7 <= src <= 8.2
