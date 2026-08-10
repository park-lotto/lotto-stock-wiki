"""TTS mp3 후처리: 속도 미세보정(atempo)과 무음삭제(silenceremove)를 ffmpeg 한 패스로.

ElevenLabs speed는 0.7~1.2만 지원해, 그 이상(1.3~1.5) 속도는 여기서 atempo로 얹는다.
무음삭제는 나레이션 사이 쉬는 구간을 잘라 빠르게 이어붙인다(레벨: off/weak/mid/strong)."""
import os
import re as _re
import subprocess
import tempfile

# ★ffmpeg 한 호출의 상한(초). 2026-08-06 실사고: 4.1초짜리 비트 mp3 하나를 처리하다
#   ffmpeg가 **영원히 끝나지 않아** 워커가 통째로 멈췄다(라이브 job 4ca11b8270ae —
#   18분째 hrtimer_nanosleep, CPU 0.4%, 출력 0바이트. 그 사이 뒤에 온 사장님 작업은
#   큐에서 대기만 했다). 서버에서 3회 재현: atempo + apad + loudnorm이 **전부** 있고
#   그 파일일 때만 멈춘다 — 하나만 빼면 매번 정상이라 ffmpeg 내부 문제로 보인다.
#   원인을 우리가 못 고치므로 **걸리면 끊고 원본으로 진행**한다. 비트 하나가 후처리를
#   못 받는 건 소리가 조금 덜 다듬어질 뿐이지만, 멈추면 제작 자체가 안 끝난다.
#   30초: 정상 처리는 1초 안에 끝난다(실측) — 정상 작업을 자를 위험이 없는 여유값.
FFMPEG_TIMEOUT_SEC = int(os.getenv("FFMPEG_TIMEOUT_SEC", "30") or 30)

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


# 비트별 라우드니스 정규화(2026-07-22). 비트마다 별도 합성한 ElevenLabs 원음 크기가
# 제각각이라, 정규화 없이 concat하면 최종 나레이션 볼륨이 오르락내리락한다(사장님 청취).
# EBU R128 single-pass loudnorm으로 모든 비트를 같은 통합 라우드니스로 끌어 맞춘다.
# I=통합 라우드니스(LUFS)·TP=트루피크 상한(dBTP)·LRA=허용 라우드니스 레인지.
# 숏폼 보이스 표준값(-16 LUFS). ⚠️ 무음 mock(키 없음)에 걸면 무음 바닥을 끌어올려
# 노이즈가 되므로 호출부가 실제 키가 있을 때만 켠다(reference_local_tts_silent_mock_trap).
_LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"


# 속도감 모드 무음 판정값 — _pace_filters와 measure_removed_spans가 **같은 값**을 써야
# "잘라낸 구간"과 "측정한 구간"이 어긋나지 않는다. 한 곳에서만 고치도록 상수로 뺐다.
_PACE_THRESHOLD = "-38dB"
_PACE_STOP_DURATION = 0.3
_PACE_START_SILENCE = 0.05


def _pace_filters():
    """앞·중간·뒤 무음 모두 제거 + 끝 고정 여백 + 클릭방지 페이드.
    기존 silence_trim(뒤/중간만)과 달리 start_periods=1로 문장 첫머리 숨까지 잘라
    다음 문장이 딱 붙게 한다. apad는 마지막(여백은 페이드 대상 아님)."""
    return [
        (f"silenceremove=start_periods=1:start_threshold={_PACE_THRESHOLD}:"
         f"start_silence={_PACE_START_SILENCE}:"
         f"stop_periods=-1:stop_duration={_PACE_STOP_DURATION}:"
         f"stop_threshold={_PACE_THRESHOLD}"),
        f"afade=t=in:st=0:d={_PACE_FADE}",
        f"apad=pad_dur={_PACE_TAIL_PAD}",
    ]


