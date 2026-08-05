"""여러 소스 대본을 하나의 편집결정목록(EDL)으로 동시 생성(설계 §3-2).

대본 합성(구 script_synth)과 장면 매칭(구 clip_match)을 한 단계로 통합한다 —
대본을 먼저 확정하고 장면을 끼워맞추면 억지 매칭이 생기므로, 모델이 비트마다
'무슨 말을 할지'와 '그 말에 맞는 소스구간(seg_id)'을 동시에 정하게 한다.

환각 방지: 모델은 소스 구간을 seg_id로만 지목하고, 실제 start/end는 코드가
인벤토리에서 되붙인다(_validate_and_ground). 표절은 n-gram 가드로 사후 검출.
build_edit_plan(Gemini 콜)은 Task 4에서 추가.
"""

import json
import os
import re
import sys
import time

from google.genai import types

from pipeline.atoms import key_vault
from shopping_shorts import comment_gen
from shopping_shorts.config import SHORTS_GEMINI_KEYS

_REQUIRED_ROLES = ["훅", "페인포인트", "반전", "실용", "CTA"]

# 영상 유형별 대본 전략 레지스트리(설계 §2·§3-1) — 유형 추가 = 항목 하나 추가.
# 장면 스파인 먼저 재설계(2026-07-29): 카테고리마다 label(화면표시)·strategy(말투)에 더해
# spine(슬롯 순서 배열)을 둔다. 각 슬롯은 {slot 이름, roles(허용 shot_role), key(is_key 선호)}.
# _build_scene_spine이 이 순서대로 태깅된 장면을 배치 → 대본이 그 순서를 따른다.
# 설계: docs/superpowers/specs/2026-07-29-장면스파인-먼저-재설계-design.md
VIDEO_TYPES = {
    "recipe": {
        "label": "🍳 요리/식품",
        "strategy": "이 영상은 레시피/살림팁이다. 핵심 재료·비법을 절대 이름으로 밝히지 마라 — "
                    "'이것', '집에 있는 이거', '한 스푼'처럼 감춰서 궁금하게 만들어라. 마지막 "
                    "CTA 비트는 '댓글에 [키워드] 남겨주시면 알려드릴게요'로 궁금증→댓글을 유도해라.",
        "spine": [
            {"slot": "완성훅", "roles": ["완성"], "key": True},
            {"slot": "재료", "roles": ["사용중", "기타"]},
            {"slot": "과정", "roles": ["사용중"]},
            {"slot": "완성샷", "roles": ["완성"]},
            {"slot": "CTA", "roles": ["기타", "완성"]},
        ],
    },
    "kitchen_tool": {
        "label": "🧰 살림템/주방",
        "strategy": "이 영상은 살림템/주방도구다. 도구가 문제를 어떻게 해결하는지 기능을 화면으로 "
                    "실증해 보여줘라. 마지막 CTA는 '댓글에 [키워드] 남겨주시면 구매링크 보내드릴게요'.",
        "spine": [
            {"slot": "실물훅", "roles": ["완성"], "key": True},
            {"slot": "문제상황", "roles": ["문제", "기타"]},
            {"slot": "기능실증", "roles": ["사용중"], "key": True},
            {"slot": "결과", "roles": ["after", "완성"]},
            {"slot": "CTA", "roles": ["기타", "완성"]},
        ],
    },
    "beauty": {
        "label": "💄 뷰티",
        "strategy": "이 영상은 뷰티템이다. 완성된 룩·발색을 먼저 보여주고 before→after 대비로 효과를 "
                    "각인시켜라. 마지막 CTA는 '댓글에 [키워드] 남겨주시면 알려드릴게요'.",
        "spine": [
            {"slot": "완성룩훅", "roles": ["완성", "after"], "key": True},
            {"slot": "before", "roles": ["before", "문제"]},
            {"slot": "사용", "roles": ["사용중"]},
            {"slot": "after대비", "roles": ["after", "완성"]},
            {"slot": "CTA", "roles": ["기타", "완성"]},
        ],
    },
    "cleaning": {
        "label": "🧼 청소/생활",
        "strategy": "이 영상은 청소/생활템이다. 더러운 before로 훅을 열고 사용→깨끗한 after 반전으로 "
                    "임팩트를 줘라. 마지막 CTA는 '댓글에 [키워드] 남겨주시면 구매링크 보내드릴게요'.",
        "spine": [
            {"slot": "before훅", "roles": ["before", "문제"], "key": True},
            {"slot": "사용", "roles": ["사용중"]},
            {"slot": "after", "roles": ["after", "완성"], "key": True},
            {"slot": "반전강조", "roles": ["after", "완성"]},
            {"slot": "CTA", "roles": ["기타", "완성"]},
        ],
    },
    "generic": {
        "label": "✨ 범용",
        "strategy": "이 영상은 제품/결과물을 소개한다. 가장 센 장면으로 훅을 열고 핵심을 실증한 뒤 "
                    "결과를 보여줘라. 마지막 CTA는 '댓글에 [키워드] 남겨주시면 보내드릴게요'.",
        "spine": [
            {"slot": "강한장면훅", "roles": ["완성", "after"], "key": True},
            {"slot": "핵심실증", "roles": ["사용중"], "key": True},
            {"slot": "결과", "roles": ["완성", "after"]},
            {"slot": "CTA", "roles": ["기타", "완성"]},
        ],
    },
}
_DEFAULT_TYPE = "generic"

# 옛 캐시/job 호환(fail-open): 예전 key를 새 key로 흡수한다.
_VIDEO_TYPE_ALIASES = {"recipe_secret": "recipe", "product_reveal": "generic"}


def _normalize_video_type(vt):
    """임의 video_type 문자열 → 유효한 VIDEO_TYPES key. 옛 key는 에일리어스, 미지값은 기본."""
    if vt in VIDEO_TYPES:
        return vt
    vt = _VIDEO_TYPE_ALIASES.get(vt)
    return vt if vt in VIDEO_TYPES else _DEFAULT_TYPE


def _build_scene_spine(seg_map, video_type):
    """태깅된 장면(seg_map)을 카테고리 spine 슬롯 순서로 배치한다(장면 순서 확정).

    반환: [{slot, seg_id, scene_desc}, ...] — 슬롯 순서 그대로. 대본 생성이 이 순서를 고정으로 받는다.
    - 각 슬롯은 요구 roles(shot_role)·key(is_key 선호)에 맞는 seg를 인벤토리에서 뽑는다.
    - 이미 쓴 seg는 재사용 안 함(중복 화면 방지). 슬롯에 맞는 게 없으면 그 슬롯은 건너뛴다
      (빈 슬롯로 렌더가 깨지지 않게 — 뒤 슬롯이 이어 채운다).
    - 빈 인벤토리·미지 카테고리는 안전 폴백(크래시 금지)."""
    if not seg_map:
        return []
    vt = _normalize_video_type(video_type)
    spine_tmpl = VIDEO_TYPES[vt].get("spine") or VIDEO_TYPES[_DEFAULT_TYPE]["spine"]
    used = set()
    out = []

    def _pick(roles, want_key):
        # 1순위: 역할 일치 + (key 선호 시) is_key. 2순위: 역할만. 3순위: 아무 미사용 seg.
        cands = [s for sid, s in seg_map.items() if sid not in used]
        if not cands:
            return None
        pref = [s for s in cands if (s.get("shot_role") in roles)]
        if want_key:
            keyed = [s for s in pref if s.get("is_key")]
            if keyed:
                return min(keyed, key=lambda s: s.get("start", 0))
        if pref:
            return min(pref, key=lambda s: s.get("start", 0))
        return None  # 역할 불일치면 이 슬롯은 비운다(아무거나 억지로 안 넣는다)

    for slot in spine_tmpl:
        seg = _pick(slot.get("roles", []), slot.get("key", False))
        if seg is None:
            continue
        used.add(seg["seg_id"])
        out.append({"slot": slot["slot"], "seg_id": seg["seg_id"],
                    "scene_desc": seg.get("scene_desc", "")})
    # 슬롯 대부분이 비어도(태깅이 역할과 안 맞아도) 최소 CTA 슬롯엔 남은 장면 하나를 채워
    # 렌더가 완전히 비지 않게 한다. 아무것도 못 채웠으면 시간순 첫 장면 하나라도.
    if not out:
        first = min(seg_map.values(), key=lambda s: s.get("start", 0))
        out = [{"slot": spine_tmpl[-1]["slot"], "seg_id": first["seg_id"],
                "scene_desc": first.get("scene_desc", "")}]
    elif out[-1]["slot"] != spine_tmpl[-1]["slot"]:
        # 마지막 슬롯(CTA)이 못 채워졌으면 마지막 배치 슬롯을 CTA로 승격(끝=CTA 보장)
        out[-1] = {**out[-1], "slot": spine_tmpl[-1]["slot"]}
    return out


def _spine_order_block(spine):
    """스파인(고정 슬롯 순서+장면)을 대본 생성 프롬프트용 하드 제약 블록으로 렌더."""
    if not spine:
        return ""
    lines = ["[장면 스파인 — 이 순서·장면은 고정이다. 순서를 바꾸지 마라]"]
    for i, b in enumerate(spine, 1):
        lines.append(f"{i}. [{b['slot']}] {b['seg_id']} · 화면:{b.get('scene_desc','')}")
    lines.append("★위 슬롯 순서대로 비트를 만들고, 각 비트 seg_ids는 해당 슬롯의 장면을 쓴다. "
                 "장면에 안 보이는 걸 지어내지 말고 그 화면에 맞는 멘트만 써라. CTA는 마지막 슬롯에만.")
    return "\n".join(lines)

# ── 덩어리 믹스(2026-07-31 사장님 지시) ──────────────────────────────────────
# "믹스할 때 완전 뒤죽박죽으로 하지 마라. 1~3개 영상에서 훅이 좋은 부분을 쭉 이어서
#  가져오고 그 장면에 맞게 대본을 넣고 / 스토리 부분에서 좋은 영상 가져와서 넣고 /
#  CTA 부분 괜찮은 영상 가져와서 넣고. 단순하게."
#
# 왜 이게 두더지를 끝내나: 지금까지는 비트마다 여기저기서 조각을 긁어모아 붙였고,
# 모자라면 렌더가 아무 데나 때웠다(video_assemble:445-471). 화면을 **먼저 연속 덩어리로
# 확정**하면 (1) 화면이 튀지 않고 (2) 각 덩어리가 몇 초인지 알기 때문에 대사 길이를
# 초 단위로 못박을 수 있다 → 부족분 자체가 생기지 않는다.
BLOCK_MIX = os.getenv("BLOCK_MIX", "1") == "1"   # 0이면 옛 스파인 경로(즉시 롤백)

# 덩어리별 역할 우선순위(shot_role). 앞에 있을수록 좋다.
_BLOCK_ROLES = {
    "훅": ("문제", "before", "완성"),
    "스토리": ("사용중", "before", "after"),
    "CTA": ("완성", "after"),
}


def _seg_seq(sid):
    """'vid-12' → ('vid', 12). 형식이 아니면 (sid, 0)."""
    vid, _, n = (sid or "").rpartition("-")
    return (vid, int(n)) if vid and n.isdigit() else (sid, 0)


def _contiguous_runs(segs):
    """같은 소스 안에서 번호가 이어지는 구간 묶음 → [[seg,...], ...] (사장님 '쭉 이어서')."""
    runs, cur = [], []
    for s in sorted(segs, key=lambda s: _seg_seq(s["seg_id"])):
        v, n = _seg_seq(s["seg_id"])
        if cur:
            pv, pn = _seg_seq(cur[-1]["seg_id"])
            if v != pv or n != pn + 1:
                runs.append(cur); cur = []
        cur.append(s)
    if cur:
        runs.append(cur)
    return runs


def _context_runs(segs):
    """연속 구간을 **맥락이 바뀌는 지점**에서 끊는다(2026-07-31 사장님).

    "대본을 중심으로 맥락이 바뀌는 구간까지를 영상의 소스로 쓰고, 그 대본 길이만큼 바꿔 넣자."
    → 컷을 초로 잘라 맞추는 게 아니라, 원본이 한 가지 이야기를 하는 동안은 **통째로** 쓴다.
    맥락 경계 판정: shot_role이 바뀌거나, 인접 구간의 화면·변화 문구가 한 단어도 안 겹칠 때.
    """
    out = []
    for run in _contiguous_runs(segs):
        cur = [run[0]]
        for s in run[1:]:
            prev = cur[-1]
            role_changed = (s.get("shot_role") or "") != (prev.get("shot_role") or "")
            a = set(_claim_key(f"{prev.get('change') or ''} {prev.get('scene_desc') or ''}"))
            b = set(_claim_key(f"{s.get('change') or ''} {s.get('scene_desc') or ''}"))
            # 실측 교정: 둘 다(and) 요구했더니 이 소재에선 경계가 거의 안 걸려 스토리가
            # 21컷 26.5초로 뭉쳤다. 역할이 바뀌거나 화제가 안 겹치면 맥락 전환으로 본다.
            if role_changed or not (a & b):
                out.append(cur); cur = []
            cur.append(s)
        if cur:
            out.append(cur)
    return out


def _secs(segs):
    return sum(max(0.0, float(s.get("end") or 0) - float(s.get("start") or 0)) for s in segs)


def _pick_run(runs, roles, want, used, max_cuts=3, prefer_late=False):
    """원하는 길이(want초)에 가장 잘 맞으면서 역할이 어울리는 연속 구간을 고른다.

    점수 = 역할 일치 → **액션(변화) 포함** → 길이 부족분. 이미 쓴 seg는 뺀다.
    max_cuts: 컷 수 상한(2026-07-31 사장님 "30초면 6컷 정도, 액션 장면은 잘게 쪼개지 마라").
    반환: [seg,...] (want나 max_cuts를 채우면 멈춘다)."""
    best, best_key = [], None
    for run in runs:
        free = [s for s in run if s["seg_id"] not in used]
        if not free:
            continue
        # ★맥락 단위로 끊는다 — 초에 맞춰 중간에서 자르지 않는다(2026-07-31 사장님).
        #   "맥락이 바뀌는 구간까지를 소스로 쓰고, 그 대본 길이만큼 바꿔서 넣는다."
        #   그래서 여기서 고르는 건 '몇 초어치'가 아니라 **맥락 덩어리 하나**다.
        #   want는 자르는 기준이 아니라 어느 덩어리가 알맞은지 고르는 기준으로만 쓴다.
        for sub in _context_runs(free):
            hit = sum(1 for s in sub if s.get("shot_role") in roles) / max(1, len(sub))
            act = sum(1 for s in sub if (s.get("change") or "").strip()) / max(1, len(sub))
            take = sub[:max_cuts]                 # max_cuts는 폭주 방지용 상한일 뿐
            acc = _secs(take)
            # CTA는 소재 뒤쪽(완성·마무리)에서 가져와야 마무리처럼 보인다 → 늦은 구간 우대.
            late = -_seg_seq(take[-1]["seg_id"])[1] if prefer_late else 0
            key = (-round(hit, 2), late, -round(act, 2), abs(acc - want))
            if best_key is None or key < best_key:
                best, best_key = take, key
    return best


def _build_scene_blocks(seg_map, target_seconds):
    """화면을 훅/스토리/CTA **세 덩어리**로 먼저 확정한다. 각 덩어리는 연속 구간.

    반환: [{"name": 훅|스토리|CTA, "segs": [seg,...], "secs": float}, ...]
    비면 [] (호출부가 옛 경로로 폴백)."""
    if not seg_map:
        return []
    runs = _contiguous_runs(list(seg_map.values()))
    want = {"훅": max(2.5, target_seconds * 0.15),
            "스토리": max(6.0, target_seconds * 0.6),
            "CTA": max(2.5, target_seconds * 0.2)}
    # 폭주 방지 상한만 둔다. 실제 컷 수는 want(초)를 채우면 멈춘다 — 원본 컷이 짧은 소재
    # (0.6~1.7초)에서 개수로 끊으면 총 길이가 턱없이 모자란다(실측 6.7초).
    cuts = {"훅": 6, "CTA": 6, "스토리": 20}
    used, out = set(), []
    # 훅(앞) → CTA(뒤) → 스토리(남은 가운데). 스토리를 먼저 잡으면 재료를 다 먹어 CTA가
    # 빈다(실측). CTA는 prefer_late로 **소재 뒤쪽**에서 가져와 마무리처럼 보이게 한다.
    for name in ("훅", "CTA", "스토리"):
        segs = _pick_run(runs, _BLOCK_ROLES[name], want[name], used,
                         max_cuts=cuts[name], prefer_late=(name == "CTA"))
        # 맥락 덩어리 하나로는 대개 짧다(실측: 훅 1.5초=8자). 목표에 닿을 때까지
        # **맥락 덩어리 단위로** 더 이어 붙인다 — 덩어리 중간에서 자르는 일은 없다.
        if segs:
            used.update(s["seg_id"] for s in segs)
            # 덩어리 통째로만 붙이므로 목표를 넘길 수밖에 없다 → 80%에서 멈춰 과다를 줄인다
            # (실측: 조건 없이 채웠더니 목표 30초짜리가 42.2초가 됐다).
            # 훅·CTA는 짧아도 되니 최소 길이만 확보하고 더 안 먹는다 — 스토리 재료를 뺏으면
            # 가운데가 빈다.
            floor = want[name] * 0.8 if name == "스토리" else 2.5
            while _secs(segs) < floor:
                more = _pick_run(runs, _BLOCK_ROLES[name], want[name] - _secs(segs), used,
                                 max_cuts=cuts[name], prefer_late=(name == "CTA"))
                if not more:
                    break
                used.update(s["seg_id"] for s in more)
                segs = segs + more
        if not segs:
            continue
        used.update(s["seg_id"] for s in segs)
        out.append({"name": name, "segs": segs, "secs": round(_secs(segs), 1)})
    order = {"훅": 0, "스토리": 1, "CTA": 2}
    out.sort(key=lambda b: order[b["name"]])
    return out


# ── 리라이트 믹스(2026-07-31, 레퍼런스 프로그램 역분석 결과) ─────────────────
# 레퍼런스 완성품을 프레임으로 뜯어보니 자기 자막이 **그 순간 원본 자막을 바꿔 말한 것**이었다:
#   "밖에 나가지 마세요"→"쿨링패치 그냥 버렸나요" / "변하는데"→"말랑말랑 젤리 같아요"
#   "거품처럼 나오더니"→"이거 뿌리는 순간" / "만드는 방법은"→"신기한 슬라임 완성"
# 즉 **원본 타임라인을 뼈대로 두고 문장만 갈아끼운다.** 화면을 새로 찾을 필요가 없다 —
# 원본이 이미 그 말에 그 화면을 붙여놨기 때문이다. 우리는 반대로 대본을 새로 쓰고 화면을
# 찾아 붙여서, 못 찾으면 어긋나고 모자라면 때웠다(며칠간의 두더지 잡기).
REWRITE_MIX = os.getenv("REWRITE_MIX", "1") == "1"   # 0이면 옛 경로(덩어리/스파인)
_MIN_LINE_SECS = 1.2      # 이보다 짧은 구간은 옆과 합친다(한 줄이 3자짜리가 되는 걸 막는다)
# 문장이 끝났다고 볼 종결(한국어 구어 자막은 마침표가 자주 없다 → 어미로 판정).
_SENT_END = ("요", "다", "죠", "네", "까", "군", "걸", "야", "임", "함", "죠?", "래요", "거든요")


def _ends_sentence(text):
    """원본 자막 한 조각이 **문장을 끝냈나**. 구두점이 없어도 종결어미로 판정한다."""
    t = (text or "").strip().rstrip("…~")
    if not t:
        return False
    if t[-1] in ".!?。":
        return True
    return t.rstrip("!?.").endswith(_SENT_END)


def _pick_timeline(seg_map, target_seconds):
    """쓸 구간을 **원본 시간순 그대로** 고른다(레퍼런스 방식).

    - 가장 재료가 많은 소스를 뼈대로 삼아 시간순으로 담는다(원본 편집 리듬을 그대로 탄다).
    - 목표에 못 미치면 다른 소스의 구간을 이어 붙인다(레퍼런스도 소스를 오간다).
    - 너무 짧은 구간은 옆과 합쳐 한 줄이 지나치게 짧아지지 않게 한다.
    반환: [[seg,...], ...] — 바깥 리스트가 '한 줄'이 붙을 단위."""
    if not seg_map:
        return []
    by_vid = {}
    for s in seg_map.values():
        by_vid.setdefault(s.get("video_id"), []).append(s)
    order = sorted(by_vid, key=lambda v: -len(by_vid[v]))     # 재료 많은 소스부터
    picked, acc = [], 0.0
    for k, vid in enumerate(order):
        segs = sorted(by_vid[vid], key=lambda s: _seg_seq(s["seg_id"])[1])
        # ★소스 전환 구멍 막기(2026-07-31 사장님 "막 섞으면 CTA 화면이 맨 앞으로 갈 수 있잖아").
        #   소스 안 순서는 코드가 지키지만, A를 다 쓰고 B를 이어 붙이면 **A의 마무리 화면이
        #   우리 영상 한가운데** 온다. 마지막 소스가 아니면 꼬리의 '완성' 컷을 잘라낸다 —
        #   마무리처럼 보이는 그림은 끝에서만 나와야 한다.
        if k < len(order) - 1:
            while segs and segs[-1].get("shot_role") in ("완성", "after"):
                segs.pop()
        # ★반대 방향도 막는다(2026-07-31 실측 job fd8bd0f2a5c1): 두 번째 이후 소스의 **도입부**
        #   (문제·before = 더러운 상태)가 우리 영상 후반에 끼면 "깔끔하게 유지" 대사에
        #   "조리대에 기름때가 지저분하다" 화면이 붙는다. 문제 화면은 앞에서만 나와야 한다.
        if k > 0:
            while segs and segs[0].get("shot_role") in ("문제", "before"):
                segs.pop(0)
        for s in segs:
            if acc >= target_seconds:
                break
            picked.append(s)
            acc += _secs([s])
        if acc >= target_seconds:
            break
    return _group_by_sentence(picked)


