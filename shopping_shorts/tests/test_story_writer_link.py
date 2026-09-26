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
        "s1": {"video_id": "s1", "full_text": "", "segments": [_seg("MAT", i) for i in range(20)]},   # 고조2 필수로 줄이 늘어 컷도 넉넉히(2026-09-26)
    }}


FEATS = [{"name": "앰플 도포", "claim": "빗 뒷면에 앰플을 채워 바른다",
          "pain": "손가락 사이로 다 흘러내리고 머리만 떡져서", "from_cuts": ["MAT-3", "MAT-4", "NOPE-9"]},
         {"name": "휴대", "claim": "가방에 들어간다", "pain": "큰 병을 들고 다녀야 했다", "from_cuts": ["MAT-7"]}]

YT_OUT = {"hook": "이걸 아직도 손으로 바른다고", "bait": "요새 이거 하나로 난리인데", "reveal": "이건 바로 두피 액체빗.",
          "contrast": "", "twist": "근데 가방에도 쏙 들어가서", "closing": "쓰는 사람마다 난리라는데",
          "escalations": [{"moment": "겨우 짜서 바르려는 순간", "what_happens": "손가락 사이로 다 흘러내리던 그 짜증을",
                           "erased": "빗 안에 넣어서 없애 버렸다는 거", "from_pain": "앰플 도포"},
                          # 고조2 무조건(2026-09-26) — 가짜 출력도 히트작 프리셋처럼 2칸
                          {"moment": "큰 병을 가방에 넣으려던 순간", "what_happens": "자리만 차지하던 그 짐을",
                           "erased": "빗 하나로 없애 버렸다는 거", "from_pain": "휴대"}]}


def _fake(monkeypatch, out=YT_OUT, feats=FEATS):
    calls = []

    def call(prompt, schema, note=None, model=None, vertex=True):   # vertex= : _call_json 스위치 인자(2026-09-26)
        calls.append(schema)
        return {"feats": feats} if schema is sw.FEATS_SCHEMA else out
    monkeypatch.setattr(sw._sg, "_call_json", call)
    return calls


def test_lines_get_feature_cuts_and_no_seed_cuts(monkeypatch):
    calls = _fake(monkeypatch)
    drafts, why = sw.make_drafts([], _job(), job_id="j1")
    assert why == "" and len(drafts) == 1 and len(calls) == 3      # 특징 1회 + 자동 1안 1회 + AI 매칭 1회
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
    assert [d["auto_pick"] for d in drafts] == [True, False] and len(calls) == 5     # 특징 1 + (쓰기 1 + AI 매칭 1) × 2안


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
        # 반전은 프리셋의 마지막 낱말([3])로 열고, 모델이 쓴 '심지어'는 떼어 낸다 — 한 줄에 신호어 두 개 금지
        assert twist.startswith(sigs[2]) and "심지어 심지어" not in twist and not twist.startswith(sigs[2] + " 심지어")


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
    # ★고조2는 길이 때문에도 안 뺀다(2026-09-26 사장님 "고조2는 무조건") — 최소 2칸이 남는다
    assert dropped == 1 and [x["role"] for x in out] == ["훅", "고조1", "고조1", "고조2", "고조2", "마무리"]
    assert sw._fit_length(lines, 999) == (lines, 0)


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


def test_insta_signal_goes_on_after_line_not_before():
    """히트작 641편 실측: 신호어 뒤에 과거 불편이 온 적 0. before 줄에 붙이면 "게다가 전에는…"이 된다."""
    o = {"opening": "와", "scene": "친구 집", "reveal": "이거", "feeling": "좋아요", "cta": "댓글",
         "beats": [{"before": "전에는 매번 쏟았거든요", "after": "이제는 한 방울도 안 흘러요", "from_pain": "", "feat": 1},
                   {"before": "전에는 손이 아팠어요", "after": "지금은 한 손으로 돼요", "from_pain": "", "feat": 1}]}
    lines = sw._to_lines(o, True, "k", 0, feats=[{"name": "x"}])
    texts = [L["text"] for L in lines if L["role"].startswith("고조")]
    assert not any(t.split()[0] in sw.IG_SETS["A"] + sw.IG_SETS["B"] and "전에는" in t for t in texts)
    assert any(t.startswith(sig) for t in texts for sig in sum(sw.IG_SETS.values(), []) if sig)


