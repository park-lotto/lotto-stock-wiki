"""대본 비트 ↔ 라이브러리 자산 매칭(순수함수).

1차 필터(무료·기계적): asset_type=clip 且 source_origin ∈ {짜집기,촬영원본}.
  (비트에 category가 없으므로 category 축은 안 쓴다 — 설계 §9 해소.)
2차 판정(Gemini _vault_call 캐스케이드): 비트 나레이션 + 후보 다축 태그 →
  {best_asset_id, score}. 점수 ≥ 임계 → 자동배치(cutaway), < 임계 → 제안만.

저신뢰 자동배치 금지: 오배치 손해가 비대칭(엉뚱한 짤이 라이브 영상에 박히는 것 >
짤 안 쓰는 것). 캐스케이드가 None(키 소진) → 조용한 실패(자동배치 없음, 예외 없음).
"""
import copy

from . import edit_plan
from .scene_assets import _ROLES   # 효과음 role 통제어휘(§3.2 방어적 재검증)

_ALLOWED_ORIGIN = ("짜집기", "촬영원본")

# 비트 역할 → 호환 자산 역할(순위). 결정적 — Gemini 안 씀(과배치 원천차단).
# 자산 역할 통제어휘: 훅·반전·CTA·비법공개·반응·전환·본문(scene_assets._ROLES).
_ROLE_FALLBACK = {
    "hook": ("훅", "반응"),                       # 시선 잡기: 귀여운 리액션·만족짤
    "problem": ("반전",),                          # 페인포인트: 눈물 양파·요리 실패
    "problem_solution": ("반전",),
    "info": ("비법공개", "전환"),                  # 레시피 본문(how-to): 만족 과정짤 (실 대본 grounding에서 추가)
    "easy_process": ("비법공개", "전환"),          # "이렇게 쉽게": 만족 슬라이스
    "process_step1": ("비법공개", "전환"),
    "process_step2": ("비법공개", "전환"),
    "process": ("비법공개", "전환"),
    "result_wow": ("반응", "본문"),                # 와우 모먼트: ASMR 먹방
    "benefit": ("반응", "본문"),
    "cta": ("CTA",),
}

_MATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "best_asset_id": {"type": "integer"},
        "score": {"type": "number"},
    },
    "required": ["best_asset_id", "score"],
}


# ── 1차 좁히기 (2026-09-08) ────────────────────────────────────────────
# 왜 필요한가 — **이 기능이 한 번 꺼진 이유가 이것이다.** mix_pipeline 주석:
#   "켜고 끄는 스위치가 없어 자산이 하나라도 등록돼 있으면 **모든 영상에 무조건**
#    적용됐다(당시 12개 등록). 사장님 지시('장면 라이브러리 없애, 안 쓰니까')"
# 실제로 서버에 남아 있는 12개는 튀김·삼겹살·서랍장·세탁기·감자튀김이다. 캠핑 의자
# 영상에 감자튀김 컷이 붙으면 시청자는 즉시 이상함을 느낀다.
#
# 그래서 Gemini에게 묻기 **전에** 말과 화면이 애초에 겹치는 후보만 남긴다.
#   · 비용 0·즉시(문자열 대조뿐) — 컷이 1만 개가 돼도 Gemini가 보는 후보는 일정하다
#   · 겹치는 게 하나도 없으면 **아무것도 안 붙인다**(그게 옛 사고의 처방이다)
_STOP = {"영상", "장면", "사람", "손", "화면", "모습", "하는", "있는", "것", "그것",
         "이것", "저것", "때", "안", "위", "아래", "옆", "앞", "뒤"}


def _tokens(text):
    """비교용 토큰 — 어간 2글자로 자른다.

    한국어는 조사·어미가 붙어 완전일치가 잘 안 된다("감자를"≠"감자"). 인스타 슬롯
    매칭에서 쓰던 것과 같은 기법이다(어간 2글자). 2글자면 과매칭이 걱정되지만,
    아래에서 **2개 이상 겹칠 때만** 통과시켜 우연을 거른다.
    """
    out = set()
    for raw in (text or "").replace(",", " ").split():
        w = "".join(ch for ch in raw if ch.isalnum())
        if len(w) < 2 or w in _STOP:
            continue
        out.add(w[:2] if len(w) > 2 else w)
    return out


