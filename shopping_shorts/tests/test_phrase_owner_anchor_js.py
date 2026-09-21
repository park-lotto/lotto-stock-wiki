# -*- coding: utf-8 -*-
"""믹스 화면(scene_play.js planClips)이 **서버가 실어 보낸 짝**으로 그리는가 — 보는 것 = 나오는 것.

서버 _lab_captions가 만든 captions(owner 포함)를 그대로 node의 planClips에 먹여,
서버 렌더 계획(_plan_phrase_clips)과 컷마다 (영상·시작·길이)가 같은지 본다(2026-09-21).
규칙을 화면에 다시 짜지 않았는지(0순위-B)도 함께 본다.
"""
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from shopping_shorts import app as appmod
from shopping_shorts import video_assemble as va

JS = Path(__file__).resolve().parents[1] / "static" / "scene_play.js"
NARR = "웬 키친타월인가 했더니, 기름때 낀 프라이팬을 쓱 닦아내는 항균 행주더라고요."
L3 = ["웬 키친타월인가 했더니", "기름때 낀 프라이팬을", "쓱 닦아내는 항균 행주더라고요"]
L4 = ["웬 키친타월인가 했더니", "기름때 낀 프라이팬을", "쓱 닦아내는", "항균 행주더라고요"]
SEG = {"a": {"video_id": "s2", "start": 30.23, "end": 31.63},
       "b": {"video_id": "s5", "start": 3.55, "end": 4.85},
       "c": {"video_id": "s2", "start": 33.76, "end": 34.80}}
TTS = 4.46
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="node 없음")


def _beat(tmp_path, lines, ids=("a", "b", "c")):
    mp3 = tmp_path / "b.mp3"
    mp3.write_bytes(b"x")
    return {"beat_idx": 0, "narration": NARR, "caption_lines": list(lines), "phrase_sync": True,
            "cap_durs": None, "cap_lead": 0.0, "tts_path": str(mp3), "target_seconds": TTS,
            "scene_override": [dict(SEG[i], seg_id=i) for i in ids]}


def _js_plan(caps, ids, live=True):
    src = JS.read_text(encoding="utf-8")
    m = re.search(r"function planClips\(.*?\n}\n", src, re.S)
    assert m, "planClips를 못 찾음"
    pre = """
const EPS=0.05, MIN_CLIP=0.8, MAX_SHOT=2.2, MAX_SLOWMO=1.15;
const DATA={segments:%s, beats:[{}], captions:{'0':%s}};
const CUTS={}, SLOW={}, STRETCH={}; let onePerSeg=false;
const IDS=%s; const lists=[%s];
function trimPieces(id){ const s=DATA.segments[id]; return s?[{video_id:s.video_id,start:s.start,end:s.end}]:[]; }
function phraseSyncOn(){ return true; }
function capsOf(i){ return DATA.captions[String(i)] || []; }
function frozenClips(){ return null; }
""" % (json.dumps(SEG), json.dumps(caps), json.dumps(list(ids)), "IDS" if live else "IDS.slice()")
    body = pre + m.group(0) + """
const out = planClips(IDS, %s, false, 0);
console.log(JSON.stringify({clips: out, caps: DATA.captions['0']}));
""" % TTS
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        path = fh.name
    r = subprocess.run(["node", path], capture_output=True, text=True, stdin=subprocess.DEVNULL,
                       encoding="utf-8")
    assert r.returncode == 0, (r.stderr or r.stdout)
    return json.loads(r.stdout.strip())


def _caps(monkeypatch, beat):
    monkeypatch.setattr(appmod.video_assemble, "_probe_duration", lambda p: TTS)
    return appmod._lab_captions({"beats": [beat]})[0]["0"]


def _same(server_plan, js_clips):
    assert len(server_plan) == len(js_clips)
    for s, c in zip(server_plan, js_clips):
        assert s["video_id"] == c["video_id"]
        assert s["start"] == pytest.approx(c["start"], abs=0.011)
        assert s["out_dur"] == pytest.approx(c["dur"], abs=0.011)     # 화면은 0.01초로 반올림한다


def test_얼린짝이_있으면_화면과_렌더가_같은_컷을_낸다(tmp_path, monkeypatch):
    b = _beat(tmp_path, L3)
    va.ensure_clip_anchor(b)
    b["caption_lines"] = list(L4)
    out = _js_plan(_caps(monkeypatch, b), ("a", "b", "c"))
    assert [c["video_id"] for c in out["clips"]] == ["s2", "s5", "s2", "s2"]
    _same(va._plan_phrase_clips(b, va._beat_material(b), TTS), out["clips"])


def test_옛_job은_화면도_장면_배정이_종전_그대로(tmp_path, monkeypatch):
    """배정은 옛 식 그대로(s2,s2,s5,s2). 이어 덮는 컷의 시작점은 서버와 같이 '되감지 않음'으로 바뀌었다."""
    b = _beat(tmp_path, L4)
    out = _js_plan(_caps(monkeypatch, b), ("a", "b", "c"))
    assert [c["video_id"] for c in out["clips"]] == ["s2", "s2", "s5", "s2"]
    _same(va._plan_phrase_clips(b, va._beat_material(b), TTS), out["clips"])


def test_화면에서_조각을_빼면_옛_식으로_그리고_받은_짝은_지운다(tmp_path, monkeypatch):
    """서버는 조각 3개 기준 짝을 줬는데 화면엔 2개뿐 — 서버도 저장 때 같은 식으로 다시 얼린다."""
    b = _beat(tmp_path, L3)
    va.ensure_clip_anchor(b)
    b["caption_lines"] = list(L4)
    caps = _caps(monkeypatch, b)
    out = _js_plan(caps, ("a", "b"))
    assert [c["video_id"] for c in out["clips"]] == ["s2", "s2", "s5", "s5"]
    assert all("owner" not in c for c in out["caps"]), "수가 되돌아와도 옛 짝을 되살리면 서버와 어긋난다"
    b2 = dict(b, scene_override=b["scene_override"][:2])
    va.ensure_clip_anchor(b2)                 # 저장(apply) 때 서버가 하는 일
    _same(va._plan_phrase_clips(b2, va._beat_material(b2), TTS), out["clips"])


def test_가짜_편성으로_불러본_것은_받은_짝을_안_지운다(tmp_path, monkeypatch):
    b = _beat(tmp_path, L3)
    va.ensure_clip_anchor(b)
    b["caption_lines"] = list(L4)
    out = _js_plan(_caps(monkeypatch, b), ("a", "b"), live=False)
    assert all("owner" in c for c in out["caps"])


def test_화면은_짝_규칙을_다시_짜지_않는다():
    src = JS.read_text(encoding="utf-8")
    assert "caps[k].owner" in src
    assert "clip_anchor" not in src, "글자 위치로 짝을 푸는 규칙은 서버 phrase_owners 한 곳에만 둔다"
