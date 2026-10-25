# -*- coding: utf-8 -*-
"""꾸밈(장식) 주인 tools/calcopy/hybrid/deco.py — 관제263 10-25 사장님 '키치잇 꾸밈(본인 사진·큰 손글씨·여러 색·소리 글자·원+화살표)이 우리 편엔 없다'.

결과물 검사(check)가 박정수 v2 꼴(포인트 0·본인 사진 0)을 거절하고, 답을 얹은 꼴은 통과시키는지 · 렌더 전 관문(rhythm cut_max·같은 구도 한 컷,
쿠팡 사진 상한에서 본인 사진 빼기) · 반복 금지를 잰다. 사보타주: apply 를 빈 함수로 / photo_share 가 own_ 을 세게 / seam_corr 무시 → 실패해야 한다."""
import json
from pathlib import Path

import pytest

from tools.calcopy.hybrid import deco as DC
from tools.calcopy.hybrid import render_bench as RB
from tools.calcopy.hybrid import styles as SS

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def st():
    return SS.load("키치잇판")


def _rows():
    T = [("N1", "배우 박정수가", [{"word": "박정수가"}]), ("N1", "시슬리 선크림 대신", [{"word": "시슬리"}]), ("O1", "안 씁니다", [{"word": "안 씁니다"}]),
         ("N4", "로션처럼 얇게 펴져서", [{"word": "로션처럼"}]), ("N4", "안 밀리더라고요", [{"word": "안 밀리더라고요"}]), ("N5", "심지어 튜브에", [{"word": "심지어"}]),
         ("N5", "적혀 있더라고요", [{"word": "적혀"}]), ("N6", "만든 거래요", [{"word": "만든 거래요"}]), ("N7", "넘을 만큼 인기래요", [{"word": "인기래요"}])]
    T += [("X", f"덩어리 {i}", [{"word": "덩어리"}]) for i in range(6)]
    t = 0.0
    out = []
    for line, text, em in T:
        out.append({"line": line, "text": text, "emph": em, "variant": "", "stickers": [], "show": [t, t + 1.0]})
        t += 1.0
    return out


def _cuts(own=True):
    c = [{"src": "a.mp4", "t0": 0.0, "t1": 10.0}, {"src": "b.mp4", "t0": 10.0, "t1": 27.0}]
    if own:
        c = [{"src": "own_1_x.jpg", "t0": 0.0, "t1": 0.8}, {"src": "a.mp4", "t0": 0.8, "t1": 10.0}, {"src": "own_2_y.jpg", "t0": 10.0, "t1": 11.0},
             {"src": "b.mp4", "t0": 11.0, "t1": 27.0}]
    return c


ANS = {"items": [
    {"kind": "multi_color", "line": "N4", "text": "로션처럼 얇게 펴져서", "words": [{"word": "로션처럼", "color": "#65FEFB"}, {"word": "얇게", "color": "#FD6B7B"}]},
    {"kind": "chunk_color", "line": "N1", "text": "배우 박정수가", "color": "#65FEFB"},
    {"kind": "chunk_color", "line": "N7", "text": "넘을 만큼 인기래요", "color": "#FD6B7B"},
    {"kind": "sound_word", "line": "N5", "text": "심지어 튜브에", "word": "두둥", "x": 22, "y": 31},
    {"kind": "circle_arrow", "line": "N5", "text": "적혀 있더라고요", "what": "Tear-Free 글자", "box": [680, 650, 920, 750]},
]}


def test_measure_kitchit(st):
    M = DC.measure(st)
    assert M["n"] == 10                                              # 줄판독 8 + 꾸밈_추가판독 2
    assert M["kinds"]["photo"]["videos"] == 7 and M["photo"]["hook"] == 5
    assert M["kinds"]["hand_big"]["videos"] == 1 and M["kinds"]["word_color"]["videos"] == 9


def test_board_has_deco(st):
    D = DC.board(st)
    assert D["kinds"]["photo"]["need"] == "core" and D["kinds"]["chunk_color"]["need"] == "core"
    assert D["accent_min"] >= 1 and not D["kinds"]["tilt"]["drawn"]