def _group_by_sentence(picked):
    """seg 리스트를 '원본 대사 한 문장이 시작~끝나는 구간'으로 묶는다(2026-07-31 사장님).

    _pick_timeline과 _build_source_sentence_sets(→_pick_slot_groups) 둘 다 이 그룹핑을
    재사용한다 — 세트 정의는 화면을 어떤 순서로 고르든(시간순이든 Gemini 판단이든)
    동일해야 하기 때문. 단 _build_source_sentence_sets는 **소스별로 따로** 호출해
    다른 소스와 섞이지 않게 한다(2026-08-01, F1 수정)."""
    groups, cur = [], []
    for s in picked:
        cur.append(s)
        if _ends_sentence(s.get("text")) and _secs(cur) >= _MIN_LINE_SECS:
            groups.append(cur); cur = []
    if cur:
        (groups[-1].extend(cur) if groups else groups.append(cur))
    return groups


_SET_SEQ_SCHEMA = {
    "type": "object",
    "properties": {
        "order": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["order"],
}


def _build_source_sentence_sets(seg_map):
    """seg_map을 **소스별 시간순으로 먼저** 문장세트로 묶는다(2026-08-01, F1/F2 재설계).

    옛 _pick_slot_sequence는 Gemini에게 seg 낱개를 자유 재정렬시킨 *뒤에* 문장으로 묶었다
    (_pick_slot_groups: seq → group). 그런데 _group_by_sentence는 "리스트에서 옆에 붙은
    seg는 같은 원본 문장이다"를 전제로 한다 — 옛 _pick_timeline(소스별 시간순)에서는 항상
    참이었지만, Gemini가 소스를 넘나들며 자유 재정렬한 리스트에서는 거짓이 될 수 있다
    (예: [a1, b3, a2] — a1+a2가 원래 한 문장인데 사이에 b3가 끼면 그룹핑이
    [a1, b3]를 한 세트로 묶어버린다 = 서로 다른 소스가 섞인 프랑켄 문장).

    그래서 순서를 뒤집는다: 그룹핑을 **먼저**, 소스별로 각자 자기 시간순 안에서만 한다
    (다른 소스와 절대 안 섞는다) → Gemini에게는 다 만들어진 세트를 어떤 순서로/얼마나
    쓸지만 묻는다(_pick_slot_groups). 이러면 세트 내부는 항상 한 소스만 담겨 프랑켄
    문장이 구조적으로 불가능하다(세트끼리 소스가 섞이는 건 허용 — 그건 완성된 문장
    두 개를 나란히 놓는 것뿐이라 문제 없음).

    반환: [{"set_id": str, "video_id": str, "segs": [seg,...], "secs": float}, ...]
    set_id는 세트의 첫 seg_id를 그대로 쓴다(Gemini 프롬프트에서 참조할 식별자로 충분하고,
    seg_id 자체가 이미 사람이 읽을 수 있는 값이라 별도 채번이 필요 없다)."""
    by_vid = {}
    for s in seg_map.values():
        by_vid.setdefault(s.get("video_id"), []).append(s)
    sets = []
    for vid in by_vid:
        segs = sorted(by_vid[vid], key=lambda s: _seg_seq(s["seg_id"])[1])
        for g in _group_by_sentence(segs):
            sets.append({"set_id": g[0]["seg_id"], "video_id": vid, "segs": g,
                         "secs": round(_secs(g), 1)})
    return sets


_MIN_SET_SECS = 4.0     # 비트 하나가 이보다 짧으면 할 말이 없다(실측 근거는 _cap_sets 참조)

# 모델이 할 말이 없을 때 뱉는 자리표시자들. 실측은 `filler`(job e99d0e8e3e02, 6개)지만
# 같은 계열이 몇 개 더 있어 함께 막는다. 역할 이름을 그대로 적은 것도 자리표시자다.
_PLACEHOLDER_NARRATIONS = {"filler", "placeholder", "tbd", "n/a", "none", "null",
                           "...", "..", "-", "내용", "대사", "빈칸"}


# 대본에서 인정하는 역할들(모델이 한글·영문 아무거나 쓴다 — 낱말 포함으로 본다).
# 여기 없는 역할(`filler` 등)은 "할 말이 없어 만든 자리"라 스토리에 기여하지 않는다.
_KNOWN_ROLE_WORDS = ("훅", "hook", "문제", "problem", "페인", "pain", "해결", "solution",
                     "결과", "result", "resolution", "반전", "실용", "혜택", "benefit",
                     "장점", "경험", "story", "전개", "process", "과정", "마무리", "cta")


def _is_known_role(role):
    r = (role or "").strip().lower()
    return any(w in r for w in _KNOWN_ROLE_WORDS)


def _dedupe_cta_beats(beats):
    """CTA는 **하나뿐**이다 — 여러 개면 마지막만 남긴다(2026-08-01).

    실측(job e99d0e8e3e02 재현): 가운데 비트를 잘라내자 CTA 비트 둘이 나란히 붙었고,
    한 후보는 "더 자세한 내용은 댓글로 물어봐주세요"가 **글자까지 똑같이** 두 번 나왔다.
    영상 끝에서 한 번 부르는 게 CTA인데 두 번 부르면 그냥 반복이다(핸드오프 백로그의
    '중간 CTA 중복'과 같은 건). 화면은 `_assign_timeline`이 다시 나눠 주므로 안 잃는다.
    """
    idx = [i for i, b in enumerate(beats or []) if _is_cta(b)]
    if len(idx) < 2:
        return beats
    keep_cta = idx[-1]
    return [b for i, b in enumerate(beats) if i == keep_cta or i not in idx]


def _trim_beats_to_slots(beats, n):
    """비트 수를 슬롯(세트) 수에 맞춘다 — 프롬프트가 부탁한 걸 코드가 확인한다.

    실측(job e99d0e8e3e02·af0e40746fe1): 세트가 5개라 "비트를 정확히 5개 만들어라"라고
    요구했는데 모델은 11개·7개를 만들고 남는 자리를 `filler` 역할로 채웠다. 자리표시자
    글자는 `_drop_placeholder_beats`가 막지만, 글자만 그럴듯하게 바꿔 오면(실측:
    "티슈로 닦아내는 장면" — 대사가 아니라 화면 설명문) 그대로 나간다.
    프롬프트로 부탁만 하고 코드로 확인하지 않으면 지켜지는지 알 수 없다는, 이 파일이
    반복해서 배운 교훈을 여기에도 적용한다.

    버리는 순서: ①정의 밖 역할(`filler` 등) 중 짧은 것 → ②그래도 많으면 훅·CTA가 아닌
    것 중 짧은 것. 훅과 CTA는 이야기의 처음과 끝이라 끝까지 남긴다.
    """
    if n <= 0 or len(beats) <= n:
        return beats
    keep = list(beats)
    while len(keep) > n:
        pool = [i for i, b in enumerate(keep) if not _is_known_role(b.get("role"))]
        if not pool:
            pool = [i for i, b in enumerate(keep)
                    if not _is_cta(b) and i != 0]
        if not pool:
            break
        drop = min(pool, key=lambda i: len((keep[i].get("narration") or "")))
        keep.pop(drop)
    return keep


def _drop_placeholder_beats(beats):
    """대사 자리에 자리표시자가 들어온 비트를 빼낸다(2026-08-01 실사고).

    실측(job e99d0e8e3e02·af0e40746fe1): 두 건 다 role이 `hook·problem·solution·
    filler×N·CTA` 모양이었다. 코드엔 `filler`를 만드는 곳이 없다 — **비트를 정확히 N개
    만들라고 요구했는데 모델이 그보다 많이 만들며 남는 자리를 `filler`로 채운 것**이고,
    그게 그대로 대본이 돼 사장님 화면까지 갔다(fit=1, 1.5초짜리 비트 6개).

    `narration`이 `filler` 같은 자리표시자거나 자기 role 이름 그대로면 대사가 아니다.
    억지로 살리지 않고 뺀다 — 화면은 `_assign_timeline`이 남은 비트에 다시 나눠 주므로
    잃지 않는다. 판정을 좁게 잡은 이유: "끝!"처럼 짧아도 진짜 대사인 것을 지우면 안 된다.
    """
    out = []
    for b in beats or []:
        txt = (b.get("narration") or "").strip()
        role = (b.get("role") or "").strip()
        if txt.lower() in _PLACEHOLDER_NARRATIONS or (role and txt.lower() == role.lower()):
            continue
        out.append(b)
    return out


def _cap_sets(sets, target_seconds):
    """세트가 너무 잘게 쪼개졌으면 **같은 소스의 이웃끼리 합친다**(2026-08-01 실사고).

    ※ 이건 **예방 가드지 관측된 사고 원인이 아니다**(2026-08-01 자기정정). `filler` 사고
    (job e99d0e8e3e02)를 처음엔 "세트가 11개라 무리한 개수를 강요했다"로 진단했는데,
    실제 세트는 5개였고 모델이 **요구받은 5개를 넘겨 11개를 뱉으며** 남는 자리를 채운
    것이었다. 원인은 `_drop_placeholder_beats`가 막는다.

    다만 세트가 목표 길이 대비 지나치게 잘게 쪼개지면(비트당 몇 초짜리) 모델에게 할 말이
    없는 자리를 강요하게 되는 건 사실이라, 묻기 전에 개수를 줄여 둔다 — 30초면 최대
    7세트(비트당 4.3초).
    합치는 대상은 **같은 소스의 붙어 있는 세트**뿐이라(원본에서도 연달아 나오던 문장들)
    합쳐도 이야기가 튀지 않는다. 짧은 쌍부터 합쳐 긴 세트는 건드리지 않는다.
    """
    if not sets or not target_seconds:
        return sets
    # ★1소스는 목표가 소재 천장(보통 18~20초)이라 4초 기준을 그대로 쓰면 4세트로 눌리는데,
    #   plan_gate는 최소 5비트를 요구한다 — 통과 자체가 불가능해진다(2026-08-04 실측:
    #   목표 18초 → 4세트 → "비트가 2개뿐" 반려). 짧은 목표에선 비트당 하한을 낮춰
    #   최소 5비트를 만들 수 있게 한다(컷이 1~2초짜리라 5비트도 충분히 할 말이 있다).
    from shopping_shorts.plan_gate import _MIN_BEATS as _GATE_MIN_BEATS
    min_set = _MIN_SET_SECS
    if target_seconds < _MIN_SET_SECS * _GATE_MIN_BEATS:           # 20초 미만
        min_set = max(2.0, target_seconds / _GATE_MIN_BEATS)
    cap = max(_GATE_MIN_BEATS, min(_MAX_BEATS, int(target_seconds // min_set)))
    if len(sets) <= cap:
        # 줄일 건 없다 — 다만 게이트 최소비트에 못 미치면 긴 세트를 쪼개 채운다.
        return _split_sets_to_min(sets, _GATE_MIN_BEATS)
    out = list(sets)
    while len(out) > cap:
        pairs = [i for i in range(len(out) - 1)
                 if out[i]["video_id"] == out[i + 1]["video_id"]]
        if not pairs:
            break                      # 소스가 번갈아 있으면 더 합칠 수 없다
        i = min(pairs, key=lambda k: out[k]["secs"] + out[k + 1]["secs"])
        a, b = out[i], out[i + 1]
        out[i:i + 2] = [{"set_id": a["set_id"], "video_id": a["video_id"],
                         "segs": a["segs"] + b["segs"],
                         "secs": round(a["secs"] + b["secs"], 1)}]
    return _split_sets_to_min(out, min(cap, _GATE_MIN_BEATS))


def _split_sets_to_min(sets, min_count):
    """세트가 게이트 최소비트보다 적으면 **가장 긴 세트를 쪼개** 개수를 맞춘다(2026-08-04).

    _cap_sets는 줄이기만 해서, 1소스처럼 문장세트가 애초에 4개뿐이면(실측: 20초 소재 →
    4세트) 최소 5비트를 영원히 못 만든다. 세그가 2개 이상인 가장 긴 세트를 반으로 나눈다
    — 같은 소스의 연속 구간을 나누는 것이라 이야기가 튀지 않는다. 더 못 쪼개면 그대로 둔다.
    """
    out = [dict(s) for s in (sets or [])]
    # ★1소스일 때만 쪼갠다. 다소스는 세트가 소스 경계를 뜻하므로 쪼개면 교차믹스 규칙이
    #   깨진다(실측: test_pick_slot_groups_f1_no_cross_source_fragment_mixing 회귀).
    #   애초에 다소스는 재료가 넉넉해 최소비트가 모자랄 일이 없다(부족 2%).
    if len({s.get("video_id") for s in out}) != 1:
        return out
    guard = 0
    while len(out) < min_count and guard < 8:
        guard += 1
        cand = [i for i, s in enumerate(out) if len(s.get("segs") or []) >= 2]
        if not cand:
            break
        i = max(cand, key=lambda k: out[k]["secs"])
        s = out[i]
        segs = s["segs"]
        half = len(segs) // 2
        a_segs, b_segs = segs[:half], segs[half:]

        def _sum(ss):
            tot = 0.0
            for x in ss:
                if isinstance(x, dict):
                    tot += max(0.0, float(x.get("end") or 0) - float(x.get("start") or 0))
            return round(tot, 1)

        a_secs = _sum(a_segs) or round(s["secs"] * half / max(1, len(segs)), 1)
        out[i:i + 1] = [
            {"set_id": s["set_id"], "video_id": s["video_id"],
             "segs": a_segs, "secs": a_secs},
            {"set_id": (b_segs[0].get("seg_id") if isinstance(b_segs[0], dict)
                        else f'{s["set_id"]}b'),
             "video_id": s["video_id"], "segs": b_segs,
             "secs": round(max(0.0, s["secs"] - a_secs), 1)},
        ]
    return out


def _set_seq_prompt(sets, target_seconds):
    lines = ["아래는 두 영상에서 뽑은 '한 문장이 시작~끝나는' 장면 세트들이다. 각 세트의 "
             "역할(무슨 내용인지)을 보고, 하나의 자연스러운 스토리로 이어지도록 몇 개를 "
             "고를지와 순서를 정하라. 같은 제품이라도 두 영상이 서로 다른 훅·전개를 가질 "
             "수 있으니, 소스에 얽매이지 말고 내용 흐름으로 판단하라.",
             f"목표 영상 길이는 약 {target_seconds}초다 — 총 길이가 거기 가깝게 되도록 "
             "필요한 세트만 골라 순서를 정하라. 세트를 전부 다 쓸 필요는 없다.",
             # ★2026-08-01 라이브 실측(job af0e40746fe1): s0 세트 합 16.9초 · s1 합 30.2초에
             #   목표가 30초라, s1 하나만으로 예산이 정확히 차서 Gemini가 s0를 통째로 버렸다
             #   (추천 후보까지 s1 단독). 버그가 아니라 예산 산수인데, 사장님이 영상 두 개를
             #   담은 이유는 같은 제품을 **다른 각도로** 보여주려는 것이라 결과가 기대와 다르다.
             #   그래서 "예산 안에서 알아서"에 영상 커버리지를 한 줄 더 얹는다.
             "★단 **영상마다 최소 한 세트씩은 반드시 골라라** — 여러 영상을 담은 이유는 같은 "
             "제품을 다른 각도로 보여주기 위해서다. 한 영상만으로 길이가 차더라도 나머지 "
             "영상에서 가장 좋은 세트를 넣고, 대신 덜 중요한 세트를 빼서 길이를 맞춰라.",
             "세트 하나는 통째로 쓰거나 안 쓰거나만 가능하다 — 세트를 쪼개거나 "
             "세트 안 순서를 바꾸거나 지어내지 마라."]
    for st in sets:
        segs = st["segs"]
        said = " ".join((s.get("text") or "").strip() for s in segs).strip()
        desc = " / ".join((s.get("scene_desc") or "").strip() for s in segs)
        lines.append(f"- [{st['set_id']}] {st['secs']}초 · {desc} · 원본 대사: {said}")
    lines.append("\n반드시 JSON {\"order\": [set_id, ...]} 형식으로만 답하라.")
    return "\n".join(lines)


def _filter_misplaced_sets(chosen):
    """완성/문제 컷의 **자리**를 바로잡는다 — 버리지 않고 옮긴다(2026-08-01 개정).

    _pick_timeline은 '완성 컷은 끝에서만, 문제 컷은 앞에서만'을 코드로 강제하지만 그건
    Gemini 실패 시의 폴백 경로에만 있었다. Gemini가 정상 응답을 준 주력 경로는 프롬프트로
    "부탁"만 하고 코드 검증이 없었다 — 이 파일이 이미 배운 교훈(요구만 하고 확인 안 하면
    지켜지는지 알 수 없다)과 같은 실패 패턴이라, 세트 단위로 같은 두 규칙을 재적용한다.

    판정(2026-08-01 실측으로 좁힘): 끝세트는 **마지막 seg가 `완성`**이거나 세트 전체가
    완성/after일 때만. `after`는 영상 중간에도 나오는 태그라 그것만으로 끝세트로 몰면
    한 소스가 통째로 사라진다(실측 lens_youtube_1f60rye). 도입세트도 같은 비대칭.

    ★처방을 '제거'에서 '이동'으로 바꾼 이유(2026-08-01, job 9c2076e18252):
    잘라내기는 규칙은 지키지만 **재료를 버린다**. 실측에서 13.0초짜리 9세그 세트(s1-4,
    끝이 완성×2)가 통째로 잘려 세트 총 35.5초 중 3분의 1이 날아갔고, 대본이 3비트로
    쪼그라들며 두 번째 영상은 CTA 한 컷만 남았다. 규칙이 요구하는 건 "결말이 중간에
    오지 마라"이지 "결말을 버려라"가 아니다 — **맨 뒤로 옮기면** 규칙도 지키고 재료도
    산다(도입세트는 맨 앞으로). 상대 순서는 그대로 둬 Gemini가 정한 흐름을 최대한 보존한다.
    """
    openings, middles, endings = [], [], []
    for st in chosen:
        segs = st["segs"]
        if not segs:
            continue
        roles = [s.get("shot_role") for s in segs]
        is_ending = roles[-1] == "완성" or all(r in ("완성", "after") for r in roles)
        is_opening = roles[0] == "문제" or all(r in ("문제", "before") for r in roles)
        if is_ending and not is_opening:
            endings.append(st)
        elif is_opening and not is_ending:
            openings.append(st)
        else:
            middles.append(st)          # 둘 다거나 둘 다 아니면 자리를 안 옮긴다
    return openings + middles + endings


# 슬롯 소스 태그(2026-08-01, 폴백 가시화) — _pick_slot_groups가 어느 경로로 결과를
# 만들었는지 표시한다. 이 파일 스타일대로 enum 대신 평범한 문자열 상수로 정의한다
# (shot_role의 "완성"/"after" 등과 같은 선례).
SLOT_SOURCE_GEMINI = "gemini"                          # Gemini 응답을 그대로 사용
SLOT_SOURCE_FALLBACK_EMPTY_ORDER = "fallback_empty_order"        # Gemini 응답에 유효한 세트가 0개
SLOT_SOURCE_FALLBACK_FILTERED_EMPTY = "fallback_filtered_empty"  # F5 필터가 고른 세트를 전부 제거
SLOT_SOURCE_EMPTY_INPUT = "empty_input"                # seg_map/sets 자체가 비어 애초에 할 게 없었음


def _slot_info(sets, chosen, kept):
    """슬롯 선택이 무엇을 버렸는지 남긴다(2026-08-01 리뷰 G3, 기록만·동작 불변).

    slot_source는 필터가 **전부** 걸러낸 경우만 표시했다 — 4세트 중 1~2개만 잘리는
    **부분 제거는 아무 흔적이 없었다**. `after` 실사고(두 영상 담았는데 한 영상만 나감)가
    바로 그 종류였고, 발견도 코드가 아니라 사장님 눈이었다. 그래서 세 숫자를 남긴다:
    무엇이 잘렸나(filtered) · 소스별로 몇 세트씩 채택됐나(picked_by_source) · 애초에
    소스별 세트가 몇 개였나(sets_by_source). 마지막 둘의 대조가 "담은 영상을 다 쓰는가"
    (G1)를 판정하는 재료가 된다.
    """
    def _by_src(items):
        out = {}
        for st in items or []:
            out[st["video_id"]] = out.get(st["video_id"], 0) + 1
        return out

    kept_ids = {st["set_id"] for st in kept or []}
    return {
        "sets_total": len(sets or []),
        "sets_by_source": _by_src(sets),
        "chosen": len(chosen or []),
        "kept": len(kept or []),
        "filtered": [st["set_id"] for st in (chosen or []) if st["set_id"] not in kept_ids],
        "picked_by_source": _by_src(kept),
        "sources_unused": sorted(set(_by_src(sets)) - set(_by_src(kept))),
    }


def _pick_slot_groups(seg_map, target_seconds=None, call=None):
    """소스별로 먼저 확정한 문장세트(_build_source_sentence_sets)를 Gemini에게 주고,
    스토리에 맞는 세트만 골라 순서를 정하게 한다(2026-08-01, F1/F2/F3 재설계).

    build_scene_first_plan이 _pick_timeline 대신 부르는 진입점. 반환은
    (groups, slot_source) 튜플(2026-08-01, 폴백 가시화 — 사장님 지적: 폴백이 조용히
    일어나면 품질이 눈에 안 띄게 깎여도 알 방법이 없다) — groups는 _pick_timeline과
    동일한 [[seg,...], ...], slot_source는 어느 경로로 만들어졌는지 나타내는 문자열
    (SLOT_SOURCE_* 상수 중 하나). 하류(_rewrite_block/_assign_timeline)는 groups의
    seg dict만 읽으므로 세트 메타(set_id 등)는 반환 전에 벗겨낸다.

    Gemini가 세트 일부만 고르면(예산 안에서) 그 서브셋을 그대로 존중한다 — 옛
    _pick_slot_sequence처럼 안 고른 걸 뒤에 강제로 보충하지 않는다(그러면 예산을 준 의미가
    없어진다). 응답이 비었거나(order 없음) 알 수 없는 id만 있어 유효한 세트가 0개면,
    안전장치 없는 전체 이어붙이기 대신 **_pick_timeline로 직접 폴백**한다 — 완성/문제
    컷 트리밍과 target_seconds 캡을 이미 갖춘, 검증된 경로다(slot_source는
    fallback_empty_order).

    Gemini가 유효한 세트를 골랐더라도 그 순서를 그대로 믿지 않는다(F5, 2026-08-01) —
    _filter_misplaced_sets로 완성/문제 컷 위치를 다시 검증한다. 이 필터가 전부 걸러내면
    (골랐던 세트가 전부 규칙 위반) 마찬가지로 _pick_timeline 폴백으로 떨어진다
    (slot_source는 fallback_filtered_empty). seg_map/sets가 애초에 비어 있으면
    Gemini를 부르지도 못했다는 뜻이라 별도 태그(empty_input)를 쓴다."""
    if not seg_map:
        return [], SLOT_SOURCE_EMPTY_INPUT, _slot_info([], [], [])
    all_sets = _build_source_sentence_sets(seg_map)
    sets = _cap_sets(all_sets, target_seconds)
    if not sets:
        return [], SLOT_SOURCE_EMPTY_INPUT, _slot_info(all_sets, [], [])
    caller = call or _vault_call
    resp = caller(_set_seq_prompt(sets, target_seconds), _SET_SEQ_SCHEMA)
    order = (resp or {}).get("order") if isinstance(resp, dict) else None
    by_id = {st["set_id"]: st for st in sets}
    chosen = []
    seen = set()
    if order:
        for sid in order:
            if sid in by_id and sid not in seen:
                chosen.append(by_id[sid])
                seen.add(sid)
    if not chosen:
        return (_pick_timeline(seg_map, target_seconds), SLOT_SOURCE_FALLBACK_EMPTY_ORDER,
                _slot_info(sets, [], []))
    kept = _filter_misplaced_sets(chosen)
    if not kept:
        return (_pick_timeline(seg_map, target_seconds), SLOT_SOURCE_FALLBACK_FILTERED_EMPTY,
                _slot_info(sets, chosen, []))
    return [st["segs"] for st in kept], SLOT_SOURCE_GEMINI, _slot_info(sets, chosen, kept)


_ALT_SEQ_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {"type": "array", "items": {"type": "string"}},
        },
    },
    "required": ["stories"],
}


def _alt_seq_prompt(sets, chosen_ids, target_seconds, n_alt):
    """이미 쓴 조합과 **다른 이야기**를 n_alt개 짜달라는 프롬프트(v4 개선, 2026-08-02).

    왜 모델에게 맡기나: 코드가 조합하면 시간순·소스커버리지 같은 **기계적 규칙**은
    지킬 수 있어도 "이야기가 이어지는가"를 못 본다(사장님 지적: "흐름이 어색하지 않아야
    하는데 가능한 거야?"). 맥락 판단은 모델만 할 수 있다.

    ★기존 `_set_seq_prompt`는 **한 글자도 안 건드린다** — 1벌째(=v3와 동일)를 만드는
      프롬프트라, 손대면 "3개 중 1개는 그대로 둔다"는 약속이 깨진다. 그래서 별도 호출."""
    used = ", ".join(chosen_ids)
    lines = [f"아래는 여러 영상에서 뽑은 '한 문장이 시작~끝나는' 장면 세트들이다.",
             f"이미 **[{used}]** 조합으로 영상 하나를 만들었다.",
             f"같은 재료로 **그것과 다른 이야기 {n_alt}개**를 더 짜라.",
             "",
             "지켜야 할 것:",
             # ★길이를 세게 못박는다(2026-08-02 실측): "가깝게"만 적었더니 3세트 15~20초로
             #   벌0(4세트 27.8초)보다 크게 짧게 나왔다. 짧으면 렌더에서 화면이 모자라
             #   프리즈가 나거나 대본이 빈약해진다. 세트 **개수**로 하한을 준다 —
             #   초 단위로 요구하면 모델이 길이를 어림잡느라 더 부정확하다.
             f"· 각 이야기는 목표 {target_seconds}초를 채워야 한다 — **세트를 최소 "
             f"{max(1, len(chosen_ids))}개** 골라라(그보다 적으면 영상이 너무 짧아진다).",
             "· **이야기가 자연스럽게 이어져야 한다** — 세트를 남는다고 아무렇게나 끼우지 마라.",
             "  훅(관심 끌기) → 전개 → 마무리 흐름이 말이 돼야 한다.",
             "· **영상마다 최소 한 세트씩** 골라라(여러 영상을 담은 이유는 같은 제품을 "
             "다른 각도로 보여주기 위해서다).",
             # ★"3연속 금지"만 적었더니 1개씩 번갈라는 뜻으로 읽혀 리듬이 잘게 쪼개졌다.
             #   사장님: "A1 A2 B1 B2 A3 A4 이런 정도는 괜찮다" — 한 영상에서 두 컷을
             #   연달아 보여주면 그 영상의 맥락이 살고, 그다음 다른 영상으로 넘어가면
             #   새 각도가 된다. 1개씩 번갈면 오히려 정신없다.
             "· **한 영상을 1~2개씩 쓰고 다른 영상으로 넘어가라** — `A A B B A A`처럼 "
             "덩어리로 번갈아도 좋다. 다만 **같은 영상을 3연속 이상 붙이지는 마라**"
             "(한 영상만 오래 나오면 시청자가 '비슷한 영상'으로 느껴 나머지를 담은 의미가 없다).",
             # ★첫 장면은 기억에 가장 많이 남는 자리다(사장님). 원본 첫 세트로 시작하면
             #   원본과 똑같이 시작하는 셈이고, 후보끼리도 첫인상이 겹친다(실측: 세 벌 다 A1).
             "· **첫 세트를 원본 맨 앞 세트로 시작하지 마라** — 원본과 똑같이 시작하면 "
             "베낀 티가 나고 첫인상이 밋밋하다. 눈길을 끄는 다른 장면으로 열어라.",
             "· 세트는 통째로 쓰거나 안 쓰거나만 가능하다 — 쪼개거나 세트 안 순서를 바꾸지 마라.",
             f"· 위에 쓴 조합과 **다른 각도**로 짜라(다른 세트로 시작하거나, 다른 영상을 "
             "중심에 두거나).",
             "",
             "세트 목록:"]
    for st in sets:
        segs = st["segs"]
        said = " ".join((s.get("text") or "").strip() for s in segs).strip()
        desc = " / ".join((s.get("scene_desc") or "").strip() for s in segs)
        lines.append(f"- [{st['set_id']}] ({st['video_id']}) {st['secs']}초 · {desc} · "
                     f"원본 대사: {said}")
    lines.append(f"\n반드시 JSON {{\"stories\": [[set_id, ...], ...]}} 형식으로 "
                 f"**{n_alt}개**를 답하라.")
    return "\n".join(lines)


def _sort_sets_in_story_order(picked, keep_order=False):
    """세트끼리의 순서를 정한다.

    ★v4의 실패(2026-08-02, job 636dd36cf2db): 정렬 키가 `(video_id, 시각)`이라 소스가
      1차 기준이 돼 **A가 전부 나온 뒤 B가 전부 나왔다**(패턴 `AAAAAABBBBBBBB`).
      시청자에겐 "영상 두 개를 앞뒤로 이어붙인 것"으로 보인다 — 같은 제품을 다른 각도로
      보여주려고 두 개를 담은 의미가 사라진다.

    ★v5(2026-08-02): 그런데 실측해보니 **모델은 이미 교차해서 준다**
      (`s1-1 → s0-12 → s0-9 → s1-7`). 그걸 이 함수가 소스별로 뭉쳐 덮어쓰고 있었다 —
      맥락을 보라고 모델을 불러놓고 그 결과를 코드가 뭉갠 꼴이다.
      → `keep_order=True`면 **모델이 정한 순서를 그대로 두고**, 같은 소스 안 시간
        역전만 바로잡는다(그 불변식은 계속 지킨다).

    `keep_order=False`(코드 조합 경로)는 종전대로 소스별 시간순으로 세운다 — 그쪽은
    애초에 순서 개념이 없는 '고르기'만 하므로 코드가 정해줘야 한다."""
    if len(picked) < 2:
        return list(picked)
    if not keep_order:
        return sorted(picked, key=lambda st: (st["video_id"], _seg_seq(st["set_id"])[1]))
    # 모델 순서 존중: 자리는 그대로 두고, **같은 소스끼리만** 시간순으로 교환한다.
    # (자리를 옮기지 않으므로 모델이 만든 A/B 교차 리듬이 보존된다.)
    out = list(picked)
    by_src = {}
    for i, st in enumerate(out):
        by_src.setdefault(st["video_id"], []).append(i)
    for vid, idxs in by_src.items():
        ordered = sorted((out[i] for i in idxs),
                         key=lambda st: _seg_seq(st["set_id"])[1])
        for slot, st in zip(idxs, ordered):
            out[slot] = st
    return out


def _covers_all_sources(picked, sets):
    """담은 영상마다 최소 한 세트씩 들어갔는가(_set_seq_prompt가 A에 요구하는 규칙)."""
    return {st["video_id"] for st in picked} >= {st["video_id"] for st in sets}


def _build_variant(base, rest, sets, want, prefer_rest):
    """세트를 골라 한 '벌'을 만든다 — 순서는 원본 시간순으로 강제한다.

    prefer_rest=True면 **안 쓰인 세트(rest)를 먼저** 담는다(= 버려지던 이야기를 살린다).
    모자라면 base에서 채우고, 소스 커버리지가 빠지면 그 소스의 세트를 하나 끌어온다.
    규칙(순서·커버리지·misplaced)을 못 지키면 None을 돌려준다 — 호출부가 A를 복제한다."""
    first = list(rest if prefer_rest else base)
    second = list(base if prefer_rest else rest)
    picked = (first + second)[:want]
    if not picked:
        return None
    # 소스 커버리지 보정: 빠진 소스가 있으면 그 소스 세트 하나를 넣고 가장 흔한 소스를 뺀다.
    if not _covers_all_sources(picked, sets):
        have = {st["video_id"] for st in picked}
        for st in first + second:
            if st["video_id"] not in have:
                counts = {}
                for p in picked:
                    counts[p["video_id"]] = counts.get(p["video_id"], 0) + 1
                drop_vid = max(counts, key=counts.get)
                for j in range(len(picked) - 1, -1, -1):
                    if picked[j]["video_id"] == drop_vid:
                        picked.pop(j)
                        break
                picked.append(st)
                have.add(st["video_id"])
                if _covers_all_sources(picked, sets):
                    break
    picked = _sort_sets_in_story_order(picked)
    kept = _filter_misplaced_sets(picked)      # A와 같은 위치 검증을 받는다
    if not kept or not _covers_all_sources(kept, sets):
        return None
    return kept


def _pick_slot_variants(seg_map, target_seconds=None, n=1, call=None):
    """슬롯을 **n벌** 만든다 — 후보마다 다른 이야기를 주기 위해(v4, 2026-08-02).

    ★1벌째(A)는 `_pick_slot_groups`를 **그대로** 부른다. 같은 프롬프트·같은 응답 처리·
      같은 필터다. 즉 **A는 v3와 코드 경로가 동일**하고, 이 함수는 A를 건드리지 않는다.
      사장님 지시가 "3개 중 1개는 그대로 둔다"였고, 프롬프트를 만지면 그 약속을 못 지킨다
      (이 트랙은 프롬프트를 만질 때마다 새 문제가 났다).

    2벌째부터는 **코드가 조합**한다 — Gemini를 다시 부르지 않으므로 과금이 안 는다.
    조합은 '어느 세트를 쓸까'만 정하고 **순서는 원본 시간순으로 강제**한다.

    왜 필요한가(실측 job 8712570702b8): 후보 3개가 s1-1→s1-5/6→s1-9→s0-9/10으로 거의
    같았다. 슬롯이 이야기를 하나만 만들고 대사 3벌이 그 위에 얹히는데, 대본은 원본 대사를
    따라가는 게 원칙이라(`_rewrite_block`) **뼈대가 같으면 결과도 같다**. 그 job은 세트
    7개 중 4개만 쓰고 3개를 버렸고, 버려진 쪽에 완전히 다른 이야기가 통째로 있었다.

    반환: (variants, slot_source, slot_info, variant_kinds)
      variants[i] = i번째 후보가 쓸 groups. 항상 n개(못 만들면 A를 복제한다 — 그러면
      v3와 같은 결과라 나빠지지 않는다). variant_kinds[i]는 "gemini"/"recombined"/"cloned"
      — 조용한 품질 저하를 막으려고 어디서 왔는지 남긴다."""
    groups, slot_source, info = _pick_slot_groups(seg_map, target_seconds, call=call)
    variants, kinds = [groups], [SLOT_SOURCE_GEMINI if slot_source == SLOT_SOURCE_GEMINI
                                 else slot_source]
    if n <= 1 or not groups:
        return variants, slot_source, info, kinds
    # A가 폴백이었다면 변형하지 않는다 — 품질이 이미 의심스러운데 조합을 늘릴 이유가 없다.
    if slot_source != SLOT_SOURCE_GEMINI:
        while len(variants) < n:
            variants.append(groups)
            kinds.append("cloned")
        return variants, slot_source, info, kinds

    sets = _cap_sets(_build_source_sentence_sets(seg_map), target_seconds)
    used_ids = {g[0]["seg_id"] for g in groups if g}
    base = [st for st in sets if st["set_id"] in used_ids]
    rest = [st for st in sets if st["set_id"] not in used_ids]
    want = len(base) or 1
    seen = [tuple(g[0]["seg_id"] for g in groups if g)]

    # ★먼저 Gemini에게 "다른 이야기"를 짜달라고 한다(v4 개선, 2026-08-02).
    #   코드 조합은 시간순·소스커버리지 같은 기계적 규칙만 지킬 뿐 **이야기가 이어지는지**를
    #   못 본다(사장님: "흐름이 어색하지 않아야 하는데"). 맥락은 모델만 판단할 수 있다.
    #   실패하면 아래 코드 조합으로 폴백한다 — 후보가 비는 것보다 낫다.
    by_id = {st["set_id"]: st for st in sets}
    ai_variants = []
    if len(sets) > len(base):          # 여유가 있을 때만 묻는다(과금 게이트)
        try:
            caller = call or _vault_call
            resp = caller(_alt_seq_prompt(sets, [st["set_id"] for st in base],
                                          target_seconds, n - 1), _ALT_SEQ_SCHEMA)
            for story in ((resp or {}).get("stories") or [])[: n - 1]:
                picked, seen_ids = [], set()
                for sid in story or []:
                    if sid in by_id and sid not in seen_ids:
                        picked.append(by_id[sid])
                        seen_ids.add(sid)
                if not picked:
                    continue
                # 모델이 정한 순서라도 **같은 소스 안 시간순**과 자리 규칙은 코드가 다시 건다
                # (프롬프트로 부탁만 하고 확인 안 하면 지켜졌는지 알 수 없다 — 이 파일의 교훈).
                kept = _filter_misplaced_sets(
                    _sort_sets_in_story_order(picked, keep_order=True))
                # ★길이 하한도 코드로 확인한다(2026-08-02): 프롬프트에 "최소 N개"를 적어도
                #   지켜졌는지는 봐야 안다. 벌0보다 크게 짧으면 화면이 모자라 프리즈가 난다.
                #   모자라면 **버리지 않고** 안 쓴 세트를 시간순으로 채운다(재료를 살린다).
                if kept and len(kept) < len(base):
                    have = {st["set_id"] for st in kept}
                    for st in sets:
                        if len(kept) >= len(base):
                            break
                        if st["set_id"] not in have:
                            kept.append(st)
                            have.add(st["set_id"])
                    kept = _filter_misplaced_sets(
                        _sort_sets_in_story_order(kept, keep_order=True))
                # ★첫 장면 차별화(2026-08-02 사장님): "첫 장면은 기억에 많이 남는다".
                #   프롬프트로 "원본 맨 앞으로 시작하지 마라"를 부탁했지만 지켜졌는지는
                #   봐야 안다(실측: 세 벌이 전부 A1로 시작했다 — 원본과 똑같이 여는 셈).
                #   이미 다른 벌이 쓴 첫 세트면, **뒤쪽에서 다른 소스 세트를 앞으로 당긴다**
                #   (버리지 않는다 — 재료를 줄이면 화면이 모자란다).
                if kept and len(kept) > 1:
                    used_first = {v[0]["set_id"] for v in ai_variants if v}
                    # ★벌0의 첫 세트도 피해야 한다. set_id는 그 세트의 **첫 seg_id**와
                    #   같은 값이므로(_build_source_sentence_sets) groups[0][0]의 seg_id를
                    #   그대로 쓴다 — 형식이 달라 비교가 늘 실패하던 버그를 여기서 고쳤다.
                    if groups and groups[0]:
                        used_first.add(groups[0][0].get("seg_id"))
                    if kept[0]["set_id"] in used_first:
                        for k in range(1, len(kept)):
                            if kept[k]["set_id"] not in used_first:
                                kept.insert(0, kept.pop(k))
                                break
                        # 앞으로 당긴 뒤에도 같은 소스 안 시간순은 지켜야 한다
                        kept = _filter_misplaced_sets(
                            _sort_sets_in_story_order(kept, keep_order=True))
                if kept and _covers_all_sources(kept, sets):
                    ai_variants.append(kept)
        except Exception:               # noqa: BLE001 — 조합 실패가 job을 죽이면 안 된다
            ai_variants = []

    for i in range(1, n):
        cand, kind = None, None
        # 1순위: 모델이 짠 이야기(맥락 있음)
        while ai_variants and cand is None:
            c = ai_variants.pop(0)
            if tuple(st["set_id"] for st in c) not in seen:
                cand, kind = c, "ai_story"
        # 2순위: 코드 조합(맥락은 운에 맡기지만 재료는 살린다)
        if cand is None and rest:
            # 2벌째는 안 쓰인 세트를 앞세우고(버려지던 이야기), 3벌째부터는 base를 앞세워
            # 서로 다른 조합이 나오게 한다.
            c = _build_variant(base, rest, sets, want, prefer_rest=(i % 2 == 1))
            if c and tuple(st["set_id"] for st in c) not in seen:
                cand, kind = c, "recombined"
        if cand:
            variants.append([st["segs"] for st in cand])
            kinds.append(kind)
            seen.append(tuple(st["set_id"] for st in cand))
        else:
            variants.append(groups)             # 재료가 없다 → A 복제(= v3와 동일)
            kinds.append("cloned")
    return variants, slot_source, info, kinds


def _avoid_phrases_block(prev_narrations, top=6):
    """앞 후보들이 이미 쓴 표현을 뽑아 "이건 쓰지 마라"로 넘긴다(2026-08-03).

    왜 필요한가: 후보를 **벌마다 따로** 부르므로 각 호출은 서로 뭘 썼는지 모른다.
    각자 원본을 보고 가장 자연스러운 표현을 고르면 **당연히 같아진다** — 실측
    (job bf1455c1ad86 재현): 프롬프트에 "다른 면을 앞세워라"를 적어도 세 후보가
    전부 "미국 목조주택 보수용 점토"를 그대로 썼다(겹침 39개).
    부탁만으로 안 되면 **앞이 뭘 썼는지 알려줘야** 한다.

    조사·흔한 말은 빼고 **내용어**만 넘긴다(그래야 '이 단어를 피하라'가 의미를 갖는다)."""
    if not prev_narrations:
        return ""
    _STOP = {"이거", "그냥", "진짜", "정말", "해서", "하고", "있는", "되는", "같은",
             "해도", "라고", "댓글", "남겨", "주세요", "궁금", "분들", "하시", "이건",
             "이렇게", "그런데", "근데", "여기", "저는", "우리", "때문", "하는", "합니다"}
    cnt = {}
    for txt in prev_narrations:
        for w in set(re.findall(r"[가-힣]{2,}", txt or "")):
            if w not in _STOP:
                cnt[w] = cnt.get(w, 0) + 1
    # ★어미가 붙은 서술어("잡아주더라고요"·"페인트칠하니")는 피해도 소용이 없다 —
    #   같은 뜻을 다른 어미로 쓰면 그만이라 표현이 안 바뀐다. 실측(2026-08-03)에서
    #   정작 중요한 '미국'·'목조주택'은 빈도순에 밀려 안 올라왔다.
    #   → **명사형(체언)을 우선**한다. 흔한 어미로 끝나는 말은 뒤로 민다.
    _VERBY = ("요", "다", "죠", "고", "니", "서", "면", "며", "게", "지")
    def _rank(w):
        verby = 1 if w.endswith(_VERBY) else 0
        return (verby, -cnt[w], -len(w))
    ranked = sorted(cnt, key=_rank)[:top]
    if not ranked:
        return ""
    return ("\n★앞서 만든 다른 후보가 이미 이런 말을 썼다: "
            + ", ".join(f"'{w}'" for w in ranked)
            + "\n  **이 표현들은 피하고 같은 내용을 다른 말로 써라** — 후보끼리 같은 문구를 "
              "반복하면 3개를 만드는 의미가 없다(사실은 바꾸지 말고 표현만).")


def _rewrite_block(groups, avoid_narrations=None):
    """고른 구간들을 '이 자리에서 하던 말을 우리 말로 바꿔 써라' 프롬프트 블록으로."""
    if not groups:
        return ""
    # ★역할 부여(2026-08-03 사장님). 제약을 더 얹는 대신 **무슨 일을 하는 건지**를
    #   알려준다 — "원본을 바꿔 써라"만으론 모델이 원본 문장에 붙어 있어서, 세 후보가
    #   전부 "미국 목조주택 보수용 점토"를 그대로 반복했다(실측 job bf1455c1ad86).
    #   목표는 '다른 표현'이 아니라 **"원본을 본 시청자도 못 알아채게 각색"**이다.
    lines = ["너는 국내 최정상 숏폼 벤치마킹 전문가다. 숏폼 여러 개를 믹스해 **새로운 영상**을 "
             "만든다.",
             "[★대사를 새로 지어내지 마라 — 이 자리에서 원본이 하던 말을 우리 말로 바꿔 쓴다]",
             "아래는 우리가 쓸 구간을 시간순으로 나열한 것이다. 화면은 이미 정해졌다.",
             "각 줄마다 **그 자리의 원본 대사와 화면**을 보고, 같은 내용을 **다른 표현으로** "
             "새로 써라. 사건·순서·의미는 원본 그대로, 말맛만 우리 것으로.",
             "",
             "★목표는 '다르게 쓰기'가 아니라 **시청자가 원본을 봤어도 알아차리지 못하게 "
             "각색하기**다. 같은 사실을 **우리 시청자 입장**에서 다시 말해라.",
             "  예) 원본 \"미국에서 목조주택 보수용으로 쓰는\" "
             "→ \"국내에서 인테리어 셀프 보수할 때 쓰는\"",
             "  ⚠️단 **성능·수치·가격·성분은 원본에 있는 것만** 써라(내구 연수·효과를 "
             "지어내지 마라). 바꾸는 건 **어느 쪽에서 바라보느냐**지 사실 자체가 아니다."]
    for i, g in enumerate(groups, 1):
        secs = round(_secs(g), 1)
        budget = max(6, int(secs * _SYLLABLES_PER_SEC))
        said = " ".join((s.get("text") or "").strip() for s in g).strip()
        seen = " / ".join(((s.get("change") or s.get("scene_desc") or "").strip())[:34]
                          for s in g)
        lines.append(f"\n{i}. [{g[0]['seg_id']}] {secs}초 · **{budget}자 이내**")
        lines.append(f"   화면: {seen}")
        lines.append(f"   원본이 한 말: {said or '(무음)'}")
    lines.append(f"\n★비트를 **정확히 {len(groups)}개** 만들어라 — i번째 비트가 위 i번 세트다. "
                 "비트의 seg_ids에는 그 세트의 seg_id를 넣어라(순서를 바꾸지 마라).")
    lines.append("★원본 문장을 그대로 베끼지 마라. 같은 사건을 다른 말로 써라.")
    # ★제품 소개를 통째로 옮기지 마라(2026-08-03 사장님). 실측 job bf1455c1ad86:
    #   후보 3개가 전부 "미국 목조주택 보수용 점토"를 명사구 그대로 반복했다 —
    #   화면은 갈렸는데 대사가 베낀 티가 났다. 원본 대사가 같은 세트를 여러 후보가
    #   쓰는 한 이건 구조적으로 반복된다(핵심 세트는 어차피 겹쳐야 한다).
    #   → 사실은 유지하되 **어느 면을 앞세울지**를 바꾸게 한다.
    lines.append(
        "★제품을 원본이 부르던 이름 그대로 되풀이하지 마라 — 같은 물건도 "
        "**우리 시청자가 쓸 상황**으로 바꿔 부를 수 있다(위 각색 지침대로).")
    avoid = _avoid_phrases_block(avoid_narrations)
    if avoid:
        lines.append(avoid)
    # 2026-07-31 실측(사장님 "대본이 후킹 중복"): 첫 세트에 훅 문장을 2~3개 몰아 썼다 —
    # A안 "놀라시나요?"+"피곤하시죠?", C안 "깨지 마세요"+"놀라 깨시나요?"+"일어나지 마세요!".
    # 같은 말을 다른 표현으로 반복하는 것도 중복이다.
    lines.append("★1번은 훅이다 — **한 문장으로** 스크롤이 멈추게 세게. 같은 뜻을 두 번 "
                 "말하지 마라(질문을 연달아 던지거나 '~하지 마세요'를 반복하지 마라). "
                 "마지막 비트는 CTA(댓글 유도)로 끝내라.")
    lines.append("★원본이 무음인 자리는 화면에 보이는 것만 말해라. 없는 걸 지어내지 마라.")
    return "\n".join(lines)


def _assign_timeline(beats, groups):
    """화면을 **원본 시간순 그대로** 코드가 배정한다(모델이 뭘 골랐든 무시).

    비트 수와 구간 수가 달라도 앞에서부터 순서대로 나눠 준다 — 순서가 곧 원본 순서라
    말과 화면이 어긋날 수가 없다.

    ⚠️ n(비트 수) != len(groups)일 때 정수분배 lo/hi 슬라이스가 겹칠 수 있다
    (예: n=6, len(groups)=5 → 비트0·1 둘 다 groups[0:1]). 그대로 두면 두 비트가
    같은 chunk에서 같은 첫 클립을 골라 화면이 중복된다(실측 job 8226822c5b09,
    ping_pong=True, n_beats=6/n_groups=5). 그래서 이번 호출 안에서 **이미 쓴
    seg_id**를 추적해 다음 비트가 그 seg_id를 또 고르면 다음 후보로 넘긴다 —
    chunk 안에 못 쓴 후보가 없으면 groups 전체에서 시간순으로 안 쓴 seg를 빌려오고,
    그마저 없으면(그룹이 비트보다 훨씬 적은 극단적 경우) 중복을 허용한다(화면 없음보다
    중복이 낫다).

    ★screen_pinned 비트(2026-08-01, F4): _ensure_cta_beat가 만든 CTA 비트는 화면이
    이미 신중하게 정해져 있다(마지막 비트 컷 재사용) — 이 함수가 인덱스 배분으로
    덮어쓰면 그 선택이 무의미해진다. screen_pinned=True인 비트는 lo/hi/chunk/pick
    계산을 건너뛰고 기존 primary를 그대로 둔다. 그 seg_id는 **본 루프 전에 미리**
    used_seg_ids에 반영한다 — 핀 비트가 비트 목록의 뒤쪽(예: 마지막 CTA)에 있어도,
    그보다 앞선 비트가 같은 컷을 먼저 채가지 않도록 순서와 무관하게 예약해야 한다.
    lo/hi 인덱스 분배도 **핀 비트를 뺀 개수**로 다시 계산한다(n_active) — 안 그러면
    "핀이 그룹 하나를 미리 가져갔다"는 사실이 나머지 비트들의 분배 폭에 반영되지
    않아, 핀이 하필 다른 비트의 자연배정 그룹과 겹칠 때 원치 않는 중복이 튄다.
    핀 비트 하나가 CTA로 추가되는 흔한 경우 n_active == len(groups)가 되어
    원래 의도한 1:1 불변식이 나머지 비트들에 대해 그대로 복원된다."""
    if not beats or not groups:
        return beats
    used_seg_ids = set()
    all_segs_in_order = [s for g in groups for s in g]
    for b in beats:
        if b.get("screen_pinned"):
            pinned_seg_id = (b.get("primary") or {}).get("seg_id")
            if pinned_seg_id is not None:
                used_seg_ids.add(pinned_seg_id)
    active_beats = [b for b in beats if not b.get("screen_pinned")]
    n = len(active_beats)
    j = 0
    for b in beats:
        if b.get("screen_pinned"):
            pinned = b.get("primary") or {}
            _flag_offtopic(b, [pinned] + list(b.get("alternates") or []))
            continue
        i = j
        j += 1
        lo = i * len(groups) // n
        hi = max(lo + 1, (i + 1) * len(groups) // n)
        chunk = [s for g in groups[lo:hi] for s in g] or groups[min(lo, len(groups) - 1)]
        chunk = _order_clips_by_words(b.get("narration") or "", chunk)
        pick = next((s for s in chunk if s.get("seg_id") not in used_seg_ids), None)
        borrowed = False
        if pick is None:
            pick = next((s for s in all_segs_in_order if s.get("seg_id") not in used_seg_ids),
                        None)
            borrowed = True
        if pick is None:
            pick = chunk[0]   # 안 쓴 seg가 하나도 없다 — 중복 허용(화면 없음보다 낫다)
        else:
            used_seg_ids.add(pick.get("seg_id"))
        # ★rest는 항상 "실제로 alternates가 될 것들"이어야 한다(2026-08-01, F4).
        #   pick이 chunk 밖(all_segs_in_order)에서 빌려왔다면 chunk 안의 seg는 하나도
        #   pick이 아니므로 `s is not pick` 필터가 chunk 전체를 그대로 통과시켜버린다
        #   — rest에 pick과 무관한 원래 로컬 chunk가 그대로 남아 offtopic 검사(아래)가
        #   실제 배정과 다른 화면을 보게 된다. 빌려온 경우엔 rest를 빈 목록으로 둔다
        #   (그 비트의 진짜 alternates는 없다 — 로컬 후보는 이미 다른 비트가 다 썼다).
        rest = [] if borrowed else [s for s in chunk if s is not pick]
        rest = _trim_rest_to_narration(b, pick, rest)
        b["primary"] = dict(pick)
        b["alternates"] = [dict(s) for s in rest]
        _flag_offtopic(b, [pick] + rest)
    return beats


def _trim_rest_to_narration(beat, pick, rest):
    """화면을 **대사가 필요한 만큼만** 붙이고 멈춘다(과적재 차단, 2026-08-01).

    왜: chunk 전체를 alternates로 넣던 탓에 한 비트가 슬롯 그룹의 세그를 통째로 가져갔다.
    실측(scratchpad/overload_probe.py, fixture_live): 훅 비트가 **2.3초 말하는데 화면을
    7.0초(클립 7개)** 붙였다. 클립들이 빠르게 스쳐 카탈로그 낭독처럼 보이던 것의 정체다.

    ★단순 개수 상한(MAX_CLIPS_PER_BEAT=3)으로 자르면 안 된다 — 같은 실측에서 feature·cta
      비트는 이미 화면이 **대사보다 짧아**(2.9s/3.5s, 3.2s/5.4s) 개수로 자르면 오히려
      프리즈가 는다. 그래서 개수가 아니라 **길이**를 기준으로 삼는다.

    여유(_LEN_TOL=0.35)는 backbone.length_status가 '화면이 남는다(under)'고 볼 때와
    같은 값을 쓴다 — 같은 현상을 두 곳이 다른 기준으로 재면 판정이 엇갈린다.
    필요분에 못 미치면 **하나도 안 자른다**(모자란 쪽은 여기서 건드릴 일이 아니다).
    실 TTS가 추정보다 길어 화면이 부족해지면 렌더 직전 `_refill_beats_to_tts`가
    실측 길이로 다시 채운다 — 그게 안전망이라 여기서 넉넉히 잘라도 된다."""
    if not rest:
        return rest
    from shopping_shorts.backbone import _LEN_TOL, narration_seconds

    need = narration_seconds(beat.get("narration") or "")
    if need <= 0:
        return rest
    budget = need * (1 + _LEN_TOL)

    def _dur(s):
        return max(0.0, (s or {}).get("end", 0) - (s or {}).get("start", 0))

    total = _dur(pick)
    if total >= budget:
        return []                      # primary만으로 이미 충분하다
    kept = []
    for s in rest:
        kept.append(s)
        total += _dur(s)
        if total >= budget:
            break                      # 이 클립까지로 예산을 넘겼다 — 여기서 멈춘다
    return kept


def _stems(txt):
    """조사·어미를 털어낸 근사 어간 집합('기름이'와 '기름'이 같게 잡히도록 앞 2글자)."""
    return {t[:2] for t in _claim_key(txt or "")}


def _order_clips_by_words(narration, segs):
    """비트 안에서 **그 말에 맞는 컷을 앞으로** 올린다(2026-07-31 사장님).

    "우리 대본에 핵심 단어를 태깅했잖아. 이 장면에 있는 게 원본 태깅이랑 맞으면
     가져오는 게 힘든 건가?" → 안 힘들다. 구간마다 화면·변화 문구가 이미 있으니
     낱말이 겹치는 컷을 먼저 보여주면 된다. 그동안은 이 비교를 딴소리 검사에만 썼다.

    실측(job fd8bd0f2a5c1): [5] "물티슈로 쓱 닦아도 끝!"에 s0-3(설치)이 먼저 오고
    s0-5(물티슈로 닦는 모습)가 두 번째라, 말할 때 화면은 아크릴판을 들고 있었다.
    또 [4] "깔끔하게 유지"에 s0-1(기름때가 지저분하게 묻어있다)이 붙었다.

    비트 안 순서만 바꾼다(비트 사이 원본 시간순은 그대로) — 겹치는 낱말이 없으면
    원래 순서를 유지한다(안정 정렬).
    """
    if len(segs) < 2:
        return segs
    want = _stems(narration)
    if not want:
        return segs

    def _hit(s):
        return len(want & _stems(f"{s.get('change') or ''} {s.get('scene_desc') or ''} "
                                f"{s.get('text') or ''}"))

    return sorted(segs, key=lambda s: -_hit(s))     # 파이썬 정렬은 안정 → 동점은 원순서


def _flag_offtopic(beat, segs):
    """이 자리의 **결**과 우리 문장이 겹치는지 검사한다(2026-07-31 사장님).

    "문장으로 소스를 끊어내는 건데, 그 화면에 전혀 다른 대본이 들어가고 있는 거 아니야?
     그 장면엔 그 대본의 결이 들어가야 하잖아."
    → 프롬프트로 요구만 하고 확인을 안 하면 지켜지는지 알 수 없다(며칠간 반복된 실패 패턴).
      우리 문장과 [그 자리 원본 대사 + 화면 + 변화]의 낱말이 **하나도 안 겹치면** 딴소리로
      보고 fit을 깎고 forced를 세운다 — 하류의 약비트 재작성·스왑·추천 점수가 그때 반응한다.
      (표현을 바꿔 쓰라고 했으니 '많이 겹쳐야' 한다고는 보지 않는다. 0겹침만 잡는다.)
    """
    # 조사·어미가 붙어 낱말이 그대로는 안 겹친다("기름이" vs "기름") → 앞 2글자로 비교.
    ours = _stems(beat.get("narration") or "")
    theirs = set()
    for s in segs:
        theirs |= _stems(" ".join(
            [s.get("text") or "", s.get("change") or "", s.get("scene_desc") or ""]))
    if ours and theirs and not (ours & theirs):
        beat["fit"] = min(int(beat.get("fit") or 5), 2)
        beat["forced"] = True
        beat["offtopic"] = True
    return beat


def _blocks_order_block(blocks):
    """확정된 세 덩어리를 대본 프롬프트용 블록으로. 덩어리마다 **글자수 예산**을 준다."""
    if not blocks:
        return ""
    lines = ["[★화면은 이미 정해졌다 — 이 세 덩어리 순서로 간다. 바꾸지 마라]",
             "각 덩어리는 원본에서 **맥락이 바뀌는 지점까지** 통째로 가져온 구간이다. "
             "그 화면을 보고 **그 화면에 맞는 대사**를, 아래 글자수 안에서 써라. "
             "화면에 없는 건 말하지 마라."]
    for i, b in enumerate(blocks, 1):
        budget = int(b["secs"] * _SYLLABLES_PER_SEC)
        lines.append(f"\n{i}) {b['name']} 덩어리 — {b['secs']}초, **{budget}자 이내로 써라**")
        for s in b["segs"]:
            chg = (s.get("change") or "").strip()
            lines.append(f"   · {s['seg_id']} 화면:{(s.get('scene_desc') or '')[:40]}"
                         + (f" | 변화:{chg[:40]}" if chg else ""))
    lines.append("\n★글자수를 넘기면 화면이 모자라 엉뚱한 장면이 깔린다. 예산 안에서 끝내라.")
    # 2026-07-31 사장님: "액션 있는 장면 부분은 원대본과 다른 대사로 써라."
    lines.append("★액션(변화)이 있는 컷에는 **원본이 하던 말을 그대로 옮기지 말고** 그 동작을 "
                 "네 말로 새로 살려 써라. 무슨 일이 일어나는지는 화면 그대로, 표현만 새로.")
    lines.append("★한 컷을 여러 문장으로 잘게 쪼개지 마라 — 컷 하나에 한 호흡으로 간다.")
    return "\n".join(lines)


def _assign_blocks(beats, blocks):
    """모델이 뭘 골랐든 **화면은 확정된 덩어리 순서대로** 다시 배정한다(2026-07-31).

    ★왜 코드가 강제하나: 프롬프트로 "이 순서 고정"이라고 말만 하고 지켰는지 검사하지
      않아서(옛 _spine_order_block) 매번 다르게 나왔다. 말은 모델 것, 화면은 코드 것.
    비트 배분: 첫 비트=훅 덩어리, 마지막 비트=CTA 덩어리, 가운데=스토리 덩어리."""
    if not beats or not blocks:
        return beats
    by = {b["name"]: list(b["segs"]) for b in blocks}
    mid = [b for b in beats[1:-1]] if len(beats) >= 3 else []
    groups = [(beats[:1], by.get("훅") or by.get("스토리") or [])]
    if mid:
        groups.append((mid, by.get("스토리") or []))
    if len(beats) >= 2:
        groups.append((beats[-1:], by.get("CTA") or by.get("스토리") or []))
    for grp, segs in groups:
        if not grp or not segs:
            continue
        # 비트별 대사 길이 비율대로 덩어리 안의 컷을 나눠 준다(긴 대사에 긴 화면).
        weights = [max(1, len((b.get("narration") or "").strip())) for b in grp]
        total_w = sum(weights)
        pos = 0
        for k, (b, w) in enumerate(zip(grp, weights)):
            n = len(segs) - pos if k == len(grp) - 1 else max(1, round(len(segs) * w / total_w))
            chunk = segs[pos:pos + n] or segs[-1:]
            pos += n
            b["primary"] = dict(chunk[0])
            b["alternates"] = [dict(s) for s in chunk[1:]]
    return beats


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

    seg_map: {seg_id: {video_id, seg_id, start, end, text, scene_desc, motion_level}}
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
                "change": (seg.get("change") or "").strip(),
                "is_key": bool(seg.get("is_key")),
                "shot_role": seg.get("shot_role") or "기타",
                "product_benefits": _seg_benefits(seg),
                "motion_level": seg.get("motion_level"),
            }
            _act = seg.get("action")
            _act_s = f" | 행위:{_act}" if _act else ""
            # ★변화(2026-07-31): 사물이 주어인 상태변화·감각 한 줄. 손동작(행위)과 별개 칸이다 —
            #   레퍼런스 실측에서 영상의 진짜 포인트("갈라지다→매끈해지다", "튀는 걸 막아준다",
            #   "모찌처럼 늘어난다")가 전부 여기 속하는데 행위 어휘 30개는 사람 손동작뿐이라
            #   하나도 못 담았다. 옛 추출본엔 필드가 없어 ""라 이 칸이 통째로 빠진다(회귀 없음).
            _chg = (seg.get("change") or "").strip()
            _chg_s = f" | 변화:{_chg}" if _chg else ""
            # 무자막 소스는 '말:'이 빈칸이라 이 라인만 보면 대본이 특장점을 녹일 재료가 없다.
            # 화면→특장점 문장을 라인에 실어 라이브 scene_first 경로도 쓰게 한다(2026-07-26).
            _ben = _seg_benefits(seg)
            _ben_s = f" | 특장점:{' / '.join(_ben[:2])}" if _ben else ""
            # motion_level은 scene_desc와 별개 필드로만 노출 — scene_desc 문자열 자체에 섞으면
            # _claim_key(아래)의 토큰화가 오염돼 무관한 세그먼트끼리 "PEAK" 토큰을 공유해
            # 앵커 dedup(_dedup_anchors)이 엉뚱하게 합쳐진다. 반드시 별도 suffix로만 붙인다.
            _ml = seg.get("motion_level")
            _ml_s = f" | 모션:{_ml}" if _ml else ""
            # 훅 비주얼(2026-07-29): 추출이 영상 보고 태깅한 shot_role(완성/조리/기타)·is_key(핵심
            # 실증)를 라인에 노출 → 훅 규칙이 '완성/실증' 장면을 첫 화면으로 고르게 한다.
            # ★scene_desc 문자열엔 절대 안 섞는다(_claim_key 토큰 오염) — 모션처럼 별도 suffix로만.
            _role_s = f" | 역할:{seg.get('shot_role') or '기타'}"
            _key_s = f" | 실증:{'Y' if seg.get('is_key') else 'N'}"
            lines.append(
                f"[{sid}] ({length}s) 화면:{seg.get('scene_desc','')} | 말:{seg.get('text','')}"
                f"{_act_s}{_chg_s}{_ben_s}{_ml_s}{_role_s}{_key_s}"
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
            # 변화(2026-07-31)도 실어 나른다 — _dedup_anchors가 "같은 물건에 일어난 다른 일"을
            # 구분하는 근거다. 없으면 뚜껑 열다/닫다가 scene_desc 토큰만 같아 한 컷으로 접혔다.
            "change": (seg.get("change") or "").strip(),
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
    def _ov(x, y):
        return bool(x) and len(x & y) / max(1, len(x)) >= 0.5

    seen_tokens = []   # 이미 채택한 [(장면 토큰, 변화 토큰)]
    out = []
    for a in anchors:
        key = set(_claim_key(a.get("scene_desc", "")))
        # ★변화(2026-07-31)를 두 번째 축으로 둔다 — 한 문자열로 합치면 scene_desc 토큰이
        #   수적으로 이겨서 "기름이 튄다"와 "가림막이 막아준다"가 여전히 접혔다(실측).
        #   장면이 겹쳐도 **일어난 일이 다르면 다른 앵커**다. 둘 다 겹칠 때만 중복.
        chg = set(_claim_key(a.get("change", "")))
        dup = any(_ov(key, pk) and (_ov(chg, pc) or not (chg or pc))
                  for pk, pc in seen_tokens)
        if dup:
            continue
        seen_tokens.append((key, chg))
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


def _is_dead_key_error(e):
    """이 키는 다시 써도 안 되는가(권한 거부·인증 실패·무효 키).

    key_vault의 is_account_disabled_error는 '계정 정지' 문구만 보므로
    'Your project has been denied access'(403 PERMISSION_DENIED)를 못 잡는다 —
    2026-07-30 실측에서 이게 대본 생성 전체를 포기시키던 뿌리였다."""
    m = str(e)
    return any(t in m for t in ("PERMISSION_DENIED", "UNAUTHENTICATED",
                                "API_KEY_INVALID", "API key not valid"))


def _vault_call(prompt, schema, max_tries=8):
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
            # ★죽은 키(403 권한거부·401 인증실패·무효키)는 **다음 키로 넘어간다**(2026-07-30).
            #   예전엔 이 셋이 위 분류 어디에도 안 걸려 아래 `return None`으로 떨어졌다 —
            #   라운드로빈이 죽은 키 하나를 집는 순간 **대본 생성이 통째로 포기**되고 호출부는
            #   옛 생성기로 조용히 폴백했다(실측 2026-07-30: 캐스케이드 14키 중 12키가 멀쩡한데
            #   403 키 하나 때문에 백테스트가 절반씩 실패). 키를 죽은 것으로 표시해 다음부터
            #   아예 안 뽑히게 하고, 지금 호출은 다음 키로 계속한다.
            if _is_dead_key_error(e):
                try:
                    key_vault.mark_exhausted(key_vault._owner_group(key) or "general", key)
                except Exception:
                    pass
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
                            benefits_block="", tone_boost=False, engine=None, engine_seed=0):
    """스토리 헌장 + 장면 팔레트 + 레퍼 구조 → 후보 n개. 각 비트는 seg_ids(2~4 다중컷)로
    장면을 지목한다. 실패 시 []. 헌장이 품질을 담당하므로 별도 검증루프 없음(1콜).

    bank_context(P0-2): 부품은행에서 조립한 승인 훅·어미·부사·CTA·스파인 블록(빈 문자열이면
    미주입=회귀0). 영상 믹스 대본이 매번 같은 훅으로 열리지 않게 로테이션된 부품을 실어준다.
    order_block(2026-07-22 백본 통합): 백본 영상의 시간순 장면 뼈대 블록. 빈 문자열이면 무주입.
    ★스토리·은행·다중컷(rich 품질기계)은 그대로 두고 화면 '순서'만 제약한다 — 별도의 뼈다귀
    생성기(장면당 한 줄)를 쓰면 스키마에 스토리 필드가 없어 이야기가 원천 불가였다(그날 실사고)."""
    char_target = int(target_seconds * _SYLLABLES_PER_SEC)
    # ── 2026-07-31 대정리(사장님 지시) — 스타일 규칙을 걷어내고 은행 벤치마킹 + 자유로.
    #    걷어낸 것: 스파인 강제 · 훅 패턴 목록 · 역할별 글자수 · 어미 종류 수 · 감각어 개수 ·
    #    강조어 횟수 · 제출 전 자가점검 6항목 · 3단계 상황 프레임 · 소스 교차 규칙.
    #    이유: 규칙끼리 이겼다(감각어↑→어미 붕괴 tone 1.00→0.67→훅 중복). 2026-07-26에도
    #    "제약 17개 충돌"로 걷어낸 자리에 같은 방식으로 다시 쌓았던 것 — 되풀이를 끊는다.
    #    남긴 것: 배선(seg_id 지목·caption_lines 일치·스키마 필드) + 중요 액션(변화) 집중.
    #    선행 설계(참고): docs/superpowers/specs/2026-07-26-대본프롬프트-단순화-Gemini종합-design.md
    lo, hi = int(char_target * 0.93), int(char_target * 1.05)
    prompt = (
        f"너는 한국 쇼핑 숏폼(살림·요리·제품) 대본 작가다. 아래 재료로 서로 다른 훅을 쓴 "
        f"대본 후보 {n}개를 만들어라. 화자가 들려주는 짧은 이야기체로, 사람이 말하듯 자연스럽게.\n\n"
        "[제품 — ★이게 중심이다. 무슨 제품이고 핵심 장점이 뭔지 여기서 잡고 절대 벗어나지 마라. "
        "다국어면 한국어로]\n"
        f"{(reference_text or '')[:1500]}\n\n"
        # ★채널 스타일(2026-08-05)을 맨 앞에 — 맨 뒤에 붙였더니 규칙 40줄에 밀려 절반만
        #   먹었다(실측 job 64e0a110: 훅 명령형·문장 뚝뚝·합쇼체 잔존). 문체는 이게 우선.
        + _style_extra() +
        # 2026-07-29(사장님 확정): 스펙 나열형 reference_text를 그대로 던지면 대본도 나열형으로
        # 나온다. 3단계 상황 프레임을 줘서 Gemini가 스스로 '썰'을 짓게 유도(고정 문구 하드코딩 금지
        # — 제품마다 실제 스펙에서 재구성해야 하므로 지시만 주고 내용은 매번 새로 만들게 한다).
        # 2026-07-31 정리: 예전엔 여기서 '불편→해결→주변반응' 3단계를 못박았는데, 그러면
        # 후보 3개가 전부 같은 구조로 나온다(실측: A/B/C가 같은 인물·같은 사건). 스펙 나열만
        # 막고 구성은 맡긴다.
        # ★2026-07-31(사장님): "대사를 창조하는 게 아니고, 스토리도 원본 3장의 스토리에서
        #   가져오는데 완전 다른 걸 하면 안 된다 — 그래야 장면이랑 맞지."
        #   앞 버전은 "이걸 겪은 사람의 이야기로 바꿔 써라"라고 창작을 시켰다. 그러면 화면에
        #   없는 사건이 나오고(실측: 훅이 '벽지가 번들거린다'인데 화면은 씻기는 장면),
        #   모델은 없는 화면을 만들 수 없으니 아무 컷이나 붙인다. 재료는 원본이다.
        "→ 스펙을 그대로 나열하지 말고, **원본 영상들이 실제로 한 말**을 재료로 이야기를 엮어라.\n\n"
        "[우리 장면 팔레트 — 이 seg_id 화면만 쓸 수 있다. '말:' 칸이 원본에서 실제로 한 말이다]\n"
        f"{inventory_text}\n\n"
        "[★원본에서 가져와라 — 지어내지 마라]\n"
        "- 스토리도 대사도 **위 인벤토리의 '말:'과 '변화:'에서 가져와 재구성**하는 것이다. "
        "원본에 없는 인물·사건·에피소드를 새로 만들지 마라. 지어내면 그 말에 맞는 화면이 "
        "없어서 결국 엉뚱한 컷이 붙는다.\n"
        "- 표현은 네 말로 다듬되(그대로 베끼기 금지), **무슨 일이 있었는지는 원본 그대로**여야 한다.\n"
        "- 원본이 말하지 않은 효능·상황을 추가하지 마라.\n\n"
        # ★2026-07-31(사장님): "레퍼런스 채널은 대본의 중요 행동을 반드시 화면과 일치시키는데
        #   우리는 계속 못 한다." 실측 레퍼 3편의 뼈대가 전부 '변화'였다 —
        #   갈라짐→닦음→매끈함 / 튐→막아줌→헹굼 / 밀가루→모찌 촉감.
        #   인벤토리에 '변화:' 칸을 새로 실었으니, 대본을 그 변화들에서 **거꾸로** 짜게 한다.
        # 화면 일치 지시는 아래 [장면과 대사] 블록으로 합쳤다(2026-07-31 정리) — 같은 말을
        # 두 군데서 하면 모델이 한쪽을 놓친다.
        + ((benefits_block + "\n\n") if benefits_block else "")
        + ((order_block + "\n\n") if order_block else "")
        # ★2026-07-27 과삭제 복구: 레버1이 스토리 강제를 전부 걷어내 대본이 '기능 자막 나열'로
        # 회귀(밋밋). 과적재 없이 이야기 핵심 4개만 린하게 되살린다(인과·대화·인물·나열금지).
        # ── 2026-07-31 대정리(사장님 지시) ──────────────────────────────────────
        # "다 빼고 제미니한테 은행에서 잘되는 대본 형식 보고 벤치마킹하되 훅/스토리/CTA는
        #  개성있게, 스토리 탄탄하게. 장면에 맞는 대사를 넣되 중요한 액션에 집중. 길이는
        #  벤치 영상 중 제일 괜찮은 걸로. 최대한 제미니한테 자유를 줘라."
        #
        # 왜: 스타일 규칙(어미 4종·감각어 4개·강조어 2회·역할별 글자수·자가점검 6항목)이
        #   40줄 넘게 쌓여 서로 이겼다 — 감각어를 강화하면 어미가 무너지고(실측 tone
        #   1.00→0.67), 어미를 고치면 훅이 중복됐다. 2026-07-26에도 "제약 17개 충돌"로
        #   한 번 걷어낸 자리에 같은 방식으로 다시 쌓은 것이다. 규칙을 더해 확률을 미는
        #   대신 **좋은 예시를 보여주고 판단을 맡긴다**(few-shot > 규칙 나열).
        # 남긴 것: 배선에 필요한 것만(seg_id 지목·caption_lines 일치·스키마 필드).
        + "[이야기]\n"
        "- 기능 나열이 아니라 하나로 이어지는 이야기로 엮어라. 무슨 일이 있었고·그래서 어떻게 "
        "됐는지가 이어지게. 문장이 각자 놀면 광고 문구로 들린다.\n"
        # ★비트 문장 잇기(2026-08-05): 비트마다 한 문장씩 닫으니 대본이 뚝뚝 끊겼다(실측).
        "- ★비트가 나뉘어 있어도 대본은 한 호흡이다 — 각 비트의 narration이 독립 문장으로 "
        "닫히지 말고, 앞 비트를 이어받아 흐르게 써라. 한 비트 안에서 장점 2~3개를 접속으로 "
        "이어 긴 문장 하나로 써도 좋다.\n"
        "- 훅·CTA·풀어내는 순서는 **후보마다 개성 있게** 달라야 한다. 다만 그 차이는 "
        f"**원본의 어느 대목을 앞세우느냐**에서 나와야지, {n}개가 각자 다른 이야기를 "
        "지어내는 게 아니다.\n"
        "- 말투는 옆에서 썰 푸는 구어체. 어떻게 살릴지는 네가 판단해라.\n"
        # ★고조 연결어(2026-08-04 사장님 지시): 스토리 중간에 놀람을 쌓는 연결어를 꼭 넣어라.
        #   비트가 각자 놀며 뚝뚝 끊기는 걸 막는 가장 싼 장치 — 문장 사이를 '그리고'가 아니라
        #   '한 단계 더'로 잇는다. 규칙 더미 금지 교훈(2026-07-31)에 따라 지시는 이 한 줄만.
        "- ★스토리 중간(전개·반전 비트)에 **놀람을 쌓는 연결어를 1~2번** 넣어라 — "
        "'심지어' '더군다나' '근데 이게 대박인 게' '놀랍게도' '이럴 수가 있나 싶게' "
        "'여기서 끝이 아니에요' 같은 것(소재에 맞는 걸 골라 변주, 매 문장 금지·훅과 CTA엔 금지).\n\n"
        "[장면과 대사]\n"
        "- 각 비트에 그 대사가 실제로 보이는 seg_id를 붙여라(2~4개, 시간순). 인벤토리에 없는 "
        "seg_id 금지, 같은 seg_id 재사용 금지.\n"
        # 2026-07-31 실측: 개수만 요구했더니 1.3초짜리 컷 하나로도 통과해 말 31.9초 vs
        # 화면 13.8초가 됐고, 모자란 만큼 뒤 클립이 당겨져 영상 전체가 밀렸다.
        "- ★붙인 컷들의 **길이 합이 그 대사를 읽는 시간 이상**이어야 한다(괄호 안 초를 더해 봐라). "
        "짧은 컷 하나만 붙이면 화면이 모자라 뒤 장면이 당겨지고 영상 전체가 어긋난다.\n"
        "- ★중요한 액션에 집중해라 — 인벤토리 '변화:' 칸이 이 영상이 눈으로 증명할 수 있는 "
        "사실이다. 그 순간을 대본의 중심에 놓고, 그 말을 하는 비트엔 그 seg_id를 맨 앞에 둬라. "
        "화면에 없는 걸 말하지 마라.\n"
        "- fit(1~5): 대사와 화면이 실제로 맞는지 솔직하게. 억지로 붙였으면 forced=true.\n"
        # 2026-07-31 실측(job 6d2150a6ae5b): 훅이 "벽지가 기름으로 번들거리네요?"인데 붙은
        # 화면은 **깨끗이 씻기는** 장면이었다(fit=5·forced=False로 자기평가). 게다가 그 컷을
        # 결과 비트에서 또 썼다. 훅은 말이 먼저 나오기 쉬워 여기서 제일 잘 어긋난다.
        "- ★훅은 특히 조심해라. 하려는 말에 맞는 화면이 없으면 **말을 바꿔라** — 화면에 있는 "
        "것으로 훅을 다시 써라. 없는 화면을 상상해서 말하지 마라.\n"
        "- 훅에 쓴 화면을 결과 비트에서 또 쓰지 마라(같은 장면이 두 번 나오면 김이 샌다).\n\n"
        "[길이]\n"
        f"- 이 영상은 {target_seconds}초짜리다. 참고 대본들의 호흡을 보고 **그중 가장 잘 읽히는 "
        f"길이**로 맞춰라(대략 {lo}~{hi}자). 기계적으로 채우지 말고 이야기가 끝나는 데서 끝내라.\n\n"
        "[형식]\n"
        "- 각 비트: role(훅·문제·해결·결과·CTA 등)·narration·seg_ids·fit·forced.\n"
        "- caption_lines: narration을 3~4어절 호흡으로 끊은 배열. 이어붙이면 narration과 "
        "글자가 정확히 같아야 한다(단어 추가·삭제 금지).\n"
        "- 마지막 비트는 CTA다. 존댓말로 끝내라(반말 금지).\n"
        # ★CTA 후킹(2026-08-03 사장님): 밋밋한 "궁금하시면 댓글에 OO"는 아무도 안 남긴다.
        #   댓글 하나가 링크 클릭으로 이어지는 구조라 CTA가 제일 센 낚시여야 한다.
        "- ★CTA는 밋밋하게 '궁금하시면 댓글 남겨주세요'로 쓰지 마라 — **댓글을 남길 명분**을 "
        "한 줄 얹어라. 명분 예시(소재에 맞는 걸 골라 변주): "
        "①검색 불가 희소성(\"검색해도 잘 안 나와서 제가 산 링크 그대로 드려요\") "
        "②가격 명분(\"제가 산 최저가 그대로 보내드려요\") "
        "③사회적 증거(\"다들 물어보셔서 댓글로만 공유해요\") "
        "④손해 회피(\"이거 모르고 사면 비싸게 사요\"). "
        "형식은 반드시 [명분 한 줄] + \"댓글에 '[키워드]' 남겨주시면 바로 보내드릴게요\"로 끝내라. "
        "유입 경로는 댓글뿐이다(프로필·링크 안내 금지). 명분은 원본에 있는 사실 범위 안에서만 — "
        "없는 가격·할인·한정수량을 지어내지 마라.\n"
        "- 각 후보에 hook, story_person, story_event, story_resolution, cta_line, "
        "cta_keyword를 채워라.\n"
        "- 억지 개그·번역투·상세페이지 상투어(꿀템·갓성비·완벽 해결·삶의 질 상승) 금지.\n"
        # 은행 = 실제로 잘 나온 대본 조각들. ★규칙이 아니라 **벤치마킹 대상**으로 준다.
        + ((f"\n[벤치마킹 — 실제로 잘 나온 대본들의 조각이다. 규칙이 아니라 참고다. "
            "이 리듬·말맛·훅의 결을 보고 **우리 소재로 새로 써라**. 그대로 베끼지 마라]\n"
            f"{bank_context}\n") if bank_context else "")
        + ((f"\n- [길이 보강] 직전 후보가 짧았다. 이번엔 최소 {lo}자 이상으로 이야기를 "
            "더 채워라.\n") if lengthen else "")
        + (("\n- [말투 보강] 직전 후보들이 밋밋했다(어미가 '~했어요/~네요'로 단조롭거나 "
            "감각이 없었다). 이번엔 말맛과 감각 묘사를 최우선으로 살려라.\n")
           if tone_boost else "")
        # 엔진 버전별 추가 블록(v3 = 백테스트 은행 few-shot).
        + _engine_extra(engine, engine_seed)
        + "\n출력은 스키마 JSON만.")
    raw = call(prompt, _SCENE_FIRST_SCHEMA)
    if not raw or not isinstance(raw, dict):
        return []
    return raw.get("candidates", []) or []


_STRONG_OPENER_TOKENS = ("와 ", "와,", "아니", "이거", "이걸", "저 이거", "헐", "대박",
                         "세상에", "이런", "저만")



def _engine_seed(reference_text):
    """은행 부품 회전용 씨앗 — 소재(reference_text)마다 다른 조각이 뽑히게 한다(2026-07-31).

    ★왜 필요한가: script_engine._bank_block 주석은 "매번 다른 조각이 보이도록 seed로
      회전시킨다"고 적혀 있는데 **본 호출의 seed가 늘 0**이라 회전이 실제로 안 됐다.
      그래서 밥솥 요리든 비누든 모든 소재에 같은 감각어 6개(꿉꿉·보송·순식간·뚝딱·사르르·촉촉)만
      실려 나갔다(2026-07-31 실측). 소재 텍스트 해시를 쓰면 **소재마다 다르되 같은 소재는
      항상 같은** 조각이 나와 백테스트 재현성도 유지된다(난수 금지).
    """
    import hashlib
    h = hashlib.md5((reference_text or "").encode("utf-8")).hexdigest()
    return int(h[:6], 16) % 97



def _style_extra():
    """채널 스타일 블록(style_profiles). 부가기능 — 실패해도 생성을 죽이지 않는다."""
    try:
        from shopping_shorts import style_profiles
        return style_profiles.style_block()
    except Exception:
        return ""


def _engine_extra(engine, seed=0):
    """엔진 버전이 얹는 추가 프롬프트 블록(script_engine).
    부가기능이라 실패해도 대본 생성을 죽이지 않는다 — 빈 문자열이면 v2와 동일."""
    try:
        from shopping_shorts import script_engine
        return script_engine.get(engine).extra_rules(seed=seed)
    except Exception:
        return ""


def _hook_opener(hook):
    """hook의 첫 절(첫 ?/!/. 까지) — 강한 오프너로 beats[0]에 얹을 조각. 없으면 ''."""
    h = (hook or "").strip()
    if not h:
        return ""
    for i, ch in enumerate(h):
        if ch in "?!":
            return h[:i + 1]
    return h.split(".")[0].strip()


def _dup_key(s):
    """중복 판정용 정규화 — 따옴표·문장부호·공백을 걷어낸 글자만 남긴다."""
    return re.sub(r"[^가-힣0-9A-Za-z]", "", s or "")


def _is_same_opening(opener, narration, prefix=8):
    """opener가 narration과 '사실상 같은 말'인가.

    ★완전 일치(substring)만 보면 안 된다(2026-07-30 실사고): 모델이 hook 필드엔
      '친구가 이거 보더니 곱네 하더라고요', beats[0]엔 '친구가 이거 보더니 "진짜 곱네"
      하더라고요'처럼 **미세하게 다르게** 쓰면 중복 판정을 빠져나가 훅이 두 번 붙었다.
    → 부호·공백을 지운 뒤 포함관계를 보고, 그래도 아니면 앞 prefix자가 같은지 본다."""
    a, b = _dup_key(opener), _dup_key(narration)
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    return len(a) >= prefix and len(b) >= prefix and a[:prefix] == b[:prefix]


def _lead_with_hook(narration, hook):
    """beats[0]이 강한 오프너로 안 열리면 hook 앞절을 붙여 강제로 세게 연다(2026-07-21).
    이미 강해 보이면(오프너 토큰 시작 or 앞 12자에 ?/!) 그대로 둔다(중복 방지)."""
    n = (narration or "").strip()
    head = n[:12]
    if n.startswith(_STRONG_OPENER_TOKENS) or "?" in head or "!" in head:
        return n
    opener = _hook_opener(hook)
    if not opener or _is_same_opening(opener, n):
        return n
    return f"{opener} {n}"


def _ground_candidate(cand, seg_map, structure="free", lead_hook=True):
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
        # ★리라이트 믹스에선 얹지 않는다(2026-07-31 사장님 "대본이 후킹 중복").
        #   첫 세트가 이미 훅 자리이고 모델이 그 자리 대사를 쓴 상태라, hook 필드를 덧붙이면
        #   같은 말이 두 번 나온다 — 실측 B안: "카페에 두면 다들 어디서 샀냐고 물어봐요"
        #   뒤에 "카페에 두면 다들 어디서 샀냐고 물어보고"가 그대로 이어졌다.
        if lead_hook and not beats_out:          # 첫 유효 비트 = 훅 자리
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
    beats_out = _ensure_cta_beat(beats_out, cand)
    beats_out = _fix_beat_structure(beats_out)
    beats_out = _fill_beat_screen_time(beats_out, seg_map)
    return {"structure": structure, "beats": beats_out}


def _beat_screen_secs(beat):
    """이 비트에 붙은 클립 길이의 합(초)."""
    tot = 0.0
    for s in [beat.get("primary")] + list(beat.get("alternates") or []):
        if s and s.get("end") is not None and s.get("start") is not None:
            tot += max(0.0, float(s["end"]) - float(s["start"]))
    return tot


def _fill_beat_screen_time(beats, seg_map, max_alts=6):
    """비트마다 **화면 길이 합 ≥ 대사 읽는 시간**이 되게 컷을 더 붙인다(2026-07-31).

    ★왜 필요한가 — 실측(job 61a2678a8e03, 사장님 영상 육안 검증):
      계획서상으론 6비트 중 5비트가 화면과 정확히 맞았는데 **실제 영상은 어긋났다**.
      비트별 말 길이 합 31.9초 vs 붙인 화면 길이 합 13.8초(절반 이하)였고,
      CTA는 7.9초를 말하는데 화면이 1.5초뿐이었다. 모자란 화면을 렌더가 다음 클립으로
      메우면서 밀림이 누적돼, 16초 "투명해서 답답하지 않아요"에 계란 붓는 팬(다음 비트의
      화면)이 걸렸다. 프롬프트는 seg_ids를 "2~4개"로 **개수만** 요구해서 1.3초짜리 컷
      하나로도 통과했다 — 대본을 아무리 고쳐도 이건 안 고쳐진다.

    붙일 컷은 **아직 안 쓴 것** 중에서 고른다(같은 소스 영상 우선 = 결이 안 튄다).
    인벤토리가 동나면 그때만 재사용을 허용한다 — 같은 화면이 두 번 나오는 게
    엉뚱한 화면이 걸리는 것보다 낫다.
    """
    if not beats:
        return beats
    used = set()
    for b in beats:
        for s in [b.get("primary")] + list(b.get("alternates") or []):
            if s and s.get("seg_id"):
                used.add(s["seg_id"])
    for b in beats:
        need = float(b.get("target_seconds") or 0)
        have = _beat_screen_secs(b)
        if have >= need or not b.get("primary"):
            continue
        home = (b["primary"] or {}).get("video_id")
        # ★말이 통하는 장면부터 채운다(2026-07-31 2차).
        #   1차 수정은 "같은 소스·앞순서"로만 골라서, 결국 video_assemble의 땜질
        #   (:445-471 = 릴의 안 쓴 뒷부분 아무 데나)을 edit_plan 단계로 앞당긴 것뿐이었다.
        #   실측: "요리할 때마다 닦는 게 진짜"에 스티커 정지컷, "스티커까지 붙이니까"에
        #   실리콘 도구 컷. → 나레이션과 '변화:'·'화면:' 문구가 겹치는 장면을 먼저 쓴다.
        words = {w for w in _claim_key(b.get("narration") or "")}

        def _rel(s):
            txt = f"{s.get('change') or ''} {s.get('scene_desc') or ''}"
            return len(words & set(_claim_key(txt)))

        pool = sorted(seg_map.values(),
                      key=lambda s: (-_rel(s), s.get("video_id") != home, s.get("start") or 0))
        alts = list(b.get("alternates") or [])
        for s in pool:
            if have >= need or len(alts) >= max_alts:
                break
            sid = s.get("seg_id")
            if not sid or sid in used:
                continue
            g = _ground_ref({"seg_id": sid}, seg_map)
            if not g:
                continue
            alts.append(g)
            used.add(sid)
            have += max(0.0, float(g["end"]) - float(g["start"]))
        if have < need:                     # 인벤토리 소진 → 재사용 허용(빈 화면보다 낫다)
            for s in pool:
                if have >= need or len(alts) >= max_alts:
                    break
                g = _ground_ref({"seg_id": s.get("seg_id")}, seg_map)
                if not g or g["seg_id"] == (b["primary"] or {}).get("seg_id"):
                    continue
                alts.append(g)
                have += max(0.0, float(g["end"]) - float(g["start"]))
        b["alternates"] = alts
    return beats


# CTA로 인식하는 role 표기(모델이 한글·영문을 섞어 쓴다).
_CTA_ROLES = ("cta", "CTA", "씨티에이", "행동유도")
# 반말 종결 → 존댓말(2026-07-30 실측: CTA가 "댓글에 커피 남겨줘"로 나온 건이 있었다).
_BANMAL_FIX = [("남겨줘", "남겨주세요"), ("달아줘", "달아주세요"), ("써줘", "써주세요"),
               ("해줘", "해주세요"), ("눌러줘", "눌러주세요"), ("봐줘", "봐주세요"),
               ("해봐", "해보세요"), ("가봐", "가보세요"), ("써봐", "써보세요")]


def _is_cta(beat):
    role = (beat.get("role") or "")
    return any(k.lower() in role.lower() for k in _CTA_ROLES)


def _has_comment_cta(text):
    """대사에 **댓글 유도**가 들어있나(2026-08-03 사장님: "CTA는 고정으로 댓글에 OO 남겨주세요로").

    프로필 링크·바로가기 안내는 우리에게 없는 경로다 — 은행에서 그 계열을 뺐지만(bank_assemble)
    프롬프트만으론 새므로 코드로도 확인한다. 표현 흔들림('남겨주세요'/'적어주세요'/'달아주세요')은
    허용한다 — 고정하려는 건 **유입 경로**지 어미가 아니다."""
    t = (text or "")
    if "댓글" not in t:
        return False
    return any(v in t for v in ("남겨", "적어", "달아", "써주", "써 주", "남기"))


def _cta_fix_narration(cand):
    """CTA 비트에 **댓글 유도**가 없으면 대사를 갈아끼운다(2026-08-03, 제자리 수정).

    우선순위: 후보가 정한 `cta_line`(유도 있을 때) → `cta_keyword`로 조립 → 기본 문구.
    비트를 새로 붙이지 않는다 — 화면이 하나 더 필요해지고 길이도 늘어난다.
    ⚠️호출 위치가 중요하다: **최종 후보 확정 뒤**에만 부른다(길이 재생성 판단 오염 방지).
    """
    plan = (cand or {}).get("plan") or {}
    beats = plan.get("beats") or []
    ctas = [b for b in beats if _is_cta(b)]
    if not ctas or any(_has_comment_cta(b.get("narration")) for b in ctas):
        return cand
    story = cand.get("story") or {}
    line = (story.get("cta_line") or "").strip()
    if not _has_comment_cta(line):
        kw = (story.get("cta_keyword") or "").strip()
        line = f"댓글에 '{kw}' 남겨주세요" if kw else "궁금하시면 댓글 남겨주세요"
    for b in beats:
        if _is_cta(b):
            b["narration"] = line
            b["target_seconds"] = round(max(1.5, len(line) / _SYLLABLES_PER_SEC), 1)
            break
    return cand


def _strip_mid_cta(cand):
    """CTA가 아닌 비트에 섞인 **댓글 유도 문장**을 걷어낸다(2026-08-03 사장님: "CTA가 두 번씩 반복됨").

    실측 job e72379132e7b: 결과 비트가 "...정보 필요하시면 댓글에 '김밥' 남겨주세요"로 끝나고
    바로 다음 CTA 비트가 또 댓글 유도 — 시청자에겐 같은 말 두 번이다. 재료가 짧은 소재에서
    모델이 모자란 분량을 CTA 문구로 채우는 패턴. 프롬프트 지시로는 안 지켜져 코드로 자른다.

    문장 단위로만 자른다(문장 일부를 수술하지 않는다). 전부 CTA 문장이라 남는 게 없으면
    원문 유지 — 빈 비트를 만드는 것보다 중복이 낫다. 자막(caption_lines)은 비워 재분할시킨다.
    ⚠️호출 위치: _cta_fix_narration과 같은 자리(최종 후보 확정 뒤) — 길이 재생성 판단 오염 방지.
    """
    beats = ((cand or {}).get("plan") or {}).get("beats") or []
    for b in beats:
        if _is_cta(b):
            continue
        narr = (b.get("narration") or "")
        if not _has_comment_cta(narr):
            continue
        parts = re.split(r"(?<=[.!?。])\s+", narr.strip())
        kept = [p for p in parts if p.strip() and not _has_comment_cta(p)]
        if not kept or len(kept) == len(parts):
            continue
        b["narration"] = " ".join(kept).strip()
        b["caption_lines"] = None
        b["target_seconds"] = round(max(1.5, len(b["narration"]) / _SYLLABLES_PER_SEC), 1)
    return cand


def _ensure_cta_beat(beats, cand):
    """CTA 비트가 없으면 후보의 cta_line으로 만들어 붙인다(2026-07-31).

    ★왜 코드가 보장하나: 라이브 경로(백본 시간순 고정) 실측에서 **20건 중 9건에 CTA 비트가
      아예 없었다**. 파이프라인이 지우는 게 아니라 모델이 처음부터 안 만든다 — 백본이 20초
      소스의 장면 순서를 고정하니 마무리 장면이 없어 '결과'에서 끝내버린다.
      프롬프트엔 이미 CTA가 필수라고 적혀 있고(지시로는 안 지켜졌다), 스키마엔 cta_line이
      따로 있으니 그걸 쓴다. 댓글 유도가 빠지면 영상의 목적 자체가 사라진다.

    화면은 마지막 비트의 컷을 재사용한다 — 새 장면을 지어낼 수 없고, CTA는 보통 마무리
    화면 위에 얹히는 자리다. cta_line이 비면 아무것도 하지 않는다(억지 생성 금지).

    ★screen_pinned=True(2026-08-01, F4): 여기서 고른 화면을 뒤이은 _assign_timeline이
    인덱스 배분으로 덮어쓰면 이 함수의 존재 의미가 없어진다 — screen_pinned 플래그로
    "이미 정해진 화면이니 재배정하지 마라"를 표시한다.
    """
    if not beats or any(_is_cta(b) for b in beats):
        return beats
    line = (cand.get("cta_line") or "").strip()
    if not line:
        return beats
    last = beats[-1]
    src = (last.get("alternates") or [None])[-1] or last.get("primary")
    if not src:
        return beats
    beats = list(beats) + [{
        "beat_idx": len(beats), "role": "CTA", "narration": line, "caption_lines": None,
        "target_seconds": round(max(1.5, len(line) / _SYLLABLES_PER_SEC), 1),
        "primary": src, "alternates": [], "effect": "cut",
        "fit": int(last.get("fit") or 0), "forced": False, "screen_pinned": True,
    }]
    return beats


_LONG_BEAT_CHARS = 55       # 이보다 길면 자막줄을 무효화한다(2026-08-01부터 화면은 안 나눈다)
# (2026-08-01 폐지) 예전엔 분할 시 파편 비트 방지에 썼다 — 화면 분할 자체가 없어져 미사용이나,
# 다른 테스트가 여전히 참조하므로 상수는 남겨둔다.
_MIN_SPLIT_CHARS = 18
# (2026-08-01 폐지) 예전엔 분할 상한이었다 — 화면 분할이 없어져 미사용, 상수만 유지.
_MAX_BEATS = 8


def _split_long_beats(beats):
    """긴 비트의 자막줄을 무효화한다(2026-08-01 재설계 — 화면은 절대 안 나눈다).

    이전엔 문장 경계로 비트 자체를 쪼개 화면도 나눴는데, 이러면 비트 수가 늘어나
    _assign_timeline 재호출 시 세트 수(불변)보다 많아져 화면 중복이 생겼다(2026-07-31
    실측 job 8226822c5b09). 새 원칙: 화면(슬롯)은 파이프라인 전체에서 불변 — 긴 비트는
    자막만 여러 줄로 나눠 보여주고 화면은 그대로 공유한다."""
    if not beats:
        return beats
    for b in beats:
        narr = (b.get("narration") or "").strip()
        if len(narr) > _LONG_BEAT_CHARS:
            b["caption_lines"] = None
    return beats


def _fix_beat_structure(beats):
    """모델이 자주 어기는 **구조** 세 가지를 코드에서 바로잡는다(2026-07-30).

    프롬프트에 문장을 더 넣어 고치려 하지 않는다 — 이 파일엔 '제약 과적재로 ★17개가
    충돌했다'는 이력이 있고, 실제로 오늘 감각어 지시를 강화하자 어미가 무너졌다.
    지킬 수 있는 건 코드가 지킨다.

    ① CTA는 마지막이어야 한다 — 실측(job d01f6567)에서 CTA 뒤에 '보충' 비트가 붙어
       영상이 CTA로 안 끝났다. CTA 비트를 맨 뒤로 옮긴다(내용은 안 건드림).
    ② CTA 반말 금지 — "댓글에 커피 남겨줘"가 나왔다. 존댓말로 교정한다.
    ③ 비트 하나에 문장을 몰아넣지 않는다 — 55자 넘고 문장이 2개 이상이면 한 문장만
       남기고 뒤는 다음 비트로 넘기지 않는다(장면·seg 배정이 틀어지므로). 대신 **자르지 않고**
       그대로 두되, 자막줄(caption_lines)만 무효화해 자막이 규칙대로 다시 끊기게 한다.
       ※ 길이 자체는 프롬프트·재생성이 담당한다. 여기서 문장을 지우면 이야기가 깨진다.
    """
    if not beats:
        return beats
    # ① CTA 뒤에 다른 비트가 있으면 CTA를 맨 뒤로.
    cta_idx = [i for i, b in enumerate(beats) if _is_cta(b)]
    if cta_idx and cta_idx[-1] != len(beats) - 1:
        i = cta_idx[-1]
        beats = beats[:i] + beats[i + 1:] + [beats[i]]
    # ② 마지막(=CTA 자리) 비트의 반말 종결 교정. 존댓말 톤 일관.
    last = beats[-1]
    narr = last.get("narration") or ""
    for a, b in _BANMAL_FIX:
        if narr.rstrip(" .!?").endswith(a):
            last["narration"] = narr.rstrip(" .!?")[: -len(a)] + b
            last["caption_lines"] = None        # 문장이 바뀌었으니 옛 자막줄은 무효
            break
    # ③ 긴 비트는 **문장 경계로 쪼개** 화면을 나눈다(문장은 안 지운다).
    beats = _split_long_beats(beats)
    # beat_idx 재부여(① 재배치로 어긋났을 수 있다 — 하류가 이 값으로 TTS·자막을 매칭한다).
    for i, b in enumerate(beats):
        b["beat_idx"] = i
    return beats


# 말투 게이트 임계(2026-07-30). 이 아래면 '옆에서 썰 푸는' 맛이 안 난다고 본다.
# 실측 기준: 목표 톤을 낸 후보는 1.00, 어미가 무너진 후보는 0.67·감각어 부족은 0.93이었다.
_TONE_GATE = 0.8


# 감각어 하한(2026-07-31). 프롬프트 목표는 4개지만 실측 평균이 1.9개라 4로 잡으면 후보가
# 거의 다 탈락해 하한이 무의미해진다. 3으로 두면 "있는 것 중 감각어가 많은 쪽"을 실제로 고른다.
_SENSORY_FLOOR = 3


def _cand_sensory(cand):
    """후보 대본의 감각어 개수(오감 형용사·의태어, 중복 제외)."""
    from shopping_shorts import tone_score
    beats = (cand.get("plan") or {}).get("beats") or []
    text = "\n".join((b.get("narration") or "").strip() for b in beats).strip()
    return tone_score.sensory_profile(text)["count"] if text else 0


def _cand_tone(cand):
    """grounding된 후보의 순수 말투 점수(0~1) — 어미 유형 다양성·감각어 밀도.
    _candidate_quality는 fun까지 섞은 값이라, 게이트는 말투만 따로 본다."""
    from shopping_shorts import tone_score
    beats = (cand.get("plan") or {}).get("beats") or []
    text = "\n".join((b.get("narration") or "").strip() for b in beats).strip()
    return tone_score.score_conversational(text)["score"] if text else 0.0


def _candidate_quality(beats):
    """후보 대본의 품질(0~1) — 대화체(tone)·재미강도(fun, D14). 전 비트 나레이션을 이어
    tone_score로 재는 순수 계산(Gemini 없음). 나레이션이 비면 0(매칭점수만으로 판정).
    P1: scene_first는 헌장 1콜이라 위키생성의 _verify_and_fix 품질정렬을 못 받았다 — 추천
    선택에 품질을 직접 넣어 '말투 좋고 재미장치 있는' 후보가 추천되게 한다."""
    from shopping_shorts import tone_score
    # ★비트 경계를 줄바꿈으로 잇는다(2026-07-30). 공백으로 이으면 나레이션에 마침표가 없는
    #   후보(실측: 07-30 job e9e74aea)가 tone_score에서 **한 문장**으로 세어져 어미 다양성이
    #   무조건 1.0으로 통과했다 — 밋밋해도 만점. tone_score._sentences는 \n도 문장 경계로 본다.
    text = "\n".join((b.get("narration") or "").strip() for b in beats).strip()
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


_BANNED_PHRASES = (
    "신세계", "삶의 질 상승", "완벽 해결", "쾌적하게", "고민 해결",
    "완벽함", "꿀템", "갓성비", "인기 만점", "볼 때마다 행복",
)


def _common_prefix_len(a, b):
    n = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        n += 1
    return n


def _banned_phrase_fuzzy_hit(beats, tail_tolerance=2):
    """금지어의 활용형(어미만 바뀐 변형) 탐지 — 정확일치(아래)가 놓치는 '쾌적하게'→'쾌적한'
    같은 경우를 잡는다(2026-07-29 실측: 실제 생성에서 새어나온 사례).

    n-gram Jaccard를 먼저 검토했으나 계산해보니 부적합했다: 임계를 낮추면 '신세계'가
    무관한 단어 '세계'에도 오탐(둘 다 겹침비율 0.5~0.67대로 비슷하거나 더 높음)하고,
    올리면 정작 잡으려던 변형이 안 걸린다. 한국어 활용형은 어간(앞)이 고정되고 어미(뒤)만
    바뀌므로 **접두 일치**가 원리에 더 맞다: 끝 tail_tolerance자 이내만 다르고 나머지
    앞부분이 정확히 같은 어절을 찾는다. 공백 있는 복합구(예: '완벽 해결')는 단일 어절의
    활용형 문제가 아니라 정확일치만으로 충분해 대상에서 뺌. 2자 이하 금지어(예: '꿀템')도
    뺌 — 접두 1자만 요구하면 오탐이 너무 커진다(예: '꿀템' vs 무관한 '꿀피부').
    ⚠️'꿀템'→'꿀팁' 같은 동의어(어간 자체가 다름)는 이 방식으로도 못 잡는다 — 그건
    _BANNED_PHRASES에 직접 추가해야 한다(오탐 없이 잡을 방법이 없음)."""
    text = " ".join((b.get("narration") or "") for b in (beats or []))
    words = [w for w in re.split(r"[^가-힣]+", text) if w]
    for phrase in _BANNED_PHRASES:
        if " " in phrase or len(phrase) < 3:
            continue
        # ★need의 하한이 2면 3자 금지어가 "앞 2자만 같으면 걸림"이 된다(2026-08-03 실사고):
        #   '완벽함'을 잡으려다 **'완벽해요'·'완벽하게'**까지 0점 반려됐다. '완벽해요'는
        #   상투어가 아니라 평범한 한국어다. 실측(job 6849ebdf1bb1): 심사위원이 최고점
        #   (0.733)을 준 후보가 이 오탐으로 규칙점수 0점이 돼 2등으로 밀렸다.
        #
        #   ★단순히 하한을 올리면 원래 잡던 것을 놓친다('쾌적하게'→'쾌적한'은 공통 앞이
        #     2자뿐이다 — 3번째가 하/한으로 갈린다). 길이로만 재면 두 사례를 못 가른다.
        #   → **금지어가 활용어인지**로 가른다. '~하게/~하다' 꼴은 어간(앞 2자)만 같으면
        #     활용형이 맞지만, '완벽함'처럼 명사형으로 끝나는 말은 그 자체가 통째로 있어야
        #     상투어다. 전자만 어간 매칭을 허용한다.
        stem = phrase
        for suf in ("하게", "하다", "스럽게", "롭게"):
            if phrase.endswith(suf) and len(phrase) - len(suf) >= 2:
                stem = phrase[: -len(suf)]
                break
        if stem != phrase:
            need = len(stem)          # 활용어: 어간만 같으면 활용형으로 본다
        else:
            need = max(len(phrase) - tail_tolerance, len(phrase) - 1, 3)
        for w in words:
            if len(w) >= need and _common_prefix_len(phrase, w) >= need:
                return True
    return False


def _banned_phrase_hit(beats):
    """AI/상세페이지 문투 금지어(2026-07-29 사장님 확정, 실측 A/B/C 후보가 반복 사용한 상투어)
    포함 여부. 하나라도 있으면 True → _score_candidate가 0점으로 반려한다. 프롬프트로만
    막으면 간헐적으로 새는데(실측: 추천작이 오히려 위반) 채점에서 강제로 걸러야 새지 않는다.
    정확일치 + 활용형 퍼지매칭(_banned_phrase_fuzzy_hit) 둘 다 검사한다."""
    text = " ".join((b.get("narration") or "") for b in (beats or []))
    if any(p in text for p in _BANNED_PHRASES):
        return True
    return _banned_phrase_fuzzy_hit(beats)


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


def _plagiarism_penalty(beats, source_full_texts, threshold=0.5, n=6):
    """표절 감점(2026-07-30): _plagiarism_flags와 같은 n-gram 겹침 계산을 채점에도 반영한다.
    이제까지는 겹침을 감지해 리뷰 화면에 경고 배지만 띄우고(app.py) 점수에는 안 반영했다 —
    _banned_phrase_hit이 겪은 것과 같은 구멍(2026-07-29 주석: '프롬프트로만 막으면 간헐적으로
    새는데 채점에서 강제로 걸러야 새지 않는다')이 표절에도 그대로 있었다. 겹침은 금지어처럼
    이분법이 아니라 연속값이라 즉시 0점 대신 초과분 비례 감점(최대 0.3, _length_penalty와
    동일 상한)으로 다룬다 — 짧은 흔한 표현까지 억울하게 0점 처리되는 걸 피한다."""
    if not source_full_texts or not beats:
        return 0.0
    worst = 0.0
    for beat in beats:
        narration = beat.get("narration", "")
        for source_text in source_full_texts:
            worst = max(worst, _ngram_overlap(narration, source_text, n))
    return round(min(0.3, max(0.0, worst - threshold)), 3)


def _score_candidate(plan, avoid_hooks=None, target_seconds=None, source_full_texts=None):
    """후보 추천 점수(0~1): 매칭(fit·억지없음·장면다양성) + 품질(대화체·재미강도). 빈 beats면 0.0.
    avoid_hooks(novelty 감점, belt-and-suspenders): 최근 영상이 쓴 훅 목록. 첫 비트(=훅)가
    그와 n-gram 겹치면 감점 → 프롬프트 회피를 무시하고 같은 훅을 낸 후보가 추천되는 걸 막는다.
    컷 리듬 감점(T6): 파편화·전역 반복이 심한 후보를 강등한다.
    길이 감점(세션#2): target_seconds가 주어지면 목표초에서 벗어난 후보를 강등한다.
    금지어 반려(2026-07-29): 상세페이지 상투어가 하나라도 있으면 무조건 0점.
    표절 감점(2026-07-30): source_full_texts가 주어지면 원문 n-gram 겹침 초과분만큼 감점."""
    beats = plan.get("beats") or []
    if not beats:
        return 0.0
    if _banned_phrase_hit(beats):
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
    score -= _plagiarism_penalty(beats, source_full_texts)  # 2026-07-30: 원문 베끼기 강등
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
            return _normalize_video_type(raw.get("video_type"))  # 옛 key도 새 key로 흡수
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
    """앵커(respined 아님)이면서 fit<=3 **또는 forced=True**인 비트의 나레이션만 화면(scene_desc)에
    맞게 1회 Gemini 호출로 미세수정. 대상 0개면 호출 없이 그대로. 실패 시 원문 유지(fail-open).

    ★2026-07-29(사장님 '장면 안 맞는 대본'): 예전엔 fit<=3만 잡아, 모델이 fit=4를 주면서 forced=True
    (장면이 말과 안 맞는데 억지로 붙임)로 표시한 비트가 재작성에서 빠져나갔다. forced는 모델이 스스로
    '억지'라고 인정한 명시 신호이므로 fit 점수와 무관하게 반드시 화면에 맞춰 고친다."""
    weak = [b for b in beats
            if not b.get("respined")
            and ((0 < int(b.get("fit") or 0) <= 3) or bool(b.get("forced")))]
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
                "detected_type": _normalize_video_type(video_type), "affiliate_target": ""}

    scripted = bool(given_script and given_script.strip())
    if scripted:
        video_type = _normalize_video_type(video_type)  # 옛 key 흡수
        n_alternates = _SCRIPTED_N_ALT
        prompt = _SCRIPTED_PROMPT.format(
            given_script=given_script.strip()[:4000], inventory=inventory, n_alternates=n_alternates)
    else:
        if video_type is None:
            video_type = detect_video_type(source_scripts)
        video_type = _normalize_video_type(video_type)  # 옛 key 흡수(감지값·인자 모두)
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
    def _line(i, f):
        base = f"  {i+1}. {f.get('seg_id')} [{f.get('action') or '-'}] {f.get('scene_desc', '')}"
        t = (f.get('text') or '').strip()
        return base + (f"  (원본대사: {t})" if t else "")
    lines = "\n".join(_line(i, f) for i, f in enumerate(flow))
    sub_vids = [s.get("video_id") for s in (source_scripts or [])
                if s.get("video_id") and s.get("video_id") != backbone_video and s.get("segments")]
    sub_block = ("(이 영상엔 서브 소스가 없다 — 위 백본 흐름만 따르면 된다.)" if not sub_vids
                 else f"서브 소스: {', '.join(sub_vids)} — **이 목록의 소스 각각을 최소 한 번씩은 "
                      "화면에 등장시켜라**(하나도 안 쓰인 채로 끝내지 마라).")
    return (
        f"[백본 흐름 — 메인영상 {backbone_video}의 시간순 전개(장면 순서 + 원본 대사 흐름)]\n{lines}\n"
        "★이 흐름을 '스토리 전개'로 삼아 **창의적으로 변형**해 따라가라 — 순서·전개는 계승하되 "
        "문장은 우리 것으로 새로 써라(원본 대사 베끼기 절대 금지, 같은 뜻 다른 구어체로 패러프레이즈).\n"
        "  (BAD) 원본대사가 \"엄마가 옆에서 보더니 진짜 곱네 하시더라고요\"인데 이 문장을 "
        "그대로/거의 그대로 옮겨쓰기.\n"
        "  (GOOD) 같은 장면·같은 뜻이지만 다른 표현: \"엄마가 딱 보시더니 놀라시더라니까요\".\n"
        f"★서브 소스 식별: 아래 인벤토리에서 seg_id가 위 흐름의 '{backbone_video}-숫자' 형식이 "
        f"**아닌** 항목은 전부 다른 영상(서브) 컷이다. {sub_block} 화면 순서는 위 뼈대(백본)를 "
        "따르되(과정이 앞뒤로 튀는 뒤죽박죽 금지), 서브 컷은 이렇게 적극 활용해라(안 쓰면 후보가 "
        "단조로워지고 서브 소스가 통째로 낭비된다):\n"
        "  · 교체(Replace): 백본의 어떤 장면보다 서브에 같은 의미의 더 직관적·자극적 컷이 있으면 "
        "그 자리에 바꿔 넣고, 그 컷의 동작을 대사에 그대로 반영해라.\n"
        "    (예) 백본 장면이 '손으로 대충 문지름'인데 서브에 같은 의미의 '거품 풍성하게 닦아내는' "
        "더 직관적 컷이 있으면 그 서브 컷으로 교체.\n"
        "  · 삽입(Insert): 백본에 없는 새 정보·리액션(주변인 반응·인증·비법)이 서브에 있으면 흐름 "
        "중간에 끼우고, 문두에 접착어(\"알고 보니\"·\"보시는 것처럼\"·\"이럴 땐\")를 붙여 자연스럽게 "
        "이어라. ★서브 컷의 동작이 백본 흐름과 안 맞아도 좋다 — 그럴 땐 특정 동작을 지목하지 않는 "
        "리액션/감상 문장(\"이거 보고 진짜 놀랐잖아요\" 류)을 그 화면에 얹어라(행위 나레이션 강제 "
        "금지 — 화면·대사가 안 맞는 것보다 낫다).\n"
        "  · ★후보마다 위 서브 소스 목록 전부(적어도 하나씩)를 화면에 반영해라 — 후보 3개 다 백본 "
        "장면만 그대로 따라가거나, 서브 소스 일부만 쓰고 나머지를 버리면 안 된다.")


