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


def _seg_benefits(seg):
    """세그먼트의 product_benefits → 문장 리스트(fail-open []). list/str 모두 허용.
    무자막 소스(text 빈칸)에서 대본이 쓸 수 있는 유일한 언어 재료라 여기서 흘리면 안 된다."""
    raw = (seg or {}).get("product_benefits")
    if not raw:
        return []
    if isinstance(raw, str):
        raw = [raw]
    return [t.strip() for t in raw if isinstance(t, str) and t.strip()]


def _build_inventory(source_scripts):
    """소스 대본들 → (seg_map, prompt_block).

    seg_map: {seg_id: {video_id, seg_id, start, end, text, scene_desc}}
    prompt_block: 모델 프롬프트에 넣을 세그먼트 인벤토리 텍스트(seg_id로만 지목하게)."""
    seg_map = {}
    lines = []
    for script in source_scripts:
        vid = script.get("video_id", "")
        segs = script.get("segments", [])
        # 첫·마지막 세그먼트 제외(CTA·썸네일 박제 차단) — 3개 이상일 때만(2개↓면 삭제 안 함).
        usable = segs[1:-1] if len(segs) >= 3 else segs
        for seg in usable:
            sid = seg["seg_id"]
            length = round(seg["end"] - seg["start"], 2)
            seg_map[sid] = {
                "video_id": vid, "seg_id": sid,
                "start": seg["start"], "end": seg["end"],
                "text": seg.get("text", ""), "scene_desc": seg.get("scene_desc", ""),
                "action": seg.get("action"),
                "is_key": bool(seg.get("is_key")),
                "shot_role": seg.get("shot_role") or "기타",
                "product_benefits": _seg_benefits(seg),
            }
            _act = seg.get("action")
            _act_s = f" | 행위:{_act}" if _act else ""
            # 무자막 소스는 '말:'이 빈칸이라 이 라인만 보면 대본이 특장점을 녹일 재료가 없다.
            # 화면→특장점 문장을 라인에 실어 라이브 scene_first 경로도 쓰게 한다(2026-07-26).
            _ben = _seg_benefits(seg)
            _ben_s = f" | 특장점:{' / '.join(_ben[:2])}" if _ben else ""
            lines.append(
                f"[{sid}] ({length}s) 화면:{seg.get('scene_desc','')} | 말:{seg.get('text','')}"
                f"{_act_s}{_ben_s}"
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
            "scene_desc": seg.get("scene_desc", ""),
            # is_key(피처데모 앵커)·shot_role(조리/완성 결)을 grounded primary/alternate에 실어
            # 나른다 — scene_first 주경로의 _apply_anchor_grain(앵커 dedup·레시피 grain)이 이 값을
            # 읽는다. seg_map(_build_inventory)이 이미 보존하므로 여기서 그대로 통과시킨다.
            "is_key": bool(seg.get("is_key")),
            "shot_role": seg.get("shot_role") or "기타"}


_FACE_TOKENS = ("얼굴", "정면", "셀카", "자기소개", "말하는 사람", "脸", "人物", "正面", "自拍")


def _is_face_seg(scene_desc):
    """scene_desc에 인물 정면/얼굴 신호가 있으면 True — 대체 카드가 있을 때 후순위로 민다."""
    s = (scene_desc or "").lower()
    return any(t.lower() in s for t in _FACE_TOKENS)


def _claim_key(scene_desc):
    """장점 요지 근사 키 — scene_desc의 2글자 이상 토큰 정렬 집합.
    같은 장점을 다른 말로 쓴 컷(넓어 그릇 가득 / 넓어 접시 가득)을 근접시키기 위한 근사."""
    import re
    toks = [t for t in re.split(r"[\s,·]+", (scene_desc or "")) if len(t) >= 2]
    return tuple(sorted(set(toks)))


def _dedup_anchors(anchors, top_n=4):
    """is_key 앵커를 장점(scene_desc 요지)별로 묶어 중복 제거, 강한 순 상위 top_n개.
    같은 장점은 첫 등장(선명 가정)만 남긴다. 순수함수."""
    seen_tokens = []   # 이미 채택한 장점들의 토큰 집합
    out = []
    for a in anchors:
        key = set(_claim_key(a.get("scene_desc", "")))
        # 기존 채택 장점과 토큰이 과반 겹치면 같은 장점으로 보고 스킵.
        dup = any(key and len(key & prev) / max(1, len(key)) >= 0.5 for prev in seen_tokens)
        if dup:
            continue
        seen_tokens.append(key)
        out.append(a)
        if len(out) >= top_n:
            break
    return out


def _apply_anchor_grain(beats, is_recipe=False):
    """scene_first 주경로(build_scene_first_plan→_ground_candidate)용 앵커 dedup + 레시피 grain.
    순수함수 — 입력 비트를 제자리 변형하지 않고 새 리스트를 반환한다.

    이 경로는 _chronological_respine(레거시/폴백)을 안 쓴다 — 그래서 is_key 앵커 중복 제거와
    레시피 완성-후치(grain)가 라이브에서 발동 안 됐다(2026-07-26 Task8, 다크피처 배선).

    ① 앵커 dedup (is_recipe와 무관, 항상): primary.is_key인 비트를 모아 _dedup_anchors로
       장점(scene_desc 요지)별 상위 top_n만 채택한다. 채택 안 된 중복 앵커 비트는 **드롭하지
       않고**(나레이션 보존), 대체(alternate)가 있으면 첫 대체를 primary로 승격해 같은 장점샷이
       두 번 primary로 안 뜨게 한다. 대체가 없으면 그대로 둔다.
    ② 레시피 grain (is_recipe=True일 때만): movable 비트(첫·마지막 제외) 중 shot_role=="완성"을
       비-완성 뒤로 안정정렬한다(완성이 조리 앞에 안 낀다). 첫/마지막 비트는 앵커로 고정.
       ★ping_pong일 땐 백본이 순서를 소유하므로 호출부가 is_recipe=False로 넘겨 grain은 끈다
       (dedup은 순서를 안 바꾸므로 항상 돌아도 안전) — build_scene_first_plan 참조.
    """
    if not beats or len(beats) < 2:
        return [dict(b) for b in beats]
    # ── ① 앵커 dedup (항상) ──────────────────────────────────────────────
    anchor_beats = [b for b in beats if (b.get("primary") or {}).get("is_key")]
    kept_ids = {(a.get("primary") or {}).get("seg_id")
                for a in _dedup_anchors([b["primary"] for b in anchor_beats], top_n=4)}
    out = []
    for b in beats:
        nb = dict(b)
        p = nb.get("primary") or {}
        if p.get("is_key") and p.get("seg_id") not in kept_ids:
            alts = list(nb.get("alternates") or [])
            if alts:                       # 중복 앵커 → 첫 대체를 primary로 승격(비트 유지)
                nb["primary"] = alts[0]
                nb["alternates"] = alts[1:]
        out.append(nb)
    # ── ② 레시피 grain (is_recipe일 때만, movable에 한해) ─────────────────
    if is_recipe and len(out) >= 3:
        head, body, tail = out[0], out[1:-1], out[-1]
        # 안정정렬: 완성(1)을 비-완성(0) 뒤로. 파이썬 sorted는 stable이라 나머지 상대순서 보존.
        body = sorted(body, key=lambda b: 1 if (b.get("primary") or {}).get("shot_role") == "완성" else 0)
        out = [head] + body + [tail]
    # beat_idx가 있으면 재부여(순서 이동 반영).
    for i, b in enumerate(out):
        if "beat_idx" in b:
            b["beat_idx"] = i
    return out


