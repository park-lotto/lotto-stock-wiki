"""TTS mp3 후처리: 속도 미세보정(atempo)과 무음삭제(silenceremove)를 ffmpeg 한 패스로.

ElevenLabs speed는 0.7~1.2만 지원해, 그 이상(1.3~1.5) 속도는 여기서 atempo로 얹는다.
무음삭제는 나레이션 사이 쉬는 구간을 잘라 빠르게 이어붙인다(레벨: off/weak/mid/strong)."""
import os
import re as _re
import subprocess
import sys
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

# ⚠️★한글 경로에서 무음 감지가 통째로 죽던 버그(2026-09-22 실측 발견).
#   ffmpeg/ffprobe는 stderr를 **UTF-8**로 내는데 text=True만 주면 파이썬이 로캘
#   (윈도우=cp949)로 디코드하다 리더 스레드에서 UnicodeDecodeError로 죽는다.
#   이 파일의 except는 전부 "실패하면 []/0.0"이라 예외가 조용히 삼켜지고,
#   호출부는 **"무음이 없다"**로 잘못 받았다.
#   실측(job 409f894230c6, 경로에 '로또의 주식' 포함):
#       detect_edge_silence → 0.0  /  detect_silences → []   (5개 비트 전부)
#       ffmpeg를 직접 돌리면 → beat_0에 0.31초 무음이 분명히 있다
#   즉 '무음이 없어서 0'이 아니라 **재지도 못하고 0**이었다. 자동 자르기가 한 번도
#   동작한 적 없었다는 뜻이다.
#   ★같은 함정을 video_assemble.py:546(_FF_TEXT)이 2026-07-16에 이미 고쳤는데
#     이 파일은 그 수정을 못 받았다 — 같은 판단이 두 벌로 갈린 전형(0순위-B).
#     여기서 상수로 뽑아 이 파일 안의 세 곳이 한 규칙을 쓰게 한다
#     (video_assemble을 import하면 순환이 된다: 그쪽이 audio_post를 쓴다).
_FF_TEXT = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}

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
# ★-30dB (2026-08-22 사장님 청취 확정). -38dB는 문장 사이 숨을 "소리 있음"으로
#   보고 안 잘라 20구간이 남았다(실측 2.38초). -30dB로 올리면 그 숨까지 잡힌다.
_PACE_THRESHOLD = "-30dB"
# ★0.12초 (2026-08-22 사장님: "문장 끝과 시작이 거의 공간 없이 가는 건데").
#   silenceremove는 무음을 **삭제하는 게 아니라 이 값까지 줄인다** — 0.3이면
#   문장 사이가 0.3초씩 벌어진다. 렌더 4편 실측에서 나온 공백이 정확히
#   0.28~0.31초로 이 상수에 걸려 있었다(무음 총 7~9%, 11~19구간).
#   메종(기준 채널)은 세그먼트 간 무음 0.0초·발화비율 96~101%다 — 빠르게 말해서가
#   아니라 **쉬지 않아서** 같은 시간에 더 담긴다.
#   ★값은 사장님 청취로 골랐다(같은 대본 191자·speed 1.6, 무음컷 강도별 실측):
#       stop 0.12 → 27.74초(잔여 2.38초/20구간)  ← 거의 안 잘린다. 여기서 멈춰 "최대 1.2초"로
#                                                   잘못 결론냈던 값이다.
#       stop 0.05 → 26.14초(잔여 0.11초/ 1구간)  ← ★채택. 메종원본 26.31초와 일치
#       stop 0.02 → 24.70초 / stop 0.00 → 22.94초(사람 원본 22.67초와 동급이나 숨이 없다)
#   ⚠️0으로 두지 않는다. 완전히 붙이면 기관총처럼 들린다(끝 여백 _PACE_TAIL_PAD와 짝).
_PACE_STOP_DURATION = 0.05
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
    spans = []
    for start, end in detect_silences(in_path, thr, d):
        if start <= 1e-3:
            # 앞무음: start_periods=1이 통째로 걷어낸다.
            spans.append((start, end))
        elif (end - start) >= _PACE_STOP_DURATION:
            # ★내부 무음은 '삭제'가 아니라 stop_duration까지 '줄이기'다(2026-08-06 실측).
            # silenceremove는 0.3초를 남긴다 — 전체를 지운다고 보면 뒤 단어를 너무
            # 많이 당겨 자막이 이번엔 반대로 빨라진다(실측: 2.2초 감지 vs 실제 1.433초).
            # 그래서 초과분만 잘린 것으로 계산한다. 뒤에서부터 깎이므로 구간 끝을 남긴다.
            spans.append((start, end - _PACE_STOP_DURATION))
    return spans


