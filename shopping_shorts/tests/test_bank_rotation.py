"""은행 부품 회전 — 소재마다 다른 조각이 실리는가(2026-07-31).

실측 결함 2개를 못 박는다:
① seed가 늘 0이라 회전이 아예 안 됐다. script_engine 주석은 "매번 다른 조각이 보이도록
   seed로 회전시킨다"고 했는데 본 호출이 항상 0을 넘겨, 밥솥 요리든 비누든 모든 소재에
   같은 감각어 6개(꿉꿉·보송·순식간·뚝딱·사르르·촉촉)만 나갔다.
② 고쳐서 seed를 넣었더니 `seed*7 % 35`에서 7이 35의 약수라 **오프셋이 5가지뿐**이었다
   (seed 56과 61이 같은 조각). 창 이동 대신 해시 정렬로 바꿨다.
"""
import re

from shopping_shorts import edit_plan, script_engine as se


def _adv(seed, bank):
    line = [l for l in se._bank_block(bank, seed=seed).splitlines() if "수식" in l]
    return re.findall(r'"([^"]+)"', line[0]) if line else []


BANK = {b: [f"{b}{i}" for i in range(35)] for b in se.BUCKETS}


def test_seed_changes_the_pick():
    """★뿌리 ②: seed가 조금만 달라도 조합이 달라져야 한다(약수 충돌 회귀)."""
    assert _adv(56, BANK) != _adv(61, BANK)
    assert _adv(0, BANK) != _adv(1, BANK)


def test_same_seed_is_reproducible():
    """백테스트가 성립하려면 같은 입력엔 항상 같은 출력이어야 한다(난수 금지)."""
    assert _adv(42, BANK) == _adv(42, BANK)


def test_material_seed_differs_by_material():
    """★뿌리 ①: 소재가 다르면 seed가 달라야 회전이 의미를 갖는다."""
    a = edit_plan._engine_seed("밥솥으로 카스테라 만들기")
    b = edit_plan._engine_seed("교도소 비누 찌든때 세탁")
    assert a != b
    assert a == edit_plan._engine_seed("밥솥으로 카스테라 만들기")   # 같은 소재는 고정


def test_sensory_bucket_carries_more_items():
    """감각어는 단어라 많이 실어야 표현이 반복되지 않는다(6개→14개)."""
    assert len(_adv(0, BANK)) == se._PER_BUCKET["adverb"] == 14


def test_generation_passes_material_seed(monkeypatch):
    """★배선: build_scene_first_plan이 소재 기반 seed를 실제로 넘기는가.
    (프롬프트 문자열을 붙잡아 서로 다른 소재가 다른 블록을 받는지 본다)"""
    seen = []
    seg = {"s0-0": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0,
                    "text": "", "scene_desc": "", "motion_level": "MED"}}
    monkeypatch.setattr(edit_plan, "_build_inventory", lambda s: (seg, "인벤토리"))
    # ★슬롯 순서질의(_pick_slot_groups, 2026-08-01)는 세지 않는다 — 이 테스트가 보는 건
    #   **대본 생성** 프롬프트가 소재마다 다른가이고, 순서질의는 소재와 무관한 별개 호출이다
    #   (다른 테스트들도 schema.required == ["order"]로 같은 구분을 한다).
    def _spy(prompt, schema, **kw):
        if (schema or {}).get("required") == ["order"]:
            return {"order": []}
        seen.append(prompt)
        return {"candidates": []}

    monkeypatch.setattr(edit_plan, "_vault_call", _spy)
    src = [{"video_id": "s0", "segments": [], "full_text": "x"}]
    edit_plan.build_scene_first_plan(src, "밥솥으로 카스테라 만들기", 30)
    edit_plan.build_scene_first_plan(src, "교도소 비누 찌든때 세탁", 30)
    assert len(seen) == 2 and seen[0] != seen[1], "소재가 달라도 같은 프롬프트가 나간다"


# ── 감각어 하한(2026-07-31) ─────────────────────────────────────────────
def _cand(narrs, score):
    return {"plan": {"beats": [{"narration": n} for n in narrs]},
            "score": score, "recommended": False}


def _pick(cands):
    """build_scene_first_plan 말미의 추천 선택과 동일한 판정(단계적 완화)."""
    toned = [i for i, c in enumerate(cands) if edit_plan._cand_tone(c) >= edit_plan._TONE_GATE]
    rich = [i for i in toned if edit_plan._cand_sensory(cands[i]) >= edit_plan._SENSORY_FLOOR]
    pool = (rich or toned) or range(len(cands))
    return max(pool, key=lambda i: cands[i]["score"])


_VIVID_FLAT = ["방마다 쿠키가 걸려 있는 거 있죠?", "만든 거라지 뭐예요.",
               "저도 찍어봤거든요.", "향이 퍼지더라구요."]
_VIVID_RICH = ["보송한 게 느껴지는 거 있죠?", "향긋한 냄새가 확 퍼지더라구요.",
               "쫀득하게 뭉쳐지거든요.", "순식간에 끝나잖아요."]


def test_sensory_floor_prefers_richer_candidate():
    """★말투가 같으면 감각어가 많은 쪽을 고른다(점수가 낮아도)."""
    cands = [_cand(_VIVID_FLAT, 0.95), _cand(_VIVID_RICH, 0.70)]
    assert edit_plan._cand_sensory(cands[1]) >= edit_plan._SENSORY_FLOOR
    assert _pick(cands) == 1


def test_falls_back_to_tone_only_when_none_rich():
    """감각어 기준을 넘는 후보가 없으면 말투 기준으로만 고른다(후보를 잃지 않는다)."""
    cands = [_cand(_VIVID_FLAT, 0.70), _cand(_VIVID_FLAT, 0.92)]
    assert _pick(cands) == 1


def test_tone_floor_still_wins_over_sensory():
    """감각어가 많아도 말투가 기준 미달이면 뽑히지 않는다(말투가 상위 기준)."""
    flat_tone = ["이걸 샀어요.", "촉촉해요.", "폭신해요.", "향긋해요.", "좋아요."]
    cands = [_cand(flat_tone, 0.99), _cand(_VIVID_FLAT, 0.60)]
    assert edit_plan._cand_tone(cands[0]) < edit_plan._TONE_GATE
    assert _pick(cands) == 1


def test_sensory_floor_is_wired():
    import inspect
    src = inspect.getsource(edit_plan.build_scene_first_plan)
    assert "_SENSORY_FLOOR" in src and "rich or toned" in src
