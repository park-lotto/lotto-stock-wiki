# -*- coding: utf-8 -*-
"""뜯기 배치 점검 — 편마다 창·틀 없는 구간·자막 띠(자리·극성·넓힘)·자막 수·후보 점수만 빠르게(제미나이 안 부름).

    PYTHONUTF8=1 py tools/calcopy/engine/check_layout.py <mp4> [<mp4> …]

워커 점검(channel/<slug>/뜯기/<id>/점검.md)의 배치·자막 띠 행과 대조하는 용도. 출력은 한 편 한 줄 + 후보 상위 3.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shopping_shorts.channelkit.bench import probe  # noqa: E402
from tools.calcopy.engine import layout1  # noqa: E402


def main() -> None:
    for p in sys.argv[1:]:
        t = time.time()
        m = probe.info(p)
        r = layout1.measure(p, m)
        vl = r["vl"]
        cap = r["caption"] or {}
        c = vl.get("caption") or {}
        print(f"{Path(p).stem} 창 {vl.get('window')} [{r['window'].get('method')}] 틀없음 {r['window'].get('other_frame_segments')} "
              f"| 자막 {c.get('pos')} {c.get('band')} {c.get('ink')} free={c.get('free', False)} 넓힘전 {c.get('band_before_extend')} "
              f"| 구간 {len(cap.get('spans', []))} 흔들림 {cap.get('unstable')} | 실패 {r.get('caption_failed')} | {time.time() - t:.0f}s")
        top = sorted([x for x in r["caption_candidates"] if x.get("score") is not None], key=lambda x: -x["score"])[:3]
        for x in top:
            print(f"    {x['pos']} {x['band']} {x['ink']} 점수 {x['score']} 구간 {x['spans']} 지속 {x['persist']} 보임 {x['coverage']} 바뀜 {x.get('change')}")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
