# -*- coding: utf-8 -*-
"""씨앗을 뼈대로 쓸 때는 **씨앗의 화자·말투·관용구 자리**를 지킨다 (2026-09-21).

★왜 생겼나(사장님 화면 확인 09-21 12:40, A안 결함):
  ①씨앗은 반말 소개체인데 결과가 "저도 아내 쓰라고 장만했습니다"(남편 1인칭 존댓말)로 바뀜
  ②씨앗 관용구 칸("이건 바로 OO"/"근데 진짜 미친 포인트는")이 빠짐
  뿌리: 원문형 프롬프트의 "사람·장소는 [상황표]를 따른다. 원문의 인물 배치를 베끼지 마라"
        + "원문의 원래 제품 이야기는 한 조각도 남기지 마라" — **남의 히트작**을 빌릴 때 규칙이다.
        씨앗은 **같은 제품**의 영상이라 이 규칙들이 거꾸로 작동한다.
"""
from shopping_shorts import backbone_assemble as ba

_SEED_CELLS = [
    {"role": "훅", "text": "이건 바로 접이식 빨래 바구니임"},
    {"role": "불편", "text": "이게 말도 안 되는 게 다 접으면 손바닥만 해짐"},
    {"role": "전환", "text": "근데 진짜 미친 포인트는 물이 안 샌다는 거"},
    {"role": "감정", "text": "이러니 다들 난리가 난 거"},
]
_GROUPS = {"product": "접이식 바구니", "order": [0],
           "groups": [{"name": "접힘", "claim": "납작하게 접힌다", "cuts": []}]}


def _patch(monkeypatch, answers):
    """_call_json을 가로채 프롬프트를 모으고, 차례로 준비한 답을 돌려준다."""
    seen = []

    def fake(prompt, schema, note=None):
        seen.append(prompt)
        return answers[min(len(seen), len(answers)) - 1]
    monkeypatch.setattr(ba._sg, "_call_json", fake)
    return seen


def _lines(texts):
    return {"lines": [{"role": c["role"], "group": -1, "text": t} for c, t in zip(_SEED_CELLS, texts)]}


_GOOD = ["이건 바로 접이식 바구니임", "이게 말도 안 되는 게 접으면 손바닥만 해짐",
         "근데 진짜 미친 포인트는 물을 담아도 안 샘", "이러니 다들 난리가 난 거"]
_BAD_VOICE = ["저도 아내 쓰라고 장만했습니다", "접으면 정말 작아져요", "물도 안 새더라고요", "다들 좋아하세요"]


def test_seed_origin_skips_cast_table_and_keeps_seed_voice_rules(monkeypatch):
    """씨앗 뼈대면 상황표(전제→상황표→대조)를 아예 안 만들고, 프롬프트가 화자·관용구를 지키라고 말한다."""
    seen = _patch(monkeypatch, [_lines(_GOOD)])
    note = {}
    out = ba.write_lines_from_origin({"cells": _SEED_CELLS, "views": 100, "seed": True},
                                     _GROUPS, {}, {}, note=note)
    assert len(seen) == 1, "씨앗 뼈대인데 상황표용 모델 호출이 더 나갔다: %d회" % len(seen)
    p = seen[0]
    assert "인물 배치를 베끼지 마라" not in p
    assert "한 조각도 남기지 마라" not in p
    assert "화자" in p and "말투" in p
    assert [l["text"] for l in out][0].startswith("이건 바로")
    assert not (note.get("seed_voice") or {}).get("issues")


def test_seed_origin_retries_once_when_voice_flips(monkeypatch):
    """반말 씨앗인데 존댓말 1인칭으로 나오면 1회 다시 쓰고, 나아진 쪽을 쓴다."""
    seen = _patch(monkeypatch, [_lines(_BAD_VOICE), _lines(_GOOD)])
    note = {}
    out = ba.write_lines_from_origin({"cells": _SEED_CELLS, "views": 100, "seed": True},
                                     _GROUPS, {}, {}, note=note)
    assert len(seen) == 2
    assert "[고칠 점]" in seen[1]
    assert out[1]["text"].startswith("이게 말도 안 되는 게")
    assert not (note.get("seed_voice") or {}).get("issues")


