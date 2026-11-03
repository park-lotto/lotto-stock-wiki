"""칼카피 틀 설명서(frame.json) — 형식 검사 · 스냅샷 변환 · 라이브 렌더러 설명서 모드 실제 렌더.

설계 docs/superpowers/specs/2026-10-15-칼카피엔진-design.md §5·§6-3.
(c)는 실제 렌더(node+puppeteer, render_layer_one)를 돌린다 — 그림에서 잉크·투명을 잰다.
"""
import copy
import json
import shutil
from pathlib import Path

import pytest
from PIL import Image

from shopping_shorts import scene_style
from shopping_shorts.calcopy_frame import schema, to_snapshot

ROOT = Path(__file__).resolve().parents[2]
FRAME_A = ROOT / "shopping_shorts/calcopy_frame/examples/frame_A_ZdeZRtCeAC4.json"


def frame_a():
    return json.loads(FRAME_A.read_text(encoding="utf-8"))


def text_layer(frame, role):
    return next(l for l in frame["layers"] if l.get("kind") == "text" and l.get("role") == role)


# ── (a) 형식 검사 ──
def test_frame_a_valid_and_zero_null_are_values():
    spec = schema.validate(frame_a())
    title = text_layer(spec, "title")
    assert title["outline"] == {"px": 0, "rgb": [0, 0, 0]}      # px 0 = 유효(외곽선 없음), 기본값으로 튀지 않는다
    assert title["letter_spacing"] == 0 and title["line_rgb"] is None and title["shadow"] is None
    video = next(l for l in spec["layers"] if l["kind"] == "video")
    assert video["x"] == 0 and video["radius"] == 0              # 0 좌표·0 모서리 그대로
    cap = text_layer(spec, "caption")
    assert cap["outline"] is None and cap["enter"] is None


def test_line_h_default_only_when_absent():
    f = frame_a(); t = text_layer(f, "caption"); t.pop("line_h")
    assert text_layer(schema.validate(f), "caption")["line_h"] == round(t["size"] * 1.15)
    f = frame_a(); text_layer(f, "caption")["line_h"] = None
    assert text_layer(schema.validate(f), "caption")["line_h"] == round(text_layer(f, "caption")["size"] * 1.15)


@pytest.mark.parametrize("break_it, word", [
    (lambda f: text_layer(f, "title").__setitem__("font", "NoSuchFont"), "font"),
    (lambda f: text_layer(f, "title").__setitem__("rgb", [0, 0, 256]), "rgb"),
    (lambda f: text_layer(f, "title").__setitem__("size", True), "size"),            # 참/거짓은 숫자가 아니다
    (lambda f: text_layer(f, "brand").__setitem__("text", ""), "text"),
    (lambda f: f["layers"].append({"kind": "video", "x": 0, "y": 0, "w": 10, "h": 10}), "video"),
    (lambda f: f["layers"].extend([{"kind": "band", "x": 0, "y": 0, "w": 1, "h": 1, "rgb": [0, 0, 0]}] * 13), "layers"),   # 기존 4~5층 + 13 = 상한 16 넘김
    (lambda f: text_layer(f, "caption").__setitem__("enter", {"kind": "slide", "ms": 300}), "enter"),   # 자막 등장은 pop|fade|rise|typewriter|none
    (lambda f: text_layer(f, "caption").__setitem__("emphasis", {"words": [], "rgb": [255, 230, 0]}), "emphasis"),
    (lambda f: f.__setitem__("canvas", [1080]), "canvas"),
])
def test_validate_rejects(break_it, word):
    f = frame_a(); break_it(f)
    with pytest.raises(schema.FrameError) as err:
        schema.validate(f)
    assert word in str(err.value)


# ── (b) 스냅샷 변환 → 서버 검사 ──
def test_to_snapshot_passes_validate_snapshot():
    snap = to_snapshot.to_snapshot(frame_a())
    ok = scene_style.validate_snapshot(copy.deepcopy(snap))
    assert ok["presetId"] == snap["presetId"] and ok["presetId"].startswith("custom_")
    assert ok["customFrame"]["frame"]["spec"] == schema.validate(frame_a())
    assert ok["hookMotion"] == "none" and ok["motionPack"] == "off"   # 등장 없음 = 라이브 기본(줌 펀치)을 물려받지 않는다
    assert to_snapshot.frame_id(schema.validate(frame_a())) == snap["presetId"]   # 같은 설명서 = 같은 번호


