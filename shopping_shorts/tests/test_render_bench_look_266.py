# -*- coding: utf-8 -*-
"""관제 266 ③ — render_bench 가 회원 팩 web.look(설정 화면에서 꾸민 모양 스냅샷)이 있으면 판 틀 대신 그것으로 틀·자막을 그린다.
견본 = fixtures/look_customframe.json(숏템설정서버 트랙 같은 이름 견본 복사 — 칼카피 틀 두 장: 0~1.804초 머리띠 남색 / 그 뒤 하늘색·자막 칸)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tools.calcopy.hybrid import render_bench as RB
from tools.calcopy.hybrid.common import StageError

FIX = Path(__file__).parent / "fixtures" / "look_customframe.json"
ROOT = Path(__file__).resolve().parents[2]


def _pack(tmp_path, look):
    p = tmp_path / "p_test.json"
    p.write_text(json.dumps({"1": {"tts": {"voice_id": "tc_6059dad0b83880769a50502f"}}, "web": {"look": look}}, ensure_ascii=False), encoding="utf-8")
    return p


def test_member_look_none_valid_invalid(tmp_path):
    assert RB.member_look(None) is None
    assert RB.member_look(_pack(tmp_path, None)) is None                       # 꾸민 모양 없음 = 판 틀 그대로
    look = json.loads(FIX.read_text(encoding="utf-8"))
    got = RB.member_look(_pack(tmp_path, look))
    assert got["presetId"] == look["presetId"] and got["customFrame"]["frame"]["spec"]
    with pytest.raises(StageError):
        RB.member_look(_pack(tmp_path, {"mode": "story", "presetId": "없는틀"}))   # 검사 실패 = 멈춤(조용히 판 틀로 안 돌아감)


def test_look_snapshot_takes_board_caption_pack_only_when_member_has_none():
    look = json.loads(FIX.read_text(encoding="utf-8"))
    st = {"caption": {"pack": None}, "packs": {}}
    snap = RB.look_snapshot(st, look)
    assert snap["presetId"] == look["presetId"] and snap["customFrame"]["id"] == look["customFrame"]["id"]


def _renderer_ready():
    if not shutil.which("node"):
        return False
    return subprocess.run(["node", "-e", "require.resolve('puppeteer',{paths:[process.argv[1]]})", str(ROOT / "tools")], capture_output=True, timeout=30).returncode == 0


@pytest.mark.skipif(not _renderer_ready(), reason="node·puppeteer 없음 — 실제 렌더 불가")
def test_look_frame_and_caption_user_values_reach_composed_video(tmp_path):
    """compose(burn_captions 와 같은 함수)에 회원 스냅샷 + 자막 크기·글자색 → 완성 프레임에 회원 틀(머리띠 남색)·창 영상(초록)·빨간 자막."""
    from PIL import Image
    from shopping_shorts import scene_style
    look = json.loads(FIX.read_text(encoding="utf-8"))
    pid = look["presetId"]
    look["captionLayouts"] = {f"{pid}:continuous:1:caption": {"placement": "free", "color": "#ff2020", "colorUser": True}}
    look["fontScales"] = {f"{pid}:frame:caption:1": 1.5}
    snap = RB.look_snapshot({"caption": {"pack": None}, "packs": {}}, RB.member_look(_pack(tmp_path, look)))
    base = tmp_path / "win.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x00c000:s=720x960:r=30:d=3", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-t", "3", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(base)], check=True, stdin=subprocess.DEVNULL)
    tl = [{"beat_idx": 0, "t0": 0, "dur": 1.9, "narration": "가", "caption_lines": ["가"], "role": "hook", "primary": {"video_id": "s0", "start": 0, "end": 1.9}},
          {"beat_idx": 1, "t0": 1.9, "dur": 1.1, "narration": "자막 색 시험", "caption_lines": ["자막 색 시험"], "role": "body", "primary": {"video_id": "s0", "start": 1.9, "end": 3}}]
    out = tmp_path / "out.mp4"
    scene_style.compose(str(base), tl, snap, str(out), tmp_path / "cw", {"text": ""})

    def frame(t):
        p = tmp_path / f"f{t}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1", str(p)], check=True, stdin=subprocess.DEVNULL)
        return Image.open(p).convert("RGB")
    a = frame(0.5)
    r, g, b = a.getpixel((540, 60))
    assert abs(r - 15) < 25 and abs(g - 59) < 25 and abs(b - 95) < 25, (r, g, b)      # 회원 틀 첫 장 머리띠(남색) — 판 틀이 아니다
    r, g, b = a.getpixel((540, 1300))
    assert g > 150 and r < 80 and b < 80, (r, g, b)                                   # 창 영상(초록)이 회원 틀의 영상 칸에
    c = frame(2.5)
    red = sum(1 for y in range(440, 760, 2) for x in range(0, 1080, 2) if (lambda p: p[0] > 180 and p[1] < 90 and p[2] < 90)(c.getpixel((x, y))))
    assert red > 300, red                                                             # 회원이 고른 자막 글자색(빨강)이 완성 영상에
