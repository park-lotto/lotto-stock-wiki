import json
from pathlib import Path
from tools.calcopy.engine import preset_brief as B

def _preset(d: Path, title_y=120):
    from tools.calcopy.engine.preset_save import variables
    d.mkdir(parents=True, exist_ok=True)
    frame = {"canvas": [1080, 1920], "layers": [{"kind": "text", "role": "title", "y": "$per_video"},
                                                {"kind": "text", "role": "caption", "y": title_y, "font": "Pretendard"}]}
    (d / "frame.json").write_text(json.dumps(frame), encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"sources": [{"video": "a"}, {"video": "b"}], "variables": variables(frame)}), encoding="utf-8")
    return d


def test_render_writes_marked_md(tmp_path):
    p = _preset(tmp_path / "preset" / "틀")
    r = B.render(p, tmp_path / "out", "내프리셋")
    md = Path(r["md"]).read_text(encoding="utf-8")
    assert md.splitlines()[0] == f"<!-- manifest_sha: {r['sha']} -->"
    assert "layers[text:title].y" in md and "편마다" in md
    assert Path(r["claude_md"]).exists()

def test_stale_when_preset_changes(tmp_path):
    p = _preset(tmp_path / "preset" / "틀")
    r = B.render(p, tmp_path / "out", "x")
    assert B.stale(Path(r["md"]), p) is False
    _preset(p, title_y=140)
    assert B.stale(Path(r["md"]), p) is True


def _real(d: Path):
    from tools.calcopy.engine.preset_save import variables
    d.mkdir(parents=True, exist_ok=True)
    frame = {"canvas": [1080, 1920], "made_from": "x", "layers": [
        {"kind": "bg", "rgb": [0, 0, 0]},
        {"kind": "text", "role": "title", "y": "$per_video", "text": "$per_video", "box": {"a": 1}},
        {"kind": "text", "role": "title", "y": 300, "text": "a|b\nc"}]}
    (d / "frame.json").write_text(json.dumps(frame), encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"sources": [], "variables": variables(frame)}), encoding="utf-8")
    return d, variables(frame)


def test_real_shape_names_match_variables(tmp_path):
    p, var = _real(tmp_path / "p")
    md = Path(B.render(p, tmp_path / "o", "n")["md"]).read_text(encoding="utf-8")
    rows = [l for l in md.splitlines() if l.startswith("| ")][1:]
    assert len(var) == 2
    marked = [l.split(" | ")[0][2:] for l in rows if l.endswith("편마다 소재에 맞춰 정함 |")]
    assert marked == var
    assert any(l.startswith("| layers[text:title#2].text |") for l in rows)
    assert all(l.count("\n") == 0 for l in rows) and "⏎" in md and "a\|b" in md
    assert not any("made_from" in l or ".kind" in l for l in rows)


def test_frames_shape(tmp_path):
    from tools.calcopy.engine.preset_save import variables
    d = tmp_path / "f"
    d.mkdir()
    frame = {"canvas": [1080, 1920], "frames": [{"id": "hook", "span": [0, 3], "layers": [
        {"kind": "text", "role": "title", "text": "$per_video"}, {"kind": "text", "role": "title", "y": 5}]}]}
    (d / "frame.json").write_text(json.dumps(frame), encoding="utf-8")
    var = variables(frame)
    (d / "manifest.json").write_text(json.dumps({"sources": [], "variables": var}), encoding="utf-8")
    md = Path(B.render(d, tmp_path / "o", "n")["md"]).read_text(encoding="utf-8")
    assert var == ["frames[hook].layers[text:title].text"]
    assert "| frames[hook].layers[text:title].text | \"$per_video\" | 편마다" in md
    assert "| frames[hook].span |" in md and "text:title#2" in md
