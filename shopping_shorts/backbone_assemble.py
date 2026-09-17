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
        "5) product: 제품 이름 한 줄.\n"
        "★컷 번호는 목록에 있는 것만. 지어내지 마라.\n\n" + blocks)
    out = _sg._call_json(prompt, _GROUP_SCHEMA, note=note) or {}
    groups = [g for g in (out.get("groups") or []) if isinstance(g, dict)]
    order = [i for i in (out.get("order") or []) if isinstance(i, int) and 0 <= i < len(groups)]
    if not order:
        order = [i for i, g in enumerate(groups) if not g.get("doubt")]
    return {"product": out.get("product") or "", "groups": groups, "order": order[:MAX_GROUPS]}


# ── 훅 고르기 ─────────────────────────────────────────────────────────
def pick_hook_spine(store, spine_id=None, seed=None):
    """승인 스파인 중 훅 규칙(hook_3s)이 있는 것. 지정 없으면 무작위 — 같은 재료로 여러 편이 나오게."""
    spines = [s for s in store.list_spines(status="approved") if s.get("hook_3s")]
    if spine_id is not None:
        for s in spines:
            if s.get("id") == spine_id:
                return s
    if not spines:
        spines = store.list_spines(status="approved")
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


def write_lines(groups_out, hook_spine, seg_index, target_seconds=25, note=None):
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
        prompt = _spine_prompt(groups_out, hook_spine, roles, tpl, feats, per_line)
        return _clean_lines(_sg._call_json(prompt, _LINES_SCHEMA, note=note) or {})
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


def _feature_roles(roles, tpl):
    """{효능…} 자리가 있는 역할 = 특징 하나를 말하는 줄. 나머지는 구조 줄(정체 숨기기·공개·마무리)."""
    return [r for r in roles if any("{효능" in t for t in (tpl.get(r) or []))]


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


def _spine_prompt(groups_out, spine, roles, tpl, feats, per_line):
    plan = _spine_plan(roles, tpl, len(groups_out["order"]))
    lines_spec = []
    order = groups_out.get("order") or []
    for k, (r, gi) in enumerate(plan):
        ex = " / ".join((tpl.get(r) or [])[:3])
        # ★group은 묶음 **원번호**(assign_cuts가 groups[gi]로 찾는다) — 순서 번호를 주면 다른 묶음 컷이 붙는다
        tgt = f"group={order[gi]} (특징 {gi + 1}번)" if 0 <= gi < len(order) else "group=-1"
        lines_spec.append(f"  {k + 1}. role={r}, {tgt} — 문장틀 예: {ex}")
    return (
        f"제품: {groups_out.get('product')}\n"
        f"대본 스타일: 「{spine.get('name')}」 — {spine.get('situation_type') or ''}\n"
        f"감정선: {spine.get('emotion_arc') or ''}\n\n"
        "특징(화면은 이미 정해져 있다 — 그 화면에서 보이는 것만 말해라):\n" + "\n".join(feats) + "\n\n"
        f"아래 줄을 **이 순서·이 역할 그대로** {len(plan)}줄 써라. 각 줄은 문장틀 예 중 하나를 골라 {{…}} 자리만 제품에 맞게 채운다.\n"
        + "\n".join(lines_spec) + "\n\n"
        "규칙:\n"
        "- 줄 수·순서·role·group을 바꾸지 마라. 줄을 합치거나 빼지 마라.\n"
        f"- 한 줄은 **마침표 하나**로 끝나는 문장 하나. 쉼표는 써도 된다. 줄당 {per_line}자 안팎.\n"
        "- 문장틀의 말투(반말·'~다는데'·'~라고')를 유지해라. 댓글 유도·구독 요청 같은 CTA를 덧붙이지 마라.\n"
        "- {나라}는 화면·자막에서 알 수 없으면 '해외'로. 화면에 없는 기능·수치를 지어내지 마라.\n"
        "- 원본 영상의 문장을 그대로 베끼지 마라.")


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
    reserved = whole_all[:max(0, n_struct)]

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
def assemble(sources, backbone_vid, store, spine_id=None, target_seconds=25, seed=None, note=None):
    """(given_script, beat_sources, meta). 실패하면 (None, None, meta) — 조용히 폴백하지 않는다."""
    note = note if note is not None else {}
    seg_index = _seg_index(sources)
    groups_out = build_groups(sources, backbone_vid, note=note)
    if not groups_out["groups"]:
        note["reason"] = "groups_empty"
        return None, None, {"note": note}
    spine = pick_hook_spine(store, spine_id=spine_id, seed=seed)
    lines = write_lines(groups_out, spine, seg_index, target_seconds, note=note)
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