def detect_silences(in_path, threshold, min_dur):
    """silencedetect 판정 그대로 [(시작초, 끝초), ...] — 원본 타임라인, 자르지 않는다.
    measure_removed_spans(무음삭제 예측)와 tts_joined(통짜 조각의 경계 찾기)가 같이 쓰는
    파서 한 벌(0순위-B). 실패·ffmpeg 없음·멈춤 → [] (호출부가 각자 폴백)."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-i", str(in_path), "-af",
             f"silencedetect=noise={threshold}:d={min_dur}", "-f", "null", "-"],
            stdin=subprocess.DEVNULL, check=True,
            timeout=FFMPEG_TIMEOUT_SEC, **_FF_TEXT)
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
            spans.append((start, end))
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


def finish_line_audio(path, *, tempo=1.0, silence_trim="off", pace_mode=False,
                      loudnorm=False):
    """합성된 한 줄 mp3의 마무리 — 무음삭제 구간 기록 + post_process. **판정은 여기 한 곳**.

    비트별 경로(mix_pipeline.synthesize_line)와 통짜 경로(tts_joined의 조각)가 같이
    쓴다(0순위-B). 2026-09-06 실사고: 통짜가 조각 마무리를 따로 조립했다가(전체에
    무음삭제를 건 뒤 정렬을 되당겨 자르기) 정렬 오차가 최대 234ms 쌓여 단어 한가운데가
    갈렸다 — 문장 사이 쉼이 3~28ms(비트별 60ms). 조각을 비트별과 **같은 코드**로
    마무리하면 쉼·여백이 구조적으로 같아진다.

    ★무음 제거 '전에' 어디를 자를지 재서 사이드카에 남긴다(2026-08-06). post_process는
    제자리 덮어쓰기라 뒤에는 원본 타임라인을 알 길이 없다. 이 구간들이 있어야 TTS
    타임스탬프를 조각별로 당겨 자막을 맞출 수 있다(선형사상으론 누적 드리프트가 남는다).
    측정 실패 = 선형 폴백(기존 동작), 렌더는 계속."""
    from . import tts_timestamps          # tts_timestamps가 이 모듈을 import한다(순환 방지)
    if pace_mode:
        try:
            tts_timestamps.save_removed(str(path), measure_removed_spans(str(path)))
        except Exception:      # noqa: BLE001
            print(f"[audio_post] 무음구간 측정 실패 — 선형 폴백: {os.path.basename(str(path))}",
                  flush=True)
    return post_process(str(path), str(path), tempo=tempo, silence_trim=silence_trim,
                        pace_mode=pace_mode, loudnorm=loudnorm)


def _audio_dur(path):
    """ffprobe로 오디오 길이(초). 실패면 0.0."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            stdin=subprocess.DEVNULL, check=True,
            timeout=FFMPEG_TIMEOUT_SEC, **_FF_TEXT)   # 멈추면 0.0 = 호출부가 판정 생략(기존 동작)
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


# 파형 막대 개수. 화면 폭이 어떻든 이 개수로 그린다(CSS flex가 늘린다).
# 120 = 20초 문장에서 막대 하나가 0.17초 — 숨 쉬는 구간이 눈에 보이는 해상도.
_WAVE_BARS = 120