def test_validate_snapshot_rebuilds_row_and_rejects_tamper():
    snap = to_snapshot.to_snapshot(frame_a())
    junk = copy.deepcopy(snap); junk["customFrame"]["frame"]["lines"] = []; junk["customFrame"]["evil"] = 1
    rebuilt = scene_style.validate_snapshot(junk)["customFrame"]
    assert "evil" not in rebuilt and rebuilt["frame"]["lines"]               # 실려 온 행은 설명서로 다시 만든다
    moved = copy.deepcopy(snap); text_layer(moved["customFrame"]["frame"]["spec"], "caption")["y"] += 5
    with pytest.raises(ValueError):                                          # 설명서를 바꾸고 번호는 그대로 = 거절
        scene_style.validate_snapshot(moved)
    story = copy.deepcopy(snap); story["mode"] = "story"
    with pytest.raises(ValueError):
        scene_style.validate_snapshot(story)
    ghost = {"version": 1, "mode": "continuous", "presetId": snap["presetId"]}   # 행 없이 번호만 = 모르는 틀
    with pytest.raises(ValueError):
        scene_style.validate_snapshot(ghost)


def test_existing_fixed_template_still_validates():
    ok = scene_style.validate_snapshot({"version": 1, "mode": "continuous", "presetId": "fixed_s0034", "hookMotion": "none"})
    assert ok["presetId"] == "fixed_s0034" and "customFrame" not in ok


# ── (c) 라이브 렌더러 설명서 모드 실제 렌더 ──
def _renderer_ready():
    """렌더러(tools/render_scene_style.js)가 require 하는 puppeteer 를 node 가 찾나 — 트랙 폴더는 상위(main) node_modules 를 쓴다."""
    import subprocess
    if not shutil.which("node"):
        return False
    probe = subprocess.run(["node", "-e", "require.resolve('puppeteer',{paths:[process.argv[1]]})", str(ROOT / "tools")],
                           capture_output=True, timeout=30)
    return probe.returncode == 0


@pytest.mark.skipif(not _renderer_ready(), reason="node·puppeteer 없음 — 실제 렌더 불가")
def test_frame_a_render_layer_has_ink_where_spec_says(tmp_path):
    frame = frame_a()
    spec = schema.validate(frame)
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
    cap = "아니 이거 해외 릴스에서 맨날 보이길래"
    timeline = [{"beat_idx": 0, "t0": 0, "dur": 8, "narration": cap, "caption_lines": [cap], "role": "hook",
                 "primary": {"video_id": "s0", "start": 0, "end": 8}},
                {"beat_idx": 1, "t0": 8, "dur": 2, "narration": "끝 장면", "caption_lines": ["끝 장면"], "role": "body",
                 "primary": {"video_id": "s0", "start": 8, "end": 10}}]   # 장면 2(8초 시작)는 틀 A 의 template_off.tail_sec=2.18 에 걸린다
    png = scene_style.render_layer_one(timeline, snap, tmp_path, 0, {"text": "닿으면 스피커\n소름 돋는 음질 수준"}, "t")
    im = Image.open(png).convert("RGBA"); px = im.load()
    assert im.size == (1080, 1920)

    def ink(y0, y1):   # 불투명하고 어두운 점(글자) 수
        return sum(1 for y in range(int(y0), int(y1), 2) for x in range(0, 1080, 3)
                   if px[x, y][3] > 200 and sum(px[x, y][:3]) < 200)
    title, caption = text_layer(spec, "title"), text_layer(spec, "caption")
    t0, t1 = title["y"], title["y"] + title["lines"] * title["line_h"]
    c0, c1 = caption["y"], caption["y"] + caption["line_h"]
    assert ink(t0, t1) > 2000, ink(t0, t1)
    assert ink(c0, c1) > 800, ink(c0, c1)
    # 원본 프레임에서 잰 자리(제목 223~397·자막 1467~1528) — 설명서가 그 자리에 그려지는지
    assert ink(223, 397) > 2000 and ink(1467, 1528) > 800
    assert ink(1560, 1900) == 0                                   # 자막 아래는 바탕만
    video = next(l for l in spec["layers"] if l["kind"] == "video")
    alpha = [px[x, y][3] for y in range(video["y"] + 4, video["y"] + video["h"] - 4, 25) for x in range(0, 1080, 40)]
    assert max(alpha) == 0                                         # 영상 창은 투명(omitBackground) — 합성이 영상을 둔다
    assert px[540, video["y"] - 6][3] == 255 and px[540, 1800][3] == 255   # 바탕은 불투명


