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

# 영상 유형별 대본 전략 레지스트리(설계 §2·§3-1) — 유형 추가 = 항목 하나 추가.
VIDEO_TYPES = {
    "recipe_secret": {
        "label": "🍳 비밀비법형",
        "strategy": "이 영상은 레시피/살림팁 '비밀비법형'이다. 핵심 재료·비법을 절대 이름으로 "
                    "밝히지 마라 — '이것', '집에 있는 이거', '한 스푼'처럼 감춰서 궁금하게 "
                    "만들어라. 마지막 CTA 비트는 반드시 '댓글에 [키워드] 남겨주시면 "
                    "알려드릴게요' 형태로 궁금증→댓글을 유도해라.",
    },
    "product_reveal": {
        "label": "🛍️ 상품형",
        "strategy": "이 영상은 제품을 직접 소개하는 '상품형'이다. 제품명·정보를 명확히 "
                    "보여줘라. 마지막 CTA 비트는 '댓글에 [키워드] 남겨주시면 구매링크 "
                    "보내드릴게요' 형태로 구매 전환을 유도해라.",
    },
}
_DEFAULT_TYPE = "product_reveal"

# 한글 1글자 ≈ 1음절이므로 "글자수 ÷ 이 값"이 실제 발화 시간(초)이다.
# 2026-07-17 성우 14명을 서버에서 실합성해 측정한 값(음절÷발화초). 성우별 speed는 이 값에
# 닿도록 역산해 박았다(voice_presets.json). 속도를 다시 튜닝하면 이 상수도 같이 움직여야 한다.
# ⚠️ produce.html의 lenText()(화면 "N자 · 약 N초" 표시)가 이 값을 JS로 못 읽으므로 별도
# 상수(SYLLABLES_PER_SEC)로 나란히 유지한다 — 둘 중 하나만 바꾸면 화면과 계획이 어긋난다.
_SYLLABLES_PER_SEC = 5.7


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
                "action": seg.get("action"),
            }
            _act = seg.get("action")
            _act_s = f" | 행위:{_act}" if _act else ""
            lines.append(
                f"[{sid}] ({length}s) 화면:{seg.get('scene_desc','')} | 말:{seg.get('text','')}{_act_s}"
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
    return {"video_id": seg["video_id"], "seg_id": sid, "start": seg["start"], "end": seg["end"],
            "scene_desc": seg.get("scene_desc", "")}


_FACE_TOKENS = ("얼굴", "정면", "셀카", "자기소개", "말하는 사람", "脸", "人物", "正面", "自拍")


def _is_face_seg(scene_desc):
    """scene_desc에 인물 정면/얼굴 신호가 있으면 True — 대체 카드가 있을 때 후순위로 민다."""
    s = (scene_desc or "").lower()
    return any(t.lower() in s for t in _FACE_TOKENS)


def _dedup_and_fill(flat, need):
    """같은 (video_id,seg_id,start) 중복 제거 후, need 미만이면 가장 긴 세그먼트를
    시간 이등분 서브슬라이스로 분할해 need개까지 채운다. 환각 없음 — start/end는 코드 계산."""
    seen, uniq = set(), []
    for s in flat:
        k = (s.get("video_id", ""), s.get("seg_id", ""), s.get("start", 0.0))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(s)
    # 부족분을 서브슬라이스로 채움 — 가장 긴 것부터 반으로 쪼갠다.
    while len(uniq) < need:
        longest = max(uniq, key=lambda s: s.get("end", 0.0) - s.get("start", 0.0), default=None)
        if longest is None or (longest["end"] - longest["start"]) < 1.0:
            break  # 더 쪼갤 게 없음 — 있는 만큼만
        mid = round((longest["start"] + longest["end"]) / 2, 2)
        half = dict(longest)
        half["seg_id"] = f"{longest['seg_id']}#2"
        half["start"] = mid
        longest["end"] = mid  # 원본은 앞 절반으로 줄임(제자리 수정)
        uniq.append(half)
    # need 미만으로 끝날 수 있다(잔여가 전부 1초 미만이면 위 break) — 호출부(_chronological_respine)가
    # 그 경우를 가드한다. 여기서 truncate는 불필요: while이 len(uniq)>=need에서 멈추므로 넘치지 않는다.
    return uniq


def _chronological_respine(beats):
    """비트의 시각 세그먼트([primary]+alternates)를 소스 시간순으로 재배치한다(2트랙 모델,
    2026-07-19). 나레이션·비트 순서는 그대로 — 화면만 요리 시간순(재료→조리→완성→시식)으로
    흐르게 해 완성↔붓기 핑퐁을 없앤다. 비트당 세그먼트 개수는 보존(길이 커버리지 유지).

    ★꼬리(마지막) 비트는 앵커로 고정한다(② 엔딩 딴 영상 버그, 2026-07-20). 전역정렬은
    (video_id,start)로 소스를 뭉치므로, 재분배 시 마지막 비트엔 항상 '가장 큰 video_id
    소스의 늦은 세그먼트'가 떨어진다 — 그게 완성/히어로 컷이라는 보장이 없고 딴 소스(에어프라이어
    바나나 등)일 수 있어, CTA 나레이션("완성! 댓글")이 엉뚱한 릴 위에 얹혔다. CTA/엔딩 비트는
    모델이 고른 완성/시식 컷을 그대로 두고, 그 앞 body 비트들만 시간순으로 흐르게 한다.

    의미 매칭(문장↔화면)을 일부러 포기한 배치이므로, 오탐 빨간불을 막기 위해 respined
    플래그로 구분한다 — fit은 조작하지 않는다(④ fit 정직화, 2026-07-20). 프런트는 respined
    비트를 중립(초록) 처리하고, fit은 모델이 매긴 원래 값을 그대로 노출한다.
    정렬 키는 (video_id, start): 한 소스는 시간순으로 이어 쓰고, 소스끼리는 묶어서 쓴다.

    ① visual_verb 앵커(2026-07-20): 나레이션이 화면의 구체적 시각행위(찢다·붓다·완성 등)를
    지목하는 비트는 그 화면이 반드시 맞아야 하므로 꼬리처럼 앵커로 고정한다 — 모델이 고른
    원 세그먼트·원 fit 그대로, respined 플래그 없음. 나머지 movable body 비트만 flat 풀에
    모아 시간순 재배치한다. visual_verb 키가 없으면 .get()이 False → movable(기존 계약)."""
    if not beats:
        return beats
    # 꼬리 비트는 respine 대상에서 제외(앵커) — 모델이 고른 화면 그대로.
    body, tail = beats[:-1], beats[-1]
    # visual_verb=True 비트도 앵커. 나머지 movable body만 flat 풀 → dedup → 시간순 재배치.
    movable_idx = [j for j, b in enumerate(body) if not b.get("visual_verb")]
    flat, counts = [], []
    for j in movable_idx:
        segs = [body[j]["primary"]] + list(body[j].get("alternates") or [])
        counts.append(len(segs))
        # 스냅샷 복사: _dedup_and_fill의 서브슬라이스가 제자리 mutation(longest["end"]=mid)하므로
        # 참조로 넣으면 원본 비트의 primary/alternates까지 오염된다(이월 Minor 픽스 1).
        flat.extend([dict(s) for s in segs])
    flat = _dedup_and_fill(flat, need=sum(counts))
    # 정렬: (video_id,start) 우선, 동시각이면 얼굴 세그먼트를 뒤로(대체 있을 때 후순위).
    ordered = sorted(flat, key=lambda s: (s.get("video_id", ""), s.get("start", 0.0),
                                          _is_face_seg(s.get("scene_desc", ""))))
    moved, i = {}, 0
    for j, n in zip(movable_idx, counts):
        chunk = ordered[i:i + n]
        i += n
        if not chunk:
            # fill이 need를 못 채운 극단 케이스(잔여 세그 전부 1초 미만) — 이 비트로 돌아올
            # 세그먼트가 바닥났다. 크래시 대신 원래 화면을 보존한다(아래 루프가 원본 append).
            # 실제로 재배치되지 않았으니 respined 플래그도 달지 않는다.
            continue
        nb = dict(body[j])
        nb["primary"] = chunk[0]
        nb["alternates"] = chunk[1:]
        nb["respined"] = True   # 시간순 스파인 배치 = b-roll by design(빨간불 대상 아님)
        moved[j] = nb           # ④ fit 덮어쓰기 삭제 — 모델 fit 그대로 보존
    # movable은 재배치본, 앵커(visual_verb·빈chunk)는 원본 그대로.
    out = [moved[j] if j in moved else dict(b) for j, b in enumerate(body)]
    # 꼬리: 앵커 — 세그먼트·fit 모두 모델이 고른 그대로(respined 아님).
    out.append(dict(tail))
    return out


def _validate_and_ground(raw_plan, seg_map, n_alternates, respine=True):
    """모델 EDL의 primary/alternates를 grounding. primary 무효 beat는 드롭,
    alternates 무효 항목은 제거하고 n_alternates개까지만.

    respine=True(기본): grounding 후 시각 세그먼트를 소스 시간순으로 재배치(2트랙 모델).
    화면이 요리 순서대로 흐르게 해 완성↔붓기 핑퐁을 없앤다. 나레이션 순서는 불변."""
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
            "fit": int(beat.get("fit") or 0),
            "visual_verb": bool(beat.get("visual_verb", False)),
        })
    if respine:
        beats_out = _chronological_respine(beats_out)
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
                    "fit": {"type": "integer"},
                    "visual_verb": {"type": "boolean"},
                },
                "required": ["role", "narration", "target_seconds", "primary"],
            },
        },
        "affiliate_target": {"type": "string"},
    },
    "required": ["beats"],
}