def measure_removed_spans(in_path, threshold=None, min_dur=None):
    """속도감 모드가 **잘라낼** 무음 구간 [(시작초, 끝초), ...]을 원본 타임라인 기준으로 반환.

    ★왜 필요한가(2026-08-06): pace_mode의 silenceremove는 내부 무음까지 전부 없앤다.
    이건 조각별(piecewise) 시간왜곡이라 tts_timestamps.rescale의 선형사상 하나로는
    표현이 안 된다 — 잘린 쉼 뒤의 단어가 갈수록 늦게 표시된다(실측 +0.11 → +0.28s 누적).
    여기서 '어디를 얼마나 잘랐나'를 재두면 rescale이 그만큼씩 당겨 정확히 맞출 수 있다.

    silencedetect는 판정만 하고 자르지 않으므로 원본 시각 그대로 읽힌다. 임계·최소길이를
    _pace_filters와 동일하게 맞춰 판정 불일치를 최소화한다(완전 동일하진 않아 ±수십ms 잔차는 남는다).
    실패·ffmpeg 없음 → [](호출부는 선형 폴백 = 기존 동작)."""
    thr = threshold or _PACE_THRESHOLD
    # 앞무음은 start_silence(0.05)만 넘어도 잘리고 내부는 stop_duration(0.3) 이상만 잘린다.
    # 더 짧은 쪽으로 잡아 앞무음을 놓치지 않고, 내부 구간은 아래에서 길이로 걸러낸다.
    d = _PACE_START_SILENCE if min_dur is None else min_dur
    try:
        r = subprocess.run(
            ["ffmpeg", "-i", str(in_path), "-af",
             f"silencedetect=noise={thr}:d={d}", "-f", "null", "-"],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
            timeout=FFMPEG_TIMEOUT_SEC)   # 멈추면 []를 반환 = 선형 폴백(기존 동작)
    except Exception:
        return []
    spans, start = [], None
    for line in (r.stderr or "").splitlines():
        if "silence_start:" in line:
            try:
                start = float(line.split("silence_start:")[1].split("|")[0].strip())
            except ValueError:
                start = None
        elif "silence_end:" in line and start is not None:
            try:
                end = float(line.split("silence_end:")[1].split("|")[0].strip())
            except ValueError:
                start = None
                continue
            if start <= 1e-3:
                # 앞무음: start_periods=1이 통째로 걷어낸다.
                spans.append((start, end))
            elif (end - start) >= _PACE_STOP_DURATION:
                # ★내부 무음은 '삭제'가 아니라 stop_duration까지 '줄이기'다(2026-08-06 실측).
                # silenceremove는 0.3초를 남긴다 — 전체를 지운다고 보면 뒤 단어를 너무
                # 많이 당겨 자막이 이번엔 반대로 빨라진다(실측: 2.2초 감지 vs 실제 1.433초).
                # 그래서 초과분만 잘린 것으로 계산한다. 뒤에서부터 깎이므로 구간 끝을 남긴다.
                spans.append((start, end - _PACE_STOP_DURATION))
            start = None
    return spans


def post_process(in_path, out_path, tempo=1.0, silence_trim="off", pace_mode=False,
                 loudnorm=False):
    """in_path mp3에 속도(tempo)·무음삭제·라우드니스 정규화를 적용해 out_path로.
    전부 no-op이면 in_path 그대로 반환.

    tempo: atempo 배율(1.0=변화없음). silence_trim: off/weak/mid/strong.
    pace_mode: True면 속도감 모드 — 앞·중간·뒤 무음을 모두 잘라 문장을 딱 붙이고
    끝 여백·가장자리 페이드를 얹는다(silence_trim은 무시). 기본 False(하위호환).
    loudnorm: True면 EBU loudnorm을 **마지막 필터**로 얹어 비트별 음성 크기를 같은
    통합 라우드니스로 맞춘다(볼륨 오르락내리락 제거). 이 필터 하나만 있어도 재인코딩을
    거치므로 tempo=1.0·silence off인 비트까지 빠짐없이 정규화된다. 기본 False."""
    filters = []
    if tempo and abs(tempo - 1.0) > 1e-3:
        filters.append(f"atempo={tempo:.3f}".rstrip("0").rstrip("."))
    if pace_mode:
        filters.extend(_pace_filters())
    else:
        sf = _silence_filter(silence_trim)
        if sf:
            filters.append(sf)
    if loudnorm:                          # 속도·무음삭제 뒤 = 최종 출력 기준으로 정규화
        filters.append(_LOUDNORM)
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
            timeout=FFMPEG_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired:
        # ★멈춘 ffmpeg는 여기서 끊고 **원본 그대로** 진행한다(2026-08-06 실사고).
        #   예외를 올리면 비트 하나 때문에 제작 전체가 실패한다 — 후처리는 다듬기지
        #   필수가 아니다. 조용히 넘기지 않고 로그를 남겨 재발을 볼 수 있게 한다.
        if same and os.path.exists(target):
            os.remove(target)
        print(f"[audio_post] ⚠️ ffmpeg {FFMPEG_TIMEOUT_SEC}초 초과 — 후처리 건너뛰고 "
              f"원본 사용: {os.path.basename(str(in_path))} (필터: {','.join(filters)})",
              flush=True)
        return in_path
    except Exception:
        if same and os.path.exists(target):
            os.remove(target)
        raise
    if same:
        os.replace(target, str(out_path))
    return str(out_path)


