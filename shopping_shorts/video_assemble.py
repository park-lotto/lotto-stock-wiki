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
_CAP_FONTSIZE = 52      # 짧은 1줄 구절이라 여유 있음 → 키움
# 레퍼런스(바이럴 숏폼) 자막 리듬: 한 구절이 1~3어절(예: "여러분, 오이 절대",
# "저도 오이를", "꼭 두 세개씩", "수분이라")로 아주 짧고, 무자막 구간 없이 빠르게
# 순차 전환된다. 목표 글자수를 작게 잡아 어절 1~3개 단위로 끊기게 한다.
_CAP_TARGET = 5         # 한 구절 목표 글자수(공백 제외). 어절 길이가 제각각이라
                        # 이 목표 근처에서 끊어도 자연히 불규칙하게(1~3어절) 나뉜다.
_CAP_MAX_WORDS = 3      # 한 구절 최대 어절 수(글자수가 짧아도 3어절 넘기지 않음).
_CAP_WRAP = 13          # 아주 긴 단일 어절 방어용(한 줄 최대 글자수, 720px 안)
_CAP_MIN_DUR = 0.25     # 한 구절 최소 표시시간(속도감). 레퍼런스도 0.2s 구절 존재.

# 한글 폰트 후보(먼저 발견되는 것 사용). repo에 NanumGothic을 번들하므로 서버·로컬
# 어디서든 별도 설치 없이 자막이 나온다(env로 다른 폰트 강제 가능).
_BUNDLED_FONT = str(Path(__file__).parent / "assets" / "NanumGothic.ttf")
_FONT_CANDIDATES = [
    os.environ.get("SHORTS_CAPTION_FONT"),
    _BUNDLED_FONT,
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


def _caption_segments(narration):
    """나레이션을 **짧은 구절 단위**로 나눈다(예: "오이 사자마자 / 냉장고에 / 넣으셨나요?").
    어절(띄어쓰기) 기준으로 묶되, 누적 글자수(공백 제외)가 _CAP_TARGET을 넘으면 끊어
    새 구절을 시작한다. 어절 길이가 제각각이라 자연히 불규칙하게 끊긴다(규칙적으로
    잘려 어색해지지 않음). 각 구절은 짧은 1줄. 반환: [구절텍스트, ...].

    방어: 목표를 크게 넘는 아주 긴 단일 어절(URL·붙여쓴 문장 등)은 _CAP_WRAP로 강제
    줄바꿈해 화면 밖으로 나가지 않게 한다."""
    narr = (narration or "").strip()
    if not narr:
        return []
    out, cur = [], []
    for w in narr.split():
        if not cur:
            cur = [w]
        # 글자수 목표 안이고 어절 수도 상한 이내면 같은 구절에 붙인다.
        elif (len("".join(cur + [w])) <= _CAP_TARGET
              and len(cur) < _CAP_MAX_WORDS):
            cur.append(w)
        else:
            out.append(" ".join(cur))
            cur = [w]
    if cur:
        out.append(" ".join(cur))
    # 목표를 크게 넘는 초장문 단일 구절만 줄바꿈으로 방어(대부분은 그대로 1줄).
    segs = []
    for s in out:
        if len(s.replace(" ", "")) > _CAP_WRAP:
            segs.extend(textwrap.wrap(s, _CAP_WRAP) or [s])
        else:
            segs.append(s)
    return segs or [narr]


def _caption_durations(segs, dur):
    """각 구절의 표시 시간(초) 리스트를 반환. 기본은 글자수 비례(균등분할 X)지만,
    아주 짧은 구절(2~3자)이 순식간에 지나가지 않도록 _CAP_MIN_DUR 하한을 준다.
    하한을 채우고 남은 시간을 나머지 구절에 글자수 비례로 재분배해, 총합은 항상
    dur를 넘지 않는다(하한들의 합이 dur를 초과하면 균등분할로 폴백)."""
    n = len(segs)
    if n == 0:
        return []
    if _CAP_MIN_DUR * n >= dur:      # 하한조차 못 채우면 균등분할
        return [dur / n] * n
    weights = [max(1, len(s.replace("\n", ""))) for s in segs]
    total_w = sum(weights)
    raw = [dur * w / total_w for w in weights]
    # 하한 미달인 구절은 하한으로 올리고, 그만큼을 하한 이상인 구절에서 비례로 회수.
    floored = [max(_CAP_MIN_DUR, r) for r in raw]
    over = sum(floored) - dur
    if over > 1e-6:
        slack_idx = [i for i, r in enumerate(floored) if r > _CAP_MIN_DUR]
        slack_total = sum(floored[i] - _CAP_MIN_DUR for i in slack_idx)
        if slack_total > 1e-6:
            for i in slack_idx:
                floored[i] -= over * (floored[i] - _CAP_MIN_DUR) / slack_total
    return floored


def _caption_vf(narration, dur, has_font, work, idx):
    """비트 영상용 -vf 필터 문자열. scale/crop으로 규격 통일 후, 폰트가 있으면
    하단 바 + 나레이션을 **짧은 구절 단위**로 순차 표시하는 drawtext들을 얹는다.
    각 구절의 표시 시간은 글자수 비례 + 최소 표시시간 하한(_caption_durations).

    ffmpeg 필터그래프는 값에 콜론(윈도 드라이브 'C:')을 못 넣으므로, 폰트·자막
    텍스트는 모두 work 폴더에 두고 **파일명만**(font.ttf / cap_*.txt) 참조한다.
    호출부는 반드시 cwd=work 로 ffmpeg를 실행해야 한다. 각 구절 텍스트는 임시
    파일(textfile=)로 넘겨 따옴표/쉼표 이스케이프 문제를 피한다."""
    base = f"scale={_OUT_W}:{_OUT_H}:force_original_aspect_ratio=increase,crop={_OUT_W}:{_OUT_H}"
    segs = _caption_segments(narration)
    if not has_font or not segs:
        return base
    durs = _caption_durations(segs, dur)
    parts = [base]
    # 하단 바(원본 소각 자막 가리기)
    parts.append(f"drawbox=x=0:y=ih-{_BAR_H}:w=iw:h={_BAR_H}:color=black@0.82:t=fill")
    t = 0.0
    for i, (seg, d) in enumerate(zip(segs, durs)):
        (work / f"cap_{idx}_{i}.txt").write_text(seg, encoding="utf-8")
        start = t
        t += d
        end = dur + 0.5 if i == len(segs) - 1 else t  # 마지막 구절은 끝까지
        parts.append(
            f"drawtext=fontfile=font.ttf:textfile=cap_{idx}_{i}.txt:"
            f"fontcolor=white:fontsize={_CAP_FONTSIZE}:line_spacing=10:"
            f"x=(w-text_w)/2:y=h-text_h-100:"
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
        src_dur = _probe_duration(src)
        clip = work / f"beat_{idx}.mp4"
        vf = _caption_vf(beat.get("narration", ""), tts_dur, bool(font), work, idx)
        # 나레이션 길이(tts_dur)만큼 소스를 ref["start"]부터 **이어서(연속)** 1배속
        # 재생한다. 구간 끝을 넘어도 그냥 원본을 계속 흘려보내 같은 2~4초가 반복되는
        # 것을 막는다. 시작점부터 tts_dur가 원본 끝을 넘으면 시작을 앞으로 당겨
        # 연속 footage를 확보한다. 원본 전체가 나레이션보다 짧을 때만 루프한다.
        start = ref["start"]
        if start + tts_dur > src_dur:
            start = max(0.0, src_dur - tts_dur)
        loop = ["-stream_loop", "-1"] if src_dur + 0.05 < tts_dur else []
        cmd = [
            "ffmpeg", "-y",
            *loop, "-ss", f"{start:.3f}", "-i", str(src),
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
