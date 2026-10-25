# -*- coding: utf-8 -*-
"""해외원본형(잇템로그 꼴) 재료 초안 — 원본별 시간순·같은 구간 재사용 0·확대 1.0·박힌 글자 표시 구간표 (관제 263 지시서 08 · 표준 §3-3 C2).

옛 자리: 세션 scratchpad `mk_v3_*.py` 11벌(10-22~24 잇템로그 v3 — 편마다 손으로 CROP·컷 시각·see 를 적은 파이썬). 그중 **기계로 정할 수 있는 것**만 여기로:
  · 확대 1.0 칸 = 원본 안에 창 비율로 들어가는 가장 큰 칸(rules.fit_height — 세로 쇼츠 원본은 폭 전체 × 창 비율 높이)
  · 쓸 수 있는 구간 = 원본 샷 표(카메라 바뀌는 곳 — yanshot.plan.shots_in) 중 다른 제품(other_product)·주인공 없는 남(other) 샷을 뺀 것, 원본별 시간순
  · 박힌 글자 = 샷 판독 text 상자 — 지운 파일(clean)이면 그대로, 아니면 '흐림'(엔진 rules.text_blur_all 이 재료.blur 를 채운다)
판단(어느 줄에 어느 구간·see·훅 장면)은 Claude 가 한다 — 회원 흐름 = flow.py 해외원본형 대본 질문(이 초안을 같이 준다) · 우리 PC = 아래 CLI 결과를 대본 쓰는 세션이 읽는다.

    PYTHONUTF8=1 py tools/calcopy/ititemlog_make.py draft --src <원본 폴더> --files d2.mp4,mkA.mp4 --version 잇템로그판_v2 [--shots 샷표.json] [--cleaned mkA.mp4] --out <재료_초안.json>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

MIN_SEG = 0.8          # 이보다 짧은 샷은 컷으로 못 쓴다(판 B 컷 ≥1.2초 — 이웃 샷과 이어 쓰는 것은 대본 쪽 판단)
NO_SHOT_STEP = 2.0     # 샷 표가 없을 때 구간을 이 길이로 나눈다


def fit_crop(sw: int, sh: int, ar: float) -> list:
    """확대 1.0 칸 [x, y, w, h](원본 픽셀, 가운데) — 높이는 rules.fit_height(주인 한 곳)."""
    from tools.calcopy.hybrid import rules as RU
    cw = min(sw, int(round(sh * ar)))
    ch = int(round(RU.fit_height(sw, sh, ar)))
    cw, ch = cw // 2 * 2, ch // 2 * 2
    return [(sw - cw) // 2, (sh - ch) // 2, cw, ch]


def draft(files: list[dict], shots: dict, ar: float, cleaned: list | None = None) -> dict:
    """files = [{name, w, h, dur}](시간순 — 원본 순서) · shots = {파일 줄기: [{i,a,b,who,product,other_product,text,desc}]} · ar = 판 창 가로/세로.
    반환 = {order, crop{이름: [x,y,w,h]}, segments{이름: [{a,b,dur,who,product,text,desc}]}, rules}. 같은 구간 재사용 0 은 대본이 앞에서부터 쓰면 지켜진다."""
    cleaned = set(cleaned or [])
    out = {"made_by": "tools/calcopy/ititemlog_make.draft", "order": [f["name"] for f in files], "crop": {}, "segments": {},
           "rules": "원본 순서대로·각 원본 안에서는 시간순으로 앞에서부터 쓴다(훅만 결과 먼저 — 판) · 같은 구간 두 번 금지 · 끝 줄은 앞에서 안 쓴 구간 · "
                    "crop 은 이 칸 그대로(확대 1.0) · text=흐림 구간은 엔진이 재료.blur 를 채운다(crop 으로 피하지 않는다)"}
    for f in files:
        name, sw, sh, dur = f["name"], int(f.get("w") or 0), int(f.get("h") or 0), float(f.get("dur") or 0)
        if not (sw and sh):
            continue
        out["crop"][name] = fit_crop(sw, sh, ar)
        rows = shots.get(name.rsplit(".", 1)[0]) or []
        if not rows:                                   # 샷 표 없음 — 고른 간격 구간(판독 없음 표시)
            rows = [{"i": k, "a": round(k * NO_SHOT_STEP, 2), "b": round(min(dur, (k + 1) * NO_SHOT_STEP), 2), "who": "?"}
                    for k in range(int(dur // NO_SHOT_STEP) + (1 if dur % NO_SHOT_STEP > 0.3 else 0))]
        segs = []
        for s in sorted(rows, key=lambda x: float(x["a"])):
            a, b = float(s["a"]), float(s["b"])
            if b - a < MIN_SEG or s.get("other_product") or s.get("who") == "other":
                continue
            segs.append({"a": round(a, 2), "b": round(b, 2), "dur": round(b - a, 2), "who": s.get("who"), "product": bool(s.get("product")),
                         "text": ("지움" if name in cleaned else "흐림") if s.get("text") else "", "desc": s.get("desc", "")})
        out["segments"][name] = segs
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("draft")
    d.add_argument("--src", required=True); d.add_argument("--files", required=True); d.add_argument("--version", required=True)
    d.add_argument("--shots"); d.add_argument("--cleaned", default=""); d.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    from tools.calcopy.hybrid import styles as STY
    from tools.calcopy.hybrid.common import probe
    _, _, ww, wh = STY.load(a.version)["frame"]["window"]
    files = []
    for n in [x for x in a.files.split(",") if x]:
        w, h, du = probe(Path(a.src) / n)
        files.append({"name": n, "w": w, "h": h, "dur": round(du, 2)})
    if a.shots:
        shots = json.loads(Path(a.shots).read_text(encoding="utf-8"))
    else:                                              # 판독 없이 카메라 바뀌는 곳만(누가·글자 칸 없음) — 판독은 Claude 몫
        from tools.calcopy.yanshot.plan import shots_in
        shots = {f["name"].rsplit(".", 1)[0]: [{"i": i, "a": round(x, 3), "b": round(y, 3)} for i, (x, y) in enumerate(shots_in(Path(a.src) / f["name"], [(0.0, f["dur"])]))]
                 for f in files}
    res = draft(files, shots, ww / wh, [x for x in a.cleaned.split(",") if x])
    Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: (len(v) if isinstance(v, dict) else v) for k, v in res.items() if k != "rules"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
