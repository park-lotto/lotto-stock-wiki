"""실제 앱의 조립·캐시 경로가 공용 사실 근거 검사를 우회하지 않는가."""
import json

import pytest

from shopping_shorts import app, product_facts, script_generate, spine_fill, wow_facts


def test_only_collected_product_facts_get_closed_evidence_boundary():
    collected = product_facts.prompt_block({"specs": ["접어서 보관"]})
    generated = product_facts.prompt_block({"_source": "llm", "specs": ["냄새 완벽 차단"]})
    assert product_facts.CONFIRMED_FACTS_MARK in collected
    assert collected.endswith(product_facts.CONFIRMED_FACTS_END)
    assert product_facts.CONFIRMED_FACTS_MARK not in generated
    assert product_facts.CONFIRMED_FACTS_END not in generated


def test_cached_wow_without_provenance_is_refetched(monkeypatch):
    keys, queried = [], []

    class Store:
        def get_setting(self, key, default=""):
            keys.append(key)
            return json.dumps([{"hook": "현지 품절", "why": "AI가 붙인 설명"}])

        def set_setting(self, *_a):
            raise AssertionError("근거 없는 결과를 캐시하면 안 된다")

    monkeypatch.setattr(wow_facts, "find", lambda subject: queried.append(subject) or [])
    assert app._wow_block_for([{"topic_product": "휴대용 변기"}], Store()) == ""
    assert queried == ["휴대용 변기"]
    assert keys[0].startswith(f"wow_facts_v{wow_facts.CACHE_VERSION}_")


@pytest.mark.parametrize("supported", [True, False])
def test_assembled_output_uses_and_records_real_claim_gate(monkeypatch, supported):
    for name in ("_is_sul_context", "_is_invention_context", "_is_conceal_context"):
        monkeypatch.setattr(app, name, lambda *_a: False)
    monkeypatch.setattr(app, "_is_insta_context", lambda *_a: True)
    monkeypatch.setattr(app, "_insta_slots", lambda *_a: ({"제품": "변기"}, ""))
    sentence = "변기를 펼쳐 비닐을 씌워요" if supported else "변기가 현지에서 품절됐어요"
    monkeypatch.setattr(spine_fill, "build_draft", lambda *_a, **_k: {
        "script": sentence, "beats": [{"role": "hook", "text": sentence}],
        "checks": [], "made_by": "조립", "style_id": 54})
    captured = []

    def judge(text, product="", evidence=None):
        captured.append(evidence)
        return {"ok": True, "topic_ok": True, "topic_why": "", "foreign_products": [],
                "claims_ok": supported, "claims_why": "" if supported else "품절 근거 없음",
                "claim_checks": [{"unit_index": 0, "claim": text, "kind": "objective",
                                  "supported": supported,
                                  "supports": [{"evidence_id": "source:source_0:transcript",
                                                "quote": "변기를 펼쳐 비닐을 씌운다"}] if supported else []}],
                "unsupported_claims": [] if supported else [{
                    "beat_index": 0, "claim": "현지 품절", "reason": "근거 없음", "evidence_ids": []}]}

    monkeypatch.setattr(script_generate, "_speaker_judge", judge)
    style = {"id": 54, "beat_roles": ["hook"], "templates": {"hook": ["{제품}"]}}
    sources = [{"product": "휴대용 변기", "topic_product": "휴대용 변기",
                "full_text": "변기를 펼쳐 비닐을 씌운다", "segments": []}]
    out, left, why = app._assembled_drafts(
        [style], sources, None, topic_product="휴대용 변기",
        facts_block=product_facts.prompt_block({"specs": ["접어서 보관"]}))
    assert captured and "접어서 보관" in json.dumps(captured, ensure_ascii=False)
    if supported:
        assert len(out) == 1 and not left
        assert any(c["name"] == "사실 근거" and c["ok"] for c in out[0]["checks"])
    else:
        assert not out and left == [style]
        assert any("사실 근거" in message for message in why)
