"""1소스 전용 로직 — 사장님 확정 스펙 4가지를 코드로 잠근다(2026-08-04)."""
from shopping_shorts import single_source as SS
from shopping_shorts import hook_patterns as HP
from shopping_shorts import plan_gate


def _seg(i, start, end, key=False, role="사용중", text=""):
    return {"seg_id": f"s0-{i}", "video_id": "s0", "start": start, "end": end,
            "is_key": key, "shot_role": role, "text": text, "scene_desc": ""}


def _material(n=13, dur=1.5):
    """n컷짜리 소재. 앞쪽 절반이 핵심, 마지막은 CTA."""
    segs, t = [], 0.0
    for i in range(n):
        role = "기타" if i == n - 1 else ("사용중" if i < n // 2 else "완성")
        txt = "댓글에 레몬 남겨주세요" if i == n - 1 else f"대사{i}"
        segs.append(_seg(i, t, t + dur, key=(i < n // 2), role=role, text=txt))
        t += dur
    return segs


# ① 길이: 상한 = 원본, 하한 = 18초
def test_never_exceeds_original():
    segs = _material(13, 1.5)          # 원본 19.5초
    span, budget = SS.budget_for(segs, target_seconds=30)
    assert budget <= span, "결과가 원본보다 길 수 없다"


def test_floor_18_seconds():
    segs = _material(20, 1.5)          # 원본 30초 → 90%면 27초
    _, budget = SS.budget_for(segs, target_seconds=30)
    assert budget >= SS.MIN_SECONDS


def test_short_original_uses_whole():
    segs = _material(6, 1.5)           # 원본 9초 — 하한 18초를 못 채운다
    span, budget = SS.budget_for(segs, target_seconds=30)
    assert budget == span, "원본이 하한보다 짧으면 원본 전체를 쓴다"


# ② 핵심(is_key) 보존
def test_keeps_all_key_segments():
    segs = _material(13, 1.5)
    _, _, _, order = SS.select_and_order(segs, target_seconds=30)
    kept = {s["seg_id"] for s in order}
    for s in segs:
        if s["is_key"]:
            assert s["seg_id"] in kept, f"핵심 {s['seg_id']}가 잘렸다"


# ③ 순서 변경 + ④ 중복 없음
def test_order_changes_and_no_duplicates():
    segs = _material(13, 1.5)
    _, _, _, order = SS.select_and_order(segs, target_seconds=30)
    ids = [s["seg_id"] for s in order]
    assert len(ids) == len(set(ids)), "같은 컷이 두 번 쓰였다"
    chrono = [s["seg_id"] for s in sorted(order, key=lambda x: x["start"])]
    assert ids != chrono, "원본 시간순 그대로면 '원본 트는 느낌'이 난다"


def test_cta_goes_last():
    segs = _material(13, 1.5)
    _, _, _, order = SS.select_and_order(segs, target_seconds=30)
    assert SS._is_cta(order[-1]), "CTA가 마지막이어야 마무리가 된다"


# 나레이션 총량 — 컷 수보다 적은 문장으로 덮는다
def test_line_count_below_cut_count():
    segs = _material(13, 1.5)
    _, _, used, order = SS.select_and_order(segs, target_seconds=30)
    assert SS.line_count(used, len(order)) <= len(order)


def test_over_budget_detects_overflow():
    used = 18.0
    fat = [{"narration": "가" * 200}]
    over, secs, gap = SS.over_budget(fat, used)
    assert over and gap > 0


def test_parse_beats_accepts_bare_list():
    assert SS.parse_beats([{"narration": "가"}]) == [{"narration": "가"}]
    assert SS.parse_beats({"beats": [{"narration": "나"}]})[0]["narration"] == "나"


# 게이트: 소재보다 큰 목표는 소재 기준으로 판정한다
def test_gate_uses_material_ceiling():
    beats = [{"primary": {"seg_id": f"s0-{i}", "video_id": "s0"},
              "target_seconds": 3.6} for i in range(5)]     # 18초
    strict = plan_gate.check_plan(beats, target_seconds=30)
    assert any("짧습니다" in v for v in strict["violations"])
    lenient = plan_gate.check_plan(beats, target_seconds=30, material_seconds=20.0)
    assert not any("짧습니다" in v for v in lenient["violations"]), \
        "20초 소재로 18초를 만들었으면 짧은 게 아니다"


# 훅 패턴 — 소재 적합성이 비율보다 우선
def test_daiso_hook_only_for_store_material():
    recipe = "레몬 스콘 반죽에 크림치즈를 채워 오븐에 구워 먹으면 맛있어요"
    store = "여러분 다이소 가면 이거 무조건 사오세요 매장에서 보이면 집어오세요"
    assert "y_store" not in [p[0] for p in HP.fitting(recipe)]
    assert "y_store" in [p[0] for p in HP.fitting(store)]


def test_yeoreobun_ratio_at_least_one_in_three():
    mat = "레몬 스콘 반죽을 오븐에 구워 먹는 레시피예요 얼려 먹으면 더 맛있어요"
    picks = HP.choose(3, material_text=mat)
    assert sum(1 for p in picks if p[2] == "여러분") >= 1


def test_choose_returns_distinct_patterns():
    mat = "레몬 스콘 반죽을 구워 먹는 레시피 만들어 보세요"
    picks = HP.choose(3, material_text=mat)
    assert len({p[0] for p in picks}) == len(picks)


def test_is_single_source():
    one = [{"video_id": "s0", "segments": [{"start": 0, "end": 1}]}]
    two = one + [{"video_id": "s1", "segments": [{"start": 0, "end": 1}]}]
    assert SS.is_single_source(one)
    assert not SS.is_single_source(two)
