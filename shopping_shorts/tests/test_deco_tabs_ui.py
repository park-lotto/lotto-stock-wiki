"""★탭 개편 회귀 — 옮기는 과정에서 id가 사라지면 그 기능이 조용히 죽는다.

updateHC/applyConfig/renderStyleCards/saveMyPreset이 전부 getElementById로 잡는다.
이 테스트는 "개편 후에도 그 id들이 살아 있는가"만 본다.
"""
import pathlib

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")

# 없어지면 그 기능이 죽는 id들(실측으로 추린 목록)
REQUIRED_IDS = [
    "hcText", "hcPreview", "hcPreviewText", "capPreviewText",
    "fullPresets", "moreStylesBtn", "myPresets", "myPresetName",
    "highlightRuleList", "fxAdvOn", "fxWizard", "advDetails", "advBody",
    "hcFont", "hcColor", "hcWeight", "hcPresets",
    "tplCards", "hcCopyCards",
]


def test_all_required_ids_present():
    missing = [i for i in REQUIRED_IDS if f'id="{i}"' not in HTML]
    assert not missing, f"탭 개편이 이 id들을 없앴다(기능이 죽는다): {missing}"


def test_tab_bar_exists():
    assert 'id="decoTabs"' in HTML


def test_four_tab_panes():
    for pane in ("decoPaneCopy", "decoPaneStyle", "decoPaneTpl", "decoPaneFx"):
        assert f'id="{pane}"' in HTML, f"{pane} 없음"


def test_preview_mirror_untouched():
    """좌측 미러는 탭 밖에 있어야 한다 — 탭을 바꿔도 계속 보여야 한다."""
    i = HTML.index('id="hcPreview"')
    j = HTML.index('id="decoTabs"')
    assert i < j, "미리보기가 탭 안으로 들어갔다(탭 전환 시 사라진다)"
