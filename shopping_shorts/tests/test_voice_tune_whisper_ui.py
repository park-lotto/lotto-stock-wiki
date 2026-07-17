"""Task 5 후속(리뷰 지적 2) — 속삭임 노브 회귀 테스트(2026-07-17).

리뷰 실측: `STAGES`에서 whisper를 지워도, `p.whisper`에 intensity를 넣어도, 수정 1(loadPreset
병합 미러링)을 되돌려도 **어떤 테스트도 안 죽었다**. 이 파일은 voice_tune.html의 **실제 소스**
(STAGES 선언 ~ loadPreset 끝)를 파일에서 그대로 잘라내 Node로 실행해 그 구멍을 잠근다 —
`shopping_shorts/tests/test_produce_category_race.py`(produce.html 실소스 추출 방식)와 같은 패턴.

잠그는 것:
  1. STAGES에 whisper가 있고 emotion_arc·intonation 사이다(태그 순서 [감정][whispers]의 근거).
  2. defaultProfile().whisper에 intensity가 없다 → renderStages 결과 whisper 스테이지에
     range 입력이 0개(설계 §6 — "속삭임 강도" 슬라이더 금지).
  3. role 체크박스를 전부 해제하면 profile.whisper.roles가 빈 배열이 된다.
  4. 수정 1의 회귀 방지: whisper 키 없는 프로파일을 loadPreset()으로 로드하면
     profile.whisper.roles가 ["반전"]으로 채워지고(서버 merge_profile 미러링),
     렌더된 role 체크박스도 "반전" 하나만 checked다(화면=엔진 일치).

Node 없으면 스킵(다른 baseline 실패로 안 잡히게).
"""
import shutil
import subprocess
import sys
import pytest

VOICE_TUNE_HTML = __import__("pathlib").Path(__file__).resolve().parents[1] / "static" / "voice_tune.html"

# 앵커는 이 두 수정과 무관하게 안정적인 텍스트(선언·다음 함수 시그니처)로 고정.
START_ANCHOR = "const STAGES=["
END_ANCHOR = "async function init(){"

NODE = shutil.which("node")


def _extract_block() -> str:
    text = VOICE_TUNE_HTML.read_text(encoding="utf-8")
    start = text.find(START_ANCHOR)
    end = text.find(END_ANCHOR)
    assert start != -1, f"START_ANCHOR 못 찾음(voice_tune.html이 바뀌었나): {START_ANCHOR!r}"
    assert end != -1 and end > start, f"END_ANCHOR 못 찾음: {END_ANCHOR!r}"
    return text[start:end]


# ---- 최소 DOM/fetch 모킹(jsdom 없이, produce.html 테스트와 같은 방식) ----
_HARNESS_PREFIX = r"""
'use strict';
function makeGenericEl(){
  return { style:{}, classList:{contains(){return false;},add(){},remove(){}},
           textContent:'', innerHTML:'', value:'', disabled:false, appendChild(){} };
}
let _stagesHTML = '';
const _stagesEl = { set innerHTML(v){ _stagesHTML = v; }, get innerHTML(){ return _stagesHTML; } };
const _elements = { stages:_stagesEl, msg:makeGenericEl(), cards:makeGenericEl() };
const document = { getElementById(id){ return _elements[id] || makeGenericEl(); } };
const seed = { value:'42' };
const nbest = { value:'3' };
const preset = { value:'p1' };
// loadPreset()의 GET('/api/voice-tune/profile/...', opts 없음)만 이 값을 돌려준다.
// previewAll()·synthOne()류(POST, opts 있음)는 corpus가 비어있어 애초에 안 불린다.
let MOCK_PROFILE_RESPONSE = { profile: {} };
function fetch(url, opts){
  if (!opts) return Promise.resolve({ json: async () => MOCK_PROFILE_RESPONSE });
  return Promise.resolve({ json: async () => ({ ok:true, text:'' }) });
}
function getWhisperFrag(){
  const frags = _stagesHTML.split('<div class="stage">').slice(1);
  return frags.find(f => f.indexOf('setWhisperRole(') !== -1);
}
// ---- 여기부터 voice_tune.html에서 그대로 잘라낸 실제 소스 ----
"""


