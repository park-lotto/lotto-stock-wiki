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
