"""자동저장(_pushWork)이 job 연결을 지우지 않는다 — node 슬라이스 그라운딩(2026-08-03).

실사고: 배포 재시작 직후 MIX_JOB이 비어 있는 순간의 자동저장이 job_id=null을 보내
서버의 job 연결(작업↔대본 3개)을 지웠다 — 사장님 작업이 "빈 작업"이 됐다.
서버(/api/produce/works)는 "안 넘어온 필드는 보존" 설계이므로, 프론트가 **모를 때는
그 필드를 아예 보내지 않는 것**이 계약이다. 여기서 실제 _pushWork를 node로 돌려 못 박는다.
"""
import json
import pathlib
import re

import pytest

# ★node는 공용 하네스로 띄운다(2026-08-21). 직접 subprocess로 부르면 pytest가 stdin을
#   캡처한 상태라 윈도우에서 WinError 6(핸들이 잘못됨)로 간헐 실패한다 —
#   track finish 게이트가 이것 때문에 헛돌았다. 하네스가 stdin=DEVNULL과 임시파일
#   실행(명령줄 32,767자 상한 회피)을 함께 처리한다.
from shopping_shorts.tests.js_harness import requires_node, run_js_proc

pytestmark = requires_node

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def _push_work_src():
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    m = re.search(r"async function _pushWork\(\).*?\n}\n", html, re.S)
    assert m, "_pushWork를 produce.html에서 찾지 못함 — 이름이 바뀌었으면 테스트도 같이 옮길 것"
    return m.group(0)


def _run(mix_job_js):
    src = _push_work_src()
    script = f"""
let HANDOFF = [{{}}];      // 저장 가드 통과용(작업이 있다)
let WORK_ID = 'W1';
let MIX_JOB = {mix_job_js};
let cur = 2;
let _lastCommitted = null, _prevCommitted = null;
function _workState(){{ return {{handoff: HANDOFF, script: '대본', step: cur, work_id: WORK_ID}}; }}
function _markSaved(){{}}
function _markLocalOnly(){{}}
function _refreshRevertBtn(){{}}
const sessionStorage = {{ setItem(){{}}, getItem(){{ return null; }} }};
const location = {{ search: '' }};
const history = {{ replaceState(){{}} }};
class URLSearchParams {{ constructor(){{}} get(){{ return null; }} }}
let SENT = null;
async function fetch(url, opts){{
  SENT = JSON.parse(opts.body);
  return {{ json: async () => ({{ok: true, work_id: 'W1'}}) }};
}}
{src}
_pushWork().then(() => console.log(JSON.stringify(SENT)));
"""
    # encoding 명시 — 윈도우 기본 cp949로는 produce.html의 한글 주석이 디코드 에러를 낸다.
    out = run_js_proc(script)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_push_work_omits_job_id_when_unknown():
    """MIX_JOB이 비면 job_id 필드 자체가 없어야 한다 — null로 보내면 서버 연결이 지워진다."""
    sent = _run("null")
    assert "job_id" not in sent, "job을 모르는 저장이 job_id를 보냈다 — 서버 연결이 null로 덮인다"
    assert sent["work_id"] == "W1" and sent["step"] == 2


def test_push_work_sends_job_id_when_known():
    sent = _run("'JOB99'")
    assert sent["job_id"] == "JOB99"
