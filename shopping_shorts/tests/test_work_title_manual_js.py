"""직접 지은 작업 이름이 자동저장에 지워지지 않는다 — node 슬라이스 그라운딩(2026-08-17).

사장님 "내 작업에 작업명 수정할수있게". 사이드바 ✏로 이름을 지어도, 제작소 화면의 STATE는
그 이름을 모르는 채라 **다음 자동저장이 이름 없는 state를 통째로 덮어써** 자동 제목으로
되돌아간다 — 겉보기엔 "이름을 바꿨는데 잠시 뒤 되돌아간다"로 보인다.

제목의 진실은 state에 있다(store._work_title이 state를 보고 목록 제목을 정한다). 그래서
_workState()가 title_manual을 실어야 하고, 복원 경로가 그것을 되살려야 한다.
★문자열 검사가 아니라 **실제로 돌려서** 못 박는다(reference_사이드바_내작업_갱신의 경고).
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _slice(pattern, what):
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    m = re.search(pattern, html, re.S)
    assert m, f"{what}를 produce.html에서 찾지 못함 — 이름이 바뀌었으면 테스트도 같이 옮길 것"
    return m.group(0)


def _run(body, state_js="{}"):
    src = _slice(r"function _workState\(\)\{.*?\n\}\n", "_workState")
    hook = _slice(r"function _applyWorkTitle\(wid, name\)\{.*?\n\}\n"
                  r"if\(typeof window[^\n]*\n", "__ssApplyWorkTitle")
    script = f"""
let HANDOFF = [], cur = 2, WORK_ID = 'W1';
let STATE = {state_js};
const window = {{}};
{src}
{hook}
{body}
"""
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30,
                       stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def test_work_state_carries_manual_title():
    """지은 이름이 있으면 저장 payload에 실린다 — 안 실으면 서버가 그 필드를 잃는다."""
    out = _run("console.log(JSON.stringify(_workState()));",
               state_js="{script:'대본', title_manual:'요거트케이크 A안'}")
    assert json.loads(out)["title_manual"] == "요거트케이크 A안"


def test_work_state_omits_key_when_no_manual_title():
    """★이름을 모를 땐 키를 **아예 안 보낸다**(빈 문자열도 안 된다).

    서버는 state를 통째로 갈아끼운다 — 이 화면이 ''를 실어 보내면 사이드바에서 방금 지은
    이름을 제작소가 지워버린다. job_id·step을 '알 때만' 보내는 것과 같은 계약이다.
    """
    st = json.loads(_run("console.log(JSON.stringify(_workState()));", state_js="{script:'대본'}"))
    assert "title_manual" not in st
    st2 = json.loads(_run("console.log(JSON.stringify(_workState()));",
                          state_js="{script:'대본', title_manual:''}"))
    assert "title_manual" not in st2


def test_hook_plants_name_into_state():
    """사이드바가 이름을 바꾸면 이 화면의 STATE에도 심긴다 → 이후 저장에 실려 나간다."""
    out = _run("""
      window.__ssApplyWorkTitle('W1', '내 이름');
      console.log(JSON.stringify(_workState()));
    """, state_js="{script:'대본'}")
    assert json.loads(out)["title_manual"] == "내 이름"


def test_hook_ignores_other_work():
    """남의 행을 고쳤을 뿐인데 지금 열린 작업 이름이 바뀌면 안 된다."""
    out = _run("""
      window.__ssApplyWorkTitle('OTHER', '남의 이름');
      console.log(JSON.stringify(_workState()));
    """, state_js="{script:'대본'}")
    assert "title_manual" not in json.loads(out)


def test_hook_empty_name_clears_state():
    """빈 이름 = 자동 제목으로 되돌리기 — STATE에서도 지워야 다음 저장이 되살리지 않는다."""
    out = _run("""
      window.__ssApplyWorkTitle('W1', '');
      console.log(JSON.stringify(_workState()));
    """, state_js="{script:'대본', title_manual:'옛 이름'}")
    assert "title_manual" not in json.loads(out)


def test_hook_survives_harness_without_window():
    """★window 없는 환경에서도 이 구간이 죽지 않는다.

    실측 사고(2026-08-17): `window.__ssApplyWorkTitle = ...`을 맨몸으로 썼더니, 이 구간
    (`let WORK_ID` 이후)을 통째로 잘라 node로 도는 다른 하네스 **5건이 ReferenceError로
    전부 죽었다**. 그 하네스들엔 window가 없다. typeof 가드를 지우면 여기서 잡힌다.
    """
    src = _slice(r"function _workState\(\)\{.*?\n\}\n", "_workState")
    hook = _slice(r"function _applyWorkTitle\(wid, name\)\{.*?\n\}\n"
                  r"if\(typeof window[^\n]*\n", "__ssApplyWorkTitle")
    script = ("let HANDOFF = [], cur = 2, WORK_ID = 'W1';\n"
              "let STATE = {script:'대본'};\n"      # ← window를 일부러 정의하지 않는다
              + src + hook + "console.log('alive');")
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=30,
                       stdin=subprocess.DEVNULL, encoding="utf-8", errors="replace")
    assert r.returncode == 0, f"window 없는 하네스에서 죽는다: {r.stderr}"
    assert r.stdout.strip() == "alive"


def test_restore_paths_hydrate_manual_title():
    """복원 경로(서버·sessionStorage·되돌리기)가 전부 title_manual을 되살린다.

    하나라도 빠지면 그 경로로 들어온 순간 이름이 사라진다 — 복원 직후에도 저장이 돌기 때문이다.
    ★실제 소스를 세어 확인한다(수를 손으로 적으면 경로가 늘 때 조용히 어긋난다).
    """
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    hydrate = html.count("STATE.title_manual = w.title_manual")
    delta = html.count("STATE.hook_inpoint_delta = (typeof w.hook_inpoint_delta")
    assert hydrate >= 3, f"복원 경로 {delta}개 중 {hydrate}개만 이름을 되살린다"
