"""이야기 작가 연결(story_writer.make_drafts) — 대본 먼저, 컷은 뒤에. 모델은 가짜로 막는다.

재는 것: ①고조 줄이 **근거 특징의 컷**을 받는가 ②씨앗 영상 컷은 안 쓰는가 ③신호어가 따로 한 줄이 아닌가
        ④못 만들면 이유를 말하는가(조용한 폴백 금지) ⑤스위치가 꺼져 있으면 호출 자체가 없는가
"""
from shopping_shorts import story_writer as sw


def _seg(v, i, desc="장면"):
    return {"seg_id": "%s-%d" % (v, i), "start": i * 3, "end": i * 3 + 3, "scene_desc": desc}


def _job():
    seed = "이거 진짜 말도 안 되는 물건인데 다들 모르더라. " * 4
    return {"backbone_main": 0, "extract": {
        "s0": {"video_id": "s0", "full_text": seed, "source_brief": {"product": "두피 액체빗"},
               "segments": [_seg("SEED", i) for i in range(6)]},
        "s1": {"video_id": "s1", "full_text": "", "segments": [_seg("MAT", i) for i in range(12)]},
    }}


FEATS = [{"name": "앰플 도포", "claim": "빗 뒷면에 앰플을 채워 바른다",
          "pain": "손가락 사이로 다 흘러내리고 머리만 떡져서", "from_cuts": ["MAT-3", "MAT-4", "NOPE-9"]},
         {"name": "휴대", "claim": "가방에 들어간다", "pain": "큰 병을 들고 다녀야 했다", "from_cuts": ["MAT-7"]}]

YT_OUT = {"hook": "이걸 아직도 손으로 바른다고", "bait": "요새 이거 하나로 난리인데", "reveal": "이건 바로 두피 액체빗.",
          "contrast": "", "twist": "근데 가방에도 쏙 들어가서", "closing": "쓰는 사람마다 난리라는데",
          "escalations": [{"moment": "겨우 짜서 바르려는 순간", "what_happens": "손가락 사이로 다 흘러내리던 그 짜증을",
                           "erased": "빗 안에 넣어서 없애 버렸다는 거", "from_pain": "앰플 도포"}]}


def _fake(monkeypatch, out=YT_OUT, feats=FEATS):
    calls = []

    def call(prompt, schema, note=None):
        calls.append(schema)
        return {"feats": feats} if schema is sw.FEATS_SCHEMA else out
    monkeypatch.setattr(sw._sg, "_call_json", call)
    return calls


def test_lines_get_feature_cuts_and_no_seed_cuts(monkeypatch):
    calls = _fake(monkeypatch)
    drafts, why = sw.make_drafts([], _job(), job_id="j1")
    assert why == "" and len(drafts) == 1 and len(calls) == 2      # 특징 1회 + 자동 1안 1회
    d = drafts[0]
    assert d["auto_pick"] is True and d["made_by"] == "이야기작가" and d["platform"] == "yt"
    esc = [b for b in d["beats"] if b["role"] == "고조1"]
    assert len(esc) == 3
    assert esc[0]["src_seg"] in ("MAT-3", "MAT-4")                  # 근거 특징의 컷(없는 번호 NOPE-9는 걸러진다)
    used = [s for b in d["beats"] for s in b["src_segs"]]
    assert used and not any(s.startswith("SEED") for s in used)     # 화면은 씨앗 영상을 안 쓴다
    assert all(b["src_segs"] for b in d["beats"])                   # 컷 없는 줄 없음


def test_signal_word_is_not_its_own_line(monkeypatch):
    _fake(monkeypatch)
    for key in ("a", "b", "c", "d", "e", "f", "g", "h"):            # 세트가 달라도
        lines = sw._to_lines(YT_OUT, False, key, 0, FEATS)
        sigs = {s for v in sw.YT_SETS.values() for s in v if s}
        assert not any(L["text"] in sigs for L in lines)
        assert sum(1 for L in lines if L["role"] == "고조1") == 3


