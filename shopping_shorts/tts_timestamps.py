"""TTS가 준 문자단위 타임스탬프 → 자막 싱크용 단어 타임스탬프(2026-07-31).

왜 생겼나 — 자막 표시시간은 **이미 실측**이었다. 다만 그 실측의 출처가 이상했다:
우리가 ElevenLabs로 만든 mp3를 GROQ Whisper로 **다시 받아쓰기**해서
(asr_check.transcribe_words) 단어 시각을 얻고 있었다. 우리가 넣은 원문을 아는데도
남에게 다시 들려주고 받아 적게 한 셈이다. 대가 셋:

  ① 비트마다 GROQ 왕복 1회(업로드+전사) — 렌더시간과 비용
  ② 받아쓴 말과 우리 원문을 difflib으로 맞춰야 하는데, 숫자("만 오천 원"↔"15,000원")·
     영어 제품명·발음교정 사전으로 다르게 읽힌 단어에서 어긋난다. caption_sync의
     _MIN_MATCH_RATIO(0.5) 미달이면 **조용히** 글자수 비례 추정으로 강등된다.
  ③ GROQ 키가 없거나 그쪽이 죽으면 전부 추정. 영상은 그대로 나오므로 사고로 안 보인다.

ElevenLabs /with-timestamps는 같은 값을 추가비용 없이 준다(같은 합성, 응답에 정렬만 얹힘).
게다가 **우리가 보낸 문자열 자체**의 정렬이라 맞출 대상이 없다 = 어긋날 수가 없다.

저장 방식은 mp3 옆 사이드카 JSON(`<mp3>.align.json`)이다. synthesize_tts의 반환값을
바꾸면 호출부(synthesize_best·mix_pipeline·app·스크립트)가 전부 걸리는데, 사이드카면
"필요한 쪽만 읽어간다". 대신 **stale이 치명적**이라(같은 경로에 새 텍스트를 재합성하면
옛 정렬이 남는다) 합성 때마다 지우고 새로 쓴다 — clear()/save() 참조.
"""
import json
import os

_SUFFIX = ".align.json"


def sidecar_path(mp3_path):
    """mp3 경로 → 정렬 사이드카 경로."""
    return str(mp3_path) + _SUFFIX


def clear(mp3_path):
    """옛 정렬 제거. ★합성 직전에 반드시 부른다 — 같은 경로 재합성 시 옛 정렬이
    남으면 새 대사에 옛 타이밍을 씌운다(자막이 통째로 밀린다)."""
    try:
        os.remove(sidecar_path(mp3_path))
    except OSError:
        pass


def save(mp3_path, alignment):
    """alignment(dict) 저장. 실패해도 조용히 넘어간다 — 사이드카가 없으면 ASR 폴백이 받는다."""
    if not alignment:
        return None
    try:
        with open(sidecar_path(mp3_path), "w", encoding="utf-8") as f:
            json.dump(alignment, f, ensure_ascii=False)
        return sidecar_path(mp3_path)
    except OSError:
        return None


def copy(src_mp3, dst_mp3):
    """src의 정렬을 dst로 옮긴다(synthesize_best가 고른 take를 확정할 때).
    src에 정렬이 없으면 dst의 옛 정렬을 지운다 — 남겨두면 stale이다."""
    try:
        with open(sidecar_path(src_mp3), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        clear(dst_mp3)
        return None
    return save(dst_mp3, data)


def words_from_alignment(alignment):
    """ElevenLabs alignment → [{"word", "start", "end"}]. 공백으로 단어를 끊는다.

    alignment = {"characters": [...], "character_start_times_seconds": [...],
                 "character_end_times_seconds": [...]}
    ★normalized_alignment가 아니라 alignment를 써야 한다 — 후자는 읽기용으로 정규화된
    텍스트(숫자→한글 등)라 우리 원문과 단어가 어긋나, 애초에 없애려던 문제가 돌아온다.
    """
    if not isinstance(alignment, dict):
        return None
    chars = alignment.get("characters")
    starts = alignment.get("character_start_times_seconds")
    ends = alignment.get("character_end_times_seconds")
    if not chars or not starts or not ends:
        return None
    n = min(len(chars), len(starts), len(ends))
    words, cur, w_start, w_end = [], [], None, None
    for i in range(n):
        ch = chars[i]
        if not isinstance(ch, str):
            continue
        if ch.strip() == "":                      # 공백·개행 = 단어 경계
            if cur:
                words.append({"word": "".join(cur), "start": w_start, "end": w_end})
                cur, w_start, w_end = [], None, None
            continue
        if w_start is None:
            w_start = float(starts[i])
        w_end = float(ends[i])
        cur.append(ch)
    if cur:
        words.append({"word": "".join(cur), "start": w_start, "end": w_end})
    return words or None


_RESCALE_MIN, _RESCALE_MAX = 0.5, 2.0


def rescale(words, final_dur):
    """TTS 시각을 **후처리된** mp3의 타임라인으로 옮긴다. 못 믿을 값이면 원본 그대로.

    ★왜 필요한가: 합성 직후 audio_post.post_process가 같은 파일을 제자리에서 고친다
    (tempo 배속 + 앞뒤 무음 트림). ASR은 그 결과물을 듣고 받아 적으니 자동으로 맞았지만,
    TTS 타임스탬프는 **후처리 전** 음성의 시각이라 그대로 쓰면 자막이 밀린다.
    둘 다 선형 변환이므로 [첫 단어 시작, 마지막 단어 끝] → [0, final_dur]로 되맞추면 된다
    (앞 트림 = 상수 이동, 배속 = 배율 — 이 한 번의 사상이 둘 다 흡수한다).

    배율이 0.5~2.0 밖이면 가정이 깨진 것(길이 측정 실패 등)이라 손대지 않는다 —
    틀린 보정보다 무보정이 낫다."""
    if not words or not final_dur or final_dur <= 0:
        return words
    first = words[0].get("start")
    last = words[-1].get("end")
    if first is None or last is None or last <= first:
        return words
    scale = final_dur / (last - first)
    if not (_RESCALE_MIN <= scale <= _RESCALE_MAX):
        return words
    out = []
    for w in words:
        s, e = w.get("start"), w.get("end")
        out.append({"word": w.get("word", ""),
                    "start": (s - first) * scale if s is not None else None,
                    "end": (e - first) * scale if e is not None else None})
    return out


def words_from_mp3(mp3_path):
    """mp3 옆 사이드카를 읽어 단어 타임스탬프 반환. 없거나 깨졌으면 None(호출부가 ASR 폴백)."""
    try:
        with open(sidecar_path(mp3_path), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    return words_from_alignment(data)
