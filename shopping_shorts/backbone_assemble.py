# -*- coding: utf-8 -*-
"""백본-먼저 조립기 (2026-09-16, 사장님 구조 그대로)

    [훅] + [특징1..N] + [CTA]
    각색 = ①훅 갈아끼우기 ②특징 순서 섞기 ③특징별 말 바꿔쓰기 ④화면은 서브 우선

왜 이 모양인가 — 두 달간 14번 "문장마다 맞는 장면 찾기"를 더 잘하려다 전부 두더지였다.
사장님(07-19): "우리 오류 = 문장마다 맞는 장면을 찾으려 한 것 자체." 특징마다 원본에 (말, 화면)
짝이 **이미** 있으니, 화면을 먼저 못 박고 그 화면에 맞는 말을 쓰면 빈칸이 생길 자리가 없다.
손 실증 job bb1cc3402937: 지정 11컷 → 최종 13컷 · 같은 그림 0 · 빈칸 0 (옛 경로 job은 10→26컷).

모델 호출은 딱 2회 — A(특징 묶기+순서) · B(문장). B는 "대본을 써라"가 아니라
"**이 화면**에 맞는 **이 특징**을 한 문장으로"다. 화면이 먼저 정해져 있어 모델이 뭐라 쓰든 화면은 맞는다.

출력은 기존 상속 경로가 그대로 받는 (given_script, beat_sources) — 새 렌더 경로를 만들지 않는다(0순위-B).
"""
import json
import random
import re
import sys
import time

from shopping_shorts import script_generate as _sg

# ── 규칙(한 곳에서만 정한다) ─────────────────────────────────────────
MAX_GROUPS = 4          # 훅·CTA 제외 특징 수 **상한** (2026-09-21 사장님 "특징은 4개까지 가야 되고")
MIN_GROUPS = 3          # 하한 — 썰채널 실측이 고조 3~4개다. 5~7개로 잘게 쪼개면 줄당 2.5초로 밋밋해진다
MIN_CUT_SECS = 0.8      # 이보다 짧은 컷은 렌더가 흡수해 화면에 안 나온다(칸채우기 핸드오프 함정 2)
SLACK_SECS = 0.3        # 컷 길이 합이 대사보다 이만큼은 더 길게 — 채우기가 안 돌게

# ★한 줄에 컷을 최소 몇 개 붙일까(2026-09-17 사장님 "근데 밋밋한거지").
#   실측: 자동조립 job ba630a537511은 7줄 전부 **컷 1개**였고 컷당 6.5초였다(대사 3.5초인데
#   첫 컷이 6.3초라 `_fill`이 한 개에서 멈춘다). 떡상 채널은 컷당 0.73~1.37초다
#   (이븐쇼핑 0.78/1.02/1.22 · 순찌홈 0.73 · 긍정템 1.07 · 치트키요정 1.13 — 12편 실측,
#    `channel/strategy/효과음_패턴분석.md`). 4.7배 느리니 화면이 안 바뀌어 밋밋하다.
#   ★떡상 채널도 그림 재고는 적다(이븐쇼핑 화면 70%가 같은 손 샷) — **있는 그림을 잘게 쪼개** 쓴다.
#   렌더(video_assemble)에 이미 2.2초 상한 라운드로빈이 있는데 **`len(segments) > 1`일 때만** 돈다
#   (`_plan_beat_clips:940`). 컷이 1개면 else 경로로 빠져 통째 재생된다 — 그래서 상한이 안 먹었다.
#   즉 고칠 자리는 렌더가 아니라 **컷을 여러 개 주는 것**이다(0순위-B: 정하는 곳은 여기 한 곳).
TARGET_CUT_SECS = 2.0   # 한 컷이 이보다 길면 줄을 더 쪼갤 여지가 있다고 본다(렌더 상한 2.2와 짝)
MIN_CUTS_PER_LINE = 2   # 줄마다 최소 이만큼 — 그래야 렌더 라운드로빈(>1)이 작동한다
# 한 줄 평균 몇 초로 잡을까 — 목표 초 ÷ 이 값 = 최대 줄 수. 실측(2026-09-18 카메라): 11줄 34.8초 = 3.2초/줄,
#   10줄 30.6초 = 3.1초/줄. 25초에 8줄이 맞다 → 3.1.
SECS_PER_LINE = 3.1
MISUSE_STYLE = "오용형"             # 재료에 딴 용도가 없으면 이 유형 스파인은 안 쓴다(사장님 09-18)
MISUSE_FALLBACK_STYLE = "제품정체형"


def _secs(text):
    """대사 읽는 시간 — 정본은 edit_plan.narr_secs 하나(말속도 상수 여러 벌 금지)."""
    from shopping_shorts.edit_plan import narr_secs
    return narr_secs(text)


def _vid_of(seg_id):
    return str(seg_id).rsplit("-", 1)[0]


def _seg_index(sources):
    """seg_id -> {secs, desc, vid, ...}. 모든 소스의 컷을 한 표로."""
    idx = {}
    for s in sources:
        for x in (s.get("segments") or []):
            sid = x.get("seg_id")
            if not sid:
                continue
            try:
                secs = round(float(x.get("end") or 0) - float(x.get("start") or 0), 2)
            except (TypeError, ValueError):
                secs = 0.0
            idx[str(sid)] = {"secs": secs, "desc": (x.get("scene_desc") or "").strip(),
                             "change": (x.get("change") or "").strip(), "role": x.get("shot_role") or "",
                             # ★vid는 **소스 번호(video_id, 예 s0)**로 — 백본을 그 번호로 부른다.
                             #   컷 번호 접두어(예 DdOayfhAnpx)로 두면 백본과 절대 안 맞아 '서브 먼저·원본 나중'이
                             #   통째로 무력이었다(2026-09-18 실측: 씨앗 s0 백본인데 원본 컷 10/29).
                             "key": bool(x.get("is_key")), "vid": s.get("video_id") or _vid_of(sid),
                             "text": (x.get("text") or "").strip()}
    return idx


# ── A. 특징 묶기 + 순서 (모델 1회) ────────────────────────────────────
_GROUP_SCHEMA = {
    "type": "object",
    "properties": {
        "product": {"type": "string"},
        "groups": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"},
            "claim": {"type": "string"},
            "where": {"type": "string", "enum": ["원본", "서브", "둘다"]},
            "doubt": {"type": "boolean"},
            "cuts": {"type": "array", "items": {"type": "string"}},
        }, "required": ["name", "claim", "where", "doubt", "cuts"]}},
        "order": {"type": "array", "items": {"type": "integer"}},
        "alt_use": {"type": "boolean"},
    },
    "required": ["product", "groups", "order", "alt_use"],
}


def _source_block(s, is_backbone):
    lines = [f"[{'원본(백본)' if is_backbone else '서브'} {s.get('video_id')}]"]
    if s.get("product_benefits"):
        lines.append("  특징: " + " / ".join(str(b) for b in s["product_benefits"][:12]))
    for x in (s.get("segments") or []):
        try:
            secs = float(x.get("end") or 0) - float(x.get("start") or 0)
        except (TypeError, ValueError):
            secs = 0
        say = (x.get("text") or "").strip()[:40]
        # ★장면마다 **그 장면이 보여주는 특징·효과**를 함께 싣는다 (2026-09-21 사장님:
        #   "장면의 특징효과등을 태깅잘해서 넣자는거야 장면에 딱맞게 말은 바꿔서").
        #   종전엔 영상 단위 특징 12개만 위에 한 번 주고 장면엔 화면·말·변화만 줬다 —
        #   모델이 "이 장면이 무슨 장점을 보여주는가"를 장면 단위로 볼 수 없었다.
        #   대본 말(text)은 **특징을 알아내는 단서**일 뿐이고 결과 문장이 아니다(말은 새로 쓴다).
        ben = " / ".join(str(b) for b in (x.get("product_benefits") or [])[:2])
        lines.append(f"  [{x.get('seg_id')}] ({secs:.1f}s) 화면:{(x.get('scene_desc') or '')[:70]}"
                     + (f" | 말:{say}" if say else "")
                     + (f" | 변화:{(x.get('change') or '')[:40]}" if x.get("change") else "")
                     + (f" | 특징:{ben[:80]}" if ben else "")
                     + (f" | 용처:{(x.get('use_point') or '')[:60]}" if x.get("use_point") else ""))
    return "\n".join(lines)


def build_groups(sources, backbone_vid, note=None):
    """특징을 같은 얘기끼리 묶고 컷을 붙인다. 원본 흐름 순서 + 서브 새 특징 삽입 위치까지."""
    blocks = "\n\n".join(_source_block(s, s.get("video_id") == backbone_vid) for s in sources)
    prompt = (
        "아래는 같은 제품을 찍은 영상 여러 편의 태깅이다. 원본(백본) 1편과 서브 여러 편.\n"
        "할 일:\n"
        "1) 모든 영상의 '특징'과 컷 화면을 보고, **같은 얘기끼리 한 묶음**으로 묶어라(예: '54개 부품'·'정밀 설계'·'정교한 결합'은 한 묶음). "
        f"묶음은 **{MIN_GROUPS}~{MAX_GROUPS}개** — 이 영상에서 **제일 센 장점만** 남겨라(2026-09-21 사장님). "
        "잘게 쪼개지 마라: 비슷한 얘기는 한 묶음으로 합치고, 약한 것은 버려라. "
        "고르는 기준은 **그 장면이 보여주는 특징·효과가 얼마나 센가**다 — 태깅의 '특징'·'용처'·'변화'를 보고 판단하라. "
        "각 묶음에 이름·한 줄 주장(claim)·그 특징이 **화면에 실제로 보이는 컷 번호들**을 붙여라. "
        "★서브 영상에 같은 동작 컷이 있으면 **반드시 서브 컷도 함께** 넣어라(원본 컷만 넣지 마라).\n"
        "2) where: 그 특징이 원본에 있으면 '원본', 서브에만 있으면 '서브', 둘 다면 '둘다'.\n"
        "3) doubt: 서브가 **다른 제품**으로 보이거나(예: 원본은 볼펜인데 버튼 피젯), 원본에 없는 기능을 말하면 true. "
        "화면은 같은 동작이라도 말이 다르면 true.\n"
        "4) order: 묶음 인덱스(0부터)를 **영상에 나올 순서**로. 원본의 논리 순서(소개→변신→증명→원리)를 지키되, "
        "서브에만 있는 특징(휴대·개봉·보관 등)은 자연스러운 자리에 끼워라. doubt=true 묶음은 order에서 빼라.\n"
        "5) product: 제품 이름 한 줄 — **한국어로**(영문 제품명은 뜻을 옮기고 브랜드만 영문. 예: 'NORDECO 빈티지 미니 카메라').\n"
        "6) alt_use: 제품을 **원래 용도가 아닌 엉뚱한 곳에 쓰는 장면**(예: 커튼 고리를 벽 수납에, 몰딩을 선반으로)이 "
        "화면이나 말에 실제로 있으면 true. 원래 용도대로 쓰는 장면뿐이면 false.\n"
        "★컷 번호는 목록에 있는 것만. 지어내지 마라.\n\n" + blocks)
    out = _sg._call_json(prompt, _GROUP_SCHEMA, note=note) or {}
    groups = [g for g in (out.get("groups") or []) if isinstance(g, dict)]
    order = [i for i in (out.get("order") or []) if isinstance(i, int) and 0 <= i < len(groups)]
    if not order:
        order = [i for i, g in enumerate(groups) if not g.get("doubt")]
    return {"product": out.get("product") or "", "groups": groups, "order": order[:MAX_GROUPS],
            "alt_use": bool(out.get("alt_use"))}


# ── 훅 고르기 ─────────────────────────────────────────────────────────
def _seed_int(seed):
    if isinstance(seed, int):
        return seed
    if seed:
        import zlib
        return zlib.crc32(str(seed).encode("utf-8"))
    return 0


def _RECIPE_ONLY_MARK(fit):
    """fit_categories가 [유형, '레시피'] 꼴(=레시피 말고 붙은 물건 카테고리가 없음)이면 '레시피'를 돌려 표식으로 쓴다."""
    others = [c for c in fit if c not in ("레시피",) and not c.endswith("형")]
    return "레시피" if ("레시피" in fit and not others) else ""