def _asset_tokens(a):
    return _tokens(" ".join([
        a.get("subject") or "", a.get("scene_desc") or "",
        " ".join(a.get("keywords") or []), a.get("title") or "",
    ]))


def narrow(assets, plan, min_hits=2):
    """대본과 말이 겹치는 컷만 남긴다 — Gemini에 넘기기 전 무료 1차 필터.

    min_hits=2 — 1글자 어간이 우연히 겹치는 것을 거른다. 실측 없이 정한 값이라
    라이브에서 '붙어야 할 게 안 붙는다'가 나오면 1로 낮춰라(반대 방향 사고는
    '엉뚱한 게 붙는다'이고, 그쪽이 훨씬 나쁘다 — 그래서 보수적으로 시작한다).
    """
    beats = (plan or {}).get("beats") or []
    said = set()
    for b in beats:
        said |= _tokens(b.get("narration") or "")
    if not said:
        return []                      # 대본이 없으면 붙일 근거도 없다
    out = []
    for a in assets:
        if len(_asset_tokens(a) & said) >= min_hits:
            out.append(a)
    return out


def _candidates(assets):
    return [a for a in assets
            if a.get("asset_type") == "clip" and a.get("source_origin") in _ALLOWED_ORIGIN]


def _prompt(narration, cands):
    lines = [f"- id={a['id']}: 소재={a.get('subject')}, 장면={a.get('scene_desc')}, "
             f"키워드={','.join(a.get('keywords') or [])}" for a in cands]
    joined = "\n".join(lines)
    return (
        "너는 영상 편집자다. 아래 나레이션 위에 b-roll(컷어웨이)로 얹을 짤을 후보 중에서 고른다.\n"
        f"나레이션: \"{narration}\"\n"
        f"후보(각 짤이 화면에 실제로 보여주는 것):\n{joined}\n\n"
        "판정 규칙(엄격히):\n"
        "- 짤이 나레이션이 말하는 **바로 그 사물이나 동작을 실제로 화면에 보여줄 때만** 높은 점수를 준다.\n"
        "- '주제가 비슷하다', '분위기가 맞다', '요리다', '살림이다' 같은 느슨한 연상은 **오배치**다 — b-roll은 말과 화면이 어긋나면 시청자가 즉시 이상함을 느낀다.\n"
        "- 후보 중 나레이션의 구체적 소재를 실제로 보여주는 게 없으면, 가장 가까운 것을 고르되 **score를 0.3 이하**로 줘라. 억지로 고신뢰를 매기지 마라.\n"
        "- 예: 나레이션이 '마법 가루를 넣는다'인데 후보가 '채 썬 오이'뿐이면 → 오이는 마법 가루가 아니다 → score 0.1~0.2.\n"
        "  나레이션이 '감자를 썬다'인데 후보에 '채 썬 감자'가 있으면 → 화면과 말이 일치 → score 0.9.\n"
        "가장 가까운 후보의 id와, 위 규칙에 따른 정직한 적합도(0~1)를 반환하라. 애매하면 낮게."
    )


