# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 **꿀템노트판** 렌더러 — 성시경 신라면 1편 (관제 097, 2026-10-18).

    PYTHONUTF8=1 py channel/kkultemnote/하이브리드_성시경/render_kkt.py [--plan]

벤치 꿀템노트(@꿀템노트-g1z) 1위 편 BpUOIUwkoG4 박자 그대로: 원음 훅 → 나레(전언·질문) ↔ 원음(답) 교대 → 원음 끝.
틀 = 검정 바탕 + 2줄 제목(SBAggroB, 분홍/흰 · 파랑/흰) + 1080² 창(y420) + '출처 : 채널' 줄(y1615) + 댓글 카드(창 아래 걸침).
★자막은 이 렌더에 넣지 않는다 — 자막표.json 만 쓴다(사장님 10-18: 자막팩에 새 효과를 넣은 뒤 그 길로 입힌다).
주인: 시각 = timeline() 한 곳. 대본.json(줄·원음 구간) + 재료.json(컷).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONTS = ROOT / "shopping_shorts/static/fonts"
W, H, WIN_Y, WIN = 1080, 1920, 420, 1080
FPS = 30
SR = 48000


def jload(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode:
        raise RuntimeError(f"rc={r.returncode} {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r


def dur_of(p) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


# ── 나레(Typecast 1회, 글자 시각으로 줄 자르기) ─────────────────────────────
def narr(S, work: Path):
    from tools.calcopy.engine import narr_align as NA
    from tools.calcopy.hybrid.render_itssum import split_by_align
    L = [l for l in S["lines"] if l["kind"] == "tts"]
    text = " ".join(l["tts"] for l in L)
    full = work / "narr_full.mp3"
    align = NA.synth_cached(text, S["voice"]["voice_id"], S["voice"].get("tempo"), full)
    if not align:
        raise RuntimeError("글자 시각 없음 — 줄 자르기 불가")
    spans = split_by_align({"lines": L}, align)
    out = {}
    for l, (a, b) in zip(L, spans):
        p = work / f"n_{l['id']}.wav"
        a0, b0 = max(0.0, a - 0.04), b + 0.06
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a0:.3f}", "-t", f"{b0 - a0:.3f}", "-i", full, "-ar", SR, "-ac", 1,
             "-af", "afade=t=in:d=0.01,areverse,afade=t=in:d=0.02,areverse", p])
        out[l["id"]] = {"wav": p, "dur": dur_of(p), "align_span": [round(a, 3), round(b, 3)], "a0": a0}
    out["_align"] = align
    return out


def cap_times_from_align(S, N):
    """나레 자막 조각 경계 = 그 조각 첫 글자의 글자 시각(Typecast align) — 글자 수 비례 어림 대신(주인 한 곳)."""
    al = N["_align"]; ch = al["characters"]; st = al["character_start_times_seconds"]
    seq = [(c, float(t)) for c, t in zip(ch, st) if c.strip() and c not in ",.?!"]
    k = 0
    for l in [x for x in S["lines"] if x["kind"] == "tts"]:
        a0 = N[l["id"]]["a0"]; starts = []
        caps_txt = [c["text"] for c in l["caps"]]
        line_chars = [c for c in l["tts"] if c.strip() and c not in ",.?!"]
        cap_first = []; pos = 0
        for t in caps_txt:      # 자막 글(숫자 표기)과 tts 글(한글 읽기)이 다를 수 있다 → 조각 비율로 tts 글자 위치를 잡는다
            cap_first.append(pos); pos += len([c for c in t if c.strip() and c not in ",.?!"])
        tot = pos
        for j, cf in enumerate(cap_first):
            idx = k + round(cf / tot * len(line_chars))
            starts.append(round(seq[idx][1] - a0, 2) if j else 0.0)
        k += len(line_chars)
        l["_cap_starts"] = starts


# ── 시간표(시각의 주인) ───────────────────────────────────────────────
def timeline(S, N: dict | None) -> dict:
    t, rows = 0.0, []
    R = S.get("render", {})
    for l in S["lines"]:
        if l["kind"] == "orig":
            a, b = l["span"]; d = b - a
        else:
            d = N[l["id"]]["dur"] if N else max(0.9, len(l["tts"].replace(" ", "")) / S.get("cps_est", 7.2))
        rows.append({"id": l["id"], "kind": l["kind"], "t0": round(t, 3), "t1": round(t + d, 3)})
        t += d + (R.get("gap_after_narr", 0.06) if l["kind"] == "tts" else R.get("gap_after_orig", 0.04))
    return {"rows": rows, "end": round(rows[-1]["t1"] + R.get("tail", 0.35), 3)}


