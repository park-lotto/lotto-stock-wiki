# -*- coding: utf-8 -*-
"""후보 3개 병렬 생성 (2026-08-06).

예전엔 for 순차라 **후보 1개 시간 × 3**이 걸렸다(실측 job 2d3687ad4e87:
후보1 40초 / 후보2 39초 / 후보3 31초 = 총 110초). 이 일은 CPU가 아니라 Gemini
응답 대기가 거의 전부라 스레드로 동시에 기다리면 벽시계가 가장 느린 하나로 줄어든다.

★선행조건: 후보별 키 오프셋(test_key_spread_and_exclusive.py). 그게 없으면 병렬로
  돌릴 때 셋이 **동시에** 같은 키를 때려 분당한도 429가 확정이다.
"""
import time

import pytest

from shopping_shorts import edit_plan


def _fixture(monkeypatch, delay=0.0, record=None):
    """_single_source_candidates가 부르는 single_source/hook_patterns를 대역으로."""
    import types as _t

    order = [{"start": 0.0, "end": 3.0, "video_id": "v", "text": "a"} for _ in range(4)]

    def _beats():
        return [{"narration": f"문장{i} 댓글에 '나도'", "covers": [i + 1]} for i in range(4)]

    ss = _t.SimpleNamespace(
        select_and_order=lambda seg, tgt: (18.0, 18.0, 18.0, order),
        script_prompt=lambda *a, **k: "p",
        BEATS_SCHEMA={}, ESCALATE_SCHEMA={}, RESTYLE_SCHEMA={},
        parse_beats=lambda raw: _beats(),
        over_budget=lambda b, u: (False, 0, 0),
        shrink_prompt=lambda *a: "p",
        cta_missing=lambda b: False,
        fix_cta_prompt=lambda *a: "p",
        escalate_prompt=lambda b: "p",
        apply_restyle=lambda beats, call, style_name=None: beats,
    )
    monkeypatch.setattr(edit_plan, "single_source", ss, raising=False)

    hp = _t.SimpleNamespace(
        choose=lambda n, material_text="": [("discover", "우연한발견"),
                                            ("y_stop_buy", "이제사지마"),
                                            ("target", "대상호출")],
        prompt_block=lambda p: "블록",
    )
    monkeypatch.setattr(edit_plan, "hook_patterns", hp, raising=False)
    monkeypatch.setitem(__import__("sys").modules, "shopping_shorts.single_source", ss)
    monkeypatch.setitem(__import__("sys").modules, "shopping_shorts.hook_patterns", hp)

    def call(prompt, schema, **kw):
        if record is not None:
            record.append(time.monotonic())
        time.sleep(delay)          # Gemini 응답 대기를 흉내
        return {}

    return call


def test_후보3개가_병렬로_돈다(monkeypatch):
    """순차면 3×delay, 병렬이면 ~1×delay."""
    call = _fixture(monkeypatch, delay=0.30)
    t0 = time.monotonic()
    out = edit_plan._single_source_candidates(
        [{"segments": [{"start": 0, "end": 3}], "full_text": "본문", "video_id": "v"}],
        {}, 18.0, 3, call, "generic")
    elapsed = time.monotonic() - t0
    assert out and len(out["candidates"]) == 3, out
    # 순차였다면 최소 0.9초. 병렬이면 0.3초대.
    assert elapsed < 0.75, f"병렬이 아니다 — {elapsed:.2f}초 걸렸다(순차면 0.9초+)"


def test_후보_순서가_보존된다(monkeypatch):
    """trio 스타일(A=메종/B=채이/C=스탠다드)이 후보 순서에 배정되므로
    완료 순서가 아니라 **입력 순서**로 나와야 한다."""
    call = _fixture(monkeypatch, delay=0.0)
    out = edit_plan._single_source_candidates(
        [{"segments": [{"start": 0, "end": 3}], "full_text": "본문", "video_id": "v"}],
        {}, 18.0, 3, call, "generic")
    pats = [c["plan"]["hook_pattern"] for c in out["candidates"]]
    assert pats == ["discover", "y_stop_buy", "target"], pats


def test_후보1개면_스레드_안쓴다(monkeypatch):
    """1개짜리에 풀을 띄우는 건 낭비 — 그냥 직접 부른다(결과는 동일해야 한다)."""
    call = _fixture(monkeypatch, delay=0.0)
    out = edit_plan._single_source_candidates(
        [{"segments": [{"start": 0, "end": 3}], "full_text": "본문", "video_id": "v"}],
        {}, 18.0, 1, call, "generic")
    assert out and len(out["candidates"]) == 1


def test_한_후보가_죽어도_나머지는_산다(monkeypatch):
    """스레드에서 예외가 새면 ex.map이 통째로 터져 대본이 0개가 된다."""
    call = _fixture(monkeypatch, delay=0.0)
    real = edit_plan.single_source.parse_beats
    state = {"n": 0}

    def flaky(raw):
        state["n"] += 1
        if state["n"] == 2:            # 두 번째 호출만 터뜨린다
            raise RuntimeError("모델 응답 깨짐")
        return real(raw)

    monkeypatch.setattr(edit_plan.single_source, "parse_beats", flaky, raising=False)
    out = edit_plan._single_source_candidates(
        [{"segments": [{"start": 0, "end": 3}], "full_text": "본문", "video_id": "v"}],
        {}, 18.0, 3, call, "generic")
    assert out and len(out["candidates"]) >= 1, f"하나 죽었다고 전멸하면 안 된다: {out}"
