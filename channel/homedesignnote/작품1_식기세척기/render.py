# -*- coding: utf-8 -*-
"""두유노홈디노(잇썸홈) 작품1 싱크대 식기세척기 — 박창수 TTS 1회 → 말속도 8.3자/초 → 토막=컷 재료 → 프리셋 틀(라이브 렌더러) → 나레+BGM.

    PYTHONUTF8=1 py channel/homedesignnote/작품1_식기세척기/render.py

입력: 같은 폴더 대본.json(tokens)·재료.json(shots) — make_plan.py 산출. 틀 = channel/homedesignnote/preset/전체화면_가운데자막(기본값).
규칙: 짤 0·효과음 0·원음 끔·BGM honwaka_puppu 나레 −14dB(원본 bench 14.4dB)·브랜드 잇썸홈.
★타입캐스트 1회 — narr_full.mp3 가 있으면 다시 안 부른다.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy import narr_video as N  # noqa: E402
from tools.calcopy.engine import preset_save as P  # noqa: E402

D = Path(__file__).parent
SRC = Path("C:/숏템_칼카피/homedesignnote/작품1_식기세척기")
R = SRC / "render"
PRESET = ROOT / "channel/homedesignnote/preset/전체화면_가운데자막"
VOICE = "tc_6059dad0b83880769a50502f"   # 박창수
CPS = 8.32
BGM = ROOT / "shopping_shorts/assets/bgm_lib/honwaka_puppu.mp3"
BGM_DB_BELOW = 14.4
TARGET_LUFS, TP = -9.0, -2.0            # 원본 50편 중앙 −7.5 ±1.5 안 · 리미터 −2 dBFS(aac 뒤 최고점 ≤ −0.5 — 1판 −1 로는 +0.2)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


def dur_of(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    import re
    I = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]); tp = float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])
    return I, tp


def main():
    R.mkdir(parents=True, exist_ok=True)
    S = json.loads((D / "대본.json").read_text(encoding="utf-8"))
    M = json.loads((D / "재료.json").read_text(encoding="utf-8"))
    lines = [l["tts"] for l in S["lines"]]
    full, tight, narr = R / "narr_full.mp3", R / "narr_tight.wav", R / "narr.wav"
    if not full.exists():
        from shopping_shorts.channelkit import providers
        providers.typecast_synth(VOICE)(" ".join(lines), str(full))
        print("TTS 1회:", full)
    if not tight.exists():
        f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
        mid = "silenceremove=stop_periods=-1:stop_duration=0.15:stop_threshold=-45dB:stop_silence=0.1"
        run(["ffmpeg", "-y", "-i", str(full), "-af", f"{f},areverse,{f},areverse,{mid}", str(tight)])
    chars = sum(t["chars"] for t in S["tokens"])
    d0 = dur_of(tight)
    tempo = round(min(1.35, max(0.8, CPS / (chars / d0))), 4)
    run(["ffmpeg", "-y", "-i", str(tight), "-af", f"atempo={tempo}", "-ar", "44100", str(narr)])
    dn = dur_of(narr)
    print(f"TTS 말속도 {chars / d0:.2f} → atempo {tempo} → {chars / dn:.2f}자/초, {dn:.2f}초")

    steps = [{"text": t["text"], "chars": t["chars"], "new_cut": True, "sent": t["line"], "line": t["line"]} for t in S["tokens"]]
    timed, dur = N.time_steps(steps, str(narr), lines=[x["text"] for x in S["lines"]])
    END = round(dur + 0.4, 3)             # 끝 여운 0.4초
    timed[-1]["t1"] = END

    # 재료: 토막마다 컷 1개(프레임 정확), 9:16 crop → 1080×1920, 원음 없음
    parts = R / "parts"; shutil.rmtree(parts, ignore_errors=True); parts.mkdir()
    lst = []
    for k, (st, sh) in enumerate(zip(timed, M["shots"])):
        n = max(1, round(st["t1"] * 30) - round(st["t0"] * 30))
        x, y, w, h = sh["src_crop"]
        out = parts / f"p{k:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{sh['ss']:.3f}", "-i", str(SRC / sh["src"]), "-an",
             "-vf", f"crop={w}:{h}:{x}:{y},scale=1080:1920:flags=lanczos,setsar=1,fps=30", "-frames:v", str(n),
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])
        lst.append(f"file '{out.as_posix()}'")
        st["frames"] = n
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    mat = R / "material.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(parts / "list.txt"), "-c", "copy", str(mat)])

    # 틀(프리셋 기본값: 자막 y 927·잇썸홈) → 라이브 렌더러
    from shopping_shorts import scene_style
    from shopping_shorts.calcopy_frame import to_snapshot
    pre, Mf = P.load(PRESET)
    F = P.apply(pre, None, None, Mf["variable_stats"], None, Mf["rules"])
    (R / "frame.json").write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    t = 0.0
    tl = []
    for i, st in enumerate(timed):
        a, b = round(t, 3), round(t + st["frames"] / 30, 3)
        tl.append({"beat_idx": i, "t0": a, "dur": round(b - a, 3), "narration": st["text"], "caption_lines": [st["text"]],
                   "role": "hook" if i == 0 else "body", "primary": {"video_id": "s0", "start": a, "end": b}})
        t = b
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(F))
    vid = R / "video.mp4"
    if "--audio-only" not in sys.argv or not vid.exists():
        shutil.rmtree(R / "work", ignore_errors=True)
        scene_style.compose(str(mat), tl, snap, str(vid), R / "work", {"text": ""})
    (R / "timeline.json").write_text(json.dumps({"tempo": tempo, "tl": tl, "timed": timed}, ensure_ascii=False, indent=1), encoding="utf-8")

    # 소리: 나레 + BGM(나레 LUFS − 14.4) → 목표 LUFS
    nI, _ = lufs(narr)
    bI, _ = lufs(BGM)
    g = (nI - BGM_DB_BELOW) - bI
    mix = R / "mix.wav"
    run(["ffmpeg", "-y", "-i", str(narr), "-stream_loop", "-1", "-i", str(BGM), "-filter_complex",
         f"[1:a]volume={g:.2f}dB,atrim=0:{t:.3f},afade=t=out:st={max(0, t - 0.6):.3f}:d=0.6[b];[0:a]apad=whole_dur={t:.3f}[n];"
         f"[n][b]amix=inputs=2:normalize=0:duration=first[o]", "-map", "[o]", "-ar", "44100", str(R / "mix_raw.wav")])
    # loudnorm 은 최고점 한도 때문에 −14 에서 멈췄다(1판 실측) → 이득 + 리미터(−1 dBFS)로 목표 LUFS
    mI, _ = lufs(R / "mix_raw.wav")
    gain = 16.0   # 압축 뒤 이득 시작값(10-17 실측: 16→−10.6 · 20→−9.9 · 24→−9.2)
    for _ in range(6):
        run(["ffmpeg", "-y", "-i", str(R / "mix_raw.wav"), "-af", f"dynaudnorm=f=100:g=9:p=0.9:m=20,acompressor=threshold=0.125:ratio=8:attack=1:release=40,volume={gain:.2f}dB,alimiter=limit={10 ** (TP / 20):.4f}:level=false:attack=1:release=30",
             "-ar", "44100", str(mix)])
        oI, _ = lufs(mix)
        _, opk = lufs(mix)
        if oI >= TARGET_LUFS - 0.4 or gain >= 22:
            break
        gain += 2.0
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", str(vid), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)])
    print("final", final, dur_of(final), "LUFS/TP", lufs(final), "bgm gain", round(g, 2))


if __name__ == "__main__":
    main()
