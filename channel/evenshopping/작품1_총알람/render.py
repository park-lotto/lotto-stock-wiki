# -*- coding: utf-8 -*-
"""재미썸홈 작품1 총 쏘는 알람시계 — 필재 TTS 1회 → 8.8자/초 → 토막=컷 재료(t11 영상 칸 1080×1407) → 숏템 t11 틀(scene_style.compose)
→ 나레 + BGM(qiuqiu, 나레 −17dB) + 숏템 효과음팩(shopping_shorts/sfx_pack.events — 자막 줄 바뀔 때, 칸 역할이 소리를 정함, 팩21_사장님) → −13.4 LUFS.

    PYTHONUTF8=1 py channel/evenshopping/작품1_총알람/render.py
입력: 같은 폴더 make_plan.py(SENTENCES·CUTS)·프리셋 manifest. ★타입캐스트 1회 — narr_full.mp3 가 있으면 다시 안 부른다.
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

D = Path(__file__).resolve().parent
ROOT = D.parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(D))
import make_plan as MP  # noqa: E402
from tools.calcopy import narr_video as N  # noqa: E402

V2 = "--v2" in sys.argv          # 사장님 10-17 수정본: TTS 단계 속도↑(atempo ≤1.2)·컷 3개 교체 → render_v2·바탕화면 _수정
R = MP.SRC / ("render_v2" if V2 else "render")
TTS_TEMPO = 1.4 if V2 else None   # Typecast output.audio_tempo
PRE = MP.PRESET
VOICE = "tc_68257f68bc6e3c161ab5078d"   # 필재(페이블 10-17)
CPS = PRE["measured"]["speech_rate"]["chars_per_s_total"]   # 8.8
BGM = ROOT / "shopping_shorts/assets/bgm_lib/qiuqiu.mp3"
BGM_DB_BELOW = 17.0                      # bench A.openvoice 17.02(말 p90 − 바닥)
TARGET_LUFS, TP = PRE["measured"]["lufs"]["I"], -2.0
DESK = Path.home() / "Desktop" / ("칼카피_재미썸홈_총쏘는알람시계_수정.mp4" if "--v2" in sys.argv else "칼카피_재미썸홈_총쏘는알람시계.mp4")
FPS = 30
# 스파인 칸 → sfx_pack 역할(ROLE_GROUPS). "이게 말도 안 되는 게"=limit(둥) · 반전=twist(둥) · 결과=more(띠링) — 페이블 10-17
SFX_ROLES = ["title", "bait", "reveal", "limit", "more", "more", "twist", "land"]


def run(cmd):
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding="utf-8", errors="replace")


def run_bytes(cmd):
    return subprocess.run(cmd, check=True, stdin=subprocess.DEVNULL, capture_output=True).stdout


def dur_of(p):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)]).stdout.strip())


def lufs(p):
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", e)[-1]), float(re.findall(r"Peak:\s+(-?[\d.]+) dBFS", e)[-1])


def main():
    R.mkdir(parents=True, exist_ok=True)
    lines = [s for _, s in MP.SENTENCES]
    full, tight, narr = R / "narr_full.mp3", R / "narr_tight.wav", R / "narr.wav"
    if not full.exists():
        from shopping_shorts.channelkit import providers
        providers.typecast_synth(VOICE, tempo=TTS_TEMPO)(" ".join(lines), str(full))
        print("TTS 1회:", full)
    if not tight.exists():
        f = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02"
        mid = "silenceremove=stop_periods=-1:stop_duration=0.15:stop_threshold=-45dB:stop_silence=0.1"
        run(["ffmpeg", "-y", "-i", str(full), "-af", f"{f},areverse,{f},areverse,{mid}", str(tight)])
    chars = MP.nchar(" ".join(lines))
    d0 = dur_of(tight)
    tempo = round(min(1.6, max(0.8, CPS / (chars / d0))), 4)
    if V2 and tempo > 1.2:
        raise SystemExit(f"atempo {tempo} > 1.2 — TTS 원속도 {chars / d0:.2f}자/초가 모자람")
    run(["ffmpeg", "-y", "-i", str(tight), "-af", f"atempo={tempo}", "-ar", "44100", str(narr)])
    dn = dur_of(narr)
    print(f"TTS {chars / d0:.2f}자/초 → atempo {tempo} → {chars / dn:.2f}자/초 {dn:.2f}초")

    # 조각 → 줄 번호(대사 순서대로 소비)
    steps, li, used = [], 0, 0
    for c in MP.CUTS:
        n = MP.nchar(c[0])
        while used >= MP.nchar(lines[li]):
            li, used = li + 1, 0
        steps.append({"text": c[0], "chars": n, "new_cut": True, "line": li}); used += n
    timed, dur = N.time_steps(steps, str(narr), lines=lines)
    END = round(dur + 0.4, 3)
    timed[-1]["t1"] = END

    # 재료: 토막마다 컷 1개, t11 영상 칸 비율 크롭 → 1080×1407, 원음 없음, 프레임 정확
    parts = R / "parts"; shutil.rmtree(parts, ignore_errors=True); parts.mkdir()
    lst, cuts = [], []
    tcur = 0
    for k, (st, c) in enumerate(zip(timed, MP.CUTS)):
        cap, kind, src, ss, cx, sfx, seen = c
        f0, f1 = round(st["t0"] * FPS), round(st["t1"] * FPS)
        n = max(1, f1 - f0)
        p = MP.path_of(src); w, h, sd = MP.probe(p)
        cw = int(h * MP.WIN[0] / MP.WIN[1]) // 2 * 2
        x = (w - cw) // 2 if cx is None else int(cx)
        if ss + n / FPS > sd:
            raise SystemExit(f"#{k + 1} 소스 길이 부족 {src} {ss}+{n / FPS:.2f}>{sd:.2f}")
        out = parts / f"p{k:02d}.mp4"
        run(["ffmpeg", "-y", "-ss", f"{ss:.3f}", "-i", str(p), "-an", "-vf",
             f"crop={cw}:{h}:{x}:0,scale={MP.WIN[0]}:{MP.WIN[1] + 1}:flags=lanczos,setsar=1,fps={FPS}", "-frames:v", str(n),
             "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)])
        lst.append(f"file '{out.as_posix()}'")
        cuts.append({"i": k + 1, "t0": round(f0 / FPS, 3), "t1": round(f1 / FPS, 3), "caption": cap, "kind": kind, "src": src, "ss": ss, "sfx": sfx})
    (parts / "list.txt").write_text("\n".join(lst), encoding="utf-8")
    mat = R / "material.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(parts / "list.txt"), "-c", "copy", str(mat)])
    total = cuts[-1]["t1"]

    # 틀: 숏템 t11, 브랜드 재미썸홈. 훅 = 제목 문장(컷 1~3) 한 장면, 그 뒤 조각마다 한 장면(자막 1줄)
    from shopping_shorts import scene_style
    T = PRE["sample_title"]
    snap = scene_style.validate_snapshot({"mode": "story", "presetId": PRE["template"]["preset_id"],
                                          "text": {"channel": PRE["brand"]["channel_name"], "hook1": T["hook1"], "hook2": T["hook2"], "bodyTitle": T["bodyTitle"]}})
    hook_n = sum(1 for c in cuts if steps[c["i"] - 1]["line"] == 0)
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": cuts[hook_n - 1]["t1"], "narration": lines[0], "caption_lines": [lines[0]], "role": "hook",
           "primary": {"video_id": "s0", "start": 0.0, "end": cuts[hook_n - 1]["t1"]}}]
    for c in cuts[hook_n:]:
        tl.append({"beat_idx": len(tl), "t0": c["t0"], "dur": round(c["t1"] - c["t0"], 3), "narration": c["caption"], "caption_lines": [c["caption"]],
                   "role": "body", "primary": {"video_id": "s0", "start": c["t0"], "end": c["t1"]}})
    vid = R / "video.mp4"
    shutil.rmtree(R / "work", ignore_errors=True)
    scene_style.compose(str(mat), tl, snap, str(vid), R / "work", {"text": f"{T['hook1']}\n{T['hook2']}", "body_title": T["bodyTitle"]})

    # 소리: 나레(목소리 중앙 −17.5dBFS로 맞춤 = sfx_pack 크기 기준) + BGM(나레 −17dB) + 숏템 효과음팩(sfx_pack 호출만)
    import numpy as np
    from shopping_shorts import sfx_pack as SP
    a = np.frombuffer(run_bytes(["ffmpeg", "-v", "error", "-i", str(narr), "-ac", "1", "-ar", "44100", "-f", "f32le", "-"]), dtype=np.float32)
    k20 = int(0.02 * 44100); fr = a[: len(a) // k20 * k20].reshape(-1, k20)
    rms = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
    vmed = float(np.median(rms[rms > rms.max() - 30]))
    ngain = -17.5 - vmed
    nI, npk = lufs(narr)
    bI, _ = lufs(BGM)
    g = (nI + ngain - BGM_DB_BELOW) - bI
    # 효과음 timeline = 대본 줄(칸) 단위, 역할 = 스파인 칸, 자막 줄 = 조각(실측 시각 cap_durs)
    roles = SFX_ROLES
    stl = []
    for li, line in enumerate(lines):
        mine = [c for c, s_ in zip(cuts, steps) if s_["line"] == li]
        t0 = mine[0]["t0"]; t1 = mine[-1]["t1"]
        stl.append({"beat_idx": li, "t0": t0, "dur": round(t1 - t0, 3), "narration": " ".join(c["caption"] for c in mine),
                    "caption_lines": [c["caption"] for c in mine], "cap_durs": [round(c["t1"] - c["t0"], 3) for c in mine],
                    "cap_lead": 0.0, "cap_offset": 0.0, "role": roles[li]})
    pname, pdir = SP.pack_for(0)
    pack = {"name": pname, "dir": pdir, "density": "normal", "level": "normal", "mute_beats": []}
    plan = SP.plan_events(stl)
    evs = SP.events(stl, pack)
    (R / "sfx_events.json").write_text(json.dumps({"pack": pname, "plan": plan, "events": evs, "timeline": stl}, ensure_ascii=False, indent=1), encoding="utf-8")
    ins, flt, lab = ["-i", str(narr), "-stream_loop", "-1", "-i", str(BGM)], [], []
    for j, (path, t, mul) in enumerate(evs):
        ins += ["-i", path]
        ms = int(round(t * 1000))
        flt.append(f"[{2 + j}:a]aresample=44100,aformat=channel_layouts=mono,volume={mul:.4f},adelay={ms}|{ms}[s{j}]")
        lab.append(f"[s{j}]")
    flt.append(f"[0:a]aformat=channel_layouts=mono,volume={ngain:.2f}dB,apad=whole_dur={total:.3f}[n]")
    flt.append(f"[1:a]aformat=channel_layouts=mono,volume={g:.2f}dB,atrim=0:{total:.3f},afade=t=out:st={max(0, total - 0.6):.3f}:d=0.6[b]")
    flt.append(f"[n][b]{''.join(lab)}amix=inputs={2 + len(lab)}:normalize=0:duration=first[o]")
    run(["ffmpeg", "-y", *ins, "-filter_complex", ";".join(flt), "-map", "[o]", "-ar", "44100", "-ac", "2", str(R / "mix_raw.wav")])
    mix = R / "mix.wav"
    gain = 6.0
    for _ in range(10):
        run(["ffmpeg", "-y", "-i", str(R / "mix_raw.wav"), "-af",
             f"acompressor=threshold=0.125:ratio=4:attack=2:release=60,volume={gain:.2f}dB,alimiter=limit={10 ** (TP / 20):.4f}:level=false:attack=1:release=30",
             "-ar", "44100", str(mix)])
        oI, _ = lufs(mix)
        if abs(oI - TARGET_LUFS) <= 0.4:
            break
        gain += (TARGET_LUFS - oI) * 0.9
    final = R / "final.mp4"
    run(["ffmpeg", "-y", "-i", str(vid), "-i", str(mix), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(final)])
    shutil.copy(final, DESK)
    md5 = [hashlib.md5(Path(p).read_bytes()).hexdigest() for p in (final, DESK)]
    fI, fpk = lufs(final)
    tsum = {k: round(sum(c["t1"] - c["t0"] for c in cuts if c["kind"] == k), 2) for k in ("제품", "유사", "짤")}
    rep = {"final": str(final), "desktop": str(DESK), "md5": md5, "dur": dur_of(final), "lufs": fI, "peak_dbfs": fpk, "tempo": tempo,
           "cps_out": round(chars / dn, 2), "cuts": len(cuts), "cut_median": sorted(c["t1"] - c["t0"] for c in cuts)[len(cuts) // 2],
           "time_by_kind": tsum, "max_caption": max(len(c["caption"]) for c in cuts), "bgm_gain_db": round(g, 2), "mix_gain_db": round(gain, 2)}
    (R / "timeline.json").write_text(json.dumps({"report": rep, "cuts": cuts, "tl": tl}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
