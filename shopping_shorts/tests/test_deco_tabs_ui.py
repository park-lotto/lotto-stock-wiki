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
    "fxAdvOn", "fxWizard", "advDetails", "advBody",
    "hcFont", "hcColor", "hcWeight",
    "tplCards", "hcCopyCards",
]

# ★일부러 뺀 자리(2026-08-24 사장님 "이건 삭제해도 되고"). 되살리려면 사장님 지시가 있어야
#   한다 — 실수로 다시 넣는 걸 막으려고 여기 남긴다.
#   highlightRuleList: 손으로 넣는 강조 단어 UI. hcPresets: 헤드카피 색 프리셋 줄.
#   둘 다 그리는 함수가 null 가드를 갖고 있어 자리가 없어도 조용히 돌아간다.
REMOVED_ON_PURPOSE = ["highlightRuleList", "hcPresets"]


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


def test_removed_ids_stay_removed():
    """사장님이 빼라고 한 자리가 슬그머니 돌아오지 않았나."""
    back = [i for i in REMOVED_ON_PURPOSE if f'id="{i}"' in HTML]
    assert not back, f"삭제하기로 한 UI가 되살아났다: {back}"


def test_removed_renderers_are_null_safe():
    """★자리를 뺐으니 그리는 함수는 반드시 조용히 돌아가야 한다.

    가드가 빠지면 renderHighlightRules/renderPresets가 던지고, 그 뒤에 이어 붙은
    호출(updateHC 등)이 통째로 죽는다 — 화면이 비는 사고가 된다.
    """
    for fn in ("renderHighlightRules", "renderPresets"):
        i = HTML.index(f"function {fn}")
        assert "if(!box) return" in HTML[i:i + 300], f"{fn}에 null 가드가 없다"
