# -*- coding: utf-8 -*-
# _deprecated_2026-10-25 → tools/calcopy/hybrid/styles/썰템쇼판.json (관제 263 지시서 07 · 표준 §3-1: 새 편은 공용 렌더러로. 설명서 프리셋 썰템쇼_화자썰 생성기 — 회원 옛 길 preset_make 가 그 결과를 읽으므로 지우지 않는다)
"""썰템쇼_화자썰 하나-빼고 렌더 검증 — 편 하나를 뺀 7편으로 프리셋을 만들고, 뺀 편의 글(제목·라벨·날짜·훅 길이)만 넣어
실제 렌더 경로(tools/calcopy/check_multi_frame.py → scene_style.compose_still → render_layer_one)로 훅·본문 프레임을 그린 뒤,
원본 같은 시각 프레임과 같은 재는 함수(hs_measure.measure_hook/measure_body)로 층별 잉크 자리를 대조한다.

    PYTHONUTF8=1 py channel/humorshowshow/preset/hs_preset.py loo [id ...]
결과: C:/숏템_칼카피/humorshowshow/preset_work/loo/<id>/{frame.json, render/compare_<t>.png, cmp.json} · loo/loo_hs.json · manifest.verification
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

from channel.humorshowshow.preset import hs_measure as HM, hs_preset as HP
from tools.calcopy.engine import preset_save as P

ROOT = HP.ROOT
LOO = HP.WORK / "loo"
TOL_PX = 4          # 잉크 위·아래 끝 y, 상자 좌표
TOL_W = 0.05        # 글 폭 비율

# (이름, 훅/본문, 원본 측정 키, 비교 꼴) — 비교 꼴: rows=[위,아래] · box=[x0,y0,x1,y1] · xw=[x0,x1](폭·가운데)
ITEMS = [("머리띠 끝", "body", "hdr_end", "num"), ("화살표", "body", "arrow", "box"), ("북마크", "body", "bookmark", "box"),
         ("로고 상자", "body", "logo", "box"), ("게시글 제목 y", "body", "title_rows", "rows"), ("게시글 제목 x", "body", "title_x", "xw"),
         ("조회수 줄 y", "body", "meta_rows", "rows"), ("조회수 줄 x", "body", "meta_x", "xw"), ("댓글 수 빨강 x", "body", "meta_red_x", "xw"),
         ("구분선", "body", "divider_rows", "rows"), ("자막 1줄 y", "body", "cap_lines", "cap0"), ("자막 1줄 x", "body", "cap_x", "capx0"),
         ("그림 창", "body", "window_rows", "rows"),
         ("훅 제목 흰 y", "hook", "white_rows", "rows"), ("훅 제목 흰 x", "hook", "white_x", "xw"), ("훅 제목 연두 y", "hook", "green_rows", "rows"),
         ("훅 제목 연두 x", "hook", "green_x", "xw"), ("훅 라벨 y", "hook", "label_rows", "rows"), ("훅 라벨 x", "hook", "label_x", "xw")]


def judge(kind, o, u):
    if o is None or u is None:
        return {"orig": o, "ours": u, "ok": None}
    if kind == "num":
        d = u - o
        return {"orig": o, "ours": u, "d": d, "ok": abs(d) <= TOL_PX}
    if kind in ("rows", "box"):
        d = [b - a for a, b in zip(o, u)]
        return {"orig": o, "ours": u, "d": d, "ok": max(abs(x) for x in d) <= TOL_PX}
    if kind in ("cap0",):
        if not o or not u:
            return {"orig": o, "ours": u, "ok": None}
        o, u = o[0], u[0]
        d = [b - a for a, b in zip(o, u)]
        return {"orig": o, "ours": u, "d": d, "ok": max(abs(x) for x in d) <= TOL_PX}
    if kind in ("xw", "capx0"):
        if kind == "capx0":
            if not o or not u:
                return {"orig": o, "ours": u, "ok": None}
            o, u = o[0], u[0]
        wo, wu = o[1] - o[0], u[1] - u[0]
        dc = (u[0] + u[1]) / 2 - (o[0] + o[1]) / 2
        dw = (wu - wo) / max(1, wo)
        return {"orig": o, "ours": u, "d_center": round(dc, 1), "d_w_pct": round(dw * 100, 1),
                "ok": abs(dc) <= TOL_PX * 2 and abs(dw) <= TOL_W}


def prep(held: str) -> dict:
    d = LOO / held
    rest = [x for x in HP.IDS if x != held]
    Mh = HP._build(d / "preset" / HP.STYLE, rest)
    pre, Mh = P.load(d / "preset" / HP.STYLE)
    per = json.loads((HP.HAND / f"frame_{held}.json").read_text(encoding="utf-8"))
    F = P.apply(pre, per, None, Mh["variable_stats"], None, Mh.get("rules"))
    F["source"] = held
    fp = d / "frame.json"
    fp.write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    T = json.loads((HM.WORK / "measure" / f"{held}.json").read_text(encoding="utf-8"))["times"]
    times = [T["hook"]] + [T[k] for k in ("body1", "body2") if T.get(k) is not None]
    return {"held": held, "frame": fp, "dir": d, "times": times, "T": T, "tg": caption_filled(held, d)}


def caption_filled(held: str, d: Path) -> Path:
    """뜯기 자막 글이 비어 있으면(무료 키 quota 로 OCR 실패 — 6편) 줄판독(클로드 눈 판독) 줄 글로 채운 사본.
    렌더 대조에서 자막 층이 그려지게 하려는 것뿐 — 자막 칸 자리·크기는 틀이 정하고, 글은 원본 화면 글과 같아야 폭 대조가 맞다."""
    J = json.loads((HP.TG / held / "뜯기.json").read_text(encoding="utf-8"))
    R = json.loads((HM.READ / f"{held}.json").read_text(encoding="utf-8"))["lines"]
    n = 0
    for it in (J.get("captions") or {}).get("items") or []:
        if it.get("text"):
            continue
        mid = (it["t0"] + it["t1"]) / 2
        ln = next((l for l in R if l["t0"] <= mid < l["t1"]), None)
        if ln:
            parts = [x.strip() for x in ln["caption"].split("/")]
            it["text"] = parts[:max(1, it.get("lines") or 1)]
            n += 1
    p = d / "뜯기_자막채움.json"
    p.write_text(json.dumps(J, ensure_ascii=False), encoding="utf-8")
    return p


def run_render(jobs: list[dict], par: int = 3):
    procs = []
    for j in jobs:
        while len([p for p in procs if p.poll() is None]) >= par:
            time.sleep(3)
        tg = j.get("tg") or HP.TG / j["held"] / "뜯기.json"
        if not tg.exists():
            j["failed"] = "뜯기 없음"
            continue
        procs.append(subprocess.Popen([sys.executable, "tools/calcopy/check_multi_frame.py", str(j["frame"]), str(tg), str(j["dir"] / "render"),
                                       "--at", *[str(t) for t in j["times"]]], cwd=str(ROOT),
                                      stdout=subprocess.DEVNULL, stderr=open(j["dir"] / "render.err", "w", encoding="utf-8")))
    for p in procs:
        p.wait()


def compare(j: dict) -> dict:
    held, T = j["held"], j["T"]
    O = json.loads((HM.WORK / "measure" / f"{held}.json").read_text(encoding="utf-8"))
    rd = j["dir"] / "render"
    U = {}
    try:
        U["hook"] = HM.measure_hook(np.asarray(Image.open(rd / f"ours_{T['hook']}.png").convert("RGB")).astype(int))
        for k in ("body1", "body2"):
            if T.get(k) is not None:
                U[k] = HM.measure_body(np.asarray(Image.open(rd / f"ours_{T[k]}.png").convert("RGB")).astype(int))
    except FileNotFoundError as e:
        return {"failed": f"렌더 그림 없음 {e.filename}"}
    rows = {}
    for name, where, key, kind in ITEMS:
        if where == "hook":
            rows[name] = judge(kind, O["hook"].get(key), U["hook"].get(key))
        else:
            for k in ("body2", "body1"):
                if k in U and O.get(k):
                    r = judge(kind, O[k].get(key), U[k].get(key))
                    if r["ok"] is not None:
                        rows[name] = {**r, "at": k}
                        break
    # 자막 폭 대조는 그린 글이 원본 화면 글과 같을 때만 — 줄판독 줄 경계(±0.5~1초)와 뜯기 자막 장면이 어긋나면 다른 글을 그린다(cj3·0Q-C)
    chk = json.loads((rd / "check.json").read_text(encoding="utf-8"))
    for name in ("자막 1줄 x",):
        r = rows.get(name)
        if r and r.get("at"):
            k = r["at"]
            want = (T["lines"]["two"] if k == "body2" else T["lines"]["one"]) or ""
            want = chr(10).join(x.strip() for x in want.split("/"))
            got = chk.get(str(T[k]), {}).get("caption", "")
            if want.replace(" ", "") != got.replace(" ", ""):
                rows[name] = {**r, "ok": None, "skip": f"그린 글 '{got}' ≠ 원본 화면 글 '{want}' — 폭 대조 제외"}
    res = {"times": j["times"], "rows": rows, "compare_png": [str(rd / f"compare_{t}.png") for t in j["times"]],
           "pass": all(r["ok"] for r in rows.values() if r.get("ok") is not None)}
    (j["dir"] / "cmp.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def loo(ids=None):
    ids = ids or HP.IDS
    jobs = [prep(h) for h in ids]
    run_render([j for j in jobs if not (j["dir"] / "render" / f"ours_{j['times'][-1]}.png").exists()])
    res = {}
    for j in jobs:
        res[j["held"]] = {"failed": j["failed"]} if j.get("failed") else compare(j)
        r = res[j["held"]]
        bad = [n for n, x in (r.get("rows") or {}).items() if x.get("ok") is False]
        print(j["held"], "통과" if r.get("pass") else "미달", bad or r.get("failed", ""))
    names = [n for n, *_ in ITEMS]
    table = {}
    for n in names:
        xs = [v["rows"][n] for v in res.values() if v.get("rows") and n in v["rows"] and v["rows"][n].get("ok") is not None]
        table[n] = {"ok": f"{sum(x['ok'] for x in xs)}/{len(xs)}",
                    "max_abs_d": max([max(abs(y) for y in x["d"]) if isinstance(x.get("d"), list) else abs(x.get("d", 0) or 0) for x in xs
                                      if "d" in x] or [None]) if any("d" in x for x in xs) else None,
                    "max_abs_center": max([abs(x["d_center"]) for x in xs if "d_center" in x] or [None]) if any("d_center" in x for x in xs) else None,
                    "max_abs_w_pct": max([abs(x["d_w_pct"]) for x in xs if "d_w_pct" in x] or [None]) if any("d_w_pct" in x for x in xs) else None}
    n = sum(1 for v in res.values() if v.get("pass"))
    summ = {"at": datetime.now().isoformat(timespec="seconds"), "tool": "channel/humorshowshow/preset/hs_loo.py (check_multi_frame 렌더 → hs_measure 대조)",
            "tol": {"px": TOL_PX, "center_px": TOL_PX * 2, "w": TOL_W}, "videos_all_pass": f"{n}/{len(res)}", "items": table,
            "detail": str(LOO / "loo_hs.json")}
    (LOO / "loo_hs.json").write_text(json.dumps({"summary": summ, "results": res}, ensure_ascii=False, indent=1), encoding="utf-8")
    M = json.loads((HP.PRESET / "manifest.json").read_text(encoding="utf-8")) if (HP.PRESET / "manifest.json").exists() else None
    if M:
        M["verification"] = summ
        (HP.PRESET / "manifest.json").write_text(json.dumps(M, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(table, ensure_ascii=False, indent=0))
    print(f"LOO {n}/{len(res)} 편 통과")
