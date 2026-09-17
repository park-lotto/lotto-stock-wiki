from pathlib import Path


HTML = (Path(__file__).parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def _function(name: str, next_name: str) -> str:
    start = HTML.index(f"function {name}(")
    end = HTML.index(f"function {next_name}(", start)
    return HTML[start:end]


def test_confirmed_draft_maps_platform_to_copy_family():
    assert "function s2CopyFamilyForDraft" in HTML
    body = _function("s2CopyFamilyForDraft", "s2Confirm")
    assert "instagram_story" in body
    assert "youtube_reveal" in body
    assert "demo_direct" in body
    assert "s2Platform" in body


def test_confirm_preserves_style_id_and_copy_family():
    start = HTML.index("function s2Confirm(")
    body = HTML[start:start + 2200]
    assert "STATE.script_style_id" in body
    assert "STATE.script_copy_family" in body
    assert "s2CopyFamilyForDraft(dr)" in body


def test_new_work_preserves_style_id_and_copy_family():
    start = HTML.index("function s2ConfirmToNewWork")
    end = HTML.index("function s2ScriptLines", start)
    body = HTML[start:end]
    assert "st.script_style_id" in body
    assert "st.script_copy_family" in body


def test_work_state_saves_and_all_restore_paths_restore_copy_family():
    work_state = _function("_workState", "_applyWorkTitle")
    assert "script_style_id" in work_state
    assert "script_copy_family" in work_state
    # 서버 복원, 되돌리기, sessionStorage 복원의 세 경로가 모두 같은 두 필드를 읽어야 한다.
    assert HTML.count("STATE.script_style_id") >= 5  # 저장 1 + 확정 1 + 복원 3
    assert HTML.count("STATE.script_copy_family") >= 6  # 현재 계열 판정까지 포함


def test_script_family_wins_until_user_explicitly_picks_template():
    current = _function("currentCopyFamily", "loadHeadcopySuggest")
    assert "copy_family_override" in current
    assert "STATE.script_copy_family" in current
    assert current.index("copy_family_override") < current.index("STATE.script_copy_family")

    pick = _function("frPick", "frUpdate")
    assert "copy_family_override:true" in pick.replace(" ", "")