def match_scene_assets(plan, assets, *, threshold=0.9, vault_call=None):
    # 임계 0.9 — 실 재료 grounding(2026-07-18)에서 확정. 자산과 무관한 주제의 대본에
    # Gemini가 억지 매칭을 딱 0.80~0.85로 뱉는 걸 관측했다(프롬프트에 반례를 넣어도 살아남음).
    # 진짜 일치(화면과 말이 같음)는 0.9~0.95로 갈리므로, 0.9+만 자동배치하고 그 아래는 전부
    # 제안으로 돌린다 = '저신뢰 자동배치 금지'의 보수적 못박기. 오배치 손해가 비대칭(엉뚱한
    # 짤이 라이브 영상에 박히는 것 > 짤 안 쓰는 것)이라 이쪽이 안전하다. 최종 안전망=검수판(사람).
    vault_call = vault_call or edit_plan._vault_call
    plan = copy.deepcopy(plan)
    # ★Gemini에 묻기 전에 좁힌다(2026-09-08) — 아래 역할 패스도 같은 목록을 쓴다.
    #   좁힌 결과가 비면 cands가 비고, 소재 패스도 역할 패스도 아무것도 안 붙인다.
    cands = narrow(_candidates(assets), plan)
    by_id = {a["id"]: a for a in cands}
    suggestions = []
    if cands:
        for beat in plan["beats"]:
            res = vault_call(_prompt(beat["narration"], cands), _MATCH_SCHEMA)
            if not res:
                continue  # 키 소진 등 → 조용한 실패
            aid = res.get("best_asset_id")
            score = float(res.get("score") or 0.0)
            if aid not in by_id:
                continue  # 모델이 후보 밖 id를 뱉음 → 방어
            if score >= threshold:
                beat["cutaway"] = {"asset_id": aid, "score": score, "match_type": "subject"}
            else:
                suggestions.append({"beat_idx": beat["beat_idx"], "asset_id": aid, "score": score})
    _role_pass(plan, cands)
    plan["asset_suggestions"] = suggestions
    return plan


def _role_pass(plan, cands):
    """소재 패스가 못 채운 빈 비트에, 비트 역할에 맞는 요소짤을 결정적으로 배치한다.
    Gemini 안 씀 — 역할 호환표로만. plan을 제자리 수정. 한 영상 내 반복 금지."""
    used = {b["cutaway"]["asset_id"] for b in plan["beats"] if b.get("cutaway")}
    by_role = {}
    for a in cands:
        by_role.setdefault(a.get("role") or "", []).append(a)
    for beat in plan["beats"]:
        if beat.get("cutaway"):
            continue  # 소재 패스가 이미 배치 — 안 건드림
        compatible = _ROLE_FALLBACK.get(beat.get("role") or "")
        if not compatible:
            continue  # 이 비트 역할은 요소짤 자리가 아님 → 빈 채로
        pool = [a for role in compatible for a in by_role.get(role, [])
                if a["id"] not in used]
        if not pool:
            continue
        chosen = _pick_role_asset(pool, beat.get("narration") or "")
        beat["cutaway"] = {"asset_id": chosen["id"], "match_type": "role"}
        used.add(chosen["id"])


def _pick_role_asset(pool, narration):
    """역할 호환 후보 중 1개. 나레이션과 keyword/subject 겹치면 우선(Gemini 없음),
    없으면 결정적 순서(최근 담은 것 = id 큰 것 우선)."""
    def overlap(a):
        text = (a.get("subject") or "") + " " + " ".join(a.get("keywords") or [])
        return sum(1 for w in text.split() if w and w in narration)
    return sorted(pool, key=lambda a: (-overlap(a), -a["id"]))[0]


# ── 효과음(sfx) 역할 매칭 (스펙 §3) ─────────────────────────────
# 클립 역할패스(_role_pass)와 알고리즘이 거의 같으나 **중복 허용**(used 세트 없음)이 유일한 차이.
# 조건분기를 넣느니 짧은 함수로 분리한다(YAGNI·단순성, 스펙 §3.4).

# 타점 통제어휘 — 렌더(video_assemble._burn_captions)가 이 이름으로 실제 초를 계산한다.
# 여기와 렌더 둘 중 한쪽만 늘리면 조용히 기본값(last)으로 떨어진다(0순위-B).
SFX_POSITIONS = ("first", "last", "transition")

