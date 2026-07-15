"""Task 9 — ① 카테고리 선택기 레이스 회귀 테스트(2026-07-15).

라이브 재현(브리프): 페이지 로드 후 첫 확정에서 refreshFinalPeek()가 ensureCategoryOptions()를
await 없이 부르고, 그 함수가 fetch 시작 전에 '로드됨' 플래그를 세워버려 곧이어 호출되는
setFinalCategoryValue(cat)가 아직 옵션이 채워지지 않은 <select>에 값을 대입 → 조용히 ''로
떨어진다(옵션은 나중에 6개 채워져도 값은 영구 빈칸).

이 테스트는 produce.html의 **실제 소스**(카테고리 선택기 블록, ensureCategoryOptions~
refreshFinalPeek)를 파일에서 그대로 잘라내 Node로 실행한다 — 재구현이 아니라 실물 코드를
검증한다. Node가 없으면 스킵(다른 baseline 실패로 집계되지 않게).
"""
import shutil
import subprocess
import sys
import pytest

PRODUCE_HTML = __import__("pathlib").Path(__file__).resolve().parents[1] / "static" / "produce.html"

# 앵커는 이번 수정으로 안 바뀌는 텍스트(주석·다음 함수 시그니처)로 고정 — 수정 전후 모두 매치돼야 한다.
START_ANCHOR = "// 카테고리 선택기(#finalCategory)"
END_ANCHOR = "async function saveScriptToWiki(btn){"

NODE = shutil.which("node")


def _extract_category_block() -> str:
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    start = text.find(START_ANCHOR)
    end = text.find(END_ANCHOR)
    assert start != -1, f"START_ANCHOR 못 찾음(produce.html이 바뀌었나): {START_ANCHOR!r}"
    assert end != -1 and end > start, f"END_ANCHOR 못 찾음: {END_ANCHOR!r}"
    return text[start:end]


_HARNESS_PREFIX = r"""
'use strict';
// ---- 최소 DOM/브라우저 모킹(jsdom 없이) ----
function makeOptionEl(){ return { value:'', textContent:'' }; }
function makeSelectEl(){
  const opts = [];
  let _value = '';
  return {
    _isSelect: true,
    get options(){ return opts; },
    set innerHTML(v){ if (v === '') opts.length = 0; },
    get innerHTML(){ return ''; },
    appendChild(opt){ opts.push(opt); },
    style: {},
    classList: { contains(){ return false; }, add(){}, remove(){} },
    set value(v){ _value = opts.some(o => o.value === v) ? v : ''; },
    get value(){ return _value; },
  };
}
function makeGenericEl(){
  return { style: {}, classList: { contains(){ return false; }, add(){}, remove(){} },
           textContent: '', innerHTML: '', disabled: false, appendChild(){} };
}
const _finalCategorySel = makeSelectEl();
const _elements = { finalCategory: _finalCategorySel, finalScriptPeek: makeGenericEl(),
                     saveWikiBtn: makeGenericEl(), pmModal: makeGenericEl() };
const document = {
  getElementById(id){ return _elements[id] || null; },
  createElement(tag){ if (tag === 'option') return makeOptionEl(); return makeGenericEl(); },
};
let _fetchCalls = [];
function fetch(url){
  _fetchCalls.push(url);
  if (String(url).indexOf('/api/wiki/categories') !== -1) {
    return new Promise(resolve => setTimeout(() => resolve({
      json: async () => ({ ok: true, categories: ['가전', '레시피', '뷰티', '생활용품', '인테리어', '기타'] }),
    }), 20));
  }
  if (String(url).indexOf('/api/produce/category') !== -1) {
    return Promise.resolve({ json: async () => ({ ok: true }) });
  }
  return Promise.reject(new Error('unmocked fetch: ' + url));
}
const STATE = { script: '테스트 대본 있음', script_src_idx: null };
let HANDOFF = [];
function esc(s){ return s; }
function lenText(){ return ''; }
function saveWork(){}
function pmLoadElementOptions(){}
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스 ----
"""

_HARNESS_SUFFIX = r"""
// ---- 회귀 시나리오: 옵션 미로드 상태에서 refreshFinalPeek() → setFinalCategoryValue() 연속 호출 ----
(async () => {
  refreshFinalPeek();                 // await 없이(실제 호출부와 동일) — ensureCategoryOptions() fire-and-forget
  setFinalCategoryValue('레시피');    // await 없이(실제 호출부 pmUseRaw 등과 동일)
  await new Promise(r => setTimeout(r, 500));  // 두 fetch 모두 끝날 시간을 넉넉히 준다(시스템 부하 대비)
  const sel = document.getElementById('finalCategory');
  if (sel.options.length === 0) {
    console.error('FAIL: 옵션이 전혀 채워지지 않음(options=' + sel.options.length + ')');
    process.exit(1);
  }
  if (sel.value !== '레시피') {
    console.error('FAIL: value=' + JSON.stringify(sel.value) + ' (기대: "레시피") — 옵션은 찼는데 값이 비어있음(레이스)');
    process.exit(1);
  }
  console.log('PASS');
  process.exit(0);
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_category_select_survives_first_confirm_race(tmp_path):
    block = _extract_category_block()
    script = _HARNESS_PREFIX + block + _HARNESS_SUFFIX
    js_path = tmp_path / "category_race.js"
    js_path.write_text(script, encoding="utf-8")
    # stdin=DEVNULL: pytest 조합에서 Windows subprocess.run이 부모의 (가끔 무효화된) stdin
    # 핸들을 자식용으로 복제하려다 간헐적으로 'OSError: [WinError 6] 핸들이 잘못되었습니다'를
    # 내는 걸 실측(다른 테스트 파일과 같이 돌 때만 재현, ~40% 빈도) — JS/로직 문제가 아니라
    # Windows 핸들 상속 경합이었다. stdin을 명시적으로 끊어 그 경로 자체를 안 타게 한다.
    result = subprocess.run([NODE, str(js_path)], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=15,
                             stdin=subprocess.DEVNULL)
    assert result.returncode == 0, (
        f"카테고리 선택기 레이스 재현(수정 전이면 실패가 정상 — 그게 버그의 증거):\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "PASS" in result.stdout
