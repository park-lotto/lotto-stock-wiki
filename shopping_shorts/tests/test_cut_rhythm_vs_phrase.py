# -*- coding: utf-8 -*-
"""컷 리듬과 구절 맞춤의 우선순위 (2026-09-24 사장님 "컷 리듬으로 배치하고 구절맞춤은 끈 상태로 시작,
켜면 구절맞춤이 이기게").

둘은 같은 것을 다르게 정한다 — 구절 맞춤은 자막 구절마다 컷(6~12개), 컷 리듬은 담은 조각 수(3~4개).
그래서 ①컷 리듬을 단 칸은 구절 맞춤을 **끈 상태로 시작**하고 ②사람이 켜면 구절이 이긴다.
또 홀드 판정이 편성(_trim)과 렌더(_apply) 두 곳에 **다르게** 적혀 있어 화면과 렌더가 어긋났다 — 한 곳으로 모았다."""
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import video_assemble as va

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"


def _seg(vid, a, b):
    return {"video_id": vid, "start": a, "end": b}


def _plan():
    return {"beats": [
        {"beat_idx": 0, "role": "훅", "narration": "훅", "target_seconds": 2.0, "primary": _seg("v1", 0, 3)},
        {"beat_idx": 1, "role": "미끼", "narration": "소문이 났다는 거", "target_seconds": 6.0,
         "primary": _seg("v1", 4, 7), "alternates": [_seg("v2", 0, 3), _seg("v3", 0, 3)]},
        {"beat_idx": 2, "role": "고조1", "narration": "요철로 먼지를 없애 버렸다는 거", "target_seconds": 3.0,
         "primary": _seg("v2", 4, 7)},
    ]}


def test_컷리듬_단_칸은_구절맞춤이_꺼진_채로_시작한다():
    plan = _plan()
    mp._trim_for_cut_rhythm(plan)
    assert [b["phrase_sync"] for b in plan["beats"]] == [False, False, False]
    assert [b["cut_rhythm"]["hold"] for b in plan["beats"]] == [True, False, True], "미끼는 홀드가 아니다"


def test_홀드_판정은_편성과_렌더가_같은_함수다():
    plan = _plan()
    mp._trim_for_cut_rhythm(plan)
    before = [b["cut_rhythm"] for b in plan["beats"]]

    class _S:
        def get_setting(self, k, d=""):
            return "1" if k == "cut_rhythm_enabled" else d

    mp._apply_cut_rhythm(plan, _S(), {"customer_id": 0})
    assert [b["cut_rhythm"] for b in plan["beats"]] == before, "렌더가 편성 표식을 덮어쓰면 화면과 달라진다"
    # 표식이 없던 칸만 렌더가 단다 — 그때도 같은 홀드 식
    plan2 = {"beats": [{"beat_idx": 0, "role": "훅", "narration": "훅"},
                       {"beat_idx": 1, "role": "미끼", "narration": "난리가 났다는 거"}]}
    mp._apply_cut_rhythm(plan2, _S(), {"customer_id": 0})
    assert [b["cut_rhythm"]["hold"] for b in plan2["beats"]] == [True, False]


def test_렌더는_구절맞춤을_켜면_컷리듬을_무시한다():
    beat = {"beat_idx": 1, "narration": "일반 걸레로 닦으면 먼지가 밀린다는 거",
            "caption_lines": ["일반 걸레로 닦으면", "먼지가 밀린다는 거"], "cap_durs": [2.0, 2.0], "cap_lead": 0.0,
            "primary": _seg("v1", 0, 3), "alternates": [_seg("v2", 0, 3)],
            "cut_rhythm": {"max_shot": 4.0, "hold": True}, "phrase_sync": True}
    src = {"v1": 30.0, "v2": 30.0}
    plan = va.plan_beat_clips_for(beat, 4.0, src)
    assert len(plan) == 2, "구절 2개 → 컷 2개(홀드 한 컷이 아니다)"
    beat["phrase_sync"] = False
    plan2 = va.plan_beat_clips_for(beat, 4.0, src)
    assert len(plan2) == 1, "구절 맞춤을 끄면 홀드가 이긴다"


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_화면도_구절맞춤이_켜지면_컷리듬을_비켜준다():
    src = JS.read_text(encoding="utf-8")
    m = re.search(r"function planClips\(.*?\n}\n", src, re.S)
    assert m
    pre = """
const EPS=0.05, MIN_CLIP=0.8, MAX_SHOT=2.2, MAX_SLOWMO=1.15;
const DATA={segments:{a:{video_id:'v',start:0,end:6},b:{video_id:'v',start:6,end:12}},
            beats:[{cut_rhythm:{hold:true,max_shot:5}}], src_duration:{v:30}};
const CUTS={}, SLOW={}, STRETCH={}; let onePerSeg=false;
const lists=[['a','b']];
let PHRASE_ON=false;
function trimPieces(id){ const s=DATA.segments[id]; return s?[{video_id:s.video_id,start:s.start,end:s.end}]:[]; }
function phraseSyncOn(){ return PHRASE_ON; }
function capsOf(){ return [{start:0},{start:1},{start:2},{start:3}]; }
function frozenClips(){ return null; }
"""
    body = pre + m.group(0) + """
const off = planClips(lists[0], 8, 1, 0).length;
PHRASE_ON = true;
const on = planClips(lists[0], 8, 1, 0).length;
console.log(JSON.stringify({off, on}));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, encoding="utf-8", stdin=subprocess.DEVNULL)
    assert r.returncode == 0, (r.stderr or r.stdout)
    import json
    d = json.loads(r.stdout.strip())
    assert d["off"] == 1, "구절 맞춤 끔 = 홀드 한 컷"
    assert d["on"] == 4, "구절 맞춤 켬 = 자막 구절 수만큼"
