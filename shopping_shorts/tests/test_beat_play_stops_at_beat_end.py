# -*- coding: utf-8 -*-
"""칸 하나만 재생하면 **그 칸 끝에서 멈춘다** (2026-09-21 이연정님 제보).

제보: "예전에는 그 칸 클릭하면 그 칸만 재생됐는데, 지금은 다음 칸까지 이어서 계속 재생된다."
라이브 재현(job 393e0ff51de0, 칸1 끝 3.267초): playKey 'beat:0'·컷 3/3 끝난 뒤에도 합본 시각이
4.74 → 11.06초로 계속 흘렀다(칸 2·3·4까지 재생).

뿌리: 09-21 새벽부터 칸별 재생도 합본(전 칸의 화면+음성이 한 파일)으로 튼다. 조각 시절엔 그 칸의
mp3가 끝나면 저절로 멎었지만 합본은 한 파일이라 혼자 안 멈춘다. '칸 끝' 신호(onended)를 거는 곳이
전체 재생(runAllFrom) 하나뿐이었고, step()은 합본을 일부러 안 세운다(전체 재생이 칸에 멈추던 사고 때문).

실제 playBeat·pvxAudio를 node에서 돌려, 합본 시각이 칸 끝을 지날 때 pause가 불리는지 본다.
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

JS = (Path(__file__).resolve().parents[1] / "static" / "scene_play.js").read_text(encoding="utf-8")
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")


def _fn(name):
    m = re.search(r"function %s\(.*?\n}\n" % re.escape(name), JS, re.S)
    assert m, name + " 를 못 찾음"
    return m.group(0)


def _run(mode):
    body = """
let _iv = []; globalThis.setInterval = (f) => { _iv.push(f); return _iv.length; };
globalThis.clearInterval = (id) => { if (id) _iv[id - 1] = null; };
const tick = () => _iv.forEach(f => f && f());
const v = { currentTime: 0, paused: false, ended: false, duration: 20, src: 'blob:x', readyState: 4, error: null,
            pauses: 0, pause(){ this.paused = true; this.pauses++; }, play(){ this.paused = false; return Promise.resolve(); } };
const PVX = { vid: v, offs: [0, 3.267, 7.4], dur: 20, key: 'k', beats: [] };
let playKey = null, seqBeat = null, seq = [], seqI = 0, seqLabel = '', curAud = null, sel = 0;
const lists = [['a']], STRETCH = {}, DATA = { beats: [{}, {}, {}] };
function planClips(){ return [{ video_id: 's0', start: 0, dur: 3.2 }]; }
function beatDur(){ return 3.267; }
function pvxAttach(i, clips){ clips.forEach(c => { c._px = v; }); return true; }
function startSeq(clips){ seq = clips; seqI = clips.length; }     // 컷은 다 돌았다(합본은 step()에서 안 선다)
function armSfx(){} function tickSub(){} function togglePause(){}
function ttsEl(){ return { pause(){}, onended: null }; }
function seatTts(){ return ttsEl(); }
%s
const mode = %s;
playBeat(0, null);
if (mode === 'all') playKey = 'all';          // 그 사이 전체 재생이 주인을 가져갔다면 건드리면 안 된다
v.currentTime = 2.0; tick();
const midPauses = v.pauses;
v.currentTime = 3.30; tick();                 // 칸1 끝(3.267)을 지났다
console.log(JSON.stringify({ midPauses, pauses: v.pauses, paused: v.paused, playKey }));
""" % (_fn("pvxAudio") + _fn("audio") + _fn("playTts") + _fn("playBeat"), json.dumps(mode))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, stdin=subprocess.DEVNULL, encoding="utf-8")
    assert r.returncode == 0, (r.stderr or r.stdout)
    return json.loads(r.stdout.strip())


def test_칸_하나_재생은_칸_끝에서_합본을_세운다():
    out = _run("beat")
    assert out["midPauses"] == 0, "칸 중간에 세우면 안 된다"
    assert out["paused"] is True and out["pauses"] == 1, "칸 끝을 지났는데 합본이 계속 돈다 = 다음 칸까지 재생"
    assert out["playKey"] == "beat:0", "끝난 뒤 다시 누르면 처음부터 — 종전 동작 그대로"


def test_주인이_바뀌었으면_세우지_않는다():
    """칸 재생 중 전체 재생으로 넘어갔으면 이 감시가 전체 재생을 멈춰 세우면 안 된다."""
    out = _run("all")
    assert out["pauses"] == 0
