# -*- coding: utf-8 -*-
"""편 하나 배치 — **얇은 입구**. 판단은 전부 bench 한 곳에 있다(0순위-B, 2026-10-16 합침).

  창(틀 없는 구간이 섞이면 시간 조각 다수결) = shopping_shorts.channelkit.bench.layout.measure_video / window_vote
  자막 띠 고르기(후보 띠 × 실제 재기 × 잉크 지속도)  = shopping_shorts.channelkit.bench.captions.choose_caption

여기는 그 둘을 부르고 analyze·bench_one 이 받던 모양({vl, bench_full, window, caption_candidates, caption})으로 묶기만 한다.
"""
from __future__ import annotations

from shopping_shorts.channelkit.bench import layout, captions


def measure(path: str, meta: dict) -> dict:
    canvas = [meta["width"], meta["height"]]
    lv = layout.measure_video(path, meta)
    L = layout.consolidate({"v": lv}, canvas)
    vl = layout.video_layout(L, "v")
    fs = lv.get("frame_segments") or {}
    window = {"method": lv.get("window_method"), "chunks": fs.get("chunks", []), "other_frame_segments": fs.get("other", [])}
    if not vl.get("window"):
        return {"vl": vl, "bench_full": L["per_video"]["v"], "window": window, "caption_candidates": [], "caption": None}
    ch = captions.choose_caption(path, vl, meta, lv["_presence"])
    vl = {**vl, "caption": ch["caption"]}
    return {"vl": vl, "bench_full": L["per_video"]["v"], "window": window, "caption_candidates": ch["scored"],
            "caption": ch["result"]}
