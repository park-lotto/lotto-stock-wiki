# -*- coding: utf-8 -*-
"""전환 확인 시트(transsheet) — 표준 §11-8 ㊴ ③: 경계마다 선명도·밝기 곡선 + 규칙 판정 초안을 보여 주고 사람(06)은 확정만 한다.

경계마다 한 줄:
  [경계 −8 ~ 끝 +8 프레임, 2프레임 간격 창 썸네일] [선명도 곡선(파랑, 직전 수준 60%·80% 선) · 밝기 Y 곡선(주황, 직전 +40·20 선)] [초안 글]
초안 = cutdet.classify_arrays(4종 규칙 주인) — kind(cut·flash·zoomblur·black) · blur_tail · 움푹 비율 · 양쪽 회복 · 흐림 길이 · Y 피크 · 색 채움.
지금 줄판독 transition(있으면)을 옆에 적고, 다르면 빨간 글씨로 표시한다.
출력: <out_dir>/<id>_trans_NN.jpg(12경계씩) + <out_dir>/<id>_trans.json(경계마다 초안·특징·지금 정답 — 06 이 confirm 칸만 채운다)

    PYTHONUTF8=1 py tools/calcopy/engine/readline_tools/transsheet.py <slug> <원본폴더> <out_dir> [--ids a,b]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.calcopy.engine.readline_tools import cutdet  # noqa: E402
from tools.calcopy.engine.readline_tools import eval_transition_loco as L  # noqa: E402

FPS = 30.0
TW, TH = 72, 96          # 썸네일
PW, PH = 300, 96         # 곡선 칸


def _arrays(slug: str, mp4: str, vid: str):
    L.dump_one(slug, mp4, vid)
    z = np.load(L.CACHE / f"{slug}__{vid}.npz")
    n = len(z["mean"])
    A = {k: z[k] for k in ("mean", "sh")}
    A["std"] = z["std"] if "std" in z.files else None
    m = min(n, len(z["r"]))
    for k in ("r", "g", "b"):
        A[k] = np.r_[z[k][:m], np.full(n - m, z[k][m - 1] if m else 0)]
    return A, cutdet.cut_groups(z["diff"], z["hd"]), json.loads(str(z["meta"]))


def _plot(A, s, e, ev, P):
    img = np.full((PH, PW, 3), 255, np.uint8)
    lo, hi = max(0, s - 12), min(len(A["mean"]), e + 17)
    xs = lambda i: int((i - lo) / max(1, hi - lo - 1) * (PW - 1))
    sh = A["sh"][lo:hi]
    y = A["mean"][lo:hi]
    smax = float(max(1e-6, sh.max()))
    pre_sh = float(np.median(A["sh"][max(0, s - 12):max(1, s - 1)]))
    for frac, col in ((P["DIP"], (200, 200, 255)), (P["REC"], (230, 230, 255))):
        yy = PH - 1 - int(min(1, frac * pre_sh / smax) * (PH - 1))
        cv2.line(img, (0, yy), (PW - 1, yy), col, 1)
    pts = [(xs(lo + i), PH - 1 - int(v / smax * (PH - 1))) for i, v in enumerate(sh)]
    cv2.polylines(img, [np.array(pts, np.int32)], False, (200, 60, 0), 2)
    pts = [(xs(lo + i), PH - 1 - int(min(255, v) / 255 * (PH - 1))) for i, v in enumerate(y)]
    cv2.polylines(img, [np.array(pts, np.int32)], False, (0, 140, 255), 1)
    yb = PH - 1 - int(P["BLACK"] / 255 * (PH - 1))
    cv2.line(img, (0, yb), (PW - 1, yb), (60, 60, 60), 1)
    for x in (xs(s), xs(e)):
        cv2.line(img, (x, 0), (x, PH - 1), (0, 0, 0), 1)
    return img


def sheet(slug: str, src_dir: str, out_dir: str, vid: str) -> dict:
    mp4 = str(Path(src_dir) / f"{vid}.mp4")
    A, groups, meta = _arrays(slug, mp4, vid)
    ev = cutdet.classify_arrays(A, groups)
    P = dict(cutdet.V2)
    lr = json.loads((ROOT / f"channel/{slug}/줄판독/{vid}.json").read_text(encoding="utf-8"))
    gt = [(l["t0"], str(l.get("transition") or "none")) for l in lr["lines"]]
    cap = cv2.VideoCapture(mp4)
    y0, y1 = meta["y0"], meta["y1"]
    rows, recs = [], []
    gmap = {round(g[0] / FPS, 3): g for g in groups}
    for e in ev:
        s, en = (0, 0) if e.get("start") else gmap.get(e["t"], (int(e["t"] * FPS), int(e["te"] * FPS)))
        now = [k for t, k in gt if e["t"] - 0.15 <= t <= e["te"] + 0.15]
        thumbs = []
        for i in range(max(0, s - 8), en + 9, 2):
            cap.set(cv2.CAP_PROP_POS_MSEC, i / FPS * 1000)
            ok, f = cap.read()
            t = cv2.resize(f[y0:y1], (TW, TH)) if ok else np.zeros((TH, TW, 3), np.uint8)
            if i in (s, en):
                cv2.rectangle(t, (0, 0), (TW - 1, TH - 1), (0, 0, 255), 2)
            thumbs.append(t)
        strip = np.hstack(thumbs[:11] + [np.zeros((TH, TW, 3), np.uint8)] * max(0, 11 - len(thumbs)))
        txt = np.full((TH, 360, 3), 255, np.uint8)
        draft = e["kind"] + (" +blur_tail" if e.get("blur_tail") else "")
        cur = now[0].split("(")[0] if now else "(줄 없음)"
        col = (0, 0, 0) if cur == e["kind"] or (cur == "none" and e["kind"] == "cut") else (0, 0, 220)
        for j, line in enumerate([f"{e['t']:.3f}s  DRAFT {draft}", f"NOW {cur if cur.isascii() else '?'}",
                                  f"dip {e['dip_ratio']} recL{int(e['rec_left'])} recR{int(e['rec_right'])} blur {e['blur_len']}f",
                                  f"Ypk {e['y_peak_jump']:+} Ymin {e['y_min']} fill {int(e['fill'])} tint {e.get('tint', 0)}"]):
            cv2.putText(txt, line, (4, 20 + 22 * j), cv2.FONT_HERSHEY_SIMPLEX, 0.45, col if j < 2 else (40, 40, 40), 1)   # 그림 글은 영문(cv2 는 한글을 못 쓴다), json 에 같은 값
        rows.append(np.hstack([strip, _plot(A, s, en, e, P), txt]))
        recs.append({"t": e["t"], "te": e["te"], "draft": e["kind"], "blur_tail": e.get("blur_tail", False), "now": cur,
                     "features": {k: e[k] for k in ("dip_ratio", "rec_left", "rec_right", "blur_len", "y_peak_jump", "y_min", "fill", "tint") if k in e},
                     "confirm": None})
    cap.release()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    sheets = []
    for k in range(0, len(rows), 12):
        p = out / f"{vid}_trans_{k // 12:02d}.jpg"
        cv2.imencode(".jpg", np.vstack(rows[k:k + 12]), [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(str(p))
        sheets.append(str(p))
    doc = {"id": vid, "slug": slug, "rule": "표준 §11-8 ㊴ · cutdet.V2", "V2": P, "boundaries": recs, "sheets": sheets,
           "how": "confirm 칸에 확정 종류(cut/flash/zoomblur/black, 블러 꼬리면 'cut+blur_tail')를 적고 줄판독 transition 에 옮긴다. 규칙 밖 사건(경계 없음)은 눈으로 추가."}
    (out / f"{vid}_trans.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug")
    ap.add_argument("src_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--ids")
    A = ap.parse_args(argv)
    ids = A.ids.split(",") if A.ids else sorted(p.stem for p in (ROOT / f"channel/{A.slug}/줄판독").glob("*.json"))
    for vid in ids:
        if not (Path(A.src_dir) / f"{vid}.mp4").exists():
            print("원본 없음", vid)
            continue
        d = sheet(A.slug, A.src_dir, A.out_dir, vid)
        diff = sum(1 for b in d["boundaries"] if b["now"] not in (b["draft"], "(줄 없음)") and not (b["now"] == "none" and b["draft"] == "cut"))
        print(vid, "경계", len(d["boundaries"]), "초안≠지금", diff, d["sheets"][:1], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
