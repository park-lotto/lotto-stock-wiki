"""①생성측 보강(2026-07-25 세션#2) — 후보가 전부 목표보다 크게 짧으면(생성 미달) 길이 강화
힌트로 1회 재생성해 합친다. ②선택 감점과 짝: 재생성은 '전부 짧을 때만'(과금 게이트), 병합 후
채점하면 긴 후보가 자연히 추천된다."""
from shopping_shorts import edit_plan


_LONG_A = "곰팡이 핀 양파를 봤는데 남편이 이거 먹어도 되냐고 묻길래 통풍만 잘하면 괜찮다고 했어요 진짜로"
_LONG_B = "그래서 베란다에 널어놨더니 며칠 뒤에 멀쩡해져서 남편이 이거 무슨 마법이냐고 깜짝 놀라더라고요"


def _src():
    return [{"video_id": "s0", "full_text": "원본", "segments": [
        {"seg_id": "s0-1", "start": 1.0, "end": 2.0, "text": "", "scene_desc": "곰팡이"},
        {"seg_id": "s0-2", "start": 2.0, "end": 3.0, "text": "", "scene_desc": "단면"},
        {"seg_id": "s0-3", "start": 3.0, "end": 5.0, "text": "", "scene_desc": "통풍"}]}]


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
        calls["n"] += 1
        if "[길이 재생성]" in prompt:      # 보강 힌트가 실제 프롬프트에 얹혔는지
            calls["lengthen_seen"] = True
            return _long_batch()
        return _short_batch()

    out = edit_plan.build_scene_first_plan(_src(), "원본대본", 20, n_candidates=2, call=fake_call)
    assert calls["n"] == 2                              # 최초 생성 + 재생성 1회
    assert calls["lengthen_seen"] is True               # 재생성 프롬프트에 힌트 주입
    assert len(out["candidates"]) == 3                  # 짧은 후보 2 + 긴 후보 1 병합
    rec = [c for c in out["candidates"] if c["recommended"]]
    assert len(rec) == 1 and rec[0]["story"]["hook"] == "LONG"   # 긴 후보 추천


def test_no_regeneration_when_length_ok():
    """후보가 목표에 근접하면 재생성하지 않는다(과금 게이트·회귀0)."""
    calls = {"n": 0}

    def fake_call(prompt, schema, **kw):
        calls["n"] += 1
        return _long_batch()          # 목표 근처 길이

    out = edit_plan.build_scene_first_plan(_src(), "원본대본", 20, n_candidates=2, call=fake_call)
    assert calls["n"] == 1                              # 재생성 없음
    assert len(out["candidates"]) == 1
