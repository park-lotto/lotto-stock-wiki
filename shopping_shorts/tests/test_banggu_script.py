# -*- coding: utf-8 -*-
"""방구석 칼카피 대본 — 규칙이 원본 12편을 통과시키고(정답을 반려하지 않는다), 어긋난 대본은 잡는지."""
import json
import os

import pytest

from shopping_shorts.channel_presets.banggu import material as mat, rules, script, spec

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "..", "..", "channel", "banggu", "scripts_2026-10-05.json")


def _gold():
    out = []
    for v in json.load(open(GOLD, encoding="utf-8"))["videos"]:
        L = [(g, t.replace("/", " ")) for g, t in v["lines"]]
        out.append((v["id"], {"kind": "hidden", "title": next(t for g, t in L if g == "T"),
                              "lines": [{"role": g, "text": t} for g, t in L if g not in ("T", "C")],
                              "comment": next((t for g, t in L if g == "C"), "")}))
    return out


@pytest.mark.parametrize("vid,s", _gold())
def test_originals_pass(vid, s):
    src = " ".join([s["title"]] + [L["text"] for L in s["lines"]])
    rej = rules.rejects(rules.lint(s, {"source_text": src}))
    assert not rej, "원본 %s 을 반려했다: %s" % (vid, rej)


def _ok():
    return {"kind": "hidden", "title": "살림 고수들이 쓴다는 고정 젤",
            "lines": [{"role": "소개", "text": "박물관에서 미술품을 붙잡아 두는 데 쓴다는 뮤지엄젤"},
                      {"role": "의문", "text": "하지만 사람들이 이걸 사는 이유는 단순히 물건을 세워 두려는 게 아니라는데"},
                      {"role": "살펴봄", "text": "제형을 살펴보니 콩알만큼만 떼어 붙여도 물건이 착 고정되고"},
                      {"role": "살펴봄", "text": "테이프처럼 누렇게 뜨거나 붙인 티가 나지도 않는다고 함"},
                      {"role": "꺾음", "text": "그러나 정작 살림 고수들이 꽂힌 포인트는 따로 있다는데"},
                      {"role": "진짜이유", "text": "그건 바로 떼어내도 자국이 하나도 남지 않아 아이랑 고양이 있는 집에서도 마음 놓고 쓸 수 있어서라고"}],
            "comment": "아니 이걸 왜 이제 알았냐 ㅋㅋ"}


SRC = "원래 박물관에서 미술품 고정하는 용도의 젤인데 콩알만큼 떼서 쓰면 착 고정 살림고수들 사이에선 유명 테이프처럼 티도 안 나고 떼어내도 자국 하나 안 남아서 아이랑 고양이 있는 집"


def _ids(s, src=SRC, **ctx):
    return {i.rule for i in rules.rejects(rules.lint(s, dict({"source_text": src}, **ctx)))}


def test_ok_passes():
    assert not _ids(_ok())


def test_flat_ending_rejected():
    s = _ok(); s["lines"][2]["text"] = "제형을 살펴보니 콩알만큼만 떼어 붙여도 물건이 착 고정됩니다"
    assert "bg_flat" in _ids(s)


def test_last_line_must_close():
    s = _ok(); s["lines"][-1]["text"] = "그건 바로 떼어내도 자국이 하나도 남지 않아 아이랑 고양이 있는 집에서도 마음 놓고 쓸 수 있다는 거"
    assert "bg_close" in _ids(s)


def test_unsourced_hype_and_number_rejected():
    s = _ok(); s["lines"][0]["text"] = "요즘 품절 대란이라는 3만 원짜리 뮤지엄젤"
    ids = _ids(s)
    assert "bg_unsourced" in ids and "bg_number" in ids


def test_comment_must_be_own_voice():
    s = _ok(); s["comment"] = "아 이건 무조건 사두어야겠다고 ㅋㅋ"
    assert "bg_comment_voice" in _ids(s)
    s["comment"] = "아 이걸 어떻게 참냐고 ㅋㅋ"
    assert not _ids(s)


def test_cta_and_you_rejected():
    s = _ok(); s["lines"][3]["text"] = "여러분도 한번 써보세요 링크는 댓글에 있다고 함"
    assert {"bg_you", "bg_cta"} <= _ids(s)


def test_seed_copy_rejected():
    s = _ok(); seed = "콩알만큼만 떼어 붙여도 물건이 착 고정되고 테이프처럼 누렇게 뜨지도 않는다고 함"
    s["lines"][2]["text"] = "콩알만큼만 떼어 붙여도 물건이 착 고정되고"
    assert "bg_copy" in _ids(s, seed_text=seed)


