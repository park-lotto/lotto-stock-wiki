"""produce.html lenText()의 SYLLABLES_PER_SEC 상수 회귀(2026-07-17, 결함②-JS쪽).

배경: 화면 "N자 · 약 N초" 표시(lenText())가 예전엔 6.5를 썼다. 파이썬 쪽 진실
(shopping_shorts/edit_plan.py의 _SYLLABLES_PER_SEC)은 5.7로 맞췄지만, JS는 그 상수를
읽지 못하므로(서버가 값을 내려주지 않음 — 이 태스크 범위 밖) produce.html에 숫자를
나란히 박아야 한다. 이 테스트는 그 숫자가 5.7인지, 그리고 lenText()가 그 이름 있는
상수(SYLLABLES_PER_SEC)를 실제로 쓰는지(하드코딩된 다른 숫자로 몰래 안 갈라졌는지) 잠근다
— test_produce_category_race.py와 같은 방식으로 produce.html 실 소스를 그대로 잘라 Node로 돌린다.

Node 없으면 스킵(다른 baseline 실패로 안 잡히게).
"""
import shutil
import subprocess
import pytest

PRODUCE_HTML = __import__("pathlib").Path(__file__).resolve().parents[1] / "static" / "produce.html"

START_ANCHOR = "const SYLLABLES_PER_SEC"
END_ANCHOR = "function onScriptInput(){"

NODE = shutil.which("node")


def _extract_block() -> str:
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    start = text.find(START_ANCHOR)
    end = text.find(END_ANCHOR)
    assert start != -1, f"START_ANCHOR 못 찾음(produce.html이 바뀌었나): {START_ANCHOR!r}"
    assert end != -1 and end > start, f"END_ANCHOR 못 찾음: {END_ANCHOR!r}"
    return text[start:end]


def _run(suffix: str, tmp_path):
    block = _extract_block()
    script = "'use strict';\n" + block + suffix
    js_path = tmp_path / "len_text_speed.js"
    js_path.write_text(script, encoding="utf-8")
    return subprocess.run([NODE, str(js_path)], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=15,
                           stdin=subprocess.DEVNULL)


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_syllables_per_sec_is_5_7(tmp_path):
    suffix = r"""
if (SYLLABLES_PER_SEC !== 5.7) {
  console.error('FAIL: SYLLABLES_PER_SEC=' + SYLLABLES_PER_SEC + '(기대 5.7 — 성우 14명 실측치)');
  process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout


@pytest.mark.skipif(NODE is None, reason="node 없음 — JS 회귀 테스트 스킵")
def test_len_text_uses_syllables_per_sec_not_a_different_number(tmp_path):
    """220자 → **실제 발화초** 기준(220/7.41≈29.7초)이다.

    ★2026-09-18 계약 정정: 종전엔 `220 / SYLLABLES_PER_SEC`(5.7) = 38.6초를 잠갔는데,
      5.7은 **배속 1.0 기준 음절 속도**라 실제 발화가 아니다. 서버는
      `_SYLLABLES_PER_SEC × _speech_speed()` = 7.41자/초를 쓰는데 화면만 5.7이라
      **30% 갈라져 있었다**(배속이 2026-08-22에 들어왔는데 JS를 같이 안 고침).
      실측(라이브 job 20개·비트 168개, TTS 실파일): 화면 642초 vs 실제 491초 = **+31%**.
      잠글 값은 '음절 상수'가 아니라 **화면이 실제 음성과 맞는가**다.
    """
    suffix = r"""
const text = '가'.repeat(220);
const out = lenText(text);
const expectedSec = Math.round(220 / SPEECH_CHARS_PER_SEC);
if (out.indexOf('약 ' + expectedSec + '초') === -1) {
  console.error('FAIL: lenText(220자)=' + out + '(기대 "약 ' + expectedSec + '초" 포함, SPEECH_CHARS_PER_SEC=' + SPEECH_CHARS_PER_SEC + ')');
  process.exit(1);
}
if (expectedSec === 34) {
  console.error('FAIL: 결과가 옛 6.5 기준(약 34초)과 같음 — 상수가 실제로 안 바뀐 것 같다'); process.exit(1);
}
if (expectedSec === 39) {
  console.error('FAIL: 배속을 안 곱한 5.7 기준(약 39초) — 서버(7.41)와 30% 갈라진다'); process.exit(1);
}
if (Math.abs(SPEECH_CHARS_PER_SEC - 7.41) > 0.01) {
  console.error('FAIL: SPEECH_CHARS_PER_SEC=' + SPEECH_CHARS_PER_SEC + ' (기대 7.41 = 5.7 x 1.30, 서버 _speech_cps와 같아야 한다)');
  process.exit(1);
}
console.log('PASS'); process.exit(0);
"""
    result = _run(suffix, tmp_path)
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "PASS" in result.stdout