def test_signal_strips_leading_conjunction():
    o = {"hook": "h", "bait": "b", "reveal": "r", "twist": "t", "closing": "c",
         "escalations": [{"moment": "근데 이건 물이 안 새", "what_happens": "x", "erased": "y", "from_pain": "", "feat": 1}]}
    lines = sw._to_lines(o, False, "k", 0, feats=[{"name": "x"}])
    first = [L["text"] for L in lines if L["role"] == "고조1"][0]
    assert "근데 이건" not in first or not any(first.startswith(s) for s in sum(sw.YT_SETS.values(), []) if s)


def test_signal_positions_fixed_contrast_first_then_escalations_then_twist():
    """히트작 5편: 공개 → [1]이게 말도 안 되는게(대비) → [2]심지어(고조) → [3]근데 진짜 충격적인 포인트는(마지막)."""
    o = {"hook": "h", "bait": "b", "reveal": "r", "contrast": "기존 컵홀더와는 달리 영하 3도까지 떨어뜨려 준다는 거",
         "twist": "60도까지 데워주는 기능까지 있다고", "closing": "c",
         "escalations": [{"moment": "m1", "what_happens": "w1", "erased": "e1", "from_pain": "", "feat": 1}]}
    lines = sw._to_lines(o, False, "k", 0, feats=[{"name": "x"}])
    _, preset = sw._pick(sw.YT_SETS, "k", 0)
    by = {}
    for L in lines:
        by.setdefault(L["role"], L["text"])          # 칸의 첫 줄
    if preset[0]:
        assert by["대비"].startswith(preset[0])
    assert by["고조1"].startswith(preset[1])
    assert by["반전"].startswith(preset[2])
    assert all(p[1] in ("심지어", "게다가", "거기다") for p in sw.YT_SETS.values())   # 두 번째 자리는 늘 '심지어' 급


def test_반전은_twist_feat_번호의_특징_컷을_받는다():
    o = {"hook": "h", "bait": "b", "reveal": "r", "contrast": "", "closing": "c",
         "twist": "물에 씻어 반영구적으로 쓴다는 거", "twist_feat": 2,
         "escalations": [{"moment": "m", "what_happens": "w", "erased": "e", "from_pain": "", "feat": 1}]}
    lines = sw._to_lines(o, False, "k", 0, feats=[{"name": "요철"}, {"name": "물세척 재사용"}])
    twist = next(L for L in lines if L["role"] == "반전")
    assert twist["group"] == 1


def test_explicit_seed_wins_over_longest_job_text(monkeypatch):
    """2026-09-26 사장님 "씨앗은 썰쇼핑인데 왜 다이소가 나오나"(work ea29430903d3).
    고른 씨앗(유튜브 썰·반말)은 job에 없고, job엔 인스타 존댓말(다이소)만 있다 →
    종전엔 인스타 글이 씨앗이 돼 존댓말 다이소 대본이 나왔다. 명시 씨앗이 오면 그것이 결·훅 꼴·제품을 정한다."""
    _fake(monkeypatch)
    seen = []
    real_write = sw.write

    def spy(product, seed_text, feats, platform="yt", **kw):
        seen.append({"product": product, "seed": seed_text, "platform": platform})
        return real_write(product, seed_text, feats, platform=platform, **kw)
    monkeypatch.setattr(sw, "write", spy)
    insta = "여러분 다이소에서 이거 절대 사서 가족 모두가 만지는 리모컨 닦아도 끝이 없죠 여기에 넣고 드라이어를 쏘기만 하면 되더라고요 " * 2
    job = {"backbone_main": None, "extract": {
        "s5": {"video_id": "s5", "full_text": insta, "source_brief": {"product": "다이소 수축 보호 필름"},
               "segments": [_seg("MAT", i) for i in range(12)]}}}
    ssul = "개발자도 예상 못한 한국 주부의 활용법 최근 딱 봤을 때는 평범한 필름지처럼 보이는 이 제품을 이용한 한국의 한 천재 주부의 활용법이 난리라는데 이건 바로 열수축 필름."
    drafts, why = sw.make_drafts([], job, job_id="j2", seed_text=ssul, seed_product="열수축 보호 필름")
    assert why == "" and len(drafts) == 1
    assert seen[0]["seed"].startswith("개발자도 예상 못한"), "씨앗은 고른 영상의 원문이어야 한다"
    assert seen[0]["platform"] == "yt", "썰(반말) 씨앗이면 결은 yt — 인스타 존댓말로 쓰면 안 된다"
    assert seen[0]["product"] == "열수축 보호 필름"
    assert drafts[0]["seed_from"] == "explicit"
    # 명시 씨앗이 없으면 종전 규칙(job에서 가장 긴 한국어 글)이 그대로 — 회귀 0
    seen.clear()
    sw.make_drafts([], job, job_id="j3")
    assert seen[0]["seed"].startswith("여러분 다이소"), "명시 씨앗 없음 → job의 가장 긴 한국어 글(종전)"
    assert seen[0]["platform"] == "ig", "존댓말 글이 씨앗이면 인스타 결 — 이게 ea29 사고의 모양이다"


