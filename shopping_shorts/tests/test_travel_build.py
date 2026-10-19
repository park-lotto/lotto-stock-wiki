"""여행형 제작 판단(관제 239) — 7장 고르기·대본 금지 검사·계획 배속·표기 문구."""
from shopping_shorts import travel_build as tb, video_assemble as va


def _j(no, kind, wow, text=False, people=False, desc=None):
    return {"no": no, "path": "p%d.jpg" % no, "kind": kind, "wow": wow, "has_text": text, "has_people": people,
            "desc_ko": desc or ("사진 %d 설명 %s" % (no, kind)), "desc_en": "photo"}


def test_pick7_ratio_order_and_exclusions():
    judged = [_j(1, "water", 3), _j(2, "water_aerial", 4), _j(3, "water", 5, text=True), _j(4, "onsen", 4),
              _j(5, "room", 4), _j(6, "room", 3), _j(7, "room", 2), _j(8, "view", 5), _j(9, "lobby", 3),
              _j(10, "restaurant", 4, people=True), _j(11, "exterior", 2)]
    got = tb.pick7(judged)
    nos = [p["no"] for p in got["photos"]]
    assert len(nos) == 7 and 3 not in nos and 10 not in nos          # 글자·사람 사진은 빠진다
    assert got["photos"][0]["kind"] == "water_aerial"                 # 첫 컷 = 위에서 본 물놀이
    kinds = [p["kind"] for p in got["photos"]]
    assert sum(k in tb.KIND_WATER for k in kinds) == 3 and kinds.count("room") == 2
    assert got["short"] == {}


def test_pick7_reports_shortage():
    got = tb.pick7([_j(1, "room", 3), _j(2, "room", 2), _j(3, "view", 4)])
    assert got["short"]["water"] == 3 and len(got["photos"]) == 3


def test_script_issues_catches_name_price_region_and_fake_visit():
    d = {"name": "네스트호텔 인천", "address": "인천 영종구 운서동 2877"}
    lines = ["네스트 가격이 18만원이에요", "영종 바다 앞이라 다녀왔는데 좋았고요"] + ["가"] * 5
    iss = " ".join(tb.script_issues(lines, d, 7))
    for w in ("가격", "숙소 이름: 네스트", "지역명: 영종", "가 본 척"):
        assert w in iss, iss


def test_script_issues_length_from_voice_speed():
    lo, hi, _, _ = tb.char_range(7)
    ok = ["가" * ((lo + hi) // 2 // 7)] * 7
    assert not [x for x in tb.script_issues(ok, {}, 7) if x.startswith("길이")]
    assert [x for x in tb.script_issues(["가" * 40] * 7, {}, 7) if x.startswith("길이")]


def test_build_plan_speeds_clip_to_line():
    durs = {"t0": 2.0, "t1": 5.0, "c0": 4.0, "c1": 4.0}
    plan, srcs = tb.build_plan(["첫 줄", "둘째 줄"], ["t0", "t1"], ["c0", "c1"], lambda p: durs[p])
    b0, b1 = plan["beats"]
    assert b0["sync_speed"] == 2.0 and b0["primary"]["end"] == 4.0        # 2초 줄에 4초 클립 = 2배
    assert b1["sync_speed"] == 1.0 and b1["primary"]["end"] == 4.0        # 줄이 더 길면 1배(늘리지 않는다)
    assert srcs == {"s0": "c0", "s1": "c1"} and b0["role"] == "hook" and b1["role"] == "cta"


def test_deco_for_feeds_disclosure_owner():
    deco = tb.deco_for({"source_label": "출처: 여기어때"})
    assert va.disclosure_texts(deco) == ["광고", "AI 콘텐츠", "출처: 여기어때"]
    assert va.disclosure_texts({}) == [] and va.disclosure_texts({"disclosure": {}}) == []


def test_write_script_picks_clean_version_and_retries_with_feedback():
    prompts = []

    def call(prompt, schema):
        prompts.append(prompt)
        good = ["가" * 19] * 7
        bad = ["가" * 19] * 6 + ["네스트 최고"]
        return {"versions": [{"type": "안티/반전형", "lines": bad}, {"type": "감각/공간 몰입형", "lines": good}]}

    picks = [_j(i, "water", 3) for i in range(7)]
    r = tb.write_script(picks, {"name": "네스트호텔"}, call=call, verify=lambda *a, **k: {"checks": []})
    assert r["chosen"]["type"] == "감각/공간 몰입형" and r["clean"] and r["attempts"] == 1


def test_style_hdn_endings_and_persona_allowed():
    good = ["와이프가 바다 앞 풀을 보여줬는데", "선베드 너머가 전부 바다라서", "로비가 미술관 같더라고요.",
            "심지어 침대에서도 바다가 보이거든요.", "밤엔 잔디밭이 빛나고", "소파가 넓더라고요.", "궁금하면 댓글 주세요."]
    iss = tb.script_issues(good, {}, 7, style="두유노홈디노")
    assert not [x for x in iss if x.startswith(("말투", "가 본 척"))], iss
    bad = ["풀이 정말 좋네요.", "바다가 보임.", "로비 최고임.", "침대 넓음.", "정원 예쁨.", "소파 좋음.", "댓글 주세요."]
    assert [x for x in tb.script_issues(bad, {}, 7, style="두유노홈디노") if x.startswith("말투")]
    assert [x for x in tb.script_issues(["다녀왔는데 좋았고요"] * 7, {}, 7) if x.startswith("가 본 척")]     # 기본 말투는 막는다