def test_picked_style_adds_second_draft(monkeypatch):
    calls = _fake(monkeypatch)
    sp = {"id": 61, "name": "고른 스타일", "no_cta": True, "beat_roles": ["훅", "고조"]}
    drafts, _ = sw.make_drafts([sp, {"id": 62, "name": "둘째"}], _job(), job_id="j1")
    assert [d["style_name"] for d in drafts] == ["씨앗 결 이야기", "고른 스타일"]
    assert [d["auto_pick"] for d in drafts] == [True, False] and len(calls) == 3


def test_reasons_are_reported(monkeypatch):
    _fake(monkeypatch, feats=[])
    assert sw.make_drafts([], _job()) == ([], "특징을 못 뽑음(빈 응답)")
    _fake(monkeypatch, out={})
    drafts, why = sw.make_drafts([], _job())
    assert drafts == [] and "0줄" in why
    short = _job()
    short["extract"]["s0"]["full_text"] = "짧다"
    drafts, why = sw.make_drafts([], short)
    assert drafts == [] and "짧음" in why
    assert sw.make_drafts([], {"extract": {}})[1]


def test_empty_line_borrows_spare_cut_only():
    """빈 줄은 넉넉한 줄에서 컷을 받는다. 단 빼면 대사를 못 덮는 줄에서는 안 뺀다."""
    idx = {"A-%d" % i: {"secs": 3.0} for i in range(4)}
    lines = [{"role": "훅", "text": "가" * 12}, {"role": "마무리", "text": "나" * 12},
             {"role": "공개", "text": "다" * 12}]
    bs = [{"role": "훅", "seg": "A-0", "segs": ["A-0", "A-1", "A-2"]}, None,
          {"role": "공개", "seg": "A-3", "segs": ["A-3"]}]
    assert sw._share_cuts(lines, bs, idx) == []
    assert bs[1]["segs"] and bs[1]["seg"] == bs[1]["segs"][0]
    assert bs[2]["segs"] == ["A-3"] and len(bs[0]["segs"]) >= 1
    tight = [{"role": "훅", "seg": "A-0", "segs": ["A-0"]}, None]
    assert sw._share_cuts(lines[:2], tight, idx) == [1] and tight[0]["segs"] == ["A-0"]


def test_model_written_line_does_not_repeat_signal():
    out = dict(YT_OUT, twist="심지어 가방에도 쏙 들어가서")
    for key in ("a", "b", "c", "d", "e", "f", "g", "h"):
        lines = sw._to_lines(out, False, key, 0, FEATS)
        _, sigs = sw._pick(sw.YT_SETS, key, 0)
        twist = next(L["text"] for L in lines if L["role"] == "반전")
        assert twist.startswith("심지어") == ("심지어" not in sigs)


def test_feature_number_beats_paraphrased_text():
    """모델이 근거를 **풀어 써도** 번호(feat)로 재료에 걸린다(실측: 글자 대조는 절반이 -1이었다)."""
    out = dict(YT_OUT, escalations=[dict(YT_OUT["escalations"][0], from_pain="바르기 고민 해결", feat=2)])
    lines = sw._to_lines(out, False, "k", 0, FEATS)
    assert {L["group"] for L in lines if L["role"] == "고조1"} == {1}
    bad = dict(YT_OUT, escalations=[dict(YT_OUT["escalations"][0], feat=9)])       # 없는 번호 → 글자 대조로
    assert {L["group"] for L in sw._to_lines(bad, False, "k", 0, FEATS) if L["role"] == "고조1"} == {0}
    assert "1. 앰플 도포" in sw._feats_block(FEATS) and "2. 휴대" in sw._feats_block(FEATS)


def test_too_long_script_drops_whole_escalations_from_the_end():
    L = lambda r, n: {"role": r, "text": "가" * n, "group": -1}
    lines = [L("훅", 20), L("고조1", 40), L("고조1", 40), L("고조2", 40), L("고조2", 40), L("고조3", 40), L("마무리", 20)]
    out, dropped = sw._fit_length(lines, 25)
    assert dropped == 2 and [x["role"] for x in out] == ["훅", "고조1", "고조1", "마무리"]   # 최소 1칸은 남는다
    assert sw._fit_length(lines, 999) == (lines, 0)
