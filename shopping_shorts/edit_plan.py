"""여러 소스 대본을 하나의 편집결정목록(EDL)으로 동시 생성(설계 §3-2).

대본 합성(구 script_synth)과 장면 매칭(구 clip_match)을 한 단계로 통합한다 —
대본을 먼저 확정하고 장면을 끼워맞추면 억지 매칭이 생기므로, 모델이 비트마다
'무슨 말을 할지'와 '그 말에 맞는 소스구간(seg_id)'을 동시에 정하게 한다.

환각 방지: 모델은 소스 구간을 seg_id로만 지목하고, 실제 start/end는 코드가
인벤토리에서 되붙인다(_validate_and_ground). 표절은 n-gram 가드로 사후 검출.
build_edit_plan(Gemini 콜)은 Task 4에서 추가.
"""

_REQUIRED_ROLES = ["훅", "페인포인트", "반전", "실용", "CTA"]


def _build_inventory(source_scripts):
    """소스 대본들 → (seg_map, prompt_block).

    seg_map: {seg_id: {video_id, seg_id, start, end, text, scene_desc}}
    prompt_block: 모델 프롬프트에 넣을 세그먼트 인벤토리 텍스트(seg_id로만 지목하게)."""
    seg_map = {}
    lines = []
    for script in source_scripts:
        vid = script.get("video_id", "")
        for seg in script.get("segments", []):
            sid = seg["seg_id"]
            length = round(seg["end"] - seg["start"], 2)
            seg_map[sid] = {
                "video_id": vid, "seg_id": sid,
                "start": seg["start"], "end": seg["end"],
                "text": seg.get("text", ""), "scene_desc": seg.get("scene_desc", ""),
            }
            lines.append(
                f"[{sid}] ({length}s) 화면:{seg.get('scene_desc','')} | 말:{seg.get('text','')}"
            )
    return seg_map, "\n".join(lines)


def _ground_ref(ref, seg_map):
    """모델이 준 구간 참조 → 인벤토리 실제 타임코드로 되붙인 {video_id,seg_id,start,end}.
    seg_id가 인벤토리에 없으면 None(모델 환각 제거)."""
    if not ref:
        return None
    sid = ref.get("seg_id")
    seg = seg_map.get(sid)
    if not seg:
        return None
    return {"video_id": seg["video_id"], "seg_id": sid, "start": seg["start"], "end": seg["end"]}


def _validate_and_ground(raw_plan, seg_map, n_alternates):
    """모델 EDL의 primary/alternates를 grounding. primary 무효 beat는 드롭,
    alternates 무효 항목은 제거하고 n_alternates개까지만."""
    beats_out = []
    for beat in raw_plan.get("beats", []):
        primary = _ground_ref(beat.get("primary"), seg_map)
        if primary is None:
            continue  # 지목 구간이 실재하지 않으면 이 비트 폐기
        alts = []
        for a in beat.get("alternates", []) or []:
            g = _ground_ref(a, seg_map)
            if g and g["seg_id"] != primary["seg_id"] and g not in alts:
                alts.append(g)
            if len(alts) >= n_alternates:
                break
        beats_out.append({
            "beat_idx": len(beats_out),
            "role": beat.get("role", ""),
            "narration": beat.get("narration", ""),
            "target_seconds": float(beat.get("target_seconds") or 0.0),
            "primary": primary,
            "alternates": alts,
            "effect": beat.get("effect", "cut"),
        })
    return {"structure": raw_plan.get("structure", ""), "beats": beats_out}


def _char_ngrams(text, n):
    t = "".join((text or "").split())
    return {t[i:i + n] for i in range(len(t) - n + 1)} if len(t) >= n else {t} if t else set()


def _ngram_overlap(a, b, n=6):
    """문자 n-gram 자카드 유사도(0~1)."""
    A, B = _char_ngrams(a, n), _char_ngrams(b, n)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def _plagiarism_flags(beats, source_full_texts, threshold=0.5, n=6):
    """각 beat narration이 소스 원문과 n-gram 겹침이 threshold 초과면 flag."""
    flags = []
    for beat in beats:
        narration = beat.get("narration", "")
        # 각 소스별로 비교해서 최대 겹침 계산
        max_overlap = 0.0
        for source_text in (source_full_texts or []):
            ov = _ngram_overlap(narration, source_text, n)
            max_overlap = max(max_overlap, ov)
        if max_overlap > threshold:
            flags.append({"beat_idx": beat["beat_idx"], "max_overlap": round(max_overlap, 3)})
    return flags
