# -*- coding: utf-8 -*-
"""channelkit.bench — 채널 실측 자 한 벌. 표본 mp4 폴더 → layout.json + bench.json.

설계: docs/superpowers/specs/2026-09-28-channelkit-bench-design.md
유일한 입구는 `run`. 순서: probe → layout(편별 → 틀 묶음) → captions → cuts(자막 교체 시각을 받는다) → audio.
기준 id(L/S/T/A…)가 bench.json criteria의 키이고, 기준마다 `method` = 잰 함수 이름.
채널 이름은 라벨로만 들어간다 — 코드 어디에도 채널별 분기·좌표가 없다.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import probe, layout, captions, cuts, audio
from . import constants as C

BASELINE_DIR = Path(__file__).with_name("baselines")


def _video_ids(sample_dir: str) -> list[tuple[str, str]]:
    return sorted((p.stem, str(p)) for p in Path(sample_dir).glob("*.mp4"))


def _stage1(args):
    vid, path = args
    meta = probe.info(path)
    return vid, meta, layout.measure_video(path, meta)


def _stage2(args):
    vid, path, meta, vl, zoom = args
    cap = captions.measure_video(path, vl, meta) if vl["caption"].get("band") else \
        {"region": None, "changes": [], "spans": [], "items": [], "glyph": []}
    cu = cuts.measure_video(path, vl, meta, cap["changes"], zoom=zoom)
    au = audio.measure_video(path, meta)
    return vid, {"captions": cap, "cuts": cu, "audio": au}


def _layout_criteria(L: dict, metas: dict) -> dict:
    main = next(v for v in L["variants"] if v["id"] == L["main"])
    ys = list(main["window_y_per_video"].values())
    crit = {
        "L.canvas": {"value": L["canvas"], "stat": "mode", "n": len(metas), "unit": "px", "method": "probe.info"},
        "L.frame_variants": {"value": {v["id"]: len(v["videos"]) for v in L["variants"]}, "stat": "count",
                             "detail": {v["id"]: {"videos": v["videos"], "window": v["window"], "caption_pos": v["caption"]["pos"],
                                                  "ink": v["caption"]["ink"], "bg_rgb": v["bg_rgb"]} for v in L["variants"]},
                             "method": "layout.consolidate"},
        "L.window": {"value": main["window"], "stat": "median [x,y,w,h]", "y0_range": [min(y[0] for y in ys), max(y[0] for y in ys)],
                     "y1_range": [min(y[1] for y in ys), max(y[1] for y in ys)], "per_video": main["window_y_per_video"],
                     "n": len(ys), "unit": "px", "method": "layout.measure_video"},
        "L.bg_rgb": {"value": main["bg_rgb"], "stat": "median", "unit": "RGB", "method": "layout.measure_video"},
        "L.logo_band": {"value": main["logo"], "stat": "rows [y0,y1)", "unit": "px", "method": "layout._logo"},
        "L.caption_pos": {"value": main["caption"]["pos"], "stat": "label", "method": "layout._caption"},
        "L.sub_band": {"value": main["caption"]["band"], "stat": "rows [y0,y1) union", "unit": "px", "method": "layout._caption"},
        "S.ink_polarity": {"value": main["caption"]["ink"], "stat": "label", "method": "layout._caption"},
    }
    if main["window"]:
        crit["L.slot_ratio"] = {"value": round(main["window"][2] / main["window"][3], 3), "stat": "w/h", "method": "layout.measure_video"}
    return crit


def run(channel: str, sample_dir: str, out_dir: str, profile: dict | None = None, workers: int | None = None,
        zoom: bool = True) -> dict:
    """표본 폴더의 mp4 전부를 재서 out_dir/layout.json·bench.json을 쓰고 bench dict를 돌려준다."""
    vids = _video_ids(sample_dir)
    if not vids:
        raise FileNotFoundError(f"mp4 없음: {sample_dir}")
    os.makedirs(out_dir, exist_ok=True)
    workers = workers or min(4, os.cpu_count() or 1)
    metas, lay = {}, {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for vid, meta, lv in ex.map(_stage1, vids):
            metas[vid], lay[vid] = meta, lv
    canvas = [metas[vids[0][0]]["width"], metas[vids[0][0]]["height"]]
    L = layout.consolidate(lay, canvas)
    with open(os.path.join(out_dir, "layout.json"), "w", encoding="utf-8") as f:
        json.dump(L, f, ensure_ascii=False, indent=1)
    per_video = {vid: {"probe": metas[vid], "layout": L["per_video"][vid], "variant": layout.variant_of(L, vid)["id"]}
                 for vid, _ in vids}
    jobs = [(vid, path, metas[vid], layout.video_layout(L, vid), zoom) for vid, path in vids]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for vid, res in ex.map(_stage2, jobs):
            per_video[vid].update(res)
    main_vids = next(v for v in L["variants"] if v["id"] == L["main"])["videos"]
    all_vids = [v for v, _ in vids]
    crit = _layout_criteria(L, metas)
    durs = [metas[v]["duration"] for v in main_vids]
    crit["T.duration"] = {"value": round(sorted(durs)[len(durs) // 2], 2), "stat": "median", "range": [min(durs), max(durs)],
                          "n": len(durs), "unit": "초(프레임÷fps)", "method": "probe.info"}
    crit.update(captions.summarize(per_video, main_vids))
    crit.update(cuts.summarize(per_video, main_vids))
    crit.update(audio.summarize(per_video, all_vids))
    main = next(v for v in L["variants"] if v["id"] == L["main"])
    bench = {
        "channel": channel, "measured_at": _dt.date.today().isoformat(), "sample": all_vids,
        "profile": profile or {}, "main_variant": L["main"],
        "constants": {k: getattr(C, k) for k in dir(C) if k.isupper()},
        "layout": {"canvas": canvas, "window": main["window"], "caption": main["caption"], "logo": main["logo"],
                   "bg_rgb": main["bg_rgb"], "variants": {v["id"]: v["videos"] for v in L["variants"]}},
        "criteria": crit, "per_video": per_video,
    }
    with open(os.path.join(out_dir, "bench.json"), "w", encoding="utf-8") as f:
        json.dump(bench, f, ensure_ascii=False, indent=1)
    return bench


def baseline(name: str) -> dict:
    """baselines/<name>*.json 중 가장 최근 것."""
    cands = sorted(BASELINE_DIR.glob(f"{name}_*.json"))
    if not cands:
        raise FileNotFoundError(f"기준선 없음: {name}")
    return json.loads(cands[-1].read_text(encoding="utf-8"))
