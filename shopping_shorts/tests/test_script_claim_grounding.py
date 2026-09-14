# -*- coding: utf-8 -*-
"""실제 변기 사고의 사실근거 경계와 모든 생성 출구를 검증한다. AI 의미 정확도는 실생성 QA 몫."""
import copy
import json

import pytest

from shopping_shorts import product_facts, script_gate as gate, script_generate as sg, wow_facts


PRODUCT = "휴대용 차량 간이 변기"


def sources():
    return [{"source_id": "toilet", "product": PRODUCT, "topic_product": PRODUCT,
             "topic_semantic_required": True, "full_text": "휴대용 변기를 펼칩니다.",
             "structure": {"hook": "현지에서 없어서 못 구한다"},
             "segments": [
                 {"seg_id": "toilet-0", "scene_desc": "변기를 펼쳐 비닐을 씌운다.",
                  "change": "접힌 변기가 펼쳐진다.", "use_point": "냄새를 완전 차단한다.",
                  "product_benefits": ["내구성이 좋아 급똥이 끝난다."]},
                 {"seg_id": "toilet-1", "scene_desc": "가루에 물을 붓자 젤로 뭉친다.",
                  "change": "액체가 젤처럼 뭉친다."},
                 {"seg_id": "toilet-2", "scene_desc": "사람이 변기 위에 앉는다."}]}]


def verdict(ok=True, claim="", reason="근거가 없다", text=""):
    return {"ok": True, "why": "", "topic_ok": True, "topic_why": "", "foreign_products": [],
            "claims_ok": ok, "claims_why": "" if ok else reason,
            "claim_checks": [{"unit_index": i, "claim": unit, "kind": "subjective",
                              "supported": ok, "supports": []}
                             for i, unit in enumerate(gate.claim_units(text))],
            "unsupported_claims": [] if ok else [{"beat_index": 0, "claim": claim,
                                                 "reason": reason, "evidence_ids": ["toilet-0"]}]}


def test_evidence_keeps_observation_and_excludes_template_and_interpretation():
    evidence = sg.claim_evidence(sources(), "[은행] 현지에서 품절대란\n[AI 지식] 몇만 원")
    rendered = json.dumps(evidence, ensure_ascii=False)
    assert "변기를 펼쳐 비닐을 씌운다" in rendered
    assert "사람이 변기 위에 앉는다" in rendered
    assert "못 구한다" not in rendered
    assert "완전 차단" not in rendered
    assert "급똥이 끝난다" not in rendered
    assert "몇만 원" not in rendered


def test_evidence_accepts_only_closed_verified_blocks_and_wow_claim():
    facts = (product_facts.CONFIRMED_FACTS_MARK + "\n- 확인된 가격: 25000원\n"
             + product_facts.CONFIRMED_FACTS_END + "\n[AI 확장] 몇백만 원\n"
             + wow_facts.WOW_MARK + " — 시청자가 모르는 것]\n"
             + "- 가루는 물을 흡수한다 (근거: 연구 https://example.org/research / 설명: 냄새분자 완전차단)\n"
             + wow_facts.WOW_END + "\n[스타일] 품절대란")
    evidence = sg.claim_evidence(sources(), facts)
    assert "25000원" in evidence["verified_product_facts"][0]
    assert evidence["verified_wow"] == [
        {"claim": "가루는 물을 흡수한다", "provenance": "연구 https://example.org/research"}]
    assert "몇백만" not in json.dumps(evidence, ensure_ascii=False)
    assert "완전차단" not in json.dumps(evidence, ensure_ascii=False)
    assert sg.claim_evidence([], product_facts.CONFIRMED_FACTS_MARK + " 가격 1원")[
        "verified_product_facts"] == []


