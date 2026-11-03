import json
from pathlib import Path
from tools.calcopy.engine import preset_brief as B

def _preset(d: Path, title_y=120):
    d.mkdir(parents=True, exist_ok=True)
    (d / "frame.json").write_text(json.dumps({"title": {"y": title_y}, "caption": {"font": "Pretendard"}}), encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"sources": [{"video": "a"}, {"video": "b"}], "variables": ["title.y"], "fixed": {}}), encoding="utf-8")
    return d

def test_render_writes_marked_md(tmp_path):
    p = _preset(tmp_path / "preset" / "틀")
    r = B.render(p, tmp_path / "out", "내프리셋")
    md = Path(r["md"]).read_text(encoding="utf-8")
    assert md.splitlines()[0] == f"<!-- manifest_sha: {r['sha']} -->"
    assert "title.y" in md and "편마다" in md
    assert Path(r["claude_md"]).exists()

def test_stale_when_preset_changes(tmp_path):
    p = _preset(tmp_path / "preset" / "틀")
    r = B.render(p, tmp_path / "out", "x")
    assert B.stale(Path(r["md"]), p) is False
    _preset(p, title_y=140)
    assert B.stale(Path(r["md"]), p) is True
