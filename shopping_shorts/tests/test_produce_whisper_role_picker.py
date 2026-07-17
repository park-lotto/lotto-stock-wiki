"""영상별 "이 영상은 속삭임을 훅에만" 선택기 — produce.html UI 회귀(2026-07-17).

배경: 성우별 whisper role은 이미 작업대(voice_tune.html)에서 고를 수 있다. 이 파일은
produce.html(영상제작소 4단계)에 새로 얹은 **영상별** 오버라이드 선택지(전체/훅에만/반전에만)의
실제 소스를 파일에서 그대로 잘라내 Node로 실행한다 — voice_tune.html의 whisper UI 테스트,
produce.html 카테고리 레이스 테스트와 같은 패턴(재구현이 아니라 실물 코드 검증).

잠그는 것:
  1. WHISPER_ROLE_PRESETS가 정확히 {전체(ASMR), 훅에만, 반전에만} 3개고 기본 선택은 '반전에만'
     (엔진 기본 프로파일 whisper.roles=['반전']과 일치 — 화면 기본=엔진 기본).
  2. whisper 톤이 아닌 성우를 골랐을 때(VOICE.variant!=='whisper') 선택 UI가 숨는다
     — 다른 톤 프리셋에 오버라이드가 새어 들어가면 안 되므로 화면에서부터 막는다.
  3. whisper 톤일 때 UI가 보이고, 버튼 3개가 렌더되며 range 입력이 0개
     (설계 §6 — "속삭임 강도" 슬라이더 금지, 태그는 켜지거나 꺼질 뿐).
  4. setWhisperPreset()으로 고르면 활성 버튼이 바뀌고 _whisperRolesForBody()가 그 roles를 반환.
  5. whisper 톤이 아니면 _whisperRolesForBody()가 null — /api/mix/voice 바디에 오버라이드가
     안 실려 프리셋 원본 프로파일이 그대로 쓰인다(하위호환, app.py _voice_snapshot과 일치).

Node 없으면 스킵(다른 baseline 실패로 안 잡히게).
"""
import shutil
import subprocess
import pytest

PRODUCE_HTML = __import__("pathlib").Path(__file__).resolve().parents[1] / "static" / "produce.html"

START_ANCHOR = "const WHISPER_ROLE_PRESETS=["
END_ANCHOR = "function pickHighlight(){"

NODE = shutil.which("node")


def _extract_block() -> str:
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    start = text.find(START_ANCHOR)
    end = text.find(END_ANCHOR)
    assert start != -1, f"START_ANCHOR 못 찾음(produce.html이 바뀌었나): {START_ANCHOR!r}"
    assert end != -1 and end > start, f"END_ANCHOR 못 찾음: {END_ANCHOR!r}"
    return text[start:end]


_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{contains(){return false;},add(){},remove(){}},
           textContent:'', innerHTML:'', value:'', disabled:false, appendChild(){} };
}
const _whisperWrap = makeGenericEl();
const _whisperBtns = makeGenericEl();
const _elements = { whisperRoleControls:_whisperWrap, whisperRoleBtns:_whisperBtns };
const document = { getElementById(id){ return _elements[id] || makeGenericEl(); } };
let VOICE = { preset_id:null, voice_id:null, settings:null, speed:1.0, silence_trim:'off',
              group_id:null, variant:null };
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스 ----
"""


def _run(suffix: str, tmp_path):
    block = _extract_block()
    script = _HARNESS_PREFIX + block + suffix
    js_path = tmp_path / "whisper_role_picker.js"
    js_path.write_text(script, encoding="utf-8")
    return subprocess.run([NODE, str(js_path)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15,
                           stdin=subprocess.DEVNULL)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_whisper_role_presets_are_exactly_three_with_reversal_default(tmp_path):
    suffix = r"""
