# -*- coding: utf-8 -*-
"""조립기가 스파인 문장틀·역할순서를 그대로 쓰는지(2026-09-17 사장님: "이븐쇼핑 스타일" = 천재·떼돈·「이건 바로 OO」·CTA 없음)."""
from shopping_shorts import backbone_assemble as ba

ROLES = ["title", "bait", "fame", "reveal", "limit", "solve", "more", "twist", "land"]
TPL = {"title": ["{나라} 천재가 만들어 떼돈 번 {제품군}의 정체"], "bait": ["평범한 이 {제품군}가"],
       "fame": ["천재가 떼돈을 벌었다는데"], "reveal": ["이건 바로 {제품}"], "limit": ["기존 {제품군}은 한계였는데"],
       "solve": ["이건 {효능}"], "more": ["심지어 {효능2}"], "twist": ["진짜 충격은 {효능3}"], "land": ["이러니 떼돈을 벌었다고"]}


def test_효능_자리만_특징줄이다():
    assert ba._feature_roles(ROLES, TPL) == ["solve", "more", "twist"]


def test_특징3개면_틀_그대로_9줄():
    plan = ba._spine_plan(ROLES, TPL, 3)
    assert [r for r, _ in plan] == ROLES
    assert [g for _, g in plan] == [-1, -1, -1, -1, -1, 0, 1, 2, -1]


def test_특징이_많으면_more를_twist_앞에_반복():
    plan = ba._spine_plan(ROLES, TPL, 5)
    assert [r for r, _ in plan] == ["title", "bait", "fame", "reveal", "limit", "solve", "more", "more", "more", "twist", "land"]
    assert [g for _, g in plan if g >= 0] == [0, 1, 2, 3, 4]


def test_특징이_적으면_남는_효능줄을_뺀다():
    plan = ba._spine_plan(ROLES, TPL, 1)
    assert [r for r, _ in plan] == ["title", "bait", "fame", "reveal", "limit", "solve", "land"]


def test_프롬프트에_CTA_금지와_문장틀이_들어간다():
    p = ba._spine_prompt({"product": "카메라", "order": [0, 1, 2]}, {"name": "이건 바로 OO"}, ROLES, TPL, ["  1. [0] a", "  2. [1] b", "  3. [2] c"], 20)
    assert "이건 바로 {제품}" in p and "CTA를 덧붙이지 마라" in p and "role=twist" in p


def test_틀_없는_스파인은_옛_경로():
    assert ba._spine_style({"name": "x"}) == ([], {})


def _idx(**kw):
    return {k: {"vid": "sub", "secs": v[0], "desc": v[1]} for k, v in kw.items()}


def test_구조줄이_특징_컷을_먼저_먹지_않는다():
    """job bb4c2734ce80 실측: title·bait·fame이 박스 컷 7개를 다 먹어 '패키지' 줄에 거리 풍경만 남았다."""
    idx = _idx(box1=(3.0, "박스 뚜껑을 열어 카메라가 드러남"), box2=(3.0, "구성품을 꺼내 보여줌"),
               whole=(3.0, "손으로 카메라 전체 형태를 보여줌"), street=(3.0, "거리 풍경 결과물"))
    groups = {"product": "카메라", "groups": [{"name": "패키지", "cuts": ["box1", "box2"]}], "order": [0]}
    lines = [{"role": "title", "text": "가" * 8, "group": -1},
             {"role": "bait", "text": "가" * 8, "group": -1},
             {"role": "solve", "text": "가" * 8, "group": 0}]
    bs, rep = ba.assign_cuts(lines, groups, idx, "bb")
    assert bs[2]["segs"][0] in ("box1", "box2"), bs
    assert bs[0]["segs"][0] in ("box1", "box2", "whole"), "구조 줄은 제품 컷(예약 외관→묶음 잔여)을 먼저, 거리 컷은 뒤: %s" % bs
    assert "street" not in bs[0]["segs"][:1]
    assert [b["role"] for b in bs] == ["title", "bait", "solve"], "출력 순서는 대본 순서 그대로"


