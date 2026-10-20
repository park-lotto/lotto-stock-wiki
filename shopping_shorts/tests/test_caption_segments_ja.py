# -*- coding: utf-8 -*-
"""일본어 자막 나누기(2026-10-21 관제 248) — 띄어쓰기가 없어 어절 규칙이 통째로 한 덩어리가 된다.

잠그는 계약: 。、에서 끊는다 · 19자(_CAP_WRAP) 넘는 조각 없음 · 이어붙이면 원문(문장부호 제외)과 같다 ·
4자 미만 끝 조각 없음 · 긴 줄은 textwrap 기계 절단이 아니라 조사 뒤에서 끊는다.
"""
import re

from shopping_shorts import video_assemble as va

_P = re.compile(r"[\s、。！？!?,.…「」『』～~'\"()（）]")
SAMPLES = [
    "ダイソーに行ったら、これだけは絶対に買ってください。",
    "値段は安いのに使い道が多すぎてびっくりしました。今すぐチェックしてみてください！",
    "このキッチングッズを一度使ったらもう普通のものには戻れなくなりますよ。",
    "えっ、本当？",
]


def _bare(s):
    return _P.sub("", s)


def test_splits_at_punctuation():
    segs = va._caption_segments(SAMPLES[0])
    assert segs[0] == "ダイソーに行ったら"
    assert len(segs) >= 2


def test_no_segment_over_wrap_and_text_preserved():
    for s in SAMPLES:
        segs = va._caption_segments(s)
        assert segs, s
        assert all(len(_bare(x)) <= va._CAP_WRAP for x in segs), (s, segs)
        assert "".join(_bare(x) for x in segs) == _bare(s), (s, segs)


def test_no_short_tail():
    for s in SAMPLES[:3]:
        segs = va._caption_segments(s)
        assert len(_bare(segs[-1])) >= 4, (s, segs)


def test_wrap_long_cuts_after_particle():
    line = "値段は安いのに使い道が多すぎてびっくりしました"
    out = va._wrap_long([line])
    assert len(out) == 2, out
    assert "".join(out) == line
    assert out[0][-1] in "はがをにでとものへ" or out[0].endswith(("から", "まで", "より", "ね", "よ")), out
    assert out[0] != line[:va._CAP_WRAP]          # textwrap 19자 기계 절단이 아니다


def test_wrap_long_manual_japanese_still_split():
    line = "値段は安いのに使い道が多すぎてびっくりしました"
    out = va._wrap_long([line], manual=True)
    assert len(out) == 2 and all(len(x) <= va._CAP_WRAP for x in out)


def test_korean_unchanged():
    k = "이거 진짜 완전 대박이라서 다들 놀랐어요"
    assert va._caption_segments(k) == ["이거 진짜 완전 대박이라서", "다들 놀랐어요"]
