import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import session_title


# --- track_of: 폴더가 곧 트랙이다 ---

def test_track_folder_gives_track_name():
    assert session_title.track_of(r"C:\Users\X\로또의 주식\.tracks\보이스") == "보이스"


def test_deeper_inside_track_still_same_track():
    # .tracks/보이스/shopping_shorts 에서 열어도 트랙은 '보이스'다.
    assert session_title.track_of(r"C:\Users\X\로또의 주식\.tracks\보이스\shopping_shorts") == "보이스"


def test_forward_slashes_work_too():
    assert session_title.track_of("/c/Users/X/로또의 주식/.tracks/모션효과") == "모션효과"


def test_main_folder_is_not_a_track():
    assert session_title.track_of(r"C:\Users\X\로또의 주식") is None


def test_tracks_dir_itself_is_not_a_track():
    # .tracks 바로 아래 이름이 없으면 트랙이 아니다.
    assert session_title.track_of(r"C:\Users\X\로또의 주식\.tracks") is None


def test_empty_cwd_is_not_a_track():
    assert session_title.track_of("") is None


# --- title_for ---

def test_title_is_track_name_in_track_folder():
    assert session_title.title_for(r"C:\X\.tracks\대본믹스통합") == "대본믹스통합"


def test_title_falls_back_to_main_label():
    assert session_title.title_for(r"C:\X\로또의 주식") == session_title.MAIN_TITLE


def test_long_track_name_is_truncated():
    long = "가" * 100
    assert len(session_title.title_for(rf"C:\X\.tracks\{long}")) == session_title.MAX_LEN


# --- OSC: 설치본 allowlist가 OSC 0/1/2/9/99/777 + BEL만 허용한다 ---

def test_osc_uses_code_2_and_bel():
    assert session_title.osc_title("보이스") == "\033]2;보이스\007"


# --- build_output: 이벤트마다 필드가 다르다 ---

def test_session_start_sets_session_name_too():
    out = session_title.build_output("SessionStart", r"C:\X\.tracks\보이스")["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    assert out["sessionTitle"] == "보이스"          # 자동요약을 처음부터 막는다
    assert out["terminalSequence"] == "\033]2;보이스\007"


def test_user_prompt_submit_only_reasserts_the_tab():
    # 매 턴 세션 이름을 덮으면 사용자의 /rename까지 밟는다. 탭만 다시 박는다.
    out = session_title.build_output("UserPromptSubmit", r"C:\X\.tracks\보이스")["hookSpecificOutput"]
    assert out["hookEventName"] == "UserPromptSubmit"
    assert "sessionTitle" not in out
    assert out["terminalSequence"] == "\033]2;보이스\007"


# --- main: 훅 계약(stdin JSON → stdout JSON) ---

def test_main_reads_cwd_from_hook_payload():
    stdin = io.StringIO(json.dumps({
        "hook_event_name": "SessionStart",
        "cwd": r"C:\X\.tracks\모션효과",
    }))
    stdout = io.StringIO()
    assert session_title.main(stdin, stdout) == 0
    out = json.loads(stdout.getvalue())["hookSpecificOutput"]
    assert out["sessionTitle"] == "모션효과"


def test_main_survives_garbage_stdin():
    # 훅이 죽으면 세션이 시끄러워진다. 입력이 깨져도 유효한 JSON을 내야 한다.
    stdout = io.StringIO()
    assert session_title.main(io.StringIO("not json"), stdout) == 0
    assert "hookSpecificOutput" in json.loads(stdout.getvalue())
