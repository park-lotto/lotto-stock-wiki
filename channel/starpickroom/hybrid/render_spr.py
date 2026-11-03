# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 — **스타픽룸판** 렌더러(관제 097, 2026-10-18). 자막 입히기 **직전**까지: 컷·나레·원음·BGM·틀(제목·출처·워터마크·로고)
→ final_nocap.mp4 + 자막표.json(자막팩에 새 효과가 들어간 뒤 지휘자가 그 길로 입힌다).

    PYTHONUTF8=1 py channel/starpickroom/hybrid/render_spr.py <doc_dir> <work_dir> [--plan]

벤치(스타픽룸) 박자가 잇썸홈판과 달라(원음이 먼저, 나레가 가운데, 원음 반응으로 끝) 시간표만 이 파일이 정한다(timeline — 시각의 주인).
나머지는 공용을 부른다(같은 판단 두 벌 금지): TTS·문장 자르기 = hybrid.render_itssum.tts_once/make_sentences(미나 = engine.narr_align 서버 합성),
소리 섞기 = render_itssum.audio, 틀 = shopping_shorts.scene_style.compose(설명서 = channel/starpickroom/preset/검정틀_금색로고_타이핑나레),
완성 인코딩 = engine.master_guard.encode_final, 1초 시트 = engine.remake.sheet_1s.
스키마 밖 층(제목 낱말 색·창 워터마크·금색 로고)은 _tools/spr_overlay.py 그림을 덮는다.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "channel/starpickroom/_tools"))
from tools.calcopy.hybrid.common import FPS, StageError, dur_of, jload, jsave, lufs, nchar, run  # noqa: E402
from tools.calcopy.hybrid import render_itssum as RI  # noqa: E402

PRESET = ROOT / "channel/starpickroom/preset/검정틀_금색로고_타이핑나레"
WIN = (1080, 1058)
DEF = {"gap": 0.20, "gap_oo": 0.25, "tail": 0.50}


def timeline(S, M, sent: dict) -> dict:
    """줄 순서 그대로 이어 붙인다. sent = {tts 줄 id: 초}. 반환 = lines·opos(원음 조각)·caps(자막 조각)·cuts(화면)·end."""
    C = {**DEF, **(S.get("render") or {})}
    t, lines, opos, caps, prev = 0.0, {}, [], [], None
    for L in S["lines"]:
        if prev is not None:
            t += C["gap_oo"] if (prev == "orig" and L["kind"] == "orig") else C["gap"]
        if L["kind"] == "orig":
            t0 = t
            for k, (a, b) in enumerate(L["spans"]):
                opos.append({"id": f"{L['id']}{k}", "line": L["id"], "src": L["src"], "span": [a, b], "pad": 0.0, "gap": 0.0, "mute": [],
                             "t0": round(t, 3), "t1": round(t + b - a, 3)})
                t += b - a
            opos[-1]["gap"] = 0.001          # audio() 가 원음 줄마다 따로 묶어 제자리에 놓게(조각 사이는 붙어 있다)
            lines[L["id"]] = [round(t0, 3), round(t, 3)]
            for txt, s0, s1 in L["caps_rel"]:
                caps.append({"line": L["id"], "j": len([c for c in caps if c["line"] == L["id"]]), "text": txt,
                             "t0": round(t0 + s0, 3), "t1": round(t0 + s1, 3), "kind": "원음"})
        else:
            d = sent[L["id"]]
            lines[L["id"]] = [round(t, 3), round(t + d, 3)]
            w = [nchar(c) for c in L["caps"]]; x = t
            for j, (c, ww) in enumerate(zip(L["caps"], w)):
                y = x + d * ww / sum(w)
                caps.append({"line": L["id"], "j": j, "text": c, "t0": round(x, 3), "t1": round(y, 3), "kind": "나레"})
                x = y
            t += d
        prev = L["kind"]
    end = round(t + C["tail"], 3)
    for i, c in enumerate(caps):     # 다음 자막까지(벤치: 조각 사이 0.1초 빈칸 — 자막표에 적고 입힐 때 적용)
        nxt = caps[i + 1]["t0"] if i + 1 < len(caps) else end
        c["show"] = [c["t0"], round(min(nxt, end), 3)]
    cuts = []
    order = [L["id"] for L in S["lines"]]
    for lid in order:
        a, b = lines[lid]
        for k, m in enumerate(M["cuts"][lid]):
            if "at" in m:
                c0 = a + float(m["at"])
            else:
                c0 = a if k == 0 else next(c for c in caps if c["line"] == lid and c["j"] == m["toks"][0])["t0"]
            cuts.append({**m, "line": lid, "t0": round(c0, 3)})
    cuts[0]["t0"] = 0.0
    for i, c in enumerate(cuts):     # 컷은 다음 컷까지(줄 사이 틈은 앞 컷이 덮는다)
        c["t1"] = cuts[i + 1]["t0"] if i + 1 < len(cuts) else end
        c["dur"] = round(c["t1"] - c["t0"], 3)
        c["over"] = round(c["dur"] - c["max"], 3) if c.get("max") is not None and c["dur"] > c["max"] else 0.0
    return {"lines": lines, "opos": opos, "caps": caps, "cuts": cuts, "end": end}