def test_transplant_reference_product_is_never_target_evidence():
    refs = sources()
    refs[0].update(product="컵홀더 트레이", full_text="컵홀더는 360도 회전합니다.")
    evidence = sg.claim_evidence(refs)
    assert evidence["source_observations"] == []
    assert "타제품 원본은 말투·구조 참고일 뿐" in sg._CLAIM_JUDGE_RULE


def test_judge_uses_one_real_call_boundary_and_separate_claim_schema(monkeypatch):
    calls = []
    monkeypatch.setattr(sg, "_call_json", lambda prompt, schema: calls.append((prompt, schema)) or verdict())
    evidence = sg.claim_evidence(sources())
    assert sg._speaker_judge("변기를 펼치면 되니 편하겠네요.", PRODUCT, evidence)["claims_ok"] is True
    assert len(calls) == 1
    assert calls[0][1] is sg._CLAIM_SPEAKER_SCHEMA
    assert "몇만 원" in calls[0][0] and "의학적 단정·인과 오류" in calls[0][0]
    assert "주관적 감탄" in calls[0][0]
    sg._speaker_judge("물때 청소가 편해요", "물때 청소")
    assert calls[1][1] is sg._SPEAKER_SCHEMA


@pytest.mark.parametrize("claim", [
    "단돈 몇만 원에 변기를 살 수 있습니다.",
    "현지선 없어서 못 구하는 변기입니다.",
    "내구성이 미쳐서 배 아픈 상황이 끝납니다.",
    "급똥을 참으면 방광에 최악입니다.",
    "냄새 분자까지 완전히 차단합니다.",
])
def test_unsupported_verdict_is_fatal_even_when_topic_matches(claim):
    checks = gate.semantic_content_checks(
        claim, PRODUCT, lambda *_a, **_k: verdict(False, claim),
        evidence=sg.claim_evidence(sources()), topic_required=True, claims_required=True)
    assert gate.fatal_fail(checks) == "사실 근거"
    assert claim in next(c["detail"] for c in checks if c["name"] == "사실 근거")


@pytest.mark.parametrize("response", [{}, {"topic_ok": True},
    {"topic_ok": True, "claims_ok": True},
    {"topic_ok": True, "claims_ok": True, "unsupported_claims": "invalid"},
    dict(verdict(), unsupported_claims=[{"claim": "품절", "reason": "근거없음"}])])
def test_missing_malformed_or_contradictory_claim_verdict_is_closed(response):
    checks = gate.semantic_content_checks(
        "변기", PRODUCT, lambda *_a, **_k: response,
        evidence=sg.claim_evidence(sources()), claims_required=True)
    assert gate.fatal_fail(checks) == "사실 근거"


def test_legacy_nonproduct_and_supported_subjective_expression_are_preserved():
    assert not gate.semantic_content_checks("물때 청소", "", None)
    checks = gate.semantic_content_checks(
        "펼치고 봉투만 씌우면 되니 편리함이 미쳤네요.", PRODUCT,
        lambda text, *_a, **_k: verdict(text=text), evidence=sg.claim_evidence(sources()), claims_required=True)
    assert not gate.fatal_fail(checks)


def test_style_rejects_unsupported_claim_and_sends_observation_fallback(monkeypatch):
    prompts = []
    monkeypatch.setattr(sg, "STYLE_REWRITES", 0)
    monkeypatch.setattr(sg, "_style_extra", lambda: "[스타일 예시] 현지선 없어서 못 구함")
    monkeypatch.setattr(sg, "_call_json", lambda prompt, *_a, **_k:
                        prompts.append(prompt) or {"beats": [{"role": "hook", "text": "변기는 몇만 원입니다."}]})
    received = []
    def judge(text, product, evidence=None):
        received.append(evidence)
        return verdict(False, "몇만 원", "가격 근거 없음")
    monkeypatch.setattr(sg, "_speaker_judge", judge)
    note = {}
    assert sg.generate_one_style(sources(), {"beat_roles": ["hook"]}, note=note) is None
    assert note["reason"] == "근거부족"
    assert received[0] == sg.claim_evidence(sources())
    assert "그 칸을 확인된 동작이나 사용 상황으로 다시 써라" in prompts[0]


