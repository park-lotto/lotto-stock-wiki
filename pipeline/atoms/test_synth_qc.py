from pipeline.atoms.synth_qc import dedupe, route

def test_dedupe_merges_same_content_keeps_sources():
    atoms = [
        {"content": "SK하이닉스 12단 HBM4E 샘플 출하", "raw_file": "raw/telegram/a.md"},
        {"content": "SK하이닉스 12단 HBM4E 샘플 출하", "raw_file": "raw/telegram/b.md"},
    ]
    out = dedupe(atoms)
    assert len(out) == 1
    assert set(out[0]["sources"]) == {"raw/telegram/a.md", "raw/telegram/b.md"}

def test_route_splits_stock_vs_sector():
    atoms = [
        {"asset": "SK하이닉스", "asset_level": "stock", "content": "x"},
        {"asset": "반도체", "asset_level": "sector", "content": "y"},
        {"asset": "", "asset_level": "market", "content": "z"},
    ]
    r = route(atoms)
    assert "SK하이닉스" in r["stock"]
    assert len(r["sector"]) == 2  # 반도체(generic) + market