SFX_DIR = ROOT / "shopping_shorts/assets/sfx_packs"


def sfx_events(S, T) -> list[dict]:
    """대본 sfx[{at:{line,j}, file, why}] → 초. 벤치: 효과음은 스티커·강조 등장 때만 한 발(스타일분석 §6)."""
    out = []
    for e in S.get("sfx") or []:
        c = next(c for c in T["caps"] if c["line"] == e["at"]["line"] and c["j"] == e["at"]["j"])
        out.append({**e, "t": round(c["t0"] + float(e.get("dt", 0.0)), 3)})
    return out


def add_sfx(mix: Path, ev: list[dict], R: Path, gain_db: float = -6.0) -> Path:
    if not ev:
        return mix
    ins, fc = ["-i", mix], []
    for k, e in enumerate(ev):
        ins += ["-i", SFX_DIR / e["file"]]
        fc.append(f"[{k + 1}:a]aresample=48000,volume={gain_db}dB,adelay={int(e['t'] * 1000)}|{int(e['t'] * 1000)}[s{k}]")
    fc.append("[0:a]" + "".join(f"[s{k}]" for k in range(len(ev))) + f"amix=inputs={len(ev) + 1}:normalize=0:duration=first[o]")
    out = R / "mix_sfx.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[o]", "-ar", 48000, out])
    return out


def frame_for_compose(S, dst: Path) -> dict:
    """프리셋 설명서 → 이 편 값(출처 글) · 덮을 층(제목·워터마크·로고)은 compose 에서 뺀다(spr_overlay 가 그린다)."""
    from tools.calcopy.engine import preset_save as P
    pre, Mf = P.load(PRESET)
    F = P.apply(pre, None, {"layers[text:title].text": "\n".join("".join(t for t, _ in L) for L in S["title_lines"]),
                 "layers[text:label].text": S["source_label"]},
                Mf.get("variable_stats"), None, Mf.get("rules"))
    v = next(l for l in F["layers"] if l["kind"] == "video")
    if (v["y"], v["h"]) != (483, 1058):   # 벤치 8편 창 실측 — 규칙(apply_rules)이 제목 글로 다시 잡은 값이 다르면 멈춘다
        raise StageError(f"창 자리 {v['y']},{v['h']} ≠ 벤치 483,1058 — 제목 글·규칙 확인")
    F["layers"] = [l for l in F["layers"] if not (l["kind"] == "image" or l.get("role") in ("title", "brand"))]
    jsave(dst, F)
    return F


