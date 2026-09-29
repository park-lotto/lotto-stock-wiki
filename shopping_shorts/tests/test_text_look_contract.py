from pathlib import Path


ROOT = Path(__file__).parents[2]
CONTRACT = (ROOT / "shopping_shorts/static/text-look-contract.js").read_text(encoding="utf-8")
EDITOR = (ROOT / "out/precision20-ui.js").read_text(encoding="utf-8")
SHOWCASE = (ROOT / "out/scene-style-ui-showcase.html").read_text(encoding="utf-8")
PRODUCE = (ROOT / "shopping_shorts/static/produce.html").read_text(encoding="utf-8")
APP = (ROOT / "shopping_shorts/app.py").read_text(encoding="utf-8")


def test_thumbnail_and_scene_editor_share_one_shadow_contract():
    for token in ("shadowX: 0.10", "shadowY: 0.13", "shadowBlur: 0.06", "shadowPasses: 3"):
        assert token in CONTRACT
    assert "TEXT_LOOK_CONTRACT" in EDITOR
    assert "TEXT_LOOK_CONTRACT" in PRODUCE
    assert "text-look-contract.js?v=1" in SHOWCASE
    assert "text-look-contract.js?v=1" in PRODUCE


def test_scene_asset_route_allows_the_shared_contract():
    assert '"shopping_shorts/static/text-look-contract.js"' in APP


def test_four_independent_text_targets_are_kept_simple():
    assert "label:'채널명',binds:['channel']" in EDITOR
    assert "label:'큰 제목',binds:['hook1','hook2']" in EDITOR
    assert "label:'작은 제목',binds:['bodyTitle']" in EDITOR
    assert "label:'자막',binds:['caption']" in EDITOR
    assert "data-look-target" in EDITOR
