"""verify_questionnaire.py 단위 테스트.

㉠ 인용 대조는 PDF 의존 → 통합 테스트 제외 (PDF 없이도 check_quotes 로직 검증)
㉡ wisereport 대조 → 실제 raw/wisereport/*.json 파일 활용
㉢ 구조 룰 → 픽스처로 결정론적 검증
"""
import pytest

from pipeline.atoms.verify_questionnaire import (
    check_quotes,
    check_wisereport,
    check_structure,
    run_verification,
    adjust_strength,
)

# ────────────────────────────────
# 픽스처
# ────────────────────────────────

STOCK_Q_CLEAN = {
    "target_kind": "stock",
    "broker": "한화투자",
    "analyst": "김성래",
    "report_date": "2026-06-19",
    "stocks": [
        {
            "name": "현대차",
            "code": "005380",
            "rating": "BUY",
            "rating_changed": None,
            "tp_new": "280,000",
            "tp_prev": "260,000",
            "tp_direction": "up",
            "earnings_outlook": "2Q26 영업이익 2.5조 예상, 전년비 +10%",
            "thesis": ["전기차 수요 회복", "환율 수혜"],
            "quote": "목표주가를 280,000원으로 상향 조정하며 BUY를 유지한다",
        }
    ],
}

STOCK_Q_DIRTY = {
    "target_kind": "stock",
    "broker": "테스트증권",
    "analyst": "홍길동",
    "report_date": "2026-06-19",
    "stocks": [
        {
            "name": "테스트종목",
            "rating": None,
            "tp_new": "100,000",
            "tp_prev": "120,000",
            "tp_direction": "up",   # ← 모순: up인데 실제로는 하락
            "earnings_outlook": None,
            "thesis": None,
            "quote": None,
        }
    ],
}

SECTOR_Q = {
    "target_kind": "sector",
    "sector_name": "MLCC",
    "sector_view": "비중확대",
    "thesis": ["재고 정상화", "AI 수요 증가"],
    "top_picks": [{"name": "삼성전기", "reason": "점유율 확대", "tp": "200,000"}],
    "quote": "MLCC 수요가 AI 서버 확산과 함께 회복세에 있다",
}

MARKET_Q = {
    "target_kind": "market",
    "market_direction": "단기 조정 후 반등 예상",
    "recommended_sectors": [
        {"sector": "반도체", "stance": "비중확대", "reason": "HBM 수요 증가"}
    ],
}


# ────────────────────────────────
# ㉠ 인용 대조 (PDF 없이)
# ────────────────────────────────

class TestCheckQuotes:
    def test_no_pdf_text_returns_flag(self):
        flags = check_quotes(STOCK_Q_CLEAN, "")
        assert any(f["code"] == "Q_NO_PDF_TEXT" for f in flags)

    def test_number_present_in_text(self):
        # 280000이 원문에 있으면 플래그 없어야 함
        fake_text = "목표주가를 280,000원으로 상향 조정하며 BUY를 유지한다. 직전 260,000원에서 올림."
        flags = check_quotes(STOCK_Q_CLEAN, fake_text)
        num_flags = [f for f in flags if f["code"] == "Q_NUM_NOT_FOUND"]
        assert len(num_flags) == 0

    def test_number_missing_triggers_flag(self):
        # 원문에 수치가 없으면 플래그
        flags = check_quotes(STOCK_Q_CLEAN, "아무 내용이나 여기 있다")
        assert any(f["code"] == "Q_NUM_NOT_FOUND" for f in flags)

    def test_sector_q_checks_quote(self):
        # sector quote 앞 20자가 원문에 없으면 플래그
        flags = check_quotes(SECTOR_Q, "전혀 다른 텍스트")
        assert any(f["code"] == "Q_QUOTE_NOT_FOUND" for f in flags)


# ────────────────────────────────
# ㉡ wisereport 대조
# ────────────────────────────────

class TestCheckWisereport:
    def test_non_stock_skips(self):
        flags = check_wisereport(SECTOR_Q, {"date": "2026-06-19"})
        assert flags == []

    def test_no_answer_key_returns_info_flag(self):
        flags = check_wisereport(STOCK_Q_CLEAN, {"date": "1999-01-01", "broker": "X"})
        assert any(f["code"] == "W_NO_ANSWER_KEY" for f in flags)

    def test_tp_mismatch_detected(self):
        # wisereport에 실제 존재하는 종목으로 의도적 tp 불일치 주입
        q = {
            "target_kind": "stock",
            "stocks": [
                {
                    "name": "삼성화재",
                    "rating": "BUY",
                    "tp_new": "600,000",  # wisereport는 800,000 (2026-06-21)
                }
            ],
        }
        meta = {"date": "2026-06-21", "broker": "상상인증권"}
        flags = check_wisereport(q, meta)
        tp_flags = [f for f in flags if f["code"] == "W_TP_MISMATCH"]
        assert len(tp_flags) == 1
        assert "삼성화재" in tp_flags[0]["msg"]

    def test_correct_tp_no_flag(self):
        q = {
            "target_kind": "stock",
            "stocks": [{"name": "삼성화재", "rating": "BUY", "tp_new": "800,000"}],
        }
        meta = {"date": "2026-06-21", "broker": "상상인증권"}
        flags = check_wisereport(q, meta)
        assert not any(f["code"] == "W_TP_MISMATCH" for f in flags)


# ────────────────────────────────
# ㉢ 구조 룰
# ────────────────────────────────

class TestCheckStructure:
    def test_clean_stock_no_flags(self):
        flags = check_structure(STOCK_Q_CLEAN)
        # S_MISSING_QUOTE는 quote 있으므로 없어야 함
        assert not any(f["code"].startswith("S_TP_DIRECTION") for f in flags)

    def test_tp_direction_up_but_lower_flagged(self):
        flags = check_structure(STOCK_Q_DIRTY)
        assert any(f["code"] == "S_TP_DIRECTION_UP_BUT_LOWER" for f in flags)

    def test_no_quote_flagged(self):
        flags = check_structure(STOCK_Q_DIRTY)
        assert any(f["code"] == "S_MISSING_QUOTE" for f in flags)

    def test_high_null_ratio_flagged(self):
        flags = check_structure(STOCK_Q_DIRTY)
        assert any(f["code"] == "S_HIGH_NULL_RATIO" for f in flags)

    def test_no_kind_flagged(self):
        flags = check_structure({})
        assert any(f["code"] == "S_NO_KIND" for f in flags)

    def test_sector_ok(self):
        flags = check_structure(SECTOR_Q)
        assert not any(f["code"].startswith("S_") for f in flags)


# ────────────────────────────────
# 통합 + trust_score
# ────────────────────────────────

class TestRunVerification:
    def test_clean_q_high_trust(self):
        # PDF 없이 실행 → Q_SKIPPED는 감점 없음
        result = run_verification(STOCK_Q_CLEAN, {"date": "2026-06-21", "broker": "한화투자"})
        assert result["trust_score"] >= 0.6  # 구조 룰 통과 기대
        assert "flags" in result

    def test_dirty_q_lower_trust(self):
        result = run_verification(STOCK_Q_DIRTY, {"date": "1999-01-01", "broker": "X"})
        assert result["trust_score"] < 1.0


class TestAdjustStrength:
    def test_high_trust_unchanged(self):
        assert adjust_strength(4, 0.9) == 4

    def test_mid_trust_minus_one(self):
        assert adjust_strength(4, 0.6) == 3

    def test_low_trust_halved(self):
        assert adjust_strength(4, 0.3) == 2

    def test_minimum_one(self):
        assert adjust_strength(1, 0.1) == 1