def pick_hook_spine(store, spine_id=None, seed=None, style=None):
    """승인 스파인 중 훅 규칙(hook_3s)이 있는 것.
    ★style(유형, 예 '오용형'·'발명품형')을 주면 **그 유형의 스파인들을 id 순으로 세워 seed로 순번**을 정한다
      (2026-09-18 사장님: "오용형을 고르면 그 유형 채널들의 잘 쓴 대본 스파인 5~10개가 순번대로 나오는 구조").
      전엔 spine_id 지정 아니면 무작위였고, 유형으로 고르는 길이 없었다.
    spine_id가 오면 그게 우선. 둘 다 없으면 무작위(seed 고정)."""
    all_sp = list(store.list_spines(status="approved") or [])
    # ★원문형 스파인은 검수 중(pending)이라 승인 목록에 없다 — **id로 콕 집어 부를 때만** 같이 본다
    #   (무작위·유형 선택 후보에는 안 들어간다: 아래 spines/pool은 all_sp가 아니라 승인분만 쓰도록 유지)
    if spine_id is not None:
        _appr = {s.get("id") for s in all_sp}
        all_sp = all_sp + [s for s in (store.list_spines(status="pending") or []) if s.get("id") not in _appr]
    spines = [s for s in all_sp if s.get("hook_3s")]
    if spine_id is not None:
        for s in all_sp:
            if s.get("id") == spine_id:
                return s
    if style:
        # 인스타 스파인(52~62)은 hook_3s가 없다 — 유형으로 고를 땐 전부 후보(2026-09-18)
        # ★레시피 전용 틀(fit에 '레시피'뿐인 것, 예 53 단정명령형 "무조건 이렇게 드세요")은 물건 소재에 주면
        #   "행주를 드세요·별미"가 된다(실측 job bbdd4bb0a0ff). 유형이 '레시피'가 아니면 뺀다.
        def _ok(sp):
            fit = sp.get("fit_categories") or []
            if style not in fit:
                return False
            return style == "레시피" or "레시피" not in _RECIPE_ONLY_MARK(fit)
        pool = sorted([s for s in all_sp if _ok(s)], key=lambda s: s.get("id") or 0)
        if pool:
            return pool[_seed_int(seed) % len(pool)]
    # 유형에 맞는 스파인이 없으면 무작위 폴백(훅 있는 것 우선)
    if not spines:
        spines = all_sp
    rnd = random.Random(seed)
    return rnd.choice(spines) if spines else {}


# ── B. 문장 쓰기 (모델 1회, 구조·컷 고정) ─────────────────────────────
_LINES_SCHEMA = {
    "type": "object",
    "properties": {"lines": {"type": "array", "items": {"type": "object", "properties": {
        "role": {"type": "string"}, "text": {"type": "string"}, "group": {"type": "integer"},
    }, "required": ["role", "text", "group"]}}},
    "required": ["lines"],
}


_ORIGIN_SCHEMA = _LINES_SCHEMA          # 원문형도 줄 모양은 같다(role·text·group)
_DUP = re.compile(r"(\S.{3,}?[.!?]?)\s*\1")


def _dedup(t):
    """전사본의 같은 말 연달아 반복('세탁 남겨주세요. 세탁 남겨주세요.')을 한 번으로."""
    prev = None
    while prev != t:
        prev, t = t, _DUP.sub(r"\1", t)
    return (t or "").strip()


_PREMISE_SCHEMA = {"type": "object", "properties": {
    "uses_already": {"type": "boolean"}, "speaker": {"type": "string"}, "other": {"type": "string"},
    "lives_together": {"type": "boolean"}, "who_admires": {"type": "string"}, "who_buys": {"type": "string"},
    "emotion_from": {"type": "string"}, "emotion_to": {"type": "string"}, "needed_scene": {"type": "string"}},
    "required": ["uses_already", "speaker", "other", "lives_together", "who_admires", "who_buys",
                 "emotion_from", "emotion_to", "needed_scene"]}
_CAST_SCHEMA = {"type": "object", "properties": {
    "fit": {"type": "boolean"}, "why_not": {"type": "string"}, "speaker": {"type": "string"}, "other": {"type": "string"},
    "lives_together": {"type": "boolean"}, "who_uses": {"type": "string"}, "who_buys": {"type": "string"},
    "opening": {"type": "string"}, "turn": {"type": "string"}, "ending": {"type": "string"}},
    "required": ["fit", "speaker", "other", "lives_together", "who_uses", "who_buys", "opening", "turn", "ending"]}
_GAP_SCHEMA = {"type": "object", "properties": {"issues": {"type": "array", "items": {"type": "string"}}},
               "required": ["issues"]}


def _origin_text(origin):
    return "\n".join("[%s] %s" % (c.get("role") or "", _dedup(c.get("text") or ""))
                     for c in (origin.get("cells") or []))


def read_premise(origin, note=None):
    """히트작 원문에 숨은 **이야기 전제**를 뽑는다 — 누가 쓰고 있었나·누가 감탄하나·누가 사나·감정이 어디서 어디로.

    ★왜(2026-09-20 사장님 "덕지덕지 붙는 거 아닌가"): 문장만 옮기면 모델이 제품에 맞추다 전제를 깬다
      (엄마가 지저분하다고 지적했는데 바로 감탄 / 아기 인형을 시어머니에게 사드림). 어색할 때마다 검사를
      덧붙이면 규칙만 늘어난다. 전제를 데이터로 넘기고 검사는 '상황표와 맞나' 하나로 모은다."""
    p = ("아래 쇼핑 숏폼 대본에서 이야기 전제를 뽑아라.\n"
         "uses_already=화자가 그 물건을 이미 쓰고 있었나 / other=상대가 누구인지(역할 이름) / "
         "lives_together=화자와 같이 사나 / who_admires=감탄하는 쪽 / who_buys=사거나 선물하는 쪽 / "
         "emotion_from→emotion_to=감정이 어디서 어디로 / needed_scene=이 이야기가 되려면 화면에 꼭 있어야 하는 장면 하나.\n"
         "★모든 값에서 **제품·업종·물건 이름을 빼라**. '전기 자전거 타는 친구'가 아니라 '그 물건을 쓰고 있는 친구', "
         "'거울 닦는 시어머니'가 아니라 '그 물건을 써 보는 어른'처럼. 어떤 제품에도 얹히는 뼈대여야 한다.\n\n"
         + _origin_text(origin))
    return _sg._call_json(p, _PREMISE_SCHEMA, note=note) or {}


def build_cast(premise, product, feats, note=None):
    """이 제품에 맞춘 상황표. fit=false면 이 스파인은 이 제품에 안 쓴다(억지로 맞추지 않는다)."""
    p = ("[원문 전제]\n%s\n\n[이 제품] %s\n%s\n\n"
         "위 전제를 이 제품 상황으로 옮긴 **상황표**를 만들어라.\n"
         "- who_uses는 이 물건을 실제로 쓰는 사람. 화자가 쓰는 물건이면 화자가 who_uses다.\n"
         "- 같이 사는 사람은 '놀러 오지' 않는다. 사주거나 선물하는 방향은 실제로 쓰는 사람 쪽으로만.\n"
         "- opening/turn/ending = 대본이 어떻게 열고, 어디서 마음이 바뀌고, 어떻게 닫는지 한 줄씩.\n"
         "- ★전제는 인물·상황 뼈대다. 제품 종류가 달라도 그 자체로는 안 맞는 게 아니다. "
         "fit=false는 **화면(특징)에 그 상황을 보여줄 장면이 없을 때만** 쓴다(예: 남이 보고 감탄하는 이야기인데 "
         "쓰는 장면이 하나도 없음). 그 경우 why_not 한 줄."
         % (json.dumps(premise, ensure_ascii=False), product, "\n".join(feats)))
    return _sg._call_json(p, _CAST_SCHEMA, note=note) or {}


def cast_gap(lines, cast, product):
    """검사는 하나로: **대본이 상황표와 맞는가**(잡다한 규칙을 덧붙이지 않는다)."""
    text = "\n".join(l.get("text") or "" for l in lines)
    p = ("[상황표]\n%s\n\n[대본]\n%s\n\n"
         "**말이 안 되는 큰 오류만** 적어라(없으면 빈 배열). 취향·표현이 아쉬운 것은 적지 마라.\n"
         "큰 오류 5가지: ①그 물건을 안 쓰는 사람에게 사주거나 선물함 ②같이 사는 사람이 '놀러 옴' 같은 관계 모순 "
         "③상황표에 없던 인물이 갑자기 나옴 ④여는 말과 뒤가 뒤집힘(혼내다가 근거 없이 칭찬 등) "
         "⑤마지막 줄이 잘렸거나 화자가 바뀜 ⑥첫 줄(훅)이 말이 안 됨(빈칸에 엉뚱한 말이 들어가 "
         "'며느리 반응 받았어요'처럼 뜻이 깨짐) ⑦첫 줄이 상황표의 opening과 다른 이야기." % (json.dumps(cast, ensure_ascii=False), text))
    out = _sg._call_json(p, _GAP_SCHEMA) or {}
    return [str(x) for x in (out.get("issues") or [])][:4]


def _cta_keyword(product):
    """댓글 키워드 — 제품 이름 끝 낱말 2~3글자(코드로 정해 매번 같은 꼴)."""
    w = [x for x in re.findall(r"[가-힣]+", product or "") if len(x) >= 2]
    t = w[-1] if w else "정보"
    return t if len(t) <= 3 else t[-2:]


_SEED_CELL_SCHEMA = {"type": "object", "properties": {"lines": {"type": "array", "items": {
    "type": "object", "properties": {"role": {"type": "string"}, "text": {"type": "string"},
                                     "fixed": {"type": "array", "items": {"type": "string"}}},
    "required": ["role", "text"]}}}, "required": ["lines"]}


def origin_from_seed(seed_src, note=None):
    """씨앗 전사를 **대본 뼈대(origin)**로 만든다 — 남의 히트작 골격을 빌리지 않는다.

    ★2026-09-21 사장님: "씨앗대로 자동배정이 하나 나오고". 그런데 자동 안이 쓰던 뼈대는
      씨앗이 아니라 **다른 히트작 원문**(노트 발명품·볼펜)이었다. 씨앗 내용을 그 골격에
      끼워 넣으니 "썰채널 어설프게 따라한" 꼴이 됐다.
      실측(09-21 오전): 씨앗을 뼈대로 쓰면 관용구 자리 6/7이 제자리에 살고 6어절 겹침 1.1%다.
    반환: {cells:[{role,text}], views, user, seed:True} — write_lines_from_origin이 그대로 먹는다.
    """
    txt = ((seed_src or {}).get("full_text") or "").strip()
    if len(txt) < 60:
        return None
    p = ("아래는 실제로 잘 된 쇼핑 숏폼 대본이다. 의미 단위로 칸을 나눠라.\n"
         "- 원문 글자를 고치거나 빼지 말고 **그대로 나누기만** 해라.\n"
         "- 칸마다 role(훅/계기/불편/전환/작동/심지어/감정/CTA 중 하나)과 text.\n"
         "- 칸마다 fixed: 그 칸에서 **제품이 바뀌어도 그대로 쓸 수 있는** 이 채널의 관용구·연결어를 원문 글자 그대로"
         "(예: '이건 바로', '이게 말도 안 되는 게', '근데 진짜 미친 포인트는'). 제품 이름·기능 낱말은 넣지 마라. 없으면 [].\n\n%s"
         % txt[:1200])
    cells = []
    # ★칸 나누기가 빈손이면 자동 안이 조용히 '남의 히트작 뼈대'로 되돌아간다(09-21 격리 실측 3회 중 1회).
    #   모델 혼잡은 잠깐 뒤 다시 하면 된다 — 1회만 다시 한다.
    for wait in (0, 4):
        if wait:
            time.sleep(wait)
        out = _sg._call_json(p, _SEED_CELL_SCHEMA, note=note) or {}
        cells = []
        for x in (out.get("lines") or []):
            t = str(x.get("text") or "").strip()
            if not t:
                continue
            # 관용구는 **그 칸 원문에 실제로 있는 글자**만 받는다 — 모델이 지어낸 말을 고정하면 안 된다.
            fx = [f.strip() for f in (x.get("fixed") or []) if isinstance(f, str) and len(f.strip()) >= 3 and f.strip() in t]
            cells.append({"role": str(x.get("role") or ""), "text": t, "fixed": fx})
        # 관용구만 있고 내용이 없는 칸("근데 진짜 미친 포인트는")은 다음 칸의 첫머리다 — 혼자 두면 대본에도
        #   내용 없는 한 줄이 생기고 그 줄에 컷이 따로 배정된다(09-21 격리 실측: 나누기가 6칸/7칸으로 흔들림).
        merged = []
        for c in cells:
            prev = merged[-1] if merged else None
            nsp = re.sub(r"\s+", "", prev["text"]) if prev else ""
            if prev and prev["fixed"] and nsp == re.sub(r"\s+", "", "".join(prev["fixed"])):
                merged[-1] = {"role": prev["role"], "text": prev["text"] + " " + c["text"],
                              "fixed": prev["fixed"] + c["fixed"]}
            else:
                merged.append(c)
        cells = merged
        if len(cells) >= 3:
            break
    if len(cells) < 3:
        if note is not None:
            note["seed_origin_failed"] = "씨앗 칸 나누기 실패(%d칸)" % len(cells)
        return None
    return {"cells": cells, "views": (seed_src or {}).get("views") or 0,
            "user": (seed_src or {}).get("video_id") or "", "seed": True}


