"""무음 틈 줄이기 — 마스터에서 말 사이 빈 구간을 일정 길이로 눌러 붙인다.

왜 필요한가: 씬을 따로 렌더해 이어 붙이면 각 씬 앞뒤의 여유가 그대로 남아
전체적으로 늘어진다(실측 2026-08-12: 753.3초 중 무음 20.3초 / 49군데).

무엇을 하나:
  1) ffmpeg silencedetect로 무음 구간을 실측한다(추측하지 않는다)
  2) 각 구간에서 KEEP초씩 앞뒤 호흡을 남기고 가운데만 잘라낸다
     → 말이 붙어버려 숨 막히는 걸 막는다. 통째로 지우지 않는 이유가 이것이다
  3) select/aselect 한 방으로 재인코딩한다(영상·음성을 같은 식으로 잘라 싱크 유지)

★자막이 픽셀에 구워져 있으므로 영상과 음성을 반드시 같이 잘라야 한다.

사용:  py tools/trim_silence.py <입력.mp4> <출력.mp4> [--keep 0.09] [--noise -35] [--min 0.30]
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=nw=1:nk=1', path],
        capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def detect_silence(path: str, noise: float, min_dur: float):
    """(시작, 끝) 초 단위 무음 구간 목록. ffmpeg 실측값만 쓴다."""
    proc = subprocess.run(
        ['ffmpeg', '-hide_banner', '-nostats', '-i', path,
         '-af', f'silencedetect=noise={noise}dB:d={min_dur}', '-f', 'null', '-'],
        capture_output=True, text=True, errors='ignore')
    log = proc.stderr
    starts = [float(m) for m in re.findall(r'silence_start: ([\d.]+)', log)]
    ends = [float(m) for m in re.findall(r'silence_end: ([\d.]+)', log)]
    if len(ends) < len(starts):
        ends.append(probe_duration(path))
    return list(zip(starts, ends))


def keep_ranges(gaps, total: float, keep: float):
    """잘라낼 구간을 뺀 '남길 구간' 목록."""
    cuts = [(s + keep, e - keep) for s, e in gaps if (e - s) > keep * 2]
    out, prev = [], 0.0
    for a, b in cuts:
        if a > prev:
            out.append((prev, a))
        prev = b
    if prev < total:
        out.append((prev, total))
    return out, sum(b - a for a, b in cuts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('dst')
    ap.add_argument('--keep', type=float, default=0.09, help='틈마다 앞뒤로 남길 호흡(초)')
    ap.add_argument('--noise', type=float, default=-35.0, help='무음 판정 기준(dB)')
    ap.add_argument('--min', dest='min_dur', type=float, default=0.30, help='이보다 짧은 틈은 손대지 않음')
    ap.add_argument('--crf', type=int, default=15)
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()

    total = probe_duration(a.src)
    gaps = detect_silence(a.src, a.noise, a.min_dur)
    ranges, saved = keep_ranges(gaps, total, a.keep)
    print(f'무음 {len(gaps)}군데 / 총 {sum(e - s for s, e in gaps):.1f}초')
    print(f'→ {saved:.1f}초 잘라내고 {total - saved:.1f}초 '
          f'({int((total - saved) // 60)}분 {(total - saved) % 60:.1f}초)로')
    if a.dry_run:
        return 0

    expr = '+'.join(f'between(t,{s:.3f},{e:.3f})' for s, e in ranges)
    script = (
        f"[0:v]select='{expr}',setpts=N/FRAME_RATE/TB[v];"
        f"[0:a]aselect='{expr}',asetpts=N/SR/TB[a]"
    )
    fd, spath = tempfile.mkstemp(suffix='.txt', text=True)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(script)
    try:
        cmd = ['ffmpeg', '-y', '-hide_banner', '-i', a.src,
               '-filter_complex_script', spath, '-map', '[v]', '-map', '[a]',
               '-c:v', 'libx264', '-preset', 'slow', '-crf', str(a.crf),
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k',
               '-movflags', '+faststart', a.dst]
        rc = subprocess.run(cmd).returncode
    finally:
        os.unlink(spath)
    if rc != 0:
        return rc

    # 실제로 줄었는지 확인하고 끝낸다(주장하지 않는다)
    print(f'\n결과 {probe_duration(a.dst):.2f}초 / 남은 무음 '
          f'{len(detect_silence(a.dst, a.noise, a.min_dur))}군데')
    return 0


if __name__ == '__main__':
    sys.exit(main())