@pytest.mark.skipif(not _renderer_ready(), reason="node·puppeteer 없음 — 실제 렌더 불가")
def test_spec_caption_user_size_color_reach_render(tmp_path):
    """관제 266: 칼카피 틀 자막에 고객이 정한 크기(fontScales)·글자색(captionLayouts colorUser)·자막박스색(bgUser)·위치(textOffsets)가
    렌더 레이어(render_layer_one — 렌더·캡컷·썸네일이 찍는 같은 페이지)에 실제로 나오는가. 값 없으면 설명서 그대로(옛 그림)."""
    frame = frame_a()
    spec = schema.validate(frame)
    cap = text_layer(spec, "caption")
    base = to_snapshot.to_snapshot(frame)
    pid = base["presetId"]
    timeline = [{"beat_idx": 0, "t0": 0, "dur": 8, "narration": "자막 크기 색 시험", "caption_lines": ["자막 크기 색 시험"], "role": "hook",
                 "primary": {"video_id": "s0", "start": 0, "end": 8}}]

    def shot(extra, tag):
        snap = scene_style.validate_snapshot({**base, **extra})
        return Image.open(scene_style.render_layer_one(timeline, snap, tmp_path / tag, 0, {"text": "제목"}, tag)).convert("RGBA")

    def stats(im, y0, y1):
        px = im.load(); dark = red = blue = 0; xs = []; ys = []
        for y in range(int(y0), int(y1), 2):
            for x in range(0, 1080, 2):
                r, g, b, a = px[x, y]
                if a < 200:
                    continue
                if r > 180 and g < 80 and b < 80:
                    red += 1; xs.append(x)
                elif b > 180 and r < 80 and g < 120:
                    blue += 1
                elif r + g + b < 200:
                    dark += 1; xs.append(x); ys.append(y)
        return {"dark": dark, "red": red, "blue": blue, "span": (max(xs) - min(xs)) if xs else 0, "cy": sum(ys) / len(ys) if ys else 0}
    y0, y1 = cap["y"] - 60, cap["y"] + cap["line_h"] + 160
    d = stats(shot({}, "d"), y0, y1)
    assert d["dark"] > 300 and d["red"] == 0 and d["blue"] == 0, d          # 기본 = 설명서 검정 글자, 상자 없음
    u = stats(shot({"fontScales": {f"{pid}:frame:caption:0": 1.5},
                    "captionLayouts": {f"{pid}:continuous:0:caption": {"placement": "free", "color": "#ff2020", "colorUser": True,
                                                                       "background": "#2050ff", "bgUser": True}}}, "u"), y0, y1)
    assert u["red"] > 300 and u["blue"] > 300, u                           # 고객 글자색·자막박스색이 렌더에 나온다
    assert u["span"] > d["span"] * 1.2, (d, u)                             # 크기 1.5배 → 글자 폭이 넓어진다
    m = shot({"textOffsets": {f"{pid}:frame:caption:0": 5}}, "m")          # 위치 ↓ 5% = 96px
    assert abs(stats(m, y0, y1)["cy"] - d["cy"] - 96) < 12, (d, stats(m, y0, y1))


@pytest.mark.skipif(not _renderer_ready(), reason="node·puppeteer 없음 — 실제 렌더 불가")
def test_template_off_tail_scene_draws_nothing(tmp_path):
    """원본 끝(21.8초~)은 틀이 사라지고 영상이 전체 화면 — template_off 에 걸린 장면은 레이어가 전부 투명, 영상 칸은 전체."""
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame_a()))
    timeline = [{"beat_idx": i, "t0": t0, "dur": d, "narration": c, "caption_lines": [c], "role": "hook" if i == 0 else "body",
                 "primary": {"video_id": "s0", "start": t0, "end": t0 + d}}
                for i, (t0, d, c) in enumerate([(0, 8, "첫 장면 자막"), (8, 2, "끝 장면 자막")])]
    layers = scene_style.render_layers(timeline, snap, tmp_path, {"text": "닿으면 스피커\n소름 돋는 음질 수준"}, "t")
    assert len(layers) == 2
    assert layers[1]["media"] == {"top": 0, "height": 100}
    assert Image.open(tmp_path / layers[1]["file"]).convert("RGBA").split()[3].getextrema()[1] == 0
    assert layers[0]["media"]["top"] > 0                                      # 장면 1은 틀 그대로
    assert Image.open(tmp_path / layers[0]["file"]).convert("RGBA").split()[3].getextrema()[1] == 255


