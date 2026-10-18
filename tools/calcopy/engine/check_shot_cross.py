# -*- coding: utf-8 -*-
"""완성본 컷이 원본 영상의 샷 경계를 넘어 옆 장면이 섞였나 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/engine/check_shot_cross.py <make 폴더> [...]

왜: 썰템쇼 10편을 박창수(느린 말)로 다시 만들자 컷이 길어져, 원본 샷에 딱 맞춰 고른 컷이 다음 샷 0.1~0.4초를 끌고 들어왔다
(작품6 52.06~53.36 ← 샷 52.05~53.19). B13(중복)·B16(되감김·점프줌)은 이걸 못 잡는다 — 워커 넷이 눈으로만 찾았다.
재는 법: make/timeline.json groups(src·ss·dur) → 그 소스 구간을 ffmpeg scene>0.25 로 훑어 컷 안쪽(앞뒤 0.04초 뺌)에 샷 경계가 있으면 걸림.
판정: 컷 앞머리·꼬리에 옆 샷이 0.4초 미만 끼면 걸림(가운데 경계는 일부러 이은 컷). 꼬리만이면 같은 샷 안으로 당긴 ss 를 제안.
짤(meme:)은 뺀다(짤 자체 편집). 걸린 컷이 있으면 rc 1.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TH = 0.25
EDGE = 0.04
HIST_MIN = 0.2              # 묶음 앞뒤 색 분포 거리 — 이 미만이면 같은 샷(움직임)
FLASH = 0.4                 # 이보다 짧게 끼는 옆 샷 = 번쩍(눈에 띈다)


def shot_cuts(src: Path, a: float, b: float) -> list[float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{max(0, a - 0.2):.3f}", "-t", f"{b - a + 0.4:.3f}", "-i", str(src),
                        "-vf", f"select='gt(scene,{TH})',showinfo", "-an", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    base = max(0, a - 0.2)
    ts = [round(base + float(x), 2) for x in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    # scene 점수는 같은 샷 안 반복 무늬 움직임(작품2 컨베이어 소시지: 0.07초마다 10개)도 잡는다 → 0.2초 안에 붙은 감지를 한 묶음으로 보고,
    # 묶음 앞뒤 색 분포 거리가 HIST_MIN 미만이면 샷 경계가 아니다(10-18 실측: 컨베이어 0.09 / 진짜 경계 0.38~1.41)
    out, grp = [], []
    for t in ts + [None]:
        if grp and (t is None or t - grp[-1] > 0.2):
            if _hist_dist(src, grp[0] - 0.06, grp[-1] + 0.06) >= HIST_MIN:
                out += grp
            grp = []
        if t is not None:
            grp.append(t)
    return out


def _hist_dist(src: Path, t0: float, t1: float) -> float:
    import numpy as np

    def h(t):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", str(src), "-frames:v", "1", "-vf", "scale=64:36",
                              "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, np.uint8).reshape(-1, 3)
        v = np.concatenate([np.histogram(x[:, c], 16, (0, 256))[0] for c in range(3)]).astype(float)
        return v / max(1.0, v.sum()) * 3
    return float(np.abs(h(t0) - h(t1)).sum() / 2)


def check(make: Path) -> list[dict]:
    d = json.loads((make / "timeline.json").read_text(encoding="utf-8"))
    out = []
    for g in d["groups"]:
        if str(g["src"]).startswith("meme:"):
            continue
        a, b = float(g["ss"]), float(g["ss"]) + float(g.get("src_span") or g["dur"])   # 늘린 컷은 원본에서 쓴 길이만
        src = make.parent / g["src"]
        inside = [t for t in shot_cuts(src, a, b) if a + EDGE < t < b - EDGE]
        # 번쩍 = 컷 앞머리나 꼬리에 다른 샷이 FLASH 초 미만 끼는 것. 가운데 경계(양쪽 다 FLASH 이상)는 일부러 여러 샷을 잇는 컷으로 본다
        head = bool(inside) and inside[0] - a < FLASH
        tail = bool(inside) and b - inside[-1] < FLASH
        fix = None
        if tail and not head:       # 같은 샷 안에서 앞으로 당기기 — 당긴 자리에 앞 경계가 없어야 한다
            ns = round(inside[-1] - (b - a) - 0.05, 2)
            if ns >= 0 and not [t for t in shot_cuts(src, ns, ns + (b - a)) if ns + EDGE < t < ns + (b - a) - EDGE]:
                fix = ns
        out.append({"src": g["src"], "ss": round(a, 2), "end": round(b, 2), "t0": g["t0"], "pieces": g["pieces"], "cross": inside,
                    "flash": head or tail, "head": head, "tail": tail, "fix_ss": fix})
    return out


if __name__ == "__main__":
    rc = 0
    for m in sys.argv[1:]:
        rows = check(Path(m))
        bad = [r for r in rows if r["flash"]]
        rc |= bool(bad)
        print(f"== {m} → {'○' if not bad else f'× 옆 샷 번쩍 컷 {len(bad)}'} (가운데 경계만 있는 컷 {sum(1 for r in rows if r['cross'] and not r['flash'])}개는 통과)")
        for r in bad:
            where = "앞" if r["head"] else "" + ("뒤" if r["tail"] else "")
            print(f"  영상 {r['t0']:6.2f}초 토막 {r['pieces']} {r['src']} {r['ss']}~{r['end']} ← 경계 {r['cross']} ({where}) 제안 ss {r['fix_ss']}")
    sys.exit(1 if rc else 0)
