# -*- coding: utf-8 -*-
"""신박리포트 시험편 1 — 대본.json → 완성 mp4 (사장님 10-20 '카운트다운으로 처음 넣고 박창수 위트 멘트').

    PYTHONUTF8=1 py channel/sinbak/시험편1/make.py [tts|build|all]

단계: ① 나레 줄마다 박창수 TTS(있으면 재사용) → 컷 길이 = max(계획, 나레+0.35)
      ② 재료 = 컷마다 원본에서 창 비율 띠를 오려 1080×1920 한가운데(frame_video 규약)
      ③ scene_style.compose(신박발견 프리셋 + 0번 장면 모션그래픽팩 countdown321) — 틀·제목·창 아래 자막·카운트다운은 엔진이 그린다
      ④ 엔진 스키마에 없는 것만 덧입힘: 신박리포트 로고 줄 · 창 안 의성어(manifest.overlay_style 색=뜻)
      ⑤ 소리 = 원음(나레 밑 −12dB) + 나레 + 배경음악 + 효과음 → −14 LUFS · TP −1.5
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
D = json.loads((HERE / "대본.json").read_text(encoding="utf-8"))
WORK = Path("C:/숏템_칼카피/sinbak/ep1/work")
PRESET = ROOT / "channel/sinbak/preset/연회색틀_둥근창_창아래자막"
W, H = 1080, 1920
WIN = (19, 541, 1041, 746)              # frame.json video 층
NARR_VOICE = "tc_6059dad0b83880769a50502f"   # 박창수
COLORS = {"외침": "#F80A50", "과정": "#EFC716", "도구": "#068EF7", "대사": "#04AF0D"}   # manifest.overlay_style.colors
FONT_DIR = ROOT / "shopping_shorts/static/fonts"


def run(cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    return r


def dur_of(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).stdout.strip())


def tts():
    from shopping_shorts.channelkit import providers
    synth = providers.typecast_synth(NARR_VOICE)
    (WORK / "tts").mkdir(parents=True, exist_ok=True)
    out = {}
    for i, s in enumerate(D["shots"]):
        if not s.get("tts"):
            continue
        p = WORK / "tts" / f"{i:02d}.mp3"
        meta = p.with_suffix(".txt")
        if not (p.exists() and meta.exists() and meta.read_text(encoding="utf-8") == s["tts"]):
            synth(s["tts"], str(p))
            meta.write_text(s["tts"], encoding="utf-8")
        out[i] = round(dur_of(p), 3)
        print(i, out[i], s["tts"])
    return out


def plan(td):
    """컷 길이 = max(계획, 나레 0.1초 뒤 시작 + 길이 + 0.25) — 원본 길이를 넘으면 멈춘다."""
    t, rows = 0.0, []
    for i, s in enumerate(D["shots"]):
        d = s["dur"] if i not in td else max(s["dur"], round(td[i] + 0.35, 2))
        if s.get("countdown"):
            d = 2.15                   # 카운트다운 길이(motion-graphics-pack.js duration) — 장면 끝에 맞춰 끝난다
        src = Path(D["src_dir"]) / f"{s['src']}.mp4"
        if s["ss"] + d > dur_of(src) + 0.01:
            raise SystemExit(f"컷 {i}: {s['ss']}+{d} > 원본 {dur_of(src):.2f}초")
        rows.append({**s, "i": i, "t0": round(t, 3), "d": d, "path": str(src)})
        t += d
    return rows


def material(rows):
    vh = WIN[3]; top = (H - vh) // 2
    parts = []
    for r in rows:
        p = WORK / "mat" / f"{r['i']:02d}.mp4"; p.parent.mkdir(parents=True, exist_ok=True)
        # 원본을 가로 1080 으로 맞춘 뒤(720p 도), 창 비율(1080×746) 띠를 cy 중심으로 오린다
        y0 = max(0, min(H - vh, int(r["cy"] - vh / 2)))
        vf = f"scale={W}:{H},crop={W}:{vh}:0:{y0},pad={W}:{H}:0:{top}:black,setsar=1,fps=30"
        run(["ffmpeg", "-y", "-v", "error", "-ss", r["ss"], "-t", r["d"], "-i", r["path"], "-vf", vf,
             "-af", "aresample=48000,aformat=channel_layouts=stereo", "-c:v", "libx264", "-crf", "16", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", p])
        parts.append(p)
    lst = WORK / "mat" / "list.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    out = WORK / "material.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-crf", "16",
         "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", out])
    return out


def compose(rows, mat):
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    frame = json.loads((PRESET / "frame.json").read_text(encoding="utf-8"))
    fz = json.loads(Path("C:/숏템_칼카피/sinbak/work/preset/frame_fzo.json").read_text(encoding="utf-8"))   # 제목 $per_video 실측값(x 96·size 73)
    for l, f in zip(frame["layers"], fz["layers"]):
        if l.get("role") == "title":
            l.update(x=f["x"], size=f["size"], line_h=f["line_h"], text=D["title"])
    snap = to_snapshot.to_snapshot(frame)
    # 0번 장면 = 모션그래픽팩 3·2·1 (효과 상자 484px 정사각 → 창 가운데 y914 에 오게 t 만 옮김)
    cd = {"kind": "mograph", "mograph": "countdown321", "l": 27.6, "t": round((914 - 242) / H * 100, 2), "w": 44.8, "h": 44.8 * 9 / 16,
          "shape": "rect", "fx": "solid", "color": "#FFFFFF", "op": 100, "soft": 0, "rot": 0, "motion": "none"}
    eff = dict(snap.get("effects") or {})
    for r in rows:
        if r.get("countdown"):
            eff[str(r["i"])] = {**(eff.get(str(r["i"])) or {}), "masks": [cd]}
    snap["effects"] = eff
    snap = scene_style.validate_snapshot(snap)
    tl = [{"beat_idx": r["i"], "t0": r["t0"], "dur": r["d"], "narration": r["cap"], "caption_lines": [r["cap"]],
           "role": "hook" if r["i"] == 0 else "body", "primary": {"video_id": "s0", "start": r["t0"], "end": r["t0"] + r["d"]}} for r in rows]
    out = WORK / "composed.mp4"
    scene_style.compose(str(mat), tl, snap, str(out), WORK / "compose", {"text": D["title"]})
    (WORK / "timeline.json").write_text(json.dumps({"rows": rows, "snapshot_effects": snap.get("effects")}, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def overlays(rows):
    """로고 줄 + 창 안 의성어 PNG (엔진 스키마 밖 — manifest.notes '스키마 글자 층에 못 담음')."""
    from PIL import Image, ImageDraw, ImageFont
    od = WORK / "ov"; od.mkdir(parents=True, exist_ok=True)
    items = []
    # 로고 줄 [94,280,773,406] — 신박리포트(우리 것, 벤치 마스코트 안 씀)
    logo = Image.new("RGBA", (680, 126), (0, 0, 0, 0)); g = ImageDraw.Draw(logo)
    g.ellipse((4, 10, 106, 112), outline=(13, 13, 13), width=12); g.line((92, 98, 122, 124), fill=(13, 13, 13), width=14)
    g.text((30, 28), "!", font=ImageFont.truetype(str(FONT_DIR / "BMDOHYEON.ttf"), 64), fill=(248, 10, 80))
    g.text((140, 6), "SINBAK REPORT", font=ImageFont.truetype(str(FONT_DIR / "BMDOHYEON.ttf"), 64), fill=(13, 13, 13))
    g.text((142, 80), "신박리포트", font=ImageFont.truetype(str(FONT_DIR / "BMDOHYEON.ttf"), 36), fill=(90, 90, 90))
    logo.save(od / "logo.png"); items.append({"png": od / "logo.png", "x": 94, "y": 280, "t0": 0, "t1": 999})
    f = ImageFont.truetype(str(FONT_DIR / "BMDOHYEON.ttf"), 106)
    k = 0
    for r in rows:
        for w in r.get("win") or []:
            box = g.textbbox((0, 0), w["text"], font=f, stroke_width=9)
            im = Image.new("RGBA", (box[2] - box[0] + 24, box[3] - box[1] + 24), (0, 0, 0, 0))
            ImageDraw.Draw(im).text((12 - box[0], 12 - box[1]), w["text"], font=f, fill=COLORS[w["color"]], stroke_width=9, stroke_fill=(0, 0, 0))
            p = od / f"w{k:02d}.png"; im.save(p); k += 1
            x = max(WIN[0] + 10, min(WIN[0] + WIN[2] - im.width - 10, int(w["x"] - im.width / 2)))
            y = max(WIN[1] + 10, min(WIN[1] + WIN[3] - im.height - 10, int(w["y"] - im.height / 2)))
            items.append({"png": p, "x": x, "y": y, "t0": r["t0"] + w["at"], "t1": r["t0"] + r["d"]})
    return items


def audio(rows, td, total):
    from shopping_shorts import bgm_lib
    ins, fl, mix = ["-i", str(WORK / "material.mp4")], [], []
    # 원음: 나레 있는 컷은 −12dB, 없는 컷(카운트다운 'three two one')·orig_db 지정 컷은 그 값
    vol = "+".join(f"between(t,{r['t0']},{r['t0'] + r['d']})*{10 ** ((r.get('orig_db', -12 if r.get('tts') else 0)) / 20):.3f}" for r in rows)
    fl.append(f"[0:a]volume='{vol}':eval=frame[o]"); mix.append("[o]")
    n = 1
    for r in rows:
        if r["i"] in td:
            ins += ["-i", str(WORK / "tts" / f"{r['i']:02d}.mp3")]
            ms = int((r["t0"] + 0.1) * 1000)
            fl.append(f"[{n}:a]aresample=48000,volume=1.6,adelay={ms}|{ms}[n{n}]"); mix.append(f"[n{n}]"); n += 1
    ins += ["-stream_loop", "-1", "-i", bgm_lib.path_of("honwaka_puppu")]
    fl.append(f"[{n}:a]aresample=48000,volume=0.12,atrim=0:{total},afade=t=out:st={total - 0.8}:d=0.8[b]"); mix.append("[b]"); n += 1
    sfx = ROOT / "shopping_shorts/assets/sfx_packs/팩21_사장님"
    hits = [(r["t0"], "ding") for r in rows if r.get("sfx") == "ding"] + [(r["t0"] + w["at"], "pop") for r in rows for w in r.get("win") or []]
    for t, name in hits:
        ins += ["-i", str(sfx / f"{name}.wav")]
        ms = int(t * 1000)
        fl.append(f"[{n}:a]aresample=48000,volume=0.5,adelay={ms}|{ms}[s{n}]"); mix.append(f"[s{n}]"); n += 1
    fl.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0,atrim=0:{total}[m]")
    pre = WORK / "mix_pre.wav"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fl), "-map", "[m]", "-ar", "48000", "-ac", "2", pre])
    err = run(["ffmpeg", "-i", pre, "-af", "loudnorm=I=-14:TP=-2.2:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    out = WORK / "mix.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", pre, "-af",
         f"loudnorm=I=-14:TP=-2.2:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true",
         "-ar", "48000", out])
    return out


def build():
    td = {int(k): v for k, v in json.loads((WORK / "tts.json").read_text(encoding="utf-8")).items()}
    rows = plan(td)
    total = round(sum(r["d"] for r in rows), 3)
    mat = material(rows)
    comp = compose(rows, mat)
    items = overlays(rows)
    ins, fl, last = ["-i", str(comp)], [], "0:v"
    for k, it in enumerate(items, 1):
        ins += ["-i", str(it["png"])]
        fl.append(f"[{last}][{k}:v]overlay={it['x']}:{it['y']}:enable='between(t,{it['t0']:.3f},{it['t1']:.3f})'[v{k}]"); last = f"v{k}"
    mix = audio(rows, td, total)
    ins += ["-i", str(mix)]
    final = WORK / "신박리포트_시험편1.mp4"
    run(["ffmpeg", "-y", "-v", "error", *ins, "-filter_complex", ";".join(fl), "-map", f"[{last}]", "-map", f"{len(items) + 1}:a",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "192k", "-t", total, final])
    print("완성:", final, f"{total}초")


if __name__ == "__main__":
    step = sys.argv[1] if len(sys.argv) > 1 else "all"
    WORK.mkdir(parents=True, exist_ok=True)
    if step in ("tts", "all"):
        (WORK / "tts.json").write_text(json.dumps(tts(), ensure_ascii=False), encoding="utf-8")
    if step in ("build", "all"):
        build()
