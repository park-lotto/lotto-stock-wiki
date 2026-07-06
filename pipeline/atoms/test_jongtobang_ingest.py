import pipeline.atoms.db as db_module
import pipeline.atoms.jongtobang_ingest as jtb


def test_signal_from_text():
    assert jtb.signal_from_text("상한가 가즈아 급등 수급 들어온다") == "bullish"
    assert jtb.signal_from_text("악재 터졌다 손절 폭락") == "bearish"
    assert jtb.signal_from_text("그냥 잡담") == "neutral"


def test_post_to_atom_is_jongtobang_tier():
    a = jtb.post_to_atom({"nid": "77", "body": "상한가 간다 수급 붙었다"},
                         "005930", "삼성전자", date="2026-07-06")
    assert a["source_type"] == "종토방"
    assert a["source_trust"] == "D"
    assert a["content_type"] == "rumor"
    assert a["signal"] == "bullish"
    assert a["asset"] == "삼성전자"
    assert a["id"] == "jtb_005930_77"


def test_ingest_posts_inserts_and_skips_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "atoms.db")
    db_module.init_db()
    posts = [
        {"nid": "1", "body": "급등 수급 매수"},
        {"nid": "2", "body": ""},          # 빈 본문 → 건너뜀
        {"nid": "3", "body": "악재 손절"},
    ]
    n = jtb.ingest_posts(posts, "005930", "삼성전자", date="2026-07-06")
    assert n == 2
    rows = db_module.query_atoms(asset="삼성전자", days=1)
    assert len(rows) == 2
    assert all(r["source_type"] == "종토방" for r in rows)


def test_crawl_and_ingest_empty_nids_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(db_module, "DB_PATH", tmp_path / "atoms.db")
    db_module.init_db()
    assert jtb.crawl_and_ingest("005930", "삼성전자", []) == 0
