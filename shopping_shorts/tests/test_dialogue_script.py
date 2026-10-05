# -*- coding: utf-8 -*-
import pytest

from shopping_shorts import dialogue_script as ds

SRC = ["이제 충전 케이블 보호기 이걸로 끝났음",
       "밋밋한 케이블 쓰던 사람들 사이에서 난리라는데",
       "이건 바로 강아지 케이블 커버.",
       "툭하면 꺾여서 단선되던 단자를 파란 강아지가 꽉 물어 지켜 버림"]


def _good():
    return {"lines": [
        {"speaker": "나레이션", "text": "이제 충전 케이블 보호기 이걸로 끝났음.", "tag": "", "src": [0]},
        {"speaker": "나레이션", "text": "밋밋한 케이블 쓰던 사람들 사이에서 난리라는데, 이건 바로 강아지 케이블 커버.", "tag": "", "src": [1, 2]},
        {"speaker": "동생", "text": "근데 단자 맨날 꺾이잖아?", "tag": "[Doubtful]", "src": [3]},
        {"speaker": "언니", "text": "파란 강아지가 꽉 물고 있어서 지켜 줘.", "tag": "excited", "src": [3]},
    ]}


def test_convert_ok_and_tag_normalized():
    out = ds.convert(SRC, "narr_then_talk", call=lambda p, s: _good())
    assert [o["speaker"] for o in out] == ["나레이션", "나레이션", "동생", "언니"]
    assert out[2]["tag"] == "doubtful"          # 대괄호·대문자 정리
    assert ds.script_text(out).count("\n") == 3
    assert "[" not in ds.script_text(out)


def test_new_number_rejected():
    bad = _good(); bad["lines"][3]["text"] = "2만 원대인데 꽉 물고 있어."
    with pytest.raises(ValueError, match="숫자"):
        ds.convert(SRC, "narr_then_talk", call=lambda p, s: bad)


def test_dropped_line_rejected():
    bad = _good(); bad["lines"][3]["src"] = [2]; bad["lines"][2]["src"] = [2]
    with pytest.raises(ValueError, match="빠짐"):
        ds.convert(SRC, "narr_then_talk", call=lambda p, s: bad)


def test_wrong_speaker_and_bracket_rejected():
    bad = _good(); bad["lines"][2]["speaker"] = "아빠"; bad["lines"][3]["text"] = "[laughs] 지켜 줘"
    errs = ds.check(SRC, [{**l, "tag": ""} for l in bad["lines"]], "narr_then_talk")
    assert any("틀 밖" in e for e in errs) and any("대괄호" in e for e in errs)


def test_remap_and_meta():
    out = ds.convert(SRC, "narr_then_talk", call=lambda p, s: _good())
    srcs = ["s0", "s1", "s2", "s3"]
    assert ds.remap_beat_sources(srcs, out) == ["s0", "s1", "s3", "s3"]
    m = ds.meta("narr_then_talk", out, {"언니": "kr-hanna-natural", "모르는": "x"})
    assert m["cast"]["언니"] == "kr-hanna-natural" and "모르는" not in m["cast"]
    assert len(m["lines"]) == len(out) and "text" not in m["lines"][0]


def test_every_form_has_cast_for_each_role():
    for k, f in ds.FORMS.items():
        assert set(f["cast"]) == set(f["roles"]), k


def test_cut_and_punct_rejected():
    out = [{"speaker": "나레이션", "text": "이제 끝났음", "tag": "", "src": [0, 1, 2]},
           {"speaker": "동생", "text": "볼 때마다 답답했던 그 스트레스를", "tag": "", "src": [3]},
           {"speaker": "언니", "text": "지켜 줘.", "tag": "", "src": [3]}]
    errs = ds.check(SRC, out, "narr_then_talk")
    assert any("조사로 끊김" in e for e in errs) and any("문장 부호" in e for e in errs)
