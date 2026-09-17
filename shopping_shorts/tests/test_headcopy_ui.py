"""고정카피 UI — 자동 채움을 하지 않는가(2026-07-19 결정)를 소스로 잠근다."""
import pathlib

HTML = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_copy_box_exists():
    assert 'id="hcCopyCards"' in HTML
    assert 'id="hcCopyMsg"' in HTML


def test_textarea_id_preserved():
    """hcText가 사라지면 updateHC/applyConfig가 통째로 죽는다."""
    assert 'id="hcText"' in HTML


def test_suggest_does_not_autofill_textarea():
    """★loadHeadcopySuggest 안에서 hcText.value에 대입하면 자동채움 버그가 되살아난다."""
    i = HTML.index("async function loadHeadcopySuggest")
    j = HTML.index("function useHeadcopy", i)
    body = HTML[i:j]
    assert "t.value=" not in body and "hcText').value =" not in body


def test_use_headcopy_calls_updateHC():
    i = HTML.index("function useHeadcopy")
    body = HTML[i:i + 600]
    assert "updateHC()" in body


def test_failure_message_is_visible():
    """못 뽑았을 때 조용히 비우지 않는다."""
    assert "문구를 못 뽑았어요" in HTML


def test_selected_copy_family_is_sent_with_script():
    """선택한 틀의 문구 계열 없이 대본만 보내면 모든 틀에 같은 제목이 나온다."""
    i = HTML.index("async function loadHeadcopySuggest")
    j = HTML.index("function useHeadcopyColor", i)
    body = HTML[i:j]
    assert "copy_family" in body
    assert "currentCopyFamily" in body


def test_paired_subline_is_applied_only_when_user_picks_copy():
    """큰 제목 카드를 누르면 그 후보와 짝인 흰 보조띠도 함께 들어간다."""
    i = HTML.index("function useHeadcopy(i)")
    body = HTML[i:i + 900]
    assert "c.subline" in body
    assert "frTitle" in body


def test_generic_customer_swap_keeps_existing_headcopy_behavior():
    """보조문구가 없는 기존 generic 후보는 흰 띠만 돌리고 큰 제목까지 바꾸지 않는다."""
    i = HTML.index("function frSwapHeadcopy")
    body = HTML[i:i + 1500]
    assert "if(picked.subline" in body
