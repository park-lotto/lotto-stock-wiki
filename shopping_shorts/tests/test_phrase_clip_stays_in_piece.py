# -*- coding: utf-8 -*-
"""구절 컷은 담은 조각의 끝을 넘지 않는다(2026-09-17 이윤정님 "미리보기에서 중간에 다른 화면이 짧게").

실측 job 1939bd7f3c50: s1 조각 5.92~7.29 바로 뒤(7.29~)가 다른 장면인데 구절 1.45초 >
조각 1.37초라 src_dur=1.45로 넘겨 0.08초가 새어 나왔다. 소스는 조각 안에서만 읽고(src_dur),
출력 길이(out_dur)는 구절 그대로 — 부족분은 _speed_and_freeze가 슬로모→정지로 채운다.
서버(_plan_phrase_clips)와 화면(scene_play.js planClips)이 같은 규칙이어야 한다(0순위-B).
"""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from shopping_shorts.video_assemble import _plan_phrase_clips

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"

# 조각 1.37초짜리 하나 + 구절 1.45초(리드인 0) → 구절이 조각보다 0.08초 길다
SEG = [{"video_id": "s1", "start": 5.92, "end": 7.29}]


def _beat():
    return {"narration": "갑작스런 낙상에서 어르신을 지켜줘요", "caption_lines": ["갑작스런 낙상에서 어르신을 지켜줘요"],
            "cap_durs": [1.45], "cap_lead": 0.0}


def test_server_src_dur는_조각_끝에서_멈추고_out_dur는_구절_그대로():
    plan = _plan_phrase_clips(_beat(), SEG, 1.45)
    assert plan and len(plan) == 1
    c = plan[0]
    assert c["out_dur"] == pytest.approx(1.45, abs=1e-6), "출력 길이는 구절(=음성) 그대로"
    assert c["start"] + c["src_dur"] <= 7.29 + 1e-6, "소스는 조각 끝을 넘지 않는다"
    assert c["src_dur"] == pytest.approx(1.37, abs=1e-6)


def test_server_조각이_충분하면_종전과_같다():
    seg = [{"video_id": "s1", "start": 5.92, "end": 9.0}]
    c = _plan_phrase_clips(_beat(), seg, 1.45)[0]
    assert c["src_dur"] == pytest.approx(1.45, abs=1e-6) and c["out_dur"] == pytest.approx(1.45, abs=1e-6)


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_화면_planClips도_조각_끝에서_멈춘다():
    src = JS.read_text(encoding="utf-8")
    m = re.search(r"function planClips\(.*?\n}\n", src, re.S)
    assert m, "planClips를 못 찾음"
    pre = """
const EPS=0.05, MIN_CLIP=0.8, MAX_SHOT=2.2, MAX_SLOWMO=1.15;
const DATA={segments:{a:{video_id:'s1',start:5.92,end:7.29}}, beats:[{}]};
const CUTS={}, SLOW={}, STRETCH={}; let onePerSeg=false;
const lists=[['a']];
function trimPieces(id){ const s=DATA.segments[id]; return s?[{video_id:s.video_id,start:s.start,end:s.end}]:[]; }
function phraseSyncOn(){ return true; }
function capsOf(){ return [{start:0}]; }
function frozenClips(){ return null; }
"""
    body = pre + m.group(0) + """
const out = planClips(['a'], 1.45, false, 0);
console.log(JSON.stringify(out));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, (r.stderr or r.stdout)
    import json
    clips = json.loads(r.stdout.strip())
    assert len(clips) == 1
    c = clips[0]
    assert c["dur"] == pytest.approx(1.45, abs=1e-6), "화면 시간은 구절 그대로"
    assert c["start"] + c["src_dur"] <= 7.29 + 1e-6, "소스는 조각 끝을 넘지 않는다(src_dur)"