_PROMPT = """너는 숏폼 쇼핑 영상 편집 감독이다. 아래 여러 소스 영상의 대본 세그먼트
인벤토리를 보고, 목표 길이 {target_seconds}초짜리 새 영상의 편집안(EDL)을 만들어라.

[소스 세그먼트 인벤토리] — 각 줄이 하나의 구간이다. 대괄호 안이 seg_id다.
{inventory}

{structure_instruction}

{type_strategy}

- affiliate_target: 이 영상이 궁극적으로 팔거나 연결할 핵심 제품/재료 하나를 정확한
  이름으로 뽑아라. 비밀비법형이면 나레이션엔 감췄더라도 이 필드엔 감춘 그 재료의
  실제 이름을, 상품형이면 그 제품명을 넣어라.

규칙(반드시 지켜라):
- 비트(beat) 단위로 순서대로 짜라. 각 비트마다: 그 순간 할 새 나레이션 문장 +
  그 말에 어울리는 소스 구간(primary는 seg_id로 지목) + 대체 후보(alternates,
  seg_id로 {n_alternates}개까지) + 예상 길이(target_seconds) + 효과(effect, 기본 "cut").
- **[길이 — 매우 중요] 최종 영상 길이 = 나레이션을 소리 내 읽는 시간이다. 목표는
  {target_seconds}초. 한국어는 초당 약 4~5자로 읽히므로, **전체 나레이션 글자수(공백
  포함)를 약 {char_target}자 내외**로 맞춰라. 이보다 많이 쓰면 자막이 너무 빨리
  지나가서 시청자가 못 읽는다 — {char_target}자를 크게 넘기지 마라. 반대로 너무 짧아도
  안 되니 {char_target}자에 가깝게 채워라. 각 비트에 글자수를 고르게 분배해라(예: 비트가
  5개면 비트당 약 {char_target}÷5자).
- **[두 영상 모두 사용 — 필수] primary 구간을 한 영상에만 몰지 마라. 제공된 소스
  영상이 여러 개면 반드시 그 영상들 모두에서 고르게 구간을 가져와 진짜로 섞어라
  (예: 소스가 2개면 둘 다 최소 한 번씩 이상 써라). 한 영상만 쓰면 믹스가 아니다.**
- **말을 먼저 다 쓰고 화면을 나중에 맞추지 마라.** "쓸 화면이 있는 말"을 골라라 —
  나레이션과 primary 구간의 화면(scene_desc)이 실제로 어울려야 한다.
- **얼굴 클로즈업 배제:** 사람 얼굴이 화면에 크게 나오는 컷(말하는 사람 정면 클로즈업,
  셀카형 인물 샷)은 피하라. 제품·요리·과정·결과물이 보이는 화면을 우선 골라라.
  얼굴만 나오는 구간은 대체 화면이 있으면 쓰지 마라(scene_desc로 판단).
- 화면이 튀지 않게: 같은 소스 안에서는 되도록 시간 순서가 크게 뒤바뀌지 않는,
  자연스럽게 이어지는 구간을 골라라.
- **소스 구간은 반드시 위 인벤토리의 seg_id로만 지목**해라. 없는 seg_id를 지어내지 마라.
- **visual_verb: 이 비트의 나레이션이 화면에서 눈으로 보이는 구체적 동작·상태(찢다·붓다·완성·꺼내다·바르다 등)를
  지목하면 true, 감정·설명·도입부처럼 특정 화면을 요구하지 않으면 false로 표시해라.**
- **표절 금지:** 소스 원문 문장·구절을 그대로 베끼지 마라. 후킹 방식·구조·핵심
  셀링포인트만 계승해서 완전히 새 표현으로 써라.
- 출력은 스키마 JSON만."""