const keys = WHISPER_ROLE_PRESETS.map(w => w.key);
if (JSON.stringify(keys) !== JSON.stringify(['all','hook','reversal'])) {
  console.error('FAIL: WHISPER_ROLE_PRESETS 키 순서/구성=' + JSON.stringify(keys)); process.exit(1);
}
const all = WHISPER_ROLE_PRESETS.find(w=>w.key==='all');
if (JSON.stringify(all.roles) !== JSON.stringify(['훅','페인포인트','반전','실용','CTA'])) {
  console.error('FAIL: 전체(ASMR) roles=' + JSON.stringify(all.roles)); process.exit(1);
}
const hook = WHISPER_ROLE_PRESETS.find(w=>w.key==='hook');
if (JSON.stringify(hook.roles) !== JSON.stringify(['훅'])) {
  console.error('FAIL: 훅에만 roles=' + JSON.stringify(hook.roles)); process.exit(1);
}
if (WHISPER_PICK !== 'reversal') {
  console.error('FAIL: 기본 선택=' + WHISPER_PICK + '(기대 reversal — 엔진 기본과 불일치)'); process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_picker_hidden_for_non_whisper_variant(tmp_path):
    suffix = r"""
VOICE.variant = 'stable';
renderWhisperRoleBtns();
if (_whisperWrap.style.display !== 'none') {
  console.error('FAIL: stable 톤인데 whisperRoleControls display=' + _whisperWrap.style.display);
  process.exit(1);
}
if (_whisperRolesForBody() !== null) {
  console.error('FAIL: stable 톤인데 _whisperRolesForBody()=' + JSON.stringify(_whisperRolesForBody()) +
    '(기대 null — 오버라이드가 다른 톤에 새어들면 안 됨)');
  process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_picker_visible_for_whisper_variant_three_buttons_no_slider(tmp_path):
    suffix = r"""
VOICE.variant = 'whisper';
renderWhisperRoleBtns();
if (_whisperWrap.style.display !== 'block') {
  console.error('FAIL: whisper 톤인데 display=' + _whisperWrap.style.display); process.exit(1);
}
const btnCount = (_whisperBtns.innerHTML.match(/setWhisperPreset\(/g) || []).length;
if (btnCount !== 3) {
  console.error('FAIL: 버튼 ' + btnCount + '개(기대 3=전체/훅에만/반전에만)'); process.exit(1);
}
const rangeCount = (_whisperBtns.innerHTML.match(/type=range|type="range"/g) || []).length;
if (rangeCount !== 0) {
  console.error('FAIL: range 입력 ' + rangeCount + '개(기대 0 — "속삭임 강도" 슬라이더 금지, 설계 §6)');
  process.exit(1);
}
// 기본 선택(반전에만)이 active 클래스를 달고 있어야 화면=엔진 기본 일치
if (_whisperBtns.innerHTML.indexOf("setWhisperPreset('reversal')\" class=\"tab active\"") === -1) {
  console.error('FAIL: 기본값 반전에만 버튼이 active가 아님 — ' + _whisperBtns.innerHTML);
  process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_selecting_hook_updates_active_button_and_body_roles(tmp_path):
    suffix = r"""
VOICE.variant = 'whisper';
renderWhisperRoleBtns();
setWhisperPreset('hook');
if (WHISPER_PICK !== 'hook') {
  console.error('FAIL: WHISPER_PICK=' + WHISPER_PICK + '(기대 hook)'); process.exit(1);
}
if (_whisperBtns.innerHTML.indexOf("setWhisperPreset('hook')\" class=\"tab active\"") === -1) {
  console.error('FAIL: 훅에만 버튼이 active로 안 바뀜 — ' + _whisperBtns.innerHTML); process.exit(1);
}
const roles = _whisperRolesForBody();
if (JSON.stringify(roles) !== JSON.stringify(['훅'])) {
  console.error('FAIL: _whisperRolesForBody()=' + JSON.stringify(roles) + '(기대 ["훅"])'); process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_selecting_all_returns_full_asmr_role_list(tmp_path):
    suffix = r"""
VOICE.variant = 'whisper';
setWhisperPreset('all');
const roles = _whisperRolesForBody();
if (JSON.stringify(roles) !== JSON.stringify(['훅','페인포인트','반전','실용','CTA'])) {
  console.error('FAIL: 전체(ASMR) roles=' + JSON.stringify(roles)); process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout
