import pipeline.atoms.cause_hunt as ch


def _q(atoms_by_asset):
    def q(asset=None, days=None, limit=None, active_only=True):
        return atoms_by_asset.get(asset, [])
    return q


def test_stage1_picks_highest_tier_atom():
    # 종토방🟠 + 공시🟢 있으면 공시 채택
    atoms = {"가온칩스": [
        {"id": "b", "content": "종토방 인수설", "source_type": "종토방",
         "source_name": "naver", "strength_score": 5},
        {"id": "a", "content": "296억 계약 공시", "source_type": "공시",
         "source_name": "DART", "strength_score": 2}]}
    r = ch.hunt_cause("가온칩스", query_fn=_q(atoms))
    assert r["found"] is True
    assert r["stage"] == "atom"
    assert r["tier"] == "🟢"
    assert r["atom_id"] == "a"


def test_stage1_telegram_tier_labeled():
    atoms = {"X": [{"id": "t", "content": "텔레 속보", "source_type": "telegram",
                    "source_name": "tg", "strength_score": 1}]}
    r = ch.hunt_cause("X", query_fn=_q(atoms))
    assert r["tier"] == "🟡"
    assert r["cause"] == "텔레 속보"


def test_stage2_llm_inference_when_no_atom():
    r = ch.hunt_cause("무원자주", query_fn=_q({}),
                      generate_fn=lambda p: "동종 반도체 강세에 동반 상승 추정(근거 약함)",
                      context_fn=lambda n: "맥락")
    assert r["found"] is True
    assert r["stage"] == "inference"
    assert r["tier"] == "🔵"
    assert r["source"] == "LLM추론"


def test_stage2_no_clue_falls_through_to_silent():
    r = ch.hunt_cause("깜깜이주", query_fn=_q({}),
                      generate_fn=lambda p: "단서 없음", context_fn=lambda n: "")
    assert r["found"] is False
    assert r["stage"] == "silent"
    assert r["flag"] == "⚠️ 전 소스 침묵 — 최우선 추적"


def test_stage3_silent_when_nothing_and_no_llm():
    r = ch.hunt_cause("완전미상", query_fn=_q({}))
    assert r["found"] is False
    assert r["stage"] == "silent"
    assert r["tier"] is None
    assert r["flag"] == "⚠️ 전 소스 침묵 — 최우선 추적"