def test_trim_rejudges_actual_final_text_instead_of_reusing_claim_success(monkeypatch):
    from shopping_shorts import edit_plan
    monkeypatch.setattr(sg, "STYLE_REWRITES", 0)
    monkeypatch.setattr(sg, "_style_extra", lambda: "")
    text = "휴대용 변기를 펼쳐 비닐을 씌워 사용하는 모습을 보여줍니다. " * 12
    monkeypatch.setattr(sg, "_call_json", lambda *_a, **_k: {"beats": [{"role": "hook", "text": text}]})
    monkeypatch.setattr(edit_plan, "_trim_to_budget", lambda *_a: "변기는 냄새분자를 완전히 차단한다")
    seen = []
    def judge(script, product, evidence=None):
        seen.append(script)
        return verdict("냄새분자" not in script, "냄새분자 완전 차단", text=script)
    monkeypatch.setattr(sg, "_speaker_judge", judge)
    note = {}
    assert sg.generate_one_style(sources(), {"beat_roles": ["hook"], "chars_per_30s": 100}, note=note) is None
    assert len(seen) == 2 and seen[-1] == "변기는 냄새분자를 완전히 차단한다"
    assert note["reason"] == "근거부족"


def test_partial_checks_exact_merged_script_and_blocks_claim_left_in_other_slot(monkeypatch):
    monkeypatch.setattr(sg, "BEAT_REGEN_TRIES", 0)
    monkeypatch.setattr(sg, "_style_extra", lambda: "")
    monkeypatch.setattr(sg, "_call_json", lambda *_a, **_k: {"text": "변기를 접어 넣으면 편해요"})
    beats = [{"role": "use", "text": "변기를 펼치고 비닐을 씌우면 돼요"},
             {"role": "use", "text": "현지선 없어서 못 구해요"}]
    seen = []
    def judge(text, product, evidence=None):
        seen.append(text)
        return verdict(False, "현지선 없어서 못 구해요")
    assert sg.regen_one_beat(sources(), None, "use", beats=copy.deepcopy(beats),
                            beat_index=0, topic_product=PRODUCT, topic_judge=judge) is None
    assert seen[0] == "변기를 접어 넣으면 편해요 현지선 없어서 못 구해요"


def test_partial_can_replace_unsupported_template_with_supported_action(monkeypatch):
    monkeypatch.setattr(sg, "BEAT_REGEN_TRIES", 0)
    monkeypatch.setattr(sg, "_style_extra", lambda: "")
    monkeypatch.setattr(sg, "_call_json", lambda *_a, **_k: {"text": "변기를 접어 가방에 넣어요"})
    style = {"beat_roles": ["scale"], "templates": {"scale": ["현지선 없어서 못 구해요"]}}
    judged = []
    result = sg.regen_one_beat(sources(), style, "scale",
        beats=[{"role": "scale", "text": "현지선 없어서 못 구해요"}], beat_index=0,
        topic_product=PRODUCT, topic_judge=lambda text, *_a, **_k: judged.append(text) or verdict(text=text))
    assert result and result["text"] == "변기를 접어 가방에 넣어요"
    assert result["matched"] is True and result["template"] == ""
    assert judged == ["변기를 접어 가방에 넣어요"]


