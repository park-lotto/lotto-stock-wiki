# -*- coding: utf-8 -*-
"""칼카피 한 편 만들기 — 틀(frame.json) + 뜯기(뜯기.json) + 재료(재료.json) + 대본(대본.json) → 우리 영상 mp4 (관제 097, 2026-10-16).

frame_video.py 의 확장판: 원본 창 부분 대신 **재료.json 의 해외 소스 구간**을 창에 넣고, 자막은 **우리 대본 줄**,
소리는 소스 원음(나레 없음 — 뜯기 소리 구성 '원음만+자막') + 배경음악(bgm_lib 곡, 비율 지정).
자막 시각·틀·꼬리(template_off)는 원본 그대로 — 그림은 라이브 렌더 경로 scene_style.compose 가 그린다.

    PYTHONUTF8=1 py tools/calcopy/remake_video.py <frame.json> <뜯기.json> <재료.json> <대본.json> <출력폴더> [bgm_id] [bgm비율=0.15] [목표LUFS=-10.1]
출력: final.mp4 · material.mp4(창·꼬리 재료 + 섞은 소리) · timeline.json · audio.json(소리 실측)
"""
import json
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import bgm_lib, scene_style, video_assemble as va  # noqa: E402
from shopping_shorts.calcopy_frame import schema, to_snapshot  # noqa: E402
from tools.calcopy.frame_video import timeline_from  # noqa: E402   ★자막 시각 나누기는 frame_video 한 곳
from tools.calcopy import hottem_audio as HA  # noqa: E402   ★컷 원음 끄기 판단은 hottem_audio.shot_muted 한 곳


def _seg(src, ss, dur, w, h, crop_y, W, H, out, full=False, src_crop=None, mute=False):
    """소스 한 구간 → W×H 캔버스. 창이면 w×h 로 cover 후 crop_y 위치로 잘라 가운데 세로에 붙이고, full 이면 W×H cover.
    mute = 원음 0(소리 줄은 남김 — 아래 '원음 없음' 판정이 그 구간을 BGM 으로 채운다)."""
    if full:
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},setsar=1"
    else:
        top = (H - h) // 2
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}:(iw-{w})/2:(ih-{h})*{crop_y},"
              f"pad={W}:{H}:0:{top}:black,setsar=1")
    if src_crop:   # 소스 안 남의 그래픽(표 상자·워터마크 등)을 먼저 잘라 냄 [x,y,w,h] — narr_video 와 같은 칸
        vf = "crop={2}:{3}:{0}:{1},".format(*src_crop) + vf
    va._run_ffmpeg(["ffmpeg", "-y", "-ss", f"{ss:.3f}", "-i", str(src), "-t", f"{dur:.3f}", "-vf", vf + ",fps=30",
                    "-af", ("volume=0," if mute else "") + "aresample=48000,aformat=channel_layouts=stereo", "-ar", "48000", "-ac", "2",
                    "-c:v", "libx264", "-crf", "16", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(out)])
    return out


