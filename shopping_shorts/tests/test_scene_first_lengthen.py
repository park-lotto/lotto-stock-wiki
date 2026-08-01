"""①생성측 보강(2026-07-25 세션#2) — 후보가 전부 목표보다 크게 짧으면(생성 미달) 길이 강화
힌트로 1회 재생성해 합친다. ②선택 감점과 짝: 재생성은 '전부 짧을 때만'(과금 게이트), 병합 후
채점하면 긴 후보가 자연히 추천된다."""
from shopping_shorts import edit_plan


_LONG_A = "곰팡이 핀 양파를 봤는데 남편이 이거 먹어도 되냐고 묻길래 통풍만 잘하면 괜찮다고 했어요 진짜로"
_LONG_B = "그래서 베란다에 널어놨더니 며칠 뒤에 멀쩡해져서 남편이 이거 무슨 마법이냐고 깜짝 놀라더라고요"


def _src():
    # 조각 5개 — 첫(s0-0)·끝(s0-4)은 인벤토리에서 제외되므로(썸네일·CTA 차단, Task 3) 후보는
    # 가운데 s0-1/s0-2/s0-3만 참조한다(실제 라이브: 첫·끝 뺀 가운데 장면을 씀).
    return [{"video_id": "s0", "full_text": "원본", "segments": [
        {"seg_id": "s0-0", "start": 0.0, "end": 1.0, "text": "", "scene_desc": "썸네일"},
        {"seg_id": "s0-1", "start": 1.0, "end": 2.0, "text": "", "scene_desc": "곰팡이"},
        {"seg_id": "s0-2", "start": 2.0, "end": 3.0, "text": "", "scene_desc": "단면"},
        {"seg_id": "s0-3", "start": 3.0, "end": 5.0, "text": "", "scene_desc": "통풍"},
        {"seg_id": "s0-4", "start": 5.0, "end": 6.0, "text": "", "scene_desc": "CTA"}]}]


def _short_batch():
    # 두 후보 모두 나레이션이 짧아 목표 20초에 크게 못 미친다(총 ~2초).
    return {"candidates": [
        {"hook": "SHORT_A", "cta_keyword": "k", "beats": [
            {"role": "훅", "narration": "곰팡이요", "seg_ids": ["s0-1", "s0-2"], "fit": 5, "forced": False},
            {"role": "cta", "narration": "댓글요", "seg_ids": ["s0-3"], "fit": 5, "forced": False}]},
        {"hook": "SHORT_B", "cta_keyword": "k", "beats": [
            {"role": "훅", "narration": "양파요", "seg_ids": ["s0-1"], "fit": 5, "forced": False},
            {"role": "cta", "narration": "봐요", "seg_ids": ["s0-3"], "fit": 5, "forced": False}]}]}


def _long_batch():
    return {"candidates": [
        {"hook": "LONG", "cta_keyword": "k", "beats": [
            {"role": "훅", "narration": _LONG_A, "seg_ids": ["s0-1", "s0-2"], "fit": 5, "forced": False},
            {"role": "cta", "narration": _LONG_B, "seg_ids": ["s0-3"], "fit": 5, "forced": False}]}]}


def test_regenerates_when_all_candidates_short():
    """전부 짧으면 lengthen=True로 재생성 → 병합 → 긴 후보가 추천된다."""
    calls = {"n": 0, "lengthen_seen": False}

    def fake_call(prompt, schema, **kw):
        if schema.get("required") == ["order"]:     # Task5: _pick_slot_groups의 순서질의(회귀0 대상 아님)
            return {"order": []}
        calls["n"] += 1
        if "[길이 보강]" in prompt:      # 보강 힌트가 실제 프롬프트에 얹혔는지(2026-07-26 마커 개명)
            calls["lengthen_seen"] = True
            return _long_batch()
        return _short_batch()

    out = edit_plan.build_scene_first_plan(_src(), "원본대본", 20, n_candidates=2, call=fake_call)
    assert calls["n"] == 2                              # 최초 생성 + 재생성 1회
    assert calls["lengthen_seen"] is True               # 재생성 프롬프트에 힌트 주입
    # ★2026-08-01: 병합은 **고르기 위한** 것이라 사람에게 내보내는 개수는 n_candidates까지만
    #   자른다(사장님 "대본이 왜 4개야?"). 재생성 자체(calls["n"]==2)와 긴 후보가 추천으로
    #   살아남는 것은 그대로 — 잘려나가면 재생성이 무의미해지므로 추천은 항상 남긴다.
    assert len(out["candidates"]) == 2                  # 상한 = n_candidates
    rec = [c for c in out["candidates"] if c["recommended"]]
    assert len(rec) == 1 and rec[0]["story"]["hook"] == "LONG"   # 긴 후보 추천(잘리지 않음)


def test_no_regeneration_when_length_ok():
    """후보가 목표에 근접하면 재생성하지 않는다(과금 게이트·회귀0)."""
    calls = {"n": 0}

    def fake_call(prompt, schema, **kw):
        if schema.get("required") == ["order"]:     # Task5: _pick_slot_groups의 순서질의(회귀0 대상 아님)
            return {"order": []}
        calls["n"] += 1
        return _long_batch()          # 목표 근처 길이

    out = edit_plan.build_scene_first_plan(_src(), "원본대본", 20, n_candidates=2, call=fake_call)
    assert calls["n"] == 1                              # 재생성 없음
    assert len(out["candidates"]) == 1


def test_cap_keeps_recommended_even_when_it_scores_low():
    """재생성분이 상한에 밀려 잘리더라도 **추천 후보는 반드시 남는다**.

    자르기가 단순 점수 상위 N이면, 재생성으로 얻은 긴 후보가 점수에서 밀릴 때
    추천이 통째로 사라진다(추천 없는 후보목록 = 화면이 아무것도 못 고른다).
    """
    calls = {"n": 0}

    def fake_call(prompt, schema, **kw):
        if schema.get("required") == ["order"]:
            return {"order": []}
        calls["n"] += 1
        if "[길이 보강]" in prompt:
            return _long_batch()
        return _short_batch()

    out = edit_plan.build_scene_first_plan(_src(), "원본대본", 20, n_candidates=1,
                                           call=fake_call)
    assert len(out["candidates"]) == 1
    rec = [c for c in out["candidates"] if c["recommended"]]
    assert len(rec) == 1 and rec[0]["story"]["hook"] == "LONG"