def test_second_escalation_is_mandatory_retry_once_then_reject(monkeypatch):
    """2026-09-26 사장님 "고조2는 무조건 들어가야 된다". 1칸이면 무엇이 모자란지 말해 1회 다시, 그래도 1칸이면 반려."""
    one = dict(YT_OUT, escalations=YT_OUT["escalations"][:1])
    prompts = []

    def call(prompt, schema, note=None, model=None, vertex=True):
        prompts.append(prompt)
        if schema is sw.FEATS_SCHEMA:
            return {"feats": FEATS}
        return one if len(prompts) == 1 else YT_OUT          # 첫 답 1칸 → 다시 → 2칸
    monkeypatch.setattr(sw._sg, "_call_json", call)
    note = {}
    lines = sw.write("두피 액체빗", "씨앗 " * 30, FEATS, platform="yt", key="k", note=note)
    roles = [L["role"] for L in lines]
    assert "고조2" in roles and note.get("escalation_retry") == 1
    assert "고조 칸이 1개뿐" in prompts[1] and "정확히 2개" in prompts[1]
    # 스키마도 구조로 막는다
    assert sw.YT_SCHEMA["properties"]["escalations"]["minItems"] == 2
    assert sw._short_schema()["properties"]["escalations"]["minItems"] == 2
    # 끝내 1칸이면 반려 — 얇은 대본을 조용히 내보내지 않는다
    monkeypatch.setattr(sw._sg, "_call_json", lambda *a, **k: one)
    note2 = {}
    assert sw.write("두피 액체빗", "씨앗 " * 30, FEATS, platform="yt", key="k", note=note2) == []
    assert note2.get("reason", "").startswith("고조2 없음")


