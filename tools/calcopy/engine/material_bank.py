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
    PYTHONUTF8=1 py tools/calcopy/engine/material_bank.py place <bank 폴더> <작품 폴더> <프리셋 폴더 | 판 이름>
        (판 이름이면 render_bench 꼴로 <작품>/<판>/대본.json·재료.json, 프리셋 폴더면 preset_make 꼴 <작품>/재료.json)
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STEP = 0.5          # 칸 간격(초) — 1초 컷을 대사에 맞춰 고르려면 0.5초(material_auto 10-18 '5초 간격은 성겼다')
CELL = 160
COLS = 8
ABA_NEAR = 10.0     # A-B-A 끼움 '같은 장면' 거리(초) — preset 잇썸홈 manifest checks.aba_same_scene_s(페이블 10-17) 와 같은 값. 판(render_bench) 길은 이 값
MERGE_CHARS = 7     # 이 글자 수 이하 조각은 다음 조각과 한 컷 — 관문 ⑤(컷 ≥0.4초) · 벤치 컷 중앙 1.07초 > 자막 조각 0.9초(자막 교체 중 같은 샷 안 39/119, 스타일분석 §1) — 10-26 5 로는 완성본 컷 중앙 0.90(재현 자 −16%, 빠른 쪽 허용 −15% 밖) → 7
HOOK_MERGE_CHARS = 4    # 훅(첫 줄)은 관문 ⑤(0.4초 ≈ 3.4자)만 지키는 최소 묶음 — 10-26 7 로 묶으니 훅 0.1~3초 컷 경계 1(판 ≥2)로 rhythm_gate 멈춤
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


PROBLEM = "문제:"     # 문제 상태 동작 이름 머리(예 '문제: 물 고임') — 태그 state 'problem' 구간


def is_problem(seg: dict) -> bool:
    """문제 상태 구간 — 제품이 나오기 전 '불편'(고인 물·머리카락 뭉치 등). 다른 제품이 보이면 안 된다(product none 만)."""
    return seg.get("state") == "problem" and seg.get("product") == "none"


def usable(seg: dict) -> bool:
    """(판단 주인 — 창고 구간을 컷 재료로 쓸 수 있나) 남의 글자 없음 · 동작 이름 있음 · (같은 제품 | 문제 상태).
    10-26 두유노판 상위 10편 대조: 사연 줄(막힘·혼남)이 말한 상태가 화면에 없어 장면 ○ 0.5 < 상위 중앙 0.75 →
    제품 없는 '문제 상태' 구간(state problem · product none · 동작 이름 '문제: …')도 재료로 쓴다. 다른 제품(other)은 계속 안 쓴다."""
    if seg.get("text") or not seg.get("act"):
        return False
    if is_problem(seg):
        return str(seg["act"]).startswith(PROBLEM)
    return seg.get("product") == "same"


def story_visible(S: dict, segs: list[dict], rule: dict | None) -> list[str]:
    """(판단 주인 — 사연 줄이 보이는 상태로 쓰였나, 렌더 전) 판 script.scene_rule {story_slots, min_problem_pieces}:
    그 칸(slot) 줄마다 조각 동작 첫 자리가 '문제: …'(창고에 있는 동작)인 조각이 min 개 이상. 모자라면 사유 목록(place 가 멈춘다)."""
    if not rule:
        return []
    have = {s["act"] for s in segs if is_problem(s)}
    bad = []
    for li, L in enumerate(S.get("lines") or []):
        if L.get("slot") not in (rule.get("story_slots") or []):
            continue
        firsts = [(pc["act"] if isinstance(pc["act"], list) else [pc["act"]])[0] for pc in L.get("pieces") or []]
        n = sum(1 for a in firsts if a in have)
        if n < int(rule.get("min_problem_pieces", 1)):
            bad.append(f"줄{li + 1}({L.get('slot')}) 문제 상태 조각 {n} < {rule.get('min_problem_pieces', 1)} — 사연을 화면에 보이는 상태로 쓰고 "
                       f"그 조각 동작 첫 자리를 창고의 문제 상태({sorted(have) or '없음 — 창고에 문제 상태 영상 태그 필요'})로")
    return bad


