"""틀 설명서 frame.json — 형식 문서 + 검사 함수 validate(frame).

설계: docs/superpowers/specs/2026-10-15-칼카피엔진-design.md §5(frame.json) · §6-3(라이브 렌더러 설명서 모드)
판단의 주인: "이 설명서가 유효한가 / 값이 무엇으로 정규화되는가"는 이 파일의 validate() 하나다.
그리는 쪽(out/precision20-ui.js renderSpec)은 여기서 정규화된 값만 받는다 — 기본값을 그쪽에서 다시 정하지 않는다.

형식 (좌표는 전부 캔버스 픽셀, 원점 왼쪽 위):

    {"canvas": [1080, 1920],
     "layers": [                       # 아래에서 위로 그리는 순서. 최대 12개(서버 스냅샷 검사의 목록 상한과 같다)
       {"kind": "bg", "rgb": [245,245,245]},                        # 화면 바탕(영상 창 밖 전부). 한 장만
       {"kind": "video", "x":0, "y":420, "w":1080, "h":1010, "radius":0},   # 영상 창 — 렌더 합성이 이 자리에 영상을 둔다. 0~1장
       {"kind": "band", "x":0, "y":0, "w":1080, "h":110, "rgb":[0,0,0], "radius":0},  # 색 띠·상자
       {"kind": "text", "role": "title", "x":540, "y":230, "w":980, "align":"center", "lines":2,
        "font":"GmarketSansBold", "size":92, "line_h":95, "rgb":[0,0,0],
        "line_rgb":[[0,0,0],[255,45,111]],          # 줄마다 색(없으면 null → 모든 줄 rgb)
        "outline":{"px":0,"rgb":[0,0,0]},           # 외곽선(없으면 null, px 0 도 '없음'으로 유효)
        "shadow":{"dx":0,"dy":4,"blur":6,"rgb":[0,0,0]},   # 그림자(없으면 null)
        "box":{"rgb":[255,255,255],"pad":12,"radius":8},   # 글자 상자(없으면 null)
        "italic": false, "letter_spacing": 0,       # 자간 px(0·음수 유효)
        "enter":{"kind":"pop","ms":300}},           # 등장 효과(없으면 null)
       {"kind": "text", "role": "caption", ...},   # 자막 — 글은 장면마다 대본 자막이 들어간다
       {"kind": "text", "role": "brand", "text": "[광고]", ...},   # 고정 문구 — text 필수
       {"kind": "image", "src": "...", "x":..., "y":..., "w":..., "h":...}
     ],
     "template_off": {"tail_sec": 3.5},   # 틀을 끄는 장면(없으면 null) — 아래 설명
     "made_by": "calcopy_frame v1", "source": "ZdeZRtCeAC4"}

틀 끄기(template_off): 그 장면은 바탕·띠·글자를 하나도 안 그리고 영상이 화면 전체가 된다(원본 끝 3.5초처럼).
  tail_sec = 영상 끝에서 이 초 안에 **시작하는** 장면(끝 경계에 걸친 장면은 켠 채 둔다). 0 = 끄는 장면 없음.
  scenes   = 장면 번호 목록(장면꾸미기 장면 = 자막 단위, 0부터). 둘 다 주면 어느 하나에 걸리면 끈다.
  어느 장면이 꺼지나의 판단은 out/precision20-ui.js specOffAt 한 곳(편집 화면·렌더·썸네일·캡컷이 같은 함수).

글자 층의 자리: role=title·caption 의 x·align 은 가로 기준(center=가운데 x, left=왼쪽 끝, right=오른쪽 끝),
y 는 첫 줄 칸의 위 끝, 줄 칸 높이 = line_h(없으면 size×1.15 반올림). 줄 n 의 칸 = [y + n·line_h, y + (n+1)·line_h).
글자가 w 보다 길면 그리는 쪽이 w 안에 들어가게 줄인다(넘쳐서 잘리는 일은 없다).

★0 은 유효한 값이다(0은 falsy 함정 — 메모리 reference_0은falsy_기본값으로튄다). 값이 '없다'는 키가 없거나 null 일 때만이다.
"""
from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAX_LAYERS = 12                     # scene_style.validate_snapshot walk() 의 목록 상한과 같다(그 상한이 주인)
KINDS = ("bg", "video", "band", "text", "image")
ROLES = ("title", "caption", "brand", "label")
ALIGNS = ("left", "center", "right")
ENTER_KINDS = ("pop", "slide", "flash")   # 제목 등장 — precision20-ui.js runHookMotion 이 그리는 것만
MADE_BY = "calcopy_frame v1"


@lru_cache(maxsize=1)
def font_families() -> frozenset:
    """그릴 수 있는 글꼴 이름 = 장면꾸미기 화면(out/scene-style-ui-showcase.html)에 @font-face 로 등록된 이름.
    여기 없는 이름을 받으면 브라우저가 조용히 다른 글꼴로 그린다 — 그래서 받지 않는다."""
    html = (ROOT / "out" / "scene-style-ui-showcase.html").read_text(encoding="utf-8")
    return frozenset(re.findall(r'@font-face\s*\{[^}]*?font-family:\s*"?([A-Za-z0-9_-]+)"?', html))


