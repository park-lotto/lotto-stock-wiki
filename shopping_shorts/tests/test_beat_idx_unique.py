# -*- coding: utf-8 -*-
"""beat_idx는 유일해야 한다 — 2026-09-06 고객 제보 회귀 방지.

증상(고객 화면): 6번 칸을 고치는데 **아래칸 대본을 안 읽고 위의 대사를 반복**하고,
수정도 삭제도 먹통이었다. 원인은 화면이 아니라 **데이터**였다:
라이브 job 3ec9df659411의 beat_idx가 [0,1,3,2,5,5,5] — 5가 셋이었다
(실측: edit_plan 있는 1438잡 중 6잡이 중복 보유).

하류는 전부 beat_idx를 유일 키로 쓴다:
  - mp3 이름          mix_pipeline._tts_path → beat_{beat_idx}_{key}.mp3
  - tts_paths dict    {b["beat_idx"]: b["tts_path"]}   ← 겹치면 마지막만 남는다
  - app.py 조회       next(... if b["beat_idx"]==beat_idx)  ← **첫 칸만** 집는다
그래서 겹치면 조용히 남의 칸에 저장·삭제·재생된다(오류도 안 난다).
"""
import pytest

from shopping_shorts import edit_plan as ep


def _mk(idx, narration, sec=3.0, seg="a"):
    return {"beat_idx": idx, "narration": narration,
            "primary": {"seg_id": seg}, "target_seconds": sec}


def test_rebuild_by_lines_gives_unique_beat_idx():
    """한 칸의 대사가 대본 여러 줄에 걸치면 그 칸이 N칸의 원본이 된다.

    _rebuild_beats_by_lines는 `nb = dict(base)`로 복사하므로 재부여가 없으면
    **base의 beat_idx가 그대로 N번 복사된다**(고객 데이터의 5,5,5가 이것).
    """
    sents = [
        "얼마 전 자취하는 친구 집에 놀러 갔어요.",
        "근데 이게 대박인 게 미끄럼 방지 장치가 있어요.",
        "다들 어디 거냐고 물어보길래 정보 정리해뒀어요.",
        "제품정보는 채널명아래 고정링크를 확인하세요.",
    ]
    beats = [
        _mk(0, sents[0], 3.0, "a"),
        # 한 칸에 세 줄이 뭉쳐 있다 → 여기서 중복이 태어난다
        _mk(5, " ".join(sents[1:]), 9.0, "b"),
    ]
    out = ep._rebuild_beats_by_lines(beats, sents)
    idxs = [b.get("beat_idx") for b in out]
    assert len(idxs) == len(set(idxs)), "beat_idx가 겹쳤다: %r" % (idxs,)
    assert idxs == list(range(len(out))), "0..n-1이 아니다: %r" % (idxs,)


def test_rebuild_by_lines_keeps_narration_order():
    """번호를 다시 매겨도 대사 내용·순서는 건드리지 않는다(회귀 방지)."""
    sents = ["첫 줄이에요.", "둘째 줄이에요.", "셋째 줄이에요."]
    beats = [_mk(0, sents[0], 3.0, "a"), _mk(1, " ".join(sents[1:]), 6.0, "b")]
    out = ep._rebuild_beats_by_lines(beats, sents)
    assert [b["narration"] for b in out] == sents


def test_find_beat_blocks_duplicate_and_allows_unique():
    """app._find_beat: 겹치면 **조용히 아무거나 고르지 않는다**(양방향 검사).

    막기만 하는 게 아니라 멀쩡한 번호는 그대로 찾혀야 한다 — 과하게 막으면
    정상 작업까지 죽는다.
    """
    from shopping_shorts.app import _find_beat

    dup = [{"beat_idx": i, "narration": "n%d" % k}
           for k, i in enumerate([0, 1, 3, 2, 5, 5, 5])]   # 고객 실측 배열
    b, err = _find_beat(dup, 5)
    assert b is None and "겹쳐" in err, "중복인데 통과했다"

    b, err = _find_beat(dup, 3)          # 유일한 번호는 정상 조회
    assert b is not None and err is None

    b, err = _find_beat(dup, 99)         # 없는 번호
    assert b is None and err == "비트 없음"

    ok = [{"beat_idx": i, "narration": "n%d" % i} for i in range(7)]
    assert all(_find_beat(ok, i)[0] is not None for i in range(7)), "정상 잡에 회귀"