def test_seed_voice_gap_detects_flip_and_missing_openers():
    gaps = ba.seed_voice_gap([{"text": t} for t in _BAD_VOICE], _SEED_CELLS)
    assert any("말투" in g for g in gaps)
    assert any("첫머리" in g for g in gaps)
    assert ba.seed_voice_gap([{"text": t} for t in _GOOD], _SEED_CELLS) == []


def test_seed_voice_gap_reports_cell_count_mismatch():
    gaps = ba.seed_voice_gap([{"text": t} for t in _GOOD[:2]], _SEED_CELLS)
    assert any("칸 수" in g for g in gaps)


def test_borrowed_origin_still_uses_cast_table(monkeypatch):
    """남의 히트작을 빌리는 종전 경로는 그대로다(상황표 규칙 유지) — 회귀 방지."""
    seen = _patch(monkeypatch, [{"who": "x"}, {"fit": True, "opening": "o"}, _lines(_GOOD), {"issues": []}])
    ba.write_lines_from_origin({"cells": _SEED_CELLS, "views": 100}, _GROUPS, {}, {}, note={})
    assert any("인물 배치를 베끼지 마라" in p for p in seen)


def test_seed_voice_gap_catches_paraphrased_idiom():
    """첫 어절은 같아도 관용구를 바꿔 쓰면 잡는다(격리 실측: '이게 말도 안 되는 게' → '이게 정말 편한 게')."""
    cells = [dict(c, fixed=f) for c, f in zip(_SEED_CELLS, (["이건 바로"], ["이게 말도 안 되는 게"],
                                                            ["근데 진짜 미친 포인트는"], []))]
    para = [_GOOD[0], "이게 정말 편한 게 접으면 손바닥만 해짐", "근데 진짜 대박인 건 물이 안 샘", _GOOD[3]]
    gaps = ba.seed_voice_gap([{"text": t} for t in para], cells)
    assert any("이게 말도 안 되는 게" in g and "근데 진짜 미친 포인트는" in g for g in gaps)
    assert ba.seed_voice_gap([{"text": t} for t in _GOOD], cells) == []


def test_origin_from_seed_retries_and_keeps_only_real_fixed(monkeypatch):
    """칸 나누기가 한 번 빈손이어도 다시 하고, 원문에 없는 '관용구'는 고정하지 않는다."""
    monkeypatch.setattr(ba.time, "sleep", lambda s: None)
    good = {"lines": [{"role": c["role"], "text": c["text"], "fixed": ["이건 바로", "지어낸 말"]} for c in _SEED_CELLS]}
    seen = _patch(monkeypatch, [{}, good])
    o = ba.origin_from_seed({"full_text": " ".join(c["text"] for c in _SEED_CELLS), "video_id": "s1"})
    assert len(seen) == 2 and o and o["seed"] is True
    assert o["cells"][0]["fixed"] == ["이건 바로"]
    assert all("지어낸 말" not in (c["fixed"] or []) for c in o["cells"])


def test_origin_from_seed_failure_is_not_silent(monkeypatch):
    monkeypatch.setattr(ba.time, "sleep", lambda s: None)
    _patch(monkeypatch, [{}])
    note = {}
    assert ba.origin_from_seed({"full_text": "가" * 80}, note=note) is None
    assert "seed_origin_failed" in note


