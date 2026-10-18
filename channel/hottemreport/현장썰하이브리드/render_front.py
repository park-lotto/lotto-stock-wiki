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


# ── 뒤를 '앞과 같은 옷'으로(10-18 사장님 "앞과 뒤가 자연스럽게 전환이 안 된다") ─────────────────────────
# 1차 실측 차이 셋: 목소리(앞 필재 / 뒤 박창수) · 화면 틀(앞 숏템리폿 제목 띠+박스 자막 / 뒤 잇썸홈 전체화면 가운데 자막) · BGM(앞 passo_bem_solto / 뒤 honwaka_puppu).
# back_style:"front" 이면 뒤도 앞 편과 같은 길(1편 make_render 의 nv.build + emph_box + 같은 틀 json)로 굽고, BGM 은 앞 곡을 cut 초부터 이어 튼다.
def _front_mod():
    import importlib.util
    one = ROOT / "channel/hottemreport/현장썰_01_가짜잠자리/make_render.py"
    spec = importlib.util.spec_from_file_location("hj_make_render_front", one)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def render_back_front(S, M, T, sent, R: Path) -> Path:
    from tools.calcopy import narr_video as nv
    mr = _front_mod()
    fs = S["front_style"]
    voice = R / "voice_only.wav"
    ins, fc = [], []
    for k, s in enumerate(sent):
        ins += ["-i", s["wav"]]
        fc.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,adelay={int(round(T['lines'][s['id']][0] * 1000))}[p{k}]")
    fc.append("".join(f"[p{k}]" for k in range(len(sent))) + f"amix=inputs={len(sent)}:normalize=0,apad,atrim=0:{T['end']:.3f}[n]")
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(fc), "-map", "[n]", "-ar", SR, voice])
    ev = []
    for c in T["caps"]:
        a, b = c["show"]
        ev.append({"kind": "emph", "text": c["text"], "rgb": mr.NARR_RGB, "t0": a, "dur": round(b - a, 3), "who": "나레"})
    line = " ".join(l["tts"].replace(",", "").rstrip(".") for l in RI.tts_lines(S)) + "."
    script = R / "back_script.json"
    jsave(script, {"final": {"lines": [{"text": line}]}, "caption_events": ev, "titles": {"hook": fs.get("title", "")}})
    cuts = [{"src": c["src"], "ss": c["ss"], "dur": c["dur"], "block": c["line"], "src_crop": c["crop"], **({"move": c["move"]} if c.get("move") else {})}
            for c in T["cuts"]]   # move = 그림 파일 컷 확대·이동(narr_video.still_move)
    mats = R / "back_materials.json"
    jsave(mats, {"cand_dir": M["cand_dir"], "shots": [{"i": 0, "full": True, "kind": "원본재편집", "src": cuts[0]["src"], "ss": cuts[0]["ss"], "cuts": cuts}]})
    nv.emph_png = mr.emph_box
    out = R / "back_nv"
    plan = {"tteutgi": None, "frames": [{"frame": str(ROOT / fs["frame"]), "t_end": None}], "script": str(script), "tts": str(voice),
            "materials": str(mats), "out": str(out), "bgm": None, "lufs": mr.LUFS_NARR, "chunk": 10, "caption_mode": "replace", "line_asr": False}
    return Path(nv.build(plan))