def test_template_off_schema():
    f = frame_a(); f["template_off"] = {"tail_sec": 0, "scenes": [3, 1, 3]}
    assert schema.validate(f)["template_off"] == {"tail_sec": 0, "scenes": [1, 3]}   # 0 = 유효(끄는 장면 없음), 번호는 정렬·중복 제거
    f = frame_a(); f["template_off"] = None
    assert schema.validate(f)["template_off"] is None
    for bad in ({"tail_sec": -1}, {"scenes": "1"}, {"when": 3}, {"tail_sec": True}):
        f = frame_a(); f["template_off"] = bad
        with pytest.raises(schema.FrameError):
            schema.validate(f)


def test_line_outline_schema_and_snapshot_depth():
    f = frame_a(); t = text_layer(f, "title")
    t["line_outline"] = [None, {"px": 6, "rgb": [255, 255, 255]}]       # {px,rgb} 로 써도 [px,r,g,b] 로 정규화
    spec = schema.validate(f)
    assert text_layer(spec, "title")["line_outline"] == [None, [6, 255, 255, 255]]
    scene_style.validate_snapshot(to_snapshot.to_snapshot(f))            # 서버 검사 깊이 상한(8) 안
    t["line_outline"] = [[6, 255, 255]]
    with pytest.raises(schema.FrameError):
        schema.validate(f)


def test_frames_with_time_spans_and_video_cuts():
    """틀 여러 장 + 시간축(훅 카드 0~1.5초 / 본문) · 영상 창 컷별 자리 · 자막 아래 붙임 · 누적 자막 valign top."""
    hook = [{"kind": "bg", "rgb": [64, 64, 64]}, {"kind": "video", "x": 0, "y": 672, "w": 1080, "h": 1026}]
    body = [{"kind": "bg", "rgb": [255, 255, 255]},
            {"kind": "video", "x": 165, "y": 750, "w": 750, "h": 897, "anchor": {"below": "caption", "gap": 18},
             "cuts": [{"t": [1.5, 3.4], "w": 750, "h": 897}, {"t": [9.97, 10.77], "w": 906, "h": 495, "x": 87, "y": 666}]},
            {"kind": "text", "role": "caption", "x": 540, "y": 554, "w": 1000, "lines": 2, "font": "BMDOHYEON", "size": 67.5,
             "line_h": 94, "rgb": [0, 0, 0], "valign": "top"}]
    f = {"canvas": [1080, 1920], "frames": [{"id": "body", "span": [1.5, None], "layers": body}, {"id": "hook", "span": [0, 1.5], "layers": hook}]}
    spec = schema.validate(f)
    assert [x["id"] for x in spec["frames"]] == ["hook", "body"]            # 시작 시각 순으로
    assert schema.layers_at(spec, 0.5)[0]["rgb"] == [64, 64, 64] and schema.layers_at(spec, 10.0)[0]["rgb"] == [255, 255, 255]
    v = next(l for l in schema.layers_at(spec, frame_id="body") if l["kind"] == "video")
    assert v["cuts"][0]["x"] is None and v["cuts"][1]["y"] == 666 and v["anchor"] == {"below": "caption", "gap": 18}
    assert text_layer({"layers": schema.layers_at(spec, 10.0)}, "caption")["valign"] == "top"
    scene_style.validate_snapshot(to_snapshot.to_snapshot(f))            # 틀 여러 장도 서버 검사 통과(행은 schema 가 검사)
    bad = copy.deepcopy(f); bad["frames"][0]["span"] = [3, 2]
    with pytest.raises(schema.FrameError):
        schema.validate(bad)