_TEMPLATE_INSTR = (
    "[구조: 템플릿 모드] 반드시 다음 역할(role)의 비트를 이 순서대로 채워라: "
    + " → ".join(_REQUIRED_ROLES) + "."
)
_FREE_INSTR = "[구조: 자유 모드] 비트 수와 구조(role 라벨)를 네가 자유롭게 정해라."

# given_script 모드(영상제작 위저드 2단계) — 나레이션을 새로 쓰지 않고 확정 대본을
# 비트로 쪼개 각 비트에 소스 영상 구간만 매칭한다.
_SCRIPTED_N_ALT = 6   # scripted 모드: 비트당 이어붙일 구간을 넉넉히 받는다(대사 길이 채우기).

_SCRIPTED_PROMPT = """너는 숏폼 쇼핑 영상 편집 감독이다. **나레이션 대본은 이미 확정**돼 있다.
아래 확정 대본을 자연스러운 비트(문장/구절) 단위로 나누고, 각 비트에 어울리는 소스
영상 구간(seg_id)을 골라 편집안(EDL)을 만들어라.

[확정 나레이션 대본] — 이 문장들을 **그대로** 사용해라(새로 쓰거나 바꾸지 마라).
{given_script}

[소스 세그먼트 인벤토리] — 각 줄이 하나의 구간이다. 대괄호 안이 seg_id다.
{inventory}

규칙(반드시 지켜라):
- 확정 대본을 순서대로 비트로 쪼개라. 각 비트의 narration은 **확정 대본의 실제 구절
  그대로**(표현·어미 바꾸지 말 것). 대본 전체가 빠짐없이 비트로 커버되게 해라.
- 각 비트마다 그 대사에 어울리는 소스 구간을, **화면에 이어서 재생할 순서대로** 골라라.
  primary가 가장 잘 맞는 첫 구간, alternates는 그 뒤로 **이어붙일 추가 구간들**(대안이 아니라
  연속 재생용)이다. **비트 대사를 읽는 시간(target_seconds)만큼 화면을 채우도록** 구간 길이 합이
  target_seconds 이상 되게 seg_id를 {n_alternates}개까지 순서대로 담아라. 서로 다른 소스 영상에
  걸쳐도 좋다(관련성 우선). 전부 대사 내용과 화면(scene_desc)이 어울려야 한다.
- **[여러 영상 모두 사용] primary 구간을 한 영상에만 몰지 마라. 소스가 여러 개면 고르게 섞어라.**
- 나레이션과 primary 구간의 화면(scene_desc)이 실제로 어울리게 골라라.
- **얼굴 클로즈업 배제:** 사람 얼굴이 크게 나오는 컷(정면 클로즈업·셀카형)은 피하고
  제품·요리·과정·결과물 화면을 우선 골라라. 얼굴만 나오는 구간은 대체 화면이 있으면 쓰지 마라.
- **소스 구간은 반드시 인벤토리의 seg_id로만 지목**해라. 없는 seg_id 지어내지 마라.
- **fit: 이 비트의 나레이션과 primary 화면이 얼마나 잘 맞는지 1~5로 솔직하게 매겨라
  (5=딱 맞음, 3=무난, 1~2=마땅한 영상이 없어 억지로 붙임). 억지로 붙였으면 낮게 줘라.**
- **visual_verb: 이 비트의 나레이션이 화면에서 눈으로 보이는 구체적 동작·상태(찢다·붓다·완성·꺼내다·바르다 등)를
  지목하면 true, 감정·설명·도입부처럼 특정 화면을 요구하지 않으면 false로 표시해라.**
- affiliate_target: 이 영상이 팔거나 연결할 핵심 제품/재료 하나를 정확한 이름으로.
- 출력은 스키마 JSON만."""