def test_hook_copy_triggers_retry_then_deterministic_and_feats_rotate(monkeypatch):
    """2026-09-26 사장님 "이렇게까지 고치고 라이브까지": 훅이 씨앗 첫 줄을 베끼면 다른 꼴로 1회 다시 →
    그래도 베끼면 결정적 채움. 안마다 특징 순서가 돌아 본문이 같아지지 않는다."""
    seed = ("개발자도 예상 못한 한국 주부의 활용법 최근 딱 봤을 때는 평범한 필름지처럼 보이는 이 제품을 이용한 "
            "한국의 한 천재 주부의 활용법이 각종 SNS에서 수천만 조회수로 바이럴 폭발함에 논란이라는데")
    copy_out = dict(YT_OUT, hook="개발자도 예상 못한 한국 주부의 미친 활용법")     # 모델이 계속 베낀다
    prompts = []

    def call(prompt, schema, note=None, model=None, vertex=True):
        prompts.append(prompt)
        if schema is sw.FEATS_SCHEMA:
            return {"feats": FEATS, "hook": {"권위자": "개발자", "대상": "주부들", "나라": "한국", "제품군": "열수축 필름"}}
        return copy_out
    monkeypatch.setattr(sw._sg, "_call_json", call)
    job = {"backbone_main": None, "extract": {
        "s1": {"video_id": "s1", "full_text": "", "segments": [_seg("MAT", i) for i in range(20)]}}}
    drafts, why = sw.make_drafts([{"id": 9, "name": "유튜브 「OO의 정체」", "no_cta": True,
                                   "templates": {"title": ["{나라} 천재가 만들어 떼돈 번 제품의 정체"]}}],
                                 job, job_id="j9", seed_text=seed, seed_product="열수축 보호 필름")
    assert why == "" and len(drafts) == 2
    from shopping_shorts import story_hook
    # 자동 1안(씨앗 결): 은행 꼴 — 베끼면 다른 꼴로 1회 다시 → 결정적 채움
    auto = drafts[0]
    assert not story_hook.copied(auto["beats"][0]["text"], seed) and "{" not in auto["beats"][0]["text"]
    assert auto["writer_note"].get("hook_retry") and auto["writer_note"].get("hook_fix") == "copied→deterministic"
    # ★고른 스타일(A안, 2026-09-26 사장님): 첫 줄은 **스타일 제목 틀**이 이긴다 — 은행이 덮어쓰지 않는다
    assert drafts[1]["beats"][0]["text"] == "한국 천재가 만들어 떼돈 번 제품의 정체"
    # 재작성 프롬프트는 다른 꼴을 지시하고 씨앗 문장은 안 보여준다
    retry = [p for p in prompts if "첫 줄을 다시 써라" in p]
    assert retry and all("개발자도 예상 못한 한국 주부의 활용법" not in p.split("[씨앗")[0] for p in retry)
    # 특징 순서: 반전 특징(맨 뒤, 새 특징 1위)은 고정, 나머지만 돈다(본문 다양화는 유지)
    assert sorted(drafts[0]["feat_names"]) == sorted(drafts[1]["feat_names"])
    assert drafts[0]["feat_names"][-1] == drafts[1]["feat_names"][-1]


# ── 차별점(2026-09-26 사장님 "대본이 씨앗이랑 거의 똑같다 — 차별 포인트는 기능·특징·장점") ─────────
def _idx(**vids):
    """seg_id → vid 표(pick_diff_feats가 영상 수를 센다)."""
    return {sid: {"vid": v} for v, sids in vids.items() for sid in sids}


def test_pick_diff_feats_prefers_new_by_video_count():
    idx = _idx(s1=["a1", "a2"], s2=["b1"], s3=["c1"], s4=["d1"])
    cands = [
        {"name": "유리컵 재사용", "seed_quote": "그대로 물컵으로 다시 쓸 수 있는", "from_cuts": ["a1", "b1", "c1"]},
        {"name": "단단한 유리", "seed_quote": "단단한 유리컵에 담아버려", "from_cuts": ["a2"]},
        {"name": "6개입", "seed_quote": "", "from_cuts": ["a1", "b1", "c1", "d1"]},      # 새것·영상 4개 → 반전
        {"name": "1인분 칼로리", "seed_quote": "", "from_cuts": ["a2"]},                  # 새것·영상 1개
        {"name": "홈카페 컵", "seed_quote": "", "from_cuts": ["c1", "d1"]},               # 새것·영상 2개
    ]
    picked, tw = sw.pick_diff_feats(cands, idx)
    names = [f["name"] for f in picked]
    assert names[-1] == "6개입" and tw == len(picked) - 1                 # 반전 = 새 특징 1위(영상 수)
    assert sum(1 for f in picked if f["new"]) >= sw.DIFF_MIN_NEW
    assert sum(1 for f in picked if not f["new"]) <= 1                     # 씨앗 특징은 고조1용 최대 1개
    assert names[0] == "유리컵 재사용" and "홈카페 컵" in names             # 씨앗 특징 중 영상 많은 것 / 새것 2위


