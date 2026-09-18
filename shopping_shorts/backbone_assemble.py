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

from shopping_shorts import script_generate as _sg

# ── 규칙(한 곳에서만 정한다) ─────────────────────────────────────────
MAX_GROUPS = 7          # 훅·CTA 제외 특징 수 상한 — 25초에 7개면 줄당 2.5초
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
                             "key": bool(x.get("is_key")), "vid": _vid_of(sid),
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
    },
    "required": ["product", "groups", "order"],
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
        lines.append(f"  [{x.get('seg_id')}] ({secs:.1f}s) 화면:{(x.get('scene_desc') or '')[:70]}"
                     + (f" | 말:{say}" if say else "")
                     + (f" | 변화:{(x.get('change') or '')[:40]}" if x.get("change") else ""))
    return "\n".join(lines)


def build_groups(sources, backbone_vid, note=None):
    """특징을 같은 얘기끼리 묶고 컷을 붙인다. 원본 흐름 순서 + 서브 새 특징 삽입 위치까지."""
    blocks = "\n\n".join(_source_block(s, s.get("video_id") == backbone_vid) for s in sources)
    prompt = (
        "아래는 같은 제품을 찍은 영상 여러 편의 태깅이다. 원본(백본) 1편과 서브 여러 편.\n"
        "할 일:\n"
        "1) 모든 영상의 '특징'과 컷 화면을 보고, **같은 얘기끼리 한 묶음**으로 묶어라(예: '54개 부품'·'정밀 설계'·'정교한 결합'은 한 묶음). "
        f"묶음은 **최소 5개, 최대 {MAX_GROUPS}개** — 너무 뭉치지 마라. 크기/휴대 · 변신 · 부품/정밀 · 결합 원리 · 실제 사용(필기 등) · 소재/마감 · "
        "휴대 실증(지갑 등) · 보관(거치대 등) · 개봉 처럼 **보여주는 동작이 다르면 다른 묶음**이다. "
        "각 묶음에 이름·한 줄 주장(claim)·그 특징이 **화면에 실제로 보이는 컷 번호들**을 붙여라. "
        "★서브 영상에 같은 동작 컷이 있으면 **반드시 서브 컷도 함께** 넣어라(원본 컷만 넣지 마라).\n"
        "2) where: 그 특징이 원본에 있으면 '원본', 서브에만 있으면 '서브', 둘 다면 '둘다'.\n"
        "3) doubt: 서브가 **다른 제품**으로 보이거나(예: 원본은 볼펜인데 버튼 피젯), 원본에 없는 기능을 말하면 true. "
        "화면은 같은 동작이라도 말이 다르면 true.\n"
        "4) order: 묶음 인덱스(0부터)를 **영상에 나올 순서**로. 원본의 논리 순서(소개→변신→증명→원리)를 지키되, "
        "서브에만 있는 특징(휴대·개봉·보관 등)은 자연스러운 자리에 끼워라. doubt=true 묶음은 order에서 빼라.\n"
        "5) product: 제품 이름 한 줄 — **한국어로**(영문 제품명은 뜻을 옮기고 브랜드만 영문. 예: 'NORDECO 빈티지 미니 카메라').\n"
        "★컷 번호는 목록에 있는 것만. 지어내지 마라.\n\n" + blocks)
    out = _sg._call_json(prompt, _GROUP_SCHEMA, note=note) or {}
    groups = [g for g in (out.get("groups") or []) if isinstance(g, dict)]
    order = [i for i in (out.get("order") or []) if isinstance(i, int) and 0 <= i < len(groups)]
    if not order:
        order = [i for i, g in enumerate(groups) if not g.get("doubt")]
    return {"product": out.get("product") or "", "groups": groups, "order": order[:MAX_GROUPS]}


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
    all_sp = store.list_spines(status="approved")
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


