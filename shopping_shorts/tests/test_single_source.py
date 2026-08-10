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
def test_story_floor_can_exceed_original():
    """★2026-08-09 정책 반전(사장님 지시) — 대본 예산은 원본을 넘을 수 있다.

    종전 `test_never_exceeds_original`은 "결과가 원본보다 길 수 없다"를 잠갔다.
    그 천장 때문에 19.5초 소재는 대본이 영원히 124자·4문장이었고, 채이 가족액자
    (few-shot 377자)·메종 긴 연결이 물리적으로 못 들어가 스타일이 죽었다
    (라이브 경로 실측: 메종 0/6 → 공간 확보 후 5/6).
    사장님 지시: "스타일을 살리려면 **중복을 허용하고** 최대한 살려야 한다.
    결국 클릭으로 이으려면 **스토리가 탄탄한 대본이 가장 우선**이다."
    → 모자란 화면은 _fill_beat_screen_time이 클립 재사용으로 채운다.
    ⚠️화면 실측(select_and_order의 컷 합계)은 여전히 원본이 천장이다 — 아래 테스트가 잠근다.
    """
    segs = _material(13, 1.5)          # 원본 19.5초
    span, budget = SS.budget_for(segs, target_seconds=30)
    assert budget >= min(SS.STORY_MIN_SECONDS, 30), "스토리 하한이 안 지켜졌다"
    assert budget > span, "원본(19.5초)보다 큰 대본 예산이 나와야 한다"


def test_screen_cuts_still_bounded_by_original():
    """★대본 예산이 늘어도 **화면(고른 컷 합계)은 원본을 못 넘는다**.

    늘어난 분량은 클립 재사용으로 채우는 것이지, 없는 화면을 만드는 게 아니다."""
    segs = _material(13, 1.5)
    span, _, _, order = SS.select_and_order(segs, target_seconds=30)
    screen = sum(float(s["end"]) - float(s["start"]) for s in order)
    assert screen <= span + 0.01, "화면 합계가 원본을 넘었다"


def test_story_floor_respects_shorter_target():
    """사용자가 목표를 더 짧게 고르면 그 값이 이긴다(하한이 목표를 늘리지 않는다)."""
    segs = _material(13, 1.5)
    _, budget = SS.budget_for(segs, target_seconds=15)
    assert budget <= 15.0 + 0.01, "사용자 목표(15초)보다 길어졌다"


def test_story_floor_rollback_switch(monkeypatch):
    """★롤백 스위치 — STORY_MIN_SECONDS=0이면 종전 동작(원본이 천장)."""
    segs = _material(13, 1.5)
    monkeypatch.setattr(SS, "STORY_MIN_SECONDS", 0.0, raising=False)
    span, budget = SS.budget_for(segs, target_seconds=30)
    assert budget <= span, "롤백 시엔 원본을 넘으면 안 된다"


def test_floor_18_seconds():
    segs = _material(20, 1.5)          # 원본 30초 → 90%면 27초
    _, budget = SS.budget_for(segs, target_seconds=30)
    assert budget >= SS.MIN_SECONDS


def test_short_original_uses_whole():
    """원본이 짧아도 **화면은 원본 전체**를 쓴다(대본 예산은 스토리 하한까지 늘어난다).

    ★2026-08-09: 종전엔 `budget == span`이었다(예산=화면=원본). 정책 반전 후
    budget은 대본 분량이라 스토리 하한까지 올라가고, 화면만 원본 전체로 남는다."""
    segs = _material(6, 1.5)           # 원본 9초
    span, budget, _, order = SS.select_and_order(segs, target_seconds=30)
    screen = sum(float(s["end"]) - float(s["start"]) for s in order)
    assert abs(screen - span) < 0.01, "원본이 짧으면 화면은 원본 전체를 쓴다"
    assert budget >= min(SS.STORY_MIN_SECONDS, 30), "대본 예산은 스토리 하한까지 확보된다"


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
