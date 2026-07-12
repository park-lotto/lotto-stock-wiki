"""EDL + 비트별 TTS → ffmpeg으로 컷 편집·오디오 교체한 최종 mp4(설계 §3-4).

각 비트의 primary 구간을 그 비트 TTS 길이에 맞춰 트림/배속보정하고, 배속보정
한도를 넘으면 alternates의 다음 후보로 자동 대체한다. concat 후 원본 오디오를
제거하고 비트별 TTS를 이어붙인 트랙으로 교체한다.
"""
import subprocess
import uuid
from pathlib import Path

_MIN_RATE = 0.8
_MAX_RATE = 1.2


def _probe_duration(path):
    """ffprobe로 미디어 길이(초)."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    out = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _rate_for(seg_len, tts_dur, min_rate, max_rate):
    """seg를 tts_dur에 맞추기 위한 setpts 배속. seg가 길면 1.0(트림), 짧으면
    필요한 배속을 [min_rate,max_rate]로 클램프. 반환 rate<min_rate면 '더 긴
    구간이 필요'하다는 신호로 호출부가 판단."""
    if seg_len <= 0:
        return max_rate
    needed = tts_dur / seg_len  # >1이면 느리게(늘려야), <1이면 빠르게
    if needed <= 1.0:
        return 1.0  # 소스가 더 길다 → 트림해서 사용
    return min(needed, max_rate)


def _pick_segment(beat, tts_dur, source_video_paths, min_rate=_MIN_RATE, max_rate=_MAX_RATE):
    """primary→alternates 순으로 배속보정 한도 내 감당 가능한 구간 선택.
    아무도 한도 내 못 맞추면 primary를 최대배속으로 best-effort 반환(비트 드롭 안 함).
    반환: (ref, setpts_rate)."""
    candidates = [beat["primary"]] + list(beat.get("alternates", []))
    best = None
    eps = 1e-9
    for ref in candidates:
        if ref["video_id"] not in source_video_paths:
            continue
        seg_len = ref["end"] - ref["start"]
        needed = (tts_dur / seg_len) if seg_len > 0 else max_rate + 1
        if needed <= 1.0:
            # 소스가 충분히 길다
            if needed >= min_rate - eps:
                return ref, max(needed, min_rate)  # 정확한 배속 (min_rate 이상)
            else:
                return ref, 1.0  # 트림으로 처리 (min_rate 미만)
        rate = min(needed, max_rate)
        if needed <= max_rate + eps:
            return ref, max(rate, min_rate)  # 한도 내 배속으로 감당 가능 (min_rate 이상)
        if best is None:
            best = (ref, max_rate)  # 아무도 못 맞추면 primary(첫 후보) 최대배속
    return best if best else (beat["primary"], max_rate)


def assemble(edit_plan, tts_paths, source_video_paths, out_path):
    """EDL을 실제 mp4로 렌더. 각 비트를 개별 mp4로 만든 뒤 concat + 오디오 교체."""
    work = Path(out_path).parent / f"asm_{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    beat_clips = []
    for beat in edit_plan["beats"]:
        idx = beat["beat_idx"]
        tts = tts_paths.get(idx)
        if not tts:
            continue
        tts_dur = _probe_duration(tts)
        ref, rate = _pick_segment(beat, tts_dur, source_video_paths)
        src = source_video_paths[ref["video_id"]]
        clip = work / f"beat_{idx}.mp4"
        # 소스 구간 잘라 배속(setpts) 적용 + tts 오디오로 교체, tts 길이에 맞춤
        # rate = tts_dur/seg_len 이 곧 setpts 배수(N). N<1=압축(빠르게), N>1=연장(느리게).
        vf = f"setpts={rate}*PTS" if rate != 1.0 else "setpts=PTS"
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(ref["start"]), "-to", str(ref["end"]), "-i", str(src),
            "-i", str(tts),
            "-filter:v", vf,
            "-map", "0:v:0", "-map", "1:a:0",
            "-t", str(tts_dur), "-shortest",
            "-c:v", "libx264", "-c:a", "aac", str(clip),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        beat_clips.append(clip)

    if not beat_clips:
        raise RuntimeError("video_assemble: 렌더할 비트가 없습니다")

    concat_txt = work / "concat.txt"
    concat_txt.write_text("".join(f"file '{c.as_posix()}'\n" for c in beat_clips), encoding="utf-8")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
           "-c:v", "libx264", "-c:a", "aac", str(out_path)]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(out_path)
