# -*- coding: utf-8 -*-
"""짧은 컷에서 미리보기가 통째로 검게 지나가던 것 (2026-09-01 사장님 제보).

증상(스크린샷 실측 · job 591432e714ca work d494d56fb57c의 8번 칸 CTA):
  미리보기가 검은 화면 · "컷 1/2" · 시간 0:00/0:02에서 안 흐름.
  ★서버는 멀쩡했다 — 소스 mp4 5개 존재, /api/mix/src 는 Range 206 정상(첫 청크 29ms),
    moov도 파일 앞(faststart), 제보 PC로 90분간 156건이 정상 전송됐다.

★근본 원인(코드 실측): step()이 시크를 기다리는 시간이 **1.5초 고정**이었다.
  구절 맞춤(2026-08-29 ac84faf6a)으로 컷이 자막 구절 길이로 짧아진 뒤
  그 칸의 컷은 1.0초·1.1초 — 즉 **기다림(1.5초) > 컷 길이(1.0초)**.
  준비되기도 전에 컷이 끝나 화면은 계속 검은 채로 다음 컷으로 넘어갔다.
  (첫 컷 소재 s0는 AV1이라 시크가 h264보다 느린 것도 겹쳤다)

계약 두 가지:
  ① 기다림은 **컷 길이보다 짧다**(cutWaitMs — 60%, 300~1500ms로 묶는다).
  ② 되감는 동안은 검은 화면 대신 **그 조각 썸네일**을 깔아둔다(holdShot).
"""
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")

_STUB = r"""
function _mkel(id){
  const el = { id, style:{}, classList:{add(){},remove(){},contains(){return false}},
    innerHTML:'', textContent:'', value:0, children:[],
    appendChild(c){ this.children.push(c); return c; }, querySelector(){return null},
    _attrs:{}, setAttribute(k,v){ this._attrs[k]=v; }, getAttribute(k){ return this._attrs[k]==null?null:this._attrs[k]; },
    parentNode:{insertBefore(){}},
    pause(){}, play(){ return {catch(){}}; }, load(){}, onended:null };
  return el;
}
const _els = {};
const document = {
  getElementById(id){ return _els[id] || (_els[id] = _mkel(id)); },
  addEventListener(){}, createElement(t){ return _mkel('new:'+t); },
  querySelectorAll(){ return []; },
  documentElement:{ style:{ setProperty(){} } },
};
const window = { addEventListener(){} };
function esc(t){ return String(t==null?'':t); }
"""


def _run(body):
    code = _STUB + JS.read_text(encoding="utf-8") + "\n" + body
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(code)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, (r.stderr or r.stdout)
    return r.stdout.strip().splitlines()


def test_기다림은_컷_길이를_넘지_않는다():
    """옛 코드: 1.5초 고정 → 1.0초짜리 컷은 켜기도 전에 끝났다."""
    out = _run("""
// 0.3초는 바닥값(300ms)에 걸린다 — 더 줄이면 첫 재생이 늘 헛돈다(옛 200ms 교훈).
[[1.0, 1000], [1.1, 1100], [2.6, 2600], [0.3, 300]].forEach(([d, ms]) => {
  const w = cutWaitMs({dur: d});
  console.log(d + ' wait=' + w + ' ' + (w <= ms ? 'OK' : 'LATE'));
});
console.log('CAP=' + cutWaitMs({dur: 99}));
""")
    for line in out[:-1]:
        assert line.endswith("OK"), f"컷보다 오래 기다린다: {line}"
    assert out[-1] == "CAP=1500", f"상한이 풀렸다: {out[-1]}"


def test_1초짜리_컷은_1초_안에_켜진다():
    """제보의 그 컷(1.0초·1.1초) — 옛 1.5초 고정이면 컷이 끝난 뒤에야 켜졌다."""
    out = _run("console.log(cutWaitMs({dur:1.0}) + ',' + cutWaitMs({dur:1.1}));")
    a, b = [int(x) for x in out[-1].split(",")]
    assert a == 600 and b == 660, out[-1]


def test_되감는_동안_썸네일이_깔린다():
    """검은 화면 대신 그 조각의 seg_thumb을 z-index 2로 덮는다(자막은 3이라 위에 남는다)."""
    out = _run("""
SL.server = true; SL.job = 'J1';
holdShot({seg_id: 's7-3', dur: 1.0}, true);
const im = _els['seekshot'];
console.log('SRC=' + im.src);
console.log('SHOW=' + im.style.display);
holdShot(null, false);
console.log('HIDE=' + _els['seekshot'].style.display);
""")
    assert out[0] == "SRC=/api/mix/seg_thumb/J1/s7-3", out[0]
    assert out[1] == "SHOW=block", out[1]
    assert out[2] == "HIDE=none", out[2]