def _vault_call(prompt, schema, max_tries=4):
    """key_vault 캐스케이드 예비키풀로 JSON 생성 호출 → raw dict. 무키/실패면 None.

    build_edit_plan이 comment_gen 전용키(1개, 쉽게 소진) 대신 배치된 예비키를
    쓰도록 하는 공용 경로(2026-07-13)."""
    keys = key_vault.get_live_keys_cascade("general")
    if not keys:
        return None
    for key in keys[:max_tries]:
        try:
            resp = key_vault.get_client_for_key(key).models.generate_content(
                model=comment_gen._MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=schema),
            )
            return json.loads(resp.text)
        except Exception as e:  # noqa: BLE001
            if key_vault.is_daily_exhausted_error(e) or key_vault.is_account_disabled_error(e):
                key_vault.mark_exhausted(key_vault._owner_group(key) or "general", key)
                continue
            if key_vault.is_quota_error(e):
                continue
            print(f"edit_plan._vault_call: {e!r}", file=sys.stderr)
            return None
    return None


_SCENE_FIRST_SCHEMA = {
    "type": "object",
    "properties": {"candidates": {"type": "array", "minItems": 1, "items": {
        "type": "object",
        "properties": {
            "hook": {"type": "string"},
            "story_person": {"type": "string"}, "story_event": {"type": "string"},
            "story_resolution": {"type": "string"}, "cta_line": {"type": "string"},
            "cta_keyword": {"type": "string"},
            "beats": {"type": "array", "minItems": 4, "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"}, "narration": {"type": "string"},
                    "seg_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "fit": {"type": "integer"}, "forced": {"type": "boolean"}},
                "required": ["role", "narration", "seg_ids", "fit"]}}},
        "required": ["hook", "beats"]}}},
    "required": ["candidates"],
}


