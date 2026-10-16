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
       #   선택: "grad_x":[[0,[156,156,156]],[0.5,[242,242,242]],[1,[170,170,170]]] — 가로 색 변화(자리 0~1, 2~12개, rgb 대신 칠함)
       #         "fade":[위px, 아래px] — 위·아래 끝에서 이만큼 바탕으로 흐려짐(훅 회색 띠처럼 가장자리가 번진 띠)
       {"kind": "text", "role": "title", "x":540, "y":230, "w":980, "align":"center", "lines":2,
        "font":"GmarketSansBold", "size":92, "line_h":95, "rgb":[0,0,0],
        "line_rgb":[[0,0,0],[255,45,111]],          # 줄마다 색(없으면 null → 모든 줄 rgb)
        "line_scale":[1.07,0.93],                   # 줄마다 크기 배율(size × 배율, 없으면 null → 모든 줄 size)
        "outline":{"px":0,"rgb":[0,0,0]},           # 외곽선(없으면 null, px 0 도 '없음'으로 유효)
        "line_outline":[null,[6,255,255,255]],      # 줄마다 외곽선 [px,r,g,b]|null(없으면 null = 모든 줄 outline)
        "shadow":{"dx":0,"dy":4,"blur":6,"rgb":[0,0,0]},   # 그림자(없으면 null)
        "box":{"rgb":[255,255,255],"pad":12,"radius":8},   # 글자 상자(없으면 null)
        "italic": false, "letter_spacing": 0,       # 자간 px(0·음수 유효) — 글자마다(공백 포함) 뒤에 붙는다(CSS)
        "valign": "center",                         # 여러 줄 칸 안 세로 자리: center | top(누적형 자막 — 1줄일 때도 첫 줄 자리)
        "word_spacing": 0,                          # 낱말 간격 px — 공백마다 더한다(CSS word-spacing). 자간이 음수면 공백이 같이 줄어 낱말이 붙는다
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
MAX_FRAMES = 4                      # 틀 여러 장(frames) 상한
MAX_CUTS = 200                      # 영상 창 컷별 자리(video.cuts) 상한
MAX_LAYERS = 16                     # 틀 한 장의 층 수. validate_snapshot 은 customFrame 을 walk 에서 빼고 check_row(이 schema)로 검사한다
#   (게시글형 본문: 바탕·창·띠 3·글 7·자막 = 13 — 12 상한에 자막이 잘려 나갔다, 2026-10-16)
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
    line_scale = _opt(layer, "line_scale")
    if line_scale is not None:
        # 줄마다 글자 크기 배율(size × 배율) — 썰풀다 제목은 1줄이 2줄보다 크다(ho5 109/95·7DY 128/87·1_V 103/93, 10-16 실측).
        #   한 크기로 평균 내면 1줄은 작고 얇게, 2줄은 크게 나왔다(LOO 획·높이 결함의 뿌리)
        if not isinstance(line_scale, list) or not 1 <= len(line_scale) <= 4:
            raise FrameError(f"{where}.line_scale: 줄마다 배율 목록(1~4개)이거나 null 이어야 합니다")
        line_scale = [_num(v, f"{where}.line_scale[{i}]", 0.3, 3) for i, v in enumerate(line_scale)]
    out["line_scale"] = line_scale
    outline = _opt(layer, "outline")
    if outline is not None:
        if not isinstance(outline, dict):
            raise FrameError(f"{where}.outline: {{px,rgb}} 이거나 null 이어야 합니다")
        outline = {"px": _num(outline.get("px"), where + ".outline.px", 0, 60), "rgb": _rgb(outline.get("rgb"), where + ".outline.rgb")}
    out["outline"] = outline
    lo = _opt(layer, "line_outline")
    if lo is not None:
        # 줄마다 외곽선 — 각 줄 [px, r, g, b] 또는 null(그 줄은 외곽선 없음). 있으면 그 줄은 outline 대신 이것.
        #   {px,rgb} 모양이 아니라 납작한 [px,r,g,b] 인 까닭: 서버 스냅샷 검사(walk)의 깊이 상한 8 안에 들어가야 한다.
        if not isinstance(lo, list) or not 1 <= len(lo) <= 4:
            raise FrameError(f"{where}.line_outline: 줄마다 [px,r,g,b]|null 목록(1~4개)이거나 null 이어야 합니다")
        norm = []
        for i, item in enumerate(lo):
            if item is None:
                norm.append(None); continue
            if isinstance(item, dict):      # {px,rgb} 로 써도 받는다
                item = [item.get("px"), *(item.get("rgb") or [None] * 3)]
            if not isinstance(item, list) or len(item) != 4:
                raise FrameError(f"{where}.line_outline[{i}]: [px,r,g,b] 또는 null 이어야 합니다")
            norm.append([_num(item[0], f"{where}.line_outline[{i}].px", 0, 60), *_rgb(item[1:], f"{where}.line_outline[{i}].rgb")])
        lo = norm
    out["line_outline"] = lo
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
    out["word_spacing"] = _num(layer.get("word_spacing", 0), where + ".word_spacing", -100, 200)
    valign = layer.get("valign", "center")
    if valign not in ("center", "top"):
        raise FrameError(f"{where}.valign: center|top 이어야 합니다")
    out["valign"] = valign      # top = 여러 줄 칸에서 글을 위에서부터(누적형 자막: 1줄일 때도 첫 줄 자리)
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


def _video_cuts(layer, where, W, H):
    """영상 창의 컷별 자리(가변 그림 칸) — cuts: [{t:[시작,끝], w, h, x?, y?}] (x 없으면 가운데, y 없으면 아래 anchor 또는 층 y).
    anchor: {"below": "caption", "gap": px} 면 창 위 끝 = 그 장면 자막 줄 수 × 줄높이 아래 + gap(자막이 1→2줄로 늘면 그림이 내려간다).
    둘 다 없으면 null — 창은 x·y·w·h 그대로."""
    cuts = layer.get("cuts")
    if cuts is not None:
        if not isinstance(cuts, list) or not 1 <= len(cuts) <= MAX_CUTS:
            raise FrameError(f"{where}.cuts: 1~{MAX_CUTS}개 목록이거나 null 이어야 합니다")
        norm = []
        for i, c in enumerate(cuts):
            wc = f"{where}.cuts[{i}]"
            if not isinstance(c, dict) or not isinstance(c.get("t"), list) or len(c["t"]) != 2:
                raise FrameError(f"{wc}: {{t:[시작,끝], w, h, x?}} 이어야 합니다")
            a, b = _num(c["t"][0], wc + ".t[0]", 0, 3600), _num(c["t"][1], wc + ".t[1]", 0, 3600)
            if b <= a:
                raise FrameError(f"{wc}.t: 끝이 시작보다 뒤여야 합니다")
            item = {"t": [a, b], "w": _num(c.get("w"), wc + ".w", 1, W), "h": _num(c.get("h"), wc + ".h", 1, H),
                    "x": None if c.get("x") is None else _num(c["x"], wc + ".x", -W, W),
                    "y": None if c.get("y") is None else _num(c["y"], wc + ".y", -H, H)}   # y 없으면 anchor(자막 아래) 또는 층 y
            norm.append(item)
        cuts = norm
    anchor = layer.get("anchor")
    if anchor is not None:
        if not isinstance(anchor, dict) or anchor.get("below") != "caption":
            raise FrameError(f"{where}.anchor: {{below: 'caption', gap}} 이거나 null 이어야 합니다")
        anchor = {"below": "caption", "gap": _num(anchor.get("gap", 0), where + ".anchor.gap", -500, 500)}
    return cuts, anchor


def _layers(layers, W, H, where0: str) -> list:
    if not isinstance(layers, list) or not 1 <= len(layers) <= MAX_LAYERS:
        raise FrameError(f"{where0}: 1~{MAX_LAYERS}개 목록이어야 합니다")
    out, count = [], {}
    for i, layer in enumerate(layers):
        where = f"{where0}[{i}]"
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
            item["cuts"], item["anchor"] = _video_cuts(layer, where, W, H)
        elif kind == "band":
            item = {"kind": "band", **_rect(layer, where, W, H), "rgb": _rgb(layer.get("rgb"), where + ".rgb"),
                    "radius": _num(layer.get("radius", 0), where + ".radius", 0, 500)}
            gx = _opt(layer, "grad_x")
            if gx is not None:
                if not isinstance(gx, list) or not 2 <= len(gx) <= 12:
                    raise FrameError(f"{where}.grad_x: [[자리 0~1, [r,g,b]], ...] 2~12개여야 합니다")
                stops = []
                for i, st_ in enumerate(gx):
                    if not isinstance(st_, (list, tuple)) or len(st_) != 2:
                        raise FrameError(f"{where}.grad_x[{i}]: [자리, [r,g,b]] 여야 합니다")
                    stops.append([_num(st_[0], f"{where}.grad_x[{i}][0]", 0, 1), _rgb(st_[1], f"{where}.grad_x[{i}][1]")])
                if any(b[0] < a[0] for a, b in zip(stops, stops[1:])):
                    raise FrameError(f"{where}.grad_x: 자리가 커지는 순서여야 합니다")
                item["grad_x"] = stops
            fd = _opt(layer, "fade")
            if fd is not None:
                if not isinstance(fd, (list, tuple)) or len(fd) != 2:
                    raise FrameError(f"{where}.fade: [위px, 아래px] 여야 합니다")
                top, bot = (_num(v, f"{where}.fade[{i}]", 0, item["h"]) for i, v in enumerate(fd))
                if top + bot > item["h"]:
                    raise FrameError(f"{where}.fade: 위+아래({top}+{bot})가 띠 높이 {item['h']} 를 넘습니다")
                item["fade"] = [top, bot]
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
    frames = frame.get("frames")
    if frames is not None:
        # 틀 여러 장 + 시간축(구간마다 다른 틀 — 예: 훅 카드 0~1.5초 / 본문 게시글). template_off 의 일반화.
        if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
            raise FrameError(f"frames: 1~{MAX_FRAMES}개 목록이어야 합니다")
        fo, ids = [], set()
        for k, fr in enumerate(frames):
            wk = f"frames[{k}]"
            if not isinstance(fr, dict) or not isinstance(fr.get("id"), str) or not re.fullmatch(r"[A-Za-z0-9_가-힣-]{1,20}", fr["id"]):
                raise FrameError(f"{wk}.id: 1~20자 이름이어야 합니다")
            if fr["id"] in ids:
                raise FrameError(f"{wk}.id: 이름이 겹칩니다({fr['id']})")
            ids.add(fr["id"])
            sp = fr.get("span")
            if not isinstance(sp, list) or len(sp) != 2:
                raise FrameError(f"{wk}.span: [시작초, 끝초|null] 이어야 합니다")
            a = _num(sp[0], wk + ".span[0]", 0, 3600)
            b = None if sp[1] is None else _num(sp[1], wk + ".span[1]", 0, 3600)
            if b is not None and b <= a:
                raise FrameError(f"{wk}.span: 끝이 시작보다 뒤여야 합니다")
            fo.append({"id": fr["id"], "span": [a, b], "layers": _layers(fr.get("layers"), W, H, wk + ".layers")})
        fo.sort(key=lambda f: f["span"][0])
        body = {"frames": fo}
    else:
        body = {"layers": _layers(frame.get("layers"), W, H, "layers")}
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
    return {"canvas": [W, H], **body, "template_off": off, "made_by": MADE_BY, "source": source}


def layers_at(spec: dict, t: float | None = None, frame_id: str | None = None) -> list:
    """정규화된 설명서의 층 목록 — 틀 여러 장이면 frame_id 또는 시각 t 가 속한 틀(없으면 첫 틀). 그리는 쪽 specLayers 와 같은 규칙."""
    if "frames" not in spec:
        return spec["layers"]
    if frame_id is not None:
        return next(f["layers"] for f in spec["frames"] if f["id"] == frame_id)
    if t is not None:
        for f in spec["frames"]:
            a, b = f["span"]
            if a <= t and (b is None or t < b):
                return f["layers"]
    return spec["frames"][0]["layers"]


def all_layers(spec: dict) -> list:
    return [l for f in spec["frames"] for l in f["layers"]] if "frames" in spec else spec["layers"]


def canonical(frame: dict) -> str:
    """정규화된 설명서의 한 줄 표기 — 같은 틀이면 같은 문자열(틀 번호 custom_<hash> 의 재료)."""
    return json.dumps(frame, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
