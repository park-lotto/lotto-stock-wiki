# -*- coding: utf-8 -*-
"""칼카피 엔진 ① 뜯기(tools/calcopy/engine/analyze.py) — 답을 아는 시험.

ffmpeg 로 1080×1920·6초·30fps 영상을 만든다: 흰 바탕 + 상단 검정 띠 + 가운데 움직이는 창(잡음 — bench layout 은
'시간에 따라 변하는 화소'로 영상 창을 찾으므로 창이 있어야 자막 자리를 잰다) + 하단 검정 자막 2개
(0~3초 "스벅 메뉴판에", 3~6초 "숨겨진 사이즈", 글꼴 GmarketSansBold).
단언: (a) 글꼴 합산 top1 == GmarketSansBold (b) 자막 구간 2개 (c) probe 1080×1920.
제미나이는 부르지 않는다 — OCR 은 라벨의 시각으로 drawtext 글자를 그대로 돌려주는 가짜, 나머지는 빈 답.
사보타주(2026-10-16): FONT 를 NanumMyeongjo-ExtraBold.otf 로 바꿔 만들면 (a)가 실패해야 한다.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FONT = "GmarketSansBold.otf"
TEXTS = ("스벅 메뉴판에", "숨겨진 사이즈")

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")


def _make_video(d: Path, font: str) -> Path:
    shutil.copy(REPO / "shopping_shorts" / "static" / "fonts" / font, d / "f.otf")
    for i, t in enumerate(TEXTS):
        (d / f"t{i}.txt").write_text(t, encoding="utf-8")
    cap = ("drawtext=fontfile=f.otf:textfile=t{i}.txt:fontsize=84:fontcolor=black:x=(w-text_w)/2:y=1580:enable='{en}'")
    vf = ("[0:v][1:v]overlay=0:420,drawbox=x=0:y=0:w=1080:h=300:color=black:t=fill,"
          + cap.format(i="0", en="lt(t,3)") + "," + cap.format(i="1", en="gte(t,3)"))
    out = d / "test.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=white:s=1080x1920:d=6:r=30",
                    "-f", "lavfi", "-i", "color=gray:s=1080x1000:d=6:r=30,noise=alls=100:allf=t+u",
                    "-filter_complex", vf, "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
                    str(out)], check=True, cwd=d)
    return out


def fake_llm(parts, prompt, tag):
    """가짜 제미나이: OCR 이면 라벨 '자막 i (t0~t1s)' 의 가운데 시각으로 그린 글자를 돌려준다."""
    if tag.startswith("ocr"):
        items = []
        for p in parts:
            if isinstance(p, str):
                m = re.match(r"자막 (\d+) \(([\d.]+)~([\d.]+)s\)", p)
                if m:
                    mid = (float(m.group(2)) + float(m.group(3))) / 2
                    items.append({"label": p, "lines": [TEXTS[0] if mid < 3 else TEXTS[1]]})
        return {"items": items}, None
    if tag.startswith("mat"):
        return {"items": [{"label": p, "kind": "글자만", "why": "시험"} for p in parts if isinstance(p, str)]}, None
    if tag.startswith("ov"):
        return {"items": [{"label": p, "overlays": []} for p in parts if isinstance(p, str)]}, None
    return {"segments": []}, None


def run_analyze(tmp: Path, font: str) -> dict:
    from tools.calcopy.engine import analyze
    v = _make_video(tmp, font)
    return analyze.analyze(str(v), str(tmp / "out"), llm=fake_llm)


def test_analyze_known_answers(tmp_path):
    R = run_analyze(tmp_path, FONT)
    assert (R["probe"]["w"], R["probe"]["h"]) == (1080, 1920)
    assert R["captions"].get("ok"), R["captions"]
    assert R["captions"]["n_spans"] == 2, R["captions"]["spans"]
    assert R["fonts"].get("ok"), R["fonts"]
    assert R["fonts"]["top3"][0]["font"] == "GmarketSansBold.otf", R["fonts"]["top3"]
    out = tmp_path / "out"
    for f in ("뜯기.json", "뜯기.md", "sheet.jpg"):
        assert (out / f).exists(), f
    assert list((out / "fonts").glob("*.png")) and list((out / "captions").glob("*.png"))
