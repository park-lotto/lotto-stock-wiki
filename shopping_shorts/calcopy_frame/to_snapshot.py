"""틀 설명서(frame.json) → 라이브 장면꾸미기 스냅샷.

방식(코드를 읽고 고른 것 — 보고서 근거):
  - 라이브 렌더러(out/precision20-ui.js)는 `fixedRows = window.CONTINUOUS20` **배열 참조**를 쓰고, `load(context, saved)`가
    `rows.findIndex(p => p.id === saved.presetId)` 로 틀을 고른다. 그래서 데이터 파일(continuous20-data.js)에 행을 영구로
    추가하지 않아도, load 가 저장본에 실린 행(customFrame)을 그 배열에 넣으면 같은 길로 그려진다.
  - 행을 **스냅샷에 실어** 보내므로 작업마다 틀이 함께 저장된다(편집기 재열기·렌더·캡컷·썸네일이 같은 저장본을 읽는다).
    데이터 파일에 행을 추가하는 방식은 틀마다 배포가 필요하고 고객 목록에 노출된다 — 그래서 고르지 않았다.
  - 서버(scene_style.validate_snapshot)는 실려 온 행을 믿지 않고 **행 안의 설명서(spec)로 행을 다시 만든다**(build_row).
    행 모양을 정하는 곳은 build_row 하나다.

틀 번호: custom_<정규화된 설명서 sha1 앞 12자리> — 같은 설명서면 같은 번호(장면별 자막 저장 키가 번호를 쓴다).
"""
from __future__ import annotations

import hashlib

from . import schema
from .. import scene_style

BLANK_IMAGE = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"   # 1×1 투명 — 고정형 미리보기 그림 자리
POP_BASE_MS = 520      # precision20-ui.js runHookMotion 'pop' 의 기본 길이(ms) — 등장 ms 를 hookMotionSpeed 로 바꾸는 기준
SLIDE_BASE_MS = 620
FLASH_BASE_MS = 480
_ENTER_BASE = {"pop": POP_BASE_MS, "slide": SLIDE_BASE_MS, "flash": FLASH_BASE_MS}
# 자막 등장 → 라이브 CAPTION_MOTIONS 키(shopping_shorts/static/caption-motions.js) — 새 애니메이션 코드 없이 이름만 옮긴다.
#   길이(ms)는 라이브 효과의 길이를 쓴다(설명서 ms 는 옮기지 못함 → unsupported 에 남김)
CAPTION_ENTER_LIVE = {"pop": "pop", "fade": "fade", "rise": "rise", "typewriter": "typing", "none": ""}
EMPH_LIVE = {"color": ("color", ""), "underline": ("underline", ""), "grow": ("color", "pop")}   # words 'auto' → wordFx(style, grow)


def caption_effects(spec: dict) -> tuple[dict, list]:
    """설명서 자막 층의 등장·강조 → (스냅샷 칸, 못 옮긴 것 목록). 판단 주인 한 곳."""
    cap = next((l for l in schema.all_layers(spec) if l["kind"] == "text" and l["role"] == "caption"), None)
    snap, unsupported = {}, []
    if not cap:
        return snap, unsupported
    if cap.get("enter"):
        snap["bodyCaptionMotion"] = CAPTION_ENTER_LIVE[cap["enter"]["kind"]]
        live = scene_style.clean_caption_enter({**cap["enter"], "kind": snap["bodyCaptionMotion"] or None})   # 길이·키프레임까지 — 모양 주인은 clean_caption_enter
        if live:
            snap["captionEnter"] = live
        if cap["enter"]["kind"] != "none" and not live:
            unsupported.append(f"자막 등장 길이 {cap['enter']['ms']}ms — 라이브 '{snap['bodyCaptionMotion']}' 효과 길이를 쓴다")
    e = cap.get("emphasis")
    if e and e["words"] == "auto":
        style, grow = EMPH_LIVE[e["style"]]
        snap["wordFx"] = {"style": style, "color": "#%02X%02X%02X" % tuple(e["rgb"]), "grow": grow}
    elif e:
        unsupported.append("낱말 목록 강조 — 라이브 wordFx 에 없는 꼴: 설명서 모드 자막에만 색 span 으로 그린다(편집기 단어 강조 단추와 무관)")
    return snap, unsupported
