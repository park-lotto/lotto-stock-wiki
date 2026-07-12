"""EDL + 비트별 TTS → ffmpeg으로 컷 편집·오디오 교체한 최종 mp4(설계 §3-4).

각 비트의 소스 구간을 그 비트 나레이션(TTS) 길이만큼 **정상 속도(1배속)** 로
재생한다. 자막이 정상 속도로 읽히도록, 영상 길이는 배속으로 압축하지 않고
나레이션 읽는 시간에 맞춰 늘린다(설계: 대본 못 줄이면 클립을 길게, 20~30초).
구간 원본이 나레이션보다 짧으면 소스를 루프(-stream_loop)해서 부족분을 채운다.
concat 후 원본 오디오를 제거하고 비트별 TTS를 이어붙인 트랙으로 교체한다.
"""
import subprocess
import uuid
from pathlib import Path


def _probe_duration(path):
    """ffprobe로 미디어 길이(초)."""
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
    out = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def _pick_segment(beat, tts_dur, source_video_paths):
    """primary→alternates 중 나레이션(tts_dur)을 1배속으로 담을 수 있는
    (구간길이 >= tts_dur) 첫 후보를 고른다. 아무도 못 담으면 가장 긴 후보를
    반환하고, 부족분은 assemble에서 소스 루프로 채운다. 반환: ref(dict).
    더 이상 배속 보정을 하지 않으므로 setpts rate는 반환하지 않는다."""
    candidates = [beat["primary"]] + list(beat.get("alternates", []))
    best = None
    best_len = -1.0
    for ref in candidates:
        if ref["video_id"] not in source_video_paths:
            continue
        seg_len = ref["end"] - ref["start"]
        if seg_len >= tts_dur:
            return ref  # 1배속으로 나레이션 전체를 담을 수 있는 첫 후보
        if seg_len > best_len:
            best, best_len = ref, seg_len
    return best if best else beat["primary"]


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
        ref = _pick_segment(beat, tts_dur, source_video_paths)
        src = source_video_paths[ref["video_id"]]
        clip = work / f"beat_{idx}.mp4"
        # 소스를 ref["start"]부터 1배속으로 재생, tts 오디오로 교체, 출력 길이를
        # tts_dur로 고정(-t). 구간이 짧으면 -stream_loop로 소스를 반복해 나레이션
        # 길이만큼 영상을 채운다(배속 압축으로 자막이 빨라지는 것을 방지).
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-ss", str(ref["start"]), "-i", str(src),
            "-i", str(tts),
            "-map", "0:v:0", "-map", "1:a:0",
            "-t", str(tts_dur),
            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(clip),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        beat_clips.append(clip)

    if not beat_clips:
        raise RuntimeError("video_assemble: 렌더할 비트가 없습니다")

    concat_txt = work / "concat.txt"
    concat_txt.write_text("".join(f"file '{c.as_posix()}'\n" for c in beat_clips), encoding="utf-8")
    # 비트 클립들은 이미 동일 설정(libx264/aac)으로 인코딩됐으므로 concat에서 다시
    # 풀 재인코딩하지 말고 스트림 복사(-c copy)한다. 재인코딩 concat은 2GB 서버에서
    # 수십 초 걸려 백그라운드 렌더가 서비스 재시작(잦은 배포)에 걸려 죽는 원인이었다
    # (2026-07-12 라이브 exit 255). -c copy는 ~0.3초로 그 취약 구간을 제거한다.
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
           "-c", "copy", str(out_path)]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(out_path)