def _scene_first_candidates(inventory_text, reference_text, target_seconds, n=3, call=_vault_call):
    """스토리 헌장 + 장면 팔레트 + 레퍼 구조 → 후보 n개. 각 비트는 seg_ids(2~4 다중컷)로
    장면을 지목한다. 실패 시 []. 헌장이 품질을 담당하므로 별도 검증루프 없음(1콜)."""
    from shopping_shorts import script_generate  # 지연 import(순환 방지)
    char_target = int(target_seconds * _SYLLABLES_PER_SEC)
    prompt = (
        "너는 한국 쇼핑 숏폼(살림·요리) 대본 작가다. 아래 '스토리 헌장'을 반드시 지켜 "
        f"탄탄한 대본 후보 {n}개를 만들어라. 단, 우리가 가진 장면으로만 말할 수 있게 쓰고, "
        "각 비트(문장)에 그 말과 어울리는 장면 seg_id를 2~4개 시간순으로 붙여라.\n\n"
        "[레퍼런스 — 훅·전개·설득구조만 계승(표절 금지), 다국어면 한국어로]\n"
        f"{(reference_text or '')[:1500]}\n\n"
        "[우리 장면 팔레트 — 이 seg_id 화면만 쓸 수 있다]\n"
        f"{inventory_text}\n\n"
        + script_generate._STORY_RULES_CORE + "\n" + script_generate._STORY_DECLARE + "\n"
        "- ★위 헌장(인과사슬·훅 한방·CTA 미끼·비법 킥 감추기)을 반드시 지켜라 — 장면에 맞추느라 "
        "스토리가 밋밋해지면 실패다. 스토리가 왕, 장면은 그 스토리를 보여줄 그림이다.\n"
        f"- 전체 나레이션 글자수 합은 약 {char_target}자 내외. 각 비트: role·narration(구어체)·"
        "seg_ids(2~4)·fit(1~5)·forced(그 장면이 이 말과 안 맞는데 억지로 붙였으면 true).\n"
        "- 화면에 없는 걸 말하지 마라. 같은 seg_id를 여러 비트에서 재사용 금지.\n"
        "출력은 스키마 JSON만.")
    raw = call(prompt, _SCENE_FIRST_SCHEMA)
    if not raw or not isinstance(raw, dict):
        return []
    return raw.get("candidates", []) or []


def _ground_candidate(cand, seg_map, structure="free"):
    """후보 비트(narration + seg_ids 다중컷)를 build_edit_plan 반환형 EDL로 grounding.
    seg_ids[0]=primary, 나머지=alternates(연속재생). start/end/scene_desc는 코드가 되붙인다.
    primary 무효 비트는 드롭. 유효 비트 0개면 None."""
    beats_out = []
    for beat in cand.get("beats", []):
        segs = beat.get("seg_ids") or []
        primary = _ground_ref({"seg_id": segs[0]}, seg_map) if segs else None
        if primary is None:
            continue
        alts, seen = [], {primary["seg_id"]}
        for sid in segs[1:]:
            g = _ground_ref({"seg_id": sid}, seg_map)
            if g and g["seg_id"] not in seen:
                alts.append(g)
                seen.add(g["seg_id"])
        narration = beat.get("narration", "")
        beats_out.append({
            "beat_idx": len(beats_out), "role": beat.get("role", ""),
            "narration": narration,
            "target_seconds": round(max(1.5, len(narration.strip()) / _SYLLABLES_PER_SEC), 1),
            "primary": primary, "alternates": alts, "effect": "cut",
            "fit": int(beat.get("fit") or 0), "forced": bool(beat.get("forced", False)),
        })
    if not beats_out:
        return None
    return {"structure": structure, "beats": beats_out}


def _score_candidate(plan):
    """후보 추천 점수(0~1): 매칭 fit·억지없음·장면다양성. 빈 beats면 0.0."""
    beats = plan.get("beats") or []
    if not beats:
        return 0.0
    avg_fit = sum(int(b.get("fit") or 0) for b in beats) / len(beats) / 5.0
    forced_ratio = sum(1 for b in beats if b.get("forced")) / len(beats)
    seg_ids = []
    for b in beats:
        seg_ids.append((b.get("primary") or {}).get("seg_id"))
        seg_ids += [(a or {}).get("seg_id") for a in (b.get("alternates") or [])]
    seg_ids = [s for s in seg_ids if s]
    diversity = (len(set(seg_ids)) / len(seg_ids)) if seg_ids else 0.0
    return round(0.5 * avg_fit + 0.3 * (1 - forced_ratio) + 0.2 * diversity, 3)


