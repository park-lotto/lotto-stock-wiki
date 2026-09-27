"""이야기 작가(story_writer.make_drafts → write_styled 한 번 호출) — 모델은 가짜로 막는다.

재는 것: ①안마다 호출 한 번·고른 스타일 칸 순서 그대로 ②없는 컷 번호는 버린다 ③검사(칸 순서·씨앗 되풀이·
        A·B 겹침·틀 예시 베낌·분량)에 걸리면 이유를 붙여 한 번 다시 쓴다 ④못 만들면 이유를 말한다 ⑤고른 씨앗이 결을 정한다
"""
from shopping_shorts import story_writer as sw


def _seg(v, i, desc="장면"):
    return {"seg_id": "%s-%d" % (v, i), "start": i * 3, "end": i * 3 + 3, "scene_desc": desc}


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


def test_seed_platform_counts_deoragoyo_as_polite():
    """2026-09-22 실측: "~더라고요"×3 + "남겨주세요" 씨앗이 썰(반말)로 판정돼 존댓말 체험담이 반말로 써졌다."""
    seed = ("차량용품 중에 제일 잘 산 아이템 꼽으라면 이게 1등이더라고요 컵홀더에 물 놔두려고 하면 항상 꽉 차 있고 "
            "사이드 수납 공간에 두면 꺼내기도 불편했는데 이거 하나 차문 쪽에 딱 달아 주니까 음료나 커피 넣어두기도 좋고 "
            "운전하면서 꺼내 마시기도 훨씬 수월하더라고요 가격도 저렴해서 보조석이랑 뒷좌석에도 하나씩 달아놨더니 "
            "간단한 짐이나 쓰레기통으로도 쓸 수 있어서 활용도가 진짜 좋은데 차에 타는 지인들마다 이거 어디서 샀냐고 "
            "항상 물어보더라고요 댓글에 '홀더' 남겨주세요")
    assert sw.seed_platform(seed) == "ig"
    yt = ("출산 맘들 환장하게 만든 천재의 발명품 언뜻 봤을 땐 그냥 평범한 빗처럼 생긴 이 제품이 미친듯이 팔리고 있다는데 "
          "이건 바로 두피 액체빗 이게 말도 안 되는 게 앰플을 손으로 바르면 골고루 바르기도 어려웠는데 "
          "근데 진짜 미친 포인트는 남편이 선물해주면 사랑받기 딱 좋다고")
    assert sw.seed_platform(yt) == "yt"


def test_seed_platform_splits_glued_sentences():
    """자막을 이어 붙여 문장 사이 띄어쓰기가 없는 전사(실측 homeditor_)도 존댓말로 본다."""
    glued = "여러분 대파 절대 안 돼요저도 매번 그랬거든요기사 식당 이모님 말씀이래요냉동 보관하면 향이 다 날아가요그래서 이렇게 하더라고요"
    assert sw.seed_platform(glued) == "ig"


def test_seed_content_hits_ignore_product_words():
    pts = ["최대 40시간 배터리", "비싼 스포츠 이어폰 자리 빼앗음", "방수 기능"]
    assert sw._seed_word_hits("가격대까지 비싼 스포츠 브랜드 제품을 압도해 버렸고", pts, "무선 이어폰") == ["비싼", "스포츠"]
    assert sw._seed_word_hits("귀걸이처럼 예쁜 이어폰이라고", pts, "무선 이어폰") == []      # 제품명 낱말은 안 센다


# ── 한 번 호출 작가(write_styled, 2026-09-27) ─────────────────────────────────────────────
SEED = "개발자도 예상 못한 한국 주부의 활용법 평범한 필름지처럼 보이는 이 제품으로 리모컨을 감싸 드라이어를 쏘면 딱 달라붙는다는데 이건 바로 열수축 필름."
SPINE = {"id": 74, "name": "유튜브 「OO의 정체」", "no_cta": True, "beat_roles": ["title", "bait", "reveal", "twist"],
         "templates": {"title": ["{나라} 천재가 만든 이 제품의 정체"], "bait": ["요즘 난리라는데"]}}


def _styled_job():
    return {"backbone_main": None, "extract": {
        "s1": {"video_id": "s1", "full_text": "", "segments": [_seg("MAT", i) for i in range(10)]}}}


def _lines(roles, cut="MAT-1", word=""):
    return [{"role": r, "text": word + "%s 칸에 들어갈 충분히 긴 한 줄 대사인데 분량을 맞추려고 조금 더 길게 이어서 말하는 거" % r, "cuts": [cut, "NOPE-9"]} for r in roles]


