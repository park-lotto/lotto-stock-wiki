# -*- coding: utf-8 -*-
"""장면 창고 → 대본 → 1:1 배치(관제 269 순서 — 사장님 10-25 "장면 모을 때 많은 영상을 처음부터 분석해야 그다음 선별") (관제 097, 2026-10-26).

material_auto 는 대본 먼저 → 줄마다 검색이라 같은 종류 다른 제품이 섞였다(창고판 README: 아이스큐브·옥수수커터). 이 도구는 거꾸로 간다:
  1) scan  : 같은 제품 후보 영상 전부를 0.5초 칸으로 잘라 번호 시트 + 원본 장면 경계(render_bench.shot_starts — 관문 ③과 같은 자)
  2) 태그  : 칸 시트를 **눈으로** 보고(오푸스 — 칼카피_시작 13) <bank>/태그.json 에 구간을 적는다
             {"segments":[{"v": 영상, "a": 초, "b": 초, "product": "same|other|none", "act": "동작 이름", "text": 남의 글자 보임?, "cx": 제품 가로 가운데 0~1, "see": "보이는 것"}]}
  3) acts  : same·글자 없음 구간을 동작별로 모은 장면 목록(acts.md) — **대본은 이 목록을 보고 쓴다**(줄마다 pieces[{text, act}])
  4) place : 대본 조각마다 그 동작 구간에서 컷 하나(조각 1 = 컷 1, 벤치 cut_eq_sub 94%) — 재사용 판정 = quality_gate.reuse_violations_bench(판 reuse.adjacent_run),
             길이 = 조각 글자 ÷ 판 cps(preset_make 계획과 같은 어림), 장면 경계를 넘지 않게(render_bench.shot_starts) → 재료.json(preset_make 가 읽는 꼴)
판단 주인: 구간 고르기(place) = 이 파일 한 곳 · 재사용·장면 경계 = 기존 주인 부르기만 · 눈 판정(태그) = 사람(오푸스) 몫(파일로만 들어온다).

    PYTHONUTF8=1 py tools/calcopy/engine/material_bank.py scan  <bank 폴더> <영상.mp4 …>
    PYTHONUTF8=1 py tools/calcopy/engine/material_bank.py acts  <bank 폴더>
    PYTHONUTF8=1 py tools/calcopy/engine/material_bank.py place <bank 폴더> <작품 폴더> <프리셋 폴더>
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STEP = 0.5          # 칸 간격(초) — 1초 컷을 대사에 맞춰 고르려면 0.5초(material_auto 10-18 '5초 간격은 성겼다')
CELL = 160
COLS = 8
SLACK = 1.15        # 조각 길이 어림 여유 — 진짜 TTS 시각으로 컷이 늘어도 장면 경계·재사용을 안 넘게(남는 건 preset_make fit_shot 몫)
EDGE = 0.1          # 장면 경계에서 이만큼 띄운다(경계 번쩍임 — render_bench.snap_ss 가 또 맞춘다)


def _probe(p: Path) -> tuple[int, int, float]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(p)],
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    j = json.loads(r.stdout)
    return int(j["streams"][0]["width"]), int(j["streams"][0]["height"]), float(j["format"]["duration"])


def scan(bank: Path, videos: list[Path], log=print) -> dict:
    """영상마다 0.5초 칸 그림 + 번호·초 시트 + 장면 경계 → <bank>/bank.json · <bank>/sheets/<영상>_N.jpg."""
    from PIL import Image, ImageDraw, ImageFont
    from tools.calcopy.hybrid.render_bench import shot_starts
    bank = Path(bank)
    (bank / "sheets").mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("C:/Windows/Fonts/malgunbd.ttf", 18)
    B = {"videos": {}}
    for v in videos:
        v = Path(v)
        w, h, d = _probe(v)
        fdir = bank / "frames" / v.stem
        fdir.mkdir(parents=True, exist_ok=True)
        if not list(fdir.glob("*.jpg")):
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(v), "-vf", f"fps=1/{STEP},scale={CELL}:{CELL}:force_original_aspect_ratio=decrease",
                            str(fdir / "%04d.jpg")], check=True, stdin=subprocess.DEVNULL)
        cells = sorted(fdir.glob("*.jpg"))
        st = shot_starts(v)
        sheets = []
        per = COLS * 6
        for s in range(0, len(cells), per):
            part = cells[s:s + per]
            rows = math.ceil(len(part) / COLS)
            sh = Image.new("RGB", (COLS * (CELL + 4), rows * (CELL + 4)), "white")
            dr = ImageDraw.Draw(sh)
            for j, f in enumerate(part):
                k = s + j
                t = round(k * STEP + STEP / 2, 2)
                x, y = (j % COLS) * (CELL + 4), (j // COLS) * (CELL + 4)
                im = Image.open(f).convert("RGB")
                sh.paste(im, (x + (CELL - im.width) // 2, y + (CELL - im.height) // 2))
                new = any(k * STEP <= b < (k + 1) * STEP for b in st)
                dr.rectangle([x, y, x + 64, y + 22], fill="red" if new else "black")      # 빨강 = 이 칸 안에서 새 샷 시작(장면 경계)
                dr.text((x + 3, y + 1), f"{t:.1f}", font=font, fill="yellow")
            p = bank / "sheets" / f"{v.stem}_{s // per + 1}.jpg"
            sh.save(p, quality=85)
            sheets.append(str(p))
        B["videos"][v.stem] = {"path": str(v), "w": w, "h": h, "dur": round(d, 3), "shots": st, "sheets": sheets}
        log(f"[scan] {v.stem} {w}x{h} {d:.1f}초 · 칸 {len(cells)} · 장면 경계 {len(st)} · 시트 {len(sheets)}")
    (bank / "bank.json").write_text(json.dumps(B, ensure_ascii=False, indent=1), encoding="utf-8")
    return B


def _tags(bank: Path) -> list[dict]:
    T = json.loads((Path(bank) / "태그.json").read_text(encoding="utf-8"))
    return T["segments"]


def usable(seg: dict) -> bool:
    """(판단 주인 — 창고 구간을 컷 재료로 쓸 수 있나) 같은 제품 · 남의 글자 없음 · 동작 이름 있음."""
    return seg.get("product") == "same" and not seg.get("text") and bool(seg.get("act"))


def acts(bank: Path) -> dict:
    """동작별 쓸 수 있는 구간 목록 → <bank>/acts.md (대본은 이 목록을 보고 쓴다)."""
    out: dict = {}
    for s in _tags(bank):
        if usable(s):
            out.setdefault(s["act"], []).append(s)
    lines = ["# 장면 창고 — 동작별 쓸 수 있는 구간(같은 제품·남의 글자 없음)", ""]
    for a, ss in sorted(out.items(), key=lambda kv: -sum(x["b"] - x["a"] for x in kv[1])):
        tot = sum(x["b"] - x["a"] for x in ss)
        lines.append(f"## {a} — {len(ss)}구간 · 합 {tot:.1f}초")
        lines += [f"- {x['v']} {x['a']:.1f}~{x['b']:.1f}  {x.get('see', '')}" for x in ss]
        lines.append("")
    (Path(bank) / "acts.md").write_text("\n".join(lines), encoding="utf-8")
    return out


def spans(segs: list[dict], want: list[str], gap: float = 0.25) -> list[dict]:
    """같은 영상·같은 동작 구간들을 이어 붙인 덩어리(사이 틈 ≤ gap — 장면 경계에서 태그를 끊은 자리). 컷이 경계를 가운데서 넘는 건 관문 ③도 허용(양쪽 ≥0.4초)."""
    out = []
    for s in sorted([x for x in segs if x["act"] in want], key=lambda x: (x["v"], x["act"], x["a"])):
        if out and out[-1]["v"] == s["v"] and out[-1]["act"] == s["act"] and s["a"] - out[-1]["b"] <= gap:
            out[-1] = {**out[-1], "b": max(out[-1]["b"], s["b"]), "see": out[-1].get("see", "") + " / " + s.get("see", "")}
        else:
            out.append(dict(s))
    return out


def _crop_x(v: dict, seg: dict, W: int, H: int) -> int | None:
    """가로 원본이면 창 비율 크롭 x(제품 가운데 cx 쪽) — 세로 원본은 None(preset_make 기본 가운데)."""
    cw = min(v["w"], int(v["h"] * W / H) // 2 * 2)
    if cw >= v["w"]:
        return None
    cx = float(seg.get("cx", 0.5)) * v["w"]
    return int(max(0, min(v["w"] - cw, cx - cw / 2)))


def place(bank: Path, work: Path, pdir: Path, log=print) -> dict:
    """대본 조각(lines[].pieces[{text, act}]) 마다 그 동작 구간에서 컷 하나 → <작품>/재료.json.
    고르는 순서: ① 같은 동작 구간 중 조각 길이가 장면 경계 안에 들어가는 자리 ② 이미 놓인 컷과 재사용 위반 0(reuse_violations_bench, 판 adjacent_run)
    ③ 조각이 적은 동작 순서(앞이 먼저) ④ 앞 컷과 같은 영상이면 바로 이어지는 자리(한 동작 이어서 — 판 '가') ⑤ 그 동작에서 가장 덜 쓴 영상 ⑥ 구간 안 앞쪽부터."""
    from tools.calcopy.hybrid.quality_gate import reuse_violations_bench
    from tools.calcopy.hybrid.render_bench import FPS, short_pieces
    from tools.calcopy.engine.preset_make import aba_list, nchar
    bank, work = Path(bank), Path(work)
    B = json.loads((bank / "bank.json").read_text(encoding="utf-8"))
    M = json.loads((Path(pdir) / "manifest.json").read_text(encoding="utf-8"))
    cfg = M["channel_rules"]["make"]
    W, H = cfg["window"]
    cps = float(cfg["cps"])
    adj = bool((cfg.get("reuse") or {}).get("adjacent_run"))
    near = float((cfg.get("checks") or {}).get("aba_same_scene_s", 1e9))
    S = json.loads((work / "대본.json").read_text(encoding="utf-8"))
    segs = [s for s in _tags(bank) if usable(s)]
    lens = {n: x["dur"] for n, x in B["videos"].items()}
    P, t = [], 0.0                      # 조각마다 화면 시각(글자÷cps 어림 × 여유) — 고르는 순서와 상관없이 먼저 정한다
    for li, L in enumerate(S["lines"]):
        for pc in L["pieces"]:
            d = round(max(1, round(nchar(pc["text"]) / cps * FPS)) / FPS * SLACK, 3)     # preset_make 계획 어림(글자÷cps) × 여유(진짜 목소리가 더 길 수 있다)
            want = pc["act"] if isinstance(pc["act"], list) else [pc["act"]]
            P.append({"i": len(P), "li": li, "text": pc["text"], "d": d, "t0": t, "want": want,
                      "room": sum(x["b"] - x["a"] for x in spans(segs, want))})
            t += d
    got: dict = {}                      # 조각 번호 → (cut, seg)
    used: dict = {}
    for q in sorted(P, key=lambda q: (q["room"], q["i"])):      # 재료가 적은 동작의 조각부터(앞 조각이 귀한 장면을 먼저 먹지 않게)
        placed = [c for c, _ in got.values()]
        base = reuse_violations_bench(placed, lens, adj)
        aba0 = aba_list(sorted(placed, key=lambda c: c["t0"]), near)
        prev, nxt = got.get(q["i"] - 1), got.get(q["i"] + 1)
        best = None
        for s in spans(segs, q["want"]):
            v = B["videos"][s["v"]]
            st = v["shots"]
            d = q["d"]
            k0 = math.ceil(s["a"] * FPS)
            k1 = math.floor((min(s["b"], v["dur"] - 0.05) - d) * FPS)
            for k in range(k0, k1 + 1, 3):            # 0.1초 걸음
                ss = k / FPS
                if short_pieces(st, ss, ss + d) or any(abs(ss - b) < EDGE for b in st):   # 장면 경계로 나뉜 짧은 조각(번쩍임) = 관문 ③과 같은 자(render_bench.short_pieces)
                    continue
                cut = {"src": s["v"], "ss": ss, "dur": d, "t0": q["t0"], "t1": q["t0"] + d, "line": f"줄{q['li'] + 1}"}
                if [x for x in reuse_violations_bench(placed + [cut], lens, adj) if x not in base]:
                    continue
                if [x for x in aba_list(sorted(placed + [cut], key=lambda c: c["t0"]), near) if x not in aba0]:    # A12 A-B-A 끼움 = preset_make.aba_list(계획 검사와 같은 판정)
                    continue
                cont = (prev is not None and prev[0]["src"] == s["v"] and 0 <= ss - (prev[0]["ss"] + prev[0]["dur"]) <= 0.6) or                        (nxt is not None and nxt[0]["src"] == s["v"] and 0 <= nxt[0]["ss"] - (ss + d) <= 0.6)
                score = (q["want"].index(s["act"]), 0 if cont else 1, used.get((s["act"], s["v"]), 0), ss - s["a"])   # 대본이 먼저 적은 동작 > 이어짐 > 덜 쓴 영상 > 앞쪽
                if best is None or score < best[0]:
                    best = (score, cut, s)
        if best is not None:
            got[q["i"]] = (best[1], best[2])
            used[(best[2]["act"], best[2]["v"])] = used.get((best[2]["act"], best[2]["v"]), 0) + 1
    shots, miss = [], []
    for q in P:
        if q["i"] not in got:
            miss.append(f"줄{q['li'] + 1} '{q['text']}' 동작 {q['want']} — 쓸 구간 없음(재사용·장면 경계·길이 {q['d']}초)")
            shots.append({"caption": q["text"], "src": None, "act": q["want"]})
            continue
        cut, s = got[q["i"]]
        v = B["videos"][s["v"]]
        row = {"caption": q["text"], "src": Path(v["path"]).name, "ss": round(cut["ss"], 3), "kind": "product", "seen": f"{s['act']} — {s.get('see', '')}"}
        cx = _crop_x(v, s, W, H)
        if cx is not None:
            row["crop_x"] = cx
        shots.append(row)
    placed = [c for c, _ in got.values()]
    if miss:
        for m in miss:
            log("⚠ [place] " + m)
        return {"ok": False, "miss": miss, "shots": shots}
    cand = {Path(B["videos"][n]["path"]).parent for n in {c["src"] for c in placed}}
    if len(cand) != 1:
        raise SystemExit(f"창고 영상이 한 폴더에 있어야 한다(preset_make cand_dir 하나): {cand}")
    R = {"cand_dir": str(cand.pop()).replace("\\", "/"), "made_by": "material_bank.place v1(관제 269 순서)", "shots": shots}
    (work / "재료.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[place] 컷 {len(shots)} → {work / '재료.json'}")
    return {"ok": True, "shots": shots}


def main() -> int:
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    if a[0] == "scan":
        scan(Path(a[1]), [Path(x) for x in a[2:]])
    elif a[0] == "acts":
        for k, v in acts(Path(a[1])).items():
            print(k, len(v), round(sum(x["b"] - x["a"] for x in v), 1))
    elif a[0] == "place":
        r = place(Path(a[1]), Path(a[2]), Path(a[3]))
        return 0 if r["ok"] else 1
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