def extract_peaks(path, bars=_WAVE_BARS):
    """mp3 → 막대별 음량 피크 [0.0~1.0] 리스트. 실패·ffmpeg 없음 → [].

    ★왜 서버에서 뽑나(2026-09-22): 브라우저 decodeAudioData로 그리면 장면 8~20개의
    mp3를 전부 받아 디코딩해야 해 패널이 느려지고, 무엇보다 **자동 자르기 판정(ffmpeg
    silencedetect)과 화면에 보이는 파형이 서로 다른 엔진**이 된다 — 같은 판단을 두 벌로
    적으면 반드시 어긋난다(0순위-B). 여기서 뽑으면 둘 다 ffmpeg 한 엔진이다.

    구현: s16le raw PCM(8kHz 모노)로 디코딩해 구간별 최대 절대값을 취한다. 8kHz면
    20초 문장이 160KB라 메모리 부담이 없고, 음량 포락선을 그리는 데는 충분하다
    (주파수 분석이 아니라 '얼마나 큰가'만 보면 되므로 샘플레이트가 낮아도 된다)."""
    try:
        r = subprocess.run(
            ["ffmpeg", "-i", str(path), "-ac", "1", "-ar", "8000",
             "-f", "s16le", "-acodec", "pcm_s16le", "-"],
            stdin=subprocess.DEVNULL, capture_output=True, check=True,
            timeout=FFMPEG_TIMEOUT_SEC)
    except Exception:
        return []
    raw = r.stdout or b""
    n = len(raw) // 2
    if n <= 0:
        return []
    import array
    samples = array.array("h")
    samples.frombytes(raw[:n * 2])
    if sys.byteorder == "big":
        samples.byteswap()      # s16le 고정 출력이므로 빅엔디안 기계에서만 뒤집는다
    step = n / float(bars)
    peaks = []
    for k in range(bars):
        lo = int(k * step)
        hi = int((k + 1) * step)
        if hi <= lo:
            hi = lo + 1
        chunk = samples[lo:min(hi, n)]
        peak = max((abs(v) for v in chunk), default=0)
        peaks.append(round(min(1.0, peak / 32768.0), 4))
    return peaks


# 문장 중간 무음을 찾을 때 쓰는 판정값. _PACE_THRESHOLD(-30dB)와 같은 기준을 쓴다 —
# 화면에 보여주는 구간과 속도감 모드가 자르는 구간이 다르면 사장님이 보는 것과 결과가 어긋난다.
_GAP_THRESHOLD = _PACE_THRESHOLD
_GAP_MIN_DUR = 0.10       # 이보다 짧은 쉼은 리듬이라 후보로 안 올린다
_GAP_KEEP = 0.06          # 구간을 지울 때 남길 숨(완전히 붙이면 기관총처럼 들린다)
# 잘린 이음매에 거는 페이드(초). _PACE_FADE(12ms)는 클릭음 방지용이라 **너무 짧아**
# 0.14 → 0 낙차를 못 감춘다(2026-09-23 실측: 그래도 한 칸에 떨어졌다).
# 25ms면 귀가 '끊겼다'가 아니라 '잦아들었다'로 듣는다.
_CUT_FADE = 0.025


def find_gaps(path, threshold=None, min_dur=None, keep=_GAP_KEEP):
    """문장 **중간**의 조용한 구간 [{start,end,drop}, ...] — 앞뒤 끝 무음은 뺀다.

    앞뒤는 head_trim/tail_trim이 이미 맡고 있어(0순위-B) 여기서 또 세면 두 벌이 된다.
    drop = 실제로 지울 길이(구간 길이에서 숨 keep을 뺀 것). keep을 남기는 이유는
    _PACE_TAIL_PAD와 같다 — 완전히 붙이면 말이 기관총처럼 들린다.

    실패·ffmpeg 없음 → []."""
    total = _audio_dur(path)
    if total <= 0:
        return []
    spans = detect_silences(path, threshold or _GAP_THRESHOLD,
                            _GAP_MIN_DUR if min_dur is None else min_dur)
    gaps = []
    for start, end in spans:
        if start <= 0.05 or end >= (total - 0.05):
            continue                      # 끝에 닿으면 엣지 트림의 몫이다
        drop = round((end - start) - keep, 3)
        if drop <= 0.02:
            continue                      # 지워봐야 티가 안 난다
        gaps.append({"start": round(start, 3), "end": round(end, 3), "drop": drop})
    return gaps


