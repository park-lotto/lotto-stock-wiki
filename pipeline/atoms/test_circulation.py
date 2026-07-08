import json
import pipeline.atoms.circulation as circ


# --- trigger_candidates: 강한 호재 원자만 후보로 ---

def _fake_query(atoms):
    def q(days=None, limit=None, active_only=True):
        return list(atoms)
    return q


def test_trigger_candidates_keeps_strong_bullish():
    atoms = [
        {"id": "a1", "content": "반도체 클러스터 확정 발표", "signal": "bullish",
         "sector": "반도체", "source_name": "DART", "source_type": "공시", "strength_score": 5},
    ]
    out = circ.trigger_candidates(min_strength=3, query_fn=_fake_query(atoms))
    assert len(out) == 1
    assert out[0]["sector"] == "반도체"
    assert out[0]["atom_id"] == "a1"


def test_trigger_candidates_drops_weak_atoms():
    atoms = [
        {"id": "w", "content": "약한 뉴스", "signal": "bullish",
         "sector": "반도체", "source_name": "N", "source_type": "news", "strength_score": 2},
    ]
    assert circ.trigger_candidates(min_strength=3, query_fn=_fake_query(atoms)) == []


def test_trigger_candidates_drops_non_bullish():
    atoms = [
        {"id": "n", "content": "정기 IR", "signal": "neutral",
         "sector": "반도체", "source_name": "N", "source_type": "news", "strength_score": 5},
    ]
    assert circ.trigger_candidates(min_strength=3, query_fn=_fake_query(atoms)) == []


def test_trigger_candidates_requires_sector():
    atoms = [
        {"id": "x", "content": "섹터없는 호재", "signal": "bullish",
         "sector": "", "source_name": "N", "source_type": "news", "strength_score": 5},
    ]
    assert circ.trigger_candidates(min_strength=3, query_fn=_fake_query(atoms)) == []


# --- mover_candidates: 히트맵 급등 - 트리거섹터 제외 ---

def _heatmap(sectors):
    return {"sectors": sectors, "updated_at": "10:00:00"}


def test_mover_candidates_filters_min_rate_and_excludes_trigger_sector():
    hm = _heatmap([
        {"name": "반도체", "avg_rate": 3.0, "stocks": [
            {"name": "반도체주", "code": "1", "change_rate": 9.0, "price": 1000}]},
        {"name": "건자재", "avg_rate": 6.0, "stocks": [
            {"name": "성신양회", "code": "004980", "change_rate": 16.0, "price": 8000},
            {"name": "미미주", "code": "2", "change_rate": 2.0, "price": 500}]},
    ])
    out = circ.mover_candidates(hm, exclude_sectors={"반도체"}, min_rate=5.0)
    names = [m["name"] for m in out]
    assert "성신양회" in names          # 다른 섹터 급등 → 후보
    assert "반도체주" not in names       # 트리거 섹터 → 제외
    assert "미미주" not in names         # min_rate 미달 → 제외


def test_mover_candidates_empty_when_all_excluded():
    hm = _heatmap([
        {"name": "반도체", "avg_rate": 5.0, "stocks": [
            {"name": "반도체주", "code": "1", "change_rate": 9.0, "price": 1000}]},
    ])
    assert circ.mover_candidates(hm, exclude_sectors={"반도체"}, min_rate=5.0) == []


# --- detect 게이트: 둘 중 하나라도 비면 LLM 호출 안 함 ---

def test_detect_no_llm_call_when_no_triggers():
    calls = []
    llm = lambda prompt: calls.append(prompt) or {"ok": True, "analysis": "[]"}
    out = circ.detect([], [{"name": "성신양회"}], llm_fn=llm)
    assert out == []
    assert calls == []  # 트리거 없으면 호출 자체를 안 함


def test_detect_no_llm_call_when_no_movers():
    calls = []
    llm = lambda prompt: calls.append(prompt) or {"ok": True, "analysis": "[]"}
    out = circ.detect([{"sector": "반도체", "content": "x"}], [], llm_fn=llm)
    assert out == []
    assert calls == []


def test_detect_returns_parsed_cards_on_match():
    triggers = [{"atom_id": "a1", "sector": "반도체", "content": "클러스터 확정",
                 "source_name": "DART", "trust": "🟢"}]
    movers = [{"name": "성신양회", "code": "004980", "sector": "건자재", "rate": 16.0}]
    resp = json.dumps({"matches": [{
        "trigger_sector": "반도체", "mover_sector": "건자재",
        "mover_stock": "성신양회", "mover_code": "004980", "pct": 16.0,
        "trigger_summary": "반도체 클러스터 확정",
        "reasoning": "건자재 2차 수혜"}]}, ensure_ascii=False)
    llm = lambda prompt: {"ok": True, "analysis": resp}
    out = circ.detect(triggers, movers, llm_fn=llm)
    assert len(out) == 1
    assert out[0]["mover_stock"] == "성신양회"
    assert out[0]["type"] == "circulation"
    assert "성신양회" in out[0]["label"]


def test_detect_empty_matches_is_ok():
    triggers = [{"atom_id": "a1", "sector": "반도체", "content": "x"}]
    movers = [{"name": "무관주", "code": "9", "sector": "화장품", "rate": 8.0}]
    llm = lambda prompt: {"ok": True, "analysis": json.dumps({"matches": []})}
    out = circ.detect(triggers, movers, llm_fn=llm)
    assert out == []  # 억지 연결 금지 — 빈 결과 정상


def test_detect_handles_llm_error():
    triggers = [{"atom_id": "a1", "sector": "반도체", "content": "x"}]
    movers = [{"name": "성신양회", "code": "1", "sector": "건자재", "rate": 16.0}]
    llm = lambda prompt: {"error": "쿼터 소진"}
    assert circ.detect(triggers, movers, llm_fn=llm) == []


def test_detect_handles_garbage_llm_response():
    triggers = [{"atom_id": "a1", "sector": "반도체", "content": "x"}]
    movers = [{"name": "성신양회", "code": "1", "sector": "건자재", "rate": 16.0}]
    llm = lambda prompt: {"ok": True, "analysis": "이것은 JSON이 아닙니다"}
    assert circ.detect(triggers, movers, llm_fn=llm) == []


# --- parse_matches: JSON 코드펜스 감싸도 파싱 ---

def test_parse_matches_strips_code_fence():
    txt = "```json\n{\"matches\": [{\"mover_stock\": \"성신양회\", \"mover_code\": \"1\", " \
          "\"trigger_sector\": \"반도체\", \"mover_sector\": \"건자재\", \"pct\": 16.0, " \
          "\"trigger_summary\": \"클러스터\", \"reasoning\": \"수혜\"}]}\n```"
    out = circ.parse_matches(txt)
    assert len(out) == 1
    assert out[0]["mover_stock"] == "성신양회"