_CONFORM_SCHEMA = {
    "type": "object",
    "properties": {"narration": {"type": "string"}},
    "required": ["narration"],
}

_CONFORM_PROMPT = """너는 숏폼 나레이션 카피 에디터다. 아래 문장을 **약 {char_target}자(공백 제외)**로
압축해라. 발화 시간을 영상 클립 길이에 맞추는 작업이다.

규칙:
- 뜻·핵심 정보·역할(훅/전개/CTA)·말투를 유지한다. 정보를 새로 지어내지 않는다.
- 압축만 한다 — 군더더기·중복·부사를 덜어낸다. 문장을 재창작하지 않는다.
- 한 문장 또는 자연스러운 짧은 문장들로.

[원문]
{narration}

스키마 JSON으로 narration 하나만 출력해라."""


def conform_narration(narration, target_seconds, max_tries=4):
    """문장을 target_seconds 발화 길이에 맞게 압축(콘폼) — 성공 시 새 문장, 실패 시 None.

    싱크 콘폼루프(2026-07-20 설계)의 T2. 영상 예산(클립 실길이×슬로모 상한)을 초과한
    비트의 나레이션만 표면 재단한다 — 서사는 대본이, 시간은 영상이 주인이다.
    게이트: 결과의 추정 발화초(공백제외 글자수÷_SYLLABLES_PER_SEC)가 목표의 0.8~1.2배
    아니면 None(뜻 훼손 없는 안전 폴백 = 호출부가 원문 유지 + freeze 잔존 플래그)."""
    narration = (narration or "").strip()
    if not narration or target_seconds <= 0:
        return None
    char_target = max(6, int(round(target_seconds * _SYLLABLES_PER_SEC)))
    raw = _vault_call(
        _CONFORM_PROMPT.format(char_target=char_target, narration=narration[:1000]),
        _CONFORM_SCHEMA, max_tries=max_tries)
    if not raw:
        return None
    new = (raw.get("narration") or "").strip()
    if not new:
        return None
    est = len("".join(new.split())) / _SYLLABLES_PER_SEC
    if not (0.8 * target_seconds <= est <= 1.2 * target_seconds):
        return None
    return new


_TYPE_SCHEMA = {
    "type": "object",
    "properties": {"video_type": {"type": "string"}},
    "required": ["video_type"],
}

_TYPE_PROMPT = """너는 숏폼 쇼핑 영상 편집 감독이다. 아래 소스 영상 대본들을 보고
이 영상들에 가장 맞는 영상 유형을 하나만 골라라.

[유형 목록]
{type_desc}

[소스 대본들]
{scripts}

가장 맞는 유형의 key 하나만 정확히 골라 스키마 JSON으로 출력해라."""


def detect_video_type(source_scripts, max_retries=3, quota_sleep=8):
    """소스 대본들(주로 full_text) → VIDEO_TYPES 중 하나의 key(설계 §3-1).

    Gemini(comment_gen 전용 키풀)로 분류한다. 전용 풀 소진·예외·무효 응답 시
    파이프라인이 끊기지 않도록 항상 _DEFAULT_TYPE을 반환한다."""
    if not SHORTS_GEMINI_KEYS:
        return _DEFAULT_TYPE
    full_texts = [s.get("full_text", "") for s in source_scripts if s.get("full_text")]
    if not full_texts:
        return _DEFAULT_TYPE
    type_desc = "\n".join(f"- {k}: {v['label']} — {v['strategy']}" for k, v in VIDEO_TYPES.items())
    prompt = _TYPE_PROMPT.format(type_desc=type_desc, scripts="\n---\n".join(full_texts))

    for attempt in range(max_retries):
        key, idx = comment_gen._current_key_and_idx()
        if key is None:
            return _DEFAULT_TYPE
        try:
            resp = comment_gen._client_for_key(key).models.generate_content(
                model=comment_gen._MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_TYPE_SCHEMA,
                ),
            )
            raw = json.loads(resp.text)
            vt = raw.get("video_type")
            return vt if vt in VIDEO_TYPES else _DEFAULT_TYPE
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
            print(f"edit_plan.detect_video_type: 미분류 오류로 기본값 반환 — {e!r}", file=sys.stderr)
            return _DEFAULT_TYPE
    return _DEFAULT_TYPE


_RECONCILE_SCHEMA = {
    "type": "object",
    "properties": {"rewrites": {"type": "array", "items": {
        "type": "object",
        "properties": {"beat_idx": {"type": "integer"}, "narration": {"type": "string"}},
        "required": ["beat_idx", "narration"]}}},
    "required": ["rewrites"],
}


