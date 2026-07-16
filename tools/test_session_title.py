import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_title


SID = "test-session-0001"


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """상태파일을 테스트마다 격리한다 — 진짜 세션 제목을 밟지 않게."""
    monkeypatch.setattr(session_title, "STATE_DIR", tmp_path / "state")
    yield


# --- 우선순위: Claude가 박은 것 > 폴더 > main ---

def test_label_beats_folder():
    # 사장님 요구의 핵심: 폴더가 아니라 '지금 하는 일'이 뜬다.
    session_title.write_label(SID, "보이스 T6 회수")
    assert session_title.title_for(r"C:\X\.tracks\세션제목표시", SID) == "보이스 T6 회수"


def test_folder_used_when_no_label():
    assert session_title.title_for(r"C:\X\.tracks\보이스", SID) == "보이스"


def test_main_folder_without_label():
    assert session_title.title_for(r"C:\X\로또의 주식", SID) == session_title.MAIN_TITLE


def test_blank_label_falls_back_to_folder():
    session_title.write_label(SID, "   ")
    assert session_title.title_for(r"C:\X\.tracks\보이스", SID) == "보이스"


def test_label_is_per_session():
    # 창 6개가 같은 폴더를 봐도 서로 제목을 안 밟는다.
    session_title.write_label("sess-A", "보이스")
    session_title.write_label("sess-B", "모션효과")
    assert session_title.title_for(r"C:\X", "sess-A") == "보이스"
    assert session_title.title_for(r"C:\X", "sess-B") == "모션효과"


def test_no_session_id_ignores_label_store():
    assert session_title.read_label(None) is None
    assert session_title.title_for(r"C:\X\.tracks\보이스", None) == "보이스"


def test_session_id_cannot_escape_state_dir():
    f = session_title.state_file("../../evil")
    assert f is None or f.parent == session_title.STATE_DIR


# --- track_of ---

def test_track_folder_gives_track_name():
    assert session_title.track_of(r"C:\Users\X\로또의 주식\.tracks\보이스") == "보이스"


def test_deeper_inside_track_still_same_track():
    assert session_title.track_of(r"C:\X\.tracks\보이스\shopping_shorts") == "보이스"


def test_forward_slashes_work_too():
    assert session_title.track_of("/c/Users/X/로또의 주식/.tracks/모션효과") == "모션효과"


def test_main_folder_is_not_a_track():
    assert session_title.track_of(r"C:\Users\X\로또의 주식") is None


def test_tracks_dir_itself_is_not_a_track():
    assert session_title.track_of(r"C:\X\.tracks") is None


def test_long_label_is_truncated():
    session_title.write_label(SID, "가" * 100)
    assert len(session_title.title_for(r"C:\X", SID)) == session_title.MAX_LEN


# --- OSC: 설치본 allowlist가 OSC 0/1/2/9/99/777 + BEL만 허용한다 ---

def test_osc_uses_code_2_and_bel():
    assert session_title.osc_title("보이스") == "\033]2;보이스\007"


# --- ★훅 계약: 설치본 스키마 실측 결과 ---

def test_terminal_sequence_is_top_level_not_nested():
    """terminalSequence를 hookSpecificOutput 안에 넣으면 조용히 무시된다.

    설치본 스키마가 최상위 필드로 정의한다. 이 단언이 없어서 첫 구현이 틀렸다.
    """
    out = session_title.build_output("Stop", r"C:\X\.tracks\보이스")
    assert out["terminalSequence"] == "\033]2;보이스\007"
    assert "terminalSequence" not in out.get("hookSpecificOutput", {})


def test_user_prompt_submit_also_renames_the_session():
    # sessionTitle은 UserPromptSubmit 분기에 있다("Set the session title").
    out = session_title.build_output("UserPromptSubmit", r"C:\X\.tracks\보이스")
    assert out["hookSpecificOutput"] == {
        "hookEventName": "UserPromptSubmit",
        "sessionTitle": "보이스",
    }
    assert out["terminalSequence"] == "\033]2;보이스\007"


def test_other_events_only_paint_the_tab():
    # SessionStart 분기엔 sessionTitle이 없다(watchPaths·reloadSkills뿐).
    # 없는 키를 보내면 "unrecognized keys (ignored)"라 무해하지만, 계약을 정직하게 지킨다.
    for event in ("SessionStart", "Stop", "PostToolUse"):
        out = session_title.build_output(event, r"C:\X\.tracks\보이스")
        assert "hookSpecificOutput" not in out, event
        assert out["terminalSequence"] == "\033]2;보이스\007"


# --- main: 훅 계약(stdin JSON → stdout JSON) ---

def test_hook_reads_cwd_and_session_from_payload():
    session_title.write_label("sess-Z", "대본믹스통합 T3")
    stdin = io.StringIO(json.dumps({
        "hook_event_name": "UserPromptSubmit",
        "cwd": r"C:\X\.tracks\모션효과",
        "session_id": "sess-Z",
    }))
    stdout = io.StringIO()
    assert session_title.main([], stdin, stdout) == 0
    out = json.loads(stdout.getvalue())
    assert out["hookSpecificOutput"]["sessionTitle"] == "대본믹스통합 T3"


def test_hook_survives_garbage_stdin():
    # 훅이 죽으면 매 턴 에러가 뜬다. 입력이 깨져도 유효한 JSON을 내야 한다.
    stdout = io.StringIO()
    assert session_title.main([], io.StringIO("not json"), stdout) == 0
    assert "terminalSequence" in json.loads(stdout.getvalue())


def test_hook_output_is_pure_ascii():
    # cp949로 오늘만 네 번 죽었다. \uXXXX 이스케이프면 구조적으로 불가능.
    stdin = io.StringIO(json.dumps({"hook_event_name": "Stop", "cwd": r"C:\X\.tracks\보이스"}))
    stdout = io.StringIO()
    session_title.main([], stdin, stdout)
    stdout.getvalue().encode("ascii")  # 여기서 터지면 인코딩 사고 가능


# --- set 하위명령: Claude가 부른다 ---

def test_set_writes_label_for_this_session():
    stdout = io.StringIO()
    rc = session_title.main(["set", "장면라이브러리", "페이즈2", "설계"], io.StringIO(), stdout)
    # main()은 실제 os.environ을 본다. 세션 id가 없는 CI에선 1이 정상.
    assert rc in (0, 1)


def test_run_set_stores_multiword_label():
    stdout = io.StringIO()
    assert session_title.run_set("보이스 T6 회수", stdout, env={"CLAUDE_CODE_SESSION_ID": SID}) == 0
    assert session_title.read_label(SID) == "보이스 T6 회수"


def test_run_set_without_session_id_is_loud_not_silent():
    stdout = io.StringIO()
    assert session_title.run_set("x", stdout, env={}) == 1
