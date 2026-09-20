"""통짜 합성 — 대본 전체를 **한 번에** TTS하고, 정렬로 잘라 비트별 mp3를 만든다.

왜 생겼나 (2026-09-05 사장님 제보 "자막이 넘어갈 때 목소리가 튀거나 살짝씩 바뀐다"):
비트마다 따로 굽고 따로 후처리해서 붙이면, 이음매 = 자막 전환 지점이 된다. 조각마다
달라지는 것이 넷이었다.

  ① 역할별 연기 태그  narration_naturalize의 whisper.roles·intonation.emphasis_roles·
                      fillers가 칸 번호/역할에 따라 켜졌다 꺼진다 → 톤이 계단처럼 바뀐다
  ② best-of-N        칸마다 다른 seed take가 뽑힌다(랭커는 오독만 보고 톤은 안 본다)
  ③ 칸별 loudnorm    파일 단위 정규화라 짧은 칸·속삭임 칸의 게인이 따로 논다
  ④ 칸별 atempo      길이 맞춤 배속이 칸마다 달라 피치·속도감이 바뀐다

통짜로 한 번 구우면 ①②가 **구조적으로** 사라지고(한 번의 발화), ③은 통짜에 loudnorm을
한 번만 걸어 없앤다. ④는 배율이 같은 선형 변환이라 조각별로 걸어도 같다.

자를 수 있는 근거: ElevenLabs `/with-timestamps`가 **우리가 보낸 문자열 그대로**의
문자단위 정렬을 준다(tts_timestamps 참조). 그래서 각 비트 텍스트가 전체 텍스트의 어디에
있는지 찾으면 그 구간의 시각을 정확히 안다 — 받아쓰기로 되짚을 필요가 없다.

★자르는 자리는 **원음**(무음삭제·배속 전)이다 (2026-09-06 실사고).
  처음엔 통짜 전체에 무음삭제·배속을 먼저 걸고, 잘라낸 구간을 예측해 정렬을 되당긴 뒤
  잘랐다. 그런데 그 예측이 실제 silenceremove와 ±수십ms씩 어긋나 45구간이 쌓이니
  컷 위치가 실제 문장 사이 무음에서 **최대 234ms** 빗나갔다(고객 작업물 2d591a0bfd40
  실측: −74/−71/+26/+153/−234/+39ms). 앞 문장 끝 0.2초가 뒷칸 머리에 붙고 거기에
  무음이 끼어 단어 한가운데가 갈렸다 — 사장님 청취 "엄청 튀는데". 원음 정렬은
  ElevenLabs가 준 그대로라 이 오차가 없다. 문단 사이 쉼(수백ms)의 **중간점**에서 자르면
  조각마다 쉼의 절반씩을 갖고, 그 뒤 조각별 마무리(무음삭제·배속·apad·끝트림)는 비트별
  경로와 **같은 함수**(audio_post.finish_line_audio)로 돈다 → 칸 사이 쉼이 비트별과
  구조적으로 같다(같은 대본·같은 프리셋 실측: 비트별 97ms / 새 통짜 105ms / 옛 통짜 0ms).
  ★정렬만 믿고 중간점에서 자르지 않는다 — 경계는 실제 무음에서 찾는다(_boundary_cuts).

맞바꾼 것: 대본 한 칸만 고쳐도 **전체를 다시 구워야** 톤이 이어진다. 부분 재합성을
남겨두면 그 칸만 다시 튄다(그게 애초의 증상이다).

폴백: 이 경로가 어디서든 실패하면 False를 돌려주고, 호출부가 종전 비트별 경로로 간다.
라이브를 죽이지 않는다.
"""
import os
import subprocess
import sys
import traceback
from pathlib import Path

from . import audio_post, config, tts, tts_timestamps, typecast_tts

# 비트 사이 구분자 — 문단 경계라 ElevenLabs가 자연스러운 호흡을 준다. 정렬에도 이 문자가
# 그대로 들어오므로 인덱스 계산이 어긋나지 않는다.
_SEP = "\n\n"

