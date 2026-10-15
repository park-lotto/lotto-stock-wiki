"""장면 틀 규칙(관제 058) — 주인은 서버 scene_style.frame_kind. 편집기 미리보기 거울(frameKindOf)과 결과가 같아야 한다."""
import json, pathlib, re, subprocess
from shopping_shorts import scene_style

UI = (pathlib.Path(__file__).resolve().parents[2] / "out" / "precision20-ui.js").read_text(encoding="utf-8")


def test_server_rules():
    assert [scene_style.frame_kind(i, None) for i in range(3)] == ["hook", "body", "body"]
    assert [scene_style.frame_kind(i, "hook_all") for i in range(3)] == ["hook"] * 3
    assert [scene_style.frame_kind(i, "body_all") for i in range(3)] == ["body"] * 3
    assert scene_style.frame_kind(0, "모르는값") == "hook"


def test_editor_mirror_matches_server(tmp_path):
    m = re.search(r"const frameKindOf=\(beatOrder,rule\)=>[^;]+;", UI)
    assert m, "편집기 거울(frameKindOf)을 못 찾음"
    js = m.group(0) + "\nconst out={};for(const r of [undefined,'hook_body','hook_all','body_all'])out[String(r)]=[0,1,2].map(i=>frameKindOf(i,r));console.log(JSON.stringify(out));"
    (tmp_path / "t.js").write_text(js, encoding="utf-8")
    out = json.loads(subprocess.run(["node", str(tmp_path / "t.js")], capture_output=True, check=True).stdout.decode())
    for r in ("undefined", "hook_body", "hook_all", "body_all"):
        rule = None if r == "undefined" else r
        assert out[r] == [scene_style.frame_kind(i, rule) for i in range(3)], r


def test_validate_accepts_rules_and_rejects_unknown():
    base = {"mode": "story", "presetId": "s0101"}
    assert scene_style.validate_snapshot({**base, "frameRule": "hook_all"})["frameRule"] == "hook_all"
    try:
        scene_style.validate_snapshot({**base, "frameRule": "x"})
        raise AssertionError("모르는 규칙을 받아들였다")
    except ValueError:
        pass
