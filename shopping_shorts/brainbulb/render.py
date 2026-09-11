# -*- coding: utf-8 -*-
"""최종 합성 — MVP: 단일 배경 `-loop 1` + 자막(subtitles) + 나레 + 효과음 베드. (아스트라 (4): 프레임 나열 불필요)

입력은 전부 파일이다: sub.ass · tts/NN.wav · sfx_plan · timing. 여기서는 판단하지 않는다 — 조립만.
효과음 팩이 없으면(저작권 미확인, 팩 미보유) 베드를 건너뛰고 그 사실을 로그에 남긴다.

★모든 ffmpeg는 **작업폴더를 cwd로** 잡고 **상대 경로**만 쓴다 (실측 2026-09-12: 한글 폴더 + concat 목록 상대경로가
  'Illegal byte sequence'와 경로 이중 결합으로 죽었다. subtitles 필터 경로 이스케이프 문제도 같이 사라진다).
"""
import os
import re
import subprocess

from . import spec


def _run(argv, what, cwd):
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"render/{what}: ffmpeg 실패 — {r.stderr[-400:]}")


def _rel(path, wd):
    return os.path.relpath(os.path.abspath(path), os.path.abspath(wd)).replace("\\", "/")


def concat_narration(files, wd, out_name="narr.wav", tail_sec=spec.TAIL_SEC):
    """카드+컷 wav를 무음 없이 이어 붙이고 꼬리 0.1초 무음을 붙인다 → narr.wav (경로는 목록 파일 기준 상대)"""
    lst = out_name + ".txt"
    with open(os.path.join(wd, lst), "w", encoding="utf-8") as fh:
        for f in files:
            fh.write("file '" + _rel(f, wd).replace("'", "'\\''") + "'\n")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
          "-af", f"apad=pad_dur={tail_sec}", "-ar", "44100", "-ac", "2", out_name], "narr", wd)
    return os.path.join(wd, out_name)


def sfx_bed(plan, timing, sfx_dir, wd, total, out_name="sfx_bed.wav"):
    """컷 시작 시각에 효과음 1발씩(게인 적용) → 베드 wav. 파일이 하나도 없으면 None."""
    inputs, filters, tags = [], [], []
    for x in plan:
        path = os.path.join(sfx_dir, os.path.basename(x["file"]))
        if not os.path.exists(path):
            continue
        g = timing["groups"][x["cut"]]
        k = len(tags)                      # 입력 번호 = 지금까지 붙인 효과음 개수 (아스트라 3R: len(inputs)는 2씩 뛴다)
        inputs += ["-i", _rel(path, wd)]
        ms = int(g["t"] * 1000)
        filters.append(f"[{k}:a]volume={x['gain']},adelay={ms}|{ms},aformat=sample_rates=44100:channel_layouts=stereo[s{k}]")
        tags.append(f"[s{k}]")
    if not inputs:
        return None
    fc = ";".join(filters) + f";{''.join(tags)}amix=inputs={len(tags)}:normalize=0,apad=whole_dur={total}[bed]"
    _run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[bed]", "-t", str(total), out_name], "sfx_bed", wd)
    return os.path.join(wd, out_name)


def _measure_loudness(path, wd):
    """1차 패스: 통합 라우드니스(LUFS)와 트루피크(dBTP). loudnorm print_format=json 을 측정용으로만 쓴다."""
    import json as _json
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", f"{spec.MIX_LOUDNORM}:print_format=json", "-f", "null", "-"],
                       cwd=wd, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise RuntimeError(f"render/mix: 라우드니스 측정 실패 — {r.stderr[-200:]}")
    d = _json.loads(m.group(0))
    return float(d["input_i"]), float(d["input_tp"])


def _gain_filter(path, wd):
    """목표 I=-16 LUFS·TP≤-1.5까지 **고정 게인**. loudnorm 2패스 대신 쓰는 이유: loudnorm은 출력 길이를 65ms 줄인다
    (실측 v006: apad를 앞뒤 어디 붙여도 28.469 vs total 28.535 → 검수 stream_sync 실패). volume은 길이를 안 건드린다."""
    li, tp = _measure_loudness(path, wd)
    gain = min(-16.0 - li, -1.5 - tp)
    return f"volume={gain:.2f}dB"


