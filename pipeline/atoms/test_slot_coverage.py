"""프로필 질문지의 모든 슬롯이 원자 변환 코드 어딘가에서 실제로 읽히는지 검사.
새 프로필을 추가할 때 이 파일에도 슬롯 목록을 등록해야 한다 — 등록 안 하면
이 테스트가 실패해서 '조용한 유실'을 막는다."""
import inspect


def _source_of(fn) -> str:
    return inspect.getsource(fn)


def test_daytrading_profile_slots_all_read_in_conversion_code():
    from pipeline.atoms.profiles import YOUTUBE_PROFILES, daytrading_atoms
    slots = YOUTUBE_PROFILES["데이트레이딩"]["slots"]
    src = _source_of(daytrading_atoms)
    missing = [s for s in slots if f'"{s}"' not in src and f"'{s}'" not in src]
    assert missing == [], f"질문지 슬롯인데 변환 코드에서 안 읽는 필드: {missing}"


def test_report_stock_slots_all_read_in_conversion_code():
    from pipeline.atoms.questionnaire import questionnaire_to_atoms
    slots = ["code", "rating", "rating_changed", "tp_new", "tp_prev", "tp_direction",
             "earnings_outlook", "estimate_revision", "next_catalyst", "thesis",
             "valuation_basis", "risk", "supply_comment", "quote"]
    src = _source_of(questionnaire_to_atoms)
    missing = [s for s in slots if f'"{s}"' not in src and f"'{s}'" not in src]
    assert missing == [], f"리포트 stock 질문지 슬롯인데 변환 코드에서 안 읽는 필드: {missing}"


def test_telegram_insight_slots_all_read_in_conversion_code():
    from pipeline.atoms.telegram_questionnaire import questionnaire_to_atoms_tg
    slots = ["leading_sectors", "stance", "methods", "stocks_mentioned",
             "noise_ratio", "quote"]
    src = _source_of(questionnaire_to_atoms_tg)
    missing = [s for s in slots if f'"{s}"' not in src and f"'{s}'" not in src]
    assert missing == [], f"텔레그램 insight 질문지 슬롯인데 변환 코드에서 안 읽는 필드: {missing}"
