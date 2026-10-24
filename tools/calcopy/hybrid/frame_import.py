# -*- coding: utf-8 -*-
"""설명서 frame.json(calcopy_frame v1 층 목록) → 판 설정 `frame` 칸 초안 (관제 263 지시서 07 · 표준 §3-3 B1). 한 번 돌리고 끝 — 판 파일이 주인.

    PYTHONUTF8=1 py tools/calcopy/hybrid/frame_import.py <frame.json> --kind post|full|window [--frame body|hook] [--out 초안.json]

픽셀 그대로 옮긴다(값을 고치지 않는다). 옮기는 법(render_bench.frame_png · _draw_post 칸 이름):
  bg → frame.bg · video → frame.window[x,y,w,h]
  (post) 위 머리띠(y=0, 폭 전체, 높이 ≥100) → post.head_bar{box[x0,y0,x1,y1],color} · 머리띠 안 작은 띠 3개 이상(같은 x·w·h) → icons bars ·
         돋보기 svg 그림 → icons search{x,y,size,stroke} · 머리띠 안 brand 글 → icons text{from:'brand'} ·
         fade 있는 띠 → post.body_box{box,color,fade} (그 안 띠 = body_box.rules, 그 안 label 글 = body_box.text) ·
         작은 글(label, 크기 < 45) → post.author_line · 그 밖 띠 → post.rules
  text role=title(줄 여러 개) → frame.title[] 줄마다 {font,px,center,color,max_w(+stroke,shadow)} · 머리띠 밑 굵은 label(제목 꼴, post) → frame.title[0]
  text role=caption → 반환 `_caption_layer`(자막 자리 — 렌더러는 자막팩이 자리를 정한다, 판 caption.band 근거로만 쓴다)
글꼴 이름: frame.json 의 글꼴 이름('CcPretendard-SemiBold')을 shopping_shorts/static/fonts 파일로(앞 'Cc' 떼고 같은 이름 .ttf/.otf). 못 찾으면 `_unresolved` 에 적는다(지어내지 않는다).
글 세로 자리: frame.json text 는 y=줄 상자 위, valign center → 줄 i 가운데 = y + line_h×(i+0.5) (render_bench._draw_text cy · _title_line center 와 같은 뜻).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FONTS = ROOT / "shopping_shorts/static/fonts"


def hexc(rgb) -> str:
    return "#%02X%02X%02X" % tuple(int(c) for c in rgb[:3])


def font_file(name: str | None, unresolved: list) -> str | None:
    if not name:
        return None
    base = re.sub(r"^Cc", "", name)
    for ext in (".ttf", ".otf"):
        if (FONTS / (base + ext)).exists():
            return base + ext
    hit = sorted(p.name for p in FONTS.glob(base + "*") if p.suffix.lower() in (".ttf", ".otf"))
    if hit:
        return hit[0]
    unresolved.append(name)
    return name


def _box(l) -> list[int]:
    return [int(l["x"]), int(l["y"]), int(l["x"] + l["w"]), int(l["y"] + l["h"])]


def _inside(l, box) -> bool:
    return box[0] <= l["x"] and l["x"] + l.get("w", 0) <= box[2] and box[1] <= l["y"] and l["y"] + l.get("h", 0) <= box[3]


def _text(l, unresolved) -> dict:
    d = {"font": font_file(l.get("font"), unresolved), "px": l["size"], "color": hexc(l["rgb"])}
    if l.get("align") == "left":
        d["x"] = int(l["x"])
    else:
        d["cx"] = int(l["x"])
    d["cy"] = round(l["y"] + l.get("line_h", l["size"]) / 2, 1)
    if l.get("word_spacing"):
        d["word_spacing"] = l["word_spacing"]
    if l.get("w"):
        d["max_w"] = int(l["w"])
    if l.get("text"):
        d["text"] = l["text"]
    return d


def _title_lines(l, unresolved) -> list[dict]:
    n = int(l.get("lines") or 1)
    lh = l.get("line_h") or l["size"]
    cols = l.get("line_rgb") or [l["rgb"]] * n
    out = []
    for i in range(n):
        d = {"font": font_file(l.get("font"), unresolved), "px": l["size"], "center": round(l["y"] + lh * (i + 0.5), 1),
             "color": hexc(cols[min(i, len(cols) - 1)] or l["rgb"]), "max_w": int(l.get("w") or 1000)}
        if l.get("outline"):
            d["stroke"] = {"px": l["outline"].get("px", 0), "color": hexc(l["outline"].get("rgb", [0, 0, 0]))}
        if l.get("shadow"):
            s = l["shadow"]
            d["shadow"] = {"dx": s.get("dx", 0), "dy": s.get("dy", 0), "color": hexc(s.get("rgb", [0, 0, 0]))}
        out.append(d)
    return out


def _search_icon(l) -> dict | None:
    src = urllib.parse.unquote(str(l.get("src") or ""))
    if "circle" not in src or "path" not in src:
        return None
    m = re.search(r"stroke-width=.?(\d+)", src)
    c = re.search(r"stroke=.?(#?\w+)", src)
    col = c.group(1) if c else "black"
    col = "#000000" if col in ("black", "#000") else col
    return {"kind": "search", "x": int(l["x"]), "y": int(l["y"]), "size": int(l["w"]), "stroke": int(m.group(1)) if m else 7, "color": col}


def convert(fj: dict, kind: str, frame_id: str | None = None) -> dict:
    frames = fj.get("frames") or [{"id": "only", "layers": fj.get("layers") or []}]
    fr = next((f for f in frames if f.get("id") == frame_id), None) if frame_id else frames[-1]
    if fr is None:
        raise SystemExit(f"frame id {frame_id} 없음 — 있는 것 {[f.get('id') for f in frames]}")
    L = fr["layers"]
    unresolved: list = []
    out: dict = {"kind": kind, "_from": f"frame_import.py ← {fj.get('made_by')} source={fj.get('source')} frame={fr.get('id')} span={fr.get('span')}"}
    bg = next((l for l in L if l["kind"] == "bg"), None)
    out["bg"] = list(bg["rgb"]) if bg else [0, 0, 0]
    vid = next((l for l in L if l["kind"] == "video"), None)
    if vid and kind != "full":
        out["window"] = [int(vid["x"]), int(vid["y"]), int(vid["w"]), int(vid["h"])]
    titles = [l for l in L if l["kind"] == "text" and l.get("role") == "title"]
    out["title"] = [x for l in titles for x in _title_lines(l, unresolved)]
    cap = next((l for l in L if l["kind"] == "text" and l.get("role") == "caption"), None)
    if cap:
        out["_caption_layer"] = {"font": font_file(cap.get("font"), unresolved), "px": cap["size"], "color": hexc(cap["rgb"]),
                                 "y_top": cap["y"], "line_h": cap.get("line_h"), "lines": cap.get("lines"), "cx": cap["x"], "max_w": cap.get("w")}
    if kind == "post":
        P: dict = {}
        bands = [l for l in L if l["kind"] == "band"]
        head = next((b for b in bands if b["y"] == 0 and b["x"] == 0 and b["w"] >= 1000 and b["h"] >= 100), None)
        used = set()
        if head:
            used.add(id(head))
            hb = {"box": _box(head), "color": hexc(head["rgb"]), "icons": []}
            small = [b for b in bands if b is not head and _inside(b, hb["box"]) and b["h"] <= 14]
            groups: dict = {}
            for b in small:
                groups.setdefault((b["x"], b["w"], b["h"]), []).append(b)
            for (x, w, h), bs in groups.items():
                if len(bs) >= 3:
                    hb["icons"].append({"kind": "bars", "x": int(x), "ys": [int(b["y"]) for b in bs], "w": int(w), "h": int(h), "color": hexc(bs[0]["rgb"])})
                    used.update(id(b) for b in bs)
            for im in [l for l in L if l["kind"] == "image" and _inside(l, hb["box"])]:
                ic = _search_icon(im)
                if ic:
                    hb["icons"].append(ic)
            for t in [l for l in L if l["kind"] == "text" and l.get("role") == "brand"]:
                d = _text(t, unresolved)
                d.update({"kind": "text", "from": "brand"})
                hb["icons"].append(d)
            P["head_bar"] = hb
        body = next((b for b in bands if b.get("fade")), None)
        if body:
            used.add(id(body))
            bb = {"box": _box(body), "color": hexc(body["rgb"]), "fade": list(body["fade"])}
            if body.get("radius"):
                bb["radius"] = body["radius"]
            inner = [b for b in bands if id(b) not in used and _inside(b, bb["box"])]
            if inner:
                bb["rules"] = [{"box": _box(b), "color": hexc(b["rgb"])} for b in inner]
                used.update(id(b) for b in inner)
            bt = next((t for t in L if t["kind"] == "text" and t.get("role") == "label" and bb["box"][1] <= t["y"] <= bb["box"][3]), None)
            if bt:
                bb["text"] = _text(bt, unresolved)
                used.add(id(bt))
            P["body_box"] = bb
        labels = [t for t in L if t["kind"] == "text" and t.get("role") == "label" and id(t) not in used]
        small_lab = [t for t in labels if t["size"] < 45]
        if small_lab:
            P["author_line"] = _text(small_lab[0], unresolved)
        big = [t for t in labels if t["size"] >= 45 and head and t["y"] >= head["y"] + head["h"]]
        if big and not out["title"]:      # 게시글 제목 줄(머리띠 밑 굵은 글 1줄) = 대본 title_lines 첫 줄 자리
            out["title"] = _title_lines({**big[0], "lines": 1}, unresolved)
        rules = [b for b in bands if id(b) not in used]
        if rules:
            P["rules"] = [{"box": _box(b), "color": hexc(b["rgb"])} for b in rules]
        out["post"] = P
    if unresolved:
        out["_unresolved_fonts"] = sorted(set(unresolved))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("frame_json")
    ap.add_argument("--kind", required=True, choices=["post", "full", "window"])
    ap.add_argument("--frame", default=None, help="frames[].id (기본 = 마지막 틀 = 본문)")
    ap.add_argument("--out", default=None)
    a = ap.parse_args(argv)
    fj = json.loads(Path(a.frame_json).read_text(encoding="utf-8"))
    res = convert(fj, a.kind, a.frame)
    s = json.dumps(res, ensure_ascii=False, indent=1)
    if a.out:
        Path(a.out).write_text(s + "\n", encoding="utf-8")
    print(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