def acts(bank: Path) -> dict:
    """동작별 쓸 수 있는 구간 목록 → <bank>/acts.md (대본은 이 목록을 보고 쓴다)."""
    out: dict = {}
    for s in _tags(bank):
        if usable(s):
            out.setdefault(s["act"], []).append(s)
    lines = ["# 장면 창고 — 동작별 쓸 수 있는 구간(같은 제품 또는 '문제:' 문제 상태(제품 없음) · 남의 글자 없음)", ""]
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
    board = None if (Path(pdir) / "manifest.json").exists() else str(pdir)     # 판 이름(render_bench 길) | 프리셋 폴더(preset_make 옛 길)
    if board:
        from tools.calcopy.hybrid import styles as ST
        st = ST.load(board)
        W, H = 1080, 1920
        cps = float(st["cps_target"])
        adj = bool((st.get("reuse") or {}).get("adjacent_run"))
        near = ABA_NEAR
    else:
        M = json.loads((Path(pdir) / "manifest.json").read_text(encoding="utf-8"))
        cfg = M["channel_rules"]["make"]
        W, H = cfg["window"]
        cps = float(cfg["cps"])
        adj = bool((cfg.get("reuse") or {}).get("adjacent_run"))
        near = float((cfg.get("checks") or {}).get("aba_same_scene_s", ABA_NEAR))
    if board:
        from tools.calcopy.hybrid.checks import aba_violations
        aba_of = aba_violations            # render_bench 길 완성본 관문(quality_gate B16)과 같은 판정 — 거리 상관없이 X→Y→X
    else:
        aba_of = lambda cs: aba_list(cs, near)  # noqa: E731
    S = json.loads((work / "대본.json").read_text(encoding="utf-8"))
    segs = [s for s in _tags(bank) if usable(s)]
    sv = story_visible(S, segs, (st.get("script") or {}).get("scene_rule") if board else None)
    if sv:
        for m in sv:
            log("⚠ [place] " + m)
        return {"ok": False, "miss": sv, "shots": []}
    lens = {n: x["dur"] for n, x in B["videos"].items()}
    P, t = [], 0.0                      # 조각마다 화면 시각(글자÷cps 어림 × 여유) — 고르는 순서와 상관없이 먼저 정한다
    for li, L in enumerate(S["lines"]):
        j = 0
        pcs = L["pieces"]
        while j < len(pcs):
            k = j + 1
            lim = MERGE_CHARS if li else HOOK_MERGE_CHARS       # 훅 줄은 덜 묶는다 — 판 rhythm.hook_cuts_3s(0.1~3초 컷 경계 ≥2, 벤치 중앙 2.5)
            while k < len(pcs) and nchar(" ".join(x["text"] for x in pcs[j:k])) <= lim:   # 짧은 조각은 다음 조각과 한 컷(관문 ⑤ 컷 ≥0.4초)
                k += 1
            grp = pcs[j:k]
            text = " ".join(x["text"] for x in grp)
            d = round(max(1, round(nchar(text) / cps * FPS)) / FPS * SLACK, 3)     # preset_make 계획 어림(글자÷cps) × 여유(진짜 목소리가 더 길 수 있다)
            a = grp[-1]["act"]
            want = a if isinstance(a, list) else [a]                                # 묶음 = 마지막 조각의 동작(짧은 앞 조각은 연결 말)
            P.append({"i": len(P), "li": li, "text": text, "d": d, "t0": t, "want": want, "j": j, "n": len(grp),
                      "room": sum(x["b"] - x["a"] for x in spans(segs, want))})
            t += d
            j = k
    got: dict = {}                      # 조각 번호 → (cut, seg)
    used: dict = {}
    for q in sorted(P, key=lambda q: (q["room"], q["i"])):      # 재료가 적은 동작의 조각부터(앞 조각이 귀한 장면을 먼저 먹지 않게)
        placed = [c for c, _ in got.values()]
        base = reuse_violations_bench(placed, lens, adj)
        aba0 = aba_of(sorted(placed, key=lambda c: c["t0"]))
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
                if [x for x in aba_of(sorted(placed + [cut], key=lambda c: c["t0"])) if x not in aba0]:    # A-B-A 끼움 = 그 길의 관문 판정(판 = quality_gate B16 checks.aba_violations · 프리셋 = preset_make A12 aba_list)
                    continue
                cont = (prev is not None and prev[0]["src"] == s["v"] and 0 <= ss - (prev[0]["ss"] + prev[0]["dur"]) <= 0.6) or                        (nxt is not None and nxt[0]["src"] == s["v"] and 0 <= nxt[0]["ss"] - (ss + d) <= 0.6)
                if q["li"]:
                    score = (q["want"].index(s["act"]), 0 if cont else 1, used.get((s["act"], s["v"]), 0), ss - s["a"])   # 대본이 먼저 적은 동작 > 이어짐 > 덜 쓴 영상 > 앞쪽
                else:     # 훅 줄 = 옆 컷과 다른 영상이 먼저(판 rhythm.hook_cuts_3s) — 10-26 6판: 같은 영상 다른 샷(흰 세면대 근접↔멀리)은 완성본 컷 경계(kal_analyze.media_of)에 안 잡혀 훅 경계 1 < 2
                    near_same = any(n is not None and n[0]["src"] == s["v"] for n in (prev, nxt))
                    score = (1 if near_same else 0, q["want"].index(s["act"]), used.get((s["act"], s["v"]), 0), ss - s["a"])
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
        row = {"caption": q["text"], "src": Path(v["path"]).name, "ss": round(cut["ss"], 3), "kind": "situation" if is_problem(s) else "product", "seen": f"{s['act']} — {s.get('see', '')}",
               "li": q["li"], "j": q["j"], "n": q["n"], "wh": [v["w"], v["h"]]}
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
    cand_dir = str(cand.pop()).replace("\\", "/")
    if board:
        emit_bench(S, shots, cand_dir, work / board, W, H, log)
    else:
        rows = []
        for r in shots:       # preset_make 꼴 = 조각마다 한 행 — 묶음의 뒤 조각은 이어감('+')
            caps = [pc["text"] for pc in S["lines"][r["li"]]["pieces"]][r["j"]:r["j"] + r["n"]] if "li" in r else [r["caption"]]
            rows.append({**{k: v for k, v in r.items() if k not in ("li", "j", "n", "wh")}, "caption": caps[0]})
            rows += [{"caption": c, "src": "+"} for c in caps[1:]]
        R = {"cand_dir": cand_dir, "made_by": "material_bank.place v1(관제 269 순서)", "shots": rows}
        (work / "재료.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[place] 컷 {len(shots)} → {work / '재료.json'}")
    return {"ok": True, "shots": shots}