def test_partial_new_candidate_gets_new_judgment_but_final_identical_text_reuses_it(monkeypatch):
    monkeypatch.setattr(sg, "BEAT_REGEN_TRIES", 1)
    monkeypatch.setattr(sg, "_style_extra", lambda: "")
    candidates = iter(["몇만 원에 변기를 삽니다", "변기를 접어 가방에 넣어요"])
    monkeypatch.setattr(sg, "_call_json", lambda *_a, **_k: {"text": next(candidates)})
    judged = []
    def judge(text, *_a, **_k):
        judged.append(text)
        return verdict("몇만" not in text, "몇만 원", "가격 근거 없음", text=text)
    result = sg.regen_one_beat(sources(), None, "use",
        beats=[{"role": "use", "text": "변기를 펼치고 비닐을 씌우면 돼요"}], beat_index=0,
        topic_product=PRODUCT, topic_judge=judge)
    assert result and result["text"] == "변기를 접어 가방에 넣어요"
    assert judged == ["몇만 원에 변기를 삽니다", "변기를 접어 가방에 넣어요"]


def test_pickup_uses_same_evidence_gate_and_keeps_valid_draft(monkeypatch):
    monkeypatch.setattr(sg, "PICKUP_MATERIAL_REWRITES", 0)
    kwargs_seen = []
    def generate(*_args, **kwargs):
        kwargs_seen.append(kwargs)
        return [{"script": "변기가 현지서 품절입니다."}, {"script": "변기를 펼치면 편하겠네요."}]
    monkeypatch.setattr(sg, "generate_variations", generate)
    monkeypatch.setattr(sg, "_speaker_judge", lambda text, *_a, **_k:
                        verdict("품절" not in text, "품절", text=text))
    reasons = []
    result = sg.generate_guarded_variations({}, sources(), {}, {}, n=2, rejection_reasons=reasons)
    assert [x["script"] for x in result] == ["변기를 펼치면 편하겠네요."]
    assert reasons[0]["reason"] == "근거부족"
    assert "사실 판정에 사용하는 근거" in kwargs_seen[0]["claim_context"]
    assert any(c["name"] == "사실 근거" and c["ok"] for c in result[0]["checks"])
    assert any(c["name"] == "주제 단일성" and c["ok"] for c in result[0]["checks"])


def test_pickup_retry_gets_specific_failed_claim_feedback(monkeypatch):
    monkeypatch.setattr(sg, "PICKUP_MATERIAL_REWRITES", 1)
    contexts = []
    def generate(*_args, **kwargs):
        contexts.append(kwargs["claim_context"])
        text = "현지선 변기가 품절입니다." if len(contexts) == 1 else "변기를 펼치니 편해요."
        return [{"script": text}]
    monkeypatch.setattr(sg, "generate_variations", generate)
    monkeypatch.setattr(sg, "_speaker_judge", lambda text, *_a, **_k:
                        verdict("품절" not in text, "현지선 변기가 품절입니다.", "재고 자료가 없다", text=text))
    result = sg.generate_guarded_variations({}, sources(), {}, {}, n=1)
    assert len(result) == 1 and "품절" not in result[0]["script"]
    assert "현지선 변기가 품절입니다." in contexts[1]
    assert "재고 자료가 없다" in contexts[1]


def audited_verdict(text, evidence_id, quote, kind="objective"):
    out = verdict(text=text)
    out["claim_checks"] = [{"unit_index": i, "claim": unit, "kind": kind,
                            "supported": True, "supports": [{"evidence_id": evidence_id, "quote": quote}]}
                           for i, unit in enumerate(gate.claim_units(text))]
    return out


@pytest.mark.parametrize("text", [
    "펼쳐서 비닐만 씌우면 끝이라 1분도 안 걸려요.",
    "응고제로 액체가 굳으니까 차 안 냄새 걱정할 필요도 없더라고.",
    "차에 쟁여두는 분들이 늘면서 입소문이 쫙 퍼졌거든요.",
    "실제로 요즘 차량 필수템으로 난리가 났대요.",
    "몇만 원이면 이 변기를 살 수 있어요.",
])
def test_phase2_real_claims_cannot_pass_with_unrelated_visual_quote(text):
    evidence = sg.claim_evidence(sources())
    response = audited_verdict(text, "scene:toilet:toilet-0:visual", "변기를 펼쳐 비닐을 씌운다.")
    checks = gate.semantic_content_checks(text, PRODUCT, lambda *_a, **_k: response,
                                          evidence=evidence, claims_required=True)
    assert gate.fatal_fail(checks) == "사실 근거"


