"""TTS mp3 후처리: 속도 미세보정(atempo)과 무음삭제(silenceremove)를 ffmpeg 한 패스로.

ElevenLabs speed는 0.7~1.2만 지원해, 그 이상(1.3~1.5) 속도는 여기서 atempo로 얹는다.
무음삭제는 나레이션 사이 쉬는 구간을 잘라 빠르게 이어붙인다(레벨: off/weak/mid/strong)."""
import os
import re as _re
import subprocess
import subprocess as _subprocess
import tempfile

# 레벨별 silenceremove 파라미터. stop_duration=자를 최소 무음길이(초), stop_threshold=무음 판정 dB.
# 강할수록 짧은 무음까지 자르고(작은 duration), 판정 임계도 관대(높은 dB).
_SILENCE = {
    "weak":   "silenceremove=stop_periods=-1:stop_duration=0.6:stop_threshold=-40dB",
    "mid":    "silenceremove=stop_periods=-1:stop_duration=0.4:stop_threshold=-38dB",
    "strong": "silenceremove=stop_periods=-1:stop_duration=0.25:stop_threshold=-35dB",
}


def _silence_filter(level):
    """레벨 문자열 → silenceremove 필터 문자열. off/미지정이면 None."""
    return _SILENCE.get(level or "off")


# 속도감 모드 전용 파라미터. 끝 여백을 남겨 기관총처럼 안 들리게(0=최대 타이트),
# 가장자리 페이드로 딱 붙일 때 클릭음 방지.
_PACE_TAIL_PAD = 0.08    # 문장 끝 고정 여백(초)
_PACE_FADE = 0.012       # 가장자리 페이드(초)


def _pace_filters():
    """앞·중간·뒤 무음 모두 제거 + 끝 고정 여백 + 클릭방지 페이드.
    기존 silence_trim(뒤/중간만)과 달리 start_periods=1로 문장 첫머리 숨까지 잘라
    다음 문장이 딱 붙게 한다. apad는 마지막(여백은 페이드 대상 아님)."""
    return [
        ("silenceremove=start_periods=1:start_threshold=-38dB:start_silence=0.05:"
         "stop_periods=-1:stop_duration=0.3:stop_threshold=-38dB"),
        f"afade=t=in:st=0:d={_PACE_FADE}",
        f"apad=pad_dur={_PACE_TAIL_PAD}",
    ]


def post_process(in_path, out_path, tempo=1.0, silence_trim="off", pace_mode=False):
    """in_path mp3에 속도(tempo)·무음삭제를 적용해 out_path로. 둘 다 no-op이면 in_path 그대로 반환.

    tempo: atempo 배율(1.0=변화없음). silence_trim: off/weak/mid/strong.
    pace_mode: True면 속도감 모드 — 앞·중간·뒤 무음을 모두 잘라 문장을 딱 붙이고
    끝 여백·가장자리 페이드를 얹는다(silence_trim은 무시). 기본 False(하위호환)."""
    filters = []
    if tempo and abs(tempo - 1.0) > 1e-3:
        filters.append(f"atempo={tempo:.3f}".rstrip("0").rstrip("."))
    if pace_mode:
        filters.extend(_pace_filters())
    else:
        sf = _silence_filter(silence_trim)
        if sf:
            filters.append(sf)
    if not filters:
        return in_path
    # ffmpeg는 같은 파일을 입력이자 출력으로 쓰지 못한다(in-place 시 입력이 잘려 실패).
    # in==out이면 임시파일에 쓴 뒤 원자적으로 교체한다.
    same = os.path.abspath(str(in_path)) == os.path.abspath(str(out_path))
    if same:
        fd, target = tempfile.mkstemp(suffix=".mp3", dir=os.path.dirname(os.path.abspath(str(out_path))))
        os.close(fd)
    else:
        target = str(out_path)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(in_path), "-af", ",".join(filters),
             "-q:a", "4", target],
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
        )
    except Exception:
        if same and os.path.exists(target):
            os.remove(target)
        raise
    if same:
        os.replace(target, str(out_path))
    return str(out_path)


def _parse_silence_edges(stderr, total_dur):
    """silencedetect stderr → (앞무음초, 뒤무음초).
    앞무음 = silence_start≈0에서 시작한 구간의 end.
    뒤무음 = silence_end≈total_dur에서 끝난 구간의 duration(끝에 닿는 것만)."""
    starts = [float(m) for m in _re.findall(r"silence_start:\s*([0-9.]+)", stderr)]
    ends = _re.findall(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", stderr)
    head = 0.0
    tail = 0.0
    for s in starts:
        if s <= 0.05:            # 0에서 시작 = 앞무음
            # 짝지는 end 찾기(첫 end)
            if ends:
                head = float(ends[0][0])
            break
    for end_t, dur in ends:
        if abs(float(end_t) - total_dur) <= 0.05:   # 끝에 닿음 = 뒤무음
            tail = float(dur)
    return head, tail


def detect_edge_silence(path, edge):
    """path의 앞/뒤 무음 길이(초). edge in {"head","tail"}. 감지 실패 시 0.0."""
    from shopping_shorts.video_assemble import _probe_duration
    total = _probe_duration(path)
    if total <= 0:
        return 0.0
    proc = _subprocess.run(
        ["ffmpeg", "-i", str(path), "-af", "silencedetect=noise=-40dB:d=0.2",
         "-f", "null", "-"],
        capture_output=True, text=True)
    head, tail = _parse_silence_edges(proc.stderr or "", total)
    return head if edge == "head" else tail