def emit_bench(S: dict, shots: list[dict], cand_dir: str, doc: Path, W: int, H: int, log=print):
    """render_bench 꼴로 <작품>/<판>/대본.json·재료.json — 줄 id L<n>, 자막 덩어리 = 대본 조각, 컷 = 조각마다 하나(cap j = 그 덩어리가 뜨는 순간, render_bench.timeline).
    크롭 = 창 비율(W:H) 원본 높이 그대로(확대 1.0 — 메모리 '확대 1.0·원본 글자는 흐림'), 가로 원본은 태그 cx 쪽(_crop_x)."""
    doc.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in S.items() if k not in ("lines", "preset")}
    from tools.calcopy.hybrid import styles as ST
    vo = ST.load(doc.name)["voice"]
    keep["voice"] = {k: vo[k] for k in ("name", "voice_id", "tempo") if k in vo}     # 판 voice(tempo 포함 — render_bench 는 판에서 name·voice_id 만 옮긴다)
    lines = []
    for li, L in enumerate(S["lines"]):
        strip = bool((ST.load(doc.name).get("caption") or {}).get("strip_punct"))     # 판 caption.strip_punct — 자막 덩어리 끝 마침표·쉼표 뺌(읽는 글은 그대로)
        caps = [re.sub(r"[.,]+$", "", pc["text"]) if strip else pc["text"] for pc in L["pieces"]]
        d = {"id": f"L{li + 1}", "kind": "tts", "tts": L.get("tts") or L["text"], "text": " ".join(caps) if strip else L["text"], "caps": caps}
        for k in ("slot", "point", "answer_at", "facts"):
            if k in L:
                d[k] = L[k]
        lines.append(d)
    cuts: dict = {}
    for r in shots:
        sw, sh = r["wh"]
        cw = min(sw, int(sh * W / H) // 2 * 2)
        x = r.get("crop_x", (sw - cw) // 2)
        cuts.setdefault(f"L{r['li'] + 1}", []).append({"src": r["src"], "ss": r["ss"], "crop": [int(x), 0, int(cw), int(sh)], "cap": r["j"], "see": r["seen"]})
    (doc / "대본.json").write_text(json.dumps({**keep, "lines": lines, "made_by": "material_bank.emit_bench(원본 = ../대본.json)"}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (doc / "재료.json").write_text(json.dumps({"cand_dir": cand_dir, "made_by": "material_bank.place v1(관제 269 순서)", "cuts": cuts, "blur": {}},
                                             ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    log(f"[place] render_bench 꼴 → {doc}")


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
