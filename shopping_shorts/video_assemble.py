"""EDL + 비트별 TTS → ffmpeg으로 컷 편집·오디오 교체·새 대본 자막을 구운 최종 mp4.

각 비트의 소스 구간을 그 비트 나레이션(TTS) 길이만큼 **정상 속도(1배속)** 로
재생한다. 자막이 정상 속도로 읽히도록, 영상 길이는 배속으로 압축하지 않고
나레이션 읽는 시간에 맞춰 늘린다(설계: 대본 못 줄이면 클립을 길게, 20~30초).
구간 원본이 나레이션보다 짧으면 소스를 루프(-stream_loop)해서 부족분을 채운다.

새 대본은 화면 하단 불투명 바 위에 **한 줄씩 순차로(progressive)** 굽는다. 바가
원본에 박힌 소각 자막을 가리고, 그 위에 새 나레이션이 읽는 속도로 한 줄씩 넘어간다.
한글 폰트가 없는 환경(폰트 미해결)에서는 자막을 생략하고 영상만 렌더한다.
concat 후 원본 오디오를 제거하고 비트별 TTS를 이어붙인 트랙으로 교체한다.
"""
import os
import shutil
import subprocess
import textwrap
import uuid
from pathlib import Path

# 출력 규격(숏폼 세로). 소스 해상도가 달라도 여기로 통일해야 concat -c copy가 안전.
_OUT_W, _OUT_H = 720, 1280
# 하단 자막 바(원본 소각 자막을 덮는다) + 한 줄 자막 스타일.
_BAR_H = 300
_CAP_FONTSIZE = 46
_CAP_WRAP = 13          # 한 줄 최대 글자수(720px 안에 들어오게)
_CAP_BASELINE_Y = _OUT_H - 190

# 한글 폰트 후보(먼저 발견되는 것 사용). 서버(우분투)는 fonts-nanum/noto 설치 필요.
_FONT_CANDIDATES = [
    os.environ.get("SHORTS_CAPTION_FONT"),
    "C:/Windows/Fonts/malgun.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
]


def _resolve_font():
    """사용 가능한 한글 폰트 경로(첫 번째 존재하는 것). 없으면 None → 자막 생략."""
    for p in _FONT_CANDIDATES:
        if p and os.path.exists(p):
            return p
    return None


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


def _wrap_lines(narration):
    """나레이션을 한 줄 최대 _CAP_WRAP자로 쪼갠 리스트. 빈 문자열이면 []."""
    narr = (narration or "").strip()
    if not narr:
        return []
    return textwrap.wrap(narr, _CAP_WRAP) or [narr]


def _caption_vf(narration, dur, has_font, work, idx):
    """비트 영상용 -vf 필터 문자열. scale/crop으로 규격 통일 후, 폰트가 있으면
    하단 바 + 나레이션을 한 줄씩 순차 표시하는 drawtext들을 얹는다.

    ffmpeg 필터그래프는 값에 콜론(윈도 드라이브 'C:')을 못 넣으므로, 폰트·자막
    텍스트는 모두 work 폴더에 두고 **파일명만**(font.ttf / cap_*.txt) 참조한다.
    호출부는 반드시 cwd=work 로 ffmpeg를 실행해야 한다. 각 줄 텍스트는 임시
    파일(textfile=)로 넘겨 따옴표/쉼표 이스케이프 문제를 피한다."""
    base = f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"
    lines = _wrap_lines(narration)
    if not has_font or not lines:
        return base
    slice_dur = dur / len(lines)
    parts = [base]
    # 하단 바(원본 소각 자막 가리기)
    parts.append(f"drawbox=x=0:y=ih-{_BAR_H}:w=iw:h={_BAR_H}:color=black@0.82:t=fill")
    for i, line in enumerate(lines):
        (work / f"cap_{idx}_{i}.txt").write_text(line, encoding="utf-8")
        start = i * slice_dur
        end = dur + 0.5 if i == len(lines) - 1 else (i + 1) * slice_dur  # 마지막 줄은 끝까지
        parts.append(
            f"drawtext=fontfile=font.ttf:textfile=cap_{idx}_{i}.txt:"
            f"fontcolor=white:fontsize={_CAP_FONTSIZE}:"
            f"x=(w-text_w)/2:y={_CAP_BASELINE_Y}:"
            f"enable='between(t,{start:.2f},{end:.2f})'"
        )
    return ",".join(parts)


def assemble(edit_plan, tts_paths, source_video_paths, out_path):
    """EDL을 실제 mp4로 렌더. 각 비트를 개별 mp4로 만든 뒤 concat + 오디오 교체."""
    work = Path(out_path).parent / f"asm_{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    # 폰트를 work에 복사해 필터그래프에서 파일명만 참조(콜론 이스케이프 회피). 비트
    # 렌더 ffmpeg는 cwd=work로 실행하므로 font.ttf / cap_*.txt가 상대경로로 잡힌다.
    font = _resolve_font()
    if font:
        try:
            shutil.copy(font, work / "font.ttf")
        except OSError:
            font = None
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
        vf = _caption_vf(beat.get("narration", ""), tts_dur, bool(font), work, idx)
        # 소스를 ref["start"]부터 1배속으로 재생, tts 오디오로 교체, 출력 길이를
        # tts_dur로 고정(-t). 구간이 짧으면 -stream_loop로 소스를 반복해 나레이션
        # 길이만큼 영상을 채운다(배속 압축으로 자막이 빨라지는 것을 방지). -vf로
        # 규격(720x1280) 통일 + 새 대본 자막을 하단 바 위에 한 줄씩 굽는다.
        cmd = [
            "ffmpeg", "-y",
            "-stream_loop", "-1", "-ss", str(ref["start"]), "-i", str(src),
            "-i", str(tts),
            "-vf", vf, "-r", "30",
            "-map", "0:v:0", "-map", "1:a:0",
            "-t", str(tts_dur),
            "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p", str(clip),
        ]
        # cwd=work: 필터그래프의 font.ttf / cap_*.txt 상대경로 해석 기준(콜론 회피).
        subprocess.run(cmd, capture_output=True, check=True, cwd=str(work))
        beat_clips.append(clip)

    if not beat_clips:
        raise RuntimeError("video_assemble: 렌더할 비트가 없습니다")

    concat_txt = work / "concat.txt"
    concat_txt.write_text("".join(f"file '{c.as_posix()}'\n" for c in beat_clips), encoding="utf-8")
    # 비트 클립들은 이미 동일 설정(720x1280 libx264/aac 30fps)으로 인코딩됐으므로
    # concat에서 다시 풀 재인코딩하지 말고 스트림 복사(-c copy)한다. 재인코딩 concat은
    # 2GB 서버에서 수십 초 걸려 백그라운드 렌더가 서비스 재시작(잦은 배포)에 걸려 죽는
    # 원인이었다(2026-07-12 라이브 exit 255). -c copy는 ~0.3초로 그 취약 구간을 제거한다.
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_txt),
           "-c", "copy", str(out_path)]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(out_path)