def test_v2_shape_rejected_and_answers_pass(st):
    v = DC.check(".", st, rows=_rows(), cuts=_cuts(own=False), end=27.0)
    assert not v["ok"] and any("포인트" in b for b in v["bad"]) and any("photo" in b for b in v["bad"])
    rows = DC.apply(_rows(), ANS, st, log=lambda m: None)
    v2 = DC.check(".", st, rows=rows, cuts=_cuts(), end=27.0)
    assert v2["ok"], v2["bad"]
    assert set(v2["accents"]) >= {"multi_color", "sound_word", "circle_arrow"}
    ca = next(s for x in rows for s in x["stickers"] if s["kind"] == "circle_arrow")
    assert ca["aim"]["box"] == [680, 650, 920, 750] and 0 < ca["r"] < 30


def test_answer_errors(st):
    with pytest.raises(DC.DecoError):
        DC.apply(_rows(), {"items": [{"kind": "hand_big", "line": "O1", "text": "안 씁니다"}]}, st)                  # 큰 손글씨 = 아직 안 그림(다음)
    with pytest.raises(DC.DecoError):
        DC.apply(_rows(), {"items": [{"kind": "big", "line": "N9", "text": "없는 덩어리"}]}, st)                    # 덩어리 없음 = 조용히 넘기지 않음
    with pytest.raises(DC.DecoError):
        DC.apply(_rows(), {"items": [{"kind": "circle_arrow", "line": "N5", "text": "적혀 있더라고요", "box": [0, 0, 800, 800]}]}, st)   # 화면 10% 넘는 대상
    with pytest.raises(DC.DecoError):
        DC.apply(_rows(), {"items": [{"kind": "tilt", "line": "N5", "text": "적혀 있더라고요"}]}, st)               # 못 그리는 종류


def test_photo_share_excludes_own():
    cuts = [{"src": "own_1.jpg", "t0": 0.0, "t1": 2.0}, {"src": "cp_1.jpg", "t0": 2.0, "t1": 3.0}, {"src": "a.mp4", "t0": 3.0, "t1": 10.0}]
    assert RB.photo_share(cuts, 10.0) == 0.1                             # 쿠팡 1초만(본인 사진 2초는 뺌)


def test_repeat_check(tmp_path, st):
    log = tmp_path / "작업기록.jsonl"
    log.write_text(json.dumps({"bench_channel": "kitchit", "deco": DC.summary(ANS), "note": "doc=다른편"}, ensure_ascii=False) + "\n", encoding="utf-8")
    bad = DC.repeat_check(ANS, st, log_path=log)
    assert any("두둥" in b for b in bad) and any("조합" in b for b in bad)
    other = {"items": [{"kind": "sound_word", "line": "N5", "text": "심지어 튜브에", "word": "짠"}, {"kind": "big", "line": "N7", "text": "넘을 만큼 인기래요"}]}
    assert DC.repeat_check(other, st, log_path=log) == []


def test_row_kinds_matches_line_kinds():
    assert DC.row_kinds({"text": "굉장히 좋아요", "emph": [{"word": "굉장히 좋아요", "color": "#FD6B7B"}]}) == ["chunk_color"]
    assert DC.line_kinds({"text": "굉장히 좋아요", "emph": [{"word": "굉장히 좋아요", "hex": "#FD6B7B"}]}) == ["chunk_color"]
    assert DC.row_kinds({"text": "이거 바르고 저거 발라", "emph": [{"word": "이거", "color": "#65FEFB"}, {"word": "저거", "color": "#BDB4FC"}]}) == ["multi_color"]
    assert DC.line_kinds({"text": "이거 바르고 저거 발라", "emph": [{"word": "이거", "hex": "#65FEFB"}, {"word": "저거", "hex": "#BDB4FC"}]}) == ["multi_color"]


def test_card_scene_frame_reads_jpg(tmp_path):
    """그림 컷(본인 사진 jpg) 프레임 — ffmpeg 는 jpg 에 -ss 를 붙이면 0프레임(10-26 v3 카드 A·접촉 시트 검정). 사보타주: 옛 thumb(-ss 늘 붙임) → None."""
    from PIL import Image
    from tools.calcopy.hybrid import thumb as TH
    p = tmp_path / "own_1_x.jpg"
    Image.new("RGB", (640, 360), (120, 30, 60)).save(p, quality=90)
    im, where = TH.card_scene_frame({"file": str(p), "ss": 0.5, "crop": [100, 0, 300, 300]}, {}, tmp_path, (540, 540))
    assert im is not None, where
