# -*- coding: utf-8 -*-
"""뜯은 틀(설명서) ↔ 우리 템플릿팩(out/continuous20-data.js 고정형 · out/precision20-data.js 훅+본문) 대조 — 가장 가까운 3개.

    PYTHONUTF8=1 py tools/calcopy/engine/template_match.py <frame.json | 프리셋 폴더> [--write]   (--write: 프리셋 manifest.nearest_template)

비교 값(1080×1920 으로 늘려 잰다 — 템플릿은 240×426·425×748 같은 작은 판):
  창 위 끝(video_from.y) · 제목 첫 줄 위 끝 · 자막 줄 y · 바탕색(title_bg) · 제목 줄 수.
점수 = |창 위 끝 차| + |제목 위 끝 차| + 0.5×|자막 y 차| + 2×바탕색 채널 최대차 + 80×|제목 줄 수 차| (작을수록 가깝다).
틀 여러 장이면 훅 틀 ↔ 고정형·훅+본문의 훅, 본문 틀 ↔ 훅+본문의 본문을 따로 잰다. 판단 주인: score() 한 곳.
'가깝다' = 점수 ≤ CLOSE(그 템플릿을 바탕으로 차이만 적는 길의 재료). 아니면 '가까운 것 없음'으로 남긴다.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.calcopy_frame import schema  # noqa: E402

CLOSE = 150
W0, H0 = 1080, 1920


def _rgb(hexv):
    try:
        h = str(hexv).lstrip("#")[:6]
        return [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    except (ValueError, TypeError):
        return None


def _load(name: str, var: str) -> list:
    raw = (ROOT / "out" / name).read_text(encoding="utf-8-sig").strip()
    return json.loads(raw.split("=", 1)[1].rstrip(";\r\n "))


def tpl_feat(f: dict, part: str) -> dict:
    """템플릿 판 하나 → 비교 값(1080×1920 기준)."""
    sy = H0 / float(f.get("height") or H0)
    lines = f.get("lines") or []
    title = [l for l in lines if l.get("bind") in ("hook1", "hook2") or (part == "hook" and l.get("bind") is None)]
    if part == "body" and not title:
        title = [l for l in lines if l.get("bind") == "bodyTitle"]
    cap = next((l for l in lines if l.get("bind") == "caption"), None)
    return {"win_top": round((f.get("video_from") or {}).get("y", 0) * sy), "title_top": round(min(l["y0"] for l in title) * sy) if title else None,
            "cap_y": round((cap["y0"] + cap["y1"]) / 2 * sy) if cap else None, "bg": _rgb(f.get("title_bg")), "title_lines": len(title)}


def frame_feat(layers: list) -> dict:
    v = next((l for l in layers if l["kind"] == "video"), None)
    bg = next((l for l in layers if l["kind"] == "bg"), None)
    t = next((l for l in layers if l["kind"] == "text" and l["role"] == "title"), None)
    if t is None:      # 게시글형 본문: 글 제목 문구(가장 큰 label)를 제목 자리로
        lab = [l for l in layers if l["kind"] == "text" and l["role"] == "label"]
        t = max(lab, key=lambda l: l["size"], default=None)
        lines = 1 if t else 0
    else:
        lines = t["lines"]
    c = next((l for l in layers if l["kind"] == "text" and l["role"] == "caption"), None)
    return {"win_top": v["y"] if v else None, "title_top": t["y"] if t else None,
            "cap_y": round(c["y"] + c["line_h"] / 2) if c else None, "bg": bg["rgb"] if bg else None, "title_lines": lines}


def score(a: dict, b: dict) -> tuple[float, dict]:
    parts = {}
    for k, w in (("win_top", 1.0), ("title_top", 1.0), ("cap_y", 0.5)):
        if a.get(k) is not None and b.get(k) is not None:
            parts[k] = round(w * abs(a[k] - b[k]), 1)
    if a.get("bg") and b.get("bg"):
        parts["bg"] = 2 * max(abs(x - y) for x, y in zip(a["bg"], b["bg"]))
    parts["title_lines"] = 80 * abs((a.get("title_lines") or 0) - (b.get("title_lines") or 0))
    return round(sum(parts.values()), 1), parts


def match(frame: dict, top: int = 3) -> dict:
    spec = schema.validate(frame)
    C, P = _load("continuous20-data.js", "CONTINUOUS20"), _load("precision20-data.js", "PRECISION20")
    parts = [(fr["id"], fr["layers"]) for fr in spec["frames"]] if spec.get("frames") else [("one", spec["layers"])]
    out = {}
    for fid, layers in parts:
        me = frame_feat(layers)
        cands = []
        if fid in ("one", "hook"):
            cands += [(r["id"], r.get("name"), "고정형", tpl_feat(r["frame"], "hook")) for r in C if r.get("frame") and not r.get("admin_only")]
            cands += [(r["id"], r.get("name"), "훅+본문·훅", tpl_feat(r["hook"], "hook")) for r in P if r.get("hook")]
        if fid in ("one", "body"):
            cands += [(r["id"], r.get("name"), "훅+본문·본문", tpl_feat(r["body"], "body")) for r in P if r.get("body")]
        rows = []
        for tid, name, kind, f in cands:
            s, why = score(me, f)
            rows.append({"id": tid, "name": name, "kind": kind, "score": s, "parts": why, "tpl": f})
        rows.sort(key=lambda r: r["score"])
        out[fid] = {"me": me, "top": rows[:top], "close": bool(rows and rows[0]["score"] <= CLOSE)}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="frame.json 또는 프리셋 폴더(frame.json + sources/ 첫 편으로 변수 채움)")
    ap.add_argument("--write", action="store_true", help="프리셋 폴더면 manifest.nearest_template 에 기록")
    a = ap.parse_args(argv)
    p = Path(a.target)
    if p.is_dir():
        from tools.calcopy.engine import preset_save as PS
        pre, M = PS.load(p)
        first = json.loads((p / "sources" / f"{M['sources'][0]['id']}.json").read_text(encoding="utf-8"))
        frame = PS.apply(pre, first)
    else:
        frame = json.loads(p.read_text(encoding="utf-8"))
    res = match(frame)
    for fid, r in res.items():
        print(f"[{fid}] 나 {r['me']}  가깝다={r['close']}(기준 ≤{CLOSE})")
        for x in r["top"]:
            print(f"   {x['score']:7.1f}  {x['id']:14s} {x['name']} ({x['kind']})  {x['parts']}")
    if a.write and p.is_dir():
        from datetime import date
        Mp = p / "manifest.json"
        M = json.loads(Mp.read_text(encoding="utf-8"))
        M["nearest_template"] = {"tool": "template_match", "at": date.today().isoformat(), "close_max": CLOSE,
                                 "frames": {fid: {"close": r["close"], "top": [{k: x[k] for k in ("id", "name", "kind", "score", "parts")} for x in r["top"]]}
                                            for fid, r in res.items()}}
        Mp.write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
        print("기록:", Mp)


if __name__ == "__main__":
    main()