def test_claim_coverage_rejects_omitted_sentence_duplicate_and_changed_claim():
    text = "변기를 펼쳐요. 현지에서 입소문이 퍼졌어요."
    evidence = sg.claim_evidence(sources())
    response = verdict(text=text)
    for rows in ([response["claim_checks"][0]],
                 [response["claim_checks"][0], response["claim_checks"][0]],
                 [dict(row, claim="다른 문장") for row in response["claim_checks"]]):
        broken = dict(response, claim_checks=rows)
        assert gate._claim_audit_errors(text, evidence, broken)


@pytest.mark.parametrize("text", ["입소문이 쫙 퍼졌어요.", "냄새 걱정이 없어요.", "1분이면 설치돼요."])
def test_objective_risk_cannot_be_labeled_subjective(text):
    assert gate._claim_audit_errors(text, sg.claim_evidence(sources()), verdict(text=text))


def test_numeric_evidence_is_fatal_only_when_required_and_uses_actual_scene_text():
    evidence = sg.claim_evidence(sources())
    assert gate.grounded_quantity_check("1분 안에 설치", evidence) == (False, ["1분"])
    evidence["items"].append({"evidence_id": "scene:timed", "kind": "visual",
                              "text": "영상 속 설치 타이머가 60초를 표시한다."})
    assert gate.grounded_quantity_check("1분 안에 설치", evidence) == (True, [])
    assert gate.grounded_quantity_check("1.5분 걸려요", evidence)[0] is False
    assert gate.fatal_fail([{"name": "수치 근거", "ok": False, "fatal": True}]) == "수치 근거"
    assert not gate.fatal_fail([{"name": "수치 근거", "ok": False}])


@pytest.mark.parametrize("price", ["2만원", "20,000원"])
def test_different_price_is_not_supported_by_similar_quote(price):
    text = "가격은 %s입니다." % price
    evidence = {"items": [{"evidence_id": "product:0", "kind": "product_fact", "text": "판매 가격은 1만원이다."}]}
    response = audited_verdict(text, "product:0", "판매 가격은 1만원이다.")
    assert gate._claim_audit_errors(text, evidence, response)


def test_negative_odor_statement_cannot_support_no_odor_and_genuine_odor_evidence_can():
    text = "사용 후 냄새 걱정이 없어요."
    for source_text, accepted in [("사용 후 냄새가 난다.", False), ("사용 후 냄새가 나지 않는다.", True)]:
        evidence = {"items": [{"evidence_id": "source:review:transcript", "kind": "transcript", "text": source_text}]}
        response = audited_verdict(text, "source:review:transcript", source_text)
        assert bool(gate._claim_audit_errors(text, evidence, response)) is not accepted


def test_invented_quote_or_id_is_rejected_even_when_model_claims_success():
    text = "변기를 펼쳐 비닐을 씌워요."
    evidence = sg.claim_evidence(sources())
    for evidence_id, quote in [("nonexistent", "변기를 펼쳐 비닐을 씌운다."),
                               ("scene:toilet:toilet-0:visual", "실험실에서 위생성이 검증됐다.")]:
        assert gate._claim_audit_errors(text, evidence, audited_verdict(text, evidence_id, quote))


