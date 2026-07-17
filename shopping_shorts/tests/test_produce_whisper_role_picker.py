"""영상별 "이 영상은 속삭임을 훅에만" 선택기 — produce.html UI 회귀(2026-07-17, 결함① 수정).

배경: 사장님이 화면에서 직접 잡은 결함 — whisperRoleBtns가 존재하고 로직도 맞는데, **위치**가
presetCards(성우 카드 14개) 전부의 **밑**, voiceControls 안 별도 div에 있었다(카드 top 293px vs
선택 UI top 1561px = 1,268px 차이, 화면 한 장(1012px)에 같이 안 잡힘). 속삭임 탭을 눌러도
선택지가 안 보이니 "적용 안 된 거 아니냐"는 오인이 발생했다.

수정: whisper role 선택 마크업을 renderPresetCards()의 카드 루프 안으로 옮겨, **선택된(active)
카드가 whisper 톤일 때만 그 카드 내부**에 렌더한다. 그래서 이 테스트는 (구) test_produce_
whisper_role_picker.py처럼 renderWhisperRoleBtns()를 별도 함수로 부르지 않고, **카드 마크업
문자열 안에서의 위치**를 잠근다 — voice_tune.html의 whisper UI 테스트가 stage 프래그먼트를
쪼개 확인하는 것과 같은 패턴(재구현이 아니라 실물 코드 검증).

잠그는 것:
  1. WHISPER_ROLE_PRESETS가 정확히 {전체(ASMR), 훅에만, 반전에만} 3개고 기본 선택은 '반전에만'.
  2. 선택된 카드가 whisper 톤일 때, role 선택 마크업(#whisperRoleControls)이 **그 카드 자신의
     마크업 프래그먼트 안**에서 발견된다(다른 카드 프래그먼트에 새어나가지 않음) — 이게 결함①의
     핵심 잠금이다. 버튼 3개, range 입력 0개(설계 §6 — "속삭임 강도" 슬라이더 금지).
  3. whisper 탭이 있지만 **선택되지 않은(비active)** 다른 카드에는 role 선택 UI가 안 뜬다
     ("속삭임 탭이 선택된 카드에만 보여야" 요구사항).
  4. 선택된 카드가 whisper가 아닌 다른 톤(stable)으로 바뀌면 그 카드 프래그먼트에서 role 선택
     UI가 사라진다.
  5. setWhisperPreset()으로 고르면 활성 버튼이 바뀌고(카드 프래그먼트 안에서), _whisperRolesForBody()가
     그 roles를 반환한다 — /api/mix/voice의 whisper_roles 배선이 안 끊겼다는 증거.
  6. whisper 톤이 아니면 _whisperRolesForBody()가 null.

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


# ---- 최소 DOM 모킹(jsdom 없이, voice_tune.html 테스트와 같은 방식) ----
_HARNESS_PREFIX = r"""
'use strict';
function esc(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function makeGenericEl(){
  return { style:{}, classList:{contains(){return false;},add(){},remove(){}},
           textContent:'', innerHTML:'', value:'', disabled:false, appendChild(){} };
}
let _presetCardsHTML = '';
const _presetCardsEl = { set innerHTML(v){ _presetCardsHTML = v; }, get innerHTML(){ return _presetCardsHTML; } };
const _elements = { presetCards:_presetCardsEl };
const document = { getElementById(id){ return _elements[id] || makeGenericEl(); } };
let VOICE = { preset_id:null, voice_id:null, settings:null, speed:1.0, silence_trim:'off',
              group_id:null, variant:null };
let VOICE_GROUPS = [];
let SEL_VARIANT = {};
const VARIANT_LABELS = {stable:'안정', natural:'자연', expressive:'표현', whisper:'속삭임'};
// 카드 하나짜리 마크업 프래그먼트를 잘라낸다 — '카드 안에 있는가'를 검증하는 핵심 헬퍼.
function getCardFrag(groupId){
  const marker = "pickPreset('" + groupId + "')";
  const idx = _presetCardsHTML.indexOf(marker);
  if (idx === -1) return null;
  const cardStart = _presetCardsHTML.lastIndexOf('<div onclick="pickPreset(', idx);
  const nextStart = _presetCardsHTML.indexOf('<div onclick="pickPreset(', idx + marker.length);
  return _presetCardsHTML.slice(cardStart, nextStart === -1 ? _presetCardsHTML.length : nextStart);
}
function mkGroup(id, name, variants){
  return { group_id:id, name:name, one_liner:'', best:false, default_variant:'stable', variants:variants };
}
function mkVariant(){
  return { preset_id:'p_'+Math.random(), voice_id:'v_'+Math.random(), voice_settings:{},
           default_speed:1.0, default_silence_trim:'off', sample_url:'' };
}
// ---- 여기부터 produce.html에서 그대로 잘라낸 실제 소스 ----
"""


def _run(suffix: str, tmp_path):
    block = _extract_block()
    script = _HARNESS_PREFIX + block + suffix
    js_path = tmp_path / "whisper_role_picker.js"
    js_path.write_text(script, encoding="utf-8")
    # stdin=DEVNULL: Windows 병렬 pytest에서 부모 stdin 핸들 복제 경합으로 간헐적 OSError
    # (WinError 50/6)가 나는 걸 이미 실측 — 이 저장소 전역 함정, 다른 node 테스트와 같은 이유.
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
if (WHISPER_PICK !== 'reversal') {
  console.error('FAIL: 기본 선택=' + WHISPER_PICK + '(기대 reversal — 엔진 기본과 불일치)'); process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_whisper_picker_renders_inside_the_selected_whisper_card(tmp_path):
    """결함①의 핵심 잠금: role 선택 UI가 '선택된 whisper 카드' 프래그먼트 자체 안에 있다.
    카드 밖(voiceControls 등 별도 섹션)에 있으면 getCardFrag가 못 찾아 FAIL."""
    suffix = r"""
VOICE_GROUPS = [
  mkGroup('g1', '미나', { stable:mkVariant(), whisper:mkVariant() }),
  mkGroup('g2', '유나', { stable:mkVariant() }),
];
SEL_VARIANT = { g1:'whisper' };
VOICE.group_id = 'g1'; VOICE.variant = 'whisper';
renderPresetCards();
const frag = getCardFrag('g1');
if (!frag) { console.error('FAIL: g1 카드 프래그먼트를 못 찾음'); process.exit(1); }
if (frag.indexOf('id="whisperRoleControls"') === -1) {
  console.error('FAIL: whisper 카드 안에 whisperRoleControls가 없음 — ' + frag); process.exit(1);
}
const btnCount = (frag.match(/setWhisperPreset\(/g) || []).length;
if (btnCount !== 3) {
  console.error('FAIL: 카드 안 버튼 ' + btnCount + '개(기대 3=전체/훅에만/반전에만)'); process.exit(1);
}
const rangeCount = (frag.match(/type=range|type="range"/g) || []).length;
if (rangeCount !== 0) {
  console.error('FAIL: whisper 선택 안에 range 입력 ' + rangeCount + '개(기대 0 — 강도 슬라이더 금지)');
  process.exit(1);
}
if (frag.indexOf("setWhisperPreset('reversal')\" class=\"tab active\"") === -1) {
  console.error('FAIL: 기본값 반전에만 버튼이 active가 아님 — ' + frag);
  process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_whisper_picker_does_not_leak_into_other_cards(tmp_path):
    """whisper 탭이 있는 카드라도 '선택(active)'되지 않았으면 role 선택 UI가 안 뜬다
    — "속삭임 탭이 선택된 카드에만 보여야" 요구사항의 직접 잠금."""
    suffix = r"""
VOICE_GROUPS = [
  mkGroup('g1', '미나', { stable:mkVariant(), whisper:mkVariant() }),
  mkGroup('g3', '수아', { stable:mkVariant(), whisper:mkVariant() }),  // whisper 탭은 있지만 비active
];
SEL_VARIANT = { g1:'whisper' };
VOICE.group_id = 'g1'; VOICE.variant = 'whisper';
renderPresetCards();
const otherFrag = getCardFrag('g3');
if (!otherFrag) { console.error('FAIL: g3 카드 프래그먼트를 못 찾음'); process.exit(1); }
if (otherFrag.indexOf('whisperRoleControls') !== -1) {
  console.error('FAIL: 비active 카드(g3)에 whisper 선택 UI가 새어들어감 — ' + otherFrag); process.exit(1);
}
// 전체 마크업에 whisperRoleControls는 정확히 1번(활성 카드에만)이어야 한다.
const totalCount = (_presetCardsHTML.match(/id="whisperRoleControls"/g) || []).length;
if (totalCount !== 1) {
  console.error('FAIL: whisperRoleControls 총 개수=' + totalCount + '(기대 1)'); process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_whisper_picker_disappears_when_variant_switches_away(tmp_path):
    suffix = r"""
VOICE_GROUPS = [ mkGroup('g1', '미나', { stable:mkVariant(), whisper:mkVariant() }) ];
SEL_VARIANT = { g1:'stable' };
VOICE.group_id = 'g1'; VOICE.variant = 'stable';
renderPresetCards();
const frag = getCardFrag('g1');
if (frag.indexOf('whisperRoleControls') !== -1) {
  console.error('FAIL: stable 톤인데 whisper 선택 UI가 남아있음 — ' + frag); process.exit(1);
}
if (_whisperRolesForBody() !== null) {
  console.error('FAIL: stable 톤인데 _whisperRolesForBody()=' + JSON.stringify(_whisperRolesForBody()));
  process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_selecting_hook_updates_active_button_in_card_and_body_roles(tmp_path):
    """선택값이 카드 안에서 바뀌고, 여전히 whisper_roles 배선(/api/mix/voice body)으로 나간다
    — 카드 위치를 옮기며 배선을 깨지 않았다는 증거."""
    suffix = r"""
VOICE_GROUPS = [ mkGroup('g1', '미나', { stable:mkVariant(), whisper:mkVariant() }) ];
SEL_VARIANT = { g1:'whisper' };
VOICE.group_id = 'g1'; VOICE.variant = 'whisper';
renderPresetCards();
setWhisperPreset('hook');
if (WHISPER_PICK !== 'hook') {
  console.error('FAIL: WHISPER_PICK=' + WHISPER_PICK + '(기대 hook)'); process.exit(1);
}
const frag = getCardFrag('g1');
if (frag.indexOf("setWhisperPreset('hook')\" class=\"tab active\"") === -1) {
  console.error('FAIL: 훅에만 버튼이 카드 안에서 active로 안 바뀜 — ' + frag); process.exit(1);
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
VOICE_GROUPS = [ mkGroup('g1', '미나', { stable:mkVariant(), whisper:mkVariant() }) ];
SEL_VARIANT = { g1:'whisper' };
VOICE.group_id = 'g1'; VOICE.variant = 'whisper';
renderPresetCards();
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
