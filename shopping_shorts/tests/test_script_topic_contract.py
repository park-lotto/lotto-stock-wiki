# -*- coding: utf-8 -*-
"""박선정님 6소스 사고 회귀: 선택 제품이 자료 순서·다제품 영상에 덮이지 않아야 한다."""
from shopping_shorts import script_gate
from shopping_shorts import script_generate as sg
from shopping_shorts.app import (_same_topic_product, _sources_for_generate,
                                 _topic_product_for_generate)
from shopping_shorts import topic_contract


SEED = "lens_youtube_vcp3ow"
COMPILATION = "lens_pinterest_1a6z7wf"
TOILET = "휴대용 차량 간이 변기"


def _brief(product):
    return {"source_brief": {"product": product},
            "segments": [{"seg_id": "x-0", "scene_desc": product}]}


def _real_case_job():
    # 실제 handoff 순서와 달리 shortcode 정렬 시 compilation이 앞으로 오는 조건까지 재현한다.
    return {"extract": {
        "lens_pinterest_cbmh0j": dict(_brief("휴대용 캠핑 변기"), full_text="캠핑 중 급할 때 쓰는 변기"),
        COMPILATION: dict(_brief("차량용 필수 액세서리 4종(컵홀더 트레이, 휴대용 화장실, 차량용 냉온장고, 점프 스타터)"),
                          full_text="컵홀더 트레이를 꽂으면 음료가 흔들리지 않습니다"),
        "lens_pinterest_wpksxu": dict(_brief("차량용 휴대용 변기"), full_text="차 안에서 쓰는 휴대용 변기"),
        "lens_pinterest_1quvexu": dict(_brief("차량용 휴대용 간이 변기"), full_text="아이의 급한 상황을 해결하는 간이 변기"),
        "lens_pinterest_1aajtrc": dict(_brief("휴대용 접이식 유아용 변기"), full_text="접이식 유아용 변기"),
        SEED: dict(_brief(TOILET), full_text=""),
    }}


class _Store:
    def get_script(self, shortcode):
        return _real_case_job()["extract"].get(shortcode)


def test_selected_silent_seed_becomes_authoritative_topic():
    job = _real_case_job()
    topic = _topic_product_for_generate({}, {"selected_shortcode": SEED}, job, _Store())
    assert topic == TOILET
    srcs = _sources_for_generate({}, job, preferred_shortcode=SEED, topic_product=topic)
    assert srcs[0]["source_id"] == SEED
    assert srcs[0]["topic_product"] == TOILET
    assert COMPILATION not in {s["source_id"] for s in srcs}
    assert all("컵홀더" not in s["full_text"] for s in srcs)
    assert len(srcs) == 5


def test_source_order_cannot_change_selected_topic():
    job = _real_case_job()
    job["extract"] = dict(reversed(list(job["extract"].items())))
    srcs = _sources_for_generate({}, job, preferred_shortcode=SEED, topic_product=TOILET)
    assert srcs[0]["source_id"] == SEED
    assert sg._sources_product(srcs) == TOILET


def test_similar_brand_or_use_target_is_not_same_product():
    assert not _same_topic_product("아이폰 케이스", "아이폰 충전기")
    assert not _same_topic_product("삼성 냉장고", "삼성 청소기")
    assert not _same_topic_product("화장실 변기 청소솔", "휴대용 변기")
    assert not _same_topic_product("휴대용 변기청소솔", "휴대용 변기")
    assert _same_topic_product("아이폰 케이스 투명", "투명 아이폰 케이스")
    assert not _same_topic_product(TOILET, "")


def test_tied_products_are_ambiguous_regardless_of_order_and_frozen_topic_resolves():
    products = ["차량용 컵홀더 트레이", TOILET]
    assert topic_contract.consensus(products) == ("", True)
    assert topic_contract.consensus(list(reversed(products))) == ("", True)
    job = {"extract": {"a": _brief(products[0]), "b": _brief(products[1])}}
    assert _topic_product_for_generate({}, {}, job, _Store()) is None
    assert _topic_product_for_generate({}, {"topic_product": TOILET}, job, _Store()) == TOILET


def test_frozen_topic_cannot_be_silently_replaced_by_new_majority():
    job = {"extract": {"a": _brief("컵홀더 트레이"),
                       "b": _brief("차량용 컵홀더 트레이"),
                       "c": _brief(TOILET)}}
    assert _topic_product_for_generate(
        {}, {"topic_product": TOILET}, job, _Store()) is None


def test_wrong_preferred_source_cannot_bypass_topic_filter():
    job = _real_case_job()
    srcs = _sources_for_generate({}, job, preferred_shortcode=COMPILATION,
                                 topic_product=TOILET)
    assert COMPILATION not in {s["source_id"] for s in srcs}


def test_explicit_transplant_topic_keeps_reference_source_and_locks_output_topic():
    srcs = _sources_for_generate(
        {"full_text": "원본 컵홀더 대본", "source_brief": {"product": "컵홀더 트레이"}},
        {}, topic_product=TOILET, explicit_topic=True)
    assert len(srcs) == 1
    assert srcs[0]["topic_product"] == TOILET
    assert srcs[0]["topic_semantic_required"] is True


def test_explicit_product_topic_still_runs_semantic_mixed_product_gate(monkeypatch):
    srcs = _sources_for_generate(
        {"full_text": "원본 컵홀더 대본", "source_brief": {"product": "컵홀더 트레이"}},
        {}, topic_product=TOILET, explicit_topic=True)
    monkeypatch.setattr(sg, "generate_variations", lambda *_a, **_k: [
        {"hook": "h", "script": "화장실도 있지만 핵심은 컵홀더 트레이예요."}])
    monkeypatch.setattr(sg, "_speaker_judge", lambda *_a, **_k: {"topic_ok": False})
    out = sg.generate_guarded_variations({}, srcs, {}, {}, mode="transplant",
                                         my_topic=TOILET, n=1)
    # ★2026-09-25 계약 변경: 이식 주제(변기)에 대한 **한국어 관측이 재료에 없으면** 0안이다.
    #   종전엔 "이 영상에서 확인한 제품은 변기…입니다 / 댓글에 남겨주세요" 두 줄 껍데기를 1안으로
    #   내보냈다 — 영상엔 컵홀더가 나오는데 변기를 확인했다고 말하는 지어낸 문장이다.
    #   샌 제품(컵홀더)이 화면에 안 나오는 계약은 그대로다.
    assert out == []


def test_non_product_free_subject_does_not_require_product_semantic_judge():
    srcs = _sources_for_generate({"full_text": "원본"}, {}, topic_product="물때 청소",
                                 explicit_topic=True)
    assert srcs[0]["topic_semantic_required"] is False


def test_single_product_rejects_multi_product_compilation_but_roundup_allows_it():
    compilation = "차량용 액세서리 4종(컵홀더 트레이, 휴대용 화장실, 냉장고, 점프 스타터)"
    assert not _same_topic_product(TOILET, compilation)
    assert _same_topic_product(compilation, "차량용 컵홀더 트레이")


def test_prompt_uses_explicit_topic_even_if_first_material_product_is_wrong():
    block = sg._mix_source_block([
        {"topic_product": TOILET, "product": "차량용 액세서리 4종", "full_text": "컵홀더", "structure": {}},
        {"product": "유아용 변기", "full_text": "변기", "structure": {}},
    ])
    assert "우리 영상의 제품 = 「%s」" % TOILET in block
    assert sg._sources_product([{"topic_product": TOILET, "product": "컵홀더"}]) == TOILET


def test_generic_vehicle_word_no_longer_approves_cupholder_script():
    checks = script_gate.fatal_content_checks(
        "차량용 컵홀더 트레이는 큰 음료도 흔들림 없이 잡아줍니다.", product=TOILET)
    subject = next(c for c in checks if c["name"] == "소재 일치")
    assert subject["ok"] is False


def test_semantic_gate_rejects_mixed_product_even_with_toilet_word():
    style = {"beat_roles": []}
    beats = [{"role": "", "text": "변기도 좋지만 컵홀더 트레이는 큰 음료를 잡아줘요."}]
    checks, _ = script_gate.check(
        style, beats, product=TOILET, topic_required=True,
        speaker_judge=lambda _text, _product: {
            "ok": True, "why": "", "topic_ok": False,
            "topic_why": "컵홀더가 중심 제품", "foreign_products": ["컵홀더 트레이"]})
    assert script_gate.fatal_fail(checks) == "주제 단일성"


def test_semantic_gate_accepts_toilet_synonyms():
    style = {"beat_roles": []}
    beats = [{"role": "", "text": "아이 급할 때 차 안에서 펼치는 휴대용 화장실이에요."}]
    checks, _ = script_gate.check(
        style, beats, product=TOILET, topic_required=True,
        speaker_judge=lambda _text, _product: {
            "ok": True, "why": "", "topic_ok": True,
            "topic_why": "", "foreign_products": []})
    assert not script_gate.fatal_fail(checks)


def test_topic_judge_failure_is_closed_for_locked_topic():
    checks, _ = script_gate.check(
        {"beat_roles": []}, [{"role": "", "text": "휴대용 변기"}],
        product=TOILET, topic_required=True,
        speaker_judge=lambda *_args: {})
    assert script_gate.fatal_fail(checks) == "주제 단일성"


def test_locked_topic_without_judge_is_closed():
    checks, _ = script_gate.check(
        {"beat_roles": []}, [{"role": "", "text": "휴대용 변기"}],
        product=TOILET, topic_required=True, speaker_judge=None)
    assert script_gate.fatal_fail(checks) == "주제 단일성"


def test_wow_subject_prefers_frozen_topic():
    from shopping_shorts.app import _wow_subject
    assert _wow_subject([{"product": "컵홀더", "topic_product": TOILET}]) == TOILET


def test_product_facts_with_different_or_unknown_linked_product_are_blocked():
    from shopping_shorts.app import _facts_for_job

    class Store:
        def __init__(self, name): self.name = name
        def get_mix_job(self, _jid):
            return {"product": {"name": self.name, "facts": {"features": ["컵홀더 사실"]}},
                    "extract": {}}

    assert _facts_for_job("j", Store("컵홀더 트레이"), TOILET) == {}
    assert _facts_for_job("j", Store(""), TOILET) == {}


def test_locked_topic_never_uses_unscoped_prefetched_first_url(monkeypatch):
    from shopping_shorts import app as app_mod

    class Store:
        def get_mix_job(self, _jid):
            return {"product": {"name": TOILET, "facts": {}}, "urls": ["cup", "toilet"],
                    "extract": {"cup": _brief("컵홀더 트레이"), "toilet": _brief(TOILET)}}

    monkeypatch.setattr(app_mod, "_prefetched_facts_for_job",
                        lambda *_a: (_ for _ in ()).throw(AssertionError("호출되면 안 됨")))
    monkeypatch.setattr(app_mod, "_llm_facts_for_job", lambda job, _st: {
        "product": next(iter(job["extract"].values()))["source_brief"]["product"]})
    assert app_mod._facts_for_job("j", Store(), TOILET) == {"product": TOILET}


def test_aipick_carries_product_identity():
    from shopping_shorts.aipick import build_aipick
    out = build_aipick([{"video_id": "v", "text": "변기", "comments": 1,
                         "product": TOILET}], {})
    assert out["pick_meta"]["product"] == TOILET
    assert out["candidates"][0]["product"] == TOILET


