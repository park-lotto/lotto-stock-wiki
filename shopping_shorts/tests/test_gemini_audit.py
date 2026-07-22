"""제미니 검열 신호등(audit_health) — 경계값 고정."""
from shopping_shorts.gemini_audit import audit_health, compute_audit


def test_all_green():
    r = audit_health({"success_rate": 0.9, "completeness_rate": 0.85, "hook_spam_ratio": 0.05})
    assert r["level"] == "🟢"
    assert r["reasons"] == []


def test_success_rate_boundary():
    assert audit_health({"success_rate": 0.5})["level"] == "🟢"     # 0.5는 통과
    assert audit_health({"success_rate": 0.49})["level"] == "🔴"    # 0.5 미만은 적신호


def test_completeness_boundary():
    assert audit_health({"completeness_rate": 0.7})["level"] == "🟢"
    assert audit_health({"completeness_rate": 0.69})["level"] == "🟡"


def test_spam_boundary():
    assert audit_health({"hook_spam_ratio": 0.15})["level"] == "🟢"
    assert audit_health({"hook_spam_ratio": 0.16})["level"] == "🟡"


def test_red_wins_over_yellow():
    # 성공률 적신호 + 완성도 주의 → 최종은 적신호
    r = audit_health({"success_rate": 0.1, "completeness_rate": 0.5, "hook_spam_ratio": 0.9})
    assert r["level"] == "🔴"
    assert len(r["reasons"]) == 3


def test_missing_metric_ignored():
    # 지표 없으면 그 항목은 판정 제외(None 안전)
    assert audit_health({})["level"] == "🟢"
    assert audit_health({"success_rate": None})["level"] == "🟢"


def test_compute_audit_from_sources():
    # 성공 3건 중 2건이 완성(hook+beat_chain>=3+부품>=5), 1건은 빈 구조
    good = {"hook": ["훅1"], "spine": {"beat_chain": ["a", "b", "c"]},
            "adverb": ["진짜", "완전"], "cta": ["댓글"], "ending": ["돼요", "예요"]}
    empty = {"hook": [], "spine": {}, "adverb": []}
    m = compute_audit(attempted=4, succeeded=3,
                      structures=[good, good, empty],
                      hook_total=10, hook_bait=3)
    assert m["attempted"] == 4 and m["succeeded"] == 3
    assert abs(m["success_rate"] - 0.75) < 1e-9        # 3/4
    assert abs(m["completeness_rate"] - 2 / 3) < 1e-9  # 3건 중 2건 완성
    assert abs(m["hook_spam_ratio"] - 0.3) < 1e-9      # 3/10
    assert m["health"]["level"] in ("🟢", "🟡", "🔴")


def test_compute_audit_zero_safe():
    m = compute_audit(attempted=0, succeeded=0, structures=[], hook_total=0, hook_bait=0)
    assert m["success_rate"] is None       # 시도 0이면 비율 계산 불가 → None(신호등 제외)
    assert m["completeness_rate"] is None
    assert m["hook_spam_ratio"] is None
    assert m["health"]["level"] == "🟢"
