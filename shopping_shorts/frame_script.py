"""프레임 태깅 추출전환 B1 (2026-07-29) — 순수 조립 로직.

영상 통째 업로드(느림의 정체) 대신: 파이썬이 컷 경계(scene_cut)로 구간을 나누고, 오디오를
Whisper로 워드 타임스탬프 전사(asr_check.transcribe_words)해 구간별 나레이션을 붙인다. 제미니는
프레임 몇 장만 받아 구간별 시각 태그(scene_desc/shot_role/is_key/product_benefits)를 단다.

이 모듈은 **순수 함수만** — 컷·워드·태그를 받아 세그먼트로 조립한다(ffmpeg·Gemini I/O 없음).
그래서 단위테스트가 빠르고, script_extract(accident zone)를 건드리지 않는다. 조립기(I/O 붙는
extract_script_frames)는 이 함수들을 쓴다.
설계: docs/superpowers/specs/2026-07-29-프레임태깅-추출전환-design.md
"""


def segments_from_cuts_and_words(cuts, words):
    """컷 경계(오름차순 타임스탬프)와 워드 타임스탬프 → [{start,end,text}].

    cuts=[t0,t1,...] 이면 구간은 [t0,t1),[t1,t2),... (경계 개수-1개). 경계가 1개 이하면
    구간을 못 만들어 [] (호출부가 기존 경로로 폴백). 워드는 start가 구간 [s,e)에 들면 그
    구간 text에 순서대로 붙인다(경계에 걸친 start==e는 다음 구간으로 — 누락 방지).
    words가 None/빈값이면 모든 구간 text는 빈칸(무자막·키없음, fail-open)."""
    ts = [float(c) for c in (cuts or [])]
    if len(ts) < 2:
        return []
    segs = [{"start": ts[i], "end": ts[i + 1], "text": ""} for i in range(len(ts) - 1)]
    buckets = [[] for _ in segs]
    for w in (words or []):
        try:
            st = float(w["start"])
            word = str(w["word"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not word:
            continue
        for i, seg in enumerate(segs):
            # [start, end) — 단, 마지막 구간은 end 포함(끝 워드 누락 방지)
            last = i == len(segs) - 1
            if seg["start"] <= st < seg["end"] or (last and st >= seg["start"]):
                buckets[i].append(word)
                break
    for seg, words_in in zip(segs, buckets):
        seg["text"] = " ".join(words_in)
    return segs


_TAG_DEFAULTS = {"scene_desc": "", "shot_role": "기타", "is_key": False,
                 "action": None, "has_effect": False, "product_benefits": []}


def merge_frame_tags(segs, tags):
    """세그먼트(start/end/text)에 제미니 프레임 태그를 인덱스로 병합.

    tags[i]가 segs[i]에 붙는다. 태그가 모자라면(길이 불일치) 남는 세그먼트는 기본값
    (fail-open — 크래시·누락 금지). scene_desc·shot_role·is_key·product_benefits만 태그에서
    가져오고 나머지 세그먼트 필드(start/end/text)는 보존한다."""
    out = []
    tags = tags or []
    for i, seg in enumerate(segs):
        tag = tags[i] if i < len(tags) and isinstance(tags[i], dict) else {}
        merged = dict(seg)
        for k, default in _TAG_DEFAULTS.items():
            merged[k] = tag.get(k, default)
        # product_benefits 정규화(str도 리스트로)
        pb = merged.get("product_benefits")
        if isinstance(pb, str):
            merged["product_benefits"] = [pb] if pb.strip() else []
        elif not isinstance(pb, list):
            merged["product_benefits"] = []
        out.append(merged)
    return out


def full_text_of(segs):
    """세그먼트 text들을 발화 순서대로 이어 full_text 생성(대본 재료·표절검사용)."""
    return " ".join(s.get("text", "").strip() for s in (segs or []) if s.get("text", "").strip())