def bgm_continue(S, vid: Path, R: Path, start: float, target: float) -> Path:
    """앞 편 BGM 곡을 start 초부터 이어 튼다(앞 make_render.bgm_mix 와 같은 loudnorm 값) → 앞과 같은 LUFS 로."""
    mr = _front_mod()
    from shopping_shorts import bgm_lib
    dur = dur_of(vid)
    tmp = R / "back_bgm.wav"
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", bgm_lib.path_of(mr.BGM), "-t", f"{start + dur:.3f}", "-af",
         f"aresample=48000,aformat=channel_layouts=mono,loudnorm=I={mr.BGM_DB}:TP=-6:LRA=11,atrim={start:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={dur - 0.5:.3f}:d=0.5",
         "-c:a", "pcm_s16le", tmp])
    mixed = R / "back_mix.wav"
    run(["ffmpeg", "-y", "-i", vid, "-i", tmp, "-filter_complex",
         "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono[m];[1:a]aformat=sample_fmts=fltp:channel_layouts=mono[b];[m][b]amix=inputs=2:normalize=0:duration=first[a]",
         "-map", "[a]", "-c:a", "pcm_s24le", mixed])
    out = R / "back.mp4"
    g = round(target - lufs(mixed)[0], 2)
    for _ in range(6):
        run(["ffmpeg", "-y", "-i", vid, "-i", mixed, "-filter_complex", f"[1:a]volume={g}dB,alimiter=limit={mr.LIMIT}:attack=3:release=40:level=false[a]",
             "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out])
        got = lufs(out)[0]
        if abs(got - target) <= 0.3:
            break
        g = round(g + (target - got), 2)
    return out


def interest_gate(S: dict) -> None:
    """(판단 주인) 흥미 이음 — 사장님 10-18 "물병 만든 영상 보면 원본 해외 영상이랑 완전 다른, 흥미롭지 못한 물건이야. 이 기준을 세워야겠다".
    앞 원본이 사람을 붙잡은 바로 그 점(원본흥미)이 뒤 쿠팡 제품에도 눈에 보여야 한다(뒤흥미). 판정 '같음'만 굽는다.
    대본.json 흥미이음 = {원본흥미, 뒤흥미, 판정: 같음|약함|없음, 근거}. 설명서 대본설명서.md §0."""
    h = S.get("흥미이음") or {}
    if h.get("판정") != "같음" and not h.get("사장님허락"):
        raise StageError(f"흥미 이음 미달(판정 {h.get('판정', '없음 — 칸을 안 채움')}): 원본흥미 {h.get('원본흥미')!r} / 뒤흥미 {h.get('뒤흥미')!r}"
                         " — 원본의 신기한 점을 가진 쿠팡 제품을 다시 찾는다")


def render(doc: Path, work: Path, plan_only=False, desktop: Path | None = None, log=print) -> dict:
    S, M = jload(doc / "대본.json"), jload(doc / "재료.json")
    interest_gate(S)
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
    fr = S["front"]
    nf = int(float(fr["cut"]) * FPS)                       # 앞은 프레임 단위로 자른다(cut 안쪽)
    fdur = nf / FPS
    if S.get("front_style"):
        back = bgm_continue(S, render_back_front(S, M, T, sent, R), R, fdur, float(fr.get("target_lufs", -15.5)))
        A = {"back_style": "front", "bgm_from": fdur}
    else:
        b_vid, nb = RI.render_b(S, M, T, R)
        T["end"] = round(nb / FPS, 3)
        mix, A = audio_b(S, T, sent, R, float(fr.get("target_lufs", -15.5)))
        back = R / "back.mp4"
        run(["ffmpeg", "-y", "-i", b_vid, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "1", "-shortest", back])
    front = R / "front.mp4"
    run(["ffmpeg", "-y", "-i", fr["src"], "-frames:v", nf, "-af", f"atrim=0:{fdur:.4f},afade=t=out:st={fdur - 0.03:.4f}:d=0.03",
         "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "1", front])
    # 이어 붙이기: 뒤를 30fps 고정으로 다시 굽고 concat 분리기로 — concat 필터는 뒤 영상(b_seg, 프레임 간격 들쭉날쭉)에서 화면을 14초로 잘라 먹었다(10-18 실측)
    back_cfr = R / "back_cfr.mp4"
    run(["ffmpeg", "-y", "-i", back, "-vf", f"fps={FPS}", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "1", back_cfr])
    final = R / "final.mp4"
    tr = S.get("transition")
    if tr:
        # 전환 효과: 앞 마지막 프레임을 tr.dur 만큼 늘려(tpad) 뒤 첫 tr.dur 와 xfade — 소리는 그대로 이어 붙여 길이·입 맞춤이 안 바뀐다
        d = float(tr.get("dur", 0.3))
        band = int(tr.get("keep_top", 560))   # 위 제목 띠(앞·뒤 같은 틀)는 넘기지 않고 그대로 — 1차 시험에서 띠까지 옆으로 밀려 어색(눈 확인)
        run(["ffmpeg", "-y", "-i", front, "-i", back_cfr, "-filter_complex",
             f"[0:v]tpad=stop_mode=clone:stop_duration={d:.3f},settb=AVTB,fps={FPS},split[f][fb];[fb]crop=1080:{band}:0:0[band];[1:v]settb=AVTB,fps={FPS}[b];"
             f"[f][b]xfade=transition={tr.get('kind', 'zoomin')}:duration={d:.3f}:offset={fdur:.4f}[x];[x][band]overlay=0:0:eof_action=pass,format=yuv420p[v];"
             "[0:a][1:a]concat=n=2:v=0:a=1[a]",
             "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-ac", "1", final])
    else:
        (R / "fb.txt").write_text(f"file '{front.as_posix()}'\nfile '{back_cfr.as_posix()}'\n", encoding="utf-8")
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
