# -*- coding: utf-8 -*-
"""판 rhythm.plain_share · photo_share_max 실측 — 벤치 줄판독(channel/<slug>/줄판독/*.json)에서 잰다(표준 §4-1 '그 채널 벤치 실측 + why').
정의는 잇템로그판·키치잇판과 같다:
  plain_share     = 꾸밈 없는 덩어리(kal_analyze._decorated 가 모두 False) ÷ 덩어리 수 — 모은 값, 허용 = 편별 값의 모은 값에서 최대 거리
  photo_share_max = '사진·화보' 줄(scene·scene_desc·notes) 초 ÷ 길이, 편별 값의 p75
10-29 샥탬판·숏템리폿판(옛 길 → 볼케이노 전환)에 두 값이 없어 회원 완성본 검사가 '측정 실패'로 멈췄다.

  cut_median      = 벤치 원본 편별 컷 길이 중앙(kal_analyze.media_of — 관문·재현과 같은 자)의 중앙, max = 가장 느린 편
  hook_cuts_3s    = 0.1~3.0초 안 컷 경계 수, min = 벤치 가장 적은 편(사장님 10-26 '벤치가 못 넘는 문턱은 빡빡')
  PYTHONUTF8=1 py tools/calcopy/hybrid/rhythm_measure.py <slug>           # 값·why 출력(판 파일은 안 바꾼다)
  PYTHONUTF8=1 py tools/calcopy/hybrid/rhythm_measure.py <slug> --media   # + 컷 두 칸(벤치 원본을 C:/숏템_칼카피/<slug>/src 에 받아 잰다)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine.kal_analyze import _decorated  # noqa: E402

PHOTO = re.compile(r"사진|화보")
DECO = ("enter_fx", "emph", "sticker", "variant")


def measure(slug: str) -> dict:
    per, tot_n, tot_plain = {}, 0, 0
    for f in sorted((ROOT / "channel" / slug / "줄판독").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        L = [l for l in d.get("lines") or [] if str(l.get("text") or "").strip()]
        if not L:
            continue
        plain = sum(1 for l in L if not any(_decorated(l)[k] for k in DECO))   # 효과음은 뺀다(placement._is_deco 와 같은 칸)
        dur = float(d.get("dur") or max(float(l.get("t1") or 0) for l in L) or 1)
        ph = sum(max(0.0, float(l.get("t1") or 0) - float(l.get("t0") or 0)) for l in d.get("lines") or []
                 if PHOTO.search(" ".join(str(l.get(k) or "") for k in ("scene", "scene_desc", "notes"))))
        per[f.stem] = {"plain": round(plain / len(L), 3), "n": len(L), "photo": round(ph / dur, 3)}
        tot_n += len(L); tot_plain += plain
    if not per:
        raise SystemExit(f"channel/{slug}/줄판독 이 비었다")
    v = round(tot_plain / tot_n, 3)
    tol = round(max(abs(p["plain"] - v) for p in per.values()) + 0.005, 3)
    ph = sorted(p["photo"] for p in per.values())
    p75 = round(ph[min(len(ph) - 1, int(round(0.75 * (len(ph) - 1))))], 3)
    ids = " · ".join(f"{k[:4]} {p['plain']}" for k, p in per.items())
    phs = " · ".join(f"{k[:4]} {p['photo']}" for k, p in per.items())
    return {"plain_share": {"v": v, "tol": tol, "why": f"벤치 {len(per)}편 줄판독 덩어리 {tot_n}개 중 꾸밈 없는 것(kal_analyze._decorated 빈 줄 = placement._is_deco 와 같은 칸) "
                                                  f"{tot_plain}개 = {v}(편별 {ids}). 허용 ±{tol} = 모은 값에서 편별 최대 거리(벤치 편이 다 들어오는 폭) — rhythm_measure.py"},
            "photo_share_max": {"v": p75, "why": f"벤치 {len(per)}편 줄판독 scene/scene_desc/notes '사진·화보' 줄 초 ÷ 길이(키치잇·잇템로그판과 같은 정의) = {phs} → p75 {p75} — rhythm_measure.py"}}


def measure_media(slug: str) -> dict:
    import shutil
    import statistics
    import subprocess
    from tools.calcopy.engine.kal_analyze import media_of
    src = Path("C:/숏템_칼카피") / slug / "src"
    src.mkdir(parents=True, exist_ok=True)
    per = {}
    for f in sorted((ROOT / "channel" / slug / "줄판독").glob("*.json")):
        vid, mp4 = f.stem, src / f"{f.stem}.mp4"
        if not mp4.exists():
            subprocess.run([shutil.which("yt-dlp") or "yt-dlp", "-q", "-f", "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4",
                            "-o", str(mp4), f"https://www.youtube.com/watch?v={vid}"], timeout=300)
        if not mp4.exists():
            raise SystemExit(f"벤치 원본을 못 받았다: {vid}")
        m = media_of(str(mp4))
        per[vid] = {"med": m["cut_median"], "hook": sum(1 for t in m["cut_at"] if 0.1 <= t <= 3.0)}
    meds = [p["med"] for p in per.values() if isinstance(p["med"], (int, float))]
    v, mx = round(statistics.median(meds), 2), max(meds)
    hooks = [p["hook"] for p in per.values()]
    return {"cut_median": {"v": v, "max": mx, "why": f"벤치 {len(per)}편 원본 컷 길이 중앙(kal_analyze.media_of = 관문·재현과 같은 자, {src.as_posix()}) 편별 "
                                                + " · ".join(f"{k[:4]} {p['med']}" for k, p in per.items()) + f" → 중앙 {v}(범위 {min(meds)}~{mx}) · max = 가장 느린 편 — rhythm_measure.py"},
            "hook_cuts_3s": {"min": min(hooks), "why": "벤치 원본 0.1~3.0초 안 컷 경계 수(media_of cut_at): " + " · ".join(f"{k[:4]} {p['hook']}" for k, p in per.items())
                                                      + f" → 중앙 {statistics.median(hooks)} · min {min(hooks)} = 벤치 가장 적은 편(사장님 10-26 '벤치가 못 넘는 문턱은 빡빡') — rhythm_measure.py"}}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    out = measure(sys.argv[1])
    if "--media" in sys.argv:
        out.update(measure_media(sys.argv[1]))
    print(json.dumps(out, ensure_ascii=False, indent=1))