def _run(node_path, suffix: str, tmp_path):
    block = _extract_block()
    script = _HARNESS_PREFIX + block + suffix
    js_path = tmp_path / "voice_tune_whisper.js"
    js_path.write_text(script, encoding="utf-8")
    # stdin=DEVNULL: Windows에서 병렬 pytest 실행 시 부모 stdin 핸들 복제 경합으로 간헐적
    # OSError가 나는 걸 produce 테스트에서 이미 실측 — 같은 이유로 여기도 끊는다.
    return subprocess.run([node_path, str(js_path)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15,
                           stdin=subprocess.DEVNULL)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_stages_has_whisper_between_emotion_arc_and_intonation(tmp_path):
    suffix = r"""
console.log(JSON.stringify(STAGES.map(([k]) => k)));
process.exit(0);
"""
    result = _run(NODE, suffix, tmp_path)
    assert result.returncode == 0, f"stderr={result.stderr}"
    import json
    keys = json.loads(result.stdout.strip().splitlines()[-1])
    assert "whisper" in keys, f"STAGES에 whisper가 없음: {keys}"
    ea, wh, it = keys.index("emotion_arc"), keys.index("whisper"), keys.index("intonation")
    assert ea < wh < it, (
        f"태그 순서 [감정][whispers]의 근거가 되는 emotion_arc < whisper < intonation 위반: {keys}"
    )


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_whisper_default_has_no_intensity_and_renders_no_range_input(tmp_path):
    suffix = r"""
profile = defaultProfile();
if ('intensity' in profile.whisper) {
  console.error('FAIL: defaultProfile().whisper에 intensity가 있음(설계 §6 위반) — ' + JSON.stringify(profile.whisper));
  process.exit(1);
}
renderStages();
const frag = getWhisperFrag();
if (!frag) { console.error('FAIL: whisper 스테이지가 렌더 결과에 없음'); process.exit(1); }
const rangeCount = (frag.match(/type=range/g) || []).length;
if (rangeCount !== 0) {
  console.error('FAIL: whisper 스테이지에 range 입력 ' + rangeCount + '개(기대 0 — "속삭임 강도" 슬라이더 금지)');
  process.exit(1);
}
const roleCheckboxCount = (frag.match(/setWhisperRole\(/g) || []).length;
if (roleCheckboxCount !== WHISPER_ROLES.length) {
  console.error('FAIL: role 체크박스 ' + roleCheckboxCount + '개(기대 ' + WHISPER_ROLES.length + ')');
  process.exit(1);
}
console.log('PASS');
process.exit(0);
"""
    result = _run(NODE, suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_unchecking_all_roles_yields_empty_array(tmp_path):
    suffix = r"""
profile = defaultProfile();  // whisper.roles=['반전']
setWhisperRole('반전', false);
if (JSON.stringify(profile.whisper.roles) !== '[]') {
  console.error('FAIL: 전부 해제 후 roles=' + JSON.stringify(profile.whisper.roles) + '(기대 [])');
  process.exit(1);
}
console.log('PASS');
process.exit(0);
"""
    result = _run(NODE, suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_missing_whisper_key_profile_fills_role_ban_on_load(tmp_path):
    """수정 1(loadPreset 병합 미러링)의 회귀 방지 — 리뷰 STALE 재현의 역:
    whisper 키가 없는 옛 동결 프로파일을 loadPreset()으로 열면 profile.whisper.roles가
    서버 merge_profile 기본값(["반전"])으로 채워지고, 렌더된 role 체크박스도 그 하나만
    checked여야 한다(화면=엔진 일치)."""
    suffix = r"""
(async () => {
  // whisper 키가 아예 없는 옛 동결 프로파일 재현(리뷰가 STALE로 잡은 그 모양).
  MOCK_PROFILE_RESPONSE = { profile: { normalize:{on:true}, spoken_style:{on:true,intensity:0.5} } };
  await loadPreset();
  if (!profile.whisper || JSON.stringify(profile.whisper.roles) !== '["반전"]') {
    console.error('FAIL: profile.whisper.roles=' + JSON.stringify(profile.whisper && profile.whisper.roles) +
      ' (기대 ["반전"] — merge_profile 미러링 실패, 수정 1 회귀)');
    process.exit(1);
  }
  const frag = getWhisperFrag();
  if (!frag) { console.error('FAIL: whisper 스테이지가 렌더 결과에 없음'); process.exit(1); }
  const checkedCount = (frag.match(/checked onchange="setWhisperRole\(/g) || []).length;
  if (checkedCount !== 1) {
    console.error('FAIL: 체크된 role 체크박스 ' + checkedCount + '개(기대 1=반전만) — ' +
      '화면이 여전히 엔진 기본값과 어긋남(리뷰 STALE 버그 재발)');
    process.exit(1);
  }
  if (frag.indexOf("checked onchange=\"setWhisperRole('반전'") === -1) {
    console.error('FAIL: 체크된 role이 반전이 아님');
    process.exit(1);
  }
  console.log('PASS');
  process.exit(0);
})().catch(e => { console.error('FAIL(예외): ' + (e && e.stack || e)); process.exit(1); });
"""
    result = _run(NODE, suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout
