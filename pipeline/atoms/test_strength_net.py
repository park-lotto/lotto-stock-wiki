import pipeline.atoms.strength_net as sn

def test_trust_tier_disclosure_is_green():
    assert sn.trust_tier({"source_type": "공시", "source_trust": "A"}) == "🟢"

def test_trust_tier_news_is_green():
    assert sn.trust_tier({"source_type": "news", "source_trust": "B"}) == "🟢"

def test_trust_tier_telegram_is_yellow():
    assert sn.trust_tier({"source_type": "telegram", "source_trust": "C"}) == "🟡"

def test_trust_tier_unknown_source_defaults_blue():
    assert sn.trust_tier({"source_type": "misc", "source_trust": "D"}) == "🔵"