def mix(narr_wav, bed_wav, wd, total, out_name="audio_final.wav"):
    n = _rel(narr_wav, wd)
    if bed_wav is None:
        g = _gain_filter(n, wd)
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", n, "-af", f"{g},apad=pad_dur=1", "-t", str(total), out_name], "mix", wd)
        return os.path.join(wd, out_name)
    raw = out_name + ".premix.wav"
    fc = f"[1:a]volume={spec.SFX_BED_DB}dB[b];[0:a][b]amix=inputs=2:normalize=0:duration=first,apad=pad_dur=1[m]"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", n, "-i", _rel(bed_wav, wd), "-filter_complex", fc, "-map", "[m]",
          "-t", str(total), raw], "premix", wd)
    g = _gain_filter(raw, wd)
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af", g, "-t", str(total), out_name], "mix", wd)
    os.remove(os.path.join(wd, raw))
    return os.path.join(wd, out_name)


def video(ass_path, audio_wav, wd, total, *, bg_image=None, frames_list=None, fonts_dir=None, fps=29.97, out_name="out/final.mp4"):
    """배경(프레임 시퀀스 > 단일 이미지 > 검정) + 자막 번인 + 오디오 → mp4. 전부 작업폴더 기준 상대 경로."""
    from .measure import _fontsdir_arg
    fonts_dir = fonts_dir or spec.FONTS_DIR
    os.makedirs(os.path.join(wd, os.path.dirname(out_name)), exist_ok=True)
    fd = _fontsdir_arg(fonts_dir, wd)
    if frames_list:
        vin = ["-f", "concat", "-safe", "0", "-i", _rel(frames_list, wd)]      # 컷별 정지 프레임(볼케이노 vconcat 방식)
    elif bg_image:
        vin = ["-loop", "1", "-framerate", str(fps), "-i", _rel(bg_image, wd)]
    else:
        vin = ["-f", "lavfi", "-i", f"color=black:s={spec.CANVAS_W}x{spec.CANVAS_H}:r={fps}"]
    # tpad로 마지막 프레임을 붙들어 두고 -t total로 자른다. -shortest는 쓰지 않는다 —
    # 프레임 시퀀스는 29.97fps 양자화로 음성보다 몇 프레임 짧아져 -shortest가 거기서 끊는다(실측: 긴 영상에서 검수 mp4_duration 실패).
    argv = ["ffmpeg", "-y", "-loglevel", "error", *vin, "-i", _rel(audio_wav, wd),
            # ★fps 정규화가 맨 앞이어야 한다 — concat 이미지 스트림은 가변 프레임률이라 tpad만으로는 영상이 0.24초 짧게 끝났다(실측 A/B/C 대조: fps 선행 시 32.366 vs 오디오 32.370)
            "-vf", f"fps={fps},tpad=stop_mode=clone:stop_duration=2,scale={spec.CANVAS_W}:{spec.CANVAS_H}:force_original_aspect_ratio=decrease,pad={spec.CANVAS_W}:{spec.CANVAS_H}:(ow-iw)/2:(oh-ih)/2,subtitles={_rel(ass_path, wd)}:fontsdir={fd}",
            "-t", str(total), "-r", str(fps), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", out_name]
    _run(argv, "video", wd)
    return os.path.join(wd, out_name)


def build(workdir, timing, ass_path, narr_files, sfx_plan, *, sfx_dir=None, bg_image=None, frames_list=None, fonts_dir=None, log=print):
    wd = os.path.abspath(workdir)
    total = timing["total"]
    narr = concat_narration(narr_files, wd)
    bed = sfx_bed(sfx_plan, timing, sfx_dir, wd, total) if sfx_dir else None
    if bed is None:
        log("[brainbulb.render] 효과음 팩 없음 — 베드 생략(나레만)")
    final = mix(narr, bed, wd, total)
    mp4 = video(ass_path, final, wd, total, bg_image=bg_image, frames_list=frames_list, fonts_dir=fonts_dir)
    log(f"[brainbulb.render] {mp4} ({total}s)")
    return {"mp4": mp4, "narr": narr, "bed": bed, "audio": final}