ID_RE = r"custom_[0-9a-f]{12}"


def _hex(rgb):
    return "#%02X%02X%02X" % tuple(rgb)


def frame_id(spec: dict) -> str:
    return "custom_" + hashlib.sha1(schema.canonical(spec).encode("utf-8")).hexdigest()[:12]


def _text_box(layer, n):
    """글자 층 n번째 줄 칸의 [x0, x1, y0, y1] — 그리는 쪽(renderSpec)과 같은 규칙(schema 문서)."""
    x, w = layer["x"], layer["w"]
    x0 = x - w / 2 if layer["align"] == "center" else (x if layer["align"] == "left" else x - w)
    y0 = layer["y"] + n * layer["line_h"]
    return x0, x0 + w, y0, y0 + layer["line_h"]


def build_row(frame) -> dict:
    """설명서 → 고정형(continuous) 행. 행 모양의 주인.
    frame.spec = 정규화된 설명서(그리는 쪽이 읽는 값). frame.lines = 편집기 입력칸 힌트(제목 1·2·자막 칸을 보이게)."""
    spec = schema.validate(frame)
    W, H = spec["canvas"]
    rid = frame_id(spec)
    lines, sample = [], {"channel": "숏템메이커", "hook1": "", "hook2": "", "bodyTitle": "", "caption": ""}
    first = schema.layers_at(spec)          # 틀 여러 장이면 첫 틀(영상 시작용)
    video = next((l for l in first if l["kind"] == "video"), None)
    # 입력칸 힌트 = 틀 전체(첫 틀 먼저, 칸마다 처음 나온 층) — 첫 틀만 보면 훅 틀 뒤 본문 틀에만 있는 자막 칸이 편집기에서 숨었다
    #   (관제 266 caption_audit 10-26: 제품비하인드썰형·화자 대사 썰형·연예인꿀맛 '자막 칸 숨김'). 편집기 frameKeys 는 이 lines 의 bind 만 본다.
    seen = set()
    for layer in first + [l for l in schema.all_layers(spec) if not any(l is f for f in first)]:
        if layer["kind"] != "text" or layer["role"] not in ("title", "caption"):
            continue
        binds = ["hook1", "hook2"][:layer["lines"]] if layer["role"] == "title" else ["caption"]
        texts = (layer["text"] or "").split("\n")
        for n, bind in enumerate(binds):
            if bind in seen:
                continue
            seen.add(bind)
            x0, x1, y0, y1 = _text_box(layer, n)
            color = (layer["line_rgb"][n] if layer["line_rgb"] and n < len(layer["line_rgb"]) else layer["rgb"])
            lines.append({"bind": bind, "x0": x0, "x1": x1, "y0": y0, "y1": y1, "h": y1 - y0,
                          "font_family": layer["font"],
                          "font_size": round(layer["size"] * ((layer.get("line_scale") or [])[n] if n < len(layer.get("line_scale") or []) else 1), 1),
                          "font_weight": 400,
                          "color": _hex(color), "no_patch": True, "max_lines": 1})
            if layer["role"] == "title" and n < len(texts):
                sample[bind] = texts[n]
    return {"id": rid, "mode": "continuous", "name": "칼카피 틀 " + (spec["source"] or rid[7:]), "views": 0,
            "source_id": rid, "frame_image": BLANK_IMAGE, "thumbnail_image": BLANK_IMAGE, "sample": sample,
            "frame": {"width": W, "height": H, "design_label": "칼카피 설명서", "spec": spec, "lines": lines,
                      "video_from": {"y": video["y"] if video else 0, "pct": round((video["y"] if video else 0) / H * 100, 1)}}}


def check_row(row) -> dict:
    """스냅샷에 실려 온 행을 믿지 않고 행 안의 설명서로 다시 만든다(scene_style.validate_snapshot 이 부른다)."""
    spec = ((row or {}).get("frame") or {}).get("spec") if isinstance(row, dict) else None
    if not isinstance(spec, dict):
        raise schema.FrameError("customFrame 에 설명서(frame.spec)가 없습니다")
    rebuilt = build_row(spec)
    if row.get("id") != rebuilt["id"]:
        raise schema.FrameError("customFrame 번호가 설명서와 맞지 않습니다")
    return rebuilt


def to_snapshot(frame, text: dict | None = None) -> dict:
    """설명서 → 라이브 렌더러 스냅샷(scene_style.validate_snapshot 을 통과하는 모양).
    text: 작업의 제목 문구 등({"hook1": .., "hook2": ..}) — 비우면 작업 제목(context.text)을 그대로 쓴다."""
    if frame.get("shortem_template"):                     # 고객이 숏템메이커 템플릿(썰20·고정20)을 고른 편(관제 234 5판)
        return template_snapshot(frame, frame["shortem_template"], text)
    row = build_row(frame)
    title = next((l for l in schema.all_layers(row["frame"]["spec"]) if l["kind"] == "text" and l["role"] == "title"), None)
    enter = title and title["enter"]
    snap = {"version": 1, "mode": "continuous", "presetId": row["id"], "customFrame": row, "sceneIndex": 0, "frameKind": "frame",
            # 제목 등장: 설명서에 없으면 'none'(라이브 기본 'zoom-punch' 카메라 확대를 물려받지 않는다)
            "hookMotion": enter["kind"] if enter else "none", "motionPack": "off"}
    if enter:
        snap["hookMotionSpeed"] = round(min(2.0, max(0.5, enter["ms"] / _ENTER_BASE[enter["kind"]])), 3)
    snap.update(caption_effects(row["frame"]["spec"])[0])
    if text:
        snap["text"] = {k: str(v) for k, v in text.items() if k in ("channel", "hook1", "hook2", "bodyTitle")}
    return snap


TEMPLATE_MODES = {"story": "precision20-data.js", "continuous": "continuous20-data.js"}


def template_rows(mode: str) -> list:
    """숏템메이커 템플릿 행(라이브 데이터 파일 out/precision20-data.js·continuous20-data.js) — 판단 주인은 그 데이터 파일.
    '원본 영상 그대로'(plain)와 칼카피 틀 행(custom_)은 템플릿이 아니라 뺀다."""
    import json
    from pathlib import Path
    raw = (Path(__file__).resolve().parents[2] / "out" / TEMPLATE_MODES[mode]).read_text(encoding="utf-8-sig").strip()
    rows = json.loads(raw.split("=", 1)[1].rstrip(";\r\n "))
    return [r for r in rows if r["id"] != "plain" and not r["id"].startswith("custom_")]


def template_snapshot(frame, tpl: dict, text: dict | None = None) -> dict:
    """프리셋 틀 대신 숏템메이커 템플릿 한 장으로 그린다. 자막 등장·강조는 프리셋(틀 설명서)이 정한 것을 그대로 옮긴다
    (바꾼 칸만 바뀐다 — 사장님 10-19). 영상 칸 자리는 템플릿이 정한다(렌더러 geometry → compose)."""
    mode, tid = tpl.get("mode"), tpl.get("id")
    if mode not in TEMPLATE_MODES or tid not in {r["id"] for r in template_rows(mode)}:
        raise schema.FrameError(f"모르는 템플릿: {mode}/{tid}")
    snap = {"version": 1, "mode": mode, "presetId": tid, "sceneIndex": 0, "motionPack": "off"}
    snap.update(caption_effects(schema.validate(frame))[0])
    snap["text"] = {"channel": str(tpl.get("channel") or "")}             # 템플릿 기본 채널명('숏템메이커')이 찍히지 않게 — 10-19 렌더 실측
    if tpl.get("ad"):                                                      # 프리셋의 [광고] 표시는 템플릿에서도 남긴다(표시 의무) — 렌더러 광고 표시 칸
        snap["branding"] = {"ad": {"on": True, "text": str(tpl["ad"])[:40], "x": 90, "y": 11, "size": 3, "opacity": 100, "color": "#ffffff"}}
    if text:
        snap["text"].update({k: str(v) for k, v in text.items() if k in ("channel", "hook1", "hook2", "bodyTitle")})
    return snap
