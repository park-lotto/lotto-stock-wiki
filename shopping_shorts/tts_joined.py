"""통짜 합성 — 대본 전체를 **한 번에** TTS하고, 정렬로 잘라 비트별 mp3를 만든다.

왜 생겼나 (2026-09-05 사장님 제보 "자막이 넘어갈 때 목소리가 튀거나 살짝씩 바뀐다"):
비트마다 따로 굽고 따로 후처리해서 붙이면, 이음매 = 자막 전환 지점이 된다. 조각마다
달라지는 것이 넷이었다.

  ① 역할별 연기 태그  narration_naturalize의 whisper.roles·intonation.emphasis_roles·
                      fillers가 칸 번호/역할에 따라 켜졌다 꺼진다 → 톤이 계단처럼 바뀐다
  ② best-of-N        칸마다 다른 seed take가 뽑힌다(랭커는 오독만 보고 톤은 안 본다)
  ③ 칸별 loudnorm    파일 단위 정규화라 짧은 칸·속삭임 칸의 게인이 따로 논다
  ④ 칸별 atempo      길이 맞춤 배속이 칸마다 달라 피치·속도감이 바뀐다

통짜로 한 번 구우면 ①~④가 **구조적으로** 사라진다. 원래 연속인 음성을 자른 것이라
붙였을 때 원본과 같다.

자를 수 있는 근거: ElevenLabs `/with-timestamps`가 **우리가 보낸 문자열 그대로**의
문자단위 정렬을 준다(tts_timestamps 참조). 그래서 각 비트 텍스트가 전체 텍스트의 어디에
있는지 찾으면 그 구간의 시각을 정확히 안다 — 받아쓰기로 되짚을 필요가 없다.

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

# 조각 앞뒤 여백(초). 앞은 자음이 깎이지 않을 만큼만, 뒤는 말끝이 뚝 끊기지 않을
# 만큼만 남긴다. audio_post.trim_tail_silence의 pad(0.08)와 같은 취지다.
_HEAD_PAD = 0.03
_TAIL_PAD = 0.08


def enabled():
    """통짜 합성을 쓸 것인가. 기본 off — 라이브에서 실측한 뒤 켠다(CLAUDE.md:
    검증 안 된 플래그를 라이브에 켜지 마라)."""
    return (os.getenv("TTS_JOINED") or "").strip().lower() in ("1", "true", "on", "yes")


def _cut(src, dst, start, end):
    """[start, end) 구간을 잘라 dst로. 재인코딩한다 — `-c copy`는 mp3 프레임 경계로
    스냅해 수십 ms가 어긋나고, 그 어긋남이 다시 이음매가 된다."""
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src),
           "-ss", f"{start:.3f}"]
    if end is not None:
        cmd += ["-to", f"{end:.3f}"]
    cmd += ["-c:a", "libmp3lame", "-q:a", "2", str(dst)]
    subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True,
                   check=True, timeout=audio_post.FFMPEG_TIMEOUT_SEC)


def _slice_alignment(align, c0, c1, t_offset):
    """전체 정렬에서 [c0, c1) 문자 구간만 떼어 조각 기준(0초 시작)으로 옮긴다."""
    chars = align["characters"]
    st = align["character_start_times_seconds"]
    en = align["character_end_times_seconds"]
    return {
        "characters": chars[c0:c1],
        "character_start_times_seconds": [t - t_offset for t in st[c0:c1]],
        "character_end_times_seconds": [t - t_offset for t in en[c0:c1]],
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
                      model_id, extra_tempo, customer_id=0, seed=None, work_dir=None):
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

    # ★후처리는 통짜에 **한 번만**. 이게 원인 ③④를 없애는 자리다.
    #   silence_trim/pace_mode는 여기서 쓰지 않는다 — 내부 무음을 지우면 정렬 시각이
    #   비선형으로 밀려 조각 경계가 어긋난다(1차 범위 밖, 필요하면 measure_removed_spans로 보정).
    # 무음 mock에 loudnorm을 걸면 무음 바닥을 노이즈로 끌어올린다
    # (reference_local_tts_silent_mock_trap). 타입캐스트는 위에서 이미 배제했으므로
    # 판정 기준은 synthesize_line의 일레븐랩스 가지와 같다.
    has_voice_key = bool(config.ELEVENLABS_API_KEY)
    try:
        audio_post.post_process(str(full), str(full), tempo=extra_tempo,
                                silence_trim="off", pace_mode=False,
                                loudnorm=has_voice_key)
    except Exception:      # noqa: BLE001
        traceback.print_exc(file=sys.stderr)
        return False
    # atempo는 시간축을 선형으로 줄인다 → 정렬 시각도 같은 배율로 나눈다.
    if extra_tempo and abs(extra_tempo - 1.0) > 1e-6:
        for k in ("character_start_times_seconds", "character_end_times_seconds"):
            align[k] = [t / extra_tempo for t in align[k]]

    spans = _spans(align["characters"], naturals)
    if not spans:
        print("[tts_joined] 비트 텍스트를 정렬에서 못 찾음 — 비트별 경로로", file=sys.stderr)
        return False

    st = align["character_start_times_seconds"]
    en = align["character_end_times_seconds"]
    # ★자를 지점은 **발화 경계**다(2026-09-05 서버 실측으로 고침).
    #   처음엔 앞뒤 비트의 중간점에서 잘랐다 — "붙이면 원본과 같다"는 게 근거였는데,
    #   실측해 보니 조각이 발화보다 길어졌다(2.26초 → 2.66초). 문단 사이 호흡 무음이
    #   조각에 통째로 남은 것이다. 칸 길이 = 조각 길이라 그만큼 화면이 늘어지고,
    #   이음매 뒤 0.3초가 무음이라 레벨이 60dB씩 튀었다(레퍼런스 릴스는 무음 0).
    #   무음을 버려도 **음색은 안 바뀐다** — 통짜의 값어치(한 번의 발화)는 그대로다.
    starts = [max(0.0, st[c0] - _HEAD_PAD) for c0, _ in spans]
    ends = [en[c1 - 1] + _TAIL_PAD for _, c1 in spans]

    for i, (c0, c1) in enumerate(spans):
        dst = str(out_paths[i])
        try:
            _cut(full, dst, starts[i], ends[i])
        except Exception:      # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            return False
        tts_timestamps.clear(dst)                      # 옛 정렬 stale 방지
        tts_timestamps.save(dst, _slice_alignment(align, c0, c1, starts[i]))
    print(f"[tts_joined] {len(spans)}비트 통짜 합성 완료 ({len(full_text)}자)", file=sys.stderr)
    return True