def test_seed_voice_gap_catches_body_copied_from_seed():
    """본문 줄이 씨앗과 6어절 넘게 같으면 잡는다. 훅(첫 칸)과 짧은 관용구는 그대로여도 된다."""
    cells = [{"role": "훅", "text": "출산 맘들 환장하게 만든 천재의 발명품"},
             {"role": "계기", "text": "언뜻 봤을 땐 그냥 평범한 빗처럼 생긴 이 제품이 미친듯이 팔리고 있다는데"},
             {"role": "감정", "text": "이러니 다들 난리가 난 거"}]
    copied = ["출산 맘들 환장하게 만든 천재의 발명품", "언뜻 봤을 땐 그냥 평범한 빗처럼 생긴 이 제품이 요즘 난리라는데",
              "이러니 다들 난리가 난 거"]
    fresh = [copied[0], "겉보기엔 흔한 빗인데 요즘 이거 없어서 못 산다는데", copied[2]]
    assert any("그대로 옮겼다" in g for g in ba.seed_voice_gap([{"text": t} for t in copied], cells))
    assert ba.seed_voice_gap([{"text": t} for t in fresh], cells) == []


def test_one_full_name_keeps_first_mention_when_no_reveal_role():
    """reveal 줄이 없는 경로(원문형·씨앗)에선 처음 나온 제품 이름을 남긴다 — "이건 바로 빗" 방지."""
    lines = [{"role": "전환", "text": "이건 바로 두피 액체빗"}, {"role": "작동", "text": "두피 액체빗 안에 토닉을 넣으면 됨"}]
    out = ba._one_full_name(lines, "두피 액체빗")
    assert out[0]["text"] == "이건 바로 두피 액체빗"
    assert out[1]["text"] == "액체빗 안에 토닉을 넣으면 됨"


def test_one_full_name_reveal_role_behaviour_unchanged():
    """틀 경로(reveal 줄 있음)는 종전 그대로: reveal만 전체 이름, 나머지는 줄인다."""
    lines = [{"role": "hook", "text": "두피 액체빗 이거 뭐임"}, {"role": "reveal", "text": "이건 두피 액체빗"}]
    out = ba._one_full_name(lines, "두피 액체빗")
    assert out[0]["text"] == "액체빗 이거 뭐임" and out[1]["text"] == "이건 두피 액체빗"


def test_seed_voice_gap_catches_single_polite_line_in_banmal_seed():
    """반말 씨앗에 한 줄만 존댓말·권유가 끼어도 잡는다(비율 문턱 0.4로는 못 잡던 것)."""
    one_odd = _GOOD[:3] + ["가방에 넣고 다니며 꺼내 써보세요"]
    gaps = ba.seed_voice_gap([{"text": t} for t in one_odd], _SEED_CELLS)
    assert any("이 줄만 다르다" in g for g in gaps)


def test_origin_from_seed_merges_idiom_only_cell_into_next(monkeypatch):
    """관용구만 있는 칸은 다음 칸 첫머리로 붙인다 — 내용 없는 한 줄이 생기지 않게."""
    monkeypatch.setattr(ba.time, "sleep", lambda s: None)
    raw = {"lines": [{"role": "훅", "text": "출산 맘들 환장하게 만든 천재의 발명품"},
                     {"role": "전환", "text": "이건 바로 두피 액체빗", "fixed": ["이건 바로"]},
                     {"role": "심지어", "text": "근데 진짜 미친 포인트는", "fixed": ["근데 진짜 미친 포인트는"]},
                     {"role": "감정", "text": "남편이 이거 하나 선물해주면 사랑받기 딱 좋다고"}]}
    _patch(monkeypatch, [raw])
    o = ba.origin_from_seed({"full_text": "가" * 80, "video_id": "s1"})
    assert [c["role"] for c in o["cells"]] == ["훅", "전환", "심지어"]
    assert o["cells"][2]["text"] == "근데 진짜 미친 포인트는 남편이 이거 하나 선물해주면 사랑받기 딱 좋다고"
    assert o["cells"][1]["text"] == "이건 바로 두피 액체빗"      # 내용이 있는 칸은 안 붙인다
