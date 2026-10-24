# -*- coding: utf-8 -*-
"""자동 띠 점검(eval_autoband) — autoband 띠로 돌린 자막 분할이 손 띠로 돌린 것과 얼마나 같은가 + 줄판독(눈) 줄 경계를 얼마나 다시 잡나.

손 띠(HAND) 출처: 잇템로그 1150~1460(06 워커 capseg) · 썰풀다 편별(spec PROFILE·seg2 띠, iZ 는 홀수 1301 → 1300) ·
                  홈디자인노트 편별(06 워커 measure.py 띠, 세션 임시 폴더 m_<id>.json band) ·
                  방구석·얌얌노 = 줄판독 y 최소−20 ~ 최대+20(손 띠 기록이 없어 눈으로 잰 글자 자리로 대신 — 기준 자체가 근사).
같음 = 경계 ±1프레임 재현율·정밀도(F1) · 줄판독 = 줄 t0 ±2프레임 재현율(자동이 손의 95% 이상이면 ○).
10-25 실측(28편, 이븐쇼핑은 color 모드가 그 채널 자막을 못 잡아 손 띠도 줄판독 재현 0~0.2 라 뺌):
  F1≥0.95 18/28 · 줄판독 ○ 21/27 — 잇템로그 4/4 · 썰풀다 5/6(fnZN 흰 상자 3줄짜리 핵 못 찾음) · 방구석 5/6 · 얌얌노 6/6(줄판독 ○) · 홈디자인노트 2~3/6.

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/eval_autoband.py [--channels ititemlog,banggu]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine.readline_tools import autoband, capseg, measure  # noqa: E402

DATA = Path("C:/숏템_칼카피")
HAND = {
    "ititemlog": {"mode": "color", "bands": {v: (1150, 1460) for v in ("SbWTqCnleC8", "zOSpeiMw1nA", "AZ2q07mBzlM", "J7GxfaVdwSU")}},
    "sseolpulda": {"mode": None, "bands": {"D3Pc6HZ6t6c": (970, 1190, "bright"), "ZdeZRtCeAC4": (1466, 1530, "dark"), "iZ-TprLYezA": (1300, 1370, "dark"),
                                           "mYxuF1A74j4": (1230, 1320, "bright"), "GqSkDhM_bV0": (1240, 1350, "bright"), "fnZNougO6NQ": (1292, 1378, "both")}},
    "homedesignnote": {"mode": "measure", "bands": {"DCXQjaWcZ-g": (570, 665), "EINoAh8C9rQ": (752, 845), "iiBUscncqIk": (100, 180),
                                                    "SU9YofB1IoI": (520, 612), "WTgQPFfdSOQ": (880, 1030), "_QqLEH4qlFQ": (920, 1012)}},
    "banggu": {"mode": "color", "bands": "lr_y"},
    "yummyknow": {"mode": "color", "bands": "lr_y"},
}


def _bounds(mp4, band, mode):
    if mode == "measure":
        return [s["t0"] for s in measure.summarize(measure.measure(mp4, *band))["segs"]]
    return [x["t0"] for x in capseg.capseg(mp4, *band, mode=mode)[1:]]


def _match(a, b, tol):
    return sum(1 for t in a if any(abs(t - u) <= tol for u in b))


def _lr_band(slug, vid):
    d = json.loads((ROOT / f"channel/{slug}/줄판독/{vid}.json").read_text(encoding="utf-8"))
    ys = [l["y"] for l in d["lines"] if isinstance(l.get("y"), list) and len(l["y"]) == 2 and all(isinstance(x, (int, float)) for x in l["y"])]
    y0 = int(min(y[0] for y in ys)) - 20
    y1 = int(max(y[1] for y in ys)) + 20
    y0 -= y0 % 2
    y1 += (y1 - y0) % 2
    return y0, y1


def _lines(slug, vid):
    p = ROOT / f"channel/{slug}/줄판독/{vid}.json"
    if not p.exists():
        return None
    return sorted(set(round(l["t0"], 3) for l in json.loads(p.read_text(encoding="utf-8"))["lines"] if l["t0"] > 0.1))


def evaluate(channels=None) -> list[dict]:
    rows = []
    for slug, H in HAND.items():
        if channels and slug not in channels:
            continue
        vids = H["bands"] if isinstance(H["bands"], dict) else sorted(p.stem for p in (ROOT / f"channel/{slug}/줄판독").glob("*.json"))
        for vid in vids:
            hb = H["bands"][vid] if isinstance(H["bands"], dict) else _lr_band(slug, vid)
            mode = hb[2] if len(hb) > 2 else H["mode"]
            hb = hb[:2]
            mp4 = str(DATA / slug / "src" / f"{vid}.mp4")
            if not Path(mp4).exists():
                continue
            ab = autoband.find_band(mp4, mode)["band"]
            R = _bounds(mp4, hb, mode)
            A = _bounds(mp4, ab, mode)
            tol = 1 / 30 + 1e-6
            rc = _match(R, A, tol) / max(1, len(R))
            pr = _match(A, R, tol) / max(1, len(A))
            L = _lines(slug, vid)
            lh = la = None
            if L:
                lh = _match(L, R, 2 / 30 + 1e-6) / len(L)
                la = _match(L, A, 2 / 30 + 1e-6) / len(L)
            rows.append({"slug": slug, "id": vid, "mode": mode, "hand": list(hb), "auto": ab, "recall": round(rc, 3), "prec": round(pr, 3),
                         "f1": round(2 * rc * pr / max(1e-9, rc + pr), 3), "lines_hand": lh and round(lh, 3), "lines_auto": la and round(la, 3)})
            print(rows[-1], flush=True)
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--channels")
    A = ap.parse_args(argv)
    rows = evaluate(A.channels.split(",") if A.channels else None)
    ok = sum(r["f1"] >= 0.95 for r in rows)
    lo = [r for r in rows if r["lines_hand"]]
    lok = sum(r["lines_auto"] >= 0.95 * r["lines_hand"] for r in lo)
    print(f"F1≥0.95 {ok}/{len(rows)} · 줄판독 경계(자동 ≥ 손×0.95) {lok}/{len(lo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
