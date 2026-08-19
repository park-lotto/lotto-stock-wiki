# -*- coding: utf-8 -*-
"""✏대본수정 편집칸이 배경 다시그리기에 살아남는지 지킨다 (2026-08-19 사장님 제보).

증상: 3단계에서 [✏ 대본수정]을 눌러 고치는 중에 글자가 사라지거나 칸이 닫혀
      "아까 분명히 고쳤는데 안 된다"가 된다.

★근본 원인(코드 실측):
  pollPhash()가 페이지를 연 뒤 최대 20회(4초 간격 ≈ 80초) 돌면서 새 phash가
  오면 render()를 부른다. render() → renderBand()가 칸 DOM을 **통째로 갈아끼우므로**
  편집 중이던 contenteditable 요소가 사라진다 = 커서·입력 중이던 글자가 날아간다.
  (autoApply/saveWork·waitNarrRegen도 같은 render()를 탄다)

계약: **편집 중인 칸이 하나라도 있으면 배경 다시그리기는 미룬다.**
      사람이 저장/취소로 편집을 닫은 뒤에 밀린 그리기를 한 번 수행한다.
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1] / "static" / "scene_lab.html"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")


def _slice(name_pat, src, what):
    m = re.search(name_pat, src, re.S)
    assert m, f"{what} 를 scene_lab.html에서 못 찾았다 — 이름이 바뀌었나?"
    return m.group(0)


def _harness(body):
    """진짜 scene_lab.html 코드를 잘라다 돌린다(복사본 금지 — 원본이 바뀌면 같이 깨져야 한다).

    ★node -e 가 아니라 임시파일로 실행한다(윈도우 명령줄 상한 32,767자 — 과거 2회 재발).
    """
    lab = LAB.read_text(encoding="utf-8")
    keep = [
        _slice(r"function openNarrEdit\(i\)\{.*?\n\}", lab, "openNarrEdit"),
        _slice(r"function closeNarrEdit\(i\)\{.*?\n\}", lab, "closeNarrEdit"),
        _slice(r"function isNarrEditing\(\)\{.*?\n\}", lab, "isNarrEditing"),
        _slice(r"function repaint\(\)\{.*?\n\}", lab, "repaint"),
        _slice(r"function flushRepaint\(\)\{.*?\n\}", lab, "flushRepaint"),
    ]
    pre = """
let RENDER_N=0, BAND_N=0, _repaintPending=false;
const NARR_EDIT={}, NARR_BUSY={};
const SL={server:true};
function render(){ RENDER_N++; }
function renderBand(){ BAND_N++; }
function nsay(t){}
function setTimeout(f,ms){ return 0; }        // 포커스 예약은 이 테스트의 관심사가 아니다
const document={querySelector(){ return null; }, getElementById(){ return null; }};
"""
    code = pre + "\n".join(keep) + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True)
    assert r.returncode == 0, (r.stderr or r.stdout)
    return r.stdout.strip()


def test_편집중이면_배경_다시그리기를_미룬다():
    """이게 깨지면 고치는 도중 글자가 날아간다(사장님 제보의 본체)."""
    out = _harness("""
      openNarrEdit(0);              // 편집칸 열기
      const before = RENDER_N;
      repaint(); repaint(); repaint();   // pollPhash 같은 배경 갱신이 세 번 들이닥침
      console.log(JSON.stringify({during: RENDER_N - before}));
    """)
    assert __import__("json").loads(out)["during"] == 0, \
        "편집 중에 render()가 돌았다 — 편집칸 DOM이 갈려 글자가 날아간다"


def test_편집을_닫으면_밀린_그리기가_한_번_수행된다():
    """미루기만 하고 안 그리면 phash·자막 갱신이 영영 화면에 안 붙는다."""
    out = _harness("""
      openNarrEdit(0);
      repaint(); repaint();          // 밀린다
      const during = RENDER_N;
      closeNarrEdit(0);              // 사람이 편집을 닫음
      console.log(JSON.stringify({during, after: RENDER_N}));
    """)
    d = __import__("json").loads(out)
    assert d["during"] == 0
    assert d["after"] == 1, "밀린 그리기가 정확히 한 번 수행돼야 한다(0=영영 안 붙음, 2+=중복)"


def test_편집중이_아니면_평소처럼_바로_그린다():
    """평상시 회귀 방지 — 안 열었으면 미룰 이유가 없다."""
    out = _harness("""
      repaint(); repaint();
      console.log(JSON.stringify({n: RENDER_N}));
    """)
    assert __import__("json").loads(out)["n"] == 2


def test_여러_칸_중_하나만_열려도_미룬다():
    out = _harness("""
      openNarrEdit(2);
      repaint();
      const during = RENDER_N;
      closeNarrEdit(2);
      console.log(JSON.stringify({during, after: RENDER_N}));
    """)
    d = __import__("json").loads(out)
    assert d["during"] == 0 and d["after"] == 1