def _fake_styled(monkeypatch, outs):
    """outs: 호출 순서대로 돌려줄 응답들(모자라면 마지막 것을 되풀이). 받은 프롬프트를 모은다."""
    prompts = []

    def call(prompt, schema, note=None, model=None, vertex=True):
        assert schema is sw.STYLED_SCHEMA, "안마다 한 번 호출 — 특징 뽑기 같은 다른 호출은 없어야 한다"
        prompts.append(prompt)
        if note is not None:
            note["auth"] = "vertex"
        return outs[min(len(prompts) - 1, len(outs) - 1)]
    monkeypatch.setattr(sw._sg, "_call_json", call)
    return prompts


def test_one_call_per_draft_keeps_style_roles_and_valid_cuts(monkeypatch):
    seed_out = {"seed_points": ["리모컨 감싸기"], "lines": _lines(["훅", "미끼", "공개", "고조", "마무리"], "MAT-2")}
    style_out = {"seed_points": ["리모컨 감싸기"], "lines": [dict(L, text="둘째 안 %d번은 완전히 다른 특징과 다른 문장으로 가위 없이 손으로 찢어지고 접착 자국도 안 남는다는데" % i) for i, L in enumerate(_lines(["title", "bait", "reveal", "reveal", "twist"], "MAT-5"))]}
    prompts = _fake_styled(monkeypatch, [seed_out, style_out])
    drafts, why = sw.make_drafts([SPINE], _styled_job(), job_id="j1", seed_text=SEED, seed_product="열수축 필름")
    assert why == "" and len(drafts) == 2 and len(prompts) == 2
    a, b = drafts
    assert a["auto_pick"] and a["style_name"] == "씨앗 결 이야기"
    assert [x["role"] for x in b["beats"]] == ["title", "bait", "reveal", "reveal", "twist"], "고른 스타일의 칸이 그대로"
    assert all(x["src_segs"] == ["MAT-5"] for x in b["beats"]), "없는 컷 번호(NOPE-9)는 버리고 적은 컷을 쓴다"
    assert "[스타일 틀]" in prompts[1] and "title:" in prompts[1] and "「{나라} 천재가" in prompts[1]
    assert "[다른 안" in prompts[1] and "[다른 안" not in prompts[0], "둘째 안은 첫 안과 다르게 쓰라는 지시를 받는다"
    assert b["writer_note"]["auth"] == "vertex"


def test_wrong_role_order_retries_once_with_reason(monkeypatch):
    bad = {"seed_points": [], "lines": _lines(["title", "reveal", "bait", "twist", "twist"])}
    good = {"seed_points": [], "lines": _lines(["title", "bait", "reveal", "twist", "twist"])}
    prompts = _fake_styled(monkeypatch, [bad, good])
    n = {}
    lines = sw.write_styled("열수축 필름", SEED, sw.frame_of(SPINE), [], {"MAT-1": {"secs": 3}}, note=n)
    assert len(prompts) == 2 and "칸 순서가 틀이 아니다" in prompts[1]
    assert [L["role"] for L in lines][:3] == ["title", "bait", "reveal"] and n["problems"] == []


def test_seed_repetition_only_after_opening_roles():
    frame = sw.frame_of(SPINE)
    out = {"seed_points": ["리모컨 드라이어 밀착"],
           "lines": [{"role": "title", "text": "리모컨에 드라이어 쏘면 밀착되는 필름", "cuts": ["MAT-1"]},
                     {"role": "bait", "text": "요즘 난리라는데 한 번 보면 안다는 거", "cuts": ["MAT-1"]},
                     {"role": "reveal", "text": "이건 바로 열수축 필름인데 그냥 필름이 아님", "cuts": ["MAT-1"]},
                     {"role": "twist", "text": "리모컨에 드라이어만 쏘면 끝이라는 거", "cuts": ["MAT-1"]},
                     {"role": "twist", "text": "가위 없이 손으로 찢어지는 게 진짜 미친 거", "cuts": ["MAT-1"]}]}
    probs = sw.styled_problems(out, frame, {"MAT-1": {}}, SEED, "열수축 필름", seconds=10)
    assert len(probs) == 1 and probs[0].startswith("4번 줄"), "제목 칸은 씨앗 셀링포인트를 써도 되고 본문 되풀이만 잡는다"


def test_ab_overlap_is_a_problem():
    frame = sw.frame_of(SPINE)
    out = {"seed_points": [], "lines": _lines(["title", "bait", "reveal", "twist", "twist"])}
    same = " ".join(L["text"] for L in out["lines"])
    assert any("[다른 안]" in p for p in sw.styled_problems(out, frame, {"MAT-1": {}}, avoid_text=same))
    assert not any("[다른 안]" in p for p in sw.styled_problems(out, frame, {"MAT-1": {}}, avoid_text="전혀 다른 문장들로만 된 원고"))