def _lufs(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    tail = r[r.rfind("Summary:"):]
    g = lambda k: float(re.search(k + r":\s+(-?[\d.]+)", tail).group(1))  # noqa: E731
    return {"I": g("I"), "LRA": g("LRA"), "TP": g("Peak")}


SILENT_DB = -40.0   # 소스 구간 평균 음량이 이보다 작으면 '원음 없음'(무음 영상) — 10-16 실측 iPFgwFa83hc -42~-70dB
BGM_FILL = 1.0      # 원음 없는 구간의 배경음 배율(원음 자리를 메운다). 원음 있는 구간은 bgm_ratio


def _mean_db(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    m = re.search(r"mean_volume:\s*(-?[\d.]+|-inf)", r)
    return -200.0 if not m or m.group(1) == "-inf" else float(m.group(1))


def _bgm_vol_expr(silent, ratio):
    """배경음 배율 식 — 원음 없는 구간(silent)은 BGM_FILL, 나머지는 ratio. ★10-16 1판은 무음 소스 두 구간이 -24·-26dB 구멍이었다(원본 -15·-21)."""
    if not silent:
        return str(ratio)
    # ★앞의 loudnorm 이 3초짜리 큰 프레임을 내서 eval=frame 이 프레임 첫 시각으로만 판정했다(꼬리 구간이 통째로 0.15) → 부르는 쪽이 asetnsamples=1024 로 잘게 자른다
    cond = "+".join(f"between(t,{a},{b})" for a, b in silent)    # 필터 그래프에서 '…' 로 감싸 쓰므로 쉼표 이스케이프 불필요
    return f"if({cond},{BGM_FILL},{ratio})"


PER_VIDEO = "$per_video"


def title_text(spec: dict, S: dict) -> str:
    """영상 위 제목 글 — 판단 한 곳(remake_video·narr_video 공용, 관제 234). 틀 제목 칸이 '편마다 정함'($per_video)이거나 비면
    이 편 대본의 제목. 10-19 실측: 만들기 입구 1편이 제목 자리에 '$per_video' 글자가 그대로 찍혀 나왔다(틀 글을 그대로 썼다)."""
    L = next((l for l in spec.get("layers") or [] if l.get("kind") == "text" and l.get("role") == "title"), None)
    t = str((L or {}).get("text") or "").strip()
    if not t or t == PER_VIDEO:
        t = str(S.get("title") or (S.get("final") or {}).get("title") or "").strip()
    return "" if t == PER_VIDEO else t


def sfx_list(M: dict, dur: float) -> list:
    """재료.json sfx → [(파일, 시각초, dB)] — 판단 한 곳(remake_video·narr_video 공용, 관제 234).
    t = 초 또는 "end-0.2"(끝에서), 파일이 비었거나 없으면 그 효과음만 빼고 이유를 찍는다(10-19 실측: 팩 자산이 없는 PC 에서
    file=None 으로 렌더 전체가 TypeError, 원음+자막형은 "end-0.2" 를 float 로 바꾸다 죽을 자리였다)."""
    out = []
    for x in M.get("sfx") or []:
        f, t = x.get("file"), x.get("t", 0)
        try:
            t = dur + float(str(t)[3:]) if isinstance(t, str) and t.startswith("end") else float(t)
        except ValueError:
            print(f"[효과음] 시각을 못 읽음 {t!r} — 뺌", file=sys.stderr)
            continue
        p = (ROOT / f) if f else None
        if not p or not p.exists():
            print(f"[효과음] 파일 없음 {f!r}(자산 #{x.get('asset_id')}) — 뺌", file=sys.stderr)
            continue
        out.append((p, max(0.0, t), float(x.get("db", 0))))
    return out


def material(M, spec, tail_start, dur, work, bgm_id, bgm_ratio, target):
    v = next(l for l in spec["layers"] if l["kind"] == "video")
    W, H = spec["canvas"]
    base = pathlib.Path(M["cand_dir"])
    parts, silent_ranges = [], []
    for s in M["shots"]:
        a, b = s["t0"], min(s["t1"], dur)
        cuts = [(a, b, False)]
        if tail_start is not None and a < tail_start < b:
            cuts = [(a, tail_start, False), (tail_start, b, True)]
        elif tail_start is not None and a >= tail_start:
            cuts = [(a, b, True)]
        for c0, c1, full in cuts:
            p = work / f"seg_{len(parts):02d}.mkv"
            parts.append(_seg(base / s["src"], s["ss"] + (c0 - s["t0"]), c1 - c0, v["w"], v["h"], s.get("crop_y", 0.5), W, H, p, full, s.get("src_crop"),
                              HA.shot_muted(s)))
            if _mean_db(p) < SILENT_DB:
                silent_ranges.append((round(c0, 3), round(c1, 3)))
    lst = work / "segs.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    silent = work / "video_src.mkv"
    va._run_ffmpeg(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(silent)])
    # 소리: 소스 원음(목표 LUFS) + 배경음악(원음 대비 bgm_ratio 배, 원음과 같은 LUFS 로 맞춘 뒤 곱함) → 전체를 목표 LUFS 로
    bgm = bgm_lib.path_of(bgm_id) if bgm_id else None
    fc = f"[0:a]loudnorm=I={target}:TP=-1.5:LRA=11,aresample=48000[src]"
    if bgm:
        fc += (f";[1:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,loudnorm=I={target}:TP=-1.5:LRA=11,aresample=48000,asetnsamples=n=1024,volume='{_bgm_vol_expr(silent_ranges, bgm_ratio)}':eval=frame,"
               f"afade=t=out:st={max(0, dur - 0.6):.3f}:d=0.6[bg];[src][bg]amix=inputs=2:normalize=0:duration=first[mx]")
        last = "mx"
    else:
        last = "src"
    fc += f";[{last}]loudnorm=I={target}:TP=-1.0:LRA=11,aresample=48000[out]"
    mixed = work / "mixed.wav"
    va._run_ffmpeg(["ffmpeg", "-y", "-i", str(silent), *(["-stream_loop", "-1", "-i", bgm] if bgm else []),
                    "-filter_complex", fc, "-map", "[out]", "-t", f"{dur:.3f}", "-c:a", "pcm_s16le", str(mixed)])
    # 한 번 loudnorm 은 목표보다 ~1dB 덜 나온다(10-16 실측 -11.0 vs -10.1) → 잰 만큼 더하고 피크 제한
    gain = round(target - _lufs(mixed)["I"], 2)
    out = work / "material.mp4"
    # 효과음(재료.json sfx: [{file, t, db}]) — 음량 맞춘 섞인 소리 위에 그 시각 그대로 얹는다(뜯기 rules 효과음 시각)
    sfx = sfx_list(M, dur)
    fc2 = f"[1:a]volume={gain}dB[a0]"
    for k, (fp, t, db) in enumerate(sfx):
        ms = int(round(t * 1000))
        fc2 += f";[{k + 2}:a]aresample=48000,aformat=channel_layouts=stereo,volume={db}dB,adelay={ms}|{ms}[s{k}]"
    if sfx:
        fc2 += ";[a0]" + "".join(f"[s{k}]" for k in range(len(sfx))) + f"amix=inputs={len(sfx) + 1}:normalize=0:duration=first[a1]"
    fc2 += f";[{'a1' if sfx else 'a0'}]alimiter=limit=0.89:level=false[a]"
    va._run_ffmpeg(["ffmpeg", "-y", "-i", str(silent), "-i", str(mixed), *[a for fp, _, _ in sfx for a in ("-i", str(fp))],
                    "-filter_complex", fc2, "-map", "0:v", "-map", "[a]",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", str(out)])
    return out, bgm, silent_ranges


def make(frame_p, J_p, M_p, S_p, out, bgm_id=None, bgm_ratio=0.15, target=-10.1) -> pathlib.Path:
    """틀·뜯기·재료·대본 → out/final.mp4 (+ material.mp4·timeline.json·audio.json). engine/remake.py 가 부른다."""
    out = pathlib.Path(out).resolve()
    shutil.rmtree(out / "work", ignore_errors=True); (out / "work").mkdir(parents=True, exist_ok=True)
    frame = json.loads(pathlib.Path(frame_p).read_text(encoding="utf-8"))
    J = json.loads(pathlib.Path(J_p).read_text(encoding="utf-8"))
    M = json.loads(pathlib.Path(M_p).read_text(encoding="utf-8"))
    S = json.loads(pathlib.Path(S_p).read_text(encoding="utf-8"))
    lines = [l["text"] for l in S["final"]["lines"]]
    spec = schema.validate(frame)
    dur = float(J["probe"]["duration"])
    tail = (spec.get("template_off") or {}).get("tail_sec")
    tail_start = round(dur - tail, 3) if tail else None
    # 자막 글자만 우리 대본으로 바꾼 뜯기 사본 → 시각은 원본 그대로
    J2 = json.loads(json.dumps(J))
    J2["captions"]["items"] = [{"i": k, "text": [t]} for k, t in enumerate(lines)]
    tl = timeline_from(J2, tail_start)
    head = {"text": title_text(spec, S)}
    snap = scene_style.validate_snapshot(to_snapshot.to_snapshot(frame))
    mat, bgm, silent = material(M, spec, tail_start, dur, out / "work", bgm_id, bgm_ratio, target)
    shutil.copy(mat, out / "material.mp4")
    final = out / "final.mp4"
    scene_style.compose(str(mat), tl, snap, str(final), out / "work" / "compose", head)
    ctx = scene_style.context_for(tl, head, snap)
    (out / "timeline.json").write_text(json.dumps({"beats": tl, "scenes": [(s["start"], s["end"], s["caption"]) for s in ctx["scenes"]],
                                                   "tail_start": tail_start}, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "audio.json").write_text(json.dumps({"bgm": bgm_id, "bgm_file": bgm, "bgm_ratio": bgm_ratio, "sfx": M.get("sfx") or [], "bgm_fill_where_source_silent": {"ranges": silent, "ratio": BGM_FILL, "silent_db": SILENT_DB}, "target_lufs": target,
                                                "final": _lufs(final), "tts": None, "narration": "없음(원음만+자막)"},
                                               ensure_ascii=False, indent=1), encoding="utf-8")
    print("final:", final)
    return final


def main():
    a = sys.argv
    make(*a[1:6], a[6] if len(a) > 6 else None, float(a[7]) if len(a) > 7 else 0.15, float(a[8]) if len(a) > 8 else -10.1)


if __name__ == "__main__":
    main()
