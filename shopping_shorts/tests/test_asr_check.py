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