def test_diff_rule_and_violations():
    feats = [{"name": "재사용", "new": False, "videos": 3}, {"name": "홈카페", "new": True, "videos": 2},
             {"name": "6개입", "new": True, "videos": 4}]
    seed = "유리컵으로 떼돈 번 천재의 발명품. 근데 진짜 충격적인 포인트는 마스카포네까지 제대로 넣어 컵 때문에 샀다가 맛 때문에 또 사게 된다고."
    pts = ["다 먹고 물컵으로 재사용", "식기세척기 사용 가능", "마스카포네 맛 때문에 재구매"]
    rule = sw._diff_rule(feats, 3, seed, pts)
    assert "고조1에서만" in rule and "새 특징(재료 2번)" in rule and "재료 3번" in rule and "물컵으로 재사용" in rule
    ok = {"escalations": [{"feat": 1}, {"feat": 2, "moment": "아침마다 커피 담을 컵이 없어서"}],
          "twist": "6개가 한 번에 들어 있어서 식구 수대로 나눠 먹는다고", "twist_feat": 3}
    assert sw._diff_violations(ok, feats, 3, seed, pts, "티라미수") == []
    bad = {"escalations": [{"feat": 2}, {"feat": 1}],
           "twist": "마스카포네까지 제대로 넣어 맛 때문에 또 사게 된다고", "twist_feat": 1}
    v = sw._diff_violations(bad, feats, 3, seed, pts, "티라미수")
    assert any("고조2" in x for x in v) and any("twist_feat=3" in x for x in v) and any("씨앗이 이미 말한 내용" in x for x in v)
    assert sw._diff_rule([{"name": "a"}], 0, seed) == ""                  # 표시 없는 재료(옛 경로) = 종전 그대로


def test_diff_one_new_feature_no_repeat():
    """새 특징이 1개면 반전 전용 — 고조2는 고조1과 다른 씨앗 특징(09-26 실측: 같은 특징을 두 번 말했다)."""
    feats = [{"name": "재사용", "new": False, "videos": 3}, {"name": "유리", "new": False, "videos": 3},
             {"name": "1인분", "new": True, "videos": 2}]
    rule = sw._diff_rule(feats, 3, "", [])
    assert "반전 전용" in rule and "서로 다른 특징" in rule and "고조2부터는" not in rule
    same = {"escalations": [{"feat": 1}, {"feat": 1}], "twist": "하나씩 꺼내 먹는다고", "twist_feat": 3}
    assert any("같은 1번" in x for x in sw._diff_violations(same, feats, 3, "", [], ""))
    grab = {"escalations": [{"feat": 1}, {"feat": 3}], "twist": "하나씩 꺼내 먹는다고", "twist_feat": 3}
    assert any("반전 전용" in x for x in sw._diff_violations(grab, feats, 3, "", [], ""))
    fine = {"escalations": [{"feat": 1}, {"feat": 2}], "twist": "하나씩 꺼내 먹는다고", "twist_feat": 3}
    assert sw._diff_violations(fine, feats, 3, "", [], "") == []


def test_seed_content_hits_ignore_product_words():
    pts = ["최대 40시간 배터리", "비싼 스포츠 이어폰 자리 빼앗음", "방수 기능"]
    assert sw._seed_word_hits("가격대까지 비싼 스포츠 브랜드 제품을 압도해 버렸고", pts, "무선 이어폰") == ["비싼", "스포츠"]
    assert sw._seed_word_hits("귀걸이처럼 예쁜 이어폰이라고", pts, "무선 이어폰") == []      # 제품명 낱말은 안 센다


def test_diff_retry_once_and_twist_filled(monkeypatch):
    feats = [{"name": "재사용", "new": False, "videos": 3, "from_cuts": ["MAT-1"]},
             {"name": "6개입", "new": True, "videos": 4, "from_cuts": ["MAT-2"]}]
    seed = ("유리컵으로 떼돈 번 천재의 발명품. "
            "근데 진짜 충격적인 포인트는 마스카포네까지 제대로 넣어 컵 때문에 샀다가 맛 때문에 또 사게 된다고.")
    copied = dict(YT_OUT, twist="마스카포네까지 제대로 넣어 컵 때문에 샀다가 맛 때문에 또 사게 된다고")
    fixed = dict(YT_OUT, twist="6개가 한 번에 들어 있어서 식구 수대로 나눠 먹는다고")
    outs, prompts = [copied, fixed], []

    def call(prompt, schema, note=None, model=None, vertex=True):
        prompts.append(prompt)
        return outs.pop(0)
    monkeypatch.setattr(sw._sg, "_call_json", call)
    note = {}
    lines = sw.write("티라미수", seed, feats, platform="yt", key="k", note=note, twist_n=2)
    assert len(prompts) == 2 and "다시 써라" in prompts[1] and note.get("diff_retry")
    tw = [L for L in lines if L["role"] == "반전"][0]
    assert "식구 수대로" in tw["text"] and tw["group"] == 1               # twist_feat 안 적어도 지정 특징(2번=idx1)