def _drop_seed(sources, seed_src, note=None):
    """화면 후보에서 씨앗 영상을 뺀다. 씨앗밖에 없으면 그대로 둔다(화면이 통째로 비면 안 된다)."""
    if not seed_src or not sources:
        return list(sources or [])
    sid = seed_src.get("video_id")
    out = [x for x in sources if x.get("video_id") != sid]
    if not out:
        return list(sources)
    if note is not None and len(out) != len(sources):
        note["seed_visual_excluded"] = sid
    return out


def seed_source(sources, backbone_main=None):
    """씨앗 영상 = 사용자가 고른 것(backbone_main), 없으면 한국어 원문이 가장 긴 소스.

    ★고르는 규칙이 두 군데 적히면 어긋난다(0순위-B). seed_type도 이 함수를 쓴다.
    """
    if not sources:
        return None
    if backbone_main is not None:
        try:
            return sources[int(backbone_main)]
        except Exception:      # noqa: BLE001 — 범위를 벗어나면 아래 기본 규칙으로
            pass
    def _ko(t):
        return sum(1 for ch in t if "가" <= ch <= "힣") / max(1, sum(1 for ch in t if ch.isalpha()))
    kor = [x for x in sources if _ko(x.get("full_text") or "") > 0.7]
    return max(kor or sources, key=lambda x: len((x.get("full_text") or "").strip()))


def seed_block(seed_src):
    """대본 프롬프트에 싣는 **씨앗 내용** — 사장님이 고른 그 영상의 제품과 실제로 한 말.

    ★씨앗은 유형 한 단어만 뽑고 버려졌다(2026-09-21 사장님 지적: "씨앗을 고르면 사실상 다른
      대본 스타일을 선택해도 안 나오는 거 아니냐"). 자동 안이든 고른 스타일이든 **씨앗 내용을
      바탕으로** 나와야 한다. 결(말투·골격)은 스파인이, 소재·제품은 씨앗이 정한다.
    """
    if not seed_src:
        return ""
    br = seed_src.get("source_brief") or {}
    txt = (seed_src.get("full_text") or "").strip()
    out = ["[씨앗 영상 — 사장님이 고른 이 소재로 쓴다]"]
    if br.get("product"):
        out.append("  제품: %s" % br["product"])
    if br.get("core"):
        out.append("  핵심: %s" % br["core"])
    if br.get("summary"):
        out.append("  요약: %s" % br["summary"])
    if txt:
        out.append("  이 영상이 실제로 한 말: %s" % txt[:900])
    return "\n".join(out) if len(out) > 1 else ""


def material_block(seg_index, limit=140):
    """대본 쓰는 모델에게 줄 **재료 전문** — 컷마다 길이·화면·그 컷에서 한 말.

    ★전엔 특징 요약 몇 줄(`이름 — 주장 (화면: 50자)`)만 넘겼다. 그 압축에서 재료의 구체적인 그림
      (금속 롤러볼·가방에 쏙·티슈에 문질러 테스트)이 통째로 증발해 대본이 뜬구름이 됐다.
      2026-09-21 실측: 같은 재료·같은 씨앗으로 전문을 주니 지어낸 사실 0에 디테일이 살아났다.
      대본이 태깅을 봐야 하는 진짜 이유는 **말한 것이 화면에 있어야** 하기 때문이다.
    """
    by_vid = {}
    for sid, v in seg_index.items():
        if (v.get("secs") or 0) <= 0:
            continue
        by_vid.setdefault(v.get("vid") or _vid_of(sid), []).append((sid, v))
    out, n = [], 0
    for vid in sorted(by_vid):
        rows = sorted(by_vid[vid], key=lambda kv: kv[0])
        buf = ["[재료 %s]" % vid]
        for sid, v in rows:
            if n >= limit:
                break
            say = (v.get("text") or "").strip()
            buf.append("  - %s (%.1f초) | %s%s"
                       % (sid, v.get("secs") or 0.0, (v.get("desc") or "").strip(),
                          ("  <말: %s>" % say[:60]) if say else ""))
            n += 1
        out.append("\n".join(buf))
    return "\n\n".join(out)


def _tpl_slots(tpl, orig):
    """훅 틀과 원문 훅을 대조해 {슬롯}에 원래 있던 말을 뽑는다.
    「디테일에 미쳐버린 {출처}이 만든 {제품군}인데」 + 원문 → {"출처": "100년 장인"}"""
    names = re.findall(r"\{([^{}]+)\}", tpl or "")
    if not names or not orig:
        return {}
    parts = re.split(r"\{[^{}]+\}", tpl)
    pat = "".join(("(.+?)" if i else "") + re.escape(p) for i, p in enumerate(parts))
    pat = pat.replace(re.escape(" "), r"\s*")
    m = re.match(r"\s*%s\s*$" % pat, orig.strip())
    if not m or len(m.groups()) != len(names):
        return {}
    return {n: g.strip() for n, g in zip(names, m.groups()) if g and g.strip()}


def enforce_hook(lines, origin, product):
    """첫 줄(훅)은 **원문 글자 그대로**. 모델이 뼈 글자를 바꿨으면(예: '충격받았어요'→'배고파졌어요')
    원문 훅으로 되돌리고, 제품 낱말 빈칸만 이 제품으로 채운다 (2026-09-20 사장님 지적)."""
    cells = origin.get("cells") or []
    tpl = (origin.get("hook_tpl") or "").strip()
    orig = (cells[0].get("text") or "").strip() if cells else ""
    if not lines or not (tpl or orig):
        return lines
    bones = [re.sub(r"\s", "", b) for b in re.split(r"\{[^{}]+\}", tpl) if b.strip()] if tpl else []
    flat = re.sub(r"\s", "", lines[0].get("text") or "")
    if bones and all(b in flat for b in bones):
        return lines                     # 뼈 글자를 지켰다 — 그대로 둔다
    fixed = tpl or orig
    if tpl:
        # ★제품 슬롯이 아닌 칸(출처·인물·대상)에 제품 이름을 꽂으면 동어반복이 된다
        #   (2026-09-21 실측: "액체빗이 만든 액체빗"). 그 자리의 **원문 낱말**을 뽑아 쓴다.
        was = _tpl_slots(tpl, orig)
        short = _cta_keyword(product)
        for n in re.findall(r"\{([^{}]+)\}", tpl):
            fill = product if n in ("제품군", "기존물건") else (was.get(n) or short)
            fixed = fixed.replace("{%s}" % n, fill, 1)
    lines[0]["text"] = fixed if fixed.endswith((".", "!", "?")) else fixed + "."
    return lines


def fix_insta_cta(lines, spine, product):
    """인스타(존댓말) 스파인의 CTA는 **기존 문구 한 가지로** 고정한다 (2026-09-20 사장님:
    "인스타형은 다 CTA가 이상해, 궁금하시면 댓글 이거 기존걸로 가야 한다").
    원문마다 제각각인 마지막 인물 행동("언니 것도 하나 더 샀다")을 그대로 옮기다 어긋나던 자리다."""
    try:
        tone = (json.loads(spine.get("voice_json") or "{}") or {}).get("tone")
    except Exception:      # noqa: BLE001
        tone = None
    if tone != "존댓말" or not lines:
        return lines
    cta = "궁금하시면 댓글에 '%s' 남겨주세요." % _cta_keyword(product)
    last = lines[-1]
    if str(last.get("role") or "").upper() in ("CTA", "CTA줄") or "댓글" in (last.get("text") or ""):
        last["text"] = cta
    else:
        lines.append({"role": "CTA", "text": cta, "group": -1})
    return lines


_POLITE_END = re.compile(r"(요|니다|니까|세요|시오|죠)[\s.!?~…]*$")


def _polite_ratio(texts):
    ts = [t for t in (texts or []) if (t or "").strip()]
    return (sum(1 for t in ts if _POLITE_END.search(t.strip())) / len(ts)) if ts else 0.0


def _opener(text):
    ws = (text or "").strip().split()
    return re.sub(r"[^\w가-힣]", "", ws[0]) if ws else ""


def seed_voice_gap(lines, cells):
    """씨앗을 뼈대로 쓴 대본이 **씨앗의 화자·말투·칸 첫머리**를 지켰나 — 모델 호출 없이 센다.

    ★상황표 대조(cast_gap)는 남의 히트작을 빌릴 때 검사다. 씨앗은 같은 제품의 영상이라 지킬 것이
      반대다: 인물을 새로 짜는 게 아니라 **씨앗 그대로**여야 한다(2026-09-21 사장님 화면 확인 —
      반말 소개체가 "저도 아내 쓰라고 장만했습니다"로 바뀌고 관용구 칸이 빠졌다).
    반환: 어긋난 점 문장 목록(없으면 []).
    """
    cells = [c for c in (cells or []) if (c.get("text") or "").strip()]
    texts = [(l.get("text") or "").strip() for l in (lines or []) if (l.get("text") or "").strip()]
    gaps = []
    if len(texts) != len(cells):
        gaps.append("칸 수가 씨앗과 다르다(씨앗 %d칸, 대본 %d줄) — 칸을 합치거나 빼지 마라" % (len(cells), len(texts)))
    po, pn = _polite_ratio([c["text"] for c in cells]), _polite_ratio(texts)
    if abs(po - pn) > 0.4:
        gaps.append("말투가 씨앗과 다르다(씨앗은 %s인데 대본은 %s) — 씨앗의 화자·말투 그대로 써라"
                    % ("존댓말" if po >= 0.5 else "반말", "존댓말" if pn >= 0.5 else "반말"))
    elif po <= 0.1 or po >= 0.9:
        # 씨앗 말투가 한결같으면 **한 줄만 튀어도** 티가 난다(09-21 격리 실측: 반말 씨앗에 끝 줄만
        #   "꺼내 써보세요"·"불편했단 말이죠"). 비율 문턱(0.4)은 이걸 못 잡는다 — 줄 단위로 본다.
        odd = [t for t in texts if bool(_POLITE_END.search(t)) != (po >= 0.9)]
        if odd:
            gaps.append("씨앗은 전부 %s인데 이 줄만 다르다(%s) — 같은 말투로 고쳐라"
                        % ("존댓말" if po >= 0.9 else "반말", " / ".join(o[-14:] for o in odd[:3])))
    # 관용구: 씨앗에서 글자 그대로 뽑아 둔 말(cells[].fixed)이 **같은 칸**에 살아 있나. 첫 어절만 세면
    #   "이게 말도 안 되는 게 → 이게 정말 편한 게"를 못 잡는다(09-21 격리 실측).
    nsp = lambda s: re.sub(r"\s+", "", s or "")      # noqa: E731 — 띄어쓰기 차이는 같은 말이다
    lost = [f for c, t in zip(cells, texts) for f in (c.get("fixed") or []) if nsp(f) not in nsp(t)]
    if lost:
        gaps.append("씨앗 관용구가 빠지거나 바뀌었다(%s) — 그 칸에 글자 그대로 넣어라" % ", ".join("'%s'" % f for f in lost[:6]))
    # 통째로 옮김: 뼈대·말투·관용구는 씨앗 것이어도 **본문 문장**은 새로 써야 한다(남의 영상이다).
    #   훅(첫 칸)은 글자 그대로 두는 게 설계라 뺀다(enforce_hook, 2026-09-20 사장님).
    #   격리 실측(09-21): 같은 재료 3회에 6어절 겹침이 1.2%~14.9%로 흔들렸다 — 계기 칸을 절반쯤 옮긴 탓.
    seed_words = " ".join(re.sub(r"[^\w가-힣\s]", " ", " ".join(c["text"] for c in cells)).split())
    copied = []
    for t in texts[1:]:
        ws = re.sub(r"[^\w가-힣\s]", " ", t).split()
        if len(ws) >= 6 and any((" " + " ".join(ws[i:i + 6]) + " ") in (" " + seed_words + " ")
                                for i in range(len(ws) - 5)):
            copied.append(" ".join(ws[:4]) + "…")
    if copied:
        gaps.append("씨앗 문장을 6어절 넘게 그대로 옮겼다(%s) — 관용구만 남기고 나머지는 네 말로 다시 써라" % ", ".join(copied[:4]))
    if not any(c.get("fixed") for c in cells):       # 관용구를 못 뽑은 씨앗이면 첫머리로 대신 본다
        miss = [c["text"].strip().split()[0] for c, t in zip(cells, texts)
                if _opener(c["text"]) and _opener(c["text"]) != _opener(t)]
        if cells and len(miss) > len(cells) / 2:
            gaps.append("칸 첫머리가 씨앗과 다르다(씨앗 첫머리: %s) — 칸을 여는 말은 씨앗 그대로 둬라" % ", ".join(miss[:6]))
    return gaps


