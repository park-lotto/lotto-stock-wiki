# -*- coding: utf-8 -*-
"""3단계 화면(scene_play.js planClips)은 컷 리듬 칸을 **서버 렌더와 같은 규칙**으로 그린다 (2026-09-23 사장님 "미끼에 엄청 몰렸다").
실측 job 93ea9d2639e6: 미끼 조각 3개·자막 구절 12개 → 화면은 12컷(1.0~1.9초)을 그렸는데 렌더는 조각 한 번씩 3컷.
홀드 칸 = 첫 조각 한 컷 · 리듬 칸 = 조각 한 번씩 비례. video_assemble.plan_beat_clips_for의 _cr 분기와 짝(0순위-B)."""
import json, re, shutil, subprocess, tempfile
from pathlib import Path
import pytest

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"
PRE = """
const EPS=0.05, MIN_CLIP=0.8, MAX_SHOT=2.2, MAX_SLOWMO=1.15;
const DATA={segments:{a:{video_id:'v',start:0,end:6},b:{video_id:'v',start:6,end:9},c:{video_id:'v',start:9,end:12}},
            beats:[{cut_rhythm:{hold:true,max_shot:5}},{cut_rhythm:{hold:false,max_shot:4}},{}], src_duration:{v:30}};
const CUTS={}, SLOW={}, STRETCH={}; let onePerSeg=false;
const lists=[['a'],['a','b','c'],['a','b','c']];
function trimPieces(id){ const s=DATA.segments[id]; return s?[{video_id:s.video_id,start:s.start,end:s.end}]:[]; }
function phraseSyncOn(){ return true; }
function capsOf(){ return [{start:0},{start:1},{start:2},{start:3},{start:4},{start:5}]; }
function frozenClips(){ return null; }
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node 없음")
def test_화면_리듬칸은_조각_한번씩_홀드칸은_한컷():
    src = JS.read_text(encoding="utf-8")
    m = re.search(r"function planClips\(.*?\n}\n", src, re.S)
    assert m
    body = PRE + m.group(0) + """
console.log(JSON.stringify([planClips(lists[0],2.5,1,0), planClips(lists[1],12,1,1), planClips(lists[2],12,1,2)]));
"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(body); path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, (r.stderr or r.stdout)
    hold, rhythm, plain = json.loads(r.stdout.strip())
    assert [c["seg_id"] for c in hold] == ["a"] and hold[0]["dur"] == pytest.approx(2.5, abs=0.01)
    assert [c["seg_id"] for c in rhythm] == ["a", "b", "c"], "리듬 칸 = 조각 한 번씩(구절 6개로 쪼개지 않는다)"
    assert sum(c["dur"] for c in rhythm) == pytest.approx(12, abs=0.05)
    assert len(plain) == 6, "표식 없는 칸은 종전대로 구절 컷"
