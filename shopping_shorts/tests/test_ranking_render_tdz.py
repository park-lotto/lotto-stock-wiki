"""랭킹 카드가 통째로 안 그려지던 회귀 — render()의 TDZ(선언 전 사용) 차단.

2026-08-18 실사고: 레퍼런스 랭킹이 인스타·쓰레드 **모든 탭**에서 빈 화면이 됐다.
데이터는 멀쩡했다(서버 api_reference가 인스타 161건을 정상 반환). 원인은 render()가
`_perChCut`을 **선언(let)보다 먼저 읽어** ReferenceError로 죽은 것:

    if(_perChCut > 0) ...     ← 1568행: 읽기
    let _perChCut = 0;        ← 1579행: 선언

`let`은 호이스팅되지만 TDZ(temporal dead zone)라 선언 전 접근은 던진다. render()가
첫 줄부터 죽으니 초기 HTML("「지금 수집」을 눌러 시작하세요")이 그대로 남아
"영상이 다 지워졌다"로 보였다.

★`node --check`로는 못 잡는다 — 문법은 완전히 유효하고 **런타임** 오류다.
  그래서 이 검사가 필요하다(코드 블록을 실제로 실행해 확인).
"""
import pathlib
import re
import shutil
import subprocess

import pytest

INDEX = pathlib.Path(__file__).resolve().parents[1] / "static" / "index.html"


def _render_body():
    """index.html에서 render() 함수 본문을 통째로 뽑는다(중괄호 균형으로 끝을 찾는다)."""
    html = INDEX.read_text(encoding="utf-8")
    i = html.find("function render(opts)")
    assert i != -1, "render(opts)를 못 찾음(구조 변경?)"
    start = html.index("{", i)
    depth = 0
    for j in range(start, len(html)):
        if html[j] == "{":
            depth += 1
        elif html[j] == "}":
            depth -= 1
            if depth == 0:
                return html[start:j + 1]
    pytest.fail("render() 끝을 못 찾음")


def test_render가_선언보다_먼저_읽는_변수가_없다():
    """let/const로 선언된 지역변수를 **선언 줄보다 위에서** 쓰면 TDZ로 죽는다."""
    body = _render_body()
    lines = body.split("\n")
    decl = {}   # 변수명 -> 처음 선언된 줄 번호
    for n, line in enumerate(lines):
        for m in re.finditer(r"\b(?:let|const)\s+(_[A-Za-z0-9_]+)", line):
            decl.setdefault(m.group(1), n)
    bad = []
    for name, dline in decl.items():
        for n, line in enumerate(lines[:dline]):
            stripped = line.strip()
            if stripped.startswith("//") or stripped.startswith("*"):
                continue          # 주석은 실행되지 않는다
            if re.search(r"\b%s\b" % re.escape(name), line):
                bad.append("%s: %d행에서 씀 → %d행에서 선언" % (name, n + 1, dline + 1))
                break
    assert not bad, (
        "render()에서 선언 전에 읽는 변수가 있다 — 화면이 통째로 빈다:\n  "
        + "\n  ".join(bad))


@pytest.mark.skipif(shutil.which("node") is None, reason="node 없음")
def test_render_블록이_실제로_실행된다():
    """정적 검사를 통과해도 진짜 도는지 본다 — 최소 스텁으로 render() 본문을 실행."""
    body = _render_body()
    harness = """
const STATE={items:[{username:'a',views:1,speed:1,density:0,age_hours:1,shortcode:'x'}],
             filters:{},q:''};
let PLATFORM='instagram', RENDER_CAP=200, PER_CHANNEL_ON=true, SPAN_DAYS=0;
const PER_CHANNEL_MAX=2, RENDER_STEP=200;
const document={getElementById:()=>null, querySelectorAll:()=>[], querySelector:()=>null,
                createElement:()=>({style:{},classList:{add(){},remove(){},toggle(){}}})};
const localStorage={getItem:()=>null,setItem(){}};
function _normUser(u){return (u||'').toLowerCase();}
function sortKey(){return 0;} function _risingCut(){return 0;}
function cardHTML(){return '';} function thumbURL(){return '';}
function renderFilterButtons(){} function stopAllPlaying(){}
function render(opts)""" + body + """
try { render(); console.log('RENDER_OK'); }
catch (e) {
  // 스텁이 못 흉내낸 것(TypeError 등)은 이 검사의 관심사가 아니다.
  // TDZ(ReferenceError: Cannot access ... before initialization)만 실패로 본다.
  if (e instanceof ReferenceError && /before initialization/.test(e.message)) {
    console.log('TDZ_FAIL: ' + e.message); process.exit(1);
  }
  console.log('RENDER_OK(스텁 한계: ' + e.constructor.name + ')');
}
"""
    import tempfile, os
    fd, path = tempfile.mkstemp(suffix=".js")
    os.close(fd)
    try:
        pathlib.Path(path).write_text(harness, encoding="utf-8")
        # ★encoding 명시 필수 — 윈도우 기본 cp949로 읽으면 한글 출력에서 죽는다.
        r = subprocess.run(["node", path], capture_output=True, text=True, timeout=60,
                           encoding="utf-8", errors="replace")
        assert "TDZ_FAIL" not in r.stdout, (
            "render()가 선언 전 변수 접근으로 죽는다 → 카드가 통째로 안 그려진다:\n"
            + r.stdout.strip())
        assert r.returncode == 0, r.stdout + r.stderr
    finally:
        os.unlink(path)