def test_material_keeps_only_quoted():
    srcs = [{"id": "seed", "text": SRC}]
    raw = {"surface": {"text": "미술품 고정", "quote": "원래 박물관에서 미술품 고정하는 용도의 젤인데"},
           "real": {"text": "떼어도 자국이 안 남음", "quote": "떼어내도 자국 하나 안 남아서"},
           "buzz": {"text": "해외 직구 1위", "quote": "해외 직구 사이트에서 판매 1위를 찍었다고"},
           "original": {"text": "업체 시공", "quote": ""}}
    kept, dropped = mat.verify(raw, srcs)
    assert set(kept) == {"surface", "real"}
    assert {n for n, _ in dropped} == {"buzz", "original"}
    assert mat.eligible(kept) == ["hidden"]
    assert mat.missing(kept)["substitute"] == ["original", "original_lack", "same_proof"]


def test_same_surface_and_real_is_not_a_contrast():
    srcs = [{"id": "seed", "text": SRC}]
    raw = {"surface": {"text": "떼어도 자국이 안 남는다", "quote": "떼어내도 자국 하나 안 남아서"},
           "real": {"text": "떼어도 자국이 안 남는다", "quote": "떼어내도 자국 하나 안 남아서"}}
    kept, _ = mat.verify(raw, srcs)
    assert mat.eligible(kept) == []


M = {"surface": {"text": "미술품 고정", "quote": "q"}, "real": {"text": "자국 없음", "quote": "q"},
     "real_who": {"text": "살림 고수들", "quote": "q"}, "kind_word": {"text": "고정 젤", "quote": ""}}


def test_signals_are_attached_by_code():
    out = {"title": "살림 고수들이 쓴다는 고정 젤", "intro": "미술품을 붙잡아 둔다는 뮤지엄젤",
           "doubt": "하지만 사람들이 이걸 사는 이유는 단순히 고정 때문이 아니라는데", "look": ["제형을 살펴보니 착 붙고"],
           "real": "그건 바로 자국이 안 남아서라고", "bonus": "", "comment": ""}
    s = script.to_script(out, "hidden", M)
    texts = [L["text"] for L in s["lines"]]
    assert texts[1].startswith("하지만 사람들이") and not texts[1].startswith("하지만 하지만")
    assert "그러나 정작 살림 고수들이 꽂힌 포인트는 따로 있다는데" in texts
    assert texts[-1].startswith("그건 바로 자국이") and "그건 바로 그건" not in texts[-1]


def test_generate_rewrites_then_passes_and_refuses_without_material():
    good = {"title": _ok()["title"], "intro": _ok()["lines"][0]["text"],
            "doubt": "사람들이 이걸 사는 이유는 단순히 물건을 세워 두려는 게 아니라는데",
            "look": ["제형을 살펴보니 콩알만큼만 떼어 붙여도 물건이 착 고정되고", "테이프처럼 누렇게 뜨거나 붙인 티가 나지도 않는다고 함"],
            "real": "떼어내도 자국이 하나도 남지 않아 아이랑 고양이 있는 집에서도 마음 놓고 쓸 수 있어서라고", "bonus": "", "comment": "아니 이걸 왜 이제 알았냐 ㅋㅋ"}
    bad = dict(good, real="떼어내도 자국이 하나도 남지 않아 아이랑 고양이 있는 집에서도 마음 놓고 쓸 수 있습니다")
    answers = [json.dumps(bad, ensure_ascii=False), json.dumps(good, ensure_ascii=False)]
    seen = []

    def call(prompt):
        seen.append(prompt)
        return answers[len(seen) - 1]
    s, issues, attempts = script.generate("뮤지엄젤", "hidden", M, call, source_text=SRC, log=lambda *_: None)
    assert attempts == 2 and not rules.rejects(issues)
    assert "재작성 지시" in seen[1] and "평서 종결" in seen[1]
    with pytest.raises(ValueError):
        script.generate("뮤지엄젤", "substitute", M, call, source_text=SRC, log=lambda *_: None)


def test_title_and_intro_must_not_repeat():
    s = _ok(); s["title"] = "미술품을 붙잡아 두는 데 쓴다는 뮤지엄젤"
    assert "bg_repeat" in _ids(s)


def test_button_click_is_not_cta():
    s = _ok(); s["lines"][3]["text"] = "버튼 클릭으로 3단계 온도를 조절한다고 함"
    assert "bg_cta" not in _ids(s)


def test_long_kind_word_dropped_and_best_merges():
    srcs = [{"id": "seed", "text": SRC}, {"id": "b", "text": "다른 영상의 말 테이프로 붙이면 누렇게 떠서 보기 싫었는데 이건 티가 안 남"}]
    kept, dropped = mat.verify({"kind_word": {"text": "도넛 모양 보강 스티커 및 전용 스탬프", "quote": ""}}, srcs)
    assert "kind_word" not in kept and dropped
    answers = iter([json.dumps({"how": {"text": "티가 안 남", "quote": "테이프로 붙이면 누렇게 떠서 보기 싫었는데 이건 티가 안 남"}}, ensure_ascii=False),
                    "JSON 아님", json.dumps({"real": {"text": "자국 없음", "quote": "떼어내도 자국 하나 안 남아서"}}, ensure_ascii=False)])
    note = {}
    m = mat.extract_best(srcs, "뮤지엄젤", lambda p: next(answers), note=note)
    assert set(m) == {"how", "real"} and note["material_from"] == {"how": "all", "real": "seed"}
