# -*- coding: utf-8 -*-
"""자막 한 줄 글자 상한 + 단순 분할 규칙(2026-09-26 사장님 "너무 길게 나뉘면 템플릿에 넘친다 / 규칙을 심플하게")."""
from shopping_shorts import video_assemble as va
from shopping_shorts import mix_pipeline as mp


def _flat(x):
    return len(x.replace(" ", ""))


def test_한줄은_상한을_안넘고_글자는_그대로():
    t = "여러분 오이 절대 냉장고에 그냥 두지 마세요 버리기 일쑤였는데 이 방법은 진짜 남겨주시면 자세한 보관비법 바로 알려드릴게요"
    out = va.simple_caption_split(t, 10)
    assert all(_flat(x) <= 10 for x in out), out
    assert "".join(out).replace(" ", "") == t.replace(" ", "")
    assert all(len(x.split()) >= 1 for x in out)


def test_문장부호_뒤에서_끊는다():
    out = va.simple_caption_split("비밀 테이블이 있어요. 근데 진짜 충격적인 포인트는", 12)
    assert out[0] == "비밀 테이블이 있어요."


def test_연결어미_뒤를_우선한다():
    # 창(10자) 안에 '일쑤였는데'가 있으면 거기서 끊는다 — 마지막 어절이 아니라
    out = va.simple_caption_split("버리기 일쑤였는데 이 방법은 진짜 대박", 10)
    assert out[0] == "버리기 일쑤였는데", out


def test_한글자_관형사_뒤에서는_안끊는다():
    out = va.simple_caption_split("냉장고에 그냥 두지 마세요 이 방법은 진짜 좋아요", 10)
    for x in out:
        assert not x.endswith((" 이", " 그", " 안", " 더")), out
    assert not any(x == "이" for x in out)


def test_고아_어절은_앞줄에서_하나_가져온다():
    out = va.simple_caption_split("자세한 보관비법 바로 알려드릴게요 여러분", 12)
    assert len(out[-1].split()) >= 2, out


def test_상한_0이면_한줄():
    assert va.simple_caption_split("가 나 다", 0) == ["가 나 다"]
    assert va.simple_caption_split("", 10) == []


class _S:
    def __init__(self, v): self.v = v
    def get_setting(self, k, d=""): return self.v if k == "caption_max_chars" else d


def test_설정_규약과_표식():
    plan = {"beats": [{"beat_idx": 0}, {"beat_idx": 1, "caption_max_chars": 8}]}
    assert mp._apply_caption_max_chars(plan, _S("admin:10"), {"customer_id": 0}) == 1
    assert [b["caption_max_chars"] for b in plan["beats"]] == [10, 8]
    plan2 = {"beats": [{"beat_idx": 0}]}
    assert mp._apply_caption_max_chars(plan2, _S("admin:10"), {"customer_id": 77}) == 0
    assert "caption_max_chars" not in plan2["beats"][0]
    assert mp._apply_caption_max_chars({"beats": [{}]}, _S(""), {"customer_id": 0}) == 0
    assert mp._gated_number(_S("admin"), {"customer_id": 0}, "caption_max_chars", 10) == 10.0


def test_표식칸은_AI없이도_단순규칙으로_줄이_생긴다():
    # pytest 가드로 ai_breath_lines는 None → 표식 칸은 단순 규칙, 표식 없는 칸은 종전(None=규칙 폴백)
    narr = "여러분 오이 절대 냉장고에 그냥 두지 마세요 버리기 일쑤였는데 이 방법은 진짜 남겨주시면 자세한 보관비법 바로 알려드릴게요"
    b = {"narration": narr, "caption_max_chars": 10}
    mp._ensure_breath_lines(b)
    assert b["caption_lines"] and all(_flat(x) <= 10 for x in b["caption_lines"]), b["caption_lines"]
    assert va.cap_preset_key("".join(b["caption_lines"])) == va.cap_preset_key(narr)
    # 렌더·화면이 쓰는 함수가 그 줄을 그대로 채택한다(재분할 없음)
    assert va._caption_segments(narr, b["caption_lines"]) == b["caption_lines"]
    b2 = {"narration": narr}
    mp._ensure_breath_lines(b2)
    assert b2["caption_lines"] is None


def test_AI줄이_상한을_넘으면_그줄만_다시_나눈다(monkeypatch):
    from shopping_shorts import script_generate as sg
    narr = "인테리어 고수들만 안다는 비밀 테이블이 있어요"
    monkeypatch.setattr(sg, "ai_breath_lines", lambda n, max_chars=None: ["인테리어 고수들만 안다는 비밀", "테이블이 있어요"])
    b = {"narration": narr, "caption_max_chars": 8}
    mp._ensure_breath_lines(b)
    assert all(_flat(x) <= 8 for x in b["caption_lines"]), b["caption_lines"]
    assert b["caption_lines"][-1] == "테이블이 있어요"
