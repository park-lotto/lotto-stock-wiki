"""핑퐁 트림 전체 길이 하한 + 핑퐁 뒤 CTA 재교정(2026-07-31).

★백테스트 하네스를 라이브 인자(핑퐁·백본·은행·심사)로 고치고 나서야 보인 결함들이다.
그전까지 하네스는 기본값(전부 OFF)으로 돌아 **라이브와 다른 경로**를 재고 있었다 —
같은 소재가 라이브 경로 67~94자 / 기본 경로 157~185자.

① 트림이 대본을 반토막 낸다: 비트마다 "화면보다 말이 길다"고 깎다 보면 소스가 짧을 때
   전체가 쪼그라든다(실측 20건에서 62~106자가 다수, 목표는 150~185자).
② 핑퐁 후처리가 CTA를 마지막에서 밀어낸다(실측 20건 중 9건 CTA끝X).
"""
from shopping_shorts import backbone, edit_plan


def _beat(i, narr, dur):
    return {"beat_idx": i, "role": "해결", "narration": narr,
            "primary": {"seg_id": f"s0-{i}", "start": 0.0, "end": dur, "video_id": "s0"},
            "alternates": []}


def _long(n):
    return "가나다라마바사아자차" * n


def test_trim_skipped_when_it_would_gut_the_script():
    """★트림을 다 적용하면 하한 밑으로 내려갈 때는 아예 적용하지 않는다."""
    beats = [_beat(i, _long(3), 1.0) for i in range(4)]      # 각 30자, 화면 1초 → 전부 over
    trims = {i: "짧게" for i in range(4)}                     # 트림하면 총 8자
    out = backbone.ping_pong_reconcile(
        beats, [], trim_call=lambda over: trims, min_total_chars=100)
    assert all(not b.get("length_trimmed") for b in out), "하한 밑인데 트림이 적용됐다"
    assert all(len(b["narration"]) == 30 for b in out), "원래 대본이 보존돼야 한다"


def test_trim_applied_when_result_stays_above_floor():
    """하한을 지키는 트림은 정상 적용된다(기능을 죽이면 안 된다)."""
    beats = [_beat(i, _long(6), 1.0) for i in range(4)]      # 각 60자
    trims = {i: _long(3) for i in range(4)}                   # 트림 후 총 120자
    out = backbone.ping_pong_reconcile(
        beats, [], trim_call=lambda over: trims, min_total_chars=100)
    assert any(b.get("length_trimmed") for b in out), "지킬 수 있는 트림까지 막으면 안 된다"


def test_no_floor_keeps_old_behavior():
    """min_total_chars=0(기본)이면 종전대로 — 다른 호출부 회귀 0."""
    beats = [_beat(i, _long(3), 1.0) for i in range(4)]
    out = backbone.ping_pong_reconcile(
        beats, [], trim_call=lambda over: {i: "짧게" for i in range(4)})
    assert any(b.get("length_trimmed") for b in out)


def test_pingpong_call_passes_floor():
    """배선 — 핑퐁 호출이 목표초에서 계산한 하한을 실제로 넘기는가."""
    import inspect
    src = inspect.getsource(edit_plan.build_scene_first_plan)
    assert "min_total_chars=" in src, "하한이 안 넘어간다"
    assert "ping_pong_reconcile" in src


def test_structure_fix_runs_after_pingpong():
    """★핑퐁 후처리(순서 재배치)가 CTA를 밀어낸 뒤 교정이 다시 걸려야 한다."""
    import inspect
    src = inspect.getsource(edit_plan.build_scene_first_plan)
    i = src.index("swap_hook_cta_for_differentiation")
    assert "_fix_beat_structure" in src[i:i + 800], "핑퐁 뒤 CTA 재교정이 없다"


# ── CTA 비트 보장(2026-07-31) ───────────────────────────────────────────
def _b(role, narr, sid="s0-1"):
    return {"beat_idx": 0, "role": role, "narration": narr,
            "primary": {"seg_id": sid, "start": 0.0, "end": 2.0, "video_id": "s0"},
            "alternates": []}


def test_cta_beat_is_added_when_model_omits_it():
    """★실측: 라이브 경로 20건 중 9건에 CTA 비트가 아예 없었다(모델이 안 만든다)."""
    beats = [_b("훅", "훅 문장"), _b("결과", "결과 문장")]
    out = edit_plan._ensure_cta_beat(beats, {"cta_line": "비법 궁금하면 댓글에 '커피' 남겨주세요"})
    assert len(out) == 3
    assert edit_plan._is_cta(out[-1])
    assert out[-1]["narration"].endswith("남겨주세요")
    assert out[-1]["primary"], "CTA 비트에도 화면이 있어야 렌더된다"


def test_existing_cta_is_not_duplicated():
    beats = [_b("훅", "훅"), _b("CTA", "댓글 남겨주세요")]
    out = edit_plan._ensure_cta_beat(beats, {"cta_line": "다른 CTA"})
    assert len(out) == 2 and out[-1]["narration"] == "댓글 남겨주세요"


def test_no_cta_line_means_no_fabrication():
    """cta_line이 비면 억지로 지어내지 않는다."""
    beats = [_b("훅", "훅"), _b("결과", "결과")]
    assert len(edit_plan._ensure_cta_beat(beats, {"cta_line": ""})) == 2
    assert len(edit_plan._ensure_cta_beat(beats, {})) == 2


def test_added_cta_survives_structure_fix():
    """붙인 CTA가 구조 교정을 거쳐도 마지막에 남아야 한다."""
    beats = [_b("훅", "훅"), _b("결과", "결과 문장")]
    out = edit_plan._fix_beat_structure(
        edit_plan._ensure_cta_beat(beats, {"cta_line": "댓글에 '방법' 남겨주세요"}))
    assert edit_plan._is_cta(out[-1])
    assert [x["beat_idx"] for x in out] == list(range(len(out)))
