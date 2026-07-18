"""픽로그 프론트 배선 — logPick 헬퍼 동작 + 결정 5곳이 그것을 부른다(스펙 §9.4: 최소 변경).

DOM-heavy 함수는 라이브로 검증하고, 여기선 ①헬퍼가 올바른 payload를 fire-and-forget으로
보내는지(Node 슬라이스) ②5개 훅이 logPick을 호출하도록 배선됐는지(구조) 잠근다.
"""
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node 없음")


def _slice(src, start, end):
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


def test_logpick_sends_merged_payload_and_swallows_failure():
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    helper = _slice(src, "function logPick(", "\n// ==END logPick==")
    harness = helper + """
    var sent = null;
    // fetch가 거절해도 logPick은 절대 던지지 않아야 한다(fire-and-forget)
    global.fetch = function(url, opts){ sent = {url: url, opts: opts}; return Promise.reject(new Error('down')); };
    logPick('S2', {picked: '초안2', candidates: ['a','b','c']});
    var body = JSON.parse(sent.opts.body);
    if (sent.url !== '/api/pick_log') { console.error('URL 틀림', sent.url); process.exit(1); }
    if (body.stage !== 'S2' || body.picked !== '초안2' || body.candidates.length !== 3) {
        console.error('payload 틀림', JSON.stringify(body)); process.exit(1);
    }
    console.log('OK');
    """
    out = subprocess.run([NODE, "-e", harness], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "OK" in out.stdout


@pytest.mark.parametrize("func_start,stage", [
    ("function pickStyleCard(", "S6"),
    ("function useDraft(", "S2"),
    ("function pmUseDraft(", "S2"),
    ("async function startProduceMix(", "S3"),
    ("function pickThumbFrame(", "S7"),
    ("async function seoGenerate(", "S8"),
])
def test_each_hook_calls_logpick(func_start, stage):
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    i = src.index(func_start)
    # 함수 몸통 대략 900자 안에 그 단계의 logPick 호출이 있어야 한다
    body = src[i:i + 900]
    assert "logPick(" in body, f"{func_start} 에 logPick 호출 없음"
    assert f"logPick('{stage}'" in body, f"{func_start} 의 단계가 {stage}가 아님"