def write_lines_from_origin(origin, groups_out, spine, seg_index, target_seconds=25, note=None, seed_src=None):
    """원문형 스파인: ①전제 읽기 → ②이 제품 상황표 → ③원문 말투로 대본 → ④상황표와 대조, 어긋나면 1회 재작성.

    ★origin이 **씨앗**(origin_from_seed, seed=True)이면 ①②④를 건너뛴다 — 상황표는 남의 히트작
      인물 배치를 이 제품에 맞게 새로 짜는 장치인데, 씨앗은 이미 이 제품의 영상이다. 거기에 상황표를
      들이대면 화자가 바뀐다(09-21 실측). 대신 seed_voice_gap으로 씨앗의 화자·말투·칸 첫머리를 지켰나 본다.
    """
    is_seed = bool(origin.get("seed"))
    cells = [c for c in (origin.get("cells") or []) if (c.get("text") or "").strip()]
    feats = []
    for k, gi in enumerate(groups_out["order"]):
        g = groups_out["groups"][gi]
        desc = " / ".join(seg_index.get(c, {}).get("desc", "")[:50] for c in (g.get("cuts") or [])[:2] if c in seg_index)
        feats.append("  %d. [%d] %s — %s (화면: %s)" % (k + 1, gi, g.get("name"), g.get("claim"), desc))
    product = groups_out.get("product") or ""
    cast = {}
    if not is_seed:
        premise = origin.get("premise") or read_premise(origin, note=note)
        cast = build_cast(premise, product, feats, note=note)
    if cast.get("fit") is False:
        if note is not None:
            note["cast_unfit"] = cast.get("why_not") or "전제가 이 제품과 안 맞음"
        return []
    hook_tpl = (origin.get("hook_tpl") or "").strip()
    hook_rule = ("- ★첫 줄(훅)은 이 틀의 글자를 한 글자도 바꾸지 말고 {}빈칸만 바꿔라: %s\n" % hook_tpl) if hook_tpl else ""
    last = _dedup(cells[-1]["text"]) if cells else ""
    loop = bool(last) and not re.search(r"[.!?요다임]\s*$", last)
    loop_rule = "- ★원문은 마지막을 끝맺지 않고 끊어 첫 장면으로 잇는다(반복 재생). 새 대본도 똑같이 끊어라.\n" if loop else ""
    # 칸마다 원문 글자수를 알려준다 — 길이는 씨앗(원문)을 따른다(2026-09-21 사장님
    #   "씨앗 길이를 따라도 된다"). 목표 초를 따로 들이대면 원문 결이 먼저 깨진다.
    cell_spec = "\n".join("  %d. %s - %d자 내외 (원문: %s)%s"
                            % (i, c.get("role") or "", len(c.get("text") or ""), c.get("text") or "",
                               (" ★이 칸에 글자 그대로 넣을 말: %s" % " / ".join("'%s'" % f for f in c["fixed"]))
                               if c.get("fixed") else "")
                            for i, c in enumerate(cells, 1))
    # 인물·제품 규칙은 뼈대가 누구 것이냐로 갈린다 — 값은 여기 한 곳에서만 정한다(0순위-B).
    if is_seed:
        head = "[원문]은 바로 [이 제품]을 소개해 잘 된 영상이다. 그 뼈대·화자 그대로 [이 제품]의 대본을 새로 써라."
        who_rule = ("- ★말하는 사람(화자)과 말투(반말/존댓말)는 원문 그대로다. 원문에 없는 '저·아내·남편·엄마' 같은 "
                    "1인칭 사연이나 새 인물을 만들지 마라.\n"
                    "- ★칸을 여는 말(원문 각 칸의 첫머리 관용구·연결어)은 그 칸 첫머리에 글자 그대로 둔다.\n"
                    "- ★첫 줄(훅)은 원문 그대로 나간다. 훅이 부른 대상(누가 쓰는 물건인지)을 본문에서 다른 사람들로 바꾸지 마라.\n")
        prod_rule = "- 제품 이야기는 아래 특징과 [재료]에 있는 것만. 원문이 말했어도 [재료] 화면에 없으면 빼라.\n"
        cast_part = ""
    else:
        head = "[상황표]대로 [이 제품]의 대본을 써라."
        who_rule = "- ★사람·장소·사는 사람은 [상황표]를 따른다. 원문의 인물 배치를 베끼지 마라.\n"
        prod_rule = "- 제품 이야기는 아래 특징에 있는 것만. 원문의 원래 제품 이야기는 한 조각도 남기지 마라.\n"
        cast_part = "[상황표]\n%s\n\n" % json.dumps(cast, ensure_ascii=False)
    prompt = (
        "아래 [원문]은 조회수 %s회가 나온 쇼핑 숏폼 대본이다. %s\n\n규칙\n%s%s"
        "- 칸은 정확히 %d개, 순서는 원문과 똑같이. 칸을 더 만들거나 빼지 마라.\n"
        "- 칸마다 원문의 말투·어미·연결어를 그대로 살리고, 글자수도 [칸 구조]의 ±20%% 안으로.\n"
        "- ★원문에 없는 칸을 새로 만들지 마라. 원문에 CTA가 없으면 '써보세요' 같은 권유로 끝내지 마라.\n"
        "%s%s"
        "- ★[재료]의 장면 설명에 실제로 보이는 것만 말해라. 화면에 없는 수치·출처·판매량·효능을 지어내지 마라.\n"
        "- 같은 문장을 두 번 쓰지 마라. 원문·특징·재료 문장을 통째로 베끼지 말고 네 말로 다시 써라.\n"
        "- 줄마다 role(원문 칸 이름), group(그 줄이 말하는 특징 번호, 훅·마무리는 -1).\n\n"
        "%s[원문]\n%s\n\n[칸 구조]\n%s\n\n[이 제품] %s\n%s\n\n"
        "%s\n\n[재료 - 이 제품 영상들의 컷마다 길이·화면·그 컷에서 한 말]\n%s"
        % (origin.get("views") or 0, head, hook_rule, loop_rule, len(cells), who_rule, prod_rule,
           cast_part, _origin_text(origin), cell_spec,
           product, "\n".join(feats), seed_block(seed_src), material_block(seg_index)))

    # 원문 칸들이 부호 없이 이어지는 꼴이면 새 대본에도 마침표를 안 붙인다.
    _open = sum(1 for c in cells if not re.search(r"[.!?。]\s*$", (c.get("text") or "").strip()))
    _punct = _open < max(1, len(cells)) * 0.6
    def _run(p):
        out = _sg._call_json(p, _ORIGIN_SCHEMA, note=note) or {}
        ls = _clean_lines(out, punct=_punct)
        for l in ls:
            l["text"] = _dedup(l.get("text") or "")
        raw_last = ((out.get("lines") or [{}])[-1].get("text") or "").strip()
        if ls and loop and not re.search(r"[.!?]\s*$", raw_last):
            ls[-1]["text"] = ls[-1]["text"].rstrip(".")
        return ls

    # 검사는 뼈대에 맞는 것 하나만: 씨앗이면 '씨앗 그대로인가', 빌린 원문이면 '상황표와 맞나'.
    _gap = (lambda ls: seed_voice_gap(ls, cells)) if is_seed else (lambda ls: cast_gap(ls, cast, product))
    _what = "씨앗과" if is_seed else "상황표와"
    lines = _run(prompt)
    gaps = _gap(lines) if lines else []
    if gaps:
        l2 = _run(prompt + "\n\n[고칠 점] 앞 대본이 %s 이렇게 어긋났다:\n- " % _what + "\n- ".join(gaps))
        left = _gap(l2) if l2 else gaps
        if l2 and len(left) < len(gaps):
            lines, gaps = l2, left
    if note is not None:
        # ★assemble_clean은 note["cast"]["issues"]로 통과 여부를 본다 — 씨앗 검사도 같은 칸에 싣는다.
        note["cast"] = {"table": cast, "issues": gaps}
        if is_seed:
            note["seed_voice"] = {"issues": gaps}
    lines = enforce_hook(lines, origin, product)
    lines = fix_insta_cta(lines, spine or {}, product)
    return _no_made_up_country(_one_full_name(lines, product), seg_index)


