# -*- coding: utf-8 -*-
"""현장썰 하이브리드 렌더 — 앞 = 이미 만든 현장썰 완성본 0~cut 초 그대로, 뒤 = 잇썸홈판 나레(하이브리드 렌더러 B 부분을 그대로 부름).

    PYTHONUTF8=1 py channel/hottemreport/현장썰하이브리드/render_front.py <doc_dir> <work_dir> [--plan] [--desktop <mp4>]

얜샷템 하이브리드 렌더러(tools/calcopy/hybrid/render_itssum.py)는 앞이 '연예인 원음(A)'이라 앞 영상을 통째로 받는 칸이 없다.
그래서 TTS·문장 자르기·B 화면(잇썸홈 전체화면_가운데자막 프리셋)은 그 함수를 **부르고**, 여기서 정하는 것은 둘뿐이다:
  ① 뒤 시간표(b_timeline — A 가 없으니 0초부터 B 줄을 잇는다. 컷·자막 규칙은 render_itssum.timeline 의 B 부분과 같은 꼴)
  ② 소리 크기 — 뒤 마스터를 앞 완성본의 LUFS(front.target_lufs)에 맞춘다(앞 −15.5 / 하이브리드 기본 −8.6 을 쓰면 이음매에서 소리가 확 커진다).
대본.json: front{src,cut,target_lufs} · voice · cps_target · bgm{id,db_below_voice} · lines[{id,kind:tts,seg:B,tts,caps}]
재료.json: cand_dir · B[{line,toks,src,ss,max,crop,see}]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import render_itssum as RI  # noqa: E402
from tools.calcopy.hybrid.common import FPS, SR, StageError, dur_of, jload, jsave, lufs, nchar, run  # noqa: E402

GAP, TAIL = 0.20, 0.50


def b_timeline(S, M, sent: dict) -> dict:
    Lm = {l["id"]: l for l in S["lines"]}
    ids = RI.b_ids(S)
    lines, t = {}, 0.0
    for k in ids:
        lines[k] = [t, t + sent[k]]
        t += sent[k] + GAP
    end = lines[ids[-1]][1] + TAIL
    caps = []
    for k in ids:
        a, b = lines[k]
        cs = Lm[k]["caps"]
        w = [nchar(c) for c in cs]
        x = a
        for j, (c, ww) in enumerate(zip(cs, w)):
            y = x + (b - a) * ww / sum(w)
            caps.append({"line": k, "j": j, "text": c, "t0": round(x, 3), "t1": round(y, 3), "kind": "나레"})
            x = y
    for i, c in enumerate(caps):
        nxt = caps[i + 1]["t0"] if i + 1 < len(caps) else end
        c["show"] = [c["t0"], round(nxt, 3)]
    cuts = []
    for i, m in enumerate(M["B"]):
        tok0 = next(c for c in caps if c["line"] == m["line"] and c["j"] == m["toks"][0])
        first = i == 0 or M["B"][i - 1]["line"] != m["line"]
        t0 = (0.0 if i == 0 else lines[m["line"]][0]) if first else tok0["t0"]
        cuts.append(dict(m, t0=round(t0, 3)))
    for i, c in enumerate(cuts):
        c["t1"] = cuts[i + 1]["t0"] if i + 1 < len(cuts) else round(end, 3)
        c["dur"] = round(c["t1"] - c["t0"], 3)
        c["over"] = round(c["dur"] - c["max"], 3) if c["dur"] > c["max"] else 0.0
    return {"lines": {k: [round(a, 3), round(b, 3)] for k, (a, b) in lines.items()}, "a_end": 0.0, "end": round(end, 3),
            "caps": caps, "cuts": cuts, "b_ids": ids}


def audio_b(S, T, sent, R: Path, target: float) -> tuple[Path, dict]:
    ins, fc = [], []
    for k, s in enumerate(sent):
        ins += ["-i", s["wav"]]
        fc.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,adelay={int(round(T['lines'][s['id']][0] * 1000))}[p{k}]")
    fc.append("".join(f"[p{k}]" for k in range(len(sent))) + f"amix=inputs={len(sent)}:normalize=0,apad,atrim=0:{T['end']:.3f}[n]")
    voice = R / "voice.wav"
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[n]", "-ar", SR, voice])
    nI, _ = lufs(voice)
    BGM = ROOT / "shopping_shorts/assets/bgm_lib" / f"{S['bgm']['id']}.mp3"
    bI, _ = lufs(BGM)
    g = round((nI - S["bgm"]["db_below_voice"]) - bI, 2)
    end = T["end"]
    raw = R / "mix_raw.wav"
    run(["ffmpeg", "-y", "-i", voice, "-stream_loop", "-1", "-i", BGM, "-filter_complex",
         f"[1:a]aresample={SR},aformat=channel_layouts=mono,atrim=0:{end:.3f},asetpts=PTS-STARTPTS,volume={g}dB,"
         f"afade=t=in:d=0.3,afade=t=out:st={end - 0.6:.3f}:d=0.6[b];[0:a][b]amix=inputs=2:normalize=0:duration=first[o]",
         "-map", "[o]", "-ar", SR, raw])
    mix = R / "mix_b.wav"
    rI, _ = lufs(raw)
    gain = round(target - rI, 2)
    for _ in range(6):                     # 리미터가 먹는 만큼 올려 맞춘다(±0.3)
        run(["ffmpeg", "-y", "-i", raw, "-af", f"volume={gain}dB,alimiter=limit=0.89:level=false:attack=1:release=30", "-ar", SR, mix])
        got, _ = lufs(mix)
        if abs(got - target) <= 0.3:
            break
        gain = round(gain + (target - got), 2)
    return mix, {"narr_lufs": nI, "bgm_gain": g, "gain": gain, "mix_lufs": lufs(mix)}


def render(doc: Path, work: Path, plan_only=False, desktop: Path | None = None, log=print) -> dict:
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    R = work / "render"
    R.mkdir(parents=True, exist_ok=True)
    if plan_only:
        est = {l["id"]: round(nchar(l["tts"]) / S["cps_target"], 3) for l in RI.tts_lines(S)}
        T = b_timeline(S, M, est)
        for c in T["cuts"]:
            log(f"  {c['line']} {c['t0']:6.2f}~{c['t1']:6.2f} {c['dur']:.2f}s max {c['max']} over {c['over']} {c['src']}@{c['ss']}")
        return {"timeline": T}
    full, align = RI.tts_once(S, R, log)
    sent, tempo, _ = RI.make_sentences(S, full, R, log, align=align)
    T = b_timeline(S, M, {s["id"]: s["dur"] for s in sent})
    over = [c for c in T["cuts"] if c["over"] > 0]
    if over:
        raise StageError("컷이 원본 샷보다 길다: " + str([(c["line"], c["src"], c["ss"], c["dur"], c["max"]) for c in over]))
    b_vid, nb = RI.render_b(S, M, T, R)
    T["end"] = round(nb / FPS, 3)
    fr = S["front"]
    mix, A = audio_b(S, T, sent, R, float(fr.get("target_lufs", -15.5)))
    back = R / "back.mp4"
    run(["ffmpeg", "-y", "-i", b_vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "1", "-shortest", back])
    nf = int(float(fr["cut"]) * FPS)                       # 앞은 프레임 단위로 자른다(cut 안쪽)
    fdur = nf / FPS
    front = R / "front.mp4"
    run(["ffmpeg", "-y", "-i", fr["src"], "-frames:v", nf, "-af", f"atrim=0:{fdur:.4f},afade=t=out:st={fdur - 0.03:.4f}:d=0.03",
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "1", front])
    # 이어 붙이기: 뒤를 30fps 고정으로 다시 굽고 concat 분리기로 — concat 필터는 뒤 영상(b_seg, 프레임 간격 들쭉날쭉)에서 화면을 14초로 잘라 먹었다(10-18 실측)
    back_cfr = R / "back_cfr.mp4"
    run(["ffmpeg", "-y", "-i", back, "-vf", f"fps={FPS}", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "1", back_cfr])
    (R / "fb.txt").write_text(f"file '{front.as_posix()}'\nfile '{back_cfr.as_posix()}'\n", encoding="utf-8")
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", R / "fb.txt", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "1", final])
    info = {"made_by": "channel/hottemreport/현장썰하이브리드/render_front.py", "front_cut": fdur, "tempo": tempo, "sentences": sent, "timeline": T,
            "audio": A, "front_lufs": lufs(front), "back_lufs": lufs(back), "final": str(final), "final_dur": dur_of(final), "final_lufs": lufs(final)}
    jsave(R / "render_info.json", info)
    from tools.calcopy.engine.remake import sheet_1s
    sheet_1s(final, doc / "final_sheet_1s.jpg")
    if desktop:
        import shutil
        from tools.calcopy.hybrid.common import md5
        Path(desktop).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(final, desktop)
        info["desktop"] = {"path": str(desktop), "md5_same": md5(final) == md5(desktop)}
        jsave(R / "render_info.json", info)
    log(f"final {final} {info['final_dur']:.2f}s 앞 {info['front_lufs']} 뒤 {info['back_lufs']} 전체 {info['final_lufs']}")
    return info


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("doc"); ap.add_argument("work")
    ap.add_argument("--plan", action="store_true"); ap.add_argument("--desktop")
    a = ap.parse_args()
    render(Path(a.doc), Path(a.work), plan_only=a.plan, desktop=Path(a.desktop) if a.desktop else None)


if __name__ == "__main__":
    main()