def test_live_quote_sentence_separator_variation_preserves_real_evidence():
    text = "사용한 봉투는 꺼내 묶어서 정리해요."
    evidence_id = "scene:toilet:bag:visual"
    evidence = {"items": [{"evidence_id": evidence_id, "kind": "visual",
        "text": "변기에서 비닐을 제거하고 묶는 모습\n사용했던 비닐이 밀봉되어 제거된다."}]}
    quote = "변기에서 비닐을 제거하고 묶는 모습. 사용했던 비닐이 밀봉되어 제거된다."
    assert not gate._claim_audit_errors(text, evidence, audited_verdict(text, evidence_id, quote))
    changed = quote.replace("밀봉되어 제거", "완전히 살균")
    assert gate._claim_audit_errors(text, evidence, audited_verdict(text, evidence_id, changed))
    assert gate._quote_norm("1.5분") != gate._quote_norm("15분")
    assert gate._quote_norm("0.5만원") != gate._quote_norm("05만원")


def test_actual_observation_and_normal_subjective_reaction_remain_allowed():
    text = "변기를 펼쳐 비닐을 씌워요. 편하겠네요!"
    evidence = sg.claim_evidence(sources())
    response = verdict(text=text)
    response["claim_checks"][0] = audited_verdict(
        gate.claim_units(text)[0], "scene:toilet:toilet-0:visual", "변기를 펼쳐 비닐을 씌운다.")["claim_checks"][0]
    assert not gate._claim_audit_errors(text, evidence, response)


def test_claim_units_preserve_decimals_quotes_newlines_and_unpunctuated_beats():
    assert gate.claim_units('1.5분이 걸려요. "가격은 2.5만원이에요."\n접어서 보관해요') == [
        "1.5분이 걸려요.", '"가격은 2.5만원이에요."', "접어서 보관해요"]
    assert gate.claim_units("변기를 펼침 봉투 장착 다시 접음") == ["변기를 펼침 봉투 장착 다시 접음"]
    assert gate._quantities("이 장면은 이 분이 설명합니다.") == []


def test_locked_generation_omits_inferred_benefits_and_usage_advice():
    text = sg._mix_source_block(sources(), full_scenes=True)
    assert "냄새를 완전 차단" not in text and "내구성이 좋아 급똥" not in text
    assert "변기를 펼쳐 비닐을 씌운다" in text


def test_locked_judge_prompt_has_no_legacy_speaker_only_instructions(monkeypatch):
    prompts = []
    monkeypatch.setattr(sg, "_call_json", lambda prompt, *_a: prompts.append(prompt) or {})
    sg._speaker_judge("변기를 펼쳐요.", PRODUCT, sg.claim_evidence(sources()))
    assert "일관되는지**만" not in prompts[0]
    assert "애매하면 통과" not in prompts[0]
    assert "[검사 문장 단위]" in prompts[0]


def test_full_and_partial_prompts_neutralize_the_same_unsupported_style(monkeypatch):
    prompts = []
    monkeypatch.setattr(sg, "STYLE_REWRITES", 0)
    monkeypatch.setattr(sg, "BEAT_REGEN_TRIES", 0)
    monkeypatch.setattr(sg, "_style_extra", lambda: "")
    monkeypatch.setattr(sg, "_call_json", lambda prompt, *_a, **_k:
                        prompts.append(prompt) or {"beats": [], "text": "변기를 접어 넣어요"})
    template = "현지에선 품절대란까지 났대요"
    style = {"id": 54, "name": "발견형", "beat_roles": ["scale"],
             "beat_descs": {"scale": "얼마나 화제인지 단정한다"},
             "templates": {"scale": [template]}}
    original = copy.deepcopy(style)
    sg.generate_one_style(sources(), style)
    result = sg.regen_one_beat(sources(), style, "scale", template=template,
        beats=[{"role": "scale", "text": template}], beat_index=0,
        topic_product=PRODUCT, topic_judge=lambda text, *_a, **_k: verdict(text=text))
    assert result and result["template"] == ""
    assert len(prompts) == 2
    assert template not in prompts[0]
    partial_instruction = prompts[1].split("[다시 쓸 칸]", 1)[1]
    assert template not in partial_instruction and "★쓸 문장틀" not in partial_instruction
    assert "얼마나 화제인지 단정한다" not in prompts[0] + partial_instruction
    assert style == original