def write_lines(groups_out, hook_spine, seg_index, target_seconds=25, note=None, seed=None):
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
    roles, tpl = _spine_style(hook_spine)
    if roles and tpl:
        # ★스파인에 문장틀(templates)·역할순서(beat_roles)가 있으면 **그 꼴 그대로** 쓴다(2026-09-17 사장님:
        #   "이븐쇼핑 스타일" = 천재·떼돈·「이건 바로 OO」·CTA 없음). 전엔 훅 한 줄만 빌리고 나머지는
        #   자체 [훅]+[특징]+[댓글CTA]로 써서 스타일이 통째로 사라졌다.
        n_lines = len(roles) + max(0, len(groups_out["order"]) - len(_feature_roles(roles, tpl)))
        per_line = max(12, int(target_seconds * cps / max(1, n_lines)))
        # ★seed를 그대로 넘긴다 — 안 넘기면 늘 0이라 **매번 첫 틀만** 쓰여 틀을 6개 만들어도
        #   같은 대본이 나온다(2026-09-18 실측으로 잡은 배선 누락). seed가 바뀌면 칸마다
        #   다음 틀로 돌아 같은 재료에서 N가지 대본이 나온다.
        prompt = _spine_prompt(groups_out, hook_spine, roles, tpl, feats, per_line, seed=seed)
        lines = _clean_lines(_sg._call_json(prompt, _LINES_SCHEMA, note=note) or {})
        return _repair_joins(lines, plan_for_repair(groups_out, roles, tpl, seed, hook_spine), note=note)
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


def _clean_lines(out):
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
        t = t.rstrip(".!?。") .replace(". ", ", ").replace("!", ",").replace("?", ",") + "."
        lines.append({"role": str(L.get("role") or "feature"), "text": t, "group": int(L.get("group", -1))})
    return lines


# ── 스파인 문장틀 그대로 쓰기 ─────────────────────────────────────────
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


def _feature_roles(roles, tpl):
    """{효능…}·{용도…} 자리가 있는 역할 = 특징 하나를 말하는 줄. 나머지는 구조 줄(정체 숨기기·공개·마무리)."""
    return [r for r in roles if any(("{효능" in t or "{용도" in t) for t in (tpl.get(r) or []))]


def _spine_plan(roles, tpl, n_feat):
    """[(role, group)] — 구조 줄은 group=-1, 특징 줄은 order 번호. 특징이 효능 자리보다 많으면
    두 번째 효능 역할(more 류)을 마지막 효능 역할(twist) 앞에 반복해 늘린다. 적으면 남는 자리는 뺀다."""
    feat_roles = _feature_roles(roles, tpl)
    plan, used = [], 0
    for r in roles:
        if r in feat_roles:
            if used < n_feat:
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

    def _structural_pool():
        """특징 줄이 다 가져간 **뒤**에 부른다. ① 특징 묶음에서 남은 컷(=제품 컷) ② 묶음 밖 '전체' 컷
        ③ 묶음 밖 나머지 ④ 사람·댓글 컷은 맨 뒤. 실측(job bba6caa3ee81): 묶음 밖 컷은 곧 찌꺼기
        (남의 채널 CTA 자막·얼굴)라 정체·떼돈 줄이 전부 그걸 받았다."""
        left = [s for s in all_sub if s in in_group and s not in used and s not in reserved]
        rest = [s for s in free if not _is_person(s) and s not in reserved]
        return (list(reserved) + [s for s in rest if _looks_whole(s)] + left + [s for s in rest if not _looks_whole(s)]
                + [s for s in free if _is_person(s)])
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
            sids = _structural_pool()
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


# ── 한 번에 ───────────────────────────────────────────────────────────
def assemble(sources, backbone_vid, store, spine_id=None, target_seconds=25, seed=None, note=None, style=None):
    """(given_script, beat_sources, meta). 실패하면 (None, None, meta) — 조용히 폴백하지 않는다."""
    note = note if note is not None else {}
    seg_index = _seg_index(sources)
    groups_out = build_groups(sources, backbone_vid, note=note)
    if not groups_out["groups"]:
        note["reason"] = "groups_empty"
        return None, None, {"note": note}
    spine = pick_hook_spine(store, spine_id=spine_id, seed=seed, style=style)
    lines = write_lines(groups_out, spine, seg_index, target_seconds, note=note, seed=seed)
    if len(lines) < 3:
        note["reason"] = "lines_short"
        return None, None, {"note": note, "groups": groups_out}
    beat_sources, report = assign_cuts(lines, groups_out, seg_index, backbone_vid)
    given = "\n".join(L["text"] for L in lines)
    meta = {"product": groups_out["product"], "spine": {"id": spine.get("id"), "name": spine.get("name")},
            "groups": groups_out, "report": report, "note": note}
    return given, beat_sources, meta


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