def _seg_key(s):
    """세그먼트 dedup 키 (video_id, seg_id, start)."""
    return (s.get("video_id", ""), s.get("seg_id", ""), s.get("start", 0.0))


def _dedup_and_fill(flat, need, reserved=None):
    """같은 (video_id,seg_id,start) 중복 제거 후, need 미만이면 가장 긴 세그먼트를
    시간 이등분 서브슬라이스로 분할해 need개까지 채운다. 환각 없음 — start/end는 코드 계산.

    reserved: 앵커(머리·꼬리·visual_verb)가 이미 쓰는 seg 키 집합. 여기 든 seg는 movable
    재배치에서 배제한다 — 머리 앵커가 쓴 화면을 그 다음 비트가 또 물어 2연속 중복이 뜨는 걸
    막는다(2026-07-26: 머리 앵커 도입이 이 방어를 뚫던 회귀 수정). 기본 None → 기존 동작."""
    reserved = set(reserved or ())
    seen, uniq = set(), []
    for s in flat:
        k = _seg_key(s)
        if k in seen:
            continue
        seen.add(k)
        if k in reserved:
            # 앵커가 이미 쓰는 화면 — primary로 그대로 쓰면 2연속 중복이 뜬다. 버리지 말고
            # 뒤쪽 절반으로 잘라(앵커는 앞쪽) 씨앗으로 남긴다. 너무 짧으면(<1초) 못 쪼개니 스킵.
            if (s.get("end", 0.0) - s.get("start", 0.0)) >= 1.0:
                mid = round((s["start"] + s["end"]) / 2, 2)
                s = dict(s, seg_id=f"{s['seg_id']}#2", start=mid)
                seen.add(_seg_key(s))
            else:
                continue
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


