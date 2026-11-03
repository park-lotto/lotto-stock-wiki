# -*- coding: utf-8 -*-
"""옛 편(편마다 복사한 make_render.py·make.py 상수)을 새 렌더러 입력(대본.json·재료.json v2)으로 옮긴다 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/hybrid/legacy_import.py itssum <옛 잇썸홈판 폴더> <새 doc 폴더>
    PYTHONUTF8=1 py tools/calcopy/hybrid/legacy_import.py jaemi  <옛 재미썸홈판 폴더(make.py)> <새 doc 폴더>

잇썸: 옛 대본.json 은 거의 그대로(원음 줄 span/spans/pieces 세 꼴을 렌더러가 읽는다). 재료.json A 의 네 꼴(함익병 한 줄기 · 박세리 H_shots/O_shots ·
장윤정 H/O · 최은경 H_shot/O1_shots/O2_shots)을 canonical A{H:[…], O:[…]} 로 바꾼다.
재미썸: make.py 모듈을 불러 상수(ORIG·A_VIS/A_SHOTS·F1_SHOT·LINES·PIECES·TEMPO·PUNCT_AT…)를 JSON 으로 옮긴다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import ROOT, jload, jsave  # noqa: E402


def _rel(src: str, cand_dir: str) -> str:
    p = Path(src)
    try:
        return p.relative_to(cand_dir).as_posix() if p.is_absolute() else src
    except ValueError:
        return src


def itssum(old: Path, new: Path, slug: str = "") -> tuple[dict, dict]:
    S, M = jload(old / "대본.json"), jload(old / "재료.json")
    cand = M["cand_dir"]
    A = M["A"]
    O = [l for l in S["lines"] if l["kind"] == "orig"]
    if "H" in A and "O" in A:                                   # 장윤정 — 이미 canonical(H 에 dur 만 있으면 weight 로)
        A2 = {"H": [{**h, "weight": h.get("weight", h.get("dur", 1.0))} for h in A["H"]], "O": A["O"], "face": A.get("face", "")}
    elif "H_shots" in A and "O_shots" in A:                     # 박세리
        pieces = O[0]["pieces"]
        t, pos = 0.0, {}
        for p in pieces:
            pos[p["id"]] = t
            t += p["span"][1] - p["span"][0] + p.get("pad_after", 0.0) + p.get("gap_after", 0.0)
        hs = []
        for h in A["H_shots"][:-1]:
            hs.append({"src": A["src"], "ss": h["ss"], "crop": h["crop"], "see": h.get("see", ""), "weight": h["max"], "max": h["max"]})
        last = A["H_shots"][-1]
        hs.append({"src": A["src"], "ss": None, "crop": last["crop"], "see": last.get("see", ""), "weight": last.get("dur", 1.0), "reach_orig": True})
        os_ = []
        for sh in A["O_shots"]:
            p = next(p for p in pieces if p["id"] == sh["piece"])
            os_.append({"at": round(pos[p["id"]] + sh["src_t"] - p["span"][0], 3), "src": A["src"], "ss": sh.get("ss", sh["src_t"]), "crop": sh["crop"], "see": sh.get("see", "")})
        A2 = {"H": hs, "O": os_, "face": A.get("face", "")}
        S.setdefault("render", {})["a_end_pad"] = 0.03
    elif "H_shot" in A:                                         # 최은경 — O1_shots/O2_shots(shot 범위) → at(이어 붙인 초)
        hs = A["H_shot"]
        A2 = {"H": [{"src": hs["src"], "ss": hs["shot"][0] + 0.03, "crop": hs["crop"], "see": hs.get("see", "")}], "O": [], "face": A.get("face", "")}
        t = 0.0
        for L in O:
            key = f"{L['id']}_shots"
            a, b = L["span"]
            for k, sh in enumerate(A.get(key, [])):
                at = t + max(0.0, sh["shot"][0] - a) if k else t
                A2["O"].append({"at": round(at, 3), "src": sh["src"], "ss": sh["shot"][0] if k == 0 and sh["shot"][0] <= a else max(sh["shot"][0], a), "crop": sh["crop"], "see": sh.get("see", "")})
            t += b - a + float(L.get("gap_before", 0.25)) if L is not O[-1] else b - a
        S.setdefault("render", {})["a_end_pad"] = 0.03
        S["render"]["gap_oo"] = 0.25
    elif "src" in A and "crop" in A:                            # 함익병 — 원본 한 줄기(H 는 원음 앞 원본 그대로 이어 읽음)
        a0 = O[0]["span"][0]
        A2 = {"H": [{"src": A["src"], "ss": None, "crop": A["crop"], "see": A.get("see", ""), "reach_orig": True}],
              "O": [{"at": 0.0, "src": A["src"], "ss": a0, "crop": A["crop"], "see": A.get("see", "")}], "face": A.get("face", "")}
        if A.get("end"):
            S.setdefault("render", {})["a_end_pad"] = round(A["end"] + 0.03 - O[-1]["span"][1], 3)
    else:
        raise ValueError(f"모르는 재료 A 꼴: {list(A)}")
    for h in A2["H"] + A2["O"]:
        h["src"] = _rel(h["src"], cand)
    for L in O:
        L["src"] = _rel(L.get("src") or A2["O"][0]["src"], cand)      # 최은경 꼴: 원음 줄에 src 없음(재료 A 의 소스)
    B = [{**b, "src": _rel(b["src"], cand)} for b in M["B"]]
    S2 = {**S, "slug": slug or S.get("slug", ""), "frame_a": "channel/mantem/frame_얜샷템.json", "_made_by": "tools/calcopy/hybrid/legacy_import.py itssum"}
    M2 = {"_note": M.get("_note", ""), "cand_dir": cand, "A": A2, "B": B, "src_urls": M.get("src_urls", {}), "audio_rule": M.get("audio_rule", "")}
    new.mkdir(parents=True, exist_ok=True)
    jsave(new / "대본.json", S2); jsave(new / "재료.json", M2)
    return S2, M2


def _load_module(py: Path):
    spec = importlib.util.spec_from_file_location("legacy_make_" + py.parent.name, py)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def jaemi(old: Path, new: Path, slug: str = "") -> tuple[dict, dict]:
    m = _load_module(old / "make.py")
    cand = str(m.SRC)
    lines = [{"slot": s, "text": t, "tts": tt} for s, t, tt in m.LINES]
    pieces = [{"caption": p[0]} for p in m.PIECES]
    orig = [{"id": n, "span": [a, b]} for n, a, b in m.ORIG]
    orig_caps = [[t, c] for t, c in m.ORIG_CAPS]
    A = []
    if hasattr(m, "A_VIS"):                                     # 장윤정: (at, src, ss, crop)
        see = getattr(m, "A_VIS_SEE", [""] * len(m.A_VIS))
        A = [{"at": at, "src": src, "ss": ss, "crop": cr, "see": see[k]} for k, (at, src, ss, cr) in enumerate(m.A_VIS)]
    else:                                                       # 함익병·박세리 (ss, crop) 조각 1:1 / 최은경 [[(ss, crop, dur)…]]
        t = 0.0
        for (n, a, b), sh in zip(m.ORIG, m.A_SHOTS):
            shots = sh if isinstance(sh, list) else [(sh[0], sh[1], None)]
            x = t
            for ss, cr, dd in shots:
                A.append({"at": round(x, 3), "src": m.HAM, "ss": ss, "crop": cr, "see": ""})
                x += (dd if dd is not None else (b - a) - (x - t))
            t += b - a
    nF1 = 0
    used = 0
    for p in m.PIECES:                      # 줄 0(F1) 조각 수
        if used >= m.nchar(m.LINES[0][1]):
            break
        nF1 += 1; used += m.nchar(p[0])
    F1 = [{"src": m.F1_SHOT[0], "ss": m.F1_SHOT[1], "crop": m.F1_SHOT[2], "from_piece": 0, "see": "F1"},
          {"src": m.F1_SHOT2[0], "ss": m.F1_SHOT2[1], "crop": m.F1_SHOT2[2], "from_piece": nF1 - 1, "see": "F1b"}]
    B, k = [], 0
    for k, p in enumerate(m.PIECES):
        if p[1] is None:
            continue
        if p[1] == "+":
            B[-1]["pieces"].append(k)
        else:
            B.append({"src": p[1], "ss": p[2], "crop": p[3], "kind": p[4], "pieces": [k], "seen": p[5]})
    S = {"slug": slug, "title": m.TITLE_A, "source_label": m.LABEL_A, "body_title": m.BODY_TITLE, "voice": {"voice_id": m.VOICE, "tempo": m.TC_TEMPO},
         "cps_target": m.CPS, "orig": orig, "orig_caps": orig_caps, "lines": lines, "pieces": pieces,
         "tts_tempo": {"all": m.TEMPO, "last": m.TEMPO_LAST}, "punct_at": [[k_, v] for k_, v in m.PUNCT_AT],
         "render": {"end_pad": getattr(m, "END_PAD", 0.7), "gap_o_f1": m.GAP_O_F1, "duck_db": m.DUCK_DB, "target_lufs": m.TARGET_LUFS, "voice_af": m.VOICE_AF,
                    "silence_d": 0.08},
         "bgm": {"id": m.BGM_A}, "frame_a": "channel/mantem/frame_얜샷템.json", "_made_by": "tools/calcopy/hybrid/legacy_import.py jaemi"}
    M = {"cand_dir": cand, "src_main": m.HAM, "A": A, "F1": F1, "B": B, "src_urls": {}}
    new.mkdir(parents=True, exist_ok=True)
    jsave(new / "대본.json", S); jsave(new / "재료.json", M)
    return S, M


def main():
    kind, old, new = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    slug = sys.argv[4] if len(sys.argv) > 4 else ""
    {"itssum": itssum, "jaemi": jaemi}[kind](old, new, slug)
    print("→", new)


if __name__ == "__main__":
    main()