def _audio_dur(path):
    """ffprobe로 오디오 길이(초). 실패면 0.0."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
            timeout=FFMPEG_TIMEOUT_SEC)   # 멈추면 0.0 = 호출부가 판정 생략(기존 동작)
        return float((r.stdout or "0").strip() or 0.0)
    except Exception:
        return 0.0


def trim_tail_silence(in_path, out_path, pad=0.08, threshold="-40dB"):
    """비트 TTS 끝의 자연 무음(호흡·여백)만 잘라 이어붙임을 딱 맞춘다 — 비트 사이 dead-air
    제거(2026-07-22, 레퍼런스 릴스는 무음 0). **뒤만** 자르고(중간 쉼·문장 리듬은 보존) 아주
    작은 여백(pad)으로 급함·클릭음 방지. areverse로 앞을 만들어 뒤 무음만 제거 후 되돌린다.
    ⚠️ 무음 mock(키 없음) 보호: 결과가 입력 대비 과도하게 짧아지면(전부 무음) 원본 유지."""
    in_dur = _audio_dur(in_path)
    filt = (f"areverse,silenceremove=start_periods=1:start_threshold={threshold}:"
            f"start_silence=0.02,areverse,apad=pad_dur={pad}")
    same = os.path.abspath(str(in_path)) == os.path.abspath(str(out_path))
    fd, tmp = tempfile.mkstemp(suffix=".mp3", dir=os.path.dirname(os.path.abspath(str(out_path))))
    os.close(fd)
    try:
        subprocess.run(["ffmpeg", "-y", "-i", str(in_path), "-af", filt, "-q:a", "4", tmp],
                       stdin=subprocess.DEVNULL, capture_output=True, check=True,
                       timeout=FFMPEG_TIMEOUT_SEC)   # 멈춤 방지 — 아래 except가 원본 유지
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        return str(in_path)   # 실패해도 원본 그대로(무해)
    out_dur = _audio_dur(tmp)
    # mock/오작동 보호: 말이 있는 비트(0.5s+)가 0.3s 미만으로 잘리면 전부 무음이었던 것 → 원본.
    if in_dur > 0.5 and out_dur < 0.3:
        os.remove(tmp)
        return str(in_path)
    os.replace(tmp, str(out_path))
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
    try:
        from shopping_shorts.video_assemble import _probe_duration
        total = _probe_duration(path)
        if total <= 0:
            return 0.0
        proc = subprocess.run(
            ["ffmpeg", "-i", str(path), "-af", "silencedetect=noise=-40dB:d=0.2",
             "-f", "null", "-"],
            capture_output=True, text=True, check=True,
            timeout=FFMPEG_TIMEOUT_SEC)   # 멈추면 아래 except가 0.0 반환(기존 동작)
        head, tail = _parse_silence_edges(proc.stderr or "", total)
        return head if edge == "head" else tail
    except Exception:
        return 0.0
