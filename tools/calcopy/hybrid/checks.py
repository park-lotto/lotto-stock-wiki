# -*- coding: utf-8 -*-
"""렌더 뒤 자동 검사 → **B표 초안(B표_draft.md)** + checks.json (관제 097, 2026-10-18). 검수 매뉴얼(tools/calcopy/검수_매뉴얼.md) B 항목을 같은 자로 잰다.

    PYTHONUTF8=1 py tools/calcopy/hybrid/checks.py <doc_dir> <work_dir> [--asr] [--bench-median 1.41]

재는 것: B1 길이 · B2 LUFS/최고점 · B3 말속도(줄별) · B4 컷 중앙·끝 컷 · B9 첫·끝 Y · B13 같은 장면 ±3초 재사용 · B16 A-B-A 끼움 · B16' check_seams(되감김·점프줌)
  · B17 TTS 35자↓·줄별 atempo ±10% · B18 쉼(voice 트랙 무음) · A9 자막 조각 글자 수 · 1초 시트 · (--asr) 완성본 원음 창·이름 줄 단독 받아쓰기(서버 제미나이 2모델)
남기는 것: 줄별 대조표(시각·대사·화면 설명) — 클로드는 이 표 + 1초 시트만 보고 ○/△/× 를 적는다.
판단 주인: 각 항목의 ○/× 는 이 파일의 row() 한 곳. 렌더 숫자는 render_info.json(렌더러가 쓴 것)만 읽는다 — 다시 계산하지 않는다.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import ROOT, dur_of, jload, jsave, lufs, md5, nchar, silences  # noqa: E402

CPS_TOL = 0.05
PEAK_MAX = -0.5
CUT_MIN, END_CUT_MIN = 1.2, 1.5
Y_MIN = 60
REUSE_S = 3.0
PAUSE_LO, PAUSE_HI = 0.22, 0.30
TTS_MAX_CHARS = 35
TEMPO_TOL = 0.10
CAP_MAX = {"잇썸홈판": 15, "재미썸홈판": 13}


def _ymean(mp4, t: float, win) -> float:
    b = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-vf",
                        f"crop={win[2]}:{win[3]}:{win[0]}:{win[1]},scale=270:-2,format=gray", "-f", "image2pipe", "-vcodec", "png", "-"],
                       capture_output=True, stdin=subprocess.DEVNULL).stdout
    from PIL import Image
    return float(np.asarray(Image.open(io.BytesIO(b))).mean()) if b else 0.0


def reuse_violations(cuts: list[dict]) -> list[str]:
    """B13: 같은 소스에서 겹치거나 ±3초 안 구간을 두 번 쓰면 걸린다(원음 조각 밑 화면이 그 원음 구간 자체인 것은 정상)."""
    bad = []
    rows = [(c["src"], float(c["ss"]), float(c["ss"]) + float(c["dur"]), c) for c in cuts]
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            s1, a1, b1, c1 = rows[i]; s2, a2, b2, c2 = rows[j]
            if s1 != s2:
                continue
            adjacent = abs(float(c1["t1"]) - float(c2["t0"])) < 0.06 or abs(float(c2["t1"]) - float(c1["t0"])) < 0.06
            forward = (a2 >= b1 - 0.05) if float(c1["t0"]) <= float(c2["t0"]) else (a1 >= b2 - 0.05)
            if adjacent and forward:
                continue            # 이어 붙인 다음 컷이 원본에서 앞으로만 간 것(원음 조각 이어 읽기)은 재사용이 아니다
            if a1 < b2 + REUSE_S and a2 < b1 + REUSE_S:
                bad.append(f"{Path(s1).stem} {a1:.1f}~{b1:.1f}({c1.get('line')}) ↔ {a2:.1f}~{b2:.1f}({c2.get('line')})")
    return bad


def aba_violations(cuts_b: list[dict]) -> list[str]:
    """B16: 소스 순서 X→Y→X(사이에 하나만 끼었다 돌아오기)."""
    seq = [Path(c["src"]).stem for c in sorted(cuts_b, key=lambda c: c["t0"])]
    return [f"{seq[i]}→{seq[i + 1]}→{seq[i + 2]} ({i})" for i in range(len(seq) - 2) if seq[i] == seq[i + 2] != seq[i + 1]]


def pauses_between(voice_wav: Path, bounds: list[tuple[float, float]], noise="-35dB") -> list[dict]:
    """B18: 줄 경계(앞 줄 끝~다음 줄 시작) 안의 무음 길이."""
    sil = silences(voice_wav, noise, 0.08)
    out = []
    for a, b in bounds:
        inside = [(max(s, a - 0.15), min(e, b + 0.15)) for s, e in sil if e > a - 0.15 and s < b + 0.15]
        gap = round(max((e - s for s, e in inside), default=0.0), 3)
        out.append({"at": [round(a, 2), round(b, 2)], "pause": gap})
    return out


def asr_check(final: Path, orig_win: list[tuple[float, float]], name: str | None, name_win: tuple[float, float] | None, said: str, log=print) -> dict:
    """완성본 원음 창·이름 줄만 잘라 서버 제미나이 2모델 단독 받아쓰기(B17·B8). 덮음 = 본인 말 글자 중 들린 비율."""
    from tools.calcopy.hybrid import server_ai
    spans = list(orig_win) + ([name_win] if name_win else [])
    res = server_ai.asr_clips(final, spans)
    n_o = len(orig_win)
    heard = [" ".join(server_ai.texts_of(res, i)[:1]) for i in range(n_o)]
    norm = lambda t: re.sub(r"[^0-9A-Za-z가-힣]", "", t)
    said_n, heard_n = norm(said), norm(" ".join(heard))
    cov = round(sum(1 for ch in set(said_n) if ch in heard_n) / max(1, len(set(said_n))), 2)
    spk = [c.get("speakers") for r in res["runs"] for c in (r.get("clips") or []) if c.get("i", 99) < n_o]
    out = {"models": res.get("ok_models"), "sec": res.get("sec"), "orig_heard": [server_ai.texts_of(res, i) for i in range(n_o)], "coverage": cov,
           "speakers_max": max([s for s in spk if isinstance(s, int)], default=None)}
    if name_win:
        texts = server_ai.texts_of(res, n_o)
        out["name_heard"] = texts
        out["name_ok_models"] = sum(1 for t in texts if name and name in norm(t))
    log(f"[asr] 모델 {out['models']} 덮음 {cov} 화자최대 {out['speakers_max']} 이름 {out.get('name_ok_models')}/{len(out.get('name_heard', []))}")
    return out


def check(doc: Path, work: Path, asr: bool = False, bench_median: float | None = None, log=print) -> dict:
    from tools.calcopy.engine import check_seams
    doc, work = Path(doc), Path(work)
    R = work / "render"
    info = jload(R / "render_info.json")
    S = jload(doc / "대본.json")
    final = R / "final.mp4"
    version = info.get("version") or (info.get("report") or {}).get("version") or "?"
    dur = dur_of(final)
    I, pk = lufs(final)
    win, mask = check_seams.from_frame(str(R / "frame_A.json"))
    seams = check_seams.check(str(final), win, mask)
    jsave(R / "seams.json", seams)
    cuts = info["cuts_flat"]
    cuts_b = [c for c in cuts if c["seg"] == "B"]
    bdur = sorted(c["dur"] for c in cuts_b)
    med = bdur[len(bdur) // 2]
    end_cut = sorted(cuts_b, key=lambda c: c["t0"])[-1]["dur"]
    rows = []

    def row(k, name, value, ok, why=""):
        rows.append({"k": k, "name": name, "value": value, "ok": ok, "why": why})
    # 줄별 말속도·atempo·쉼·자막 길이는 판별로 모양이 다르다
    if version == "잇썸홈판":
        T = info["timeline"]
        sent = info["sentences"]
        rates = {s["id"]: round(s["chars"] / s["dur"], 2) for s in sent}
        tempos = [s["tempo"] for s in sent]
        tempo_ref = info["tempo"]                       # 잇썸: 줄별 늘림/줄임은 기본 atempo 대비(B17 ±10%)
        cps_target = S["cps_target"]
        tts_chars = [nchar(l["tts"]) for l in S["lines"] if l["kind"] == "tts"]
        caps_len = max(len(c["text"].replace(" ", "")) for c in T["caps"])
        line_ids = [T["h_id"]] + T["b_ids"]
        bounds = [(T["lines"][a][1], T["lines"][b][0]) for a, b in zip(line_ids[:-1], line_ids[1:]) if T["lines"][b][0] > T["lines"][a][1]]
        pauses = pauses_between(R / "voice.wav", bounds)
        orig_win = [(T["opos"][0]["t0"], T["opos"][-1]["t1"])]
        name_win = tuple(T["lines"][T["h_id"]])
        said = " ".join(l.get("said", "") for l in S["lines"] if l["kind"] == "orig")
        cap_rows = [(c["show"][0], c["show"][1], ("[원음] " if c["kind"] == "원음" else "") + c["text"]) for c in T["caps"]]
    else:
        rep = info["report"]
        rates = {l["slot"] + str(i): r for i, (l, r) in enumerate(zip(info["lines"], rep["line_rates"]))}
        tempos = [rep["atempo"]["all"], rep["atempo"]["last"]]
        tempo_ref = rep["atempo"]["all"]
        cps_target = S["cps_target"]
        tts_chars = [l["chars"] for l in info["lines"]]
        caps_len = rep["max_caption"]
        pauses = [{"at": p.get("at"), "pause": p.get("now")} for p in rep["atempo"].get("pauses", [])]
        orig_win = [(0.0, rep["orig_sec"])]
        f1 = [p for p in info["pieces"] if p["line"] == 0]
        name_win = (f1[0]["t"][0], f1[-1]["t"][1])
        said = " ".join(c for _, c in S["orig_caps"])
        cap_rows = [(p["t"][0], p["t"][1], ("[TTS] " if p["line"] == 0 else "") + p["caption"]) for p in info["pieces"]]
        cap_rows = [(e["t0"], e["t1"], "[원음] " + e["text"]) for e in info["a_caps"] if e["who"] == "원음"] + cap_rows
    mean_rate = sum(rates.values()) / len(rates)
    row("B1", "길이", f"{dur:.2f}초", 20.0 <= dur <= 35.0, "하이브리드 정본 27~29초 · 벤치 24.6")
    row("B2", "LUFS·최고점", f"{I} LUFS · {pk} dBFS", pk <= PEAK_MAX, "판별 목표(잇썸 −8.6 / 재미썸 −14)와 대조는 사람")
    row("B3", "말속도(줄별 자/초)", f"평균 {mean_rate:.2f} vs 목표 {cps_target} · " + " ".join(f"{k}:{v}" for k, v in rates.items()),
        abs(mean_rate / cps_target - 1) <= CPS_TOL, f"{(mean_rate / cps_target - 1) * 100:+.1f}%")
    row("B4", "B 컷 중앙·끝 컷", f"중앙 {med:.2f}초(컷 {len(cuts_b)}) · 끝 {end_cut:.2f} · 최단 {bdur[0]:.2f}" + (f" · 벤치 {bench_median}(×{med / bench_median:.2f})" if bench_median else ""),
        bdur[0] >= CUT_MIN - 1e-6 and end_cut >= END_CUT_MIN and (not bench_median or med / bench_median >= 0.9),
        ("△ 느린 쪽(벤치 ×1.3 넘음 — 재료가 모자라 못 쪼갰으면 적는다)" if bench_median and med / bench_median > 1.3 else "빠르면 반려 쪽(B4)"))
    y0, y1 = _ymean(final, 0.3, win), _ymean(final, dur - 0.3, win)
    row("B9", "첫·끝 컷 Y≥60", f"{y0:.0f} · {y1:.0f}", y0 >= Y_MIN and y1 >= Y_MIN)
    b13 = reuse_violations(cuts)
    row("B13", "같은 장면 ±3초 재사용", b13 or "0", not b13)
    aba = aba_violations(cuts_b)
    row("B16", "A-B-A 끼움", aba or "0", not aba)
    row("B16'", "check_seams 되감김·점프줌", f"컷 {len(seams['컷'])} · 되감김 {len(seams['되감김'])} · 점프줌 {len(seams['점프줌'])}({seams['점프줌_판정'] or '드묾'})", seams["ok"])
    row("B17", "TTS 35자↓ · 줄별 배속 ±10%(기본 atempo 대비)", f"글자 {tts_chars} · atempo {tempos} (기본 {tempo_ref})",
        max(tts_chars) <= TTS_MAX_CHARS and all(abs(t / tempo_ref - 1) <= TEMPO_TOL + 1e-6 for t in tempos))
    pv = [p["pause"] for p in pauses if p["pause"] is not None]
    row("B18", "쉼 0.22~0.30", " ".join(f"{p:.2f}" for p in pv), all(PAUSE_LO - 0.02 <= p <= PAUSE_HI + 0.03 for p in pv) if pv else False, "voice 트랙 −35dB(잇썸) / tts_pause 기록(재미썸)")
    row("A9", f"자막 조각 ≤{CAP_MAX.get(version, 13)}자", caps_len, caps_len <= CAP_MAX.get(version, 13))
    from tools.calcopy.hybrid import thumb
    fc = thumb.face_check(final, win, name_win, log)
    row("T1", "첫 프레임·H 구간 연예인 얼굴(1개·크게·가운데)", " ".join(f"{r['t']}s:{'○' if r['ok'] else r['why']}" for r in fc["frames"]), fc["ok"],
        "사장님 10-18 '썸네일은 무조건 연예인' — 제품 컷 시작 금지")
    from tools.calcopy.engine.remake import sheet_1s
    sheet = doc / "final_sheet_1s.jpg"
    if not sheet.exists():
        sheet_1s(final, sheet)
    asr_res = None
    if asr:
        name = S.get("celeb") or S.get("slug", "")[:3]
        asr_res = asr_check(final, orig_win, name, name_win, said, log)
        row("B17''", "원음 창 단독 받아쓰기 = 본인 말(2모델)", f"{asr_res['models']} 덮음 {asr_res['coverage']} 화자 {asr_res['speakers_max']} / 들림 {asr_res['orig_heard']}",
            asr_res["coverage"] >= 0.55 and (asr_res["speakers_max"] or 1) <= 1 and len(asr_res["models"] or []) >= 2, "모델 2개 미만이면 교차 확인 모자람")
        if name_win:
            row("A11'", f"이름 '{name}' 받아쓰기", f"{asr_res.get('name_heard')} ({asr_res.get('name_ok_models')}/{len(asr_res.get('name_heard') or [])})",
                (asr_res.get("name_ok_models") or 0) >= 1 and (asr_res.get("name_ok_models") or 0) == len(asr_res.get("name_heard") or []))
    # 줄별 대조표(시각·대사·그때 화면) — 판정 칸은 비워 둔다(클로드가 시트 보고 적는다)
    def see_at(t):
        hits = [c for c in cuts if c["t0"] - 1e-3 <= t < c["t1"] + 1e-3]
        return " / ".join(f"{Path(c['src']).stem}@{c['ss']} {c.get('see', '')}" for c in sorted(hits, key=lambda c: c["seg"]))[:120]
    table = [f"| {a:.2f}–{b:.2f} | {txt} | {see_at((a + b) / 2)} |  |" for a, b, txt in sorted(cap_rows)]
    ok_auto = all(r["ok"] for r in rows)
    L = [f"# B표 초안 — 얜샷템 하이브리드 {S.get('slug', '')} · {version} (자동 검사, tools/calcopy/hybrid/checks.py)", "",
         f"완성본 `{final}` · MD5 `{md5(final)}` · {dur:.2f}초 · {I} LUFS · 1초 시트 `{sheet}`",
         f"자동 판정: {'전부 ○' if ok_auto else '× ' + ', '.join(r['k'] for r in rows if not r['ok'])} — **사람이 볼 것**: 줄↔장면(A3) · 자막 잔존(B7) · 꾸밈·얼굴(B5) · 남의 신체(A13) · 원본 자막 띠 크롭(시트)", "",
         "## 줄별 대조표 (대사 | 그 순간 화면 | ○/△/× — 클로드가 1초 시트 보고 적는다)", "| 초 | 대사(자막) | 화면(소스@초 설명) | 판정 |", "|---|---|---|---|", *table, "",
         "## B 항목(자동)", "| # | 항목 | 값 | ○/× | 비고 |", "|---|---|---|---|---|",
         *[f"| {r['k']} | {r['name']} | {r['value']} | {'○' if r['ok'] else '×'} | {r['why']} |" for r in rows], ""]
    (doc / "B표_draft.md").write_text("\n".join(L), encoding="utf-8")
    res = {"ok_auto": ok_auto, "rows": rows, "dur": dur, "lufs": I, "peak": pk, "cut_median": med, "end_cut": end_cut, "seams": {"ok": seams["ok"], "되감김": len(seams["되감김"]), "점프줌": len(seams["점프줌"]), "컷": len(seams["컷"])},
           "face": fc, "asr": asr_res, "draft": str(doc / "B표_draft.md"), "md5": md5(final)}
    jsave(work / "checks.json", res)
    log(f"[checks] {'통과' if ok_auto else '걸림'}: " + " ".join(f"{r['k']}{'○' if r['ok'] else '×'}" for r in rows) + f" → {doc / 'B표_draft.md'}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc"); ap.add_argument("work"); ap.add_argument("--asr", action="store_true"); ap.add_argument("--bench-median", type=float)
    a = ap.parse_args()
    r = check(Path(a.doc), Path(a.work), a.asr, a.bench_median)
    print(json.dumps({k: v for k, v in r.items() if k != "rows"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
