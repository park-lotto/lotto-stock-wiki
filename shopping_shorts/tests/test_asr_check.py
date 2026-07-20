from shopping_shorts import asr_check


def test_diff_flags_mismatched_words():
    """원문 vs 재전사 → 다른 토큰을 mismatch로 표시(정규화 후 비교)."""
    d = asr_check.diff_words("이건 정말 좋아요", "이건 저말 좋아요")
    assert d["ok"] is False
    assert any(w["kind"] == "sub" and w["ref"] == "정말" for w in d["words"])

def test_diff_ignores_tags_and_punct():
    """감정태그·문장부호는 무시하고 발음 토큰만 비교."""
    d = asr_check.diff_words("[warm] 이건 좋아요.", "이건 좋아요")
    assert d["ok"] is True

def test_transcribe_without_key_returns_none(monkeypatch):
    monkeypatch.setattr(asr_check.config, "GROQ_API_KEY", "")
    assert asr_check.transcribe("/x.mp3") is None

def test_asr_score_higher_when_more_mismatch():
    good = asr_check.diff_words("좋아요", "좋아요")
    bad = asr_check.diff_words("좋아요 예뻐요", "조아요 이뻐요")
    assert asr_check.mismatch_score(bad) > asr_check.mismatch_score(good)


def test_diff_normalizes_numbers_units_both_sides():
    """숫자·단위·기호 표기차는 오독이 아니다 — Whisper가 '삼 점 오 킬로그램'을
    '3.5kg'로 되표기해도(또는 그 반대여도) 양쪽을 읽기말로 맞춰 오탐을 막는다.
    설계 의도(normalize_reading 재사용)가 실제로 배선됐는지 고정한다."""
    # 성우는 정확히 읽었는데 표기만 다른 케이스 → 오독 아님
    assert asr_check.diff_words("3.5kg 감량", "삼 점 오 킬로그램 감량")["ok"] is True
    assert asr_check.diff_words("50% 할인이에요", "오십 퍼센트 할인이에요")["ok"] is True
    assert asr_check.diff_words("1+1 행사", "일 플러스 일 행사")["ok"] is True
    # 천단위 쉼표는 숫자의 일부(일반 문장부호 쉼표와 구분) → 숫자로 정규화돼 수렴
    assert asr_check.diff_words("무려 2,847", "무려 이천팔백사십칠")["ok"] is True


def test_diff_still_catches_real_number_misread():
    """정규화가 진짜 숫자 오독까지 삼키면 안 된다 — 3kg를 5kg로 읽으면 잡아야 한다."""
    d = asr_check.diff_words("3kg 감량", "5kg 감량")
    assert d["ok"] is False
