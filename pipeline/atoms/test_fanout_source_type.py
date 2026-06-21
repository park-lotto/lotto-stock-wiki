# pipeline/atoms/test_fanout_source_type.py
from pipeline.atoms.telegram_questionnaire import questionnaire_to_atoms_tg


def test_source_type_defaults_telegram():
    q = {"stocks": [{"name": "삼성전자", "signal": "bull", "reason": "x",
                     "ts": "10:00", "quote": "q", "sector": "반도체"}]}
    meta = {"date": "2026-06-19", "channel": "잠실개미고급수집", "type": "stock_tips", "trust": "C"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    assert atoms and all(a["source_type"] == "telegram" for a in atoms)


def test_source_type_blog_override():
    q = {"stocks": [{"name": "삼성전자", "signal": "bull", "reason": "x",
                     "ts": "10:00", "quote": "q", "sector": "반도체"}]}
    meta = {"date": "2026-06-19", "channel": "pokara61", "type": "stock_tips",
            "trust": "B", "source_type": "blog"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    assert atoms and all(a["source_type"] == "blog" for a in atoms)
