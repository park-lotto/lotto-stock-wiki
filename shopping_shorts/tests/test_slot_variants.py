"""v4(2026-08-02) — 슬롯을 후보 수만큼 뽑되 **1벌째는 v3 그대로**인가.

왜: 후보 3개가 같은 화면·같은 이야기로 나왔다(실측 job 8712570702b8:
s1-1→s1-5/6→s1-9→s0-9/10). 슬롯이 이야기를 하나만 만들고 대사 3벌이 그 위에 얹히는데,
대본은 원본 대사를 따라가는 게 원칙이라(_rewrite_block) 뼈대가 같으면 결과도 같다.

사장님 지시: "3개 중 1개는 그대로 둔다. 한번 해보고 아니면 v3로."
→ 벌A는 `_pick_slot_groups`를 그대로 부른다(프롬프트 무변경). 이 테스트가 그걸 못박는다.
"""
from shopping_shorts import edit_plan


def _sets(n_per_src=4):
    """소스 2개 × 세그 여러 개 — 세트가 여러 개 나와 여유가 생기게 한다."""
    out = []
    for si, vid in enumerate(("s0", "s1")):
        segs = []
        for i in range(n_per_src * 2):
            segs.append({"seg_id": f"{vid}-{i}", "video_id": vid,
                         "start": float(i * 2), "end": float(i * 2 + 2),
                         "text": f"{vid}문장{i}." if i % 2 == 0 else "",
                         "scene_desc": f"{vid} 장면{i}", "shot_role": "사용중"})
        out.append({"video_id": vid, "full_text": "원본", "segments": segs})
    return out


def _seg_map():
    seg_map, _ = edit_plan._build_inventory(_sets())
    return seg_map


def _fake_order(order_ids):
    def call(prompt, schema, **kw):
        if (schema or {}).get("required") == ["order"]:
            return {"order": list(order_ids)}
        return {}
    return call


def test_variant_a_is_identical_to_v3():
    """★핵심: 1벌째는 `_pick_slot_groups`와 완전히 같은 결과여야 한다.

    같은 Gemini 응답을 주입해 코드 경로만 비교한다 — 모델 비결정성을 배제해야
    '같다'를 단정할 수 있다."""
    sm = _seg_map()
    sets = edit_plan._cap_sets(edit_plan._build_source_sentence_sets(sm), 30)
    call = _fake_order([st["set_id"] for st in sets[:3]])

    v3_groups, v3_src, _ = edit_plan._pick_slot_groups(sm, 30, call=call)
    variants, v4_src, _, kinds = edit_plan._pick_slot_variants(sm, 30, n=3, call=call)

    assert [g[0]["seg_id"] for g in variants[0]] == [g[0]["seg_id"] for g in v3_groups]
    assert v4_src == v3_src
    assert kinds[0] == v3_src


def test_variants_differ_when_sets_are_spare():
    """여유가 있으면 2벌째부터는 다른 조합이 나온다(그게 이 기능의 목적이다)."""
    sm = _seg_map()
    sets = edit_plan._cap_sets(edit_plan._build_source_sentence_sets(sm), 30)
    if len(sets) < 4:
        return                      # 여유가 없는 fixture면 이 검사는 의미가 없다
    call = _fake_order([st["set_id"] for st in sets[:2]])   # 2개만 골라 여유를 남긴다
    variants, src, _, kinds = edit_plan._pick_slot_variants(sm, 30, n=3, call=call)
    ids = [tuple(g[0]["seg_id"] for g in v) for v in variants]
    assert len(set(ids)) > 1, f"벌이 전부 같다 — 차별화가 안 됐다: {ids}"


def test_variant_count_always_matches_request():
    """여유가 없어도 요청한 벌 수만큼 돌려준다(모자라면 A 복제 = v3와 동일)."""
    sm = _seg_map()
    sets = edit_plan._cap_sets(edit_plan._build_source_sentence_sets(sm), 30)
    call = _fake_order([st["set_id"] for st in sets])       # 전부 고름 → 여유 0
    variants, _src, _info, kinds = edit_plan._pick_slot_variants(sm, 30, n=3, call=call)
    assert len(variants) == 3
    assert len(kinds) == 3
    # 여유가 없으면 복제되므로 벌A와 같아야 한다(나빠지지 않는다)
    base = [g[0]["seg_id"] for g in variants[0]]
    for v, k in zip(variants[1:], kinds[1:]):
        if k == "cloned":
            assert [g[0]["seg_id"] for g in v] == base


def test_fallback_slot_source_is_not_recombined():
    """A가 폴백이었다면 변형하지 않는다 — 품질이 의심스러운데 조합을 늘릴 이유가 없다."""
    sm = _seg_map()
    call = _fake_order([])          # order 비었음 → _pick_timeline 폴백
    variants, src, _info, kinds = edit_plan._pick_slot_variants(sm, 30, n=3, call=call)
    assert src != edit_plan.SLOT_SOURCE_GEMINI
    assert all(k != "recombined" for k in kinds[1:]), kinds


def test_variants_keep_original_time_order():
    """조합은 '어느 세트를 쓸까'만 정한다 — 순서는 원본 시간순이어야 한다.

    코드가 순서를 창작하면 이야기가 거꾸로 흐른다(이 트랙이 반복해 겪은 실패).

    ★벌이 작으면(세트 2개) 같은 소스가 두 번 안 들어가 **역전이 생길 수가 없어**
      정렬을 뒤집어도 통과한다(가짜 green — 회귀 주입으로 실제로 확인했다).
      그래서 **한 소스에서 여러 세트를 고르게** 해 역전이 가능한 모양을 만든다."""
    sm = _seg_map()
    sets = edit_plan._cap_sets(edit_plan._build_source_sentence_sets(sm), 30)
    s0 = [st["set_id"] for st in sets if st["video_id"] == "s0"]
    s1 = [st["set_id"] for st in sets if st["video_id"] == "s1"]
    assert len(s0) >= 2 and len(s1) >= 2, "픽스처에 소스당 세트가 2개 이상 있어야 한다"
    # 한 소스에서 2개씩 고른다 → 벌 안에 같은 소스가 여러 번 들어가 역전 검사가 성립한다
    call = _fake_order([s0[0], s1[0], s0[1], s1[1]])
    variants, _src, _info, _k = edit_plan._pick_slot_variants(sm, 30, n=3, call=call)
    checked = 0
    for v in variants:
        seq = [(g[0]["video_id"], edit_plan._seg_seq(g[0]["seg_id"])[1]) for g in v]
        by_src = {}
        for vid, ix in seq:
            by_src.setdefault(vid, []).append(ix)
        if any(len(x) >= 2 for x in by_src.values()):
            checked += 1
        rev = sum(1 for a, b in zip(seq, seq[1:]) if a[0] == b[0] and b[1] < a[1])
        assert rev == 0, f"같은 소스 안에서 시간이 거꾸로 갔다: {seq}"
    assert checked, "역전이 가능한 벌이 하나도 없었다 — 이 검사는 아무것도 못 잡는다"