def _single_source_candidates(source_scripts, seg_map, target_seconds,
                              n_candidates, call, detected, judge=False):
    """1소스 전용 대본 생성(2026-08-04, handoff 남은작업①의 '핵심 배선').

    기존 경로는 목표길이 조정+훅 주입'만' 하고 생성은 범용 생성기가 해서
    ① 훅이 10패턴 뼈대를 무시하고 ② 총량이 목표(원본 90%, 하한 20초)에 못 미치거나
    튀었다(실측 job ae8961b5f3af: 원본 22.0초 → 플랜 14.6초, 훅 패턴 밖).

    여기서는 single_source가 처음부터 끝까지 운전한다:
      컷 선별·순서(select_and_order) → 후보마다 다른 훅 패턴(hook_patterns.choose)
      → script_prompt(문장수·글자예산 강제) → over_budget/shrink 교정루프
      → covers 기반으로 화면을 코드가 배정(모든 컷 100% 커버 = 화면길이가 예산 그대로).
    실패(빈 후보)면 None을 돌려 기존 경로로 폴백한다(회귀0).
    """
    from shopping_shorts import single_source, hook_patterns
    _src_entry = next((s for s in source_scripts if s.get("segments")), {})
    segments = _src_entry.get("segments") or []
    # ★video_id 필수(2026-08-04 실사고 job ed7445bfa4e7): extract의 세그먼트에는 video_id가
    #   없다(소스 키 아래 중첩). 없이 내보내면 조립기가 원본 mp4를 못 찾아 그 비트의 클립이
    #   전멸하고, video_assemble의 '클립 0개 비트는 조용히 스킵'에 걸려 **훅이 통째로
    #   빠진 미리보기**가 나갔다(화면보충이 붙은 비트만 우연히 살아남았다).
    _vid = _src_entry.get("video_id")
    for _s in segments:
        _s.setdefault("video_id", _vid)
    span, budget, used, order = single_source.select_and_order(segments, target_seconds)
    if not order:
        return None
    _mat = " ".join((s.get("full_text") or "") for s in source_scripts)
    pats = hook_patterns.choose(max(3, n_candidates), material_text=_mat)
    if not pats:
        return None
    print("[1소스대본] 원본 %.1f초 → 예산 %.1f초, 컷 %d개, 훅후보: %s"
          % (span, budget, len(order), " / ".join(p[1] for p in pats)), file=sys.stderr)
    src_texts = [s.get("full_text", "") for s in source_scripts]
    cands = []
    for i in range(max(1, n_candidates)):
        pat = pats[i % len(pats)]
        prompt = single_source.script_prompt(order, used, hook_patterns.prompt_block(pat))
        beats = single_source.parse_beats(call(prompt, single_source.BEATS_SCHEMA))
        # 총량 교정루프(최대 2회) — 넘치면 표현만 줄여 다시 받는다.
        for _ in range(2):
            over, _secs, _o = single_source.over_budget(beats, used)
            if not beats or not over:
                break
            b2 = single_source.parse_beats(
                call(single_source.shrink_prompt(beats, used), single_source.BEATS_SCHEMA))
            if b2:
                beats = b2
        if not beats:
            continue
        # CTA 교정(2026-08-04): 마지막 문장에 '댓글'이 없으면 그 문장만 고쳐 받는다(2회).
        # 실측: 프롬프트 강화 후에도 3후보 중 1~2개가 감상문으로 끝났다 — 코드로 보장한다.
        for _ in range(2):
            if not single_source.cta_missing(beats):
                break
            b3 = single_source.parse_beats(
                call(single_source.fix_cta_prompt(beats, _mat), single_source.BEATS_SCHEMA))
            if b3 and not single_source.cta_missing(b3):
                beats = b3
        if single_source.cta_missing(beats):
            # LLM 교정까지 실패(키 소진·429)해도 CTA는 보장 — 결정적 문구로 마지막 문장 교체.
            kw = "나도" if "나도" in _mat else "정보"
            beats[-1]["narration"] = f"방법이 궁금하면 댓글에 '{kw}' 남겨주시면 바로 보내드릴게요."
        # ★CTA 비트 생존 보장(2026-08-04 실측): 모델이 CTA를 제대로 써도 covers가 비면
        # 아래 커버 배정에서 컷 0개 → 통째로 탈락 → 앞 문장이 [cta] 자리로 밀려
        # "안심이라 최고예요"류 감상문이 CTA가 됐다(fix_cta 호출 0회가 증거 — 프롬프트
        # 문제가 아니었다). 마지막 컷을 CTA 비트 소유로 강제한다.
        if beats:
            lastc = len(order)
            if lastc not in {int(c) for c in (beats[-1].get("covers") or [])
                             if str(c).lstrip("-").isdigit()}:
                for b in beats[:-1]:
                    b["covers"] = [c for c in (b.get("covers") or [])
                                   if str(c).lstrip("-").isdigit() and int(c) != lastc]
                beats[-1]["covers"] = (beats[-1].get("covers") or []) + [lastc]
        # 고조 연결어(2026-08-04 사장님 지시 "꼭 넣어줘"): 프롬프트로는 0/3 — 글자예산
        # 규칙('제일 중요')에 밀리고 shrink의 '수식어 덜어내라'에 깎인다(실측). 중간 비트
        # 하나에 코드가 앞붙인다(후보마다 다른 연결어 = 말투 변주, +4~8자는 예산 오차 안).
        _CONNS = ["심지어", "놀랍게도", "근데 이게 대박인 게", "더군다나"]
        if len(beats) >= 3 and not any(
                cn in (b.get("narration") or "") for b in beats for cn in _CONNS):
            # ★고조 재작성(2026-08-04 사장님 "연결어랑 뒷내용이 안 이어진다"): 기계적
            #   앞붙이기는 '심지어' 뒤에 이미 말한 장점이 와서 고조가 안 됐다. LLM이
            #   자리를 고르고 **앞에 안 나온 새 장점**으로 그 문장을 다시 쓴다.
            #   실패(키 소진 등) 시에만 종전 기계식 앞붙이기로 폴백.
            _esc = call(single_source.escalate_prompt(beats), single_source.ESCALATE_SCHEMA)
            _n = _esc.get("n") if isinstance(_esc, dict) else None
            _txt = (_esc.get("narration") or "").strip() if isinstance(_esc, dict) else ""
            if (_txt and isinstance(_n, int) and 2 <= _n <= len(beats) - 1
                    and any(c in _txt for c in _CONNS)):
                beats[_n - 1]["narration"] = _txt
            else:
                mid = beats[len(beats) // 2]
                mid["narration"] = f"{_CONNS[i % len(_CONNS)]} {mid['narration']}"
        # ★스타일 통째 리라이트(2026-08-05): 컷 매핑 생성은 광고 카피 결을 못 벗는다(3바퀴
        #   실측) → 완성된 나레이션을 스타일 few-shot 보고 문체만 다시 쓴다(40/40 검증 방식).
        #   문장수·순서 고정이라 covers 유효. 실패 시 원본 유지·스타일 off면 no-op.
        #   ★trio(기본): 후보마다 다른 채널 스타일 — A=메종(발견담)/B=채이(가족드라마)/
        #   C=스탠다드(유머목격담). 사장님 확정 3각(2026-08-05).
        from shopping_shorts import style_profiles as _sp0
        beats = single_source.apply_restyle(beats, call,
                                            style_name=_sp0.candidate_style(i))
        # ★빈 나레이션 비트는 **커버 배정 전에** 걸러낸다(2026-08-04 라이브 실측 job
        #   bcdf871a6d57: 추천 후보가 16.8초 — 버려진 비트의 컷이 같이 사라져 하한 미달).
        #   먼저 거르면 아래 '구멍은 직전 비트가 이어받는다'가 그 컷들을 살린다.
        beats = [b for b in beats if (b.get("narration") or "").strip()]
        if not beats:
            continue
        # covers → 화면 배정. 모델이 빠뜨린 컷은 직전 비트에 붙여 **컷 100% 커버**를 코드가
        # 보장한다(화면 총길이 == used == 예산 → 길이 하한이 프롬프트 아닌 코드로 지켜진다).
        covered_by = {}                      # 컷 번호(1-base) → 비트 인덱스
        for bi, b in enumerate(beats):
            for c in (b.get("covers") or []):
                try:
                    c = int(c)
                except (TypeError, ValueError):
                    continue
                if 1 <= c <= len(order):
                    covered_by.setdefault(c, bi)
        last_bi = 0
        for c in range(1, len(order) + 1):
            if c in covered_by:
                last_bi = covered_by[c]
            else:
                covered_by[c] = last_bi      # 구멍은 직전 비트가 이어받는다
        beat_cuts = {}
        for c in sorted(covered_by):
            beat_cuts.setdefault(covered_by[c], []).append(c)
        plan_beats = []
        for bi, b in enumerate(beats):
            narration = (b.get("narration") or "").strip()
            cuts = beat_cuts.get(bi) or []
            if not narration or not cuts:
                continue
            covered = [order[c - 1] for c in cuts]
            def _clean(s):
                return {k: v for k, v in s.items() if k != "_dur"}
            plan_beats.append({
                "beat_idx": len(plan_beats), "role": "",
                "narration": narration, "caption_lines": None,
                "target_seconds": round(max(1.5, len(narration) / _SYLLABLES_PER_SEC), 1),
                "primary": _clean(covered[0]),
                "alternates": [_clean(s) for s in covered[1:]],
                "effect": "cut", "fit": 5, "forced": False,
            })
        if len(plan_beats) < 3:
            continue
        plan_beats[0]["role"] = "hook"
        plan_beats[-1]["role"] = "cta"
        for b in plan_beats[1:-1]:
            b["role"] = "story_event"
        if len(plan_beats) >= 4:
            plan_beats[-2]["role"] = "story_resolution"
        plan_beats = _fix_beat_structure(plan_beats)
        # ★비트별 콘폼(2026-08-04 실측 job 923d/285d): 총량은 예산 안인데 **비트별로**
        #   문장이 제 화면보다 길면 _fill_beat_screen_time이 클립을 재사용해 화면을
        #   나레이션에 맞춰 뻥튀기 — 원본 43초짜리가 61~80초 영상이 됐다(중복 금지 위반).
        #   1소스는 화면(컷 100% 커버)이 주인이다 — 문장을 화면 길이에 맞춰 압축한다.
        for b in plan_beats:
            if b is plan_beats[-1]:
                continue    # CTA는 압축 제외 — 마지막 컷이 짧으면 보상 문구("보내드릴게요")가
                            # 잘려나간다(실측: 1.9초 컷에 맞춰 "댓글에 나도 남겨요"로 뭉개짐).
                            # 화면 부족분은 아래 _fill_beat_screen_time이 채운다.
            if any((b["narration"] or "").startswith(c) for c in _CONNS):
                continue    # 고조 문장은 압축 제외 — conform이 연결어를 군더더기로 깎아
                            # 사장님 지시("연결어 꼭") 문장이 소리 없이 사라졌다(실측).
            _scr = sum(max(0.0, float(s.get("end") or 0) - float(s.get("start") or 0))
                       for s in [b["primary"]] + b["alternates"])
            _spoken = len("".join((b["narration"] or "").split())) / _SYLLABLES_PER_SEC
            if _scr > 0.5 and _spoken > _scr * 1.1:
                _new = conform_narration(b["narration"], _scr)
                if _new:
                    b["narration"] = _new
                    b["caption_lines"] = None
            b["target_seconds"] = round(max(1.5, len(b["narration"].strip()) / _SYLLABLES_PER_SEC), 1)
        plan_beats = _fill_beat_screen_time(plan_beats, seg_map)
        # ★최종 안전망(2026-08-04): 위 CTA 보장 3중(프롬프트·LLM교정·컷생존)에도 뒤
        # 단계(_fix_beat_structure 등)가 마지막 비트를 갈아치우는 경로가 실측 1/6 남았다.
        # plan 확정 직후라 어떤 경로로 와도 여기서 잡힌다.
        if plan_beats and "댓글" not in (plan_beats[-1].get("narration") or ""):
            _kw = "나도" if "나도" in _mat else "정보"
            plan_beats[-1]["narration"] = f"댓글에 '{_kw}' 남겨주시면 방법 바로 보내드릴게요."
            plan_beats[-1]["caption_lines"] = None
        plan = {"structure": "free", "beats": plan_beats, "detected_type": detected,
                "single_source": True, "hook_pattern": pat[0],
                "affiliate_target": "", "plagiarism_flags": _plagiarism_flags(plan_beats, src_texts)}
        rule_score = _score_candidate(plan, target_seconds=budget, source_full_texts=src_texts)
        cand = {"plan": plan, "story": {"hook": plan_beats[0]["narration"]},
                "score": rule_score, "recommended": False}
        if judge:
            from shopping_shorts import candidate_judge
            jr = candidate_judge.judge(plan_beats, call=call)
            if jr:
                cand["judge"] = jr
                cand["score"] = round(0.5 * rule_score + 0.5 * jr["total"], 3)
        scr = sum(float(b.get("target_seconds") or 0) for b in plan_beats)
        print("[1소스대본] 후보%d 훅패턴=%s %d비트 나레이션 %.1f초 / 화면예산 %.1f초"
              % (i + 1, pat[0], len(plan_beats), scr, used), file=sys.stderr)
        cands.append(cand)
    if not cands:
        return None
    # ★추천에 스타일 이탈 감점(2026-08-05): 리라이트 실패로 옛 카피체로 남은 후보가
    #   ★추천으로 뽑히던 실사고(job 31b394c4). 표시 score는 안 건드리고 선택에만 반영.
    from shopping_shorts import style_profiles as _sp

    def _pick_key(k):
        narrs = [(b.get("narration") or "")
                 for b in (cands[k]["plan"].get("beats") or [])]
        return cands[k]["score"] - _sp.style_penalty(narrs)

    best = max(range(len(cands)), key=_pick_key)
    cands[best]["recommended"] = True
    return {"candidates": cands, "detected_type": detected}


def build_scene_first_plan(source_scripts, reference_text, target_seconds,
                           n_candidates=3, video_type=None, call=None, ping_pong=False,
                           backbone_meta=None, backbone_forced=None, bank_context="",
                           avoid_hooks=None, backbone_base=False, judge=False,
                           is_recipe=False, engine=None):
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
    detected = _normalize_video_type(
        video_type or (detect_video_type(source_scripts) if source_scripts else _DEFAULT_TYPE))
    if not seg_map:
        return {"candidates": [], "detected_type": detected}
    _call = call or _vault_call
    # ★1소스 전용 경로(2026-08-04): 훅 10패턴·길이(하한 20초·원본 90%)를 single_source가
    #   처음부터 끝까지 운전한다. 실패하면 None → 아래 기존 경로 그대로(회귀0).
    from shopping_shorts import single_source as _ss
    if _ss.is_single_source(source_scripts):
        _ss_result = _single_source_candidates(
            source_scripts, seg_map, target_seconds, n_candidates, _call, detected, judge=judge)
        if _ss_result and _ss_result.get("candidates"):
            return _ss_result
        print("[1소스대본] 전용 생성 실패 — 기존 경로 폴백", file=sys.stderr)
    # 화면 순서 뼈대(order_block)를 두 모드로 정한다:
    #  ★기본 경로(backbone_base off = 라이브 기본): 장면 스파인 먼저(2026-07-29 사장님).
    #    카테고리 감지 → 그 카테고리 스파인 슬롯 순서로 태깅된 장면을 먼저 배치(장면 순서 확정)
    #    → 대본 생성에 하드 제약으로 넣어 narration-first를 뒤집는다('장면이 운전대').
    #  백본 모드(backbone_base on, opt-in): 특정 백본 영상의 시간순을 순서 뼈대로 쓴다(기존 동작 보존).
    # 설계: docs/superpowers/specs/2026-07-29-장면스파인-먼저-재설계-design.md
    bb_video, order_block, blocks, tl_groups = None, "", [], []
    # ★리라이트 믹스는 **백본 여부와 무관하게** 먼저 시도한다(2026-07-31 실측 job 52f64c62b3ef).
    #   처음엔 backbone_base가 꺼진 분기에만 넣었는데, 라이브 설정이 backbone_base_enabled=1이라
    #   리라이트 믹스가 **아예 안 돌았다**(오프라인 검증을 백본 꺼진 상태로만 해서 못 봤다).
    #   원본 타임라인을 뼈대로 쓰는 것이 백본(한 영상의 시간순을 뼈대로)의 상위 개념이므로
    #   리라이트가 되면 그걸 쓰고, 재료가 모자라 못 만들 때만 백본/덩어리로 내려간다.
    # slot_source: _pick_slot_groups가 Gemini 판단을 썼는지 폴백했는지(2026-08-01, 폴백
    # 가시화) — REWRITE_MIX가 꺼져 슬롯 경로 자체를 안 탔으면 None(아래에서 plan에 안 붙는다).
    slot_source = None
    slot_info = None
    slot_variants, slot_kinds = [], []
    if REWRITE_MIX:
        # v4(2026-08-02): 슬롯을 후보 수만큼 뽑는다 — 1벌째는 v3와 같은 경로(무변경),
        # 2벌째부터는 **버려지던 세트**로 코드가 조합한다(Gemini 재호출 없음).
        slot_variants, slot_source, slot_info, slot_kinds = _pick_slot_variants(
            seg_map, target_seconds, n=n_candidates, call=_call)
        tl_groups = slot_variants[0] if slot_variants else []
    if tl_groups:
        order_block = _rewrite_block(tl_groups)
        if backbone_base:
            from shopping_shorts import backbone
            bb_video = backbone.pick_backbone(source_scripts, meta=backbone_meta,
                                              forced=backbone_forced)   # 핑퐁이 참조한다
    elif backbone_base:
        from shopping_shorts import backbone
        bb_video = backbone.pick_backbone(source_scripts, meta=backbone_meta,
                                          forced=backbone_forced)
        if bb_video:
            order_block = _backbone_order_block(bb_video, source_scripts)
    else:
        # ★덩어리 믹스(2026-07-31 사장님): 훅/스토리/CTA 세 덩어리를 연속 구간으로 먼저 확정.
        #   화면이 먼저 정해지므로 덩어리 초 → 글자수 예산을 대본에 줄 수 있고,
        #   배정도 코드가 강제한다(_assign_blocks) — 옛 스파인은 "고정이다"라고 말만 하고
        #   지켰는지 검사하지 않아 매번 다르게 나왔다. BLOCK_MIX=0으로 즉시 롤백.
        blocks = _build_scene_blocks(seg_map, target_seconds) if BLOCK_MIX else []
        order_block = (_blocks_order_block(blocks) if blocks
                       else _spine_order_block(_build_scene_spine(seg_map, detected)))
    src_texts = [s.get("full_text", "") for s in source_scripts]

    outer_tl_groups = tl_groups

    def _ground_score(raws, groups=None):
      # groups: 이 묶음이 쓸 슬롯(v4, 2026-08-02). None이면 종전과 똑같이 바깥의
      # tl_groups를 쓴다 — REWRITE_MIX가 꺼진 경로(tl_groups=[])도 그대로 보존된다.
      tl_groups = outer_tl_groups if groups is None else groups
      if bb_video:
        for r in raws:
            r.setdefault("_backbone_video", bb_video)   # 핑퐁 순서고정이 이 백본을 쓴다
      cands = []
      for r in raws:
        plan = _ground_candidate(r, seg_map, lead_hook=not tl_groups)
        if plan is None:
            continue
        # ★자리표시자 방벽(2026-08-01 실사고, job e99d0e8e3e02): 모델이 요구한 비트 수를
        #   넘겨 만들며 남는 자리를 `filler`라는 **글자 그대로** 채웠고, 그게 대본으로
        #   나가 사장님 화면까지 갔다. 프롬프트로 "하지 마라"만 적으면 지켜졌는지 알 수
        #   없다는 게 이 파일의 반복된 교훈이라, 코드로 막는다(화면은 아래
        #   _assign_timeline이 어차피 다시 배정하므로 비트를 빼도 화면은 안 잃는다).
        plan["beats"] = _dedupe_cta_beats(_drop_placeholder_beats(plan.get("beats") or []))
        if tl_groups:
            # 모델이 요구한 개수를 안 지키므로 코드가 맞춘다(위 함수 주석 참조).
            plan["beats"] = _trim_beats_to_slots(plan["beats"], len(tl_groups))
        if not plan["beats"]:
            continue
        # ★화면은 원본 시간순 그대로 코드가 배정한다(리라이트 믹스).
        if tl_groups:
            plan["beats"] = _assign_timeline(plan["beats"], tl_groups)
        elif blocks:
            plan["beats"] = _assign_blocks(plan["beats"], blocks)
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
        # ★압축 뒤에 구조 교정을 한 번 더(2026-07-30). conform_narration이 길이를 줄이면서
        #   존댓말을 반말로 압축한다 — 실측: CTA "…남겨주세요"가 "…남겨줘"로 바뀌어 나갔다
        #   (_ground_candidate에서 이미 교정했는데 그 뒤 conform이 되돌린 것). 멱등이라
        #   두 번 불러도 무해하고, 압축으로 짧아진 비트는 분할 대상에서 자연히 빠진다.
        plan["beats"] = _fix_beat_structure(plan["beats"])
        if ping_pong:
            from shopping_shorts import backbone
            # 1) 행위 매칭(화면-대사 어긋남 + 길이) 2) 백본 순서 고정(과정순서)
            plan["beats"] = backbone.ping_pong_reconcile(
                plan["beats"], source_scripts,
                rewrite_call=lambda bs: _bb_rewrite(bs, _call),
                trim_call=lambda bs: _bb_trim(bs, _call),
                # 트림이 대본을 목표의 75% 밑으로 깎으면 아예 적용하지 않는다(2026-07-31).
                # 넘치는 화면은 렌더의 _refill_beats_to_tts가 클립을 더 붙여 흡수한다.
                min_total_chars=int((target_seconds or 0) * _SYLLABLES_PER_SEC * 0.75))
            # ★슬롯 경로(tl_groups)에선 아래 백본 화면 후처리 5종을 **건너뛴다**
            #   (G2, 2026-08-01). 이들은 primary/alternates만 만지는데, 이 블록 뒤의
            #   `_assign_timeline`(2회차)이 그 둘을 통째로 재설정하므로 **결과가 예외 없이
            #   소멸한다** — 일을 하고 그 일을 버리는 구조였다.
            #
            #   실측(scratchpad/g2_probe.py, 반사실 대조): 소재 5종 × 후보 16개 전부
            #   "스킵했을 때의 최종 화면 == 실제 최종 화면" 0건 차이. 검사가 실제로 무는지도
            #   고의 차이 주입으로 확인했다(9건 검출).
            #   ⚠️단순히 "5종 실행 전/후"를 비교하면 안 된다 — _assign_timeline이 우연히
            #     같은 세그를 고른 경우를 '살아남았다'로 오판한다(초안이 실제로 그랬다).
            #     반드시 **스킵한 비트에 같은 _assign_timeline을 걸어** 대조해야 한다.
            #
            #   이 5종이 슬롯을 깨뜨리며 만든 두더지가 여럿이었다(ping_pong 클립 중복 배정,
            #   CTA가 끝에서 밀려남 → _fix_beat_structure를 3번 부르게 된 원인).
            #   ping_pong_reconcile(위)은 **나레이션도 재작성**하므로 여기서 건드리지 않는다.
            #   tl_groups가 없는 경로(REWRITE_MIX=0)에선 종전대로 전부 돈다.
            if not tl_groups:
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
                # 영상 차별화(2026-07-27, 최종 단계): 훅(첫 비트)=비-A 소스 최고장면 / CTA(끝)=중간
                # 소스 클립(원본 엔딩 회피). 화면만 재배정(narration 불변) → 다른 후처리 뒤에 마지막으로.
                plan["beats"] = backbone.swap_hook_cta_for_differentiation(
                    plan["beats"], bb, source_scripts)
        # ★핑퐁 후처리 뒤 구조 재교정(2026-07-31). 원래는 위 backbone 5종이 비트 순서를
        #   다시 짜면서 **CTA가 마지막이 아니게 되는** 것을 되돌리려고 넣었다(라이브 설정
        #   백테스트 20건 중 9건이 CTA끝X). 슬롯 경로에선 그 5종을 이제 안 타므로 그 사유는
        #   사라졌지만, **ping_pong_reconcile은 여전히 비트를 재작성**하므로 교정은 남긴다.
        #   멱등이라 이미 정상인 계획엔 아무 일도 하지 않는다.
        plan["beats"] = _fix_beat_structure(plan["beats"])
        # ★리라이트 믹스는 화면을 **맨 마지막에 다시 못박는다**(2026-07-31 실측 job e288f2f0c387).
        #   ⚠️2026-08-01(G2)로 의미가 바뀌었다: 예전엔 뒤따르는 backbone 5종이 화면을 뒤섞어
        #   그것을 되돌리는 게 주목적이었으나, 이제 그 5종을 슬롯 경로에서 건너뛰므로
        #   여기서 되돌릴 것이 없다. 남은 역할은 **ping_pong_reconcile이 바꾼 화면**을
        #   원본 슬롯 순서로 되돌리는 것 하나다(그 함수는 나레이션과 화면을 함께 만진다).
        if tl_groups:
            plan["beats"] = _assign_timeline(plan["beats"], tl_groups)
        plan["detected_type"] = detected
        plan["affiliate_target"] = r.get("story_event", "") or ""
        plan["plagiarism_flags"] = _plagiarism_flags(plan["beats"], src_texts)
        # 슬롯 폴백 가시화(2026-08-01): tl_groups가 있을 때만(=슬롯 경로를 실제로 탔을 때만)
        # 의미가 있다 — REWRITE_MIX가 꺼진 경로는 tl_groups가 애초에 []라 slot_source도 None.
        if tl_groups:
            plan["slot_source"] = slot_source
            if slot_info:
                plan["slot_info"] = slot_info      # G3 관측: 무엇이 잘리고 어느 소스가 빠졌나
        story = {k: r.get(k, "") for k in
                 ("hook", "story_person", "story_event", "story_resolution", "cta_line", "cta_keyword")}
        rule_score = _score_candidate(plan, avoid_hooks=avoid_hooks, target_seconds=target_seconds,
                                       source_full_texts=src_texts)
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
    # ★v4(2026-08-02): 슬롯이 여러 벌이면 **벌마다 따로** 대본을 뽑는다.
    #   벌마다 세트 목록이 다르므로 order_block("i번째 비트가 위 i번 세트다")도 달라진다 —
    #   한 번에 뽑으면 어느 후보가 어느 벌을 따라야 하는지 프롬프트가 말할 수 없다.
    #   대본 생성 호출이 벌 수만큼 늘어난다(과금) — 사장님이 "그냥 확실하게"로 택한 방식.
    #   벌이 1개뿐이면(여유 없음·폴백) 종전과 완전히 같은 1회 호출로 돈다.
    _distinct = []
    for i, g in enumerate(slot_variants or []):
        ids = tuple(x[0]["seg_id"] for x in g if x)
        if ids not in [d[0] for d in _distinct]:
            _distinct.append((ids, i, g))
    if len(_distinct) > 1:
        raws, cands = [], []
        # ★앞 후보가 쓴 대사를 다음 호출에 넘긴다(2026-08-03). 벌마다 따로 부르므로
        #   서로 뭘 썼는지 모르고, 각자 원본을 보면 같은 표현을 고른다(실측: 세 후보가
        #   전부 "미국 목조주택 보수용 점토"). 프롬프트로 "다르게 써라"만으론 안 됐다.
        said_before = []
        for k, (_ids, vi, g) in enumerate(_distinct):
            sub = _scene_first_candidates(
                inventory, reference_text, target_seconds, n=1, call=_call,
                bank_context=bank_context,
                order_block=_rewrite_block(g, avoid_narrations=said_before),
                benefits_block=benefits_block, engine=engine,
                engine_seed=_engine_seed(reference_text) + k)
            raws.extend(sub or [])
            got = _ground_score(sub or [], groups=g)
            for c in got:
                c["plan"]["slot_variant"] = slot_kinds[vi] if vi < len(slot_kinds) else "?"
                said_before.append(" ".join((b.get("narration") or "")
                                            for b in (c["plan"].get("beats") or [])))
            cands.extend(got)
        # ★벌마다 따로 부르면 **한 벌만 실패해도 후보가 빈다**(실측: 3벌인데 후보 2개).
        #   한 번에 뽑던 옛 경로엔 없던 위험이라, 부족분을 1벌째 슬롯으로 메운다.
        #   (모자란 채 내보내면 사장님 화면에 후보가 2개만 뜬다 — 그게 더 나쁘다.)
        if len(cands) < len(_distinct):
            need = len(_distinct) - len(cands)
            fill = _scene_first_candidates(
                inventory, reference_text, target_seconds, n=need, call=_call,
                bank_context=bank_context, order_block=order_block,
                benefits_block=benefits_block, engine=engine,
                engine_seed=_engine_seed(reference_text) + 100)
            got = _ground_score(fill or [], groups=tl_groups)
            for c in got:
                c["plan"]["slot_variant"] = "refill"   # 차별화 실패를 숨기지 않는다
            raws.extend(fill or [])
            cands.extend(got[:need])
    else:
        raws = _scene_first_candidates(inventory, reference_text, target_seconds, n=n_candidates,
                                       call=_call, bank_context=bank_context,
                                       order_block=order_block,
                                       benefits_block=benefits_block, engine=engine,
                                       engine_seed=_engine_seed(reference_text))
        cands = _ground_score(raws)
    # ①생성측 보강(세션#2): 후보가 전부 목표보다 크게 짧으면(생성이 목표초 미달) 길이 강화
    # 힌트로 1회 재생성해 합친다. ②선택 감점(_length_penalty)이 짧은 후보를 강등하므로 병합 후
    # 채점하면 긴 후보가 자연히 추천된다. 재생성은 '전부 짧을 때만' — 소스 footage 부족이 아니라
    # 생성 자체가 목표초에 못 미친 경우로 한정(과금 게이트, 1회 상한, 실패해도 기존 후보 유지).
    # ★리라이트 믹스는 목표초가 아니라 **세트 총 길이**가 상한이다(2026-07-31).
    #   재료가 22초치뿐인데 목표가 30초면 아무리 다시 뽑아도 못 채운다 — 그대로 두면 매번
    #   Gemini를 한 번 더 부르고(과금) 후보가 6개로 불어난다(사장님 "대본이 6개?").
    len_goal = target_seconds
    if tl_groups:
        len_goal = min(target_seconds, sum(_secs(g) for g in tl_groups))
    if cands and len_goal and len_goal > 0:
        def _cand_secs(c):
            return sum(float(b.get("target_seconds") or 0.0)
                       for b in c["plan"].get("beats", []))
        if max((_cand_secs(c) for c in cands), default=0.0) < 0.92 * len_goal:
            # ★재생성도 벌별로(v4). 옛 코드는 order_block(1벌째) 하나로 n개를 다시 뽑아
            #   **재생성분이 전부 벌A의 화면을 쓰게** 만들었다 — 차별화가 여기서 무너진다.
            #   벌이 1개면 종전과 동일하게 한 번만 돈다.
            for k, (_ids, vi, g) in enumerate(_distinct or [((), 0, tl_groups)]):
                raws2 = _scene_first_candidates(
                    inventory, reference_text, target_seconds,
                    n=(1 if len(_distinct) > 1 else n_candidates), call=_call,
                    bank_context=bank_context,
                    order_block=(_rewrite_block(g) if len(_distinct) > 1 else order_block),
                    lengthen=True, benefits_block=benefits_block, engine=engine,
                    engine_seed=_engine_seed(reference_text) + 1 + k)
                got = _ground_score(raws2, groups=(g if len(_distinct) > 1 else None))
                for c in got:
                    c["plan"]["slot_variant"] = (slot_kinds[vi] if vi < len(slot_kinds)
                                                 else "?")
                cands = cands + got
    # ★말투 게이트(2026-07-30 사장님 승인). 후보가 **전부** 밋밋하면 1회만 다시 뽑아 합친다.
    # 위 길이 재생성과 같은 규율: 전부 미달일 때만(과금 게이트) · 1회 상한 · 실패해도 기존 유지.
    # 없으면 감점이 순위표 노릇만 해서 3개가 다 밋밋할 때 그중 최선이 그대로 나간다
    # (실측 07-30: tone 0.67짜리가 추천으로 나갔다). 합친 뒤 아래 best 선택이 알아서 고른다.
    if cands and max(_cand_tone(c) for c in cands) < _TONE_GATE:
        # 길이 재생성과 같은 이유로 벌별로 돈다(v4) — 안 그러면 말투 재생성분이 전부
        # 벌A의 화면을 쓴다.
        for k, (_ids, vi, g) in enumerate(_distinct or [((), 0, tl_groups)]):
            raws3 = _scene_first_candidates(
                inventory, reference_text, target_seconds,
                n=(1 if len(_distinct) > 1 else n_candidates), call=_call,
                bank_context=bank_context,
                order_block=(_rewrite_block(g) if len(_distinct) > 1 else order_block),
                tone_boost=True, benefits_block=benefits_block, engine=engine,
                engine_seed=_engine_seed(reference_text) + 2 + k)
            got = _ground_score(raws3, groups=(g if len(_distinct) > 1 else None))
            for c in got:
                c["plan"]["slot_variant"] = slot_kinds[vi] if vi < len(slot_kinds) else "?"
            cands = cands + got
    if cands:
        # ★말투 하한(2026-07-30). 최종 score는 0.75×매칭 + 0.25×품질이고 품질 안에서 말투가
        #   0.6이라, 말투가 최종 점수의 **15%**뿐이다 → tone 0.4짜리와 1.0짜리의 점수 차이가
        #   0.09에 불과해 매칭 점수 차이에 쉽게 뒤집힌다. 실측(95건 중 27건 약함)에서 평서과다
        #   19건·생생어미0 13건이 그대로 추천으로 나갔다.
        #   → 매칭 가중치는 건드리지 않고, **기준을 넘는 후보가 하나라도 있으면 그 안에서만**
        #     고른다. 전부 미달이면 종전대로(폴백) — 재료가 빈약한 소재에서 후보를 잃지 않는다.
        # ★감각어 하한도 함께(2026-07-31). 프롬프트는 "감각어 4개 이상"을 요구하는데 실측
        #   평균은 1.9개였다 — 지시만으로는 안 지켜진다. 은행에 감각어를 6개→14개로 늘리고
        #   소재마다 다른 조각을 보여줘도 사용량은 그대로였다(v7 2.2 → v8 1.9, 노이즈 범위).
        #   반면 말투는 '하한'을 세우자 불량이 10건→0건이 됐다(2026-07-30). 같은 방법을 쓴다.
        #   ★단계적으로 완화한다: 둘 다 넘는 후보 → 말투만 넘는 후보 → 전부(폴백).
        #   재료가 빈약한 소재에서 후보를 잃지 않으면서, 여유가 있을 때만 감각어를 요구한다.
        toned = [i for i, c in enumerate(cands) if _cand_tone(c) >= _TONE_GATE]
        rich = [i for i in toned if _cand_sensory(cands[i]) >= _SENSORY_FLOOR]
        qualified = rich or toned
        pool = qualified or range(len(cands))
        best = max(pool, key=lambda i: cands[i]["score"])
        cands[best]["recommended"] = True
        # ★내보내는 후보는 n_candidates개까지만(2026-08-01 사장님 "대본이 왜 4개야?").
        #   위 재생성(길이·말투)은 **고르기 위해** 후보를 더 뽑는 장치다 — 합쳐놓고 그중
        #   최선을 고르는 게 목적이지, 사람에게 6개를 늘어놓는 게 목적이 아니었다.
        #   그래서 선택 로직(합치기·하한·best)은 그대로 두고, **화면에 나가는 개수만** 자른다.
        #   추천 후보는 점수와 무관하게 반드시 남긴다(잘려나가면 추천이 사라진다).
        keep = sorted(range(len(cands)), key=lambda i: (i != best, -cands[i]["score"]))
        keep = sorted(keep[:max(1, n_candidates)])      # 원래 순서(A/B/C)를 유지해 보여준다
        cands = [cands[i] for i in keep]
    # ★CTA 유입 경로 교정(2026-08-03 사장님: "CTA는 고정으로 댓글에 OO 남겨주세요로").
    #   은행에서 '프로필 👉 @아이디' 계열을 뺐고 프롬프트에도 형식을 박았지만 간헐적으로
    #   샌다(실측 job 23208dec38e6: "비결 궁금하시면 프로필 링크 확인해주세요").
    #   ★반드시 **여기서**(최종 후보 확정 뒤) 해야 한다 — 생성 단계에서 대사를 갈아끼우면
    #     후보 길이가 바뀌어 **길이 재생성 판단('전부 짧은가')을 오염시킨다**
    #     (실측: test_scene_first_lengthen 2건이 그렇게 깨졌다). 여기선 이미 선택이 끝나
    #     길이가 판단에 안 쓰이므로 안전하다.
    for _c in cands:
        _cta_fix_narration(_c)
        _strip_mid_cta(_c)      # 비CTA 비트에 샌 댓글 유도 제거(2026-08-03 "CTA 두 번 반복")
    return {"candidates": cands, "detected_type": detected}
