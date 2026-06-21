"""텔레그램 타입별 질문지 프롬프트 검증."""
from pipeline.atoms.telegram_questionnaire import QUESTIONNAIRES


def test_all_five_types_present():
    """5가지 타입 전부 존재."""
    assert set(QUESTIONNAIRES) == {"sector", "market", "stock_tips", "insight", "report_relay"}


def test_common_rules_in_every_prompt():
    """모든 프롬프트에 공통 규칙 포함."""
    for ctype, p in QUESTIONNAIRES.items():
        assert "null" in p, f"'{ctype}' 프롬프트에 'null' 키워드 없음"
        assert "quote" in p, f"'{ctype}' 프롬프트에 'quote' 키워드 없음"
        assert "ts" in p, f"'{ctype}' 프롬프트에 'ts' 키워드 없음"


def test_insight_has_methods_and_stance():
    """insight 타입은 methods·stance·noise_ratio 포함."""
    p = QUESTIONNAIRES["insight"]
    assert "methods" in p, "insight 프롬프트에 'methods' 키워드 없음"
    assert "stance" in p, "insight 프롬프트에 'stance' 키워드 없음"
    assert "noise_ratio" in p, "insight 프롬프트에 'noise_ratio' 키워드 없음"


def test_prompts_inject_sector_taxonomy():
    """모든 프롬프트에 섹터 택소노미 목록 주입."""
    from pipeline.atoms.sector_classify import sectors_list
    sample = sectors_list()[0]  # "반도체"
    for ctype, p in QUESTIONNAIRES.items():
        assert "sector" in p, f"'{ctype}' 프롬프트에 'sector' 키워드 없음"
        assert sample in p, f"'{ctype}' 프롬프트에 택소노미 목록('반도체') 미주입"


def test_stock_slots_have_sector():
    """종목 멘션 있는 타입은 sector 칸 안내 포함."""
    for ctype in ("sector", "stock_tips", "insight", "report_relay"):
        p = QUESTIONNAIRES[ctype]
        assert "sector" in p, f"'{ctype}' 프롬프트에 sector 칸 안내 없음"
