# -*- coding: utf-8 -*-
"""칼카피 엔진 ① 뜯기(tools/calcopy/engine/analyze.py) — 답을 아는 시험.

ffmpeg 로 1080×1920·6초·30fps 영상을 만든다: 흰 바탕 + 상단 검정 띠 + 가운데 움직이는 창(잡음 — bench layout 은
'시간에 따라 변하는 화소'로 영상 창을 찾으므로 창이 있어야 자막 자리를 잰다) + 하단 검정 자막 2개
(0~3초 "스벅 메뉴판에", 3~6초 "숨겨진 사이즈", 글꼴 GmarketSansBold).
단언: (a) 글꼴 합산 top1 == GmarketSansBold (b) 자막 구간 2개 (c) probe 1080×1920.
제미나이는 부르지 않는다 — OCR 은 라벨의 시각으로 drawtext 글자를 그대로 돌려주는 가짜, 나머지는 빈 답.
사보타주(2026-10-16): FONT 를 NanumMyeongjo-ExtraBold.ttf 로 바꿔 만들면 (a)가 실패해야 한다.
제목 띠(검정 띠 위 흰 글자, BlackHanSans "숨은 메뉴 꿀팁")는 fonts.title 1위가 BlackHanSans 여야 한다(사보타주: 제목 글꼴을 바꾸면 실패).
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
TITLE_FONT = "BlackHanSans.ttf"     # 제목 띠는 자막과 다른 글꼴(분석기 2판 fonts.title)
TITLE = "숨은 메뉴 꿀팁"

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg 없음")


def _make_video(d: Path, font: str, title_font: str = TITLE_FONT) -> Path:
    shutil.copy(REPO / "shopping_shorts" / "static" / "fonts" / font, d / "f.otf")
    shutil.copy(REPO / "shopping_shorts" / "static" / "fonts" / title_font, d / "tf.ttf")
    (d / "title.txt").write_text(TITLE, encoding="utf-8")
    for i, t in enumerate(TEXTS):
        (d / f"t{i}.txt").write_text(t, encoding="utf-8")
    cap = ("drawtext=fontfile=f.otf:textfile=t{i}.txt:fontsize=84:fontcolor=black:x=(w-text_w)/2:y=1580:enable='{en}'")
    vf = ("[0:v][1:v]overlay=0:420,drawbox=x=0:y=0:w=1080:h=300:color=black:t=fill,"
          "drawtext=fontfile=tf.ttf:textfile=title.txt:fontsize=110:fontcolor=white:x=(w-text_w)/2:y=95,"
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
    if tag.startswith("title"):
        return {"items": [{"label": p, "lines": [TITLE]} for p in parts if isinstance(p, str)]}, None
    if tag.startswith("mat"):
        return {"items": [{"label": p, "kind": "글자만", "why": "시험"} for p in parts if isinstance(p, str)]}, None
    if tag.startswith("ov"):
        return {"items": [{"label": p, "overlays": []} for p in parts if isinstance(p, str)]}, None
    return {"segments": []}, None


def run_analyze(tmp: Path, font: str, title_font: str = TITLE_FONT) -> dict:
    from tools.calcopy.engine import analyze
    v = _make_video(tmp, font, title_font)
    return analyze.analyze(str(v), str(tmp / "out"), llm=fake_llm)


def test_analyze_known_answers(tmp_path):
    R = run_analyze(tmp_path, FONT)
    assert (R["probe"]["w"], R["probe"]["h"]) == (1080, 1920)
    assert R["captions"].get("ok"), R["captions"]
    assert R["captions"]["n_spans"] == 2, R["captions"]["spans"]
    assert R["fonts"].get("ok"), R["fonts"]
    assert R["fonts"]["top3"][0]["font"] == "GmarketSansBold.otf", R["fonts"]["top3"]
    assert R["fonts"]["title"].get("top3"), R["fonts"].get("title_bands")
    assert R["fonts"]["title"]["top3"][0]["font"] == TITLE_FONT, R["fonts"]["title"]
    assert R["fonts"]["title"]["italic"] is False
    out = tmp_path / "out"
    for f in ("뜯기.json", "뜯기.md", "sheet.jpg"):
        assert (out / f).exists(), f
    assert list((out / "fonts").glob("*.png")) and list((out / "captions").glob("*.png"))


def _make_accum_video(d: Path) -> Path:
    """흰 바탕 · 위 고정 제목 2줄(검정, 영상 내내 같음) · 가운데 잡음 창 · 아래 검정 누적형 자막
    (0~6초 1줄 '스벅 메뉴판에', 3~6초 2줄째 '숨겨진 사이즈' 덧붙음). 2026-10-16 방구석·썰풀다 점검 결함 재현용:
    제목이 자막 1등으로 뽑힘(썰풀다 7DYbxVNz5q8) · 흰 바탕 검정 글자를 bright 로 고름(방구석 ILIiqCJAOSI)."""
    shutil.copy(REPO / "shopping_shorts" / "static" / "fonts" / FONT, d / "f.otf")
    for name, t in (("a", TEXTS[0]), ("b", TEXTS[1]), ("h1", "스타벅스 직원만"), ("h2", "아는 비밀 메뉴")):
        (d / f"{name}.txt").write_text(t, encoding="utf-8")
    dt = "drawtext=fontfile=f.otf:textfile={f}.txt:fontsize={s}:fontcolor=black:x=(w-text_w)/2{jx}:y={y}{en}"
    # 제목은 0.5초마다 3px 흔들린다 — 압축·애니로 고정 제목의 잉크가 출렁여 '구간'이 여럿 잡히던 썰풀다 7DYb 꼴
    jit = "+3*mod(floor(t*2)\,2)"
    vf = ("[0:v][1:v]overlay=0:520," + dt.format(f="h1", s=96, y=170, en="", jx=jit) + ","
          + dt.format(f="h2", s=96, y=300, en="", jx=jit)
          + "," + dt.format(f="a", s=72, y=1560, en="", jx="") + "," + dt.format(f="b", s=72, y=1660, en=":enable='gte(t,3)'", jx=""))
    out = d / "accum.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=white:s=1080x1920:d=6:r=30",
                    "-f", "lavfi", "-i", "color=gray:s=1080x900:d=6:r=30,noise=alls=100:allf=t+u",
                    "-filter_complex", vf, "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
                    str(out)], check=True, cwd=d)
    return out


def test_layout_title_not_caption_and_dark_ink(tmp_path):
    """고정 제목은 자막이 아니고(바뀜≈0), 흰 바탕 검정 자막은 dark, 누적형 2줄째까지 띠에 들어간다."""
    from shopping_shorts.channelkit.bench import probe
    from tools.calcopy.engine import layout1
    v = _make_accum_video(tmp_path)
    r = layout1.measure(str(v), probe.info(str(v)))
    c = r["vl"]["caption"]
    assert c["pos"] == "below" and c["ink"] == "dark", (c, r["caption_candidates"])
    cap = r["caption"]
    assert len(cap["spans"]) == 2, cap["spans"]
    assert [it["lines"] for it in cap["items"]] == [1, 2], cap["items"]
    above = [x for x in r["caption_candidates"] if x["pos"] == "above" and x.get("score") is not None]
    assert all(x["change"] < 0.3 for x in above), above


def _blocks(w: int, h: int, dur: float, lo: int = 0, span: int = 255) -> str:
    """프레임마다 4×4 덩어리 무작위 밝기(압축 뒤에도 시간 표준편차가 커서 bench 창 검출이 확실히 잡는다)."""
    return (f"nullsrc=s={w // 4}x{h // 4}:d={dur}:r=30,geq=lum='{lo}+random(1)*{span}':cb=128:cr=128,"
            f"scale={w}:{h}:flags=neighbor")


def _ff(d: Path, out: str, inputs: list[str], vf: str, dur: float = 6) -> Path:
    args = ["ffmpeg", "-v", "error", "-y"]
    for i in inputs:
        args += ["-f", "lavfi", "-i", i]
    subprocess.run(args + ["-filter_complex", vf, "-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
                           out], check=True, cwd=d)
    return d / out


def test_outlined_caption_on_moving_bright_video(tmp_path):
    """움직이는 밝은 영상 위 흰 글자 + 굵은 검정 외곽선(6px) 자막 2개(mYxuF1A74j4 꼴):
    창 안 bright 자막으로 잡히고, 자막 2개가 흔들림으로 버려지지 않으며, 외곽선 두께 4~8px·그림자 없음."""
    from shopping_shorts.channelkit.bench import probe
    from tools.calcopy.engine import layout1
    shutil.copy(REPO / "shopping_shorts" / "static" / "fonts" / FONT, tmp_path / "f.otf")
    for i, t in enumerate(TEXTS):
        (tmp_path / f"t{i}.txt").write_text(t, encoding="utf-8")
    cap = ("drawtext=fontfile=f.otf:textfile=t{i}.txt:fontsize=80:fontcolor=white:borderw=6:bordercolor=black:"
           "x=(w-text_w)/2:y=1250:enable='{en}'")
    vf = ("[0:v][1:v]overlay=0:300," + cap.format(i=0, en="lt(t,3)") + "," + cap.format(i=1, en="gte(t,3)"))
    v = _ff(tmp_path, "outl.mp4", ["color=black:s=1080x1920:d=6:r=30", _blocks(1080, 1620, 6, lo=120, span=135)], vf)
    r = layout1.measure(str(v), probe.info(str(v)))
    c = r["vl"]["caption"]
    assert c["pos"] == "inside" and c["ink"] == "bright", (c, r["caption_candidates"])
    capr = r["caption"]
    assert len(capr["spans"]) == 2, (capr["spans"], capr.get("unstable"))
    g = capr["glyph"][0]
    assert g["outline"] and 4 <= g["outline_px"] <= 8 and g["shadow"] is None, g


def test_hook_card_then_body_frame(tmp_path):
    """0~1.5초 훅 카드(어두운 전면 + 큰 흰 제목) 뒤 본문 틀(흰 바탕·창·아래 자막): 틀이 다른 구간이 1.5초±0.1 에서 끝난다.
    12초 — 창 다수결 조각(6초 기준, 최소 3조각)이 2초 조각이면 표본 4장이라 창이 안 잡힌다(실영상은 20초 이상)."""
    from shopping_shorts.channelkit.bench import probe
    from tools.calcopy.engine import layout1
    shutil.copy(REPO / "shopping_shorts" / "static" / "fonts" / FONT, tmp_path / "f.otf")
    (tmp_path / "h.txt").write_text("오늘의 비밀", encoding="utf-8")
    for i, t in enumerate(TEXTS):
        (tmp_path / f"t{i}.txt").write_text(t, encoding="utf-8")
    cap = "drawtext=fontfile=f.otf:textfile=t{i}.txt:fontsize=72:fontcolor=black:x=(w-text_w)/2:y=1560:enable='{en}'"
    vf = ("[0:v][1:v]overlay=0:420," + cap.format(i=0, en="between(t,1.5,6.75)") + "," + cap.format(i=1, en="gte(t,6.75)")
          + ",drawbox=x=0:y=0:w=1080:h=1920:color=0x202020:t=fill:enable='lt(t,1.5)'"
          + ",drawtext=fontfile=f.otf:textfile=h.txt:fontsize=140:fontcolor=white:x=(w-text_w)/2:y=800:enable='lt(t,1.5)'")
    v = _ff(tmp_path, "hook.mp4", ["color=white:s=1080x1920:d=12:r=30", _blocks(1080, 1000, 12)], vf, dur=12)
    r = layout1.measure(str(v), probe.info(str(v)))
    other = r["window"]["other_frame_segments"]
    assert other and abs(other[0][0] - 0.0) <= 0.1 and abs(other[0][1] - 1.5) <= 0.1, (other, r["window"])
    assert r["vl"]["window"][1] == 420, r["vl"]["window"]