def test_프롬프트의_group은_묶음_원번호다():
    g = {"product": "x", "order": [2, 0]}          # 순서 1번 = 묶음 2, 순서 2번 = 묶음 0
    p = ba._spine_prompt(g, {"name": "s"}, ROLES, TPL, ["a", "b"], 20)
    assert "role=solve, group=2 (특징 1번)" in p and "role=twist, group=0 (특징 2번)" in p   # 2개면 첫·마지막(반전)


def test_구조줄은_남은_제품컷을_먼저_사람컷은_맨뒤():
    idx = _idx(box1=(3.0, "박스를 열어 카메라가 드러남"), box2=(3.0, "구성품을 꺼냄"), box3=(3.0, "본체를 꺼내 보여줌"),
               face=(3.0, "남성이 카메라를 들고 구매처를 언급함"), cta=(3.0, "댓글 유도 화면"))
    groups = {"product": "카메라", "groups": [{"name": "패키지", "cuts": ["box1", "box2", "box3"]}], "order": [0]}
    lines = [{"role": "title", "text": "가" * 8, "group": -1}, {"role": "solve", "text": "가" * 8, "group": 0}]
    bs, _ = ba.assign_cuts(lines, groups, idx, "bb")
    assert bs[1]["segs"] and all(x.startswith("box") for x in bs[1]["segs"])
    assert bs[0]["segs"][0].startswith("box"), "묶음에서 남은 제품 컷을 먼저 쓴다: %s" % bs
    assert "face" not in bs[0]["segs"][:1] and "cta" not in bs[0]["segs"][:1]


def test_외관컷은_구조줄_몫으로_예약된다():
    """job bb50a7ba99ba: 특징 줄이 '옆면·뒷면 마감' 컷까지 써서 정체 줄엔 거리 풍경만 남았다."""
    idx = _idx(whole=(3.0, "손으로 카메라의 옆면과 뒷면을 돌려가며 마감을 보여줌"), open1=(3.0, "포장을 벗김"),
               open2=(3.0, "박스에서 꺼냄"), street=(3.0, "거리 풍경 결과물"))
    groups = {"product": "카메라", "groups": [{"name": "언박싱", "cuts": ["open1", "whole", "open2"]}], "order": [0]}
    lines = [{"role": "title", "text": "가" * 8, "group": -1}, {"role": "solve", "text": "가" * 20, "group": 0}]
    bs, _ = ba.assign_cuts(lines, groups, idx, "bb")
    assert bs[0]["segs"][0] in ("whole", "open2"), "구조 줄은 예약된 외관·박스 컷을 받는다: %s" % bs
    assert bs[1]["segs"][0] == "open1", "특징 줄은 예약 안 된 컷을 먼저 쓴다: %s" % bs


def test_seed가_문자열이어도_틀을_고른다():
    """배치는 seed=job id 문자열을 넘긴다(2026-09-18 4건 전부 TypeError)."""
    g = {"product": "x", "order": [0]}
    p1 = ba._spine_prompt(g, {"name": "s"}, ROLES, TPL, ["a"], 20, seed="iba25602b41")
    p2 = ba._spine_prompt(g, {"name": "s"}, ROLES, TPL, ["a"], 20, seed=3)
    assert "role=solve" in p1 and "role=solve" in p2


def test_어미_겹침을_잡고_기계로_고친다():
    """2026-09-18 실측 4건(job bba3a1e8f7a1·bbe6fcfabec1)."""
    bad = ["심지어 칸막이로 소품을 분류한다는는데.", "이건 틈새 공간을 최대로 활용한다는는데.",
           "연기를 강력하게 싹 빨아들여 주는는데.", "심지어 진짜 대박인 건 어디서나 가볍게 쓰는 건까지 해 준다는데.",
           "근대 진짜 충격적인 포인트는 설치 후 정리가 너무 완벽하다는 거."]
    for b in bad[:4]:
        assert ba._bad_join(b), b
    fixed = [ba._fix_join(b) for b in bad]
    assert fixed[0] == "심지어 칸막이로 소품을 분류한다는데." and fixed[2] == "연기를 강력하게 싹 빨아들여 주는데."
    assert fixed[3] == "심지어 진짜 대박인 건 어디서나 가볍게 쓰까지 해 준다는데." or "건까지 해" not in fixed[3]
    assert fixed[4].startswith("근데 ")
    for f in fixed[:3]:
        assert not ba._bad_join(f), f


