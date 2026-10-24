# -*- coding: utf-8 -*-
"""장면↔대사 계획 매칭 루프 — 렌더 **전에** 줄마다 후보 컷을 완성본 채점과 같은 함수로 채점해 고른다 (관제 263 지시서 14 · 표준 §12-3).

    PYTHONUTF8=1 py tools/calcopy/hybrid/material_fit.py plan <doc> <work> --version <판> [--apply] [--sign] [--no-supplement] [--floor-hi 7 --floor-lo 5]

판단 주인: 점수 = oneshot/scene_fit.judge_rubric(루브릭 10/7/5/3/1 · 3프레임 띠 · 2회 중앙값) — 완성본 측정(quality_gate)과 **같은 함수**.
  이 파일이 새로 정하는 것 = 후보 만들기(샷 × 처음·가운데·끝)·제약(채점 전 제외)·역할 하한·고르기·루프(최대 3회)·멈춤 사유.
  제약 판정은 주인 함수 그대로 import: 재사용 = quality_gate.reuse_violations_bench · A-B-A = checks.aba_violations ·
  원본 밖 재료 얼굴 = runner_ops._cut_faces · 샷 = yanshot.plan.shots_in · 대사 고침 검사 = script_audit.audit.
흐름: ① 샷 표(원본 샷마다 3프레임 띠) → 샷 설명(소넷 1회/10샷) → 줄마다 후보 샷 순위(글 1회) — 후보 줄이기일 뿐, 점수는 ②
      ② 칸(줄 × 컷 자리)마다 후보 ≤10 → judge_rubric → ③ 역할 하한(본문·공개·증거·반전 ≥7 / 훅·이음·다리·끝 ≥5) 넘는 최고점, 재사용·A-B-A 제약 안에서
      ④ 편 평균 ≥ 목표(상위 편 p75) ∧ 7 미만 비율 ≤ 목표(p25) 이고 하한 미달 0 → 통과. 아니면 (a) 보충 재료 검색(screen.search, 원본 밖은 얼굴 없는 컷만)
         (b) 대사 고침 제안(소넷 — 뜻·어미·글자 수 ±2 유지, script_audit 새 실패 0) → 사인(--sign) → 다시. 최대 3회 → 멈춤(사유: 줄 …).
산출: <doc>/장면대사_계획.json · <doc>/재료_계획.json(재료.json 꼴 + fit·fit_why·cand_n) · --apply 면 <doc>/재료.json 을 덮어씀(옛 것은 재료_사람.json).
대사를 고치면 새 목소리 합성이 필요하다 — 이 파일은 합성하지 않는다(고친 줄 목록 = 장면대사_계획.json fixes, needs_tts).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import ROOT, jload, jsave  # noqa: E402

MAX_ROUNDS = 3            # 표준 §12-3 ④ 최대 3회
MAX_CANDS = 10            # 칸 하나의 후보 = 시트 한 장(scene_fit.PER_SHEET) — 순위 후보가 제약에 걸려 모자라면 순위 밖 샷 가운데로 채운다(10-25 ep13 N6·N7 위반 컷 남음)
TOP_SHOTS = 8             # 줄마다 순위 상위 샷 수(샷마다 자리 3개 — 제약을 통과한 것만 사람 컷 포함 10 개까지)
FLOOR_HI, FLOOR_LO = 7, 5
ROLE_HI = ("본문", "공개", "증거", "반전")      # 지침서 §3-4(handoff 10-19) — 대사가 화면을 가리키는 줄
ROLE_LO = ("훅", "이음", "다리", "끝")          # 연결·여는·닫는 줄(4~5점 정상)
FIT_GOAL = 7              # '7 미만 비율'의 7 = material_auto.FIT_MIN(summarize 가 읽는다)
EDGE = 0.05               # 샷 경계 여유(초)
FLASH = 0.25              # 컷 처음·끝 이 초 안에 원본 샷 경계가 있으면 번쩍임(다른 장면 몇 프레임) — 관문 '컷 끝 번쩍임 없음(0.2초 안 장면 경계)'과 같은 뜻, 0.05 여유
WORKERS = 3
import threading  # noqa: E402
_FACE_LOCK = threading.Lock()

SHOT_PROMPT = """그림의 노란 번호 칸 = 원본 영상의 장면(샷) 하나 — 같은 샷의 처음·가운데·끝 3프레임이 가로로 붙어 있다(얹힌 글자는 무시).
칸마다 화면에 보이는 것을 한국어 한 줄로: 누가(사람 수·성별) · 무엇을(물건·제품 모양·색) · 어떤 상태·동작인지. 추측 금지, 보이는 것만.
출력 JSON만: {{"shots":[{{"n":번호,"desc":"한 줄"}}]}}  (번호 {lo}~{hi})"""

RANK_PROMPT = """숏폼 편집자다. [대사 줄]마다 그 대사가 말하는 동작·상태·대상이 **화면에 보이는** 장면을 [장면 목록]에서 잘 맞는 순서로 최대 {k}개 골라라(장면 id 그대로).
맞는 게 적으면 적게 골라도 된다. 감탄·반응 대사는 그 반응(표정·몸짓)이 보이는 장면.
[대사 줄]
{lines}
[장면 목록] (id: 설명)
{shots}
출력 JSON만: {{"lines":[{{"id":"줄 id","shots":["장면 id", …]}}]}}"""

FIX_PROMPT = """숏폼 대본 편집자다. 아래 나레 줄은 화면(고른 장면)이 대사와 안 맞는다. 대사를 **화면에 실제로 보이는 것**에 맞춰 조금 고쳐라.
지킬 것: ① 뜻(전하는 사실)은 유지 — 없는 사실·효능·숫자를 지어내지 마라 ② 끝 어미·끝 문장부호 유지(원문 끝 '{ending}' 과 마지막 부호 '{punct}' 그대로 — 부호가 줄 경계다) ③ 글자 수(공백 뺀) 원문 {n}자 ±2
④ 자막 덩어리(caps)는 고친 대사를 앞에서부터 그대로 나눈 것(이어 붙이면 문장부호만 빼고 대사와 같다), 덩어리 수 {nc}개 유지 ⑤ 말투·존댓말 유지.
[줄] {lid} (역할 {role})
[원문 대사] {tts}
[원문 자막 덩어리] {caps}
[화면에 보이는 것(컷 순서)] {seen}
[앞뒤 대사] 앞: {prev} / 뒤: {next}
출력 JSON만: {{"tts":"고친 대사","caps":["덩어리1", …],"why":"무엇을 화면에 맞췄나 한 줄"}}"""


def floor_of(role: str | None, floors: dict | None = None) -> int:
    f = {"hi": FLOOR_HI, "lo": FLOOR_LO, **(floors or {})}
    r = str(role or "")
    if any(k in r for k in ROLE_HI):
        return f["hi"]
    if any(k in r for k in ROLE_LO):
        return f["lo"]
    return f["hi"]              # 모르는 역할 = 본문 취급(느슨하게 빠지지 않게)


# ── 그림 ──────────────────────────────────────────────────────────────────
def _frame(src: Path, t: float, crop, h: int = 400):
    import io
    from PIL import Image
    vf = (f"crop={int(crop[2])}:{int(crop[3])}:{int(crop[0])}:{int(crop[1])}," if isinstance(crop, list) and len(crop) == 4 else "") + f"scale=-2:{h}"
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", str(src), "-frames:v", "1", "-vf", vf,
                        "-f", "image2pipe", "-vcodec", "png", "-"], stdin=subprocess.DEVNULL, capture_output=True).stdout
    return Image.open(io.BytesIO(b)).convert("RGB") if b else Image.new("RGB", (round(h * 9 / 16), h), (60, 0, 0))


def strip(src: Path, ss: float, dur: float, crop, dst: Path) -> Path:
    """컷 = 처음·가운데·끝 3프레임 띠(scene_fit.render_items 와 같은 시점 규칙: 끝에서 min(0.1, 길이/4) 안쪽)."""
    from PIL import Image
    if dst.exists():
        return dst
    e = min(0.1, dur / 4)
    fr = [_frame(src, t, crop) for t in (ss + e, ss + dur / 2, ss + dur - e)]
    im = Image.new("RGB", (sum(f.width for f in fr) + 8, max(f.height for f in fr)), "white")
    x = 0
    for f in fr:
        im.paste(f, (x, 0))
        x += f.width + 4
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=85)
    return dst


def center_crop(src: Path, aspect: float) -> list | None:
    """재료.json 에 칸이 없는 소스(보충 재료 등) = 판 창 비율 가운데 자르기 [x,y,w,h] — 채점 그림과 렌더가 같은 칸을 보게(10-25: 사람 칸 1080×1434 를 다른 크기 영상에 물려 렌더 실패)."""
    from tools.calcopy.hybrid.common import probe
    try:
        w, h, _ = probe(src)
    except Exception:  # noqa: BLE001
        return None
    if w / h > aspect:
        cw = int(round(h * aspect)) // 2 * 2
        return [(w - cw) // 2, 0, cw, h]
    ch = int(round(w / aspect)) // 2 * 2
    return [0, (h - ch) // 2, w, ch]


def _key(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False, default=str).encode()).hexdigest()[:12]


# ── 시간표 → 칸 ─────────────────────────────────────────────────────────────
def timeline_of(S: dict, M: dict, st: dict, work: Path, log=print) -> dict:
    """줄 시각·자막 덩어리. 렌더된 시간표(work/render/timeline.json — 진짜 목소리 길이)가 있고 줄이 같으면 그것, 없으면 render_bench.timeline 어림(합성 안 함)."""
    p = Path(work) / "render" / "timeline.json"
    ids = [l["id"] for l in S["lines"]]
    if p.exists():
        T = jload(p)
        if list((T.get("lines") or {}).keys()) == ids:
            return T
        log(f"[fit] {p} 줄이 대본과 달라 어림 시간표로")
    from tools.calcopy.hybrid import render_bench
    log("[fit] 렌더 시간표 없음 — 글자÷cps 어림(목소리 합성 안 함)")
    return render_bench.timeline(S, M, st, None, None)


def slots_of(S: dict, M: dict, T: dict) -> list[dict]:
    """칸 = 화면 컷 자리. 나레 줄 = 재료.json 의 컷 수·비율 그대로(컷 리듬은 안 바꾼다) · 원음 줄 = 입 맞춤 고정 컷(고르지 않고 점수만)."""
    lines, rows, end = T["lines"], T.get("rows") or [], float(T["end"])
    order = [l["id"] for l in S["lines"]]
    Lm = {l["id"]: l for l in S["lines"]}
    by_line = {}
    for r in rows:
        by_line.setdefault(r.get("line"), []).append(r)
    out = []
    fixed = [c for c in T.get("cuts") or [] if c.get("kind") == "orig"]
    for i, lid in enumerate(order):
        L = Lm[lid]
        a = float(lines[lid][0])
        nxt = float(lines[order[i + 1]][0]) if i + 1 < len(order) else end
        lrows = by_line.get(lid, [])
        text = " ".join(r.get("text") or "" for r in lrows)

        def piece_at(t):
            here = [r.get("text") or "" for r in rows if float((r.get("show") or [r["t0"], r["t1"]])[0]) <= t < float((r.get("show") or [r["t0"], r["t1"]])[1])]
            return " ".join(here) or (lrows[0].get("text") if lrows else "(자막 없음)")
        if L["kind"] == "orig":
            for k, c in enumerate([c for c in fixed if c.get("line") == lid]):
                t0, t1 = float(c["t0"]), float(c["t1"])
                out.append({"id": f"{lid}#{k}", "line": lid, "k": k, "kind": "orig", "role": L.get("role"), "t0": t0, "t1": t1, "dur": round(t1 - t0, 3),
                            "piece": piece_at((t0 + t1) / 2), "text": text, "fixed": {**c, "dur": round(t1 - t0, 3)}})
            continue
        cs = (M.get("cuts") or {}).get(lid) or [{"w": 1}]
        ws = [float(c.get("w", 1)) for c in cs]
        acc = 0.0
        for k, (c, w) in enumerate(zip(cs, ws)):
            t0 = a + (nxt - a) * acc / sum(ws)
            acc += w
            t1 = a + (nxt - a) * acc / sum(ws)
            if i == 0 and k == 0:
                t0 = 0.0
            out.append({"id": f"{lid}#{k}", "line": lid, "k": k, "kind": "tts", "role": L.get("role"), "t0": round(t0, 3), "t1": round(t1, 3),
                        "dur": round(t1 - t0, 3), "w": w, "piece": piece_at((t0 + t1) / 2), "text": text, "human": c if c.get("src") else None})
    return out


# ── 샷 표·설명·순위(후보 줄이기) ─────────────────────────────────────────────
def shot_table(src_dir: Path, srcs: list[str], fdir: Path, log=print) -> dict:
    """{src: [{i, a, b}]} — yanshot.plan.shots_in(장면 전환 검출). fdir/shots.json 캐시(파일 크기·시각 열쇠)."""
    from tools.calcopy.hybrid.common import dur_of
    from tools.calcopy.yanshot.plan import shots_in
    cp = fdir / "shots.json"
    C = jload(cp) if cp.exists() else {}
    out = {}
    for s in srcs:
        p = src_dir / s
        if not p.exists():
            log(f"[fit] 재료 없음 {p} — 후보에서 뺌")
            continue
        k = f"{s}|{p.stat().st_size}|{int(p.stat().st_mtime)}"
        if k not in C:
            d = dur_of(p)
            C[k] = {"dur": d, "shots": [{"i": i, "a": a, "b": b} for i, (a, b) in enumerate(shots_in(p, [(0.0, d)]))]}
        out[s] = C[k]
    fdir.mkdir(parents=True, exist_ok=True)
    jsave(cp, C)
    return out


def describe_shots(table: dict, src_dir: Path, crops: dict, fdir: Path, llm, log=print) -> dict:
    """샷마다 한 줄 설명(소넷, 시트 10칸 1회) — 후보 순위용. {"<src>#<i>": desc}. fdir/shot_desc.json 캐시."""
    from tools.calcopy.engine.material_auto import _as_int
    from tools.calcopy.oneshot.scene_fit import _sheet
    cp = fdir / "shot_desc.json"
    C = jload(cp) if cp.exists() else {}
    todo = []
    for s, v in table.items():
        for sh in v["shots"]:
            sid = f"{Path(s).stem}#{sh['i']}"
            if sid not in C:
                img = strip(src_dir / s, sh["a"], sh["b"] - sh["a"], crops.get(s), fdir / "shots" / f"{Path(s).stem}_{sh['i']:03d}.jpg")
                todo.append({"sid": sid, "img": str(img)})
    for c0 in range(0, len(todo), 10):
        ch = todo[c0:c0 + 10]
        sp = _sheet(ch, fdir / f"shots_{c0 // 10}.jpg")
        got = {}
        for _ in range(2):
            r, err = llm([sp.read_bytes()], SHOT_PROMPT.format(lo=0, hi=len(ch) - 1), "ma_fit:shot")
            got.update({_as_int(x.get("n")): str(x.get("desc") or "") for x in (r or {}).get("shots") or [] if isinstance(x, dict) and _as_int(x.get("n")) is not None})
            if all(j in got for j in range(len(ch))):
                break
        for j, it in enumerate(ch):
            if got.get(j):
                C[it["sid"]] = got[j]
            else:
                log(f"[fit] 샷 설명 답 없음 {it['sid']} — 순위에서 빠짐")
        jsave(cp, C)
    return C


def rank_shots(slots: list[dict], desc: dict, fdir: Path, llm, k: int = TOP_SHOTS, log=print) -> dict:
    """줄마다 후보 샷 순위(글 1회). {줄 id: [sid…]}. 점수가 아니다 — 후보 줄이기. fdir/rank.json 캐시(입력 열쇠)."""
    lines = {}
    for s in slots:
        if s["kind"] == "tts":
            lines.setdefault(s["line"], s["text"])
    if not lines or not desc:
        return {}
    key = _key(sorted(lines.items()), sorted(desc.items()), k)
    cp = fdir / "rank.json"
    C = jload(cp) if cp.exists() else {}
    if key in C:
        return C[key]
    body = RANK_PROMPT.format(k=k, lines="\n".join(f"{i}: {t}" for i, t in lines.items()), shots="\n".join(f"{i}: {d}" for i, d in desc.items()))
    out = {}
    for _ in range(2):
        r, err = llm([], body, "ma_fit:rank")
        for x in (r or {}).get("lines") or []:
            if isinstance(x, dict) and x.get("id") in lines:
                out[x["id"]] = [s for s in x.get("shots") or [] if s in desc][:k]
        if all(i in out for i in lines):
            break
    miss = [i for i in lines if i not in out]
    if miss:
        log(f"[fit] 후보 순위 답 없음 {miss} — 그 줄은 사람 컷·전체 샷 가운데 자리로만")
    C[key] = out
    jsave(cp, C)
    return out


# ── 후보·제약 ───────────────────────────────────────────────────────────────
def _new_viol(base: list[dict], cand: dict, src_len: dict) -> list[str]:
    """cand 가 base 컷들과 새로 만드는 재사용 위반 — 판정은 quality_gate.reuse_violations_bench(짝마다 판정하는 함수라 짝으로 부른다)."""
    from tools.calcopy.hybrid.quality_gate import reuse_violations_bench
    out = []
    for x in base:
        if x["src"] == cand["src"]:
            out += reuse_violations_bench([x, cand], src_len)
    return out


def constraint_flags(cand: dict, table: dict, fixed: list[dict], src_len: dict, outside: set, work: Path | None) -> dict:
    """채점 전 제약(표준 §12-3 ②) — 위반이면 그 이유(reject)를 적고 채점하지 않는다.
    shot_edge = 컷 처음·끝 FLASH 초 안에 원본 샷 경계(번쩍임 — 가운데서 넘는 것은 원본 편집 그대로라 허용) · src_end = 원본 끝을 넘음 · reuse = 고정 컷(원음)과 겹침·거리(quality_gate.reuse_violations_bench) ·
    face_outside = 원본 밖 재료에 사람 얼굴(runner_ops._cut_faces) · text_box = 박힌 글자 상자(미측정 — 재료 crop 이 피한다)."""
    s, ss, d = cand["src"], float(cand["ss"]), float(cand["dur"])
    fl = {"shot_edge": False, "src_end": False, "reuse": [], "face_outside": None, "text_box": None, "outside": s in outside}
    v = table.get(s)
    if v:
        if ss + d > float(v["dur"]) + 1e-3:
            fl["src_end"] = True
        bounds = [x["a"] for x in v["shots"][1:]]
        fl["shot_edge"] = any(ss + EDGE < b < ss + d - EDGE and (b - ss < FLASH or ss + d - b < FLASH) for b in bounds)
    fl["reuse"] = _new_viol(fixed, {**cand, "t0": cand["t0"], "t1": cand["t1"]}, src_len)
    if fl["outside"] and work is not None and not (fl["shot_edge"] or fl["src_end"]):
        from tools.calcopy.hybrid.runner_ops import _cut_faces
        with _FACE_LOCK:              # _cut_faces 는 work/_faces/<stem>_k.jpg 를 같은 이름으로 쓴다 — 칸 스레드끼리 겹치면 빈 파일을 읽고 죽었다(10-25)
            try:
                fl["face_outside"] = _cut_faces(Path(work), cand["_path"], ss, d, cand.get("crop")) > 0
            except Exception as e:  # noqa: BLE001 — 못 재면 '얼굴 없음'으로 치지 않는다(미측정 = 못 씀)
                sys.stderr.write(f"[fit] 얼굴 검사 실패 {cand['src']}@{ss}: {type(e).__name__} — 후보에서 뺌\n")
                fl["face_outside"] = True
    fl["reject"] = [k for k in ("shot_edge", "src_end", "face_outside") if fl.get(k)] + (["reuse"] if fl["reuse"] else [])
    return fl


def candidates(slot: dict, table: dict, ranked: list[str], src_dir: Path, crops: dict, fixed: list[dict], src_len: dict,
               outside: set | None = None, work: Path | None = None, extra: list[dict] | None = None) -> tuple[list[dict], list[dict]]:
    """칸 하나의 후보 [{src, ss, dur, crop, shot, pos, from, flags}] — 사람 컷(있으면) + 순위 샷마다 가운데·처음·끝 + 보충(extra).
    제약 위반은 **점수 전에** 빼고 (rejected) 로 돌려준다. 후보 ≤ MAX_CANDS."""
    outside = outside or set()
    d = float(slot["dur"])
    raw = []
    h = slot.get("human")
    if h and h.get("src"):
        raw.append({"src": h["src"], "ss": float(h.get("ss") or 0), "crop": h.get("crop", crops.get(h["src"])), "from": "human", "see": h.get("see")})
    order = list(ranked or [])
    if not order:      # 순위가 없으면 모든 샷의 가운데(샷 표 순서)
        order = [f"{Path(s).stem}#{x['i']}" for s, v in table.items() for x in v["shots"]]
    stem2src = {Path(s).stem: s for s in table}
    per_shot = []
    for r, sid in enumerate(order):
        stem, _, i = sid.partition("#")
        s = stem2src.get(stem)
        if s is None or not i.isdigit():
            continue
        sh = next((x for x in table[s]["shots"] if x["i"] == int(i)), None)
        if not sh:
            continue
        a, b = sh["a"] + EDGE, sh["b"] - EDGE
        pos = [("mid", (a + b - d) / 2), ("start", a), ("end", b - d)]
        got = []
        for name, t in pos:
            t = round(max(0.0, t), 2)
            if all(abs(t - g["ss"]) >= 0.3 for g in got):
                got.append({"src": s, "ss": t, "crop": crops.get(s), "shot": sid, "pos": name, "from": f"rank{r}"})
        per_shot.append(got)
    for k in range(3):                     # 샷마다 가운데 먼저 돌고, 그다음 처음·끝(상위 샷이 고루 들어가게)
        raw += [g[k] for g in per_shot if len(g) > k]
    ranked_set = set(order)
    for s, v in table.items():             # 순위 밖 샷의 가운데로 채운다(제약을 통과한 후보가 MAX_CANDS 에 모자랄 때 — 순위는 후보 줄이기일 뿐)
        for x in v["shots"]:
            sid = f"{Path(s).stem}#{x['i']}"
            if sid not in ranked_set:
                raw.append({"src": s, "ss": round(max(0.0, (x["a"] + x["b"] - d) / 2), 2), "crop": crops.get(s), "shot": sid, "pos": "mid", "from": "fill"})
    raw += list(extra or [])
    keep, rej, seen = [], [], set()
    for c in raw:
        k2 = (c["src"], round(float(c["ss"]), 1))
        if k2 in seen:
            continue
        seen.add(k2)
        c = {**c, "dur": d, "t0": slot["t0"], "t1": slot["t1"], "line": slot["line"], "_path": src_dir / c["src"]}
        c["flags"] = constraint_flags(c, table, fixed, src_len, outside, work)
        if c["flags"]["reject"] and c.get("from") == "human":
            c["blocked"] = True           # 사람 컷은 제약에 걸려도 점수는 낸다(전·후 비교용) — 고르지는 않는다
            keep.append(c)
            rej.append(c)
            continue
        (rej if c["flags"]["reject"] else keep).append(c)
    return keep[:MAX_CANDS], rej


# ── 점수(판단 주인 = scene_fit.judge_rubric) ───────────────────────────────────
def score(cands: list[dict], slot: dict, wd: Path, llm) -> list[dict]:
    """후보마다 3프레임 띠 → judge_rubric(완성본 채점과 같은 함수·같은 루브릭). 캐시 = wd/cache.json(시트 그림·글 sha)."""
    from tools.calcopy.oneshot.scene_fit import judge_rubric
    if not cands:
        return []
    items = []
    for c in cands:
        img = strip(c["_path"], float(c["ss"]), float(c["dur"]), c.get("crop"), Path(wd) / "strips" / f"{Path(c['src']).stem}_{float(c['ss']):.2f}_{float(c['dur']):.2f}_{_key(c.get('crop'))[:6]}.jpg")   # 칸(crop)도 이름에 — 칸이 바뀌면 다른 그림
        items.append({"img": str(img), "piece": slot["piece"], "line": slot["text"]})
    res = judge_rubric(items, Path(wd), llm, cache=Path(wd) / "cache.json")
    for c, r in zip(cands, res):
        c["score"], c["scores"], c["seen"] = r.get("score"), r.get("scores"), r.get("seen") or r.get("why", "")
    return cands


# ── 고르기 ─────────────────────────────────────────────────────────────────
BEAM = 200                # 고르기 = 칸 전체를 함께 보는 빔 탐색(앞 칸 욕심 고르기는 A-B-A·재사용에 막혀 뒤 칸이 빈다 — 10-25 가짜 답 실측)
BELOW_PENALTY = 6         # 하한 미달 칸 하나 = 점수 6 깎음(평균보다 하한 통과를 먼저)
VIOL_PENALTY = 100        # 제약 위반 컷(다른 후보가 하나도 없을 때만 남기는 것)


def select(slots: list[dict], src_len: dict, floors: dict | None = None) -> list[dict]:
    """칸 전체에서 (점수 합 − 하한 미달 × BELOW_PENALTY) 가 가장 큰 고르기 — 원음 고정 컷·서로 간 재사용 ×(quality_gate.reuse_violations_bench)·
    나레 컷 A-B-A ×(checks.aba_violations) 제약 안에서. 같은 점이면 사람 컷. 제약 안 후보가 하나도 없는 칸만 위반 컷을 남기고 그 사실을 적는다(빈칸 금지)."""
    from tools.calcopy.hybrid.checks import aba_violations
    fixed = [{**s["fixed"], "src": s["fixed"]["src"], "ss": float(s["fixed"]["ss"])} for s in slots if s["kind"] == "orig"]
    beams = [(0.0, [], [])]          # (값, 고른 컷들(제약 검사용), 칸별 결정)
    for s in slots:
        if s["kind"] == "orig":
            beams = [(v, ch, dec + [{"pick": s.get("fixed_scored") or {**s["fixed"], "score": None}, "below": False, "why": "원음 고정(입 맞춤)"}])
                     for v, ch, dec in beams]
            continue
        fl = floor_of(s.get("role"), floors)
        cands = sorted([c for c in s.get("cands") or [] if c.get("score") is not None and not c.get("blocked")],
                       key=lambda c: (-c["score"], c.get("from") != "human", str(c.get("from"))))
        nxt = []
        for v, ch, dec in beams:
            tts_prev = [c for c in ch if c["kind"] == "tts"]
            ok_any, skipped = False, []
            for c in cands:
                cut = {"src": c["src"], "ss": float(c["ss"]), "dur": float(c["dur"]), "t0": s["t0"], "t1": s["t1"], "line": s["line"], "kind": "tts"}
                rv = _new_viol(fixed + ch, cut, src_len)
                aba = aba_violations([{"src": x["src"], "t0": x["t0"]} for x in tts_prev[-2:]] + [{"src": c["src"], "t0": s["t0"]}])
                if rv or aba:
                    skipped.append(f"{c['src']}@{c['ss']} " + (f"재사용 {rv[0]}" if rv else "A-B-A"))
                    continue
                ok_any = True
                below = c["score"] < fl
                nxt.append((v + c["score"] - BELOW_PENALTY * below + (0.01 if c.get("from") == "human" else 0), ch + [cut],
                            dec + [{"pick": {**c, **cut}, "below": below, "floor": fl, "why": ("하한 미달" if below else "통과")}]))
            if not ok_any:           # 제약 안 후보 0 — 최고점(또는 사람 컷)을 위반째 남긴다
                pool = cands or [c for c in s.get("cands") or [] if c.get("score") is not None]
                if pool:
                    c = pool[0]
                    cut = {"src": c["src"], "ss": float(c["ss"]), "dur": float(c["dur"]), "t0": s["t0"], "t1": s["t1"], "line": s["line"], "kind": "tts"}
                    nxt.append((v + c["score"] - VIOL_PENALTY, ch + [cut], dec + [{"pick": {**c, **cut, "violation": skipped[:2] or ["제약 위반 컷"]}, "below": True, "floor": fl,
                                                                                    "why": f"제약 안 후보 0 — 위반째 남김 {skipped[:2]}"}]))
                else:
                    nxt.append((v - VIOL_PENALTY, ch, dec + [{"pick": None, "below": True, "floor": fl, "why": "후보 0"}]))
        if any(not (x[2][-1].get("pick") or {}).get("violation") and x[2][-1].get("pick") for x in nxt):   # 제약 지킨 길이 하나라도 있으면 위반 길은 버린다
            nxt = [x for x in nxt if not (x[2][-1].get("pick") or {}).get("violation") and x[2][-1].get("pick")]
        nxt.sort(key=lambda x: -x[0])
        seen_k, beams = set(), []
        for x in nxt:                    # 다양성: 최근 나레 컷 3개가 같은 길은 하나만(같은 앞 고르기만 200개 남아 뒤 칸이 막히던 것, 10-25 ep13 실측)
            k = tuple((c["src"], round(c["ss"], 1)) for c in x[1] if c["kind"] == "tts")[-3:]
            if k in seen_k:
                continue
            seen_k.add(k)
            beams.append(x)
            if len(beams) >= BEAM:
                break
    best = beams[0][2] if beams else []
    return [{**s, **d} for s, d in zip(slots, best)]


def summary_of(sel: list[dict]) -> dict:
    from tools.calcopy.oneshot.scene_fit import summarize
    sc = [(s.get("pick") or {}).get("score") for s in sel]
    return summarize(sc, [s.get("role") for s in sel])


def goal_of(st: dict, slug: str | None, log=print) -> dict | None:
    """목표 = 판 targets.scene_fit(07 이 상위편_목표.json 에서 적은 값) — 그 출처가 상위편_목표가 아니면(눈 점수 임시값) 상위편_목표.json 을 읽고 경고."""
    t = ((st.get("targets") or {}).get("scene_fit") or {})
    tm = t.get("mean_goal", (t.get("mean") or {}).get("ours_goal") if isinstance(t.get("mean"), dict) else None)
    tb = t.get("below7_goal", (t.get("below7") or {}).get("ours_goal") if isinstance(t.get("below7"), dict) else None)
    same_ruler = "상위편_목표" in json.dumps(t, ensure_ascii=False)
    p = ROOT / "channel" / (slug or "_") / "_kal" / "상위편_목표.json"
    top = (jload(p).get("scene_fit") or {}) if p.exists() else {}
    if tm is not None and tb is not None and same_ruler:
        return {"mean": float(tm), "below7": float(tb), "src": "판 targets.scene_fit(상위편_목표 출처)"}
    if top.get("p75_mean") is not None:
        if tm is not None:
            log(f"[fit] 경고: 판 targets.scene_fit({tm}/{tb})는 같은 자 재측정 전 값 — 상위편_목표.json({top['p75_mean']}/{top['p25_below7']})을 쓴다(07 이 판에 옮겨 적을 것)")
        else:
            log("[fit] 경고: 판 targets.scene_fit 없음 — 상위편_목표.json 을 직접 읽는다(07 이 판에 적을 것)")
        return {"mean": float(top["p75_mean"]), "below7": float(top["p25_below7"]), "src": str(p.relative_to(ROOT))}
    if tm is not None and tb is not None:
        log("[fit] 경고: 상위편_목표.json 없음 — 판 targets(눈 점수 임시값)로")
        return {"mean": float(tm), "below7": float(tb), "src": "판 targets.scene_fit(임시)"}
    log("[fit] 경고: 목표 없음 — 하한만 본다")
    return None


def verdict(sel: list[dict], goal: dict | None) -> tuple[bool, dict, list[dict]]:
    sm = summary_of(sel)
    under = [s for s in sel if s["kind"] == "tts" and s.get("below")]
    ok_goal = goal is None or (sm["mean"] is not None and sm["mean"] >= goal["mean"] and (sm["below_rate"] or 0) <= goal["below7"])
    weak = list(under)
    if not ok_goal:          # 목표 미달이면 7 미만 나레 칸도 고칠 대상(훅·이음·다리는 분모 밖이라 뺀다)
        from tools.calcopy.oneshot.scene_fit import SKIP_ROLES
        weak += [s for s in sel if s["kind"] == "tts" and s not in weak and ((s.get("pick") or {}).get("score") or 0) < FIT_GOAL
                 and not any(k in str(s.get("role") or "") for k in SKIP_ROLES)]
    return (not under and ok_goal), sm, weak


# ── (a) 보충 재료 · (b) 대사 고침 ─────────────────────────────────────────────
GENERIC = ("크림", "제품", "같은", "비슷한", "정확한", "이름", "쿠팡", "세트", "콜라겐", "핑크", "마스크")   # 흔한 낱말(10-25 ep13 콜라겐 마스크팩이 들어옴)


def supplement(weak: list[dict], doc_S: dict, work: Path, log=print, n: int = 6, take: int = 2) -> list[str]:
    """하한 미달 줄 → screen.search('<제품> <동작 낱말>') → 짧은 순 take 개 받기(src/sup_<id>.mp4). 받은 파일 이름 목록.
    받은 것은 원본 밖 재료 — 후보가 될 때 얼굴 있는 컷은 제약(face_outside)이 뺀다. 실패는 사유를 남기고 빈 목록(조용히 통과 아님)."""
    from tools.calcopy.hybrid import screen
    prod = re.sub(r"\(.*?\)", "", str(doc_S.get("product") or "")).strip()
    words = []
    for s in weak:
        for w in re.findall(r"[가-힣A-Za-z]{2,}", s["text"]):
            if w not in words and len(words) < 3:
                words.append(w)
    qs = [f"{prod} {w}" for w in words] or [prod]
    try:
        cands = screen.search(work, qs, n=n, exclude=["모음", "TOP", "추천"], log=log)
    except Exception as e:  # noqa: BLE001 — 검색이 막히면 사유를 남기고 대사 고침으로 넘어간다
        log(f"[fit] 보충 검색 실패: {type(e).__name__}: {str(e)[:160]}")
        return []
    # 길이 모름(서버 API 결과 — 대개 쇼츠)도 받는다: 길이 아는 90초 이하 짧은 순 → 모르는 것 순(10-25 ep13: 14개 중 11개가 길이 None 이라 다 빠졌다)
    toks = [t for t in re.findall(r"[가-힣]{2,}|[A-Za-z]{3,}", str(doc_S.get("product") or "")) if t not in GENERIC]
    hit = (lambda c: sum(1 for t in toks if t.lower() in (c.get("title") or "").lower()))
    cands = [c for c in cands if hit(c) >= 1]          # 제목에 제품 낱말(브랜드·성분·모양) 1개 이상 — 10-25 ep13 '톤업 선크림'이 들어왔다
    cands = sorted(cands, key=lambda c: -hit(c))
    cands = (sorted([c for c in cands if c.get("duration") and c["duration"] <= 90], key=lambda c: c["duration"])
             + [c for c in cands if not c.get("duration")])[:take]
    got = []
    for c in cands:
        try:
            for p in screen.download(work, [c["id"]], prefix="sup_", log=log):
                got.append(str(Path(p).relative_to(Path(work) / "src")).replace("\\", "/"))
        except Exception as e:  # noqa: BLE001
            log(f"[fit] 보충 받기 실패 {c['id']}: {type(e).__name__}: {str(e)[:160]}")
    return got


def _ending(t: str) -> str:
    m = re.search(r"([가-힣]{1,3})\s*[,.?!~]*\s*$", t)
    return m.group(1) if m else ""


def propose_fixes(weak_lines: list[str], sel: list[dict], S: dict, llm, version: str | None, work: Path, log=print) -> list[dict]:
    """미달 나레 줄 → 대사 고침 제안 {line, old, new, caps, why, audit_ok, checks}. 검사 = 끝 어미 같음·글자 수 ±2·caps 이어 붙이기 = 대사·script_audit 새 실패 0."""
    from tools.calcopy.hybrid import script_audit as SA
    from tools.calcopy.hybrid.common import nchar
    Lm = {l["id"]: l for l in S["lines"]}
    order = [l["id"] for l in S["lines"]]
    tmp = Path(work) / "_material_fit"
    tmp.mkdir(parents=True, exist_ok=True)
    base_p = tmp / "대본_원문.json"
    jsave(base_p, S)
    base_bad = {r["kind"] + "|" + str(r.get("rule", "")) for r in SA.audit(base_p, version)["rules"] if not r["ok"]}
    out = []
    for lid in weak_lines:
        L = Lm[lid]
        if L.get("kind") != "tts":
            continue
        i = order.index(lid)
        seen = " / ".join(str((s.get("pick") or {}).get("seen") or "") for s in sel if s["line"] == lid)
        caps = [c["text"] for c in L.get("caps") or []]
        body = FIX_PROMPT.format(punct=(re.findall(r"[,.?!~]", L["tts"].strip()[-1:]) or [""])[0], ending=_ending(L["tts"]), n=nchar(L["tts"]), nc=len(caps), lid=lid, role=L.get("role"), tts=L["tts"], caps=caps, seen=seen,
                                 prev=Lm[order[i - 1]].get("tts") or Lm[order[i - 1]].get("said") if i else "", next=(Lm[order[i + 1]].get("tts") or "") if i + 1 < len(order) else "")
        r, err = llm([], body, "ma_fit:fix")
        if not r or not r.get("tts"):
            out.append({"line": lid, "old": L["tts"], "new": None, "why": f"제안 답 없음({err})", "audit_ok": False})
            continue
        new, ncaps = str(r["tts"]).strip(), [str(x) for x in r.get("caps") or []]
        plain = (lambda t: re.sub(r"[\s,.?!~…'\"“”]", "", t))
        checks = {"ending": _ending(new) == _ending(L["tts"]), "punct": new.strip()[-1:] == L["tts"].strip()[-1:], "chars": abs(nchar(new) - nchar(L["tts"])) <= 2,
                  "caps": plain("".join(ncaps)) == plain(new) and len(ncaps) == len(caps), "changed": plain(new) != plain(L["tts"])}
        S2 = {**S, "lines": [({**l, "tts": new, "caps": [{**(l["caps"][k] if k < len(l.get("caps") or []) else {}), "text": t} for k, t in enumerate(ncaps)]}
                              if l["id"] == lid else l) for l in S["lines"]]}
        p2 = tmp / f"대본_고침_{lid}.json"
        jsave(p2, S2)
        a2 = SA.audit(p2, version)
        new_bad = [r2["why"] for r2 in a2["rules"] if not r2["ok"] and (r2["kind"] + "|" + str(r2.get("rule", ""))) not in base_bad]
        checks["audit"] = not new_bad
        out.append({"line": lid, "old": L["tts"], "new": new, "caps": ncaps, "why": str(r.get("why") or ""), "seen": seen,
                    "checks": checks, "audit_new_fail": new_bad, "audit_ok": all(checks.values())})
        log(f"[fit] 고침 제안 {lid}: «{L['tts']}» → «{new}» 검사 {checks}")
    return out


def apply_fixes(S: dict, fixes: list[dict]) -> dict:
    ok = {f["line"]: f for f in fixes if f.get("audit_ok")}
    return {**S, "lines": [({**l, "tts": ok[l["id"]]["new"], "caps": [{**(l["caps"][k] if k < len(l.get("caps") or []) else {}), "text": t}
                                                                       for k, t in enumerate(ok[l["id"]]["caps"])]} if l["id"] in ok else l)
                           for l in S["lines"]]}


def _retext(slots: list[dict], S: dict, T: dict) -> None:
    """고친 대사로 칸의 자막 조각·문장을 다시 적는다(시각은 그대로 — 새 합성 전 어림). 그 칸의 점수는 다시 매긴다."""
    Lm = {l["id"]: l for l in S["lines"]}
    for s in slots:
        L = Lm[s["line"]]
        if L.get("kind") != "tts":
            continue
        caps = [c["text"] for c in L.get("caps") or []]
        txt = " ".join(caps)
        if txt == s["text"]:
            continue
        n = len([x for x in slots if x["line"] == s["line"]])
        s["text"] = txt
        s["piece"] = caps[min(len(caps) - 1, int(s["k"] * len(caps) / max(1, n)))] if caps else txt
        s.pop("cands", None)


# ── 계획 ───────────────────────────────────────────────────────────────────
def plan(doc, work, version: str, llm=None, apply: bool = False, sign: bool = False, do_supplement: bool = True, floors: dict | None = None,
         max_rounds: int = MAX_ROUNDS, log=print) -> dict:
    """줄마다 최고점 후보 → 재료_계획.json · 미달 → (a) 보충 → (b) 대사 고침(sign 이면 받아들여 다시) — 최대 max_rounds 회 → 장면대사_계획.json."""
    from tools.calcopy.engine import material_auto as MA
    from tools.calcopy.hybrid import styles as STY
    from tools.calcopy.oneshot.scene_fit import RUBRIC_V
    doc, work = Path(doc), Path(work)
    st = STY.load(version)
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    S0 = json.loads(json.dumps(S))
    llm = llm or MA.LLM()
    src_dir = Path(M.get("cand_dir") or work / "src")
    fdir = work / "_material_fit"
    fdir.mkdir(parents=True, exist_ok=True)
    T = timeline_of(S, M, st, work, log)
    slots = slots_of(S, M, T)
    crops = {}
    for cs in (M.get("cuts") or {}).values():
        for c in cs if isinstance(cs, list) else [cs]:
            if c.get("src") and isinstance(c.get("crop"), list):
                crops.setdefault(c["src"], c["crop"])
    for s in slots:
        if s["kind"] == "orig":
            crops.setdefault(s["fixed"]["src"], s["fixed"].get("crop") if isinstance(s["fixed"].get("crop"), list) else None)
    _, _, ww, wh = st["frame"]["window"]
    aspect = ww / wh
    for sname in list({(s.get("human") or {}).get("src") for s in slots} | {s["fixed"]["src"] for s in slots if s["kind"] == "orig"}) :
        if sname and not crops.get(sname):
            crops[sname] = center_crop(src_dir / sname, aspect)
    srcs = sorted({s for s in crops} | {(s.get("human") or {}).get("src") for s in slots if s.get("human")} - {None})
    outside_all: set = set()
    goal = goal_of(st, (st.get("bench") or {}).get("channel"), log)
    rounds, fixes_all, stop = [], [], None
    sup_tried: set = set()
    for rnd in range(1, max_rounds + 1):
        table = shot_table(src_dir, srcs, fdir, log)
        src_len = {s: v["dur"] for s, v in table.items()}
        desc = describe_shots(table, src_dir, crops, fdir, llm, log)
        ranked = rank_shots(slots, desc, fdir, llm, log=log)
        fixed = [{**s["fixed"], "ss": float(s["fixed"]["ss"])} for s in slots if s["kind"] == "orig"]

        def run_slot(s):
            if s["kind"] == "orig":
                f = s["fixed"]
                c = {"src": f["src"], "ss": float(f["ss"]), "dur": s["dur"], "crop": f.get("crop") if isinstance(f.get("crop"), list) else crops.get(f["src"]),
                     "_path": src_dir / f["src"], "from": "orig"}
                s["fixed_scored"] = {**f, **score([c], s, fdir / "slots" / s["id"].replace("#", "_"), llm)[0], "_path": None}
                return s
            if "cands" not in s:
                keep, rej = candidates(s, table, ranked.get(s["line"]), src_dir, crops, fixed, src_len, outside_all, work)
                s["cands"], s["rejected"] = score(keep, s, fdir / "slots" / f"{s['id'].replace('#', '_')}_{_key(s['text'], s['piece'])}", llm), rej
            return s
        with ThreadPoolExecutor(WORKERS) as ex:
            list(ex.map(run_slot, slots))
        sel = select(slots, src_len, floors)
        ok, sm, weak = verdict(sel, goal)
        rounds.append({"round": rnd, "mean": sm["mean"], "below7": sm["below_rate"], "below_n": sm["below_min"], "ok": ok,
                       "weak": [s["id"] for s in weak], "supplement": [], "fixes": []})
        log(f"[fit] {rnd}회 평균 {sm['mean']} · 7 미만 {sm['below_min']}/{sm['below_base']}({sm['below_rate']}) · 목표 {goal} · 미달 {[s['id'] for s in weak]} → {'통과' if ok else '다시'}")
        if ok:
            break
        if rnd == max_rounds:
            stop = f"멈춤(사유: {max_rounds}회 뒤에도 미달 — 줄 {sorted({s['line'] for s in weak})})"
            break
        # (a) 보충 재료
        wl = sorted({s["line"] for s in weak})
        new_src = []
        if do_supplement and not set(wl) <= sup_tried:
            new_src = supplement(weak, S, work, log)
            sup_tried |= set(wl)
            rounds[-1]["supplement"] = new_src
            if new_src:
                for f in new_src:
                    outside_all.add(f)
                    srcs.append(f)
                    crops[f] = center_crop(src_dir / f, aspect)
                for s in slots:
                    if s["line"] in wl:
                        s.pop("cands", None)
                continue
        # (b) 대사 고침 제안
        fx = propose_fixes([l for l in wl if any(s["line"] == l and s["kind"] == "tts" for s in slots)], sel, S, llm, version, work, log)
        fixes_all += fx
        rounds[-1]["fixes"] = [f["line"] for f in fx if f.get("audit_ok")]
        if not any(f.get("audit_ok") for f in fx):
            stop = f"멈춤(사유: 보충 재료 0 · 대사 고침 통과 0 — 줄 {wl})"
            break
        if not sign:
            stop = f"사인 대기(wait_user) — 대사 고침 {[f['line'] for f in fx if f.get('audit_ok')]} 를 받아들이면 --sign 으로 다시"
            break
        S = apply_fixes(S, fx)
        _retext(slots, S, T)
    sel = select(slots, src_len, floors)
    ok, sm, weak = verdict(sel, goal)
    # 재료_계획.json
    M2 = json.loads(json.dumps({k: v for k, v in M.items()}))
    cuts = dict(M2.get("cuts") or {})
    for lid in [l["id"] for l in S["lines"] if l["kind"] == "tts"]:
        mine = [s for s in sel if s["line"] == lid]
        new = []
        for s in mine:
            p = s.get("pick")
            if not p:
                new.append({**(s.get("human") or {}), "fit": None, "fit_why": s["why"], "cand_n": len(s.get("cands") or [])})
                continue
            h = s.get("human") or {}
            same = h.get("src") == p["src"] and abs(float(h.get("ss") or -9) - float(p["ss"])) < 0.05
            new.append({"src": p["src"], "ss": round(float(p["ss"]), 3), "w": s["w"], "crop": p.get("crop") or crops.get(p["src"]) or "face",
                        "see": h.get("see") if same else (p.get("seen") or ""), "fit": p.get("score"), "fit_why": p.get("seen") or "", "cand_n": len(s.get("cands") or []),
                        **({"outside": True} if p["src"] in outside_all else {})})
        cuts[lid] = new
    for s in sel:
        if s["kind"] == "orig" and s["line"] in cuts:
            for c in cuts[s["line"]]:
                if isinstance(c, dict) and s.get("fixed_scored") and c.get("see") == s["fixed"].get("see"):
                    c["fit"] = s["fixed_scored"].get("score")
    M2["cuts"] = cuts
    M2["_fit_note"] = f"material_fit.plan {RUBRIC_V} — 줄마다 후보 → scene_fit.judge_rubric → 역할 하한·재사용·A-B-A 안 최고점"
    jsave(doc / "재료_계획.json", M2)
    if apply:
        if not (doc / "재료_사람.json").exists():
            jsave(doc / "재료_사람.json", M)
        jsave(doc / "재료.json", M2)
    changed = [l for l in S["lines"] if l["kind"] == "tts" and l.get("tts") != next(x for x in S0["lines"] if x["id"] == l["id"]).get("tts")]
    res = {"made_by": "tools/calcopy/hybrid/material_fit.plan", "rubric": RUBRIC_V, "version": version,
           "lines": [{"id": s["id"], "line": s["line"], "role": s.get("role"), "kind": s["kind"], "floor": s.get("floor"),
                      "fit": (s.get("pick") or {}).get("score"), "scores": (s.get("pick") or {}).get("scores"),
                      "pick": {k: (s.get("pick") or {}).get(k) for k in ("src", "ss", "from", "shot", "pos")} if s.get("pick") else None,
                      "human_fit": next((c.get("score") for c in s.get("cands") or [] if c.get("from") == "human"), None),
                      "seen": (s.get("pick") or {}).get("seen"), "piece": s["piece"], "cand_n": len(s.get("cands") or []),
                      "rejected": [{"src": c["src"], "ss": c["ss"], "why": c["flags"]["reject"]} for c in s.get("rejected") or []],
                      "below": s.get("below"), "why": s.get("why"),
                      "fixed_by": ("dialogue" if s["line"] in {l["id"] for l in changed} else ("supplement" if (s.get("pick") or {}).get("src") in outside_all else None))}
                     for s in sel],
           "mean": sm["mean"], "below7": sm["below_rate"], "below_n": sm["below_min"], "below_base": sm["below_base"],
           "human": summary_of([{**s, "pick": {"score": next((c.get("score") for c in s.get("cands") or [] if c.get("from") == "human"), None)}
                                 if s["kind"] == "tts" else s.get("pick")} for s in sel]),
           "target": goal, "ok": ok, "rounds": rounds, "stop": None if ok else stop, "fixes": fixes_all,
           "needs_tts": [l["id"] for l in changed], "calls": len(getattr(llm, "calls", None) or [])}
    jsave(doc / "장면대사_계획.json", res)
    log(f"[fit] 결과 평균 {sm['mean']}(사람 {res['human']['mean']}) · 7 미만 {sm['below_rate']}(사람 {res['human']['below_rate']}) · 목표 {goal} · ok {ok} · {res['stop'] or ''}")
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("doc"); p.add_argument("work"); p.add_argument("--version", required=True)
    p.add_argument("--apply", action="store_true"); p.add_argument("--sign", action="store_true", help="대사 고침 제안을 받아들여 다시 채점(우리 사인)")
    p.add_argument("--no-supplement", action="store_true"); p.add_argument("--floor-hi", type=int); p.add_argument("--floor-lo", type=int)
    p.add_argument("--rounds", type=int, default=MAX_ROUNDS)
    a = ap.parse_args(argv)
    floors = {k: v for k, v in (("hi", a.floor_hi), ("lo", a.floor_lo)) if v is not None}
    r = plan(a.doc, a.work, a.version, apply=a.apply, sign=a.sign, do_supplement=not a.no_supplement, floors=floors or None, max_rounds=a.rounds)
    for x in r["lines"]:
        print(f"  {x['id']:5} {str(x.get('role'))[:10]:10} fit {x['fit']!s:>4} (사람 {x['human_fit']!s:>4}) 하한 {x['floor']!s:>3} 후보 {x['cand_n']:2} 제외 {len(x['rejected']):2} "
              f"{(x.get('pick') or {}).get('src')}@{(x.get('pick') or {}).get('ss')} {x.get('why', '')[:50]}")
    print(json.dumps({k: r[k] for k in ("mean", "below7", "human", "target", "ok", "stop", "needs_tts")}, ensure_ascii=False))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