def test_row_lines_cover_caption_in_later_frame():
    """관제 266: 훅 틀(제목)·본문 틀(자막)로 나뉜 설명서 — 편집기 입력칸 힌트(frame.lines)가 첫 틀만 보면 자막 칸이 숨었다
    (제품비하인드썰형·화자 대사 썰형·연예인꿀맛, caption_audit '자막 칸 숨김'). 칸마다 처음 나온 층 하나, 첫 틀 먼저."""
    title = {"kind": "text", "role": "title", "x": 540, "y": 200, "w": 980, "lines": 2, "font": "JalnanGothic", "size": 100, "line_h": 120, "rgb": [255, 255, 255]}
    cap = {"kind": "text", "role": "caption", "x": 540, "y": 554, "w": 1000, "lines": 2, "font": "BMDOHYEON", "size": 67.5, "line_h": 94, "rgb": [0, 0, 0]}
    f = {"canvas": [1080, 1920], "frames": [{"id": "hook", "span": [0, 1.5], "layers": [{"kind": "bg", "rgb": [0, 0, 0]}, title]},
                                             {"id": "body", "span": [1.5, None], "layers": [{"kind": "bg", "rgb": [255, 255, 255]}, dict(title, y=60), cap]}]}
    lines = to_snapshot.build_row(f)["frame"]["lines"]
    assert [l["bind"] for l in lines] == ["hook1", "hook2", "caption"]
    assert lines[0]["y0"] == 200 and lines[1]["y0"] == 320          # 제목 칸은 첫 틀 층(본문 틀의 y=60 제목이 덮지 않는다)
    assert lines[2]["y0"] == 554 and lines[2]["font_family"] == "BMDOHYEON"


def test_line_scale_schema_and_snapshot_font_size():
    """줄마다 크기 배율(line_scale) — 썰풀다 제목 1줄이 2줄보다 크다(10-16). 편집기 줄 힌트 font_size 도 배율대로."""
    f = frame_a()
    t = text_layer(f, "title"); t["line_scale"] = [1.1, 0.9]
    spec = schema.validate(f)
    assert text_layer(spec, "title")["line_scale"] == [1.1, 0.9]
    row = to_snapshot.build_row(spec)
    sizes = [l["font_size"] for l in row["frame"]["lines"] if l["bind"] in ("hook1", "hook2")]
    assert sizes == [round(t["size"] * 1.1, 1), round(t["size"] * 0.9, 1)]
    bad = copy.deepcopy(f); text_layer(bad, "title")["line_scale"] = [5]
    with pytest.raises(schema.FrameError):
        schema.validate(bad)


def test_caption_effects_to_live_snapshot():
    """자막 등장·강조 → 라이브 스냅샷 칸(bodyCaptionMotion·wordFx) — 새 애니메이션 없이 이름만 옮긴다(to_snapshot.caption_effects)."""
    f = frame_a()
    cap = text_layer(f, "caption")
    cap["enter"] = {"kind": "typewriter", "ms": 400}
    cap["emphasis"] = {"words": "auto", "rgb": [255, 230, 0], "style": "grow"}
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(f))
    assert snap["bodyCaptionMotion"] == "typing" and snap["motionPack"] == "off"
    assert snap["wordFx"] == {"style": "color", "color": "#FFE600", "grow": "pop"}
    cap["emphasis"] = {"words": ["구미공장"], "rgb": [255, 45, 111], "style": "color"}
    fx, unsupported = to_snapshot.caption_effects(schema.validate(f))
    assert "wordFx" not in fx and any("낱말 목록" in u for u in unsupported)


@pytest.mark.skipif(not _renderer_ready(), reason="node·puppeteer 없음 — 실제 렌더 불가")
def test_caption_emphasis_words_render_color(tmp_path):
    """낱말 목록 강조: 렌더 레이어에서 그 낱말 자리만 강조색(분홍) — 설명서 모드 자막 색 span(precision20-ui.js specEmph)."""
    f = frame_a()
    cap = text_layer(f, "caption")
    cap["emphasis"] = {"words": ["해외 릴스"], "rgb": [255, 45, 111], "style": "color"}
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(f))
    c = "아니 이거 해외 릴스에서 맨날 보이길래"
    timeline = [{"beat_idx": 0, "t0": 0, "dur": 3, "narration": c, "caption_lines": [c], "role": "hook",
                 "primary": {"video_id": "s0", "start": 0, "end": 3}}]
    png = scene_style.render_layer_one(timeline, snap, tmp_path, 0, {"text": "닿으면 스피커\n소름 돋는 음질 수준"}, "t")
    im = Image.open(png).convert("RGBA"); px = im.load()
    y0, y1 = cap["y"], cap["y"] + cap["line_h"]
    pink = [x for y in range(int(y0), int(y1), 2) for x in range(0, 1080, 2)
            if px[x, y][3] > 200 and abs(px[x, y][0] - 255) < 40 and abs(px[x, y][1] - 45) < 50 and abs(px[x, y][2] - 111) < 50]
    assert len(pink) > 300, len(pink)
    assert 250 < min(pink) and max(pink) < 600, (min(pink), max(pink))   # '해외 릴스' 자리(실측 311~539)만