# ★효과음 한 발의 길이 상한(초) — 이보다 길면 컷을 덮는다.
#   이븐쇼핑류 실측: 중앙 80ms · 200ms 이하가 93%(channel/strategy/효과음_패턴분석.md, 441건).
#   상한을 200ms에 맞추면 뇌전구 팩에서 pop4·click·x_click·r3_click 4계열 25개가 남는다.
_SFX_MAX_SECS = 0.20

# ★타점 기본값 = **칸이 넘어가는 순간**(transition), 역할 무관 (2026-08-29).
#
# 종전엔 훅만 transition이고 나머지는 "last"(칸의 마지막 자막)였다. 실측해보니
# 대세 채널은 **역할을 가리지 않고 컷 경계에** 소리를 얹는다:
#
#   실측 3편 — 이븐쇼핑(영어더빙) 28.5s·긍정템 17.5s·공가미 19.6s
#     · 컷 55개 중 52개(95%)에 소리가 붙어 있다
#       (이븐쇼핑 25컷중 23 / 긍정템 21컷중 20 / 공가미 9컷중 9)
#     · 타점은 컷 경계 그 자리 — Δ중앙값 **-12ms**, 평균 +2ms.
#       컷보다 먼저 27개 / 나중 25개로 반반이라 "경계에 맞춘 것"이 분명하다.
#     · 소리 길이는 20~200ms(중앙값 ~50ms)로 짧다.
#   검출법: 8~16kHz 고역 전이(반짝·whoosh) + 20~120Hz 저역 임팩트(붐).
#          합성 정답파일로 먼저 검증하고 썼다(5/5 정확, 음성만인 파일엔 0건 오탐).
#
# 즉 "문장을 맺는 자리(last)"는 우리 추측이었고, 실제로는 **장면이 바뀌는 자리**다.
# last를 쓰려면 칸마다 손으로 바꾸면 된다(api_produce_mix_sfx가 그대로 받는다).
_SFX_POSITION = {}
_SFX_POSITION_DEFAULT = "transition"


def _sfx_position(beat_role):
    """이 역할의 **기본** 타점 이름. 사람이 칸마다 바꿀 수 있다(api_produce_mix_sfx).
    실제 몇 초인지는 렌더(_burn_captions)가 계산한다 — 여기선 위치 이름만."""
    return _SFX_POSITION.get(beat_role, _SFX_POSITION_DEFAULT)


def _sfx_candidates(assets):
    """효과음 후보 = asset_type이 sfx이고 role이 통제어휘(scene_assets._ROLES) 안인 것.
    표절 게이트(source_origin)는 적용 안 함 — 소리 파일이라 검사 대상이 다름(§3.2)."""
    return [a for a in assets
            if a.get("asset_type") == "sfx" and a.get("role") in _ROLES]


# ★벤치마크 순환 공식 — 추측이 아니라 **실측된 것**을 그대로 옮긴다.
#   (channel/volcano/뇌전구_역분석_8편_2026-09-12.md: "32컷 전 구간 5편 완전 동일(접미사까지,
#    전편 3편 포함 8/8). 4칸 틀 × 계열별 주기". ⚠"12주기 반복"이 아니다 — 13번째가 r3_click이다.)
#     i%4==0 → pop4                                         ← ★첫 컷(훅)은 항상 이것
#     i%4==1 → click, r3_click, x_click, r3_click, x_click  (주기 5)
#     i%4==2 → boing, hit, r3_hit                           (주기 3)
#     i%4==3 → ding, r3_ding, x_ding                        (주기 3)
#   ⚠️2·3번 자리(boing·hit·ding류)는 우리 실측에서 600~1500ms로 길어 컷을 덮는다.
#     쇼핑 숏폼(컷 1.7초)엔 안 맞아 _SFX_MAX_SECS로 걸러진다 → 그 자리는 남은 짧은 계열이 채운다.
_CYCLE_SLOTS = (
    ("pop4",),
    ("click", "r3_click", "x_click", "r3_click", "x_click"),
    ("boing", "hit", "r3_hit"),
    ("ding", "r3_ding", "x_ding"),
)