def render_video(S, M, T, R: Path) -> Path:
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    import spr_overlay
    src = Path(M["cand_dir"])
    parts = R / "parts"; shutil.rmtree(parts, ignore_errors=True); parts.mkdir(parents=True)
    lst = []
    for k, c in enumerate(T["cuts"]):
        n = round(c["t1"] * FPS) - round(c["t0"] * FPS)
        c["frames"] = n
        p = parts / f"c{k:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{c['ss']:.3f}", "-i", src / c["src"], "-an", "-vf", RI.crop_vf(c["crop"], *WIN), "-frames:v", n,
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", p])
        lst.append(f"file '{p.as_posix()}'")
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    mat = R / "mat.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", parts / "list.txt", "-c", "copy", mat])
    n = sum(c["frames"] for c in T["cuts"])
    F = frame_for_compose(S, R / "frame.json")
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": round(n / FPS, 3), "narration": "", "caption_lines": [], "role": "hook",
           "primary": {"video_id": "s0", "start": 0.0, "end": round(n / FPS, 3)}}]
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(F))
    seg = R / "seg.mp4"; shutil.rmtree(R / "work", ignore_errors=True)
    scene_style.compose(str(mat), tl, snap, str(seg), R / "work", {"text": ""})
    ov = spr_overlay.build({"lines": S["title_lines"], "watermark": "얜샷템", "logo": "얜샷템"}, R / "overlay.png")
    out = R / "video.mp4"
    run(["ffmpeg", "-y", "-i", seg, "-loop", "1", "-i", ov, "-filter_complex", "[0:v][1:v]overlay=0:0:shortest=1,format=yuv420p[v]", "-map", "[v]",
         "-frames:v", n, "-r", FPS, "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", out])
    return out


def render(doc: Path, work: Path, plan_only=False, log=print) -> dict:
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    R = work / "render"; R.mkdir(parents=True, exist_ok=True)
    tts = [l for l in S["lines"] if l["kind"] == "tts"]
    if plan_only:
        T = timeline(S, M, {l["id"]: round(nchar(l["tts"]) / S["cps_target"], 3) for l in tts})
        jsave(doc / "plan/계획_시간표.json", T)
        for c in T["cuts"]:
            log(f"  {c['line']} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c.get('max')} over {c['over']} {c['src']}@{c['ss']}")
        return T
    full, align = RI.tts_once(S, R, log)
    sent, tempo, inner = RI.make_sentences(S, full, R, log, align=align)
    T = timeline(S, M, {s["id"]: s["dur"] for s in sent})
    over = [c for c in T["cuts"] if c["over"] > 0]
    if over:
        raise StageError("컷이 원본 샷보다 길다: " + str([(c["line"], c["src"], c["ss"], c["dur"], c["max"]) for c in over]))
    vid = render_video(S, M, T, R)
    T["end"] = round(sum(c["frames"] for c in T["cuts"]) / FPS, 3)
    mix, A = RI.audio(S, M, T, sent, R)
    ev = sfx_events(S, T)
    mix = add_sfx(mix, ev, R)
    A["sfx"] = ev
    final = R / "final_nocap.mp4"
    from tools.calcopy.engine.master_guard import encode_final
    A = {**A, "master_guard": encode_final(vid, mix, final, -0.5, log=log)}
    info = {"made_by": "channel/starpickroom/hybrid/render_spr.py", "version": "스타픽룸판(자막 전)", "tempo": tempo, "sentences": sent,
            "timeline": T, "audio": A, "final": str(final), "final_dur": dur_of(final), "final_lufs": lufs(final)}
    jsave(R / "render_info.json", info)
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, doc / "final_nocap_sheet_1s.jpg")
    log(f"final {final} {info['final_dur']:.2f}초 LUFS/TP {info['final_lufs']}")
    return info


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("doc"); ap.add_argument("work"); ap.add_argument("--plan", action="store_true")
    a = ap.parse_args()
    render(Path(a.doc), Path(a.work), plan_only=a.plan)