class FrameError(ValueError):
    """설명서가 형식에 맞지 않는다 — 메시지에 어느 층의 어느 값인지 적는다."""


def _num(v, where, lo=-10000, hi=10000, integer=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
        raise FrameError(f"{where}: {lo}~{hi} 사이 숫자여야 합니다 (받은 값 {v!r})")
    if integer and int(v) != v:
        raise FrameError(f"{where}: 정수여야 합니다 (받은 값 {v!r})")
    return int(v) if integer else (int(v) if float(v).is_integer() else float(v))


def _rgb(v, where):
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise FrameError(f"{where}: [r,g,b] 세 숫자여야 합니다 (받은 값 {v!r})")
    return [_num(c, f"{where}[{i}]", 0, 255, integer=True) for i, c in enumerate(v)]


def _opt(layer, key):
    """키가 없거나 null 이면 None(=없음). 0·빈 목록은 그대로 돌려준다."""
    return layer.get(key) if key in layer else None


def _rect(layer, where, W, H):
    x = _num(layer.get("x"), where + ".x", -W, W)
    y = _num(layer.get("y"), where + ".y", -H, H)
    w = _num(layer.get("w"), where + ".w", 1, 2 * W)
    h = _num(layer.get("h"), where + ".h", 1, 2 * H)
    return {"x": x, "y": y, "w": w, "h": h}


def _text(layer, where, W, H):
    role = layer.get("role")
    if role not in ROLES:
        raise FrameError(f"{where}.role: {ROLES} 중 하나여야 합니다 (받은 값 {role!r})")
    out = {"kind": "text", "role": role}
    out["x"] = _num(layer.get("x"), where + ".x", -W, 2 * W)
    out["y"] = _num(layer.get("y"), where + ".y", -H, 2 * H)
    out["w"] = _num(layer.get("w"), where + ".w", 1, 2 * W)
    align = layer.get("align", "center")
    if align not in ALIGNS:
        raise FrameError(f"{where}.align: {ALIGNS} 중 하나여야 합니다")
    out["align"] = align
    out["lines"] = _num(layer.get("lines", 1), where + ".lines", 1, 4, integer=True)
    font = layer.get("font")
    if not isinstance(font, str) or font not in font_families():
        raise FrameError(f"{where}.font: 장면꾸미기 화면에 등록된 글꼴이 아닙니다 ({font!r}) — "
                         "등록 목록은 schema.font_families()")
    out["font"] = font
    out["size"] = _num(layer.get("size"), where + ".size", 4, 600)
    line_h = _opt(layer, "line_h")
    out["line_h"] = round(out["size"] * 1.15) if line_h is None else _num(line_h, where + ".line_h", 4, 900)
    out["rgb"] = _rgb(layer.get("rgb"), where + ".rgb")
    line_rgb = _opt(layer, "line_rgb")
    if line_rgb is not None:
        if not isinstance(line_rgb, list) or not 1 <= len(line_rgb) <= 4:
            raise FrameError(f"{where}.line_rgb: 줄마다 [r,g,b] 목록(1~4개)이거나 null 이어야 합니다")
        line_rgb = [_rgb(c, f"{where}.line_rgb[{i}]") for i, c in enumerate(line_rgb)]
    out["line_rgb"] = line_rgb
    outline = _opt(layer, "outline")
    if outline is not None:
        if not isinstance(outline, dict):
            raise FrameError(f"{where}.outline: {{px,rgb}} 이거나 null 이어야 합니다")
        outline = {"px": _num(outline.get("px"), where + ".outline.px", 0, 60), "rgb": _rgb(outline.get("rgb"), where + ".outline.rgb")}
    out["outline"] = outline
    shadow = _opt(layer, "shadow")
    if shadow is not None:
        if not isinstance(shadow, dict):
            raise FrameError(f"{where}.shadow: {{dx,dy,blur,rgb}} 이거나 null 이어야 합니다")
        shadow = {"dx": _num(shadow.get("dx", 0), where + ".shadow.dx", -100, 100),
                  "dy": _num(shadow.get("dy", 0), where + ".shadow.dy", -100, 100),
                  "blur": _num(shadow.get("blur", 0), where + ".shadow.blur", 0, 200),
                  "rgb": _rgb(shadow.get("rgb"), where + ".shadow.rgb")}
    out["shadow"] = shadow
    box = _opt(layer, "box")
    if box is not None:
        if not isinstance(box, dict):
            raise FrameError(f"{where}.box: {{rgb,pad,radius}} 이거나 null 이어야 합니다")
        box = {"rgb": _rgb(box.get("rgb"), where + ".box.rgb"), "pad": _num(box.get("pad", 0), where + ".box.pad", 0, 300),
               "radius": _num(box.get("radius", 0), where + ".box.radius", 0, 500)}
    out["box"] = box
    italic = layer.get("italic", False)
    if not isinstance(italic, bool):
        raise FrameError(f"{where}.italic: 참/거짓이어야 합니다")
    out["italic"] = italic
    out["letter_spacing"] = _num(layer.get("letter_spacing", 0), where + ".letter_spacing", -100, 200)
    enter = _opt(layer, "enter")
    if enter is not None:
        if not isinstance(enter, dict) or enter.get("kind") not in ENTER_KINDS:
            raise FrameError(f"{where}.enter.kind: {ENTER_KINDS} 중 하나이거나 enter 가 null 이어야 합니다")
        enter = {"kind": enter["kind"], "ms": _num(enter.get("ms", 300), where + ".enter.ms", 0, 5000)}
        if role != "title":
            raise FrameError(f"{where}.enter: v1 은 제목(title) 등장만 그립니다 — 자막 등장은 아직 없음")
    out["enter"] = enter
    text = _opt(layer, "text")
    if role in ("brand", "label"):
        if not isinstance(text, str) or not text.strip() or len(text) > 80:
            raise FrameError(f"{where}.text: {role} 층은 1~80자 고정 문구가 필요합니다")
    elif text is not None and (not isinstance(text, str) or len(text) > 200):
        raise FrameError(f"{where}.text: 200자 이하 글이거나 null 이어야 합니다")
    out["text"] = text
    return out


def validate(frame) -> dict:
    """설명서 한 장을 검사하고 정규화한 사본을 돌려준다(원본은 건드리지 않는다). 형식이 틀리면 FrameError."""
    if not isinstance(frame, dict):
        raise FrameError("설명서는 객체(dict)여야 합니다")
    canvas = frame.get("canvas")
    if not isinstance(canvas, (list, tuple)) or len(canvas) != 2:
        raise FrameError("canvas: [가로, 세로] 여야 합니다")
    W = _num(canvas[0], "canvas[0]", 100, 4000, integer=True)
    H = _num(canvas[1], "canvas[1]", 100, 4000, integer=True)
    layers = frame.get("layers")
    if not isinstance(layers, list) or not 1 <= len(layers) <= MAX_LAYERS:
        raise FrameError(f"layers: 1~{MAX_LAYERS}개 목록이어야 합니다")
    out, count = [], {}
    for i, layer in enumerate(layers):
        where = f"layers[{i}]"
        if not isinstance(layer, dict) or layer.get("kind") not in KINDS:
            raise FrameError(f"{where}.kind: {KINDS} 중 하나여야 합니다")
        kind = layer["kind"]
        if kind == "bg":
            if "src" in layer and layer["src"] is not None:
                raise FrameError(f"{where}: v1 바탕은 단색(rgb)만 그립니다 — 사진·흐림 바탕은 아직 없음")
            item = {"kind": "bg", "rgb": _rgb(layer.get("rgb"), where + ".rgb")}
        elif kind == "video":
            item = {"kind": "video", **_rect(layer, where, W, H),
                    "radius": _num(layer.get("radius", 0), where + ".radius", 0, 500)}
        elif kind == "band":
            item = {"kind": "band", **_rect(layer, where, W, H), "rgb": _rgb(layer.get("rgb"), where + ".rgb"),
                    "radius": _num(layer.get("radius", 0), where + ".radius", 0, 500)}
        elif kind == "image":
            src = layer.get("src")
            if not isinstance(src, str) or not re.fullmatch(r"[^\s\"'<>()\\]{1,300}", src):
                raise FrameError(f"{where}.src: 따옴표·괄호·공백 없는 경로여야 합니다")
            item = {"kind": "image", "src": src, **_rect(layer, where, W, H)}
        else:
            item = _text(layer, where, W, H)
        key = item.get("role", kind)
        count[key] = count.get(key, 0) + 1
        out.append(item)
    for single in ("bg", "video", "title", "caption"):
        if count.get(single, 0) > 1:
            raise FrameError(f"{single} 층은 한 장만 둘 수 있습니다 (받은 수 {count[single]})")
    off = frame.get("template_off")
    if off is not None:
        if not isinstance(off, dict) or set(off) - {"tail_sec", "scenes"}:
            raise FrameError("template_off: {tail_sec, scenes} 이거나 null 이어야 합니다")
        tail = off.get("tail_sec")
        scenes = off.get("scenes")
        if scenes is not None:
            if not isinstance(scenes, list) or len(scenes) > MAX_LAYERS:
                raise FrameError(f"template_off.scenes: 장면 번호 목록(최대 {MAX_LAYERS}개)이거나 null 이어야 합니다")
            scenes = sorted({_num(n, f"template_off.scenes[{i}]", 0, 9999, integer=True) for i, n in enumerate(scenes)})
        off = {"tail_sec": None if tail is None else _num(tail, "template_off.tail_sec", 0, 600), "scenes": scenes}
    source = frame.get("source")
    if source is not None and (not isinstance(source, str) or len(source) > 200):
        raise FrameError("source: 200자 이하 글이거나 null 이어야 합니다")
    return {"canvas": [W, H], "layers": out, "template_off": off, "made_by": MADE_BY, "source": source}


def canonical(frame: dict) -> str:
    """정규화된 설명서의 한 줄 표기 — 같은 틀이면 같은 문자열(틀 번호 custom_<hash> 의 재료)."""
    return json.dumps(frame, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
