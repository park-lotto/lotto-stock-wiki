from pathlib import Path
from pipeline.atoms.synth_rollup import build_index

def test_index_collects_stock_oneliner(tmp_path):
    sd = tmp_path / "stock"; sd.mkdir()
    (sd / "stock_AAA.md").write_text(
        "# AAA\n## 종합 스토리\n> **2026-06-22 갱신**: 강한 모멘텀\n", encoding="utf-8")
    md = build_index(tmp_path)
    assert "AAA" in md
    assert "강한 모멘텀" in md