def _chronological_respine(beats, is_recipe=False):
    """비트의 시각 세그먼트([primary]+alternates)를 소스 시간순으로 재배치한다(2트랙 모델,
    2026-07-19). 나레이션·비트 순서는 그대로 — 화면만 요리 시간순(재료→조리→완성→시식)으로
    흐르게 해 완성↔붓기 핑퐁을 없앤다. 비트당 세그먼트 개수는 보존(길이 커버리지 유지).

    ★머리(첫/훅) 비트도 앵커로 고정한다(2026-07-25) — 모델이 훅에 고른 '최고 장면'이
    시간순 재배치에 안 밀리게. 단 비트가 3개 미만이면 머리·꼬리를 둘 다 빼면 body가 비므로
    짧을 땐 꼬리만 고정(기존 동작).
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
    # ★훅(첫 비트)도 앵커: 모델이 훅에 고른 '최고 장면'이 시간순 재배치에 안 밀리게 고정.
    if len(beats) < 3:
        # 머리·꼬리를 둘 다 앵커로 빼면 body가 빌 수 있어, 짧으면 꼬리만 고정(기존 동작).
        head, body, tail = None, beats[:-1], beats[-1]
    else:
        head, body, tail = beats[0], beats[1:-1], beats[-1]
    # visual_verb=True 비트도 앵커. 나머지 movable body만 flat 풀 → dedup → 시간순 재배치.
    movable_idx = [j for j, b in enumerate(body) if not b.get("visual_verb")]
    anchor_idx = [j for j, b in enumerate(body) if b.get("visual_verb")]
    # 앵커(머리·꼬리·visual_verb)가 이미 쓰는 seg는 movable 재배치에서 배제 — 앵커 화면을
    # 그 다음 비트가 또 물어 같은 장면 2연속으로 뜨는 걸 막는다(머리 앵커 도입 회귀 수정).
    reserved = set()
    for b in ([head, tail] + [body[j] for j in anchor_idx]):
        if not b:
            continue
        for s in [b.get("primary")] + list(b.get("alternates") or []):
            if s:
                reserved.add(_seg_key(s))
    flat, counts = [], []
    for j in movable_idx:
        segs = [body[j]["primary"]] + list(body[j].get("alternates") or [])
        counts.append(len(segs))
        # 스냅샷 복사: _dedup_and_fill의 서브슬라이스가 제자리 mutation(longest["end"]=mid)하므로
        # 참조로 넣으면 원본 비트의 primary/alternates까지 오염된다(이월 Minor 픽스 1).
        flat.extend([dict(s) for s in segs])
    flat = _dedup_and_fill(flat, need=sum(counts), reserved=reserved)
    # 정렬: (video_id,start) 우선, 동시각이면 얼굴 세그먼트를 뒤로(대체 있을 때 후순위).
    # 레시피면 완성 세그먼트를 조리/기타 뒤로(finish_last) — 완성이 조리 앞에 안 낀다.
    # 제품(is_recipe=False)이면 finish_last 항상 0 → 기존 (video_id,start,face)와 동일.
    def _sort_key(s):
        finish_last = 1 if (is_recipe and s.get("shot_role") == "완성") else 0
        return (finish_last, s.get("video_id", ""), s.get("start", 0.0),
                _is_face_seg(s.get("scene_desc", "")))
    ordered = sorted(flat, key=_sort_key)
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
    if head is not None:
        out.insert(0, dict(head))   # 훅 앵커 — 모델이 고른 화면 그대로(respined 아님)
    # 꼬리: 앵커 — 세그먼트·fit 모두 모델이 고른 그대로(respined 아님).
    out.append(dict(tail))
    return out


def _validate_and_ground(raw_plan, seg_map, n_alternates, respine=True, is_recipe=False):
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
        beats_out = _chronological_respine(beats_out, is_recipe=is_recipe)
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
            # ★503/과부하는 일시적(2026-07-24 실측: scene_first가 이걸로 죽어 옛 대본으로 폴백,
            # 30초·7~8컷·대화 개선이 통째로 안 탔다). 포기 대신 잠깐 쉬고 다음 키로 재시도한다.
            m = str(e)
            if any(c in m for c in ("503", "UNAVAILABLE", "overloaded", "high demand")):
                time.sleep(2)
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
            "beats": {"type": "array", "minItems": 6, "items": {
                "type": "object",
                "properties": {
                    "role": {"type": "string"}, "narration": {"type": "string"},
                    "caption_lines": {"type": "array", "items": {"type": "string"}},
                    "seg_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                    "fit": {"type": "integer"}, "forced": {"type": "boolean"}},
                "required": ["role", "narration", "seg_ids", "fit"]}}},
        "required": ["hook", "beats"]}}},
    "required": ["candidates"],
}


def _source_benefits_block(source_scripts):
    """소스별 product_benefits → 프롬프트 블록(무자막 소스용). 전부 비면 빈 문자열=무주입.

    무자막 해외영상(2026-07-26)은 full_text·text가 0자라 레퍼런스에도 팔레트 '말:' 칸에도
    언어 재료가 없다 — 화면에서 뽑은 특장점만이 유일한 재료다. 이 블록이 없으면 대본이
    "무슨 제품인지"를 모르고 감상만 쓴다(실측: 전동수납장 소스가 화면 재료로만 쓰였다)."""
    lines = []
    for i, s in enumerate(source_scripts or [], 1):
        raw = s.get("product_benefits")
        if isinstance(raw, str):
            raw = [raw]
        bens = [t.strip() for t in (raw or []) if isinstance(t, str) and t.strip()]
        if not bens:
            bens = _collect_seg_benefits(s.get("segments"))
        if bens:
            lines.append(f"- 소스{i}: " + " / ".join(bens[:4]))
    if not lines:
        return ""
    return ("[제품 특장점 — 화면으로 확인된 사실. ★자막 없는 소스라 대사가 비어도 이 장점을 "
            "우리 말(스토리)로 반드시 녹여라. 없는 기능은 지어내지 마라]\n" + "\n".join(lines))


def _collect_seg_benefits(segments):
    """세그먼트별 특장점 집계(순서 보존 중복제거) — 소스 최상위 필드가 없는 캐시용 폴백."""
    out = []
    for seg in segments or []:
        for b in _seg_benefits(seg):
            if b not in out:
                out.append(b)
    return out


def _scene_first_candidates(inventory_text, reference_text, target_seconds, n=3, call=_vault_call,
                            bank_context="", order_block="", lengthen=False,
                            benefits_block=""):
    """스토리 헌장 + 장면 팔레트 + 레퍼 구조 → 후보 n개. 각 비트는 seg_ids(2~4 다중컷)로
    장면을 지목한다. 실패 시 []. 헌장이 품질을 담당하므로 별도 검증루프 없음(1콜).

    bank_context(P0-2): 부품은행에서 조립한 승인 훅·어미·부사·CTA·스파인 블록(빈 문자열이면
    미주입=회귀0). 영상 믹스 대본이 매번 같은 훅으로 열리지 않게 로테이션된 부품을 실어준다.
    order_block(2026-07-22 백본 통합): 백본 영상의 시간순 장면 뼈대 블록. 빈 문자열이면 무주입.
    ★스토리·은행·다중컷(rich 품질기계)은 그대로 두고 화면 '순서'만 제약한다 — 별도의 뼈다귀
    생성기(장면당 한 줄)를 쓰면 스키마에 스토리 필드가 없어 이야기가 원천 불가였다(그날 실사고)."""
    from shopping_shorts import script_generate  # 지연 import(순환 방지)
    char_target = int(target_seconds * _SYLLABLES_PER_SEC)
    prompt = (
        "너는 한국 쇼핑 숏폼(살림·요리) 대본 작가다. 아래 '스토리 헌장'을 반드시 지켜 "
        f"탄탄한 대본 후보 {n}개를 만들어라.\n"
        "★★대본은 '화자가 들려주는 짧은 이야기'다(화면 설명문이 아니다). 반드시 대화·사건·"
        "반전이 있게 써라: 'A가 ~라고 하길래 / 나는 ~했는데 / 그랬더니 ~ / 근데 알고보니 ~(반전) "
        "/ 그래서 지금은 ~' 식으로. 화면에 그 사람·그 순간이 안 보여도 된다 — 이야기는 화자의 "
        "목소리로 흐르고, 장면은 그 밑에 깔리는 먹음직스러운 그림일 뿐이다. '맛있다·진하다·예술이다' "
        "같은 감상 나열은 이야기가 아니다(반려). 누가·무슨 말·왜·그래서·반전이 있어야 한다.\n"
        "★★구체적 인용 대화 필수: 실제 주고받은 말을 **따옴표로 최소 2번** 넣어라 — "
        "'남편이 \"밥 없어?\" 하길래' / '그래서 제가 \"이거 먹어봐\" 했더니' / '한 입 먹고 \"이거 "
        "밖에서 파는 거야?\" 하더라고요' 식으로. 두루뭉실 요약('맛있대요') 말고 그 순간 그 사람이 "
        "한 말을 그대로. 이 대화가 있고 없고가 탄탄함을 가른다.\n"
        "★장면 붙이기: 각 비트에 seg_id를 2~4개 시간순으로 붙이되, **결정적 행위 비트**(비법 얹기·"
        "붓기·자르기 등)만 그 행위 장면과 정확히 맞춰라. 나머지 이야기 비트는 화면을 설명할 "
        "필요 없이 먹음직스러운 장면을 깔면 된다(대사와 화면이 1:1일 필요 없음).\n"
        f"★후보 {n}개는 톤을 서로 다르게 해라 — 그중 **딱 하나**는 자연스러운 위트·유머를 "
        "스토리에 살짝 녹여라(상황에서 피식 나오는 정도·공감개그·가벼운 반전). ⚠️억지 개그·"
        "썰렁·오글거림·말장난 금지 — 어색하면 안 넣느니만 못하다. 나머지 후보는 진솔하게.\n\n"
        "[레퍼런스 — ★참고용 흐름 감만. 뼈대를 통째로 차용하지 마라. 훅·전개는 아래 [은행] "
        "블록의 실제 수집물이 우선이다(레퍼런스보다 은행). 다국어면 한국어로]\n"
        f"{(reference_text or '')[:1500]}\n\n"
        "[우리 장면 팔레트 — 이 seg_id 화면만 쓸 수 있다]\n"
        f"{inventory_text}\n\n"
        + ((benefits_block + "\n\n") if benefits_block else "")
        + ((order_block + "\n\n") if order_block else "")
        + script_generate._STORY_RULES_CORE + "\n" + script_generate._STORY_DECLARE + "\n"
        "- ★위 헌장(인과사슬·훅 한방·CTA 미끼·비법 킥 감추기)을 반드시 지켜라 — 장면에 맞추느라 "
        "스토리가 밋밋해지면 실패다. 스토리가 왕, 장면은 그 스토리를 보여줄 그림이다.\n"
        "- ★★영상은 beats를 읽는다 — hook은 헤드라인 필드일 뿐 화면엔 안 나온다. 그러니 "
        "beats[0].narration을 반드시 hook과 같은 강한 오프너('와 이거 진짜 대박인데요?'·'이걸 왜 "
        "이제 알았지?'·'저 이거 몰라서 손해 봤잖아요'·'이거 진짜 절대 하지 마세요' 류)로 시작해라. "
        "hook만 세게 써놓고 첫 비트를 '매번 ~하던 참이었거든요'처럼 밋밋하게 열면 실패다. "
        "beats[0]이 곧 그 hook이어야 한다.\n"
        f"- ★★★길이는 목표 {char_target}자(약 {target_seconds}초)에 **정확히** 맞춰라. 전체 나레이션 "
        f"글자수 합이 **{int(char_target*0.9)}~{int(char_target*1.1)}자** 안에 반드시 들어와야 한다.\n"
        f"  ⚠️가장 흔한 실패 = **너무 짧게 쓰는 것**이다(대부분 목표의 절반밖에 안 쓴다). "
        f"{int(char_target*0.9)}자보다 짧으면 이야기가 빈약해 **무조건 반려** — 대화 인용·반전·구체적 "
        f"반응·감각 묘사를 더 넣어 {char_target}자를 반드시 채워라. 반대로 {int(char_target*1.1)}자를 "
        f"넘겨도 반려.\n"
        f"  ★비트는 6~7개로 나누되 **6~7비트의 글자수 합 = {char_target}자**가 되게 고르게 배분해라: "
        f"비트가 6개면 각 비트 약 {char_target//6}자, 7개면 각 약 {char_target//7}자. 한 비트를 "
        f"20자 밑으로 쓰면 총량이 모자라 반려된다(각 비트를 알차게 채워라).\n"
        "  ★따옴표 대화는 그 순간 실제로 오간 말을 살려 넣되 자연스러운 길이로 — 대화·서술 어느 쪽도 "
        "억지로 줄이지 마라. 총량이 모자라면 오히려 이야기를 더 촘촘히 채워라.\n"
        "  각 비트: role·narration(구어체)·seg_ids(2~4)·fit(1~5)·forced(그 장면이 이 말과 안 맞는데 억지로면 true).\n"
        "- ★caption_lines: 그 비트 narration을 화면 자막용으로 **3~4어절 호흡 단위**로 끊은 "
        "배열(너무 잘게 쪼개면 화면에서 문장이 뚝뚝 끊겨 보인다 — 한 호흡에 3~4어절씩 넉넉히). "
        "수식어는 반드시 뒤 명사와 한 줄에 둬라('만든 사람'을 '만든'|'사람'으로 쪼개지 마라, "
        "'이 소스'·'특제 비법'처럼 관형어+명사는 붙인다). 이어붙이면 narration과 글자가 정확히 "
        "같아야 한다(단어 추가·삭제 금지, 문장부호 유지).\n"
        "- 화면에 없는 걸 말하지 마라. 같은 seg_id를 여러 비트에서 재사용 금지.\n"
        # ★비트↔비트 연결(2026-07-22): 문장이 뚝뚝 끊기지 않게 한 편의 글로 흐르게 한다.
        # 앞 문장을 이어받는 연결(그래서·근데·이때·그랬더니…)로 자연스럽게, 단 '때문에 요즘 우리'
        # 처럼 다음 조각이 앞과 안 맞물리는 어색한 중간 연결어는 금지. 소리내어 읽어도 매끄럽게.
        "- ★비트들을 하나의 이어지는 이야기로 써라 — 각 문장이 앞 문장을 자연스럽게 이어받아야 "
        "한다(뚝뚝 끊긴 조각 나열 금지, 어색한 중간 연결어 금지). 인물을 세웠으면 끝까지 관통.\n"
        "- ★★★스토리 전개 고도화(7~8비트 드라마 아크, 30초를 꽉 채워라): 이야기를 촘촘히·극적으로 "
        "전개해라 — ① 강한 훅(감탄·충격) → ② 상황·인물 설정(누가·왜, 대화 인용) → ③ 기대/시련 고조"
        "(그래서 어땠는데) → ④ **반전 1**(예상 밖의 전개, '근데 웬걸') → ⑤ 절정·증거(생생한 반응·대화 "
        "인용) → ⑥ **반전 2/비하인드**(알고보니 이게 비법이었다·의외의 결말) → ⑦ 해소 → ⑧ CTA. "
        "각 비트가 다른 단계를 맡아 이야기가 '깊어지게'. ★반전은 최소 2번(예상 뒤집기), 매 비트에 "
        "다음이 궁금한 갈고리를 남겨라.\n"
        "- ★★재미·극적 재미요소를 살려라(밋밋 반려): 의외성·공감개그(상황에서 피식)·과장된 리액션을 "
        "대화 인용으로('남편이 \"이거 밖에서 파는 거 아냐?\" 하는 거예요' 류). 오글·억지 개그·말장난은 "
        "금지 — 진짜 있었던 일처럼 자연스럽게 웃기고 놀랍게.\n"
        "- ★★은행 부사·수식어를 적극 써라(지금 안 쓰고 있다): 아래 [은행]의 '부사' 부품(예: "
        "'단 몇 초 만에'·'극도로'·'너무너무'·'막')과 생생한 형용사를 나레이션에 녹여 밋밋한 문장을 "
        "살려라 — 감각·강도를 부사로 키워라(단, 한 문장에 몰아넣지 말고 자연스럽게).\n"
        + ((bank_context + "\n") if bank_context else "")
        # ①생성측 보강(세션#2): 직전 후보가 전부 목표보다 크게 짧을 때 1회 재생성하며 이 힌트를
        # 얹는다. 대본 길이 뒤죽박죽의 생성측 뿌리 — 프롬프트가 목표를 지시해도 실제 출력이 짧게
        # 나온 경우, 길이 하한을 명시하고 비트를 잘게 쪼개지 말고 알차게 채우라고 강제한다.
        + ((f"- ★★★[길이 재생성] 직전 후보들이 목표보다 크게 짧았다. 이번엔 반드시 전체 "
            f"나레이션 글자수 합을 **최소 {int(char_target*0.9)}자 이상**(목표 {char_target}자)에 "
            "맞춰라. 비트는 6~7개로 유지하되(잘게 쪼개지 마라) 각 비트의 이야기를 더 촘촘하게 "
            "채워라 — 대화 인용을 한 번 더, 반전·구체적 반응·감각 묘사를 보태 각 문장을 알차게.\n")
           if lengthen else "")
        + "출력은 스키마 JSON만.")
    raw = call(prompt, _SCENE_FIRST_SCHEMA)
    if not raw or not isinstance(raw, dict):
        return []
    return raw.get("candidates", []) or []


_STRONG_OPENER_TOKENS = ("와 ", "와,", "아니", "이거", "이걸", "저 이거", "헐", "대박",
                         "세상에", "이런", "저만")


def _hook_opener(hook):
    """hook의 첫 절(첫 ?/!/. 까지) — 강한 오프너로 beats[0]에 얹을 조각. 없으면 ''."""
    h = (hook or "").strip()
    if not h:
        return ""
    for i, ch in enumerate(h):
        if ch in "?!":
            return h[:i + 1]
    return h.split(".")[0].strip()


def _lead_with_hook(narration, hook):
    """beats[0]이 강한 오프너로 안 열리면 hook 앞절을 붙여 강제로 세게 연다(2026-07-21).
    이미 강해 보이면(오프너 토큰 시작 or 앞 12자에 ?/!) 그대로 둔다(중복 방지)."""
    n = (narration or "").strip()
    head = n[:12]
    if n.startswith(_STRONG_OPENER_TOKENS) or "?" in head or "!" in head:
        return n
    opener = _hook_opener(hook)
    if not opener or opener in n:
        return n
    return f"{opener} {n}"


def _ground_candidate(cand, seg_map, structure="free"):
    """후보 비트(narration + seg_ids 다중컷)를 build_edit_plan 반환형 EDL로 grounding.
    seg_ids[0]=primary, 나머지=alternates(연속재생). start/end/scene_desc는 코드가 되붙인다.
    primary 무효 비트는 드롭. 유효 비트 0개면 None.
    ★영상은 beats를 읽으므로 첫 비트가 밋밋하면 hook(강한 오프너)을 앞에 얹는다."""
    hook = cand.get("hook", "")
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
        cap_lines = beat.get("caption_lines") or None
        if not beats_out:                       # 첫 유효 비트 = 훅 자리
            new_narr = _lead_with_hook(narration, hook)
            if new_narr != narration:           # 훅을 얹었으면 옛 자막줄은 무효(정규식 폴백)
                cap_lines = None
            narration = new_narr
        beats_out.append({
            "beat_idx": len(beats_out), "role": beat.get("role", ""),
            "narration": narration, "caption_lines": cap_lines,
            "target_seconds": round(max(1.5, len(narration.strip()) / _SYLLABLES_PER_SEC), 1),
            "primary": primary, "alternates": alts, "effect": "cut",
            "fit": int(beat.get("fit") or 0), "forced": bool(beat.get("forced", False)),
        })
    if not beats_out:
        return None
    return {"structure": structure, "beats": beats_out}


def _candidate_quality(beats):
    """후보 대본의 품질(0~1) — 대화체(tone)·재미강도(fun, D14). 전 비트 나레이션을 이어
    tone_score로 재는 순수 계산(Gemini 없음). 나레이션이 비면 0(매칭점수만으로 판정).
    P1: scene_first는 헌장 1콜이라 위키생성의 _verify_and_fix 품질정렬을 못 받았다 — 추천
    선택에 품질을 직접 넣어 '말투 좋고 재미장치 있는' 후보가 추천되게 한다."""
    from shopping_shorts import tone_score
    text = " ".join((b.get("narration") or "").strip() for b in beats).strip()
    if not text:
        return 0.0
    tone = tone_score.score_conversational(text)["score"]         # 0~1(문어체·AI냄새·어미단조 감점)
    fun = 1.0 if tone_score.fun_intensity(text)["has_strong"] else 0.0
    return 0.6 * tone + 0.4 * fun


def _cut_rhythm_penalty(beats):
    """컷 리듬 감점(0~0.2, 브리프 T6) — 파편화(비트당 클립 과다=짧은 컷 연발)와 전역 반복
    (같은 seg 재사용=B롤 체인)을 감지한다. T1~T5가 구성을 고쳐도 후보들이 이 축에서 다를 수
    있어, 추천 선택이 파편·반복 후보를 다시 고르지 않게 하는 안전망. 잘 구성된 후보(비트당
    클립 ≤ MAX_CLIPS_PER_BEAT·seg 전부 고유)는 0 → 정상 경로 회귀0."""
    beats = beats or []
    if not beats:
        return 0.0
    seg_ids = []
    for b in beats:
        p = (b.get("primary") or {}).get("seg_id")
        if p:
            seg_ids.append(p)
        for a in (b.get("alternates") or []):
            sid = (a or {}).get("seg_id")
            if sid:
                seg_ids.append(sid)
    clips = len(seg_ids)
    if clips == 0:
        return 0.0
    from shopping_shorts.config import MAX_CLIPS_PER_BEAT
    avg_clips = clips / len(beats)
    frag = min(1.0, max(0.0, avg_clips - MAX_CLIPS_PER_BEAT) / MAX_CLIPS_PER_BEAT)
    repeat = 1.0 - len(set(seg_ids)) / clips     # 고유가 아닌 클립 비중(전역 반복)
    return round(min(0.2, 0.1 * frag + 0.1 * repeat), 3)


def _length_penalty(beats, target_seconds):
    """후보 길이가 목표초에서 벗어날수록 감점(2026-07-25 세션#2). 선택이 길이를 무시해 21.3초
    짜리가 30초 목표에 뽑히던 것(후보 A/B/C 길이 뒤죽박죽)을 막는다. 후보 길이 = 비트별
    target_seconds 합(≈나레이션 글자수 기준). 목표의 0.9~1.15배는 무감점(약간 넘는 건 conform이
    흡수) — 벗어나면 편차 비례 감점(최대 0.3). target_seconds 없으면 0(기존 동작 유지)."""
    if not target_seconds or target_seconds <= 0 or not beats:
        return 0.0
    total = sum(float(b.get("target_seconds") or 0.0) for b in beats)
    if total <= 0:
        return 0.0
    ratio = total / target_seconds
    dev = max(0.0, 0.9 - ratio) + max(0.0, ratio - 1.15)
    return round(min(0.3, dev), 3)


def _score_candidate(plan, avoid_hooks=None, target_seconds=None):
    """후보 추천 점수(0~1): 매칭(fit·억지없음·장면다양성) + 품질(대화체·재미강도). 빈 beats면 0.0.
    avoid_hooks(novelty 감점, belt-and-suspenders): 최근 영상이 쓴 훅 목록. 첫 비트(=훅)가
    그와 n-gram 겹치면 감점 → 프롬프트 회피를 무시하고 같은 훅을 낸 후보가 추천되는 걸 막는다.
    컷 리듬 감점(T6): 파편화·전역 반복이 심한 후보를 강등한다.
    길이 감점(세션#2): target_seconds가 주어지면 목표초에서 벗어난 후보를 강등한다."""
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
    match = 0.5 * avg_fit + 0.3 * (1 - forced_ratio) + 0.2 * diversity
    quality = _candidate_quality(beats)          # 나레이션 없으면 0 → 매칭점수만(기존 계약 유지)
    score = 0.75 * match + 0.25 * quality
    score -= _cut_rhythm_penalty(beats)          # T6: 파편·반복 후보 강등(안전망)
    score -= _length_penalty(beats, target_seconds)  # 세션#2: 목표초 벗어난 후보 강등
    if avoid_hooks:
        hook = beats[0].get("narration") or ""
        overlap = max((_ngram_overlap(hook, h) for h in avoid_hooks), default=0.0)
        score -= 0.3 * overlap                   # 최근 훅과 겹칠수록 감점(최대 0.3)
    return round(max(0.0, min(1.0, score)), 3)


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
        return _trim_to_budget(narration, char_target)   # Gemini 실패·쿼터 → 결정적 폴백
    new = (raw.get("narration") or "").strip()
    if not new:
        return _trim_to_budget(narration, char_target)
    est = len("".join(new.split())) / _SYLLABLES_PER_SEC
    if not (0.8 * target_seconds <= est <= 1.2 * target_seconds):
        return _trim_to_budget(narration, char_target)   # Gemini 결과 부적합 → 결정적 폴백
    return new


# 문법을 안 깨고 뺄 수 있는 군더더기 부사·강조어(콘폼 결정적 폴백용). '계란물을 모두 부어요'
# → '계란물을 부어요'처럼 뜻·문장은 그대로 두고 시간만 줄인다.
_FILLER_WORDS = ("모두", "정말", "진짜", "아주", "너무", "살짝", "그냥", "이제", "바로",
                 "좀", "막", "딱", "한번", "완전", "엄청", "되게", "조금", "약간", "다시",
                 "계속", "꼭", "이렇게", "그렇게", "얼른", "어서", "곧바로", "무려")


def _trim_to_budget(narration, char_target):
    """Gemini 없이 결정적으로 대사를 예산 글자수에 맞추는 콘폼 폴백(2026-07-22, 사장님 요청).
    Gemini 쿼터·실패로 콘폼이 조용히 안 되던 걸 대체 — 문법이 안 깨지게 군더더기 부사부터
    하나씩 덜어 길이를 줄인다. 이미 예산 내거나 뺄 게 없어 그대로면 None(원문 유지)."""
    def clen(s):
        return len("".join(s.split()))
    narration = (narration or "").strip()
    if not narration or clen(narration) <= char_target:
        return None
    words = narration.split()
    for filler in _FILLER_WORDS:
        if clen(" ".join(words)) <= char_target:
            break
        if filler in words:
            words = [w for w in words if w != filler]
    new = " ".join(words).strip()
    return new if (new and new != narration) else None


def _conform_overflow_beats(beats, target_seconds, conform=None):
    """후보 총 나레이션이 목표초를 넘으면(>1.15배) 각 비트를 목표 발화초에 맞게 압축한다.
    _length_penalty 주석이 약속한 'conform 흡수'의 실제 배선(2026-07-26). conform은 주입
    가능(테스트용) — 기본은 conform_narration. 총량이 예산 이내면 원본 그대로(무변경)."""
    if not beats or not target_seconds or target_seconds <= 0:
        return beats
    def _clen(s):
        return len("".join((s or "").split()))
    total_chars = sum(_clen(b.get("narration", "")) for b in beats)
    budget = target_seconds * _SYLLABLES_PER_SEC
    if total_chars <= budget * 1.15:
        return beats                      # 예산 이내 → 무변경(회귀0)
    conform = conform or conform_narration
    # 비트별 목표초 = 그 비트의 현재 글자 비중 × 전체 목표초 (긴 비트가 더 줄어든다)
    out = []
    for b in beats:
        nb = dict(b)
        cur = _clen(b.get("narration", ""))
        if cur and total_chars > 0:
            beat_target_sec = target_seconds * (cur / total_chars)
            new_narr = conform(b.get("narration", ""), beat_target_sec)
            if new_narr and _clen(new_narr) < cur:
                nb["narration"] = new_narr
                nb["target_seconds"] = round(max(1.5, _clen(new_narr) / _SYLLABLES_PER_SEC), 1)
        out.append(nb)
    return out


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
        "아래 비트들은 대사와 화면이 어긋난다. ★스토리가 왕이다 — 화자가 들려주는 이야기 흐름과 "
        "말투를 그대로 유지해라. 화면묘사문으로 바꾸지 마라('달콤한 향이 퍼지네요' 같은 장면설명 금지). "
        "대사가 화면과 **정면으로 모순되는 구체적 동작 단어**(예: 화면은 뒤집는데 '썰어')만 그 한 곳을 "
        "화면과 안 부딪히게 살짝 바꾸거나 빼라. 나머지 이야기 문장은 절대 건드리지 마라. "
        "화면에 없는 사실 지어내지 마라.\n"
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
                    n_alternates=2, max_retries=4, quota_sleep=8, given_script=None,
                    is_recipe=False):
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
    grounded = _validate_and_ground(raw, seg_map, n_alternates, is_recipe=is_recipe)
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


def _verify_fits(beats):
    """fit 자기신고 검증(2026-07-22 페이블 점검): fit은 생성 Gemini의 자기채점이라 전부 5/5로
    나와 — 화면의 '매칭 5/5' 표시, 추천점수의 avg_fit(50%), fit≤2 스왑버튼, fit≤3 약비트
    재작성이 전부 무력화돼 있었다(banana 실사고: '썰어' 대사에 '뒤집는' 화면이 fit5).
    행위 증거가 있을 때만 정직하게 깎는다: 나레이션 행위 ≠ 화면 행위(둘 다 검출) → fit≤2.
    모호하면(행위 미검출) 보류 = 오탐 없음. ping_pong이 스왑으로 고치면 fit=5로 복원된다."""
    from shopping_shorts import backbone
    for b in beats:
        if backbone.beat_action_mismatch(b):
            b["fit"] = min(int(b.get("fit") or 0), 2)
            b["fit_evidence"] = "action_mismatch"
    return beats


def _backbone_order_block(backbone_video, source_scripts):
    """백본 영상의 시간순 장면 뼈대 → rich 생성 프롬프트에 넣을 '순서 제약' 블록.

    ★생성기를 갈아끼우지 않는다(2026-07-22 페이블 점검 결론). 예전엔 백본용 뼈다귀 생성기
    (장면당 narration+seg_id 한 줄, 스토리 필드 없는 스키마)를 따로 만들어 스마트믹스가 그리로
    빠졌고 — 스키마가 이야기를 표현 못 해 단조·무스토리·은행묻힘이 구조적으로 났다. 이제
    rich 생성기(_scene_first_candidates: 스토리 선언·짤드라마 헌장·은행·다중컷·사이징)를 그대로
    쓰고, 백본이 주는 건 이 '화면 순서' 제약 하나다. 백본=순서, rich=대본."""
    from shopping_shorts import backbone
    bb_src = next((s for s in (source_scripts or [])
                   if s.get("video_id") == backbone_video), None)
    if not bb_src:
        return ""
    flow = backbone.backbone_flow(bb_src)
    if not flow:
        return ""
    lines = "\n".join(
        f"  {i+1}. {f.get('seg_id')} [{f.get('action') or '-'}] {f.get('scene_desc', '')}"
        for i, f in enumerate(flow))
    return (
        f"[화면 순서 뼈대 — 백본 영상 {backbone_video}의 시간순 진행]\n{lines}\n"
        "★화면 진행은 위 뼈대의 시간순을 따르라 — 비트들의 seg_ids가 전체적으로 이 순서를 "
        "거스르지 않게 배치해라(과정이 뒤로 갔다 앞으로 오는 뒤죽박죽 금지). 다른 영상(서브) "
        "컷은 흐름에 맞는 자리에 끼워 넣어도 된다. 순서는 뼈대를 따르되, 대사는 헌장대로 "
        "온전히 하나의 이야기로 써라.")


def build_scene_first_plan(source_scripts, reference_text, target_seconds,
                           n_candidates=3, video_type=None, call=None, ping_pong=False,
                           backbone_meta=None, backbone_forced=None, bank_context="",
                           avoid_hooks=None, backbone_base=False, judge=False,
                           is_recipe=False):
    """장면 우선 대본 모드: 팔레트+헌장으로 후보 n개 생성 → 각 EDL grounding·채점 →
    최고 score에 recommended=True. 각 candidate.plan은 build_edit_plan 반환형(하류 렌더 호환).
    후보 0개면 candidates=[](호출부가 기존 build_edit_plan로 폴백).

    ping_pong=True(opt-in, 기본 off로 회귀0): grounding 후 backbone 핑퐁으로 비트별
    대본↔장면을 왕복 조정(행위 불일치=fit 거짓말 잡기 → 같은 행위 클립 스왑 or 나레이션 재작성).

    backbone_base=True(opt-in, 기본 off로 회귀0): 백본-베이스 확정스펙(2026-07-21). 레퍼런스
    자유생성 대신 **잘된 영상 1개의 흐름(순서·리듬)** 을 뼈대로, 실제 장면 인벤토리(백본+서브)에
    맞춰 100% 우리 대본을 생성한다(없는 장면 요구 차단 → 소스에 클립 없어도 천장 없음). 백본을
    못 고르거나 생성이 비면 조용히 레퍼런스-먼저로 폴백(회귀0)."""
    seg_map, inventory = _build_inventory(source_scripts)
    detected = video_type or (detect_video_type(source_scripts) if source_scripts else _DEFAULT_TYPE)
    if not seg_map:
        return {"candidates": [], "detected_type": detected}
    _call = call or _vault_call
    # 백본 통합(2026-07-22 페이블 점검): 생성기는 rich 하나만 쓴다. backbone_base면 백본을
    # 골라 '화면 순서 제약' 블록만 프롬프트에 얹는다 — 스토리·은행·다중컷은 rich가 담당,
    # 백본은 순서만 담당. (예전 뼈다귀 생성기 분기는 스키마에 스토리 필드가 없어 폐기.)
    bb_video, order_block = None, ""
    if backbone_base:
        from shopping_shorts import backbone
        bb_video = backbone.pick_backbone(source_scripts, meta=backbone_meta,
                                          forced=backbone_forced)
        if bb_video:
            order_block = _backbone_order_block(bb_video, source_scripts)
    src_texts = [s.get("full_text", "") for s in source_scripts]

    def _ground_score(raws):
      if bb_video:
        for r in raws:
            r.setdefault("_backbone_video", bb_video)   # 핑퐁 순서고정이 이 백본을 쓴다
      cands = []
      for r in raws:
        plan = _ground_candidate(r, seg_map)
        if plan is None:
            continue
        # fit 정직화(페이블): 행위 불일치 증거가 있으면 자기신고 fit을 깎는다 — 스왑버튼·
        # 약비트 재작성·추천점수가 실제로 작동. ping_pong이 스왑으로 고치면 5로 복원됨.
        plan["beats"] = _verify_fits(plan["beats"])
        # 앵커 dedup(항상) + 레시피 grain(비-핑퐁일 때만) — 주경로 배선(Task8).
        # ping_pong이면 백본이 순서를 소유하므로 grain 리오더는 끄고(is_recipe=False),
        # dedup(순서 불변, primary→alternate 스왑만)만 남긴다. 백본은 과정순서를 이미 처리한다.
        plan["beats"] = _apply_anchor_grain(plan["beats"], is_recipe=(is_recipe and not ping_pong))
        # 초과 흡수(Task11): 총 나레이션이 목표초를 넘으면 각 비트를 conform으로 줄인다.
        # _length_penalty 주석이 약속한 실제 배선 — 채점 전에 적용해 감점이 콘폼된 길이를 본다.
        plan["beats"] = _conform_overflow_beats(plan["beats"], target_seconds)
        if ping_pong:
            from shopping_shorts import backbone
            # 1) 행위 매칭(화면-대사 어긋남 + 길이) 2) 백본 순서 고정(과정순서)
            plan["beats"] = backbone.ping_pong_reconcile(
                plan["beats"], source_scripts,
                rewrite_call=lambda bs: _bb_rewrite(bs, _call),
                trim_call=lambda bs: _bb_trim(bs, _call))
            # 이 후보의 백본(순서 뼈대) — 백본-베이스면 후보 자신의 것, 아니면 전역 선정.
            bb = r.get("_backbone_video") or backbone.pick_backbone(
                source_scripts, meta=backbone_meta, forced=backbone_forced)
            if bb:
                plan["beats"] = backbone.order_by_backbone(plan["beats"], bb)
            # 반복장면·한소스 편중 해소: 쓴 클립 재사용 금지 + 덜 쓴 소스 우선 교체
            plan["beats"] = backbone.dedup_and_balance(plan["beats"], source_scripts)
            # 서브 의무삽입: 아예 안 쓰인 소스(s2=0)를 같은 행위로 강제 삽입(dedup으론 못 잡음)
            plan["beats"] = backbone.ensure_sources_used(plan["beats"], source_scripts)
            # 전역 컷 반복 해소(alternates 포함) + 비트당 클립 상한 → 뚝뚝 끊김·B롤 반복 해소
            # (dedup_and_balance는 primary만 봐서 B롤 체인이 비트마다 반복됐다, job 실측).
            plan["beats"] = backbone.dedup_clips_global(plan["beats"], source_scripts)
        plan["detected_type"] = detected
        plan["affiliate_target"] = r.get("story_event", "") or ""
        plan["plagiarism_flags"] = _plagiarism_flags(plan["beats"], src_texts)
        story = {k: r.get(k, "") for k in
                 ("hook", "story_person", "story_event", "story_resolution", "cta_line", "cta_keyword")}
        rule_score = _score_candidate(plan, avoid_hooks=avoid_hooks, target_seconds=target_seconds)
        cand = {"plan": plan, "story": story, "score": rule_score, "recommended": False}
        # ★심사위원(사장님 기준: 대본품질·장면싱크·스토리라인) — judge on일 때만(Gemini 콜).
        # 규칙점수(빠른 계산)와 반반 섞어 최종 순위. 심사 실패는 규칙점수만으로 폴백(무해).
        from shopping_shorts import candidate_judge
        if judge:
            jr = candidate_judge.judge(plan.get("beats"), call=_call)
            if jr:
                cand["judge"] = jr
                cand["score"] = round(0.5 * rule_score + 0.5 * jr["total"], 3)
        # T6 컷리듬/반복 감점은 _score_candidate(rule_score) 안에서 이미 빠진다 — 여기서 또 빼면
        # 이중 감점(2026-07-24 병합에서 candidate_judge판+edit_plan판 중복 발견). 관측용으로만 노출.
        _cp = _cut_rhythm_penalty(plan.get("beats"))
        if _cp:
            cand["cut_penalty"] = round(_cp, 3)
        cands.append(cand)
      return cands

    # 무자막 소스 특장점 블록(2026-07-26): 전부 비면 빈 문자열=무주입(회귀0).
    benefits_block = _source_benefits_block(source_scripts)
    raws = _scene_first_candidates(inventory, reference_text, target_seconds, n=n_candidates,
                                   call=_call, bank_context=bank_context, order_block=order_block,
                                   benefits_block=benefits_block)
    cands = _ground_score(raws)
    # ①생성측 보강(세션#2): 후보가 전부 목표보다 크게 짧으면(생성이 목표초 미달) 길이 강화
    # 힌트로 1회 재생성해 합친다. ②선택 감점(_length_penalty)이 짧은 후보를 강등하므로 병합 후
    # 채점하면 긴 후보가 자연히 추천된다. 재생성은 '전부 짧을 때만' — 소스 footage 부족이 아니라
    # 생성 자체가 목표초에 못 미친 경우로 한정(과금 게이트, 1회 상한, 실패해도 기존 후보 유지).
    if cands and target_seconds and target_seconds > 0:
        def _cand_secs(c):
            return sum(float(b.get("target_seconds") or 0.0)
                       for b in c["plan"].get("beats", []))
        if max((_cand_secs(c) for c in cands), default=0.0) < 0.92 * target_seconds:
            raws2 = _scene_first_candidates(
                inventory, reference_text, target_seconds, n=n_candidates, call=_call,
                bank_context=bank_context, order_block=order_block, lengthen=True,
                benefits_block=benefits_block)
            cands = cands + _ground_score(raws2)
    if cands:
        best = max(range(len(cands)), key=lambda i: cands[i]["score"])
        cands[best]["recommended"] = True
    return {"candidates": cands, "detected_type": detected}
