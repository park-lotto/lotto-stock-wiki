"""제작소 — 핸드오프 플래그 보존 + 임시 대본 합침(2026-07-18).

★2026-07-23 Task 4(숏템메이커 리뉴얼): "우리 시스템으로 믹스" 탭 전체(SCRIPT_MODE_HTML.mix ·
switchMixSource · loadWikiForMix · mergePicks · genMix · renderDrafts · MIX_ELEMS)를 제거했다.
이 테스트가 앵커 삼던 mergePicks()와 마커(`// ── 임시 대본 끝 ──`)가 produce.html에서 사라져
슬라이스 자체가 불가능해졌다 — 스킵(브리프 지시: 같은 커밋에서 삭제/스킵)."""
import json
import pathlib
import shutil
import subprocess

import pytest

pytestmark = pytest.mark.skip(
    reason="Task4: mergePicks·믹스탭 UI 제거로 앵커 소실(2026-07-23) — AI PICK 자동담김으로 대체")

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")

_START = "function mergePicks("
_END = "// ── 임시 대본 끝 ──"


def _slice():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    return src[src.index(_START):src.index(_END)]


_DRIVER = r"""
(function(){
  const server = [{shortcode:'wiki1', name:'위키A', category:'요리', thumbnail:'', full_text:'S급 대본'}];
  const handoff = [
    {shortcode:'tmp1', name:'임시A', thumbnail:'', category:'청소', pickScript:true, script:'임시 대본', useFootage:true},
    {shortcode:'nofoot', pickScript:false, useFootage:true},          // 대본 아님 — 담긴대본에 안 감
    {shortcode:'wiki1', pickScript:true, script:'중복(무시)', useFootage:true},  // 서버와 겹침
  ];
  const merged = mergePicks(server, handoff);
  console.log(JSON.stringify({
    codes: merged.map(m=>m.shortcode),
    tmpText: (merged.find(m=>m.shortcode==='tmp1')||{}).full_text,
    dupCount: merged.filter(m=>m.shortcode==='wiki1').length,
  }));
})();
"""


def _run(tmp_path):
    js = tmp_path / "t.js"
    js.write_text(_slice() + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_merge_adds_temp_scripts(tmp_path):
    got = _run(tmp_path)
    assert "tmp1" in got["codes"]              # 임시 대본이 합쳐진다
    assert got["tmpText"] == "임시 대본"
    assert "nofoot" not in got["codes"]        # pickScript 아니면 안 들어간다


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_merge_dedups_by_shortcode(tmp_path):
    got = _run(tmp_path)
    assert got["dupCount"] == 1               # 서버와 겹치면 하나만(서버 우선)