def cut_gaps(in_path, out_path, gaps, keep=_GAP_KEEP):
    """gaps 구간을 잘라낸 mp3를 만든다. gaps가 비면 아무것도 안 하고 None.

    ★왜 파일을 새로 만드나: 렌더는 `-ss`로 **앞만** 건너뛸 수 있어 중간은 뺄 수 없다.
    잘라낸 파일을 미리 만들어 넘기면 렌더·자막·캡컷이 **기존 경로를 그대로** 쓴다
    — 세 곳에 같은 잘라내기 논리를 심지 않는다(0순위-B).

    각 구간은 keep만큼 숨을 남기고 지운다. 조각 경계엔 아주 짧은 페이드를 걸어
    클릭음을 막는다(_PACE_FADE와 같은 이유)."""
    if not gaps:
        return None
    total = _audio_dur(in_path)
    if total <= 0:
        return None
    # 남길 조각 = 전체에서 (구간 시작+keep ~ 구간 끝)을 뺀 나머지
    keeps, cur = [], 0.0
    for g in sorted(gaps, key=lambda x: x["start"]):
        s, e = float(g["start"]) + keep, float(g["end"])
        if s <= cur or e <= cur or s >= total:
            continue
        if s > cur:
            keeps.append((cur, min(s, total)))
        cur = min(e, total)
    if cur < total:
        keeps.append((cur, total))
    keeps = [(a, b) for a, b in keeps if (b - a) > 0.01]
    if len(keeps) <= 1:
        return None                       # 자를 게 없거나 통째로 남는다
    parts = []
    last = len(keeps) - 1
    for k, (a, b) in enumerate(keeps):
        seg = b - a
        f = [f"[0:a]atrim=start={a:.3f}:end={b:.3f}", "asetpts=PTS-STARTPTS"]
        # ★페이드는 **잘린 이음매에만** 건다(2026-09-23 사장님 "무음자르기후 5초가 뚝끊김").
        #   첫 조각의 시작과 마지막 조각의 끝은 원래 문장의 앞뒤 끝이라 **말이 살아있다** —
        #   거기에 페이드를 걸면 멀쩡한 말을 깎아 오히려 뚝 끊긴다.
        #   실측(beat_0 끝): 0.141 -> 0.000 한 칸 낙하 = 사장님이 들으신 5.61초 그 지점.
        if k > 0:
            f.append(f"afade=t=in:st=0:d={min(_CUT_FADE, seg/2):.3f}")
        if k < last:
            d = min(_CUT_FADE, seg / 2)
            f.append(f"afade=t=out:st={max(0.0, seg - d):.3f}:d={d:.3f}")
        parts.append(",".join(f) + f"[p{k}]")
    fc = ";".join(parts) + ";" + "".join(f"[p{k}]" for k in range(len(keeps))) \
         + f"concat=n={len(keeps)}:v=0:a=1[out]"
    fd, tmp = tempfile.mkstemp(suffix=".mp3",
                               dir=os.path.dirname(os.path.abspath(str(out_path))))
    os.close(fd)
    try:
        subprocess.run(["ffmpeg", "-y", "-i", str(in_path), "-filter_complex", fc,
                        "-map", "[out]", "-q:a", "4", tmp],
                       stdin=subprocess.DEVNULL, check=True,
                       timeout=FFMPEG_TIMEOUT_SEC, **_FF_TEXT)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        return None                       # 실패해도 원본은 무사 — 호출부가 원본을 쓴다
    out_dur = _audio_dur(tmp)
    # 보호: 말이 있던 비트가 0.3초 밑으로 잘렸다면 판정이 틀린 것 → 버리고 원본 유지.
    if total > 0.5 and out_dur < 0.3:
        os.remove(tmp)
        return None
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
            stdin=subprocess.DEVNULL, check=True,
            timeout=FFMPEG_TIMEOUT_SEC, **_FF_TEXT)   # 멈추면 아래 except가 0.0 반환(기존 동작)
        head, tail = _parse_silence_edges(proc.stderr or "", total)
        return head if edge == "head" else tail
    except Exception:
        return 0.0