def _bb_rewrite(beats, call=_vault_call):
    """핑퐁 재작성 콜백(backbone.ping_pong_reconcile용) — 화면과 못 맞춘 비트의 나레이션을
    화면(scene_desc)에 맞게 1회 수정 → {beat_idx: 새나레이션}. 실패/무대상이면 {}."""
    if not beats:
        return {}
    lines = "\n".join(
        f"[{b['beat_idx']}] 화면:{(b.get('primary') or {}).get('scene_desc','')} | 현재대사:{b.get('narration','')}"
        for b in beats)
    prompt = (
        "아래 비트들은 대사와 화면이 어긋난다. 각 대사를 **뜻과 정보는 유지**하되 화면(scene_desc)에 "
        "어울리도록 표현만 자연스럽게 고쳐라. 화면에 없는 사실을 지어내지 마라.\n"
        f"{lines}\n출력은 rewrites 배열의 JSON만.")
    raw = call(prompt, _RECONCILE_SCHEMA)
    if not raw or not isinstance(raw, dict):
        return {}
    return {int(r["beat_idx"]): r["narration"]
            for r in raw.get("rewrites", []) if r.get("narration")}


def _bb_trim(beats, call=_vault_call):
    """핑퐁 길이 트림 콜백 — 화면보다 긴 대사를 뜻 유지하며 target_chars 이내로 줄인다
    → {beat_idx: 줄인 나레이션}. 대사가 다음 장면으로 넘어가는 것 방지."""
    if not beats:
        return {}
    lines = "\n".join(
        f"[{b['beat_idx']}] {b.get('target_chars', 0)}자 이내: {b.get('narration', '')}"
        for b in beats)
    prompt = (
        "아래 대사들은 화면보다 길어 다음 장면으로 넘어간다. 각 대사를 **뜻·정보·말투는 유지**하되 "
        "지정한 글자수 이내로 자연스럽게 줄여라(끊긴 느낌 없이 완결). 화면에 없는 사실 지어내지 마라.\n"
        f"{lines}\n출력은 rewrites 배열의 JSON만.")
    raw = call(prompt, _RECONCILE_SCHEMA)
    if not raw or not isinstance(raw, dict):
        return {}
    return {int(r["beat_idx"]): r["narration"]
            for r in raw.get("rewrites", []) if r.get("narration")}


def _reconcile_weak_beats(beats, call=_vault_call):
    """앵커(respined 아님)이면서 fit<=3인 비트의 나레이션만 화면(scene_desc)에 맞게
    1회 Gemini 호출로 미세수정. 대상 0개면 호출 없이 그대로. 실패 시 원문 유지(fail-open)."""
    weak = [b for b in beats if not b.get("respined") and 0 < int(b.get("fit") or 0) <= 3]
    if not weak:
        return beats
    lines = "\n".join(
        f"[{b['beat_idx']}] 화면:{(b.get('primary') or {}).get('scene_desc','')} | 현재대사:{b.get('narration','')}"
        for b in weak)
    prompt = (
        "아래 비트들은 대사와 화면이 어긋난다. 각 비트의 대사를 **뜻과 정보는 유지**하되 "
        "화면(scene_desc)에 어울리도록 표현만 자연스럽게 고쳐라. 화면에 없는 사실을 지어내지 마라.\n"
        f"{lines}\n출력은 rewrites 배열의 JSON만.")
    raw = call(prompt, _RECONCILE_SCHEMA)
    if not raw or not isinstance(raw, dict):
        return beats
    fixes = {int(r["beat_idx"]): r["narration"]
             for r in raw.get("rewrites", []) if r.get("narration")}
    out = []
    for b in beats:
        nb = dict(b)
        if b["beat_idx"] in fixes:
            nb["narration"] = fixes[b["beat_idx"]]
        out.append(nb)
    return out


