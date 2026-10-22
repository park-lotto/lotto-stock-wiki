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
    assert len(out) >= 2 and all(len(x) <= va._JA_CAP_WRAP for x in out), out   # 관제 254: 일본어 한 줄 10자
    assert "".join(out) == line
    assert out[0][-1] in "はがをにでとものへ" or out[0].endswith(("から", "まで", "より", "ね", "よ")), out
    assert out[0] != line[:va._CAP_WRAP]          # textwrap 19자 기계 절단이 아니다


def test_wrap_long_manual_japanese_still_split():
    line = "値段は安いのに使い道が多すぎてびっくりしました"
    out = va._wrap_long([line], manual=True)
    assert len(out) >= 2 and all(len(x) <= va._JA_CAP_WRAP for x in out)   # 관제 254


def test_korean_unchanged():
    k = "이거 진짜 완전 대박이라서 다들 놀랐어요"
    assert va._caption_segments(k) == ["이거 진짜 완전 대박이라서", "다들 놀랐어요"]


# ── 2026-10-21 라이브 e2e(job 1e2c12ade064) 캡컷 21구절에서 잡은 어절 가운데 절단 4건 — 다시 나지 않는다 ──
LIVE_LINES = [
    "丈夫なコップとして再利用できるように変えたんです。",      # 종전 "再利用で|きる"
    "しかも食器棚で重ねられなかった普通のカップとは違って、",  # 종전 "重ね|られなかった"
    "場所ばかり取って割れやすかったストレスを、",             # 종전 "割れ|やすかった"(조사 없어 가운데 절단)
    "スッキリ重ねられるようにして解消したんだとか。",         # 종전 "スッキリ重ね|られる"
    "でも本当に衝撃的なのは、マスカルポーネがたっぷり詰まっていて味のためにリピ買いしちゃうこと。",
]
INTACT = ("再利用できる", "重ねられ", "割れやすかった", "ために")


def test_live_lines_keep_words_intact():
    for s in LIVE_LINES:
        segs = va._caption_segments(s)
        assert all(len(_bare(x)) <= va._CAP_WRAP for x in segs), (s, segs)
        assert "".join(_bare(x) for x in segs) == _bare(s), (s, segs)
        for w in INTACT:
            if w in s:
                assert any(w in x for x in segs), ("낱말이 갈렸다", w, segs)


def test_particle_followed_by_hiragana_is_not_a_cut():
    out = va._ja_split_long("丈夫なコップとして再利用できるように変えたんです")
    assert out[0].endswith(("として", "できるように")) or "再利用できる" in "".join(out[:1]) or any("再利用できる" in x for x in out), out
    assert not any(x.endswith("再利用で") for x in out), out