def test_reasons_are_reported_not_silent(monkeypatch):
    _fake_styled(monkeypatch, [{}])
    drafts, why = sw.make_drafts([], _styled_job(), seed_text=SEED)
    assert drafts == [] and "씨앗 결 이야기" in why
    assert sw.make_drafts([], {"extract": {}})[1]


def test_explicit_seed_sets_voice_and_product(monkeypatch):
    """ea29 사고(09-26) 회귀: 고른 씨앗(썰·반말)이 결을 정한다 — job의 인스타 존댓말 글이 씨앗이 되면 안 된다."""
    out = {"seed_points": [], "lines": _lines(["훅", "미끼", "공개", "고조", "마무리"])}
    prompts = _fake_styled(monkeypatch, [out])
    insta = "여러분 다이소에서 이거 절대 사서 가족 모두가 만지는 리모컨 닦아도 끝이 없죠 여기에 넣고 드라이어를 쏘기만 하면 되더라고요 " * 2
    job = {"backbone_main": None, "extract": {
        "s5": {"video_id": "s5", "full_text": insta, "source_brief": {"product": "다이소 수축 보호 필름"},
               "segments": [_seg("MAT", i) for i in range(12)]}}}
    drafts, why = sw.make_drafts([], job, job_id="j2", seed_text=SEED, seed_product="열수축 보호 필름")
    assert why == "" and drafts[0]["platform"] == "yt" and drafts[0]["seed_from"] == "explicit"
    assert "[제품] 열수축 보호 필름" in prompts[0] and "개발자도 예상 못한" in prompts[0] and sw._VOICE["yt"] in prompts[0]
    prompts.clear()
    drafts, _ = sw.make_drafts([], job, job_id="j3")
    assert drafts[0]["platform"] == "ig" and sw._VOICE["ig"] in prompts[0], "명시 씨앗 없음 → job의 가장 긴 한국어 글(종전)"


def test_short_seed_flow_is_not_dropped_but_length_is_checked():
    """씨앗 흐름이 4칸이어도 분량이 맞으면 버리지 않는다(옛 MIN_LINES=5가 b2b1480b3fd8 씨앗 결 안을 통째로 버렸다)."""
    frame = sw.frame_of(None)
    four = {"seed_points": [], "lines": _lines(["훅", "공개", "고조", "마무리"])}
    assert sw.styled_problems(four, frame, {"MAT-1": {}}, seconds=16) == []
    assert any("너무 짧다" in p for p in sw.styled_problems(four, frame, {"MAT-1": {}}, seconds=40))
    assert any("줄뿐" in p for p in sw.styled_problems({"lines": _lines(["훅", "끝"])}, frame, {"MAT-1": {}}))


def test_template_copy_is_a_problem_but_skeleton_variant_is_not():
    """2026-09-27 사장님: 뼈대는 같아도 말을 바꾸면 다른 내용처럼 보인다 — 예시 문장 통째 옮김만 잡는다."""
    sp = {"id": 59, "name": "사회증거형", "beat_roles": ["hook", "proof", "cta"],
          "templates": {"hook": ["이거 모르면 진짜 손해예요"], "proof": ["주변에서 하나둘 다 이거 쓰길래 저만 모르나 싶었어요"],
                        "cta": ["궁금하면 댓글에 '나도' 남겨주세요"]}}
    frame = sw.frame_of(sp)

    def run(texts):
        out = {"seed_points": [], "lines": [{"role": r, "text": t, "cuts": ["MAT-1"]}
                                            for r, t in zip(["hook", "proof", "proof", "cta"], texts)]}
        return [p for p in sw.styled_problems(out, frame, {"MAT-1": {}}, seconds=8) if "틀 예시" in p]
    copied = run(["이거 모르면 진짜 손해예요", "주변에서 하나둘 다 이거 쓰길래 저만 모르나 싶었거든요",
                  "아이 들어 올려서 착 얹으면 끝이라 편하더라고요", "궁금하면 댓글에 '나도' 남겨주세요"])
    assert len(copied) == 3 and copied[0].startswith("1번") and copied[1].startswith("2번")
    varied = run(["이거 모르고 애 안았다간 허리 나가요", "주변 육아 아빠들이 다 이거 쓰길래 저도 궁금해서 봤거든요",
                  "아이 들어 올려서 착 얹으면 끝이라 편하더라고요", "목마 궁금한 분은 댓글에 아빠 남겨주세요"])
    assert varied == []