# ── 틀(제목·출처) 그림 ────────────────────────────────────────────────
def frame_png(S, path: Path):
    F = S["frame"]
    im = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    for k, line in enumerate(F["title_lines"]):
        size = F["title_size"][k]
        while True:
            font = ImageFont.truetype(str(FONTS / F["title_font"]), size)
            wid = sum(font.getlength(seg["t"]) for seg in line)
            if wid <= F["title_max_w"] or size <= 60:
                break
            size -= 2
        x = (W - wid) / 2
        top = F["title_top"][k]
        bb = font.getbbox("가")
        for seg in line:
            d.text((x, top - bb[1]), seg["t"], font=font, fill=tuple(seg["rgb"]))
            x += font.getlength(seg["t"])
    cf = ImageFont.truetype(str(FONTS / F["credit_font"]), F["credit_size"])
    cw = cf.getlength(S["source_label"]); cb = cf.getbbox("출")
    d.text(((W - cw) / 2, F["credit_top"] - cb[1]), S["source_label"], font=cf, fill=tuple(F["credit_rgb"]))
    im.paste((0, 0, 0, 0), (0, WIN_Y, W, WIN_Y + WIN))       # 창 자리 투명
    im.save(path)


def comment_png(C: dict, path: Path):
    """유튜브 댓글 카드(벤치 m0Ex 3.0초·KCx 11.6초 실측: 흰 상자, 글 ~30px 검정, 아래 줄 엄지·숫자·엄지아래·'답글')."""
    f = ImageFont.truetype(str(FONTS / "Pretendard-Regular.otf"), C.get("size", 30))
    fs = ImageFont.truetype(str(FONTS / "Pretendard-Regular.otf"), 28)
    sym = ImageFont.truetype("C:/Windows/Fonts/segmdl2.ttf", 32)          # 윤곽 엄지(Like E8E1 · Dislike E8E0) — 벤치 카드도 윤곽선
    tw = f.getlength(C["text"])
    w = int(min(980, tw + 2 * 22)); h = 142
    im = Image.new("RGBA", (w, h), (255, 255, 255, 255)); d = ImageDraw.Draw(im)
    d.text((20, 14), C["text"], font=f, fill=(15, 15, 15))
    d.text((20, 86), "\ue8e1", font=sym, fill=(30, 30, 30))
    d.text((66, 88), str(C["likes"]), font=fs, fill=(96, 96, 96))
    d.text((130, 86), "\ue8e0", font=sym, fill=(30, 30, 30))
    d.text((210, 88), "답글", font=fs, fill=(30, 30, 30))
    im.save(path)
    return w, h


# ── 그림 ─────────────────────────────────────────────────────────────
def cut_list(S, M, T):
    """줄마다 컷 → [{t0,t1,src,ss,crop,see}] (원음 줄은 ss 를 원음 구간 시작에 맞춰 입을 맞춘다)."""
    cuts = []
    for r in T["rows"]:
        cs = M["cuts"][r["id"]]
        span = r["t1"] - r["t0"]
        nxt = next((x["t0"] for x in T["rows"] if x["t0"] > r["t0"]), T["end"])
        span_full = nxt - r["t0"]                                 # 다음 줄 시작까지(쉼 포함) 화면을 채운다
        wsum = sum(c.get("weight", 1) for c in cs); t = r["t0"]
        for k, c in enumerate(cs):
            d = span_full * c.get("weight", 1) / wsum if k < len(cs) - 1 else (r["t0"] + span_full - t)
            if c.get("max") and d > c["max"] + 1e-3:
                raise RuntimeError(f"{r['id']} 컷 {k} {d:.2f}초 > max {c['max']}")
            cuts.append({"line": r["id"], "t0": round(t, 3), "t1": round(t + d, 3), **c})
            t += d
    return cuts


