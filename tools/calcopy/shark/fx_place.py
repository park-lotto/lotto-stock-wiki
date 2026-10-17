# -*- coding: utf-8 -*-
"""샥탬스토리 꾸밈 자리 제안 — 대본 줄 박자(fn)로 벤치 QMJ 와 같은 박자·같은 대상에 꾸밈을 놓는다 (관제 097, 2026-10-18).

(판단 주인: 어느 줄에 어떤 꾸밈) propose() 한 곳. 박자 낱말·기본 자리는 rules.json placement. 좌표(얼굴·제품)는 편마다 눈으로 고쳐
재료.json effects 에 쓴다(how='hand' 표시된 꾸밈은 다시 쓰지 않는다).

    PYTHONUTF8=1 py tools/calcopy/shark/fx_place.py <편 폴더> <작업 폴더> [--write]   # 제안 표 + 1차 완성본 그 시각 프레임 시트(<작업>/fx_place.jpg)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.calcopy.shark.caption_style import rules  # noqa: E402


def beat(fn: str) -> str:
    P = rules()["placement"]["beats"]
    for k, words in P.items():
        if any(w in (fn or "") for w in words):
            return k
    return "기타"


def propose(S: dict, info: dict) -> list[dict]:
    """줄 박자 → 꾸밈 목록[{line, kind, at, t, color?, why}]. t 는 줄 안 시각(렌더러 effects 가 완성본 시각으로 바꿈)."""
    PL = rules()["placement"]
    L = S["final"]["lines"]
    li = {x["id"]: x for x in info["lines"]}
    caps = {}
    for c in info["captions"]:
        caps.setdefault(c["line"], []).append(c)
    cuts = {}
    for c in info["cuts"]:
        if not c.get("dropped"):
            cuts.setdefault(c["line"], []).append(c)
    kind = {l["id"]: ("O" if l.get("kind") in ("orig", "원음") else "N") for l in L}
    bt = {l["id"]: beat(l.get("fn")) for l in L}
    out, used = [], set()

    def add(line, k, why, t=None, at=None, **kw):
        x = li[line]
        out.append({"line": line, "kind": k, "at": at or PL["at"][k], "t": t or [0.0, round(x["t1"] - x["t0"], 3)], "why": why, **kw})
        used.add((line, k))

    first = L[0]["id"]
    add(first, "red_circle", "벤치 0초 결말 반응 얼굴 빨간 원(첫 컷 내내) — 얼굴 자리는 눈으로", t=[0.0, round(cuts[first][0]["t1"] - li[first]["t0"], 3)])
    demo = [l["id"] for l in L if bt[l["id"]] == "시연" and kind[l["id"]] == "N"]
    if demo:
        add(demo[0], "arrow_green_down", "벤치 0.567~1.267 둘째 컷 제품 위 초록 아래 화살표 — 제품 자리는 눈으로", t=[0.0, 0.7])
    pain = [l["id"] for l in L if bt[l["id"]] == "불편"]
    if pain:
        p = next((x for x in pain if kind[x] == "O"), pain[0])
        d = li[p]["t1"] - li[p]["t0"]
        add(p, "dashed_circle", "벤치 9.3~11.6 기존 불편 장면 빨간 점선 원(돌며)", t=[0.2, round(min(d, 3.7), 3)])
        if d > 2.5:
            add(p, "flash", "벤치 11.2 불편 줄 빨강 번쩍", t=[round(min(d - 0.5, 3.0), 3), round(min(d, 3.45), 3)], color="빨강")
    num = re.compile(r"[0-9]")
    for l in L:   # 분홍 위 화살표 = 숫자 박자 줄의 숫자 조각 하나(벤치 12.017 '수십키로')
        if bt[l["id"]] == "숫자":
            c = next((c for c in caps.get(l["id"], []) if num.search(c["text"])), None)
            if c:
                x = li[l["id"]]
                add(l["id"], "arrow_pink_up", f"벤치 12.017~13.82 숫자 조각 분홍 위 화살표 — '{c['text']}'",
                    t=[round(c["t0"] - x["t0"], 3), round(min(c["t1"] - x["t0"], c["t0"] - x["t0"] + 1.8), 3)])
                break
    if len(demo) >= 2:
        d2 = demo[1]
        add(d2, "arrow_curve_red", "벤치 20.367~22.9 해결 장면 빨간 곡선 화살표(찌르기)+휙", t=[0.0, round(min(2.5, li[d2]["t1"] - li[d2]["t0"]), 3)])
    money = re.compile(PL["money_re"])
    def _offer(beats):
        return next((l["id"] for l in L if kind[l["id"]] == "O" and l["id"] != first and bt[l["id"]] in beats
                     and money.search(" ".join(c["text"] for c in caps.get(l["id"], [])))), None)
    offer = _offer(("제안",)) or _offer(("숫자",))   # 벤치 돈다발 = 투자 제안 금액 줄(매출 숫자 줄보다 먼저 고름)
    if offer:
        add(offer, "flash", "벤치 38.667 투자 제안 컷 초록 번쩍", t=[0.0, 0.45], color="초록")
        add(offer, "money_emoji", "벤치 38.7~40.0 날개 돈다발", t=[0.033, 1.333])
    dec = next((l["id"] for l in L if bt[l["id"]] == "성사" and l["id"] != offer), None)
    if dec:
        add(dec, "flash", "벤치 44.367 결정 빨강 번쩍", t=[0.0, 0.45], color="빨강")
    after = next((l["id"] for l in L if bt[l["id"]] == "결과"), None)
    if after:
        add(after, "flash", "벤치 45.667 거래 성공·결과 초록 번쩍", t=[0.0, 0.45], color="초록")
    # 번쩍이 분당 placement.flash_per_min 아래면 숫자·시연 줄 둘째 컷 시작(벤치 7.1·28.1 = 장면 넘김)에 초록을 보탠다
    dur = info["dur"]
    have = [li[e["line"]]["t0"] + e["t"][0] for e in out if e["kind"] == "flash"]
    for l in L:
        if len(have) / dur * 60 >= PL["flash_per_min"]:
            break
        if bt[l["id"]] in ("숫자", "시연", "불편") and len(cuts.get(l["id"], [])) >= 2:
            t = cuts[l["id"]][1]["t0"]
            if all(abs(t - h) > 3.0 for h in have):
                x = li[l["id"]]
                add(l["id"], "flash", "벤치 7.1·28.1 장면 넘김 초록 번쩍(분당 횟수 채움)", t=[round(t - x["t0"], 3), round(t - x["t0"] + 0.45, 3)], color="초록")
                have.append(t)
    return out


def sheet(final: Path, info: dict, eff: list[dict], dst: Path):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 26)
    li = {x["id"]: x for x in info["lines"]}
    tiles = []
    for e in eff:
        t = li[e["line"]]["t0"] + e["t"][0] + 0.15
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(final), "-frames:v", "1", "-vf",
                            "crop=1080:1052:0:434,drawgrid=w=100:h=100:t=2:c=yellow@0.5,scale=360:351", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           capture_output=True)
        im = Image.frombytes("RGB", (360, 351), r.stdout[:360 * 351 * 3])
        d = ImageDraw.Draw(im)
        x, y = e["at"][0] / 3, (e["at"][1] - 434) / 3
        d.ellipse([x - 8, y - 8, x + 8, y + 8], outline=(255, 0, 255), width=3)
        d.text((4, 2), f"{e['line']} {e['kind']} {t:.1f}", font=font, fill=(255, 255, 0), stroke_width=2, stroke_fill=(0, 0, 0))
        tiles.append(im)
    sh = Image.new("RGB", (360 * 4, 351 * ((len(tiles) + 3) // 4)))
    for i, im in enumerate(tiles):
        sh.paste(im, ((i % 4) * 360, (i // 4) * 351))
    sh.save(dst, quality=85)


def main():
    doc, work = Path(sys.argv[1]), Path(sys.argv[2])
    S = json.loads((doc / "대본.json").read_text(encoding="utf-8"))
    info = json.loads((work / "render" / "render_info.json").read_text(encoding="utf-8"))
    eff = propose(S, info)
    for e in eff:
        print(e["line"], e["kind"], e["t"], e["at"], e.get("color", ""), "—", e["why"])
    sheet(work / "render" / "final.mp4", info, eff, work / "fx_place.jpg")
    print(work / "fx_place.jpg")
    if "--write" in sys.argv:
        p = doc / "재료.json"
        M = json.loads(p.read_text(encoding="utf-8"))
        hand = [e for e in M.get("effects") or [] if e.get("how") == "hand"]
        M["effects"] = hand + [{**e, "how": "auto"} for e in eff if not any(h["kind"] == e["kind"] and h["line"] == e["line"] for h in hand)]
        p.write_text(json.dumps(M, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("재료.json effects", len(M["effects"]))


if __name__ == "__main__":
    main()