def _has_pack(cands):
    """벤치마크 팩이 깔려 있나 — 그 경우에만 공식 순환을 쓴다(없으면 종전 역할 경로)."""
    return any((a.get("source_ref") or "") == "volcano/sfx_norm" for a in cands)


def _cycle_pool(cands):
    """역할표 밖 칸이 돌려 쓸 효과음 줄 세우기 — **벤치마크 순환 공식**대로.

    ★첫 컷(i=0)은 pop4 — 8편 실측에서 예외 없이 같았다(사장님: "후킹 처음에 들어가는 공통 효과음").
    공식이 부르는 계열이 (길이 상한에 걸려) 없으면 남은 계열에서 가로로 이어 채운다.
    ★팩에 든 것만 쓴다 — 08-21 검증용 톤("띠용(테스트)"·"뿅(테스트)")이 섞이면 결이 튄다.
    결정적(정렬 고정)이라 같은 대본이면 항상 같은 배열이 나온다.
    """
    packed = [a for a in cands if (a.get("source_ref") or "") == "volcano/sfx_norm"] or cands
    # ★긴 소리는 뺀다(2026-09-17 사장님 "이븐쇼핑이랑 최대한 비슷하게 해").
    #   실측 대조 — 뇌전구 팩 79개: 길이 중앙 421ms · 200ms 이하 29% · 반짝 25%/붐 53%
    #             이븐쇼핑류 12편 441건: 길이 중앙 80ms · 200ms 이하 93% · 반짝 80%/붐 17%
    #   팩이 5배 길고 계열 비율이 거의 반대다. 컷이 1.7초인데 drum(1535ms)·ding(1060ms)을
    #   얹으면 컷 하나를 통째로 덮는다(실측 job sfxb04ef8057에 censor·drum·fail이 들어갔다).
    #   ★이름으로 고르지 않는다 — 팩이 바뀌면 또 어긋난다(0순위-B). **잰 길이**로 거른다.
    #   통과분(실측): pop4 38ms · click 125ms · x_click 127ms · r3_click 167ms = 4계열 25개.
    short = [a for a in packed if 0 < float(a.get("duration") or 0) <= _SFX_MAX_SECS]
    packed = short or packed          # 길이를 못 잰 팩이면 종전대로(조용히 비지 않게)
    lanes = {}
    for a in sorted(packed, key=lambda x: x["id"]):
        fam = ((a.get("keywords") or [""])[0] if isinstance(a.get("keywords"), list)
               else str(a.get("keywords") or "").split(",")[0])
        lanes.setdefault(fam or "기타", []).append(a)
    # 공식대로 한 바퀴 — 각 계열은 자기 줄에서 순서대로 뽑아 쓴다(같은 파일 연속 금지).
    order = sorted(lanes)                      # 계열 이름순 = 실행마다 같다
    take = {k: 0 for k in lanes}
    out, rounds = [], max(len(v) for v in lanes.values()) * len(_CYCLE_SLOTS)
    for i in range(rounds):
        slot = _CYCLE_SLOTS[i % len(_CYCLE_SLOTS)]
        fam = slot[(i // len(_CYCLE_SLOTS)) % len(slot)]
        if fam not in lanes:                   # 길이 상한에 걸려 없는 계열 → 남은 것으로 대체
            left = [k for k in order if take[k] < len(lanes[k])] or order
            fam = left[i % len(left)]
        lane = lanes[fam]
        out.append(lane[take[fam] % len(lane)])
        take[fam] += 1
    return out or [a for v in lanes.values() for a in v]


def match_sfx(plan, assets):
    """비트 역할 → 효과음 역할 결정적 매칭. Gemini 0회. plan을 복사해 반환.
    beat["sfx"] = {asset_id, match_type:"role", position}. 클립 컷어웨이(beat["cutaway"])와
    다른 키라 한 비트가 장면짤+효과음을 동시에 가질 수 있다. **중복 허용**(같은 효과음이
    여러 비트에 배치 가능) — used 세트가 없는 게 클립 역할패스와의 유일한 차이(§3.4)."""
    plan = copy.deepcopy(plan)
    cands = _sfx_candidates(assets)
    by_role = {}
    for a in cands:
        by_role.setdefault(a["role"], []).append(a)
    for beat in plan["beats"]:
        # ★사람이 고르거나 옮긴 것은 건드리지 않는다(2026-08-21). 재매칭은 대본이 바뀔
        #   때마다 도는데(mix_pipeline), 무조건 덮으면 사장님이 칸에서 바꾼 효과음이
        #   조용히 되돌아간다 — "바꿨는데 그대로"로 겪는다.
        if (beat.get("sfx") or {}).get("match_type") == "manual":
            continue
        # ★팩(뇌전구)이 깔려 있으면 **역할을 보지 않고 공식 순환**을 쓴다(2026-09-17 사장님
        #   "이븐쇼핑이랑 최대한 비슷하게 해" · "후킹 처음에 들어가는 공통 효과음 있어").
        #   역할 경로로 가면 길이 상한을 안 타서 훅에 r3_pop(353ms)·CTA에 x_ding(859ms) 같은
        #   긴 소리가 붙었다(실측). 벤치마크는 훅이 **항상 pop4**(8편 전부 동일)이고 컷 번호로만
        #   정한다 — 역할별 표는 그 실측과 어긋난다. 팩이 없으면 종전 역할 경로 그대로(회귀 0).
        cyc = _cycle_pool(cands) if _has_pack(cands) else None
        if cyc:
            chosen = cyc[beat.get("beat_idx", 0) % len(cyc)]
            beat["sfx"] = {"asset_id": chosen["id"], "match_type": "cycle",
                           "position": _sfx_position(beat.get("role"))}
            continue
        compatible = _ROLE_FALLBACK.get(beat.get("role") or "")
        if not compatible:
            # ★역할표에 없는 역할도 **빈 채로 두지 않는다**(2026-09-17 사장님 "효과음이랑 짤을
            #   뇌전구 껄로 쓰라는 거야"). 종전엔 표에 없으면 통째로 건너뛰어, 백본 대본처럼
            #   역할이 `feature`인 칸은 **전부 소리가 없었다**(실측 job cut1da908c80: 배치 0/7칸,
            #   자산은 81개인데 하나도 안 붙음). 표를 늘리는 건 두더지다 — 역할이 새로 생길
            #   때마다 또 빈다(조사 기록: `match_sfx` 배치 5/9칸도 같은 원인).
            #   실측이 가리키는 답: 벤치마크는 **역할을 안 보고 컷마다 순환**한다
            #   (뇌전구 역분석 — 27컷 전부 1발씩, pop4→click→boing→ding… 컷 번호대로 고정 순환.
            #    무작위 아님. 효과음 실측 12편에서도 "역할이 아니라 컷에 붙는다").
            #   그래서 표에 없으면 **전체 후보를 비트 순번으로 돌려쓴다**(결정적 = 재실행해도 같다).
            if not cands:
                continue
            # ★계열을 **번갈아** 돈다 — 벤치마크 순환이 pop4→click→boing→ding처럼 매 컷 결이
            #   바뀐다. id 순으로만 돌리면 boing_0,1,2,3이 연달아 나와 한 소리만 반복된다(실측).
            #   계열별로 한 줄씩 세우고 가로로 읽어 계열이 겹치지 않게 한다.
            pool = _cycle_pool(cands)
            chosen = pool[beat.get("beat_idx", 0) % len(pool)]
            beat["sfx"] = {"asset_id": chosen["id"], "match_type": "cycle",
                           "position": _sfx_position(beat.get("role"))}
            continue
        pool = [a for role in compatible for a in by_role.get(role, [])]   # 중복 허용
        if not pool:
            continue
        chosen = _pick_role_asset(pool, beat.get("narration") or "")
        beat["sfx"] = {"asset_id": chosen["id"], "match_type": "role",
                       "position": _sfx_position(beat.get("role"))}
    return plan
