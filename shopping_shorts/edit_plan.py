"""여러 소스 대본을 하나의 편집결정목록(EDL)으로 동시 생성(설계 §3-2).

대본 합성(구 script_synth)과 장면 매칭(구 clip_match)을 한 단계로 통합한다 —
대본을 먼저 확정하고 장면을 끼워맞추면 억지 매칭이 생기므로, 모델이 비트마다
'무슨 말을 할지'와 '그 말에 맞는 소스구간(seg_id)'을 동시에 정하게 한다.

환각 방지: 모델은 소스 구간을 seg_id로만 지목하고, 실제 start/end는 코드가
인벤토리에서 되붙인다(_validate_and_ground). 표절은 n-gram 가드로 사후 검출.
build_edit_plan(Gemini 콜)은 Task 4에서 추가.
"""

import json
import sys
import time

from google.genai import types

from pipeline.atoms import key_vault
from shopping_shorts import comment_gen
from shopping_shorts.config import SHORTS_GEMINI_KEYS

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


_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "structure": {"type": "string"},
        "beats": {
            "type": "array", "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"},
                    "narration": {"type": "string"},
                    "target_seconds": {"type": "number"},
                    "primary": {
                        "type": "object",
                        "properties": {"seg_id": {"type": "string"}},
                        "required": ["seg_id"],
                    },
                    "alternates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"seg_id": {"type": "string"}},
                            "required": ["seg_id"],
                        },
                    },
                    "effect": {"type": "string"},
                },
                "required": ["role", "narration", "target_seconds", "primary"],
            },
        },
    },
    "required": ["beats"],
}

_PROMPT = """너는 숏폼 쇼핑 영상 편집 감독이다. 아래 여러 소스 영상의 대본 세그먼트
인벤토리를 보고, 목표 길이 {target_seconds}초짜리 새 영상의 편집안(EDL)을 만들어라.

[소스 세그먼트 인벤토리] — 각 줄이 하나의 구간이다. 대괄호 안이 seg_id다.
{inventory}

{structure_instruction}

규칙(반드시 지켜라):
- 비트(beat) 단위로 순서대로 짜라. 각 비트마다: 그 순간 할 새 나레이션 문장 +
  그 말에 어울리는 소스 구간(primary는 seg_id로 지목) + 대체 후보(alternates,
  seg_id로 {n_alternates}개까지) + 예상 길이(target_seconds) + 효과(effect, 기본 "cut").
- **말을 먼저 다 쓰고 화면을 나중에 맞추지 마라.** "쓸 화면이 있는 말"을 골라라 —
  나레이션과 primary 구간의 화면(scene_desc)이 실제로 어울려야 한다.
- **소스 구간은 반드시 위 인벤토리의 seg_id로만 지목**해라. 없는 seg_id를 지어내지 마라.
- **표절 금지:** 소스 원문 문장·구절을 그대로 베끼지 마라. 후킹 방식·구조·핵심
  셀링포인트만 계승해서 완전히 새 표현으로 써라.
- 비트별 target_seconds 합이 대략 {target_seconds}초가 되게 하고, 각 비트 길이는
  지목한 구간이 감당할 수 있는 범위로 잡아라.
- 출력은 스키마 JSON만."""

_TEMPLATE_INSTR = (
    "[구조: 템플릿 모드] 반드시 다음 역할(role)의 비트를 이 순서대로 채워라: "
    + " → ".join(_REQUIRED_ROLES) + "."
)
_FREE_INSTR = "[구조: 자유 모드] 비트 수와 구조(role 라벨)를 네가 자유롭게 정해라."


def build_edit_plan(source_scripts, target_seconds, structure="template",
                    n_alternates=2, max_retries=4, quota_sleep=8):
    """소스 대본들 → 그라운딩·표절검사된 EDL(설계 §3-2). 전용 풀 소진/실패 시 빈 EDL."""
    empty = {"structure": structure, "beats": [], "plagiarism_flags": []}
    if not SHORTS_GEMINI_KEYS:
        raise RuntimeError("edit_plan: SHORTS_GEMINI_KEY가 설정되지 않았습니다")
    seg_map, inventory = _build_inventory(source_scripts)
    if not seg_map:
        return empty
    prompt = _PROMPT.format(
        target_seconds=target_seconds, inventory=inventory, n_alternates=n_alternates,
        structure_instruction=(_TEMPLATE_INSTR if structure == "template" else _FREE_INSTR),
    )
    source_full_texts = [s.get("full_text", "") for s in source_scripts]

    for attempt in range(max_retries):
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            return empty
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=comment_gen._MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_RESPONSE_SCHEMA,
                ),
            )
            raw = json.loads(resp.text)
            raw.setdefault("structure", structure)
            grounded = _validate_and_ground(raw, seg_map, n_alternates)
            grounded["plagiarism_flags"] = _plagiarism_flags(grounded["beats"], source_full_texts)
            return grounded
        except Exception as e:
            m = str(e)
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                comment_gen._mark_key_exhausted(idx)
                continue
            if key_vault.is_quota_error(e):
                time.sleep(quota_sleep)
                continue
            if attempt < max_retries - 1 and any(c in m for c in ("503", "UNAVAILABLE", "overloaded")):
                time.sleep((attempt + 1) * 5)
                continue
            print(f"edit_plan: 미분류 오류로 빈 EDL 반환 — {e!r}", file=sys.stderr)
            return empty
    return empty