def test_정상_문장은_안_건드린다():
    ok = ["이건 보풀 없이 식기 물기를 닦아낼 수 있다는 거.", "이게 말도 안 되는게 그냥 필터만 갈아 끼워주면 되는데.",
          "최근 누가 봐도 평범한 이 미니 후드 하나가 전 세계에서 미친 듯이 품절 대란이라는데.", "완벽하다고."]
    for o in ok:
        assert not ba._bad_join(o), o
        assert ba._fix_join(o) == o


class _FakeStore:
    def __init__(self, spines): self._s = spines
    def list_spines(self, status=None): return self._s


def test_유형을_주면_그_유형_스파인들을_순번대로_돈다():
    """2026-09-18 사장님: 오용형 고르면 그 유형 스파인들이 순번대로."""
    sp = [{"id": 60, "hook_3s": "x", "fit_categories": ["발명품형"]}, {"id": 65, "hook_3s": "x", "fit_categories": ["발명품형"]},
          {"id": 66, "hook_3s": "x", "fit_categories": ["발명품형"]}, {"id": 56, "hook_3s": "x", "fit_categories": ["오용형"]}]
    st = _FakeStore(sp)
    assert [ba.pick_hook_spine(st, seed=i, style="발명품형")["id"] for i in range(4)] == [60, 65, 66, 60]
    assert ba.pick_hook_spine(st, seed="jobid-abc", style="오용형")["id"] == 56
    assert ba.pick_hook_spine(st, spine_id=56, seed=0, style="발명품형")["id"] == 56, "spine_id가 우선"
    assert ba.pick_hook_spine(st, seed=0, style="없는유형")["id"] in (56, 60, 65, 66), "유형에 스파인이 없으면 무작위 폴백"


def test_특징이_많아도_틀_밖_반복은_2줄까지():
    plan = ba._spine_plan(ROLES, TPL, 7)      # 효능 자리 3개 + 특징 7개
    assert len([1 for r, g in plan if g >= 0]) == 3 + ba.MAX_EXTRA_FEATURE_LINES


def test_효능칸이_둘뿐인_오용형은_줄을_안_늘린다():
    roles = ["title", "bait", "origin", "notice", "cases", "twist"]
    tpl = {"title": ["{권위자}도 몰랐던"], "bait": ["요새 난리인데"], "origin": ["원래는 {본래용도}였음"], "notice": ["근데 {속성}에 주목"],
           "cases": ["초보는 {용도} 고수는 {용도2}"], "twist": ["근데 미친 활용법은 따로 있었는데 {용도끝}"]}
    plan = ba._spine_plan(roles, tpl, 5)
    assert [r for r, _ in plan] == roles, plan


def test_슬롯_이름이_글자로_새면_지운다():
    out = {"lines": [{"role": "twist", "text": "근데 진짜 충격적인 포인트는 슬라이딩 덮개로 물건을 숨기는 용도끝", "group": -1},
                     {"role": "x", "text": "이건 {효능}다는 거", "group": 0}]}
    L = ba._clean_lines(out)
    assert L[0]["text"] == "근데 진짜 충격적인 포인트는 슬라이딩 덮개로 물건을 숨기는." and "{" not in L[1]["text"]


def test_유형으로_고르면_hook_3s_없는_스파인도_후보():
    st = _FakeStore([{"id": 52, "fit_categories": ["지인증언형"]}, {"id": 55, "hook_3s": "x", "fit_categories": ["제품정체형"]}])
    assert ba.pick_hook_spine(st, seed=0, style="지인증언형")["id"] == 52