# 통짜 합성 상한(글자). 넘으면 폴백 — 너무 긴 텍스트는 한 요청에 안 들어가고,
# 실패 시 전부를 잃는다. 숏폼 대본(30~60초)은 보통 300자 안팎이다.
_MAX_CHARS = int(os.getenv("TTS_JOINED_MAX_CHARS", "2500") or 2500)

# 조각이 **원음**의 문단 사이 쉼에서 이웃과 나눠 갖는 여백의 상한(초). 이웃과의 중간점을
# 절대 넘지 않으므로(_piece_bounds) 소리를 물어오는 일은 없고, 상한은 쉼이 아주 길 때
# 조각에 딸려오는 무음을 제한할 뿐이다. 실제 칸 사이 쉼은 여기서 정하지 않는다 —
# 조각별 마무리(audio_post.finish_line_audio: 속도감 모드는 앞뒤 무음을 걷고
# _PACE_TAIL_PAD를 얹는다 / 아니면 finalize_beat_audio의 trim_tail_silence)가 비트별
# 경로와 같은 규칙으로 정한다. 값이 넉넉한 이유: ElevenLabs 정렬도 수십ms는 흔들리므로
# 첫 자음·말끝이 깎이지 않게 한다.
_HEAD_PAD = 0.05
_TAIL_PAD = 0.60

# 경계 무음 찾기(초). 문단 사이 쉼은 원음에서 0.5~1.5초라 문장 안 쉼(≤0.33초 실측)과
# 길이로 갈린다. 정렬이 가리키는 경계 [앞 끝, 뒤 시작]을 _BOUNDARY_WINDOW만큼 넓힌
# 창과 겹치는 무음 중 _BOUNDARY_SIL_MIN 이상인 가장 긴 것의 **중심**에서 자른다.
# ★왜 정렬만 못 믿나(2026-09-06 실측): ElevenLabs가 뒷문장 첫 글자 시작을 실제보다
#   200ms 늦게 준 경계가 있었다(2d591a0bfd40 2→3, 실제 소리 15.155s vs 정렬 15.36s).
#   정렬 중간점(15.24)은 그 글자 한가운데였다. 무음을 못 찾으면 정렬 중간점으로 폴백.
_BOUNDARY_SIL_MIN = 0.15
_BOUNDARY_WINDOW = 0.15


def enabled():
    """통짜 합성을 쓸 것인가. 기본 off — 라이브에서 실측한 뒤 켠다(CLAUDE.md:
    검증 안 된 플래그를 라이브에 켜지 마라)."""
    return (os.getenv("TTS_JOINED") or "").strip().lower() in ("1", "true", "on", "yes")


def _cut(src, dst, start, end):
    """[start, end) 구간을 잘라 dst로. 재인코딩한다 — `-c copy`는 mp3 프레임 경계로
    스냅해 수십 ms가 어긋나고, 그 어긋남이 다시 이음매가 된다. 자르기는 필터(atrim)로
    한다 — 출력 옵션 `-ss/-to`보다 시각이 정확하고 뒤에 필터를 이어 붙일 수 있다."""
    filt = f"atrim=start={start:.3f}"
    if end is not None:
        filt += f":end={end:.3f}"
    filt += ",asetpts=PTS-STARTPTS"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", filt,
           "-c:a", "libmp3lame", "-q:a", "2", str(dst)]
    subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                   check=True, timeout=audio_post.FFMPEG_TIMEOUT_SEC)


def _boundary_cuts(st, en, spans, silences):
    """이웃 조각 사이 경계마다 (컷 시각, 무음 시작, 무음 끝). 무음을 못 찾으면 정렬
    중간점과 (None, None)."""
    cuts = []
    for i in range(len(spans) - 1):
        e_i = en[spans[i][1] - 1]
        s_n = st[spans[i + 1][0]]
        lo, hi = e_i - _BOUNDARY_WINDOW, s_n + _BOUNDARY_WINDOW
        cands = [(a, b) for a, b in silences
                 if (b - a) >= _BOUNDARY_SIL_MIN and b > lo and a < hi]
        if cands:
            a, b = max(cands, key=lambda ab: ab[1] - ab[0])
            cuts.append(((a + b) / 2, a, b))
        else:
            cuts.append(((e_i + s_n) / 2, None, None))
    return cuts