def render_video(S, M, T, work: Path, plan=False):
    src = Path(M["cand_dir"])
    cuts = cut_list(S, M, T)
    (work / "cuts.json").write_text(json.dumps(cuts, ensure_ascii=False, indent=1), encoding="utf-8")
    if plan:
        th = []
        for c in cuts:
            mid = c["ss"] + (c["t1"] - c["t0"]) / 2
            x, y, w, h = c["crop"]
            p = work / f"plan_{len(th):02d}.jpg"
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{mid:.2f}", "-i", src / c["src"], "-frames:v", 1, "-vf", f"crop={w}:{h}:{x}:{y},scale=300:300", p])
            im = Image.open(p); dd = ImageDraw.Draw(im); dd.rectangle((0, 0, 300, 22), fill=(0, 0, 0))
            dd.text((4, 4), f"{c['line']} {c['t0']:.2f}-{c['t1']:.2f}", fill=(255, 230, 0)); th.append(im)
        cols = 6; rows = (len(th) + cols - 1) // cols
        sheet = Image.new("RGB", (300 * cols, 300 * rows))
        for i, im in enumerate(th):
            sheet.paste(im, (300 * (i % cols), 300 * (i // cols)))
        sheet.save(work / "계획_시트.jpg"); return cuts
    parts = []
    for i, c in enumerate(cuts):
        x, y, w, h = c["crop"]; n = round((c["t1"] - c["t0"]) * FPS)
        p = work / f"v_{i:02d}.mp4"
        zoom = c.get("zoom")      # [시작배, 끝배] 천천히 확대(벤치 줌 p90 16%/초)
        vf = f"crop={w}:{h}:{x}:{y},scale={WIN}:{WIN}:flags=lanczos,fps={FPS}"
        if zoom:
            z0, z1 = zoom
            vf = (f"crop={w}:{h}:{x}:{y},scale={WIN * 2}:{WIN * 2}:flags=lanczos,fps={FPS},"
                  f"zoompan=z='{z0}+({z1}-{z0})*on/{max(1, n - 1)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={WIN}x{WIN}:fps={FPS}")
        run(["ffmpeg", "-y", "-v", "error", "-ss", f"{c['ss']:.3f}", "-i", src / c["src"], "-an", "-vf", vf, "-frames:v", n,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", 16, "-pix_fmt", "yuv420p", p])
        parts.append(p)
    lst = work / "parts.txt"; lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    win = work / "win.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", 0, "-i", lst, "-c", "copy", win])
    frame_png(S, work / "frame.png")
    C = S.get("comment")
    ins = ["-i", win, "-loop", 1, "-i", work / "frame.png"]
    fc = f"color=c=black:s={W}x{H}:r={FPS}:d={T['end']:.3f}[bg];[bg][0:v]overlay=0:{WIN_Y}:shortest=0[a];[a][1:v]overlay=0:0[b]"
    last = "b"
    if C:
        cw, ch = comment_png(C, work / "comment.png")
        ins += ["-loop", 1, "-i", work / "comment.png"]
        t0 = next(r["t0"] for r in T["rows"] if r["id"] == C["from"]); t1 = T["end"] if C["to"] == "end" else next(r["t0"] for r in T["rows"] if r["id"] == C["to"])
        fc += f";[b][2:v]overlay={(W - cw) // 2}:{C['bottom'] - ch}:enable='between(t,{t0:.3f},{t1:.3f})'[c]"; last = "c"
    out = work / "video.mp4"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc + f";[{last}]format=yuv420p[v]", "-map", "[v]", "-t", f"{T['end']:.3f}",
         "-r", FPS, "-c:v", "libx264", "-preset", "medium", "-crf", 17, out])
    return cuts


# ── 소리 ─────────────────────────────────────────────────────────────
def render_audio(S, M, T, N, work: Path):
    src = Path(M["cand_dir"]); R = S.get("render", {})
    ins, fl, mix = [], [], []
    for r in T["rows"]:
        l = next(x for x in S["lines"] if x["id"] == r["id"])
        k = len(ins) // 2
        if l["kind"] == "orig":
            a, b = l["span"]
            ins += ["-i", src / l["src"]]
            fl.append(f"[{k}:a]atrim={a}:{b},asetpts=PTS-STARTPTS,aresample={SR},aformat=channel_layouts=mono,highpass=f=90,"
                      f"volume={R.get('orig_db', 0)}dB,afade=t=in:d=0.015,afade=t=out:st={b - a - 0.02:.3f}:d=0.02,adelay={int(r['t0'] * 1000)}[s{k}]")
        else:
            ins += ["-i", N[r["id"]]["wav"]]
            fl.append(f"[{k}:a]aresample={SR},aformat=channel_layouts=mono,volume={R.get('narr_db', 0)}dB,adelay={int(r['t0'] * 1000)}[s{k}]")
        mix.append(f"[s{k}]")
    kv = len(ins) // 2
    fc = ";".join(fl) + f";{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=longest,apad=whole_dur={T['end']:.3f}[voice]"
    voice = work / "voice.wav"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", fc, "-map", "[voice]", "-t", f"{T['end']:.3f}", "-ar", SR, voice])
    bg = ROOT / "shopping_shorts/assets/bgm_lib" / f"{S['bgm']['id']}.mp3"
    out = work / "audio.wav"
    fc2 = (f"[0:a]aformat=channel_layouts=stereo[v];[1:a]atrim=0:{T['end']:.3f},asetpts=PTS-STARTPTS,aresample={SR},volume={S['bgm']['db']}dB,"
           f"afade=t=out:st={T['end'] - 0.4:.3f}:d=0.4,aformat=channel_layouts=stereo[m];[v][m]amix=inputs=2:normalize=0:duration=first,"
           f"loudnorm=I={R.get('target_lufs', -15.3)}:TP=-1.8:LRA=7[o]")
    run(["ffmpeg", "-y", "-v", "error", "-i", voice, "-stream_loop", -1, "-i", bg, "-filter_complex", fc2, "-map", "[o]", "-ar", SR, out])
    return out


def caption_table(S, T, N):
    """자막표.json — 자막 입히기 직전 상태(지휘자가 자막팩 새 효과로 입힌다). 원음 줄은 caps_rel(원음 구간 상대 초), 나레 줄은 글자 시각."""
    rows = []
    for r in T["rows"]:
        l = next(x for x in S["lines"] if x["id"] == r["id"])
        for c in l.get("caps", []):
            rows.append({"line": l["id"], "who": "원음" if l["kind"] == "orig" else "나레",
                         "t0": round(r["t0"] + c["at"][0], 2), "t1": round(r["t0"] + c["at"][1], 2), **{k: v for k, v in c.items() if k != "at"}})
    return rows


def main():
    plan = "--plan" in sys.argv
    S = jload(HERE / "대본.json"); M = jload(HERE / "재료.json")
    work = Path(S["work_dir"]); work.mkdir(parents=True, exist_ok=True)
    N = None if plan else narr(S, work)
    T = timeline(S, N)
    if N:
        cap_times_from_align(S, N)
    for l in S["lines"]:
        if l["kind"] == "tts":
            d = next(r for r in T["rows"] if r["id"] == l["id"]); dur = d["t1"] - d["t0"]
            st = l.get("_cap_starts") or [round(sum(len(c["text"]) for c in l["caps"][:j]) / sum(len(c["text"]) for c in l["caps"]) * dur, 2) for j in range(len(l["caps"]))]
            for j, c in enumerate(l["caps"]):
                c["at"] = [st[j], st[j + 1] if j + 1 < len(st) else round(dur, 2)]
    (work / "timeline.json").write_text(json.dumps(T, ensure_ascii=False, indent=1), encoding="utf-8")
    render_video(S, M, T, work, plan=plan)
    if plan:
        print("계획 시트", work / "계획_시트.jpg", "길이", T["end"]); return
    a = render_audio(S, M, T, N, work)
    final = work / "final_nocap.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", work / "video.mp4", "-i", a, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-shortest", final])
    tab = {"_note": "자막 입히기 직전 — 이 표대로 자막팩(kkultemnote 보강안)으로 입힌다. 초는 final_nocap.mp4 기준.",
           "video": str(final), "pack": "kkultemnote(보강안 channel/kkultemnote/자막팩_보강안.json)",
           "style_keys": {"orig": "speakers.orig(꾸불림 90 흰·검정 테, 컷인)", "orig_pop": "variants.orig_pop(popOvershoot 380ms)",
                          "orig_red": "variants.orig_red(빨강 #F51814, 컷인)", "narr": "speakers.narr(굵은 고딕 83 흰 + emph 노랑 #FDF60E, flashIn 66ms)"},
           "stickers": [{"kind": "comment_card", "in_video": True, "t0": next(r["t0"] for r in T["rows"] if r["id"] == S["comment"]["from"]), "t1": T["end"],
                         "text": S["comment"]["text"], "likes": S["comment"]["likes"], "note": "렌더에 이미 들어 있음(틀 층) — 자막 입힐 때 다시 넣지 말 것"}],
           "timeline": T, "narr_align": {k: v["align_span"] for k, v in N.items() if not k.startswith("_")}, "rows": caption_table(S, T, N)}
    (HERE / "자막표.json").write_text(json.dumps(tab, ensure_ascii=False, indent=1), encoding="utf-8")
    print("완성(자막 전)", final, "길이", T["end"])


if __name__ == "__main__":
    main()