def test_style_hook_line_and_land_enforced():
    sp = {"name": "유튜브 「OO의 정체」", "templates": {
        "title": ["{나라} 천재가 만들어 떼돈 번 제품의 정체", "{대상}이 더 많이 쓰는 {제품군}의 정체"],
        "land": ["이러니 떼돈을 벌었다고", "완벽하다고"]}}
    # 나라가 없으면 채울 수 있는 둘째 틀
    assert sw.style_hook_line(sp, {"대상": "러너들", "제품군": "오픈형 이어폰"}) == "러너들이 더 많이 쓰는 오픈형 이어폰의 정체"
    # 아무 틀도 못 채우면 None — 모델이 틀의 빈칸을 채운다(빈칸을 빼면 "예상 못한 미친 활용법"처럼 약해진다)
    assert sw.style_hook_line(sp, {}) is None
    st = sw._style_of(sp, {"나라": "일본"}, "", "k", 0)
    lines = [{"role": "훅", "text": "개발자도 예상 못한 뜻밖의 활용법"}, {"role": "마무리", "text": "벌써 품절 난리라는데"}]
    out = sw._enforce_style(lines, st)
    assert out[0]["text"] == "일본 천재가 만들어 떼돈 번 제품의 정체" and out[-1]["text"] == "이러니 떼돈을 벌었다고"
    # 채울 재료가 없으면 강제하지 않는다 — 스타일 이름 각도로 모델이 쓴 첫 줄 그대로
    st0 = sw._style_of(sp, {}, "", "k", 0)
    assert "스타일 이름" in st0["hook_angle"] and "{" not in st0["hook_angle"]
    keep = sw._enforce_style([{"role": "훅", "text": "러너들 구원한 이어폰의 정체"}], st0)
    assert keep[0]["text"] == "러너들 구원한 이어폰의 정체"


def test_seed_points_catch_missed_quote():
    """모델이 인용을 빠뜨려도 씨앗 셀링포인트 목록과 낱말이 겹치면 '씨앗이 이미 말함'(09-26 실측 두 건)."""
    idx = _idx(s1=["a"], s2=["b"])
    pts = ["휘어지는 본체와 특수 실리콘 패드로 귀에 밀착", "압박감 줄임", "최대 40시간 배터리", "식기세척기 사용 가능"]
    cands = [{"name": "간편한 세척", "claim": "다 먹은 후 헹궈 바로 씀", "seed_quote": "", "seed_point": 0,
              "from_cuts": ["a"], "_seed_points": pts},
             {"name": "편안한 착용감", "claim": "특수 실리콘 패드가 귀에 밀착돼 압박감이 없다", "seed_quote": "", "seed_point": 0,
              "from_cuts": ["a"], "_seed_points": pts},
             {"name": "패션 아이템", "claim": "피어싱처럼 귀에 달아 스타일을 더한다", "seed_quote": "", "seed_point": 0,
              "from_cuts": ["b"], "_seed_points": pts},
             {"name": "방수", "claim": "땀에 젖어도 멀쩡", "seed_quote": "", "seed_point": 3, "from_cuts": ["b"], "_seed_points": pts}]
    picked, _ = sw.pick_diff_feats(cands, idx)
    new = {f["name"]: f["new"] for f in picked}
    assert new.get("패션 아이템") is True
    assert all(not f["new"] for f in picked if f["name"] in ("간편한 세척", "편안한 착용감", "방수"))