def test_more_칸_없는_인스타형은_줄을_안_늘린다():
    roles = ["hook", "ask", "reveal", "method", "result", "cta"]
    tpl = {"hook": ["충격 받았어요"], "ask": ["이거 하나면 {효능}다는 거예요"], "reveal": ["알고 보니 {효능}라는 거 있죠"],
           "method": ["{효능}, 그러면 끝이라는데"], "result": ["진짜 {효능} 거 있죠"], "cta": ["댓글에 나도"]}
    plan = ba._spine_plan(roles, tpl, 6)
    assert [r for r, _ in plan] == roles, plan


def test_레시피_전용_스파인은_물건_유형에서_안_뽑힌다():
    sp = [{"id": 53, "fit_categories": ["권유지시형", "레시피"]},              # 레시피 전용
          {"id": 52, "fit_categories": ["지인증언형", "홈템", "뷰티", "레시피"]},  # 물건에도 씀
          {"id": 99, "fit_categories": ["권유지시형", "홈템"]}]
    st = _FakeStore(sp)
    assert ba.pick_hook_spine(st, seed=0, style="권유지시형")["id"] == 99
    assert ba.pick_hook_spine(st, seed=0, style="지인증언형")["id"] == 52
    assert ba.pick_hook_spine(st, seed=0, style="레시피")["id"] in (53, 52)


def test_스파인이_다르면_같은_틀이어도_시작점이_다르다():
    g = {"product": "x", "order": [0]}
    tpl = {r: ["A{효능}는데", "B{효능}는데", "C{효능}는데"] if r in ("solve", "more", "twist") else ["%s1" % r, "%s2" % r, "%s3" % r] for r in ROLES}
    p74 = ba._spine_prompt(g, {"id": 74, "name": "s"}, ROLES, tpl, ["a"], 20, seed=0)
    p75 = ba._spine_prompt(g, {"id": 75, "name": "s"}, ROLES, tpl, ["a"], 20, seed=0)
    picked = lambda p: [l.split("문장틀:")[-1] for l in p.splitlines() if "문장틀:" in l]
    assert picked(p74) != picked(p75), "스파인이 다르면 조합이 달라야"


def test_칸마다_따로_돌아_회원100명_조합이_많다():
    """2026-09-18 실측 66번: 칸마다 틀 3개인데 모든 칸이 같이 움직여 100명 중 조합 3가지뿐."""
    import uuid
    roles = ["a", "b", "c", "d"]
    tpl = {r: ["%s1" % r, "%s2" % r, "%s3" % r] for r in roles}
    plan = [(r, -1) for r in roles]
    combos = {tuple(ba._pick_templates(plan, tpl, "bb" + uuid.uuid4().hex[:10], {"id": 66})) for _ in range(100)}
    assert len(combos) >= 40, len(combos)          # 3^4=81가지 중 100명이면 40가지 이상 나와야


def test_같은_칸이_반복되면_다음_틀():
    tpl = {"more": ["m1", "m2", "m3"]}
    out = ba._pick_templates([("more", 0), ("more", 1)], tpl, 0, {"id": 0})
    assert out[0] != out[1]


def test_특징이_줄면_가운데부터_빼고_반전은_남긴다():
    plan = ba._spine_plan(ROLES, TPL, 2)          # 효능 칸 solve·more·twist 중 2개만
    feat = [r for r, g in plan if g >= 0]
    assert feat == ["solve", "twist"], plan