def _piece_bounds(st, en, spans, full_dur, silences=()):
    """조각별 (start, end) — 원음 타임라인. 이웃과의 **경계 컷을 넘지 않는다**.

    st/en = 문자별 시작·끝(원음), spans = 비트별 문자 구간, silences = 원음의 무음 구간.
    경계 컷은 _boundary_cuts(실제 무음 중심, 없으면 정렬 중간점). 조각 i는 앞 경계 컷과
    뒤 경계 컷 사이에서, 경계 무음이 있으면 **소리 기준**(무음 끝 − _HEAD_PAD ~ 무음
    시작 + _TAIL_PAD)으로, 없으면 정렬 기준(발화 시작 − _HEAD_PAD ~ 발화 끝 + _TAIL_PAD)
    으로 여백을 갖는다. 조각끼리 절대 겹치지 않는다(같은 소리가 두 칸에 안 들어간다).
    정렬이 뒤집힌 병적 경우(끝<시작)만 여백 없이 발화 구간 그대로."""
    out = []
    n = len(spans)
    cuts = _boundary_cuts(st, en, spans, silences)
    for i, (c0, c1) in enumerate(spans):
        s_i, e_i = st[c0], en[c1 - 1]
        if i == 0:
            start = max(0.0, s_i - _HEAD_PAD)
        else:
            cut, _a, b = cuts[i - 1]
            start = max(cut, (b if b is not None else s_i) - _HEAD_PAD)
        if i == n - 1:
            end = min(full_dur, e_i + _TAIL_PAD)
        else:
            cut, a, _b = cuts[i]
            end = min(cut, (a if a is not None else e_i) + _TAIL_PAD)
        if end <= start:
            start, end = max(0.0, s_i), max(e_i, s_i + 0.01)
        out.append((start, end))
    return out


def _slice_alignment(align, c0, c1, t_offset, t_len=None):
    """전체 정렬에서 [c0, c1) 문자 구간만 떼어 조각 기준(0초 시작)으로 옮긴다.
    t_len(조각 길이)이 있으면 [0, t_len]으로 죈다 — 말끝 "…"에 문단 쉼이 통째로 붙어
    조각 밖까지 뻗는 일이 있는데(실측 0.64초), 그대로 두면 rescale의 배율이 어긋난다."""
    chars = align["characters"]
    st = align["character_start_times_seconds"]
    en = align["character_end_times_seconds"]

    def _c(t):
        t -= t_offset
        if t_len is not None:
            t = min(t, t_len)
        return max(t, 0.0)
    return {
        "characters": chars[c0:c1],
        "character_start_times_seconds": [_c(t) for t in st[c0:c1]],
        "character_end_times_seconds": [_c(t) for t in en[c0:c1]],
    }


def _spans(align_chars, naturals):
    """전체 정렬 문자열에서 각 비트 텍스트의 [시작, 끝) 인덱스를 순서대로 찾는다.

    구분자 길이로 계산하지 않고 **실제로 찾는다** — 모델이 태그를 흘리거나 공백을
    바꿔도 어긋나지 않게. 하나라도 못 찾으면 None(=폴백)."""
    joined = "".join(align_chars)
    spans, cur = [], 0
    for nat in naturals:
        idx = joined.find(nat, cur)
        if idx < 0:
            return None
        spans.append((idx, idx + len(nat)))
        cur = idx + len(nat)
    return spans


