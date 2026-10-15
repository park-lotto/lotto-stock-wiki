# -*- coding: utf-8 -*-
"""나레 있는 칼카피 한 편 — 틀 여러 장(훅 카드·본문) + 누적형 자막 + 가변 그림 칸 + TTS 나레 + BGM (관제 097, 2026-10-16).

remake_video.py(나레 없는 '원음+자막')의 짝. yummyknow rGFXQlS9Cp4 꼴:
  - 틀: 구간마다 다른 frame.json (0~훅 끝 = 훅 카드, 그 뒤 = 본문 게시글). 구간마다 scene_style.compose 로 그리고 잇는다.
  - 자막: 나레 문장을 한 줄 조각(약 14자)으로 나눠 1줄 → 1줄+2줄(줄바꿈 \\n) → 새 1줄 … (누적형). 렌더러는 lines>1 자막을 pre-line 으로 그린다.
  - 시각: TTS 한 파일의 말 구간(silencedetect)에 글자 수 비례로 놓고, 조각 경계는 가까운 쉼(±0.4초)에 붙인다.
  - 그림 칸: 재료.json shots[i].box_w(기본 750px)로 폭을 맞춰 창 맨 위 가운데에 놓고 나머지는 흰 바탕(원본: 컷마다 크기 다름).
  - 컷: 새 1줄 조각이 시작할 때(원본 컷=자막교체 1.0).

    PYTHONUTF8=1 py tools/calcopy/narr_video.py <plan.json>
plan = {"tteutgi","frames":[{"frame","t_end"}...],"script","tts","materials","out","bgm","bgm_ratio","lufs","chunk"}
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import bgm_lib, scene_style, video_assemble as va  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402
from tools.calcopy.remake_video import _lufs  # noqa: E402


# ── 자막 조각 ─────────────────────────────────────────────────────────────
def chunk_sentence(s: str, n: int = 14) -> list[str]:
    """문장 → 한 줄 조각들(공백 제외 n자 안팎, 쉼표 뒤에서 먼저 끊는다). 원본 한 줄 중앙 ≈ 10~14자(OCR 실측)."""
    words, out, cur = s.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if cur and len(cand.replace(" ", "")) > n:
            out.append(cur); cur = w
        else:
            cur = cand
        if cur.endswith(",") and len(cur.replace(" ", "")) >= n * 0.6:
            out.append(cur); cur = ""
    if cur:
        out.append(cur)
    return [o.rstrip(",") for o in out]


def steps_of(sentences: list[str], n: int = 14) -> list[dict]:
    """누적형 단계: 조각 짝마다 [1줄] → [1줄\\n2줄]. 문장이 바뀌면 새로. 반환 [{text, chars(새로 읽는 글자), new_cut}]"""
    steps = []
    subs = [x for line in sentences for x in re.split(r"(?<=[?.!])\s+", line.strip()) if x]   # 한 줄에 문장 여럿이면 문장마다 새로
    for si, s in enumerate(subs):
        ch = chunk_sentence(s, n)
        for k in range(0, len(ch), 2):
            a = ch[k]
            steps.append({"text": a, "chars": len(a.replace(" ", "")), "new_cut": True, "sent": si})
            if k + 1 < len(ch):
                steps.append({"text": a + "\n" + ch[k + 1], "chars": len(ch[k + 1].replace(" ", "")), "new_cut": False, "sent": si})
    return steps


def speech_segments(audio: str, noise="-38dB", d=0.12) -> tuple[list[tuple[float, float]], float]:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", audio, "-af", f"silencedetect=noise={noise}:d={d}", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    st = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r)]
    en = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r)]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio],
                               capture_output=True, text=True).stdout.strip())
    sil = sorted(zip(st, en + [dur] * (len(st) - len(en))))
    segs, t = [], 0.0
    for a, b in sil:
        if a > t + 0.05:
            segs.append((t, a))
        t = max(t, b)
    if dur > t + 0.05:
        segs.append((t, dur))
    return segs, dur


def time_steps(steps: list[dict], audio: str, snap: float = 0.4) -> tuple[list[dict], float]:
    """글자 수 비례로 말 구간에 놓고, 조각 시작을 가까운 말 구간 시작(쉼 끝)에 붙인다."""
    segs, dur = speech_segments(audio)
    total_speech = sum(b - a for a, b in segs)
    total_chars = sum(s["chars"] for s in steps)

    def at(frac):   # 말 시간 비율 → 실제 시각
        x = frac * total_speech
        for a, b in segs:
            if x <= b - a:
                return a + x
            x -= b - a
        return segs[-1][1]
    starts, c = [], 0
    for s in steps:
        t = at(c / total_chars)
        near = min((a for a, _ in segs), key=lambda a: abs(a - t))
        starts.append(near if abs(near - t) <= snap else t)
        c += s["chars"]
    starts[0] = 0.0
    for i in range(1, len(starts)):            # 순서 보장(붙이기로 뒤집히지 않게)
        starts[i] = max(starts[i], starts[i - 1] + 0.3)
    out = [{**s, "t0": round(starts[i], 3), "t1": round(starts[i + 1] if i + 1 < len(starts) else dur, 3)} for i, s in enumerate(steps)]
    return out, dur


# ── 재료(그림 칸) ──────────────────────────────────────────────────────────
def shot_clip(src, ss, dur, win, box_w, full, out, ar=None):
    """창(win = video 층) 크기 캔버스: full=True 면 꽉 채움(cover), 아니면 흰 바탕 위 box_w 폭 그림을 맨 위 가운데.
    ar = 가로/세로 비율로 먼저 가운데 자르기(가로 소스를 원본 그림 칸처럼 세로로). src 가 그림 파일이면 dur 동안 멈춘 그림."""
    W, H = 1080, 1920
    w, h = win["w"], win["h"]
    top = (H - h) // 2
    pre = f"crop='min(iw,ih*{ar})':'min(ih,iw/{ar})'," if ar else ""
    if full:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},pad={W}:{H}:0:{top}:white,setsar=1,fps=30"
    else:
        bh = h - 16
        vf = (f"scale={box_w}:{bh}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:8:white,"
              f"pad={W}:{H}:0:{top}:white,setsar=1,fps=30")
    still = Path(src).suffix.lower() in (".png", ".jpg", ".jpeg")
    inp = ["-loop", "1", "-i", str(src)] if still else ["-ss", f"{ss:.3f}", "-i", str(src)]
    va._run_ffmpeg(["ffmpeg", "-y", *inp, "-t", f"{dur:.3f}", "-vf", pre + vf, "-an",
                    "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])
    return out


def build(plan: dict):
    out = Path(plan["out"]).resolve()
    shutil.rmtree(out / "work", ignore_errors=True); (out / "work").mkdir(parents=True, exist_ok=True)
    S = json.loads(Path(plan["script"]).read_text(encoding="utf-8"))
    sentences = [l["text"] for l in S["final"]["lines"]]
    M = json.loads(Path(plan["materials"]).read_text(encoding="utf-8"))
    steps, dur = time_steps(steps_of(sentences, plan.get("chunk", 14)), plan["tts"])
    # 훅 카드 끝 = 둘째 문장이 시작하는 시각(원본: 훅 카드 1.5초 = 첫 문장 "…억울했던 이유?" 동안)
    hook_end = plan["frames"][0].get("t_end") or next(s["t0"] for s in steps if s["sent"] >= 1)
    # 훅 카드 구간은 자막 없음(원본: 훅 카드엔 제목만) — 첫 문장 조각은 훅 동안 말로만
    cuts = [s["t0"] for s in steps if s["new_cut"] and s["t0"] >= hook_end - 1e-6]
    cuts = sorted(set([0.0, hook_end] + cuts)) + [dur]
    shots_t = [(a, b) for a, b in zip(cuts, cuts[1:]) if b - a > 0.05]
    mshots = M["shots"]
    if len(mshots) < len(shots_t):
        raise SystemExit(f"재료 컷 {len(mshots)}개 < 필요한 컷 {len(shots_t)}개 — 재료.json shots 를 늘려라(컷 시각: {shots_t})")
    base = Path(M["cand_dir"])
    seg_files = []
    for fi, fr in enumerate(plan["frames"]):
        t_a = 0.0 if fi == 0 else plan["frames"][fi - 1]["t_end"] or hook_end
        t_b = fr.get("t_end") or dur
        if fi == 0:
            t_b = hook_end
        frame = json.loads(Path(fr["frame"]).read_text(encoding="utf-8"))
        spec = schema.validate(frame)
        win = next(l for l in spec["layers"] if l["kind"] == "video")
        has_cap = any(l["kind"] == "text" and l["role"] == "caption" for l in spec["layers"])
        parts = []
        for k, (a, b) in enumerate(shots_t):
            if b <= t_a + 1e-6 or a >= t_b - 1e-6:
                continue
            a2, b2 = max(a, t_a), min(b, t_b)
            sh = mshots[k]
            p = out / "work" / f"f{fi}_s{k:02d}.mp4"
            parts.append(shot_clip(base / sh["src"], sh["ss"] + (a2 - a), b2 - a2, win, sh.get("box_w", 750), sh.get("full", fi == 0), p, sh.get("ar")))
        lst = out / "work" / f"f{fi}.txt"
        lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        mat = out / "work" / f"f{fi}_mat.mp4"
        va._run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                        "-shortest", "-c:v", "copy", "-c:a", "aac", str(mat)])
        tl, bi = [], 0
        for s in steps:
            a, b = max(s["t0"], t_a), min(s["t1"], t_b)
            if b - a <= 0.02:
                continue
            txt = s["text"] if has_cap else ""
            tl.append({"beat_idx": bi, "t0": round(a - t_a, 3), "dur": round(b - a, 3), "narration": txt, "caption_lines": [txt] if txt else [],
                       "role": "hook" if bi == 0 else "body", "primary": {"video_id": "s0", "start": a - t_a, "end": b - t_a}})
            bi += 1
        title = next((l for l in spec["layers"] if l["kind"] == "text" and l["role"] == "title"), None)
        snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
        seg = out / "work" / f"seg{fi}.mp4"
        scene_style.compose(str(mat), tl, snap, str(seg), out / "work" / f"compose{fi}", {"text": (title or {}).get("text") or ""})
        seg_files.append(seg)
    vlist = out / "work" / "segs.txt"
    vlist.write_text("".join(f"file '{p.as_posix()}'\n" for p in seg_files), encoding="utf-8")
    vid = out / "work" / "video.mp4"
    # ★-c copy 로 이으면 두 조각의 시간 단위가 달라 r_frame_rate 120 이 됐다(대조가 길이 7.97초로 잼, 10-16) → 다시 인코딩해 30fps 로
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(vlist), "-an", "-r", "30", "-c:v", "libx264", "-crf", "16",
                    "-preset", "veryfast", "-pix_fmt", "yuv420p", str(vid)])
    # 소리: 나레(목표 LUFS) + BGM(나레 대비 비율) — 원본 '원음 깔림 False'
    target = plan.get("lufs", -16.2)
    bgm = bgm_lib.path_of(plan.get("bgm")) if plan.get("bgm") else None
    fc = f"[1:a]loudnorm=I={target}:TP=-1.5:LRA=11,aresample=48000[n]"
    ins = ["-i", plan["tts"]]
    if bgm:
        ins += ["-stream_loop", "-1", "-i", bgm]
        fc += (f";[2:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,loudnorm=I={target}:TP=-1.5:LRA=11,aresample=48000,volume={plan.get('bgm_ratio', 0.15)}[b]"
               f";[n][b]amix=inputs=2:normalize=0:duration=first[m]")
    fc += f";[{'m' if bgm else 'n'}]alimiter=limit=0.89:level=false[a]"
    mixed = out / "work" / "mixed.wav"
    va._run_ffmpeg(["ffmpeg", "-y", *ins, "-filter_complex", fc.replace("[1:a]", "[0:a]", 1).replace("[2:a]", "[1:a]", 1),
                    "-map", "[a]", "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(mixed)])
    gain = round(target - _lufs(mixed)["I"], 2)   # 한 번 loudnorm 은 목표보다 ~1dB 덜 나온다(remake_video 와 같은 보정)
    final = out / "final.mp4"
    va._run_ffmpeg(["ffmpeg", "-y", "-i", str(vid), "-i", str(mixed), "-filter_complex", f"[1:a]volume={gain}dB,alimiter=limit=0.89:level=false[a]",
                    "-map", "0:v", "-map", "[a]", "-t", f"{dur:.3f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(final)])
    (out / "timeline.json").write_text(json.dumps({"steps": steps, "hook_end": hook_end, "shots": shots_t, "dur": dur},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "audio.json").write_text(json.dumps({"tts": plan["tts"], "bgm": plan.get("bgm"), "bgm_ratio": plan.get("bgm_ratio", 0.15),
                                                "target_lufs": target, "final": _lufs(final)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("final:", final)
    return final


if __name__ == "__main__":
    build(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")))