def test_material_bundle_filters_scene_facts_with_same_topic(monkeypatch):
    from shopping_shorts import app as app_mod

    class Store:
        def get_mix_job(self, _jid):
            return None
        def get_produce_work(self, _wid, customer_id=0):
            return {"state": {"handoff": [
                {"shortcode": k, "useFootage": True, "url": "https://x/" + k}
                for k in _real_case_job()["extract"]]}}
        def get_script(self, shortcode):
            return _real_case_job()["extract"].get(shortcode)

    monkeypatch.setattr(app_mod, "_sul_block_for_sources", lambda *_a, **_k: "")
    monkeypatch.setattr(app_mod, "_wow_block_for", lambda *_a, **_k: "")
    srcs, _facts, job, _jid, scene = app_mod._materials_for_generate(
        {}, {"work_id": "w", "selected_shortcode": SEED}, Store(), 174)
    assert sg._sources_product(srcs) == TOILET
    assert COMPILATION not in job["extract"]
    assert "컵홀더" not in scene


def test_multi_product_list_style_does_not_require_single_topic_consensus(monkeypatch):
    from shopping_shorts import app as app_mod

    class Store:
        def get_mix_job(self, _jid): return None
        def get_produce_work(self, _wid, customer_id=0):
            return {"state": {"handoff": [
                {"shortcode": "a", "useFootage": True},
                {"shortcode": "b", "useFootage": True}]}}
        def get_script(self, sc):
            return _brief("컵홀더 트레이" if sc == "a" else TOILET)

    monkeypatch.setattr(app_mod, "_sul_block_for_sources", lambda *_a, **_k: "")
    monkeypatch.setattr(app_mod, "_wow_block_for", lambda *_a, **_k: "")
    srcs, *_ = app_mod._materials_for_generate(
        {}, {"work_id": "w"}, Store(), 174, spines=[{"is_list": True}])
    assert {s["product"] for s in srcs} == {"컵홀더 트레이", TOILET}
    import pytest
    with pytest.raises(ValueError):
        app_mod._materials_for_generate(
            {}, {"work_id": "w"}, Store(), 174,
            spines=[{"is_list": True}, {"is_list": False}])
    with pytest.raises(ValueError):
        app_mod._materials_for_generate(
            {}, {"work_id": "w", "topic_product": "전혀 다른 냉장고"}, Store(), 174,
            spines=[{"is_list": True}])


def test_work_with_no_linked_job_ignores_stale_same_customer_job(monkeypatch):
    from shopping_shorts import app as app_mod

    class Store:
        def get_mix_job(self, _jid):
            return {"customer_id": 174, "extract": {"old": _brief("컵홀더 트레이")}}
        def get_produce_work(self, _wid, customer_id=0):
            return {"job_id": None, "state": {"handoff": [
                {"shortcode": "new", "useFootage": True}]}}
        def get_script(self, _sc): return dict(_brief(TOILET), full_text="휴대용 변기")

    monkeypatch.setattr(app_mod, "_sul_block_for_sources", lambda *_a, **_k: "")
    monkeypatch.setattr(app_mod, "_wow_block_for", lambda *_a, **_k: "")
    srcs, _facts, _job, jid, _scene = app_mod._materials_for_generate(
        {}, {"work_id": "w", "job_id": "old"}, Store(), 174)
    assert jid == ""
    assert {s["product"] for s in srcs} == {TOILET}


def test_beat_regen_restores_saved_explicit_topic_contract(monkeypatch):
    from shopping_shorts import app as app_mod

    class Store:
        def get_mix_job(self, _jid):
            return {"customer_id": 174, "extract": {
                "cup": dict(_brief("컵홀더 트레이"), full_text="컵홀더 원본")}}
        def get_produce_work(self, _wid, customer_id=0):
            return {"job_id": "j", "state": {"s2": {"materials": {
                "topic_product": TOILET, "topic_explicit": True}}}}

    monkeypatch.setattr(app_mod, "_sul_block_for_sources", lambda *_a, **_k: "")
    monkeypatch.setattr(app_mod, "_wow_block_for", lambda *_a, **_k: "")
    srcs, *_ = app_mod._materials_for_generate(
        {}, {"work_id": "w", "job_id": "j", "topic_product": TOILET}, Store(), 174)
    assert len(srcs) == 1 and srcs[0]["product"] == "컵홀더 트레이"
    assert srcs[0]["topic_product"] == TOILET
    assert srcs[0]["topic_semantic_required"] is True


