# -*- coding: utf-8 -*-
"""preset_make 렌더 전 관문 — preset_make 컷을 render_bench 꼴로 바꿔 **이미 있는 관문 함수를 그대로 부른다**(2026-10-25).

왜: 재미썸홈·잇썸홈·썰템쇼 등이 쓰는 preset_make 는 계획 검사(A4·A9·A11·A12·B15)와 완성본 B표만 돌고
    render_bench 의 렌더 전 관문(남의 글자·멈춤·장면 경계·컷 길이·받아쓰기·대본 글)과 품질 관문 기록이 0건이었다.
    실결함: 작품6 취객선비잔 남의 글자(쇼핑몰 '일시품절' 화면)·멈춤 · 작품9 B·C 읽는 글 영문 'SNS' · 창고판 옥수수커터 검사 미달인데 손으로 납품.
판단 주인(여기서 새로 정하는 판단 없음 — 부르기만):
  G-1 대본 글        = hybrid/script_audit.text_defects
  ② 줄별 받아쓰기    = engine/narr_verify.gate_sent
  ③⑤⑦④ 컷           = hybrid/render_bench.cut_boundary_gate · cut_length_gate · cut_still_gate · cut_content_gate · photo_gate
  ⑧ 길이             = render_bench.plan_length_gate(진짜 목소리 길이일 때만)
  G-10 접촉 시트      = render_bench.contact_sheet
여기가 정하는 것 = 꼴 바꾸기(to_bench) 한 곳 + 관문 기록(<작품>/품질관문/<완성본 md5>.json — engine/deliver 가 읽는다) 쓰기.
관문이 보는 그림 = 굽는 그림: 크롭 칸(c['box'])을 그대로 넘기고, render_bench 프레임 필터(crop→scale)와 preset_make.part_vf 가
  같은 그림인지 test_preset_gates 가 픽셀로 대조한다. 늘림(fit_shot speed)·움직임(move) 컷의 멈춤은 preset_make.part_vf 그림으로 잰다
  (판정은 같은 quality_gate.still_spans).
우회 플래그 없음 — 멈추면 GateStop(이유 전부)을 낸다.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

FPS = 30
GATE_NAME = "preset_gates:v1(2026-10-25)"


class GateStop(RuntimeError):
    """렌더 전 관문 멈춤 — 메시지에 관문·컷·이유를 다 적는다."""


def _stop(stage: str, bad: list[str]):
    if bad:
        raise GateStop(f"[관문 멈춤 · {stage}] " + " / ".join(bad) + " — 대본·재료를 고쳐 다시(우회 없음)")


# ── 꼴 바꾸기(어댑터 한 곳) ───────────────────────────────────────────────
def bench_script(w: dict) -> dict:
    """preset_make 대본 줄 → render_bench/script_audit 대본 꼴 {lines:[{id, kind, tts, text}]}. id = '줄<번호>'."""
    return {"lines": [{"id": f"줄{i + 1}", "kind": "orig" if l.get("orig") else "tts", "tts": l.get("tts") or l.get("text") or "",
                       "text": l.get("text") or ""} for i, l in enumerate(w["lines"])]}


def win_of(cfg: dict) -> tuple[int, int]:
    """preset_make 재료 창 = 조각 굽는 크기(render_parts 의 W×H2)."""
    W, H = cfg["window"]
    return int(W), int(H) + (int(H) % 2)


def _fit_est(c: dict, n: int, cfg: dict) -> dict:
    """계획(--plan) 어림 컷에 preset_make.build_cuts 와 같은 샷 맞춤(판단 주인 preset_make.fit_shot)을 건 사본 — 관문이 굽힐 ss·speed 를 본다.
    10-25 실측: 태양의맛썬 컷 ss 40.40 은 앞 0.1초 번쩍을 fit_shot 이 렌더 때 40.54 로 옮기는데, 어림 계획은 옮기기 전 자리를 재 ③이 거짓으로 멈췄다."""
    fit = cfg.get("fit_shot") or {}
    c2 = {**c, "n": n, "speed": 1.0}
    if fit.get("enabled") and not c.get("orig") and "src_dur" in c:
        from tools.calcopy.engine import preset_make as PM
        PM.fit_shot(c2, fit)
    return c2


def to_bench(w: dict, cfg: dict, name: str = "") -> dict:
    """preset_make 계획(w['cuts']) → render_bench 관문 입력. 반환 {T, Tsrc, M, st, measured}.
    measured = build_cuts 뒤(진짜 목소리 시각, c['f0']·c['n'] 있음) / 아니면 글자÷cps 어림(계획 --plan).
    T    = 화면 길이(컷 프레임 수 n) — cut_length_gate·plan_length_gate·photo_gate
    Tsrc = 원본에서 실제로 읽는 길이(n×speed) — cut_boundary_gate·cut_content_gate·cut_still_gate·contact_sheet"""
    ww, wh = win_of(cfg)
    measured = all("f0" in c and "n" in c for c in w["cuts"])
    cuts, t = [], 0.0
    for k, c in enumerate(w["cuts"]):
        if measured:
            n, t0 = int(c["n"]), c["f0"] / FPS
        else:
            sec = sum(w["pieces"][i]["chars"] for i in c["pieces"]) / float(cfg["cps"])
            n, t0 = max(1, round(sec * FPS)), t
            c = _fit_est(c, n, cfg)        # 어림 길이에도 build_cuts 와 같은 샷 맞춤(fit_shot)을 걸어 굽힐 ss·늘림으로 잰다(w 는 안 바꾼다)
        t = t0 + n / FPS
        li = w["pieces"][c["pieces"][0]]["line"]
        cuts.append({"src": str(c["path"]), "ss": float(c["ss"]), "crop": [int(v) for v in c["box"]], "frames": n,
                     "t0": round(t0, 3), "t1": round(t0 + n / FPS, 3), "dur": round(n / FPS, 3),
                     "line": f"줄{li + 1}", "kind": "orig" if c.get("orig") else "tts", "pm_k": k, "pm_n": n,
                     "speed": float(c.get("speed", 1.0)), "move": c.get("move")})
    end = round(cuts[-1]["t1"], 3) if cuts else 0.0
    src_cuts = [{**c, "frames": max(1, round(c["frames"] * c["speed"]))} for c in cuts]
    allow = ((cfg.get("checks") or {}).get("length_s") or {}).get("allow") or [0, 1e9]
    st = {"name": name, "frame": {"kind": "window", "window": [0, 0, ww, wh]}, "thumb_card_face": bool(cfg.get("thumb_card_face")),
          "length": {"min": float(allow[0]), "max": float(allow[1])}, "rhythm": cfg.get("rhythm") or {}}
    return {"T": {"cuts": cuts, "end": end}, "Tsrc": {"cuts": src_cuts, "end": end}, "M": {"cand_dir": str(w["data"]), "blur": {}},
            "st": st, "measured": measured}


# ── 관문 ─────────────────────────────────────────────────────────────────
def text_gate(w: dict) -> list[str]:
    """G-1(TTS 전) — preset_make 는 TTS 를 덩어리마다 따로 합성하므로 joined=False(줄 끝 부호 규칙 없음)."""
    from tools.calcopy.hybrid import script_audit as SA
    return [f"G-1 {x['line']} {x['rule']}: {x['why']}" for x in SA.text_defects(bench_script(w), joined=False)]


def voice_gate(w: dict, cfg: dict, cache: Path, full: Path, out: Path, log=print) -> list[str]:
    """② 합성 직후 줄별 받아쓰기(engine/narr_verify.gate_sent). 덩어리 파일(cache/tts/chunk)이 있으면 덩어리마다, 없으면(들인 한 파일) 전체 한 줄."""
    from tools.calcopy.engine import narr_verify as NV
    from tools.calcopy.engine import name_dict as ND
    from tools.calcopy.engine import preset_make as PM
    R = Path(out) / "narr_verify"
    R.mkdir(parents=True, exist_ok=True)
    tempo = cfg.get("tts_tempo")
    chunks = [ND.apply_all(c, w["voice"]) for c in PM.tts_chunks([l["tts"] for l in w["lines"]], cfg.get("tts_split"))]
    files = [cache / "tts" / "chunk" / f"{PM.sha([w['voice'], tempo, ch])}.mp3" for ch in chunks]
    if all(f.exists() for f in files):
        S = {"lines": [{"id": f"덩어리{i + 1}", "kind": "tts", "tts": ch} for i, ch in enumerate(chunks)]}
        sent = [{"id": f"덩어리{i + 1}", "wav": str(f)} for i, f in enumerate(files)]
    else:
        S = {"lines": [{"id": "전체", "kind": "tts", "tts": " ".join(chunks)}]}
        sent = [{"id": "전체", "wav": str(full)}]
    PM.run(["ffmpeg", "-y", "-v", "error", "-i", full, "-ac", "1", "-ar", "44100", "-b:a", "128k", R / "narr_full.mp3"])
    try:
        return [f"② {x}" for x in NV.gate_sent(S, sent, R, log)]
    except Exception as e:  # noqa: BLE001 — 못 쟀으면 통과로 치지 않는다
        return [f"② 줄별 받아쓰기 못 잼({type(e).__name__}: {str(e)[:160]})"]


def _still_own(c: dict, cfg: dict) -> list[tuple[float, float]]:
    """늘림·움직임 컷의 멈춤 — preset_make.part_vf(굽는 필터 그대로) 회색 프레임 → quality_gate.still_spans."""
    import numpy as np
    from tools.calcopy.engine import preset_make as PM
    from tools.calcopy.hybrid import quality_gate as QG
    ww, wh = win_of(cfg)
    sh = max(8, round(108 * wh / ww / 2) * 2)
    n = int(c["pm_n"])          # 화면 프레임 수(굽는 -frames:v) — c["frames"] 는 원본에서 읽는 길이(n×speed)
    pc = {"box": c["crop"], "speed": c["speed"], "move": c["move"], "n": n}
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{c['ss']:.3f}", "-i", c["src"], "-an", "-vf",
                          PM.part_vf(pc, ww, wh) + f",scale=108:{sh},format=gray", "-frames:v", str(n), "-f", "rawvideo", "-"],
                         capture_output=True, stdin=subprocess.DEVNULL).stdout
    fr = np.frombuffer(raw[:len(raw) - len(raw) % (108 * sh)], np.uint8).reshape(-1, sh, 108).astype(np.int16)
    return QG.still_spans(fr)


def cut_gates(G: dict, doc: Path | None, R: Path, log=print) -> list[str]:
    """③⑤⑦④·사진·⑧ 을 render_bench 함수로. 반환 = 문제 목록(빈 목록 = 통과). 잰 값 캐시 R/cut_content.json."""
    from tools.calcopy.hybrid import render_bench as RB
    T, Ts, M, st = G["T"], G["Tsrc"], G["M"], G["st"]
    bad = []
    bad += [f"⑤ {x}" for x in RB.cut_length_gate(T, st)]
    bad += [f"⑧ {x}" for x in RB.plan_length_gate(T, st, G["measured"])]
    bad += [f"사진 {x}" for x in RB.photo_gate(T, st)]
    bad += [f"③ {x}" for x in RB.cut_boundary_gate(Ts, M, st)]
    plain = [c for c in Ts["cuts"] if c["speed"] == 1.0 and not c.get("move")]
    for c in plain:          # 컷 하나씩 — 문구의 컷 번호가 preset_make 컷 번호(pm_k)·접촉 시트 번호와 같게(걸러낸 목록 번호 0 을 바꿔 적는다)
        k = c["pm_k"]
        bad += ["⑦ " + x.replace("컷 멈춤 0 ", f"컷 멈춤 {k} ", 1) for x in RB.cut_still_gate({"cuts": [c], "end": Ts["end"]}, M, st)]
    for c in Ts["cuts"]:
        if c in plain or not Path(c["src"]).exists():
            continue
        sp = _still_own(c, G["cfg"]) if G.get("cfg") else []
        if sp:
            bad.append(f"⑦ 컷 멈춤 {c['pm_k']} {c['line']} {c['src']}@{c['ss']}: 컷 안 {[(round(a, 2), round(b, 2)) for a, b in sp]}초가 멈춘 그림"
                       f"(늘림 {c['speed']}·move {c['move']} 그대로 잼) — 움직이는 장면으로 바꾼다")
    bad += [f"④ {x}" for x in RB.cut_content_gate(Ts, M, st, doc=doc, R=R, log=log)]
    return bad


def pre_render(w: dict, cfg: dict, out: Path, doc: Path | None, name: str = "", log=print, sheet_to: Path | None = None) -> dict:
    """렌더 전 관문 묶음(컷) + 접촉 시트(sheet_to, 없으면 out/계획_접촉시트.jpg). 반환 {bad, sheet, measured}.
    멈출지는 부른 쪽(make_one)이 정한다(계획은 표로, 제작은 GateStop)."""
    from tools.calcopy.hybrid import render_bench as RB
    G = to_bench(w, cfg, name)
    G["cfg"] = cfg
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sheet = RB.contact_sheet(G["Tsrc"], G["M"], G["st"], Path(sheet_to or out / "계획_접촉시트.jpg"), bench_script(w))
    if sheet:
        log(f"  접촉 시트(컷마다 처음·가운데·끝, 굽는 칸 그대로) → {sheet}")
    bad = cut_gates(G, doc, out, log)
    (out / "관문_렌더전.json").write_text(json.dumps({"gate": GATE_NAME, "measured": G["measured"], "bad": bad,
                                                     "cuts": G["T"]["cuts"], "end": G["T"]["end"]}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"bad": bad, "sheet": str(sheet) if sheet else None, "measured": G["measured"]}


# ── 완성본 관문 기록(납품이 읽는다) ─────────────────────────────────────────
def record(doc: Path, final_md5: str, rows: list[dict], passed: list[str], log=print) -> Path:
    """<작품>/품질관문/<완성본 md5>.json — preset_make B표(rows) + 통과한 렌더 전 관문 이름. engine/deliver.check 가 ok·rows 를 본다.
    rows 꼴 = deliver 가 읽는 {group, what, ok, value, src}."""
    rr = [{"group": str(r.get("B")), "what": str(r.get("항목")), "ok": bool(r.get("ok")), "value": r.get("값"), "src": f"preset_make 기준 {r.get('기준')}"}
          for r in rows]
    rr += [{"group": "렌더 전", "what": g, "ok": True, "value": "통과", "src": "preset_gates"} for g in passed]
    rep = {"gate": GATE_NAME, "renderer": "preset_make", "ok": all(r["ok"] for r in rr), "final_md5": final_md5,
           "at": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": rr, "n": len(rr), "n_bad": sum(not r["ok"] for r in rr)}
    p = Path(doc) / "품질관문" / f"{final_md5}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log(f"  [관문 기록] {p} · {'○' if rep['ok'] else '× ' + str(rep['n_bad']) + '칸'}")
    return p