def test_25초면_정체형은_8줄_안팎():
    g = {"product": "x", "order": list(range(7))}
    roles = ROLES
    feat_n = len(ba._feature_roles(roles, TPL))
    allow = max(1, int(25 // ba.SECS_PER_LINE) - (len(roles) - feat_n))
    plan = ba._spine_plan(roles, TPL, min(len(g["order"]), allow))
    assert 7 <= len(plan) <= 9, len(plan)


def test_읽는_초가_넘치면_가운데_특징줄부터_뺀다():
    long = "가" * 40
    lines = [{"role": "title", "text": long, "group": -1}] + \
            [{"role": "f%d" % i, "text": long, "group": i} for i in range(5)] + \
            [{"role": "land", "text": "끝", "group": -1}]
    out = ba._fit_length(lines, 25)
    assert sum(ba._secs(L["text"]) for L in out) <= 27 or len([L for L in out if L["group"] >= 0]) == 2
    assert out[0]["role"] == "title" and out[-1]["role"] == "land"
    feats = [L["role"] for L in out if L["group"] >= 0]
    assert feats[0] == "f0" and feats[-1] == "f4", feats


def test_짧으면_그대로():
    lines = [{"role": "a", "text": "짧다", "group": 0}]
    assert ba._fit_length(lines, 25) == lines


def test_제품_전체이름은_공개줄에만():
    p = "NORDECO 빈티지 미니 카메라"
    lines = [{"role": "title", "text": "미친 %s의 정체." % p, "group": -1},
             {"role": "reveal", "text": "이건 바로 %s." % p, "group": -1},
             {"role": "more", "text": "%s로 찍으면 감성." % p, "group": 0}]
    out = ba._one_full_name(lines, p)
    assert out[0]["text"] == "미친 카메라의 정체." and p in out[1]["text"] and out[2]["text"].startswith("카메라로")


def test_다는으로_끊기면_거를_붙인다():
    assert ba._fix_join("레버를 돌려 손맛까지 느끼게 해준다는.") == "레버를 돌려 손맛까지 느끼게 해준다는 거."
    assert ba._fix_join("이러니 난리가 났다는데.") == "이러니 난리가 났다는데."


def test_특징_순서는_양끝_두고_가운데를_섞는다():
    o = [0, 1, 2, 3, 4]
    outs = {tuple(ba._shuffle_middle(o, "bb%03d" % i)) for i in range(30)}
    assert all(x[0] == 0 and x[-1] == 4 and sorted(x) == o for x in outs)
    assert len(outs) >= 3, "회원마다 다른 순서"
    assert tuple(o) not in outs or len(outs) > 1
    assert ba._shuffle_middle([0, 1, 2], 1) == [0, 1, 2]


def test_주게_해_주는데_이중어미():
    assert ba._fix_join("이게 말도 안 되는게 주방 인테리어를 살려주게 해 주는데.") == "이게 말도 안 되는게 주방 인테리어를 살려주는데."


def test_백본은_소스번호로_불러도_원본컷을_가린다():
    """2026-09-18 실측: 컷 번호는 플랫폼 id 접두어(DdOayfhAnpx-3)인데 백본은 's0'으로 불러
    '서브 먼저' 규칙이 원본 컷을 한 번도 못 알아봤다(씨앗 s0인데 원본 컷 10/29)."""
    sources = [{"video_id": "s0", "segments": [{"seg_id": "DdOayfhAnpx-%d" % i, "start": i, "end": i + 2, "scene_desc": "원본 행주 닦기"} for i in range(4)]},
               {"video_id": "s1", "segments": [{"seg_id": "tiktokXYZ-%d" % i, "start": i, "end": i + 2, "scene_desc": "서브 행주 닦기"} for i in range(4)]}]
    idx = ba._seg_index(sources)
    assert idx["DdOayfhAnpx-0"]["vid"] == "s0" and idx["tiktokXYZ-0"]["vid"] == "s1"
    groups = {"product": "행주", "groups": [{"name": "닦기", "cuts": ["DdOayfhAnpx-0", "DdOayfhAnpx-1", "tiktokXYZ-0", "tiktokXYZ-1"]}], "order": [0]}
    lines = [{"role": "solve", "text": "가" * 10, "group": 0}]
    bs, _ = ba.assign_cuts(lines, groups, idx, "s0")
    assert all(not s.startswith("DdOayfhAnpx") for s in bs[0]["segs"]), bs