def synthesize_joined(beats, naturals, out_paths, *, voice_id, settings, speed,
                      model_id, extra_tempo, customer_id=0, seed=None, work_dir=None,
                      silence_trim="off", pace_mode=False):
    """비트 전체를 한 번에 합성해 out_paths[i]에 조각을 쓴다. 성공하면 True.

    naturals[i] = 그 비트의 naturalize된 텍스트(호출부가 line_profile로 만든 것).
    실패는 전부 False — 호출부가 종전 비트별 경로로 폴백한다."""
    if not beats or len(beats) != len(naturals) != len(out_paths):
        return False
    if typecast_tts.is_typecast(model_id):
        return False              # 타입캐스트는 문자단위 정렬 계약이 다르다(1차 범위 밖)
    full_text = _SEP.join(naturals)
    if len(full_text) > _MAX_CHARS:
        print(f"[tts_joined] {len(full_text)}자 > 상한 {_MAX_CHARS} — 비트별 경로로",
              file=sys.stderr)
        return False

    work = Path(work_dir or Path(out_paths[0]).parent)
    work.mkdir(parents=True, exist_ok=True)
    full = work / "_joined.mp3"
    try:
        tts.synthesize_tts(full_text, str(full), voice_id=voice_id,
                           voice_settings=settings, speed=speed, model_id=model_id,
                           seed=seed, customer_id=customer_id)
    except Exception:      # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return False

    align = tts_timestamps.load(str(full))
    if not align or not align.get("characters"):
        print("[tts_joined] 정렬 없음 — 비트별 경로로", file=sys.stderr)
        return False

    spans = _spans(align["characters"], naturals)
    if not spans:
        print("[tts_joined] 비트 텍스트를 정렬에서 못 찾음 — 비트별 경로로", file=sys.stderr)
        return False

    # ★통짜에 거는 후처리는 **loudnorm 하나**(원인 ③). 시간축을 안 바꾸므로 정렬이 그대로
    #   맞는다. 무음삭제·배속은 조각별로(아래 finish_line_audio) — 통짜에 먼저 걸면 정렬을
    #   되당겨야 하는데 그 예측 오차가 컷을 최대 234ms 빗나가게 했다(모듈 주석).
    # 무음 mock에 loudnorm을 걸면 무음 바닥을 노이즈로 끌어올린다
    # (reference_local_tts_silent_mock_trap). 타입캐스트는 위에서 이미 배제했으므로
    # 판정 기준은 synthesize_line의 일레븐랩스 가지와 같다.
    has_voice_key = bool(config.ELEVENLABS_API_KEY)
    if has_voice_key:
        try:
            audio_post.post_process(str(full), str(full), loudnorm=True)
        except Exception:      # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            return False

    st = align["character_start_times_seconds"]
    en = align["character_end_times_seconds"]
    full_dur = audio_post._audio_dur(str(full)) or (en[-1] + _TAIL_PAD)
    # 경계는 **실제 무음**에서 찾는다(정렬은 창을 정할 뿐). 실패([])면 정렬 중간점 폴백.
    silences = audio_post.detect_silences(str(full), audio_post._PACE_THRESHOLD,
                                          _BOUNDARY_SIL_MIN)
    bounds = _piece_bounds(st, en, spans, full_dur, silences)

    for i, (c0, c1) in enumerate(spans):
        dst = str(out_paths[i])
        start, end = bounds[i]
        try:
            _cut(full, dst, start, end)
            tts_timestamps.clear(dst)                      # 옛 정렬 stale 방지
            tts_timestamps.save(dst, _slice_alignment(align, c0, c1, start, end - start))
            # 조각 마무리 = 비트별 경로와 같은 함수(무음구간 기록 → 배속·무음삭제·apad).
            # loudnorm은 통짜에 이미 걸었다 — 여기서 또 걸면 원인 ③이 되살아난다.
            audio_post.finish_line_audio(dst, tempo=extra_tempo, silence_trim=silence_trim,
                                         pace_mode=pace_mode, loudnorm=False)
        except Exception:      # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            return False
    print(f"[tts_joined] {len(spans)}비트 통짜 합성 완료 ({len(full_text)}자)", file=sys.stderr)
    return True