def write_lines(groups_out, hook_spine, seg_index, target_seconds=25, note=None, seed=None, seed_src=None,
                use_seed_origin=False):
    """훅 1줄 + 특징 묶음마다 1줄 + CTA 1줄. 각 줄은 **마침표 하나**(문장분리기가 줄 수를 세는 함정)."""
    from shopping_shorts.edit_plan import _SYLLABLES_PER_SEC, _speech_speed
    cps = _SYLLABLES_PER_SEC * _speech_speed()
    n_lines = len(groups_out["order"]) + 2
    per_line = max(12, int(target_seconds * cps / n_lines))
    try:
        chain = json.loads(hook_spine.get("beat_chain_json") or "[]")
    except Exception:
        chain = []
    hook_rule = (chain[0] if chain else "") or hook_spine.get("situation_type") or ""
    feats = []
    for k, gi in enumerate(groups_out["order"]):
        g = groups_out["groups"][gi]
        desc = " / ".join(seg_index.get(c, {}).get("desc", "")[:50] for c in (g.get("cuts") or [])[:2] if c in seg_index)
        feats.append(f"  {k + 1}. [{gi}] {g.get('name')} — {g.get('claim')} (화면: {desc})")
    # ★길이는 씨앗을 따른다(2026-09-21 사장님 "씨앗 길이를 따라도 된다"). 씨앗이 37.8초인데
    #   25초로 자르면 칸이 통째로 빠져 "부실하다"가 된다(실측 B안 16.3초).
    _seed_secs = _secs((seed_src or {}).get("full_text") or "") if seed_src else 0.0
    if _seed_secs >= 12.0:
        target_seconds = _seed_secs
    origin = spine_origin(hook_spine)
    # ★자동 안(씨앗 배정)은 **씨앗 자신을 뼈대**로 쓴다 — 남의 히트작 골격을 빌리지 않는다.
    #   스파인이 씨앗 유형으로 고른 것이면 그 스파인의 원문 대신 씨앗 원문을 뼈대로 둔다.
    if seed_src and (use_seed_origin or (hook_spine or {}).get("_use_seed_origin")):
        _so = origin_from_seed(seed_src, note=note)
        if _so:
            origin = _so
            if note is not None:
                note["origin_from_seed"] = True
                note["seed_cells"] = _so.get("cells")     # 점검 도구가 **대본을 만든 그 칸**과 대조한다
    if origin:
        return write_lines_from_origin(origin, groups_out, hook_spine, seg_index, target_seconds,
                                       note=note, seed_src=seed_src)
    roles, tpl = _spine_style(hook_spine)
    if roles and tpl:
        # ★스파인에 문장틀(templates)·역할순서(beat_roles)가 있으면 **그 꼴 그대로** 쓴다(2026-09-17 사장님:
        #   "이븐쇼핑 스타일" = 천재·떼돈·「이건 바로 OO」·CTA 없음). 전엔 훅 한 줄만 빌리고 나머지는
        #   자체 [훅]+[특징]+[댓글CTA]로 써서 스타일이 통째로 사라졌다.
        # ★목표 초에 맞춰 특징 줄 수를 자른다(2026-09-18 실측: 정체형 10~11줄 = 30.6~34.8초, 목표 25초).
        #   구조 줄(정체·떼돈·이건 바로·마무리)은 스타일의 뼈대라 안 자르고, 특징 줄만 앞에서부터 남긴다.
        #   줄당 SECS_PER_LINE초로 잡으면 몇 줄까지 되는지가 나온다.
        feat_n = len(_feature_roles(roles, tpl))
        structural = len(roles) - feat_n
        allow = max(1, int(target_seconds // SECS_PER_LINE) - structural)
        if len(groups_out["order"]) > allow:
            groups_out = dict(groups_out, order=list(groups_out["order"])[:allow])
            feats = feats[:allow]
        n_lines = len(roles) + max(0, len(groups_out["order"]) - feat_n)
        per_line = max(12, int(target_seconds * cps / max(1, n_lines)))
        # ★seed를 그대로 넘긴다 — 안 넘기면 늘 0이라 **매번 첫 틀만** 쓰여 틀을 6개 만들어도
        #   같은 대본이 나온다(2026-09-18 실측으로 잡은 배선 누락). seed가 바뀌면 칸마다
        #   다음 틀로 돌아 같은 재료에서 N가지 대본이 나온다.
        prompt = _spine_prompt(groups_out, hook_spine, roles, tpl, feats, per_line, seed=seed)
        # ★고른 스타일도 **씨앗 내용을 바탕으로** 쓴다(2026-09-21 사장님). 틀은 스파인이, 소재는 씨앗이.
        _sb = seed_block(seed_src)
        if _sb:
            prompt += chr(10) + chr(10) + _sb
        # ★틀 경로도 재료를 **전문으로** 본다(2026-09-21 사장님 "B는 완전 부실하게").
        #   전엔 원문형 경로에만 넣어, 틀 경로는 `이름 - 주장 (화면 50자)` 요약만 보고 썼다.
        #   그 결과가 "구멍의 정체"·"내부까지 밀봉" 같은 뜬 문장이다(재료엔 그런 말이 없다).
        prompt += (chr(10) * 2 + "[재료 - 컷마다 길이·화면·그 컷에서 한 말]" + chr(10)
                   + material_block(seg_index) + chr(10) * 2
                   + "- 위 재료에 실제로 보이는 것만 말해라. 화면에 없는 기능·수치를 지어내지 마라.")
        lines = _clean_lines(_sg._call_json(prompt, _LINES_SCHEMA, note=note) or {})
        lines = _repair_joins(lines, plan_for_repair(groups_out, roles, tpl, seed, hook_spine), note=note)
        lines = _one_full_name(lines, groups_out.get("product") or "")
        lines = _no_made_up_country(lines, seg_index)
        return _fit_length(lines, target_seconds, note=note)
    prompt = (
        f"제품: {groups_out.get('product')}\n"
        f"훅 스타일: 「{hook_spine.get('name')}」 — {hook_rule}\n"
        f"말투: {hook_spine.get('emotion_arc') or ''} / {hook_spine.get('appeal') or ''}\n\n"
        "아래 특징을 **이 순서 그대로** 한 줄씩 써라. 화면은 이미 정해져 있다 — 그 화면에서 보이는 것을 말해라.\n"
        + "\n".join(feats) + "\n\n"
        "규칙:\n"
        f"- 줄 구성: 훅 1줄(role=hook, group=-1) → 특징 줄들(role=feature, group=위 [번호]) → CTA 1줄(role=cta, group=-1). 총 {n_lines}줄.\n"
        f"- 한 줄은 **마침표 하나**로 끝나는 문장 하나. 쉼표는 써도 된다. 줄당 {per_line}자 안팎.\n"
        "- 구어체, 남에게 말하듯. 원본 영상의 문장을 그대로 베끼지 마라.\n"
        "- 훅은 훅 스타일 규칙대로. CTA는 반드시 「궁금하면 댓글에 '○○' 남겨주세요」 꼴 — ○○은 제품과 관련된 두세 글자 낱말.\n"
        "- 화면에 없는 기능·수치를 지어내지 마라.")
    out = _sg._call_json(prompt, _LINES_SCHEMA, note=note) or {}
    return _clean_lines(out)


# ★'한국'은 넣지 않는다 — 우리 시청자 기준 말("한국은 물론 전 세계")이라 바꾸면 "해외은 물론"이 된다(실측 bbbd6f20fe39)
_COUNTRY = re.compile(r"(미국|일본|중국|독일|프랑스|영국|이탈리아|스웨덴|덴마크|대만|베트남|태국|호주|캐나다|스페인|네덜란드|스위스)")
# 나라 이름 뒤에 오면 '해외'로 바꿔도 되는 말(사람·회사). 이 밖의 말(냉장고·주방) 앞의 나라 이름은 뺀다
_PERSONISH = r"(천재|개발자|디자이너|엔지니어|사람|주부|엄마|아빠|회사|기업|브랜드|제조사|직원|장인|발명가|공학자|교수|의사|박사|셰프|현지)"
# '해외'로 바꾼 뒤 받침 없는 말에 맞게 조사 고치기(나라 이름은 받침이 제각각이라)
_JOSA_FIX = [("해외은", "해외는"), ("해외이 ", "해외가 "), ("해외을", "해외를"), ("해외과", "해외와"), ("해외으로", "해외로")]


def _no_made_up_country(lines, seg_index):
    """소스(태깅 설명·말)에 없는 나라 이름은 '해외'로 바꾼다.
    프롬프트('모르면 해외로')를 모델이 어겼다(실측 행주 job bb4246b57a36: "프랑스 천재" — 소스 어디에도 없음)."""
    blob = " ".join((v.get("desc") or "") + " " + (v.get("text") or "") for v in (seg_index or {}).values())
    out = []
    for L in lines:
        t = L["text"]
        for c in set(_COUNTRY.findall(t)):
            if c not in blob:
                # ★사람·회사 앞이면 '해외'(해외 천재), 물건 앞이면 나라만 뺀다(09-18 실측 76번
                #   "일본 냉장고 보고 만든 일본 천재" → "해외 냉장고 … 해외 천재"로 두 번 걸렸다)
                t = re.sub(c + r" (?!" + _PERSONISH + r")", "", t)
                t = t.replace(c, "해외")
        for x, y in _JOSA_FIX:
            t = t.replace(x, y)
        out.append(dict(L, text=t.replace("해외 해외", "해외")))
    return out


def _one_full_name(lines, product):
    """제품 전체 이름은 **공개 줄(reveal) 한 번만**. 나머지 줄은 끝 낱말(카메라·수납함)로 줄인다.
    프롬프트로 말해도 모델이 어겼다(실측 job bb38c10bcca9: 5번 줄 "NORDECO 빈티지 미니 TLR 카메라로") → 코드로 못 박는다."""
    words = (product or "").split()
    if len(words) < 2:
        return lines
    short = words[-1]
    # ★원문형·씨앗 경로의 칸 이름은 훅/전환/작동…이라 'reveal' 줄이 없다. 그대로 두면 이름을 밝히는
    #   유일한 줄까지 깎여 "이건 바로 빗"이 된다(09-21 격리 실측 3회 중 3회). 그땐 **처음 나온 곳**이 공개 줄이다.
    has_reveal = any(L.get("role") == "reveal" for L in lines)
    out, kept = [], False
    for L in lines:
        t = L["text"]
        if product in t:
            if L.get("role") == "reveal":
                pass
            elif not has_reveal and not kept:
                kept = True
                head, _, tail = t.partition(product)
                t = head + product + tail.replace(product, short)
            else:
                t = t.replace(product, short)
        out.append(dict(L, text=t))
    return out


def _fit_length(lines, target_seconds, note=None, slack=2.0):
    """실제 읽는 초(narr_secs 합)를 재서 목표+slack을 넘으면 **가운데 특징 줄부터** 뺀다.
    ★줄 수로만 맞추면 안 된다(2026-09-18 실측: 8줄인데 정체형 30.3초·발명품형 29.1초 — bait 틀 하나가 50자).
      구조 줄(group=-1: 훅·정체·공개·마무리)과 첫·마지막 특징 줄은 남긴다(반전이 끝맺음).
    짧은 건 늘리지 않는다 — 없는 말을 지어내게 된다(오용형 6줄 18초는 틀 구조 그대로)."""
    def total(ls):
        return sum(_secs(L["text"]) for L in ls)
    lines = list(lines)
    dropped = []
    while total(lines) > target_seconds + slack:
        feat_idx = [i for i, L in enumerate(lines) if (L.get("group") if L.get("group") is not None else -1) >= 0]
        # ★특징 줄은 3개까지 남긴다(2026-09-18 사장님 "용도 보통 4개 아닌가"). 2개까지 빼면 오용형의
        #   초보→고수→반전에서 고수 줄이 빠져 용도가 2개가 됐다(실측 6편 중 3편). 원문 중앙값도 3이다
        #   (이븐쇼핑 78편 장점 전환 · 초보고수 꼴 183편 용도 전환).
        if len(feat_idx) <= MIN_FEATURE_LINES:
            break
        k = feat_idx[len(feat_idx) // 2]
        dropped.append(lines.pop(k)["text"])
    if note is not None and dropped:
        note["length_dropped"] = dropped
    return lines


def _clean_lines(out, punct=True):
    lines = []
    for L in (out.get("lines") or []):
        t = re.sub(r"\s+", " ", str(L.get("text") or "")).strip()
        if not t:
            continue
        # ★슬롯 이름이 글자로 새는 것(실측 job bbd3cfdd12de "…숨기는 용도끝.") — 중괄호 유무 모두 지운다
        t = re.sub(r"\{[^{}]*\}", "", t)
        t = re.sub(r"\s*(용도끝|용도[0-9]?|효능[0-9]?|속성[0-9]?|본래용도|권위자|제품군|성과|대상)\s*(?=[.,]|$)", "", t).strip()
        if not t:
            continue
        # 마침표 하나로 강제 — 문장 안 마침표는 쉼표로, 끝은 마침표
        # ★원문이 부호 없이 다음 칸으로 이어지는 꼴(~없지만 / ~물론이고)이면 마침표를 안 붙인다.
        #   붙이면 이어져야 할 말이 끊겨 비문이 된다(2026-09-21 실측 "…흘러내리지만.").
        #   뒤 단계는 안전하다 — edit_plan.script_sentences는 **줄 단위**로 자르고(마침표 무관),
        #   _narr_key는 문장부호를 지우고 비교한다.
        t = t.rstrip(".!?。") .replace(". ", ", ").replace("!", ",").replace("?", ",")
        if punct:
            t += "."
        lines.append({"role": str(L.get("role") or "feature"), "text": t, "group": int(L.get("group", -1))})
    return lines


# ── 스파인 문장틀 그대로 쓰기 ─────────────────────────────────────────
def spine_origin(spine):
    """원문형 스파인이면 {cells:[{role,text}], views, user, hook_tpl} — 아니면 None (2026-09-20 사장님 확정).

    ★왜: 칸별 빈칸 문장틀을 조립하면 남의 문장에 제품 말만 끼워 문장이 깨진다
      (실측 09-19~20: 칸 조각 조립 15편 전부 / 스파인 78·79 5줄 중 3줄 — "통잠이 쏙 올라오는데",
       "앞으로 아기 인형 들고 다닐 일은 없겠는데요"). 히트작 원문 한 편을 통째로 보여주고
      제품 이야기만 바꿔 쓰게 하면 흐름·조사가 안 깨진다(소재 12종 36편 중 34편 검사 통과).
    스파인은 그대로 남는다 — 유형·말투·훅 고정·회원별 순번을 정하는 관리 단위."""
    # ★templates만 있고 beat_roles가 없는 스파인도 있다 — _spine_style은 둘 다 없으면 ([],{})라
    #   원문을 못 찾는다. 여기선 templates만 보고 판단한다.
    tpl = spine.get("templates")
    if not isinstance(tpl, dict):
        try:
            tpl = json.loads(spine.get("templates_json") or "{}")
        except Exception:      # noqa: BLE001
            tpl = {}
    o = tpl.get("_origin") if isinstance(tpl, dict) else None
    if not (isinstance(o, dict) and o.get("cells")):
        return None
    return _strip_caption_noise(o)


# ★자막 잡음은 **읽는 자리에서** 지운다 (2026-09-21 사장님 "음악저게 이번에도 나오는게
#   구조적으로 뭐가있네 문제"). 유튜브 자동자막이 남긴 `[음악]`·`[박수]`가 원문 칸에
#   박혀 있었고, 백본은 원문을 그대로 베끼는 게 일이라 **대본에 그대로 나왔다**
#   (실측 스파인 387: "…아이템이 [음악] 있어." → 생성된 대본에도 동일).
#   DB만 고치면 새로 넣는 스파인에서 또 나온다 — 원문을 읽는 유일한 관문인
#   여기서 걸러야 재발이 없다(0순위-B: 판정은 한 곳에서).
_CAPTION_NOISE = re.compile(r"\s*\[\s*(음악|박수|웃음|박수소리|Music|Applause|Laughter)\s*\]\s*", re.I)


def _strip_caption_noise(origin):
    """원문 칸·훅틀에서 `[음악]` 같은 자막 잡음을 걷어낸 사본을 돌려준다.
    원본 dict를 고치지 않는다 — 호출부가 DB 객체를 그대로 들고 있을 수 있다."""
    cells = origin.get("cells") or []
    if not any(_CAPTION_NOISE.search(c.get("text") or "") for c in cells)             and not _CAPTION_NOISE.search(origin.get("hook_tpl") or ""):
        return origin                      # 흔한 길 — 사본을 안 만든다
    out = dict(origin)
    out["cells"] = [dict(c, text=_clean_noise_text(c.get("text") or "")) for c in cells]
    if origin.get("hook_tpl"):
        out["hook_tpl"] = _clean_noise_text(origin["hook_tpl"])
    return out


def _clean_noise_text(t):
    return re.sub(r"\s{2,}", " ", _CAPTION_NOISE.sub(" ", t)).strip()


def _spine_style(spine):
    """(beat_roles, templates). list_spines가 풀어준 값이 없으면 *_json 컬럼에서. 둘 다 없으면 ([], {})."""
    roles = spine.get("beat_roles")
    tpl = spine.get("templates")
    if roles is None or tpl is None:
        try:
            roles = json.loads(spine.get("beat_roles_json") or "[]")
            tpl = json.loads(spine.get("templates_json") or "{}")
        except Exception:
            return [], {}
    return list(roles or []), dict(tpl or {})


MAX_EXTRA_FEATURE_LINES = 2   # 틀 밖으로 늘리는 특징 줄 상한(위 실측)
MIN_FEATURE_LINES = 3         # 길이 맞추기에서 남기는 특징 줄 하한(_fit_length)


def _feature_roles(roles, tpl):
    """{효능…}·{용도…} 자리가 있는 역할 = 특징 하나를 말하는 줄. 나머지는 구조 줄(정체 숨기기·공개·마무리)."""
    return [r for r in roles if any(("{효능" in t or "{용도" in t) for t in (tpl.get(r) or []))]


def _spine_plan(roles, tpl, n_feat):
    """[(role, group)] — 구조 줄은 group=-1, 특징 줄은 order 번호. 특징이 효능 자리보다 많으면
    두 번째 효능 역할(more 류)을 마지막 효능 역할(twist) 앞에 반복해 늘린다. 적으면 남는 자리는 뺀다."""
    feat_roles = _feature_roles(roles, tpl)
    # 특징이 효능 칸보다 적으면 **첫 칸과 마지막 칸(반전)을 남기고 가운데부터** 뺀다
    #   (25초 맞추기에서 twist가 잘리던 것 — 반전이 스타일의 끝맺음이라 빠지면 안 된다)
    keep_feat = list(feat_roles)
    while len(keep_feat) > max(n_feat, 0) and len(keep_feat) > 2:
        keep_feat.pop(len(keep_feat) // 2)
    if n_feat < len(keep_feat):                 # 1개만 남으면 첫 효능 줄(반전만 덩그러니면 어색)
        keep_feat = keep_feat[:n_feat]
    plan, used = [], 0
    for r in roles:
        if r in feat_roles:
            if r in keep_feat and used < n_feat:
                plan.append([r, None]); used += 1          # 번호는 마지막에 순서대로
        else:
            plan.append([r, -1])
    # ★반복은 최대 2줄까지(2026-09-18 실측 오용형2: 특징 5개에 twist류가 4번 이어져 9줄·34초). 틀의 6~9줄 구조가 본체다.
    n_feat = min(n_feat, used + MAX_EXTRA_FEATURE_LINES)
    # ★효능 칸이 3개 미만(오용형: cases·twist뿐)이면 늘리지 않는다 — 늘리면 twist("근데 미친 활용법은 따로 있는데")가
    #   3번 이어진다(실측 오용형0~4 전부). 오용형은 cases 한 줄이 특징을 나열하는 구조라 틀 그대로 6줄이 맞다.
    if len(feat_roles) < 3 or "more" not in roles:
        # ★'심지어(more)' 칸이 없는 틀(오용형·인스타형)은 칸마다 역할이 달라 반복하면 어색하다
        #   (실측 인스타 지인증언형 job bb22636a44f0: "알고 보니…" 3줄 연속). 유튜브 정체·발명품형만 늘린다.
        n_feat = min(n_feat, used)
    if used < n_feat and feat_roles:
        rep = feat_roles[1] if len(feat_roles) > 1 else feat_roles[0]
        pos = next((i for i, (r, _) in enumerate(plan) if r == feat_roles[-1]), len(plan))
        while used < n_feat:
            plan.insert(pos, [rep, None]); used += 1; pos += 1
    gi = 0
    for item in plan:
        if item[1] is None:
            item[1] = gi; gi += 1
    return [tuple(x) for x in plan]


def _spine_prompt(groups_out, spine, roles, tpl, feats, per_line, seed=None):
    plan = _spine_plan(roles, tpl, len(groups_out["order"]))
    lines_spec = []
    order = groups_out.get("order") or []
    # ★틀은 **코드가 골라 하나만** 준다(2026-09-18 사장님 "5개 중 랜덤으로 골라주면 반려고 뭐고 없다").
    #   종전엔 `[:3]`으로 앞 3개를 나열해 모델에게 맡겼다. 두 가지가 고장났다:
    #     ① 틀을 5~6개로 늘려도 **뒤엣것은 보이지도 않는다**(56번은 6개 중 3개만).
    #     ② 여러 개를 보여주면 모델이 대개 첫 번째를 쓰고, 그 어조를 다음 줄에 복제한다
    #        → 한 어미가 50~70%(실측: 68번 `미쳤다는 거` 3줄, 67번 `~함` 5줄).
    #   하나만 주면 고를 여지가 없어 틀 그대로 나오고, 같은 칸이 여러 줄이면(more×N)
    #   **줄마다 다른 틀**이 돌아가 어미가 저절로 섞인다. 판정에 기대지 않는 게 핵심이다.
    #   ★무작위가 아니라 **순서대로 돌린다**(2026-09-18 사장님). 난수는 우연히 같은 틀을 두 번
    #     뽑을 수 있지만, 순서대로면 틀이 N개일 때 **N가지가 반드시 다 나온다**. 재현도 된다.
    #     시작 위치만 seed로 옮겨 같은 재료에서 여러 편을 뽑을 때 첫 줄이 겹치지 않게 한다.
    # seed는 호출부마다 꼴이 다르다 — 배치는 job id **문자열**(bb_batch5.py `seed=base`), 시험은 int.
    #   문자열이면 `i % len`이 TypeError(2026-09-18 4건 전부 예외). 문자열은 crc32로 정수화한다.
    # 시작점(seed + 스파인id×7, 스파인마다 엇갈림)과 칸별 순번은 _pick_templates 한 곳에서 정한다
    picked = _pick_templates(plan, tpl, seed, spine)
    for k, (r, gi) in enumerate(plan):
        ex = picked[k]
        # ★group은 묶음 **원번호**(assign_cuts가 groups[gi]로 찾는다) — 순서 번호를 주면 다른 묶음 컷이 붙는다
        tgt = f"group={order[gi]} (특징 {gi + 1}번)" if 0 <= gi < len(order) else "group=-1"
        lines_spec.append(f"  {k + 1}. role={r}, {tgt} — 문장틀: {ex}")
    return (
        f"제품: {groups_out.get('product')}\n"
        f"대본 스타일: 「{spine.get('name')}」 — {spine.get('situation_type') or ''}\n"
        f"감정선: {spine.get('emotion_arc') or ''}\n\n"
        "특징(화면은 이미 정해져 있다 — 그 화면에서 보이는 것만 말해라):\n" + "\n".join(feats) + "\n\n"
        f"아래 줄을 **이 순서·이 역할 그대로** {len(plan)}줄 써라. 줄마다 **그 줄에 적힌 문장틀 하나**를 쓰고 "
        f"{{…}} 자리만 제품에 맞게 채운다 — 틀을 바꾸거나 다른 줄의 틀을 쓰지 마라(말끝이 줄마다 달라야 한다).\n"
        + "\n".join(lines_spec) + "\n\n"
        "규칙:\n"
        "- 줄 수·순서·role·group을 바꾸지 마라. 줄을 합치거나 빼지 마라.\n"
        f"- 한 줄은 **마침표 하나**로 끝나는 문장 하나. 쉼표는 써도 된다. 줄당 {per_line}자 안팎.\n"
        "- 문장틀의 말투(반말·'~다는데'·'~라고')를 유지해라. 댓글 유도·구독 요청 같은 CTA를 덧붙이지 마라.\n"
        "- {나라}는 화면·자막에서 알 수 없으면 '해외'로.\n"
        # ★가격·숫자를 지어내지 않는다(실측 68·69: "단돈 몇만 원"·"몇천 원짜리"). 특징·화면에 가격이 없으면 '이 가격'으로.
        # ★제품 이름이 영문 그대로 나왔다(실측 job bb1b0f32df87 "이건 바로 Retro Style Mini TLR Digital Camera").
        "- 제품 이름 전체({제품})는 **'이건 바로' 공개 줄에서 한 번만** 써라. 다른 줄은 '이 제품'·'이 카메라'처럼 짧은 일반명({제품군})으로(실측: 한 편에 제품명 3번 반복).\n"
        "- {제품}·{제품군}은 **한국어로** 써라. 영문 제품명은 뜻을 한국어로 옮기고, 브랜드명만 영문 그대로 둔다(예: 'NORDECO 빈티지 미니 카메라').\n"
        "- {가격}은 위 특징·화면에 **실제 가격이 있을 때만** 채워라. 없으면 '이 가격'·'이 값'으로 쓰고 숫자를 지어내지 마라. "
        "{본래용도}도 원본에서 확인된 것만 — 모르면 그 틀 대신 '평범해 보이는' 식으로 에둘러라.\n"
        # ★빈칸에 무엇을 넣을지 **원문 예시로** 못 박는다(2026-09-18 실측). 안 적어두면
        #   {성과}에 형용사가 들어가 "정교한 해외 천재의 발명품"처럼 어색해진다.
        #   원문은 전부 동사구다: 세월을 되찾아주는 / 업계 자체를 망하게 한 / 여름을 지배해 버린.
        "- {성과}는 **동사구**로 채워라 — 예: '세월을 되찾아주는', '업계 자체를 망하게 한', "
        "'여름을 지배해 버린'. 형용사 한 단어('정교한')는 쓰지 마라.\n"
        "- {대상}은 사람·업계 같은 **명사**로 — 예: '문구 업계', '다이어트 하는 사람들'.\n"
        # ★빈칸 뒤에 어미가 바로 붙는 틀({효능}는데·{효능}다는 거·{효능}주는데)은 빈칸을 **어간**으로 끝내야
        #   맞물린다. 실측(2026-09-18 4건): '분류한다+는는데'·'빨아들여 주는+는데'·'쓰는 건+까지 해 준다는데'.
        "- ★빈칸 바로 뒤에 어미가 붙어 있으면 빈칸은 **그 어미에 맞물리는 어간**으로 끝내라. 완성된 문장을 빈칸에 넣지 마라. "
        "예) '{효능}는데' → '연기를 싹 빨아들이는데' / '{효능}다는 거' → '기름을 알아서 모은다는 거' / "
        "'{효능}주는데' → '한 장씩 뜯어 쓰게 해 주는데' / '{효능2}까지 해 준다는데' → '어디서나 가볍게 쓰는 것까지 해 준다는데'. "
        "'~는는데'·'~다는는데'·'~는 건까지 해'처럼 같은 어미가 겹치면 틀린 것이다.\n"
        "- ★문장틀의 **끝말을 바꾸지 마라**. 틀이 '~는데'로 끝나면 '~는데'로, '~다는 거'면 "
        "'~다는 거'로 끝내라(실측: 틀을 벗어나면 '~하는 거'처럼 이 채널에 없는 말이 된다).\n"
        "- 원본 영상의 문장을 그대로 베끼지 마라.")



# ── 어미 결합 검사·수리 ────────────────────────────────────────────────
# 틀 '{효능}는데'에 모델이 '분류한다는'을 넣으면 '분류한다는는데'가 된다(2026-09-18 실측 4건).
# 순서: ①기계 수리(겹친 어미 축약) ②그래도 깨졌으면 그 줄만 다시 쓰게 1회 ③그래도면 기계 수리본 유지.
_JOIN_FIXES = [
    (re.compile(r"는는데"), "는데"), (re.compile(r"다는는데"), "다는데"), (re.compile(r"는는 거"), "는 거"),
    (re.compile(r"다는다는"), "다는"), (re.compile(r"는데는데"), "는데"), (re.compile(r"는 건까지 해"), "까지 해"),
    (re.compile(r"주는는데"), "주는데"), (re.compile(r"^근대 "), "근데 "), (re.compile(r"한다는는"), "한다는"),
    # 문장이 '~다는'에서 끊김(실측 job bb931fdbf7c8 "느끼게 해준다는.") → '~다는 거'
    (re.compile(r"다는(?=\.?$)"), "다는 거"),       # 끝 마침표가 붙어 와도 잡는다
    # '~주게 해 주는데' 이중(실측 행주 정체형 "살려주게 해 주는데") → '~주는데'
    (re.compile(r"주게 해 주"), "주"),
    # 고수 줄 '{용도2} 만들어 버림'에 동작이 들어오면 "보관하는 것 만들어 버림"(09-18 실측 2편) → '~하는 데 써 버림'
    (re.compile(r"(\S+는) 것 만들어 버림"), r"\1 데 써 버림"),
]
_BAD_JOIN = re.compile(r"는는|데데|다는다는|는데는데|는 건까지 해")


def _bad_join(text):
    t = str(text or "").rstrip(".").strip()
    return bool(_BAD_JOIN.search(t))


def _fix_join(text):
    t = str(text or "")
    for rx, rep in _JOIN_FIXES:
        t = rx.sub(rep, t)
    return t


def _pick_templates(plan, tpl, seed, spine):
    """줄마다 쓸 문장틀 — **한 곳에서만** 정한다(_spine_prompt·plan_for_repair 공용, 0순위-B).
    ★칸마다 **따로** 돈다(혼합진법): 칸 k의 순번 = (시작점 ÷ 앞 칸들 틀 수의 곱) mod 이 칸 틀 수.
      전엔 모든 칸이 같은 숫자로 같이 움직여, 칸마다 틀이 3개면 회원 100명에게 조합이 **3가지**뿐이었다
      (2026-09-18 실측 66번: 100명 중 44명이 같은 대본). 이제 조합 수 = 칸별 틀 수의 곱.
    같은 칸이 또 오면(more×N) 그 칸 안에서 다음 틀로."""
    import zlib
    # 시작점 = (seed, 스파인id)를 **함께** 해시 — 같은 회원이라도 스파인이 다르면 조합 전체가 달라진다
    #   (단순 덧셈이면 혼합진법 둘째 칸부터 다시 겹쳤다: 74·75 bait 동일, 테스트로 잡음)
    start = zlib.crc32(("%s|%s" % (_seed_int(seed), (spine or {}).get("id") or 0)).encode("utf-8"))
    base, radix = {}, 1
    for r, _ in plan:
        if r in base:
            continue
        n = len(tpl.get(r) or [])
        if n:
            base[r] = (start // radix) % n
            radix *= n
    out, used = [], {}
    for r, _ in plan:
        cands = list(tpl.get(r) or [])
        if not cands:
            out.append(""); continue
        i = base.get(r, 0) + used.get(r, 0); used[r] = used.get(r, 0) + 1
        out.append(cands[i % len(cands)])
    return out


def plan_for_repair(groups_out, roles, tpl, seed, spine=None):
    """줄 번호 → 그 줄에 쓰인 문장틀(다시 쓸 때 같은 틀을 준다). 시작점은 `_spine_prompt`와 **같은 규칙**."""
    plan = _spine_plan(roles, tpl, len(groups_out["order"]))
    return _pick_templates(plan, tpl, seed, spine)


_ONE_LINE_SCHEMA = {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}


def _repair_joins(lines, templates, note=None):
    for i, L in enumerate(lines):
        t = _fix_join(L["text"])
        if _bad_join(t):
            tpl = templates[i] if i < len(templates) else ""
            prompt = (f"아래 문장은 문장틀 「{tpl}」의 빈칸을 채운 것인데 어미가 겹쳐 틀렸다.\n"
                      f"틀린 문장: {t}\n"
                      "틀의 끝말은 그대로 두고 빈칸 부분만 어간으로 고쳐 자연스러운 한 문장으로 다시 써라. "
                      "뜻·길이는 유지하고 새 내용을 넣지 마라. 마침표 하나로 끝내라.")
            out = _sg._call_json(prompt, _ONE_LINE_SCHEMA, note=note) or {}
            t2 = _fix_join(re.sub(r"\s+", " ", str(out.get("text") or "")).strip())
            if t2 and not _bad_join(t2):
                t = t2.rstrip(".!?。") + "."
        L["text"] = t
    return lines

# ── 컷 지정 (코드 — 부탁하지 않는다) ──────────────────────────────────
def assign_cuts(lines, groups_out, seg_index, backbone_vid):
    """줄마다 컷을 **길이가 대사를 넘을 때까지** 붙인다. 서브 우선, 원본은 폴백. 이미 쓴 컷은 안 쓴다.
    훅·CTA(group=-1)는 order 밖의 '휴대/외관' 류 서브 컷 → 없으면 아무 미사용 서브 컷."""
    used = set()

    def _cands(sids):
        out = [s for s in sids if s in seg_index and s not in used and seg_index[s]["secs"] >= MIN_CUT_SECS]
        sub = [s for s in out if seg_index[s]["vid"] != backbone_vid]
        org = [s for s in out if seg_index[s]["vid"] == backbone_vid]
        return sub + org      # 서브 먼저

    def _fill(sids, need):
        """길이가 대사를 넘을 때까지 + **컷 수가 최소 개수를 넘을 때까지** 붙인다.
        ★길이만 보면 6.3초짜리 컷 하나로 3.5초 대사가 끝나 화면이 안 바뀐다(밋밋).
          렌더 라운드로빈은 컷이 2개 이상일 때만 돌아 2.2초씩 번갈아 보여준다."""
        want = MIN_CUTS_PER_LINE if need > TARGET_CUT_SECS else 1
        picked, have = [], 0.0
        for s in _cands(sids):
            picked.append(s); used.add(s); have += seg_index[s]["secs"]
            if have >= need + SLACK_SECS and len(picked) >= want:
                break
        return picked, have

    all_sub = [s for s, v in seg_index.items() if v["vid"] != backbone_vid]
    order = groups_out.get("order") or []
    in_group = {c for g in groups_out["groups"] for c in (g.get("cuts") or [])}
    # 구조 줄(정체·떼돈·이건 바로·한계·마무리)용 후보: 어느 특징에도 안 들어간 컷 중 '제품 전체·외관'을 먼저,
    # 그다음 나머지 미배정 컷, 마지막에야 특징 컷. ★특징 줄이 먼저 배정받는다(아래 순서) — 전엔 구조 줄이
    # 먼저 돌며 첫 묶음(박스 열기) 컷 7개를 다 먹어 정작 "패키지·구성품" 줄엔 거리 풍경만 남았다(job bb4c2734ce80).
    def _looks_whole(s):
        d = str(seg_index[s].get("desc") or "")
        return any(k in d for k in ("전체", "외관", "정면", "형태", "들어 올", "손에", "제품을 보여", "옆면", "뒷면", "마감", "돌려가며", "박스"))
    def _is_person(s):
        d = str(seg_index[s].get("desc") or "")
        return any(k in d for k in ("남성", "여성", "사람", "얼굴", "댓글", "구매처", "언급", "말하", "인사"))
    free = [s for s in all_sub if s not in in_group]
    # ★구조 줄 몫 예약(2026-09-17, job bb50a7ba99ba 실측): 특징 줄이 '제품 전체·외관' 컷까지 다 쓰면
    #   정체·떼돈 줄엔 거리 풍경·샘플 사진만 남는다. 구조 줄 수만큼 외관 컷을 먼저 떼어 두고,
    #   특징 줄은 그 묶음에 다른 컷이 없을 때만 예약 컷을 쓴다.
    n_struct = sum(1 for L in lines if not (L.get("group") is not None and 0 <= L.get("group") < len(groups_out["groups"])))
    whole_all = [s for s in all_sub if _looks_whole(s) and not _is_person(s) and seg_index[s]["secs"] >= MIN_CUT_SECS]
    reserved = whole_all[:max(0, n_struct * MIN_CUTS_PER_LINE)]   # 줄당 2컷 규칙만큼(실측: 5컷은 3줄에서 동났다, job bb5c64454fd7)

    def _is_problem(s):
        """1단계 태그 역할이 '문제/before' = 불편·기존 방식 장면. 공개("이건 바로 X")·훅·마무리에 붙으면 딴 그림이다
        (2026-09-22 사장님 화면: 공개 줄에 '일회용 청소포 뽑는 모습'). 설명문 낱말(_looks_whole)이 하나도 안 걸리는
        재료에선 종전 순서가 '남은 아무 컷'으로 떨어져 문제 컷이 갔다 — 태그로 가른다."""
        return str(seg_index[s].get("role") or "") in ("문제", "before")

    def _structural_pool(line_role=""):
        """특징 줄이 다 가져간 **뒤**에 부른다. ① 특징 묶음에서 남은 컷(=제품 컷) ② 묶음 밖 '전체' 컷
        ③ 묶음 밖 나머지 ④ 사람·댓글 컷은 맨 뒤. 실측(job bba6caa3ee81): 묶음 밖 컷은 곧 찌꺼기
        (남의 채널 CTA 자막·얼굴)라 정체·떼돈 줄이 전부 그걸 받았다.
        ★역할로 가른다(2026-09-22): 미끼(불편·기존 방식 자리)는 문제/before 컷을 **먼저**, 그 밖의 구조 줄(훅·공개·마무리)은
          문제/before 컷을 **맨 뒤**(사람 컷 바로 앞)로. 히트작 훅·공개는 제품이 보이는 컷이다."""
        left = [s for s in all_sub if s in in_group and s not in used and s not in reserved]
        rest = [s for s in free if not _is_person(s) and s not in reserved]
        prob = [s for s in rest + left if _is_problem(s)]
        rest = [s for s in rest if not _is_problem(s)]
        left = [s for s in left if not _is_problem(s)]
        base = (list(reserved) + [s for s in rest if _looks_whole(s)] + left + [s for s in rest if not _looks_whole(s)])
        if str(line_role or "").startswith("미끼"):
            return prob + base + [s for s in free if _is_person(s)]
        return base + prob + [s for s in free if _is_person(s)]
    beat_sources, report = [None] * len(lines), [None] * len(lines)
    feature_first = sorted(range(len(lines)), key=lambda i: 0 if 0 <= (lines[i].get("group") if lines[i].get("group") is not None else -1) < len(groups_out["groups"]) else 1)
    for li in feature_first:
        L = lines[li]
        need = _secs(L["text"])
        gi = L.get("group", -1)
        if gi is not None and 0 <= gi < len(groups_out["groups"]):
            gc = list(groups_out["groups"][gi].get("cuts") or [])
            sids = [c for c in gc if c not in reserved] + [c for c in gc if c in reserved]
        else:
            sids = _structural_pool(L.get("role"))
        picked, have = _fill(sids, need)
        # ★모자라면 서브에서 보충 — 짧은 컷(<MIN_CUT_SECS)을 거르고 나면 그룹 컷만으론 부족할 때가 있다
        #   (실측 1회차: 펜촉 줄 화면 2.6s < 대사 4.9s). 안 채우면 3단계 채우기가 대본 안 보고 메운다.
        if have < need + SLACK_SECS:
            more, more_have = _fill(free + all_sub, need - have)   # 특징 밖 컷부터(남의 특징 컷을 뺏지 않게)
            picked += more; have += more_have
        # ★길이는 찼는데 **컷이 1개뿐**이면 한 장 더 붙인다(2026-09-17). 위 보충은 길이가 모자랄
        #   때만 돌아서, 6.3초짜리 한 컷이 3.5초 대사를 덮으면 그대로 1컷으로 끝났다 = 밋밋.
        #   렌더 라운드로빈은 컷 2개 이상에서만 작동하므로 여기서 개수를 채워야 한다.
        if len(picked) < MIN_CUTS_PER_LINE and need > TARGET_CUT_SECS:
            more, more_have = _fill(free + all_sub, 0.0)  # 0.0 = 개수만 채운다(길이는 이미 찼다)
            picked += more; have += more_have
        if not picked:                                   # 그래도 없으면 원본 아무 컷
            picked, have = _fill(list(seg_index), need)
        beat_sources[li] = {"role": L["role"], "seg": picked[0] if picked else "", "segs": picked}
        report[li] = {"text": L["text"], "need": round(need, 1), "have": round(have, 1),
                      "cuts": picked, "from_sub": all(seg_index[s]["vid"] != backbone_vid for s in picked)}
    return beat_sources, report


def _shuffle_middle(order, seed):
    """특징 순서 바꾸기(사장님 구조 ②, 2026-09-18) — **첫 특징(소개)과 마지막(마무리)은 두고 가운데만** seed로 섞는다.
    ★머리말엔 '순서 섞기'라 적어 놓고 build_groups는 '원본 순서를 지켜라'였다 → 원본과 같은 순서로 나왔다(자가점검으로 발견).
      통째로 섞으면 '개봉 → 사용' 같은 흐름이 깨질 수 있어 양 끝은 고정한다. 회원마다(seed) 다른 순서."""
    order = list(order or [])
    if len(order) <= 3:
        return order
    mid = order[1:-1]
    rnd = random.Random(_seed_int(seed) ^ 0x5EED)
    for _ in range(3):                     # 원본 순서 그대로 나오면 다시 섞는다(가운데 2개 이상일 때)
        rnd.shuffle(mid)
        if mid != order[1:-1]:
            break
    return [order[0]] + mid + [order[-1]]


# ── 한 번에 ───────────────────────────────────────────────────────────
def assemble(sources, backbone_vid, store, spine_id=None, target_seconds=25, seed=None, note=None, style=None,
             seed_src=None, use_seed_origin=False):
    """(given_script, beat_sources, meta). 실패하면 (None, None, meta) — 조용히 폴백하지 않는다.

    ★대본은 씨앗을 쓰고 **화면은 씨앗 영상을 안 쓴다**(2026-09-21 사장님). 씨앗은 남의 히트작이라
      그 화면을 그대로 깔면 우리 영상이 아니게 된다. 실측(work 7f7d2393eb0b): 주컷 5/7·대안 69.6%가
      씨앗 컷이었고 재료 7편 중 4편은 한 컷도 안 쓰였다. 말투·골격·소재는 씨앗이, 그림은 재료가 준다.
    """
    note = note if note is not None else {}
    vis_sources = _drop_seed(sources, seed_src, note=note)
    if backbone_vid not in {s_.get("video_id") for s_ in vis_sources} and vis_sources:
        backbone_vid = max(vis_sources, key=lambda x: len(x.get("segments") or [])).get("video_id")
        note["backbone_moved"] = backbone_vid      # 씨앗이 백본이었으면 재료 중 하나로 옮긴다
    seg_index = _seg_index(vis_sources)
    groups_out = build_groups(vis_sources, backbone_vid, note=note)
    # ★모델 혼잡(503)은 잠깐 뒤 다시 하면 된다 — 전엔 0.7초 만에 포기해 대본 0개(09-18 실측 42건 중 2건 전부 503).
    #   혼잡일 때만 다시 한다. 다른 이유로 비면(재료 문제) 바로 실패로 둔다.
    for wait in (4, 10):
        if groups_out["groups"] or not re.search(r"503|UNAVAILABLE|overloaded|high demand", str(note.get("detail") or ""), re.I):
            break
        time.sleep(wait)
        note.pop("detail", None)
        groups_out = build_groups(sources, backbone_vid, note=note)
    if not groups_out["groups"]:
        note["reason"] = "groups_empty"
        return None, None, {"note": note}
    groups_out = dict(groups_out, order=_shuffle_middle(groups_out["order"], seed))
    spine = pick_hook_spine(store, spine_id=spine_id, seed=seed, style=style)
    # ★오용형은 재료에 '딴 용도' 장면이 있을 때만(2026-09-18 사장님 결정). 볼펜·후드집업처럼 없으면
    #   "고수들은 카드 지갑 비상 필기구 만들어 버림" 같은 억지 용도를 지어낸다(실측 batch 7편 중 3편).
    #   없으면 같은 seed로 제품정체형을 고른다 — 조용히 바꾸지 않고 note에 남긴다.
    if MISUSE_STYLE in (spine.get("fit_categories") or []) and not groups_out.get("alt_use"):
        note["style_switched"] = {"from": spine.get("name"), "why": "재료에 딴 용도 장면 없음"}
        spine = pick_hook_spine(store, seed=seed, style=MISUSE_FALLBACK_STYLE)
        note["style_switched"]["to"] = spine.get("name")
    lines = write_lines(groups_out, spine, seg_index, target_seconds, note=note, seed=seed, seed_src=seed_src,
                        use_seed_origin=use_seed_origin)
    if len(lines) < 3:
        note["reason"] = "lines_short"
        return None, None, {"note": note, "groups": groups_out}
    beat_sources, report = assign_cuts(lines, groups_out, seg_index, backbone_vid)
    given = "\n".join(L["text"] for L in lines)
    # 씨앗을 뼈대로 썼으면 이름도 그렇게 말한다 — 유형을 고르느라 집은 스파인 이름("히트작 발명품형…")이
    #   뜨면 그 스파인 틀로 만든 줄 안다(2026-09-21 사장님 화면 확인).
    _sp_name = "씨앗 그대로" if note.get("origin_from_seed") else spine.get("name")
    meta = {"product": groups_out["product"], "spine": {"id": spine.get("id"), "name": _sp_name},
            "groups": groups_out, "report": report, "note": note}
    return given, beat_sources, meta


def to_draft(given, beat_sources, meta):
    """assemble 결과 → 2단계 초안 모양(script_generate.generate_by_styles와 같은 키).
    화면(produce.html s2Confirm)은 beats[].text를 줄로, beats[].src_seg/src_segs를 3단계 장면으로 넘긴다
    — 그래서 화면·3단계는 한 글자도 안 고친다(새 통로를 만들지 않는다)."""
    from shopping_shorts import script_gate
    lines = [l for l in (given or "").split("\n") if l.strip()]
    beats = []
    for i, t in enumerate(lines):
        b = (beat_sources[i] if i < len(beat_sources or []) else {}) or {}
        segs = [x for x in (b.get("segs") or []) if x]
        beats.append({"role": b.get("role") or "", "text": t, "src_seg": b.get("seg") or (segs[0] if segs else ""),
                      "src_segs": segs, "sec": script_gate.est_seconds(t)})
    full = " ".join(lines)
    sp = (meta or {}).get("spine") or {}
    return {"style_id": sp.get("id"), "style_name": sp.get("name"), "beats": beats, "script": full,
            "hook": lines[0] if lines else "", "checks": [], "passed": True, "tries": 1,
            "chars": len(script_gate.norm(full)), "sec": script_gate.est_seconds(full),
            "made_by": "백본", "style_switched": ((meta or {}).get("note") or {}).get("style_switched")}


def sources_from_extract(extract):
    """mix_jobs.extract_json({sN:{...}}) → sources 리스트(video_id 보장)."""
    out = []
    for k in sorted(extract or {}):
        v = extract[k]
        if not isinstance(v, dict):
            continue
        s = dict(v)
        segs = s.get("segments") or []
        s["video_id"] = s.get("video_id") or (_vid_of(segs[0]["seg_id"]) if segs else k)
        out.append(s)
    return out


if __name__ == "__main__":       # 서버에서: python3 -m shopping_shorts.backbone_assemble <base_job> <backbone_vid> [spine_id]
    from shopping_shorts.store import Store
    db = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
    base, bb = sys.argv[1], sys.argv[2]
    sid = int(sys.argv[3]) if len(sys.argv) > 3 else None
    st = Store(db)
    job = st.get_mix_job(base)
    sources = sources_from_extract(job.get("extract") or {})
    given, bs, meta = assemble(sources, bb, st, spine_id=sid)
    print(json.dumps({"given_script": given, "beat_sources": bs, "meta": meta}, ensure_ascii=False, indent=1))

def assemble_clean(sources, backbone_vid, store, spines, target_seconds=25, seed=None, want=2, note=None,
                   seed_src=None):
    """스파인 여러 개를 돌려 **인물·상황 검사를 통과한 대본만** 돌려준다 (2026-09-20 사장님 확정 B안).

    대본 한 편을 규칙으로 완벽하게 만들려 하면 규칙만 늘어난다(09-19~20 실측). 대신 여러 편 뽑아
    멀쩡한 것만 화면에 올린다. 통과본이 하나도 없으면 빈 목록 — 화면은 "이 영상엔 맞는 스타일이 없다"고 말한다.
    반환: [{spine, given, beat_sources, meta}] (최대 want개, 앞에서부터 통과 순)
    """
    out, tried = [], []
    for sp in (spines or []):
        n = {}
        try:
            given, bs, meta = assemble(sources, backbone_vid, store, spine_id=sp.get("id"),
                                       target_seconds=target_seconds, seed="%s-%s" % (seed or "", sp.get("id")),
                                       note=n, seed_src=seed_src,
                                       use_seed_origin=bool(sp.get("_use_seed_origin")))
        except Exception as e:      # noqa: BLE001 — 한 스파인 실패가 나머지를 막으면 안 된다
            tried.append({"spine": sp.get("name"), "why": repr(e)[:80]})
            continue
        issues = ((n.get("cast") or {}).get("issues")) or []
        if not given:
            tried.append({"spine": sp.get("name"), "why": n.get("cast_unfit") or n.get("reason") or "대본 없음"})
            continue
        if issues:
            tried.append({"spine": sp.get("name"), "why": "; ".join(issues)[:120]})
            continue
        out.append({"spine": sp, "given": given, "beat_sources": bs, "meta": meta})
        if len(out) >= want:
            break
    if note is not None:
        note["skipped"] = tried          # 왜 안 썼는지 화면이 말할 수 있게(조용한 폴백 금지)
    return out


_TYPES = ["오용형", "제품정체형", "발명품형", "지인증언형", "권유지시형", "물건발견형", "금지경고형", "사회증거형",
          "정체의문형", "무지후회형", "목격담형", "가성비형", "만능템형", "다이소지목형", "내자랑형"]
_SEEDT_SCHEMA = {"type": "object", "properties": {"type": {"type": "string"}, "why": {"type": "string"}},
                 "required": ["type"]}


def seed_type(sources, backbone_main=None, note=None):
    """씨앗 영상이 이미 어떤 유형으로 찍혔는지 판정한다 — "이 영상에 딱 맞는 스타일"의 근거(2026-09-19 사장님).
    씨앗 유형을 따르면 재료와 대본이 어긋나지 않는다(오용형은 딴 용도 장면이 이미 있다)."""
    if not sources:
        return ""
    seed = seed_source(sources, backbone_main)
    text = (seed.get("full_text_ko") or seed.get("full_text") or "").strip()
    if len(text) < 60:
        return ""
    out = _sg._call_json(
        "아래는 쇼핑 숏폼 대본이다. 첫 문장이 **어떻게 여는가**로 유형을 하나 고르고 why 한 줄.\n유형: %s\n\n%s"
        % (", ".join(_TYPES), text[:900]), _SEEDT_SCHEMA, note=note) or {}
    t = str(out.get("type") or "").strip()
    return t if t in _TYPES else ""


def origin_spines(store, typ, limit=6):
    """그 유형의 **원문형 스파인**(히트작 원문을 담은 것). 없으면 빈 목록 → 호출부가 옛 경로로 간다."""
    out = []
    for st in ("approved", "pending"):          # 승인된 것 먼저, 아직 검수 중인 것 나중
        for sp in (store.list_spines(status=st) or []):
            if not spine_origin(sp):
                continue
            if typ and typ not in (sp.get("fit_categories") or json.loads(sp.get("fit_categories_json") or "[]")):
                continue
            out.append(sp)
    return out[:limit]
