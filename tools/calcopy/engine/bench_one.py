# -*- coding: utf-8 -*-
"""영상 1편을 bench 자 한 벌로 잰다 — `channelkit.bench.run()`의 편 단위 흐름을 그대로 한 편에.

흐름(bench/__init__.py run 과 같은 순서·같은 함수, bench 코드는 고치지 않고 부르기만):
  probe.info → layout.measure_video → layout.consolidate({vid: …}) → layout.video_layout
  → captions.measure_video(자막 띠가 있을 때) → cuts.measure_video(자막 교체 시각을 받는다) → audio.measure_video

대조 도구(compare.py)와 분석기(analyze.py)가 같이 부른다 — 편 하나 재는 법은 여기 한 곳(0순위-B).
단계 하나가 실패해도 멈추지 않고 `errors[단계] = 이유`로 남긴다(조용한 실패 금지: 결과에 그대로 보인다).

layout 모드:
  "bench"  (기본) bench.run 과 똑같이 measure_video → consolidate → video_layout
  "single" tools/calcopy/engine/layout1.measure(편 하나 감싸개: 엔딩 전체화면·머리띠 오인 보정)를 쓴다.
           layout1 이 없으면 **오류로** 멈춘다(조용히 bench 로 되돌아가지 않는다).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from shopping_shorts.channelkit.bench import probe, layout, captions, cuts, audio  # noqa: E402

_EMPTY_CAP = {"region": None, "changes": [], "spans": [], "items": [], "glyph": []}


def _err(e: Exception) -> str:
    return f"{type(e).__name__}: {str(e)[:160]}"


def measure(path: str, vid: str | None = None, zoom: bool = False, layout_mode: str = "bench") -> dict:
    """편 하나의 bench 측정. 반환 = {vid, path, probe, layout, vl, layout_method, captions, cuts, audio, errors}.
    zoom 기본 False(ORB 줌 추적은 느리고 대조 기준에 없다). 필요하면 True."""
    vid = vid or Path(path).stem
    res: dict = {"vid": vid, "path": str(path), "layout_mode": layout_mode, "errors": {}}
    try:
        meta = probe.info(path)
    except Exception as e:  # noqa: BLE001 — probe 가 안 되면 아무것도 못 잰다
        res["errors"]["probe"] = _err(e)
        return res
    res["probe"] = meta
    canvas = [meta["width"], meta["height"]]
    vl = None
    try:
        if layout_mode == "bench":
            lv = layout.measure_video(path, meta)
            L = layout.consolidate({vid: lv}, canvas)
            vl = layout.video_layout(L, vid)
            res["layout"] = L["per_video"][vid]
            res["layout_method"] = "layout.measure_video+layout.consolidate+layout.video_layout"
        elif layout_mode == "single":
            from tools.calcopy.engine import layout1  # 없으면 ImportError 로 멈춘다(되돌아가기 없음)
            m = layout1.measure(path, meta)
            vl = m["vl"]
            res["layout"] = {**m["bench_full"], "window": vl["window"], "bg_rgb": vl["bg_rgb"], "caption": vl["caption"]}
            res["layout_method"] = "layout1.measure(" + m["window"].get("method", "") + ")"
            res["layout1"] = {"window": m["window"], "caption_candidates": m["caption_candidates"]}
        else:
            raise ValueError(f"layout_mode 모름: {layout_mode}")
    except ImportError:
        raise
    except Exception as e:  # noqa: BLE001
        res["errors"]["layout"] = _err(e)
    res["vl"] = vl
    cap = dict(_EMPTY_CAP)
    if vl is not None:
        try:
            if vl["caption"].get("band"):
                cap = captions.measure_video(path, vl, meta)
            else:
                res["errors"]["captions"] = "자막 띠 못 찾음(layout caption.band=None)"
        except Exception as e:  # noqa: BLE001
            res["errors"]["captions"] = _err(e)
        try:
            res["cuts"] = cuts.measure_video(path, vl, meta, cap["changes"], zoom=zoom)
            if res["cuts"].get("cuts") is None:
                res["errors"]["cuts"] = "영상창 못 찾음(layout window=None)"
        except Exception as e:  # noqa: BLE001
            res["errors"]["cuts"] = _err(e)
    res["captions"] = cap
    try:
        res["audio"] = audio.measure_video(path, meta)
    except Exception as e:  # noqa: BLE001
        res["errors"]["audio"] = _err(e)
    return res


if __name__ == "__main__":
    import json
    import argparse
    ap = argparse.ArgumentParser(description="영상 1편 bench 측정")
    ap.add_argument("video")
    ap.add_argument("--layout", default="bench", choices=["bench", "single"])
    ap.add_argument("--zoom", action="store_true")
    a = ap.parse_args()
    r = measure(a.video, zoom=a.zoom, layout_mode=a.layout)
    print(json.dumps({k: v for k, v in r.items() if k not in ("captions",)}, ensure_ascii=False, indent=1, default=str)[:6000])
    sys.exit(0)
