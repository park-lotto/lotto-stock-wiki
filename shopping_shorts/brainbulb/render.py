# -*- coding: utf-8 -*-
"""최종 합성 — MVP: 단일 배경 `-loop 1` + 자막(subtitles) + 나레 + 효과음 베드. (아스트라 (4): 프레임 나열 불필요)

입력은 전부 파일이다: sub.ass · tts/NN.wav · sfx_plan · timing. 여기서는 판단하지 않는다 — 조립만.
효과음 팩이 없으면(저작권 미확인, 팩 미보유) 베드를 건너뛰고 그 사실을 로그에 남긴다.
"""
import os
import subprocess

from . import spec


def _run(argv, what):
    r = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"render/{what}: ffmpeg 실패 — {r.stderr[-400:]}")


def concat_narration(files, out_wav, tail_sec=spec.TAIL_SEC):
    """카드+컷 wav를 무음 없이 이어 붙이고 꼬리 0.1초 무음을 붙인다 → narr.wav"""
    lst = out_wav + ".txt"
    with open(lst, "w", encoding="utf-8") as fh:
        for f in files:
            fh.write("file '" + f.replace("\\", "/").replace("'", "'\\''") + "'\n")
    _run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst,
          "-af", f"apad=pad_dur={tail_sec}", "-ar", "44100", "-ac", "2", out_wav], "narr")
    return out_wav


def sfx_bed(plan, timing, sfx_dir, out_wav, total):
    """컷 시작 시각에 효과음 1발씩(게인 적용) → 베드 wav. 파일이 하나도 없으면 None."""
    inputs, filters, tags = [], [], []
    for x in plan:
        path = os.path.join(sfx_dir, os.path.basename(x["file"]))
        if not os.path.exists(path):
            continue
        g = timing["groups"][x["cut"]]
        k = len(inputs)
        inputs += ["-i", path]
        filters.append(f"[{k}:a]volume={x['gain']},adelay={int(g['t'] * 1000)}|{int(g['t'] * 1000)},aformat=sample_rates=44100:channel_layouts=stereo[s{k}]")
        tags.append(f"[s{k}]")
    if not inputs:
        return None
    fc = ";".join(filters) + f";{''.join(tags)}amix=inputs={len(tags)}:normalize=0,apad=whole_dur={total}[bed]"
    _run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", fc, "-map", "[bed]", "-t", str(total), out_wav], "sfx_bed")
    return out_wav


def mix(narr_wav, bed_wav, out_wav, total):
    if bed_wav is None:
        _run(["ffmpeg", "-y", "-loglevel", "error", "-i", narr_wav, "-t", str(total), out_wav], "mix")
        return out_wav
    fc = f"[1:a]volume={spec.SFX_BED_DB}dB[b];[0:a][b]amix=inputs=2:normalize=0:duration=first[m]"
    _run(["ffmpeg", "-y", "-loglevel", "error", "-i", narr_wav, "-i", bed_wav, "-filter_complex", fc, "-map", "[m]", "-t", str(total), out_wav], "mix")
    return out_wav


def video(ass_path, audio_wav, out_mp4, total, *, bg_image=None, fonts_dir=None, fps=29.97):
    """배경(없으면 검정) + 자막 번인 + 오디오 → mp4. subtitles 필터 경로 이스케이프를 피하려고 ASS 폴더를 cwd로 잡는다."""
    from .measure import _fontsdir_arg
    fonts_dir = fonts_dir or spec.FONTS_DIR
    cwd = os.path.dirname(os.path.abspath(ass_path))
    ass_rel = os.path.basename(ass_path)
    fd = _fontsdir_arg(fonts_dir, cwd)
    if bg_image:
        vin = ["-loop", "1", "-framerate", str(fps), "-i", bg_image]
    else:
        vin = ["-f", "lavfi", "-i", f"color=black:s={spec.CANVAS_W}x{spec.CANVAS_H}:r={fps}"]
    argv = ["ffmpeg", "-y", "-loglevel", "error", *vin, "-i", audio_wav,
            "-vf", f"scale={spec.CANVAS_W}:{spec.CANVAS_H}:force_original_aspect_ratio=decrease,pad={spec.CANVAS_W}:{spec.CANVAS_H}:(ow-iw)/2:(oh-ih)/2,subtitles={ass_rel}:fontsdir={fd}",
            "-t", str(total), "-r", str(fps), "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k", "-shortest", out_mp4]
    r = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        raise RuntimeError(f"render/video: ffmpeg 실패 — {r.stderr[-400:]}")
    return out_mp4


def build(workdir, timing, ass_path, narr_files, sfx_plan, *, sfx_dir=None, bg_image=None, fonts_dir=None, log=print):
    out = os.path.join(workdir, "out")
    os.makedirs(out, exist_ok=True)
    total = timing["total"]
    narr = concat_narration(narr_files, os.path.join(workdir, "narr.wav"))
    bed = sfx_bed(sfx_plan, timing, sfx_dir, os.path.join(workdir, "sfx_bed.wav"), total) if sfx_dir else None
    if bed is None:
        log("[brainbulb.render] 효과음 팩 없음 — 베드 생략(나레만)")
    final = mix(narr, bed, os.path.join(workdir, "audio_final.wav"), total)
    mp4 = video(ass_path, final, os.path.join(out, "final.mp4"), total, bg_image=bg_image, fonts_dir=fonts_dir)
    log(f"[brainbulb.render] {mp4} ({total}s)")
    return {"mp4": mp4, "narr": narr, "bed": bed, "audio": final}