def build_edit_plan(source_scripts, target_seconds, structure="template", video_type=None,
                    n_alternates=2, max_retries=4, quota_sleep=8, given_script=None):
    """소스 대본들 → 그라운딩·표절검사된 EDL(설계 §3-2). 실패 시 빈 EDL.

    video_type이 None이면 detect_video_type()으로 자동 판별한다(설계 §3-1).
    given_script이 주어지면(영상제작 2단계) 나레이션을 새로 쓰지 않고 그 확정 대본을
    비트로 쪼개 각 비트에 소스 영상 구간만 매칭한다.
    키는 key_vault 캐스케이드 예비키풀을 쓴다(comment_gen 전용키 소진 회피)."""
    seg_map, inventory = _build_inventory(source_scripts)
    if not seg_map:
        return {"structure": structure, "beats": [], "plagiarism_flags": [],
                "detected_type": video_type or _DEFAULT_TYPE, "affiliate_target": ""}

    scripted = bool(given_script and given_script.strip())
    if scripted:
        video_type = video_type if video_type in VIDEO_TYPES else _DEFAULT_TYPE
        n_alternates = _SCRIPTED_N_ALT
        prompt = _SCRIPTED_PROMPT.format(
            given_script=given_script.strip()[:4000], inventory=inventory, n_alternates=n_alternates)
    else:
        if video_type is None:
            video_type = detect_video_type(source_scripts)
        if video_type not in VIDEO_TYPES:
            video_type = _DEFAULT_TYPE
        prompt = _PROMPT.format(
            target_seconds=target_seconds, inventory=inventory, n_alternates=n_alternates,
            char_target=int(target_seconds * _SYLLABLES_PER_SEC),
            structure_instruction=(_TEMPLATE_INSTR if structure == "template" else _FREE_INSTR),
            type_strategy=VIDEO_TYPES[video_type]["strategy"],
        )

    empty = {"structure": structure, "beats": [], "plagiarism_flags": [],
             "detected_type": video_type, "affiliate_target": ""}
    raw = _vault_call(prompt, _RESPONSE_SCHEMA, max_tries=max_retries)
    if raw is None:
        return empty
    raw.setdefault("structure", structure)
    grounded = _validate_and_ground(raw, seg_map, n_alternates)
    grounded["beats"] = _reconcile_weak_beats(grounded["beats"])
    # 각 비트 target_seconds는 나레이션 글자수 기준으로 재계산(실제 렌더 길이 =
    # 나레이션 읽는 시간 ≈ 글자수÷_SYLLABLES_PER_SEC초). UI 표시 초와 실제 길이가 어긋나지 않게.
    for _b in grounded["beats"]:
        _n = len((_b.get("narration") or "").strip())
        _b["target_seconds"] = round(max(1.5, _n / _SYLLABLES_PER_SEC), 1)
    grounded["structure"] = structure
    grounded["detected_type"] = video_type
    grounded["affiliate_target"] = raw.get("affiliate_target", "")
    # given_script 모드에선 나레이션이 사용자 확정 대본이므로 소스원문 표절검사 생략.
    grounded["plagiarism_flags"] = ([] if scripted
                                    else _plagiarism_flags(grounded["beats"],
                                                           [s.get("full_text", "") for s in source_scripts]))
    return grounded


def build_scene_first_plan(source_scripts, reference_text, target_seconds,
                           n_candidates=3, video_type=None, call=None, ping_pong=False):
    """장면 우선 대본 모드: 팔레트+헌장으로 후보 n개 생성 → 각 EDL grounding·채점 →
    최고 score에 recommended=True. 각 candidate.plan은 build_edit_plan 반환형(하류 렌더 호환).
    후보 0개면 candidates=[](호출부가 기존 build_edit_plan로 폴백).

    ping_pong=True(opt-in, 기본 off로 회귀0): grounding 후 backbone 핑퐁으로 비트별
    대본↔장면을 왕복 조정(행위 불일치=fit 거짓말 잡기 → 같은 행위 클립 스왑 or 나레이션 재작성).
    """
    seg_map, inventory = _build_inventory(source_scripts)
    detected = video_type or (detect_video_type(source_scripts) if source_scripts else _DEFAULT_TYPE)
    if not seg_map:
        return {"candidates": [], "detected_type": detected}
    _call = call or _vault_call
    raws = _scene_first_candidates(inventory, reference_text, target_seconds, n=n_candidates, call=_call)
    src_texts = [s.get("full_text", "") for s in source_scripts]
    cands = []
    for r in raws:
        plan = _ground_candidate(r, seg_map)
        if plan is None:
            continue
        if ping_pong:
            from shopping_shorts import backbone
            # 1) 행위 매칭(화면-대사 어긋남 + 길이) 2) 백본 순서 고정(과정순서)
            plan["beats"] = backbone.ping_pong_reconcile(
                plan["beats"], source_scripts,
                rewrite_call=lambda bs: _bb_rewrite(bs, _call),
                trim_call=lambda bs: _bb_trim(bs, _call))
            bb = backbone.pick_backbone(source_scripts)
            if bb:
                plan["beats"] = backbone.order_by_backbone(plan["beats"], bb)
        plan["detected_type"] = detected
        plan["affiliate_target"] = r.get("story_event", "") or ""
        plan["plagiarism_flags"] = _plagiarism_flags(plan["beats"], src_texts)
        story = {k: r.get(k, "") for k in
                 ("hook", "story_person", "story_event", "story_resolution", "cta_line", "cta_keyword")}
        cands.append({"plan": plan, "story": story, "score": _score_candidate(plan), "recommended": False})
    if cands:
        best = max(range(len(cands)), key=lambda i: cands[i]["score"])
        cands[best]["recommended"] = True
    return {"candidates": cands, "detected_type": detected}