def test_pickup_rejects_semantically_mixed_product(monkeypatch):
    sources = [{"full_text": "아이 급할 때 쓰는 휴대용 변기", "product": TOILET,
                "topic_product": TOILET}]
    monkeypatch.setattr(sg, "generate_variations", lambda *_a, **_k: [
        {"hook": "변기", "script": "변기도 있지만 컵홀더 트레이가 큰 음료를 잡아줘요."}])
    monkeypatch.setattr(sg, "_speaker_judge", lambda *_a, **_k: {
        "ok": True, "why": "", "topic_ok": False,
        "topic_why": "컵홀더가 중심", "foreign_products": ["컵홀더 트레이"]})
    reasons = []
    out = sg.generate_guarded_variations({}, sources, {}, {}, n=1,
                                         rejection_reasons=reasons)
    assert len(out) == 1 and out[0]["made_by"] == "장면근거"
    assert TOILET in out[0]["script"] and "컵홀더" not in out[0]["script"]
    assert reasons and all(r["detail"] == "주제 단일성" for r in reasons)


def test_beat_regen_retries_topic_leak_then_accepts(monkeypatch):
    replies = iter([{"text": "컵홀더 트레이는 음료를 잡아줘요"},
                    {"text": "아이 급할 때 차 안에서 펼쳐 쓰면 돼요"}])
    monkeypatch.setattr(sg, "_call_json", lambda *_a, **_k: next(replies))
    judged = []
    def judge(text, product, **_kw):
        judged.append((text, product))
        return {"topic_ok": "컵홀더" not in text, "claims_ok": True,
                "claims_why": "", "claim_checks": [{"unit_index": i, "claim": t, "kind": "subjective",
                                  "supported": True, "supports": []}
                                 for i, t in enumerate(script_gate.claim_units(text))],
                "unsupported_claims": []}
    beats = [{"role": "hook", "text": "차에서 아이가 급하면 당황하죠"},
             {"role": "body", "text": "휴대용 변기를 펼쳐 쓰는 방식이에요"}]
    out = sg.regen_one_beat(
        [{"full_text": "휴대용 변기", "product": TOILET, "topic_product": TOILET}],
        {"beat_roles": ["hook", "body"], "templates": {}}, "hook", beats,
        topic_product=TOILET, topic_judge=judge)
    assert out and "컵홀더" not in out["text"]
    assert out["tries"][0]["fails"] == ["주제이탈"]
    assert all(p == TOILET for _t, p in judged)


def test_beat_regen_topic_check_replaces_only_requested_duplicate_role(monkeypatch):
    monkeypatch.setattr(sg, "_call_json", lambda *_a, **_k: {"text": "새 변기 문장"})
    seen = []
    def judge(text, _product, **_kw):
        seen.append(text)
        return {"topic_ok": True, "claims_ok": True, "claims_why": "", "claim_checks": [{"unit_index": i, "claim": t, "kind": "subjective",
                                  "supported": True, "supports": []}
                                 for i, t in enumerate(script_gate.claim_units(text))],
                "unsupported_claims": []}
    beats = [{"role": "item", "text": "첫 변기"},
             {"role": "item", "text": "둘째 변기"}]
    out = sg.regen_one_beat(
        [{"full_text": "휴대용 변기", "product": TOILET, "topic_product": TOILET}],
        {"beat_roles": ["item"], "templates": {}}, "item", beats,
        topic_product=TOILET, topic_judge=judge, beat_index=1)
    assert out
    assert "첫 변기\n새 변기 문장" in seen[0]


def test_beat_regen_rejects_out_of_range_or_wrong_role_index(monkeypatch):
    monkeypatch.setattr(sg, "_call_json", lambda *_a, **_k: {"text": "컵홀더 문장"})
    beats = [{"role": "hook", "text": "휴대용 변기"}]
    kw = dict(topic_product=TOILET, topic_judge=lambda *_a: {"topic_ok": True})
    assert sg.regen_one_beat([], None, "hook", beats, beat_index=99, **kw) is None
    assert sg.regen_one_beat([], None, "body", beats, beat_index=0, **kw) is None
