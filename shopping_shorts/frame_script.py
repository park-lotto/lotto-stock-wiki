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


_EMPTY = {"segments": [], "full_text": "", "product_benefits": []}


def _default_boundaries(video_path):
    """실 컷 경계 리스트 [0, cut1, ..., duration]. detect_cuts(내부 컷)+길이로 조립.
    감지 실패/짧으면 길이만 알면 통구간 1개([0,dur])라도 만든다(호출부 폴백 최소화)."""
    from shopping_shorts import scene_cut, frame_extract
    try:
        dur = float(frame_extract._probe_duration(video_path))
    except Exception:
        dur = 0.0
    if dur <= 0:
        return []
    try:
        cuts = [float(c) for c in scene_cut.detect_cuts(video_path, threshold=0.3)]
    except Exception:
        cuts = []
    bounds = sorted({0.0, dur} | {c for c in cuts if 0.0 < c < dur})
    return bounds


def _gemini_tag_frames(frame_paths, caption, segs):
    """프레임 N장(구간별 1장) → 제미니가 구간별 시각태그 배열 반환.
    영상 통째 대신 이미지 파트만 보낸다(업로드/PROCESSING 급감). 실패 시 [](호출부 fail-open).
    반환: [{scene_desc, shot_role, is_key, product_benefits}, ...] (프레임 순서=구간 순서)."""
    import json
    from shopping_shorts import comment_gen, script_extract
    from shopping_shorts.video_analysis import _MODEL
    try:
        from google.genai import types
    except Exception:
        return []
    key, idx = comment_gen._current_key_and_idx()
    if key is None:
        return []
    # 프레임을 순서대로 image part로. 구간 타이밍·나레이션을 텍스트로 함께 준다.
    seg_lines = "\n".join(
        f"{i+1}번 장면({round(s.get('start',0),1)}~{round(s.get('end',0),1)}초) 나레이션:{s.get('text','') or '(없음)'}"
        for i, s in enumerate(segs))
    prompt = (
        "아래는 한 영상을 장면전환마다 자른 대표 프레임들이다(순서=장면 순서). 각 프레임을 보고 "
        f"장면별 태그를 매겨라. 총 {len(frame_paths)}장.\n{seg_lines}\n\n"
        "각 장면마다: scene_desc(화면에 뭐가 보이나 짧게, 주 대상 정확히), "
        "shot_role(before/사용중/after/완성/문제/기타 중 하나), is_key(제품 기능·효과를 화면으로 "
        "실증하면 true, 도입·인사·CTA면 false), product_benefits(자막 없어도 화면으로 보이는 특장점 "
        "한국어 1~2문장, 없으면 빈 배열). 프레임 순서대로 tags 배열로 출력."
        f"\n캡션(참고):{caption or '(없음)'}")
    parts = [prompt]
    for fp in frame_paths:
        try:
            with open(fp, "rb") as fh:
                parts.append(types.Part.from_bytes(data=fh.read(), mime_type="image/jpeg"))
        except Exception:
            continue
    try:
        resp = comment_gen._client_for_key(key).models.generate_content(
            model=_MODEL, contents=parts,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=_TAGS_SCHEMA))
        return json.loads(resp.text).get("tags", []) or []
    except Exception as e:
        print(f"frame_script._gemini_tag_frames: 실패 — {e!r}", file=__import__('sys').stderr)
        return []


_TAGS_SCHEMA = {
    "type": "object",
    "properties": {"tags": {"type": "array", "items": {"type": "object", "properties": {
        "scene_desc": {"type": "string"},
        "shot_role": {"type": "string", "enum": ["before", "사용중", "after", "완성", "문제", "기타"]},
        "is_key": {"type": "boolean"},
        "product_benefits": {"type": "array", "items": {"type": "string"}},
    }, "required": ["scene_desc", "shot_role"]}}},
    "required": ["tags"],
}


def extract_script_frames(video_path, video_id, caption="", *,
                          get_boundaries=None, extract_frame_at=None,
                          extract_audio=None, transcribe_words=None, tag_frames=None):
    """B1 조립기: 영상 통째 업로드 없이 {segments, full_text, product_benefits} 반환.
    출력 스키마는 script_extract.extract_script와 100% 동일(다운스트림 무변경).
    모든 I/O는 주입 가능(기본은 실제 구현) — 단위테스트가 목킹한다. 컷 못 만들면 빈 결과."""
    import tempfile
    from pathlib import Path
    from shopping_shorts import script_extract
    get_boundaries = get_boundaries or _default_boundaries
    if extract_frame_at is None:
        from shopping_shorts import frame_extract
        extract_frame_at = frame_extract.extract_frame_at
    if extract_audio is None:
        from shopping_shorts import scene_assets
        extract_audio = scene_assets.extract_audio
    if transcribe_words is None:
        from shopping_shorts import asr_check
        transcribe_words = asr_check.transcribe_words
    tag_frames = tag_frames or _gemini_tag_frames

    boundaries = get_boundaries(video_path)
    if len(boundaries or []) < 2:
        return dict(_EMPTY)

    # 오디오 전사(실패·키없음 → None, text 빈칸 fail-open)
    words = None
    try:
        work = Path(tempfile.mkdtemp(prefix="frame_asr_"))
        mp3 = extract_audio(video_path, str(work / "audio.mp3"))
        if mp3:
            words = transcribe_words(mp3)
    except Exception:
        words = None

    segs = segments_from_cuts_and_words(boundaries, words)
    if not segs:
        return dict(_EMPTY)

    # 구간 중앙 프레임 1장씩
    frame_dir = tempfile.mkdtemp(prefix="frame_tag_")
    frame_paths = []
    for s in segs:
        mid = (s["start"] + s["end"]) / 2.0
        try:
            fp = extract_frame_at(video_path, frame_dir, mid)
        except Exception:
            fp = None
        if fp:
            frame_paths.append(fp)

    tags = tag_frames(frame_paths, caption, segs) or []
    merged = merge_frame_tags(segs, tags)
    segments = script_extract._assign_seg_ids(video_id, merged)
    return {
        "segments": segments,
        "full_text": full_text_of(segments),
        "product_benefits": script_extract._collect_benefits(segments),
    }
