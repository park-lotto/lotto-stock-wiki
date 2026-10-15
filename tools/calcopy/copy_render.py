# -*- coding: utf-8 -*-
"""칼카피본 렌더 — 썰풀다 A틀을 그대로 재현해 대본 하나를 영상으로 (관제 097, 2026-10-15).

    PYTHONUTF8=1 py tools/calcopy/copy_render.py <대본.json> <장면 mp4 폴더> <출력폴더>

틀(실측 bench_main/layout.json variant A, 원본 15편): 1080×1920 흰 배경(252,249,253) · 로고줄 y10~64 ·
제목 2줄 띠 y117~351(위 검정 / 아래 자홍) · 영상 창 y349~1622 가로 전폭 · 자막 = 창 안 아래쪽 흰 글자+검은 테두리, 강조 연두, 팝 등장.
소리: 타입캐스트 남자 나레(박창수) — 말 속도는 원본 7.4자/초에 맞춰 tempo 를 고른다. 효과음 = sfx_pack(깨끗한 것만) 줄 바뀔 때.
장면: 줄마다 폴더의 클립을 차례로(줄 길이만큼, 클립 안에서 겹치지 않게) — 장면 매칭은 다음 단계.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

W, H = 1080, 1920
WIN = (349, 1621)                  # 영상 창 y 범위
TITLE_Y = (117, 351)
BG = "0xFCF9FD"
FONT_DIR = ROOT / "shopping_shorts/channel_presets/brainbulb/fonts"
FONT = "SB Aggro"                  # SBAggroB.ttf — 원본 제목·자막처럼 굵은 고딕
NARR = "tc_68257f68bc6e3c161ab5078d"     # 필재(숏템 기본 tc-piljae-stable) — 사장님 10-15
TARGET_CPS = 8.2                   # 사장님 "무음 없이 빠르게"(원본 7.4)
GAP = 0.0                         # 줄 사이(원본은 쉬지 않고 이어 말한다)
BGM = ROOT / "shopping_shorts/assets/bgm_lib/otsukare_summer.mp3"   # 쉼(-40dB↓) 0개·하위5% -19.3dB — 끊어 치는 곡은 끊겨 들린다
BGM_GAIN = 0.30                    # 고정 크기(자동 낮추기 없음 — 오르내림이 끊김처럼 들렸다)
MEME_DIR = Path("C:/숏템_칼카피/memes")
SFX_DIR = Path("C:/숏템_칼카피/sseolpulda/sfx_pack")


def _dur(p) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                                capture_output=True, text=True).stdout.strip() or 0)


def _trim(src: Path) -> Path:
    """TTS 앞뒤 무음 자르기 — 줄마다 앞 0.1~0.18s·뒤 0.08~0.24s 무음이 붙어 줄 경계마다 0.3~0.4s 소리가 비었다(10-15 실측)."""
    dst = src.with_suffix(".trim.wav")
    if not dst.exists():
        f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
        mid = "silenceremove=stop_periods=-1:stop_duration=0.1:stop_threshold=-45dB:stop_silence=0.05"   # 문장 안 쉼도 0.05초만
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", f"{f},areverse,{f},areverse,{mid}", str(dst)], check=True)
    return dst


def tts(lines, out: Path, tempo: float):
    from shopping_shorts.channelkit import providers
    synth = providers.typecast_synth(NARR, tempo=tempo)
    parts = []
    for i, t in enumerate(lines):
        f = out / f"n{i:02d}.mp3"
        if not f.exists():
            synth(t, str(f))
        t = _trim(f)
        parts.append((t, _dur(t)))
    return parts


def _ass_time(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def ass(title: list[str], subs: list[tuple[float, float, str]], path: Path):
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: T1,{FONT},124,&H00141414,&H0,&H00FFFFFF,&H0,1,0,0,0,100,100,0,0,1,0,0,8,20,20,0,1
Style: T2,{FONT},124,&H009E1AC8,&H0,&H00FFFFFF,&H0,1,0,0,0,100,100,0,0,1,0,0,8,20,20,0,1
Style: S,{FONT},84,&H00FFFFFF,&H0,&H00000000,&H0,1,0,0,0,100,100,0,0,1,8,0,2,60,60,0,1
Style: AD,{FONT},30,&H00888888,&H0,&H00FFFFFF,&H0,0,0,0,0,100,100,0,0,1,0,0,9,30,30,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    end = subs[-1][1] if subs else 1
    ev = [f"Dialogue: 0,{_ass_time(0)},{_ass_time(end)},AD,,0,0,0,,{{\\pos(1050,20)}}[광고]",
          f"Dialogue: 0,{_ass_time(0)},{_ass_time(end)},T1,,0,0,0,,{{\\pos(540,135)}}{title[0]}",
          f"Dialogue: 0,{_ass_time(0)},{_ass_time(end)},T2,,0,0,0,,{{\\pos(540,240)}}{title[1] if len(title) > 1 else ''}"]
    y = WIN[0] + int((WIN[1] - WIN[0]) * 0.70)
    keys = {w for w in " ".join(title).split() if len(w) >= 2}
    def _hl(t):   # 제목 낱말이 나오면 연두 강조(원본: 강조어 연두)
        return " ".join(r"{\c&H0060FF7A&}" + w + r"{\c&H00FFFFFF&}" if any(k[:2] in w for k in keys) else w for w in t.split())
    for a, b, t in subs:
        t = _hl(t)
        # 팝 등장: 0.12초에 115%→100%
        ev.append(f"Dialogue: 1,{_ass_time(a)},{_ass_time(b)},S,,0,0,0,,{{\\pos(540,{y})\\fscx115\\fscy115\\t(0,120,\\fscx100\\fscy100)}}{t}")
    path.write_text(hdr + "\n".join(ev) + "\n", encoding="utf-8")


def _chunks(text: str, n: int = 14) -> list[str]:
    """자막은 한 줄 짧게(원본 자막 = 구절 단위) — 어절을 n자 안쪽으로 묶는다."""
    out, cur = [], ""
    for w in text.split():
        if cur and len(cur) + 1 + len(w) > n:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def render(script_path: str, clips_dir: str, out_dir: str):
    d = json.loads(Path(script_path).read_text(encoding="utf-8"))
    if isinstance(d, list):
        d = next(x for x in d if x.get("lines"))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    lines = [l["text"] for l in d["lines"]]
    chars = sum(len(t.replace(" ", "")) for t in lines)
    # 1차로 1.0 tempo 길이를 재고 목표 말 속도에 맞춘 tempo 로 다시
    (out / "probe").mkdir(exist_ok=True)
    probe = tts(lines[:1], out / "probe", 1.0)
    base_cps = len(lines[0].replace(" ", "")) / probe[0][1]
    tempo = round(min(1.6, max(1.0, TARGET_CPS / base_cps)), 2)
    narr = tts(lines, out, tempo)
    # 전체 말 속도를 목표에 맞춘다(첫 줄로 고른 tempo 만으로는 모자란다) — 모자란 만큼 atempo
    spoken = sum(d for _, d in narr)
    fac = round(min(1.3, max(1.0, (chars / spoken) and TARGET_CPS / (chars / spoken))), 3)
    if fac > 1.01:
        sped = []
        for f, _ in narr:
            g = f.with_name(f.stem + f".x{fac}.wav")
            if not g.exists():
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-af", f"atempo={fac}", str(g)], check=True)
            sped.append((g, _dur(g)))
        narr = sped
    # 나레 이어 붙이기(줄 사이 0.05초) + 시각표
    t, subs, seg = 0.0, [], []
    for (f, du), text in zip(narr, lines):
        pieces = _chunks(text)
        per = du / max(1, sum(len(p) for p in pieces))
        a = t
        for p in pieces:
            b = a + per * len(p)
            subs.append((a, b, p))
            a = b
        seg.append((t, t + du))
        t += du + GAP
    total = t
    title = (d.get("title") or "").split("\n")
    ass(title, subs, out / "subs.ass")
    # 장면: 줄마다 클립 하나(차례로), 창 크기로 크롭
    wh = WIN[1] - WIN[0]
    picks_p = Path(clips_dir) / "picks.json"
    cuts = []
    if picks_p.exists():
        # 오푸스가 고른 줄별 장면: 동영상(1순위)·사진(2순위, 천천히 확대)·흑백·효과음
        P = {x["i"]: x for x in json.loads(picks_p.read_text(encoding="utf-8"))["lines"]}
        for i, (a, b) in enumerate(seg):
            x = P.get(i, {})
            cuts.append((Path(clips_dir) / x["src"], x.get("start", 0.0), (b - a) + 0.05, x))
    else:
        clips = sorted(Path(clips_dir).glob("*.mp4"))
        used = {}
        for i, (a, b) in enumerate(seg):
            c = clips[i % len(clips)]
            cd = _dur(c)
            st = used.get(c, 0.5)
            if st + (b - a) + 0.1 > cd:
                st = 0.3
            used[c] = st + (b - a) + 0.05
            cuts.append((c, st, (b - a) + 0.05, {"kind": "video"}))
    inputs, fil = [], []
    for k, (c, st, du, x) in enumerate(cuts):
        bw = ",hue=s=0" if x.get("bw") else ""
        if x.get("kind") == "photo":
            inputs += ["-loop", "1", "-t", f"{du:.2f}", "-i", str(c)]
            nf = max(1, int(du * 30))
            zoom = f",zoompan=z='1+0.12*on/{nf}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={nf}:s={W}x{wh}:fps=30" if x.get("zoom") else ""
            fil.append(f"[{k}:v]scale={W*2}:{wh*2}:force_original_aspect_ratio=increase,crop={W*2}:{wh*2}{zoom},scale={W}:{wh},setsar=1,fps=30,"
                       f"format=yuv420p{bw},trim=duration={du:.2f},setpts=PTS-STARTPTS[v{k}]")
        else:
            inputs += ["-ss", f"{st:.2f}", "-t", f"{du:.2f}", "-i", str(c)]
            fil.append(f"[{k}:v]scale={W}:{wh}:force_original_aspect_ratio=increase,crop={W}:{wh},setsar=1,fps=30,"
                       f"format=yuv420p{bw},setpts=PTS-STARTPTS[v{k}]")
    fil.append("".join(f"[v{k}]" for k in range(len(cuts))) + f"concat=n={len(cuts)}:v=1:a=0[win]")
    fil.append(f"color=c={BG}:s={W}x{H}:d={total:.2f}:r=30[bg]")
    memes = []
    for k, (c, st, du, x) in enumerate(cuts):
        if x.get("meme"):
            mf = next(iter(sorted(MEME_DIR.glob(x["meme"] + "_*.mp4"))), None)
            if mf:
                memes.append((k, mf))
    fil.append(f"[bg][win]overlay=0:{WIN[0]}:shortest=1[base0]")
    cur = "base0"
    for n, (k, mf) in enumerate(memes):
        inputs += ["-i", str(mf)]
        j = sum(1 for a in inputs if a == "-i") - 1
        t0 = seg[k][0]
        fil.append(f"[{j}:v]scale=460:-2,setpts=PTS-STARTPTS+{t0:.2f}/TB[m{n}]")
        fil.append(f"[{cur}][m{n}]overlay=W-w-30:{WIN[1]}-h-40:enable='between(t,{t0:.2f},{t0 + 1.2:.2f})':eof_action=pass[base{n + 1}]")
        cur = f"base{n + 1}"
    fil.append(f"[{cur}]null,ass={(out / 'subs.ass').as_posix().replace(':', '\\\\:')}:fontsdir={FONT_DIR.as_posix().replace(':', '\\\\:')}[vout]")
    # 소리: 나레 + 효과음(줄 바뀔 때, 깨끗한 팩에서 돌려 씀)
    def _n():   # 지금까지 넣은 입력 수 = 다음 입력 번호(짤이 앞에 끼어도 번호가 안 밀린다)
        return sum(1 for a in inputs if a == "-i")
    alist = []
    for k, (f, du) in enumerate(narr):
        j = _n()
        inputs += ["-i", str(f)]
        alist.append(f"[{j}:a]adelay={int(seg[k][0] * 1000)}|{int(seg[k][0] * 1000)}[a{k}]")
    sfx = sorted(SFX_DIR.glob("*.wav"))
    sx = []
    for k in range(len(seg)):
        x = cuts[k][3]
        f = (SFX_DIR / x["sfx"]) if x.get("sfx") else (sfx[k % len(sfx)] if (sfx and not picks_p.exists() and k) else None)
        if not f:
            continue
        j = _n()
        inputs += ["-i", str(f)]
        alist.append(f"[{j}:a]volume=0.45,adelay={int(seg[k][0] * 1000)}|{int(seg[k][0] * 1000)}[s{len(sx)}]")
        sx.append(f"[s{len(sx)}]")
    jb = _n()
    inputs += ["-stream_loop", "-1", "-i", str(BGM)]
    alist.append("".join(f"[a{k}]" for k in range(len(narr))) + f"amix=inputs={len(narr)}:normalize=0[nar]")
    alist.append(f"[{jb}:a]volume={BGM_GAIN},atrim=0:{total:.2f}[bg]")
    mix_in = "[nar][bg]" + "".join(sx)
    alist.append(f"{mix_in}amix=inputs={2 + len(sx)}:normalize=0,loudnorm=I=-14:TP=-1.5[aout]")
    fil += alist
    mp4 = out / "칼카피본.mp4"
    cmd = ["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(fil), "-map", "[vout]", "-map", "[aout]",
           "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "192k", str(mp4)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(r.stderr[-1500:])
    meta = {"tempo": tempo, "seconds": round(total, 2), "chars": chars, "cps": round(chars / total, 2),
            "cuts": len(cuts), "subs": len(subs), "sfx": len(sx)}
    (out / "render_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(mp4, meta)
    return mp4


if __name__ == "__main__":
    render(*sys.argv[1:4])
