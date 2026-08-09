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
    """_single_source_candidates가 부르는 single_source/hook_patterns를 대역으로.

    ★_one_candidate는 `from shopping_shorts import single_source`를 **함수 안에서**
      한다. sys.modules를 바꿔치는 방식은 다른 테스트가 이미 진짜 모듈을 import해
      둔 뒤엔 안 먹는다(단독 실행은 통과, 전체 실행은 실패 — 실제로 겪었다).
      그래서 **진짜 모듈 객체의 속성을 monkeypatch**한다. monkeypatch가 테스트
      끝에 원복하므로 다른 테스트에 새지 않는다."""
    from shopping_shorts import hook_patterns as real_hp
    from shopping_shorts import single_source as real_ss

    order = [{"start": 0.0, "end": 3.0, "video_id": "v", "text": "a"} for _ in range(4)]

    def _beats(raw=None):
        return [{"narration": f"문장{i} 댓글에 '나도'", "covers": [i + 1]} for i in range(4)]

    for name, val in (
        ("select_and_order", lambda seg, tgt, **kw: (18.0, 18.0, 18.0, order)),
        ("script_prompt", lambda *a, **k: "p"),
        ("parse_beats", _beats),
        ("over_budget", lambda b, u: (False, 0, 0)),
        ("shrink_prompt", lambda *a, **k: "p"),
        ("cta_missing", lambda b: False),
        ("fix_cta_prompt", lambda *a, **k: "p"),
        ("escalate_prompt", lambda b: "p"),
        ("apply_restyle", lambda beats, call, style_name=None, **kw: beats),
        # ★서명 보장(2026-08-09)도 다른 교정루프와 같이 꺼둔다 — 이 테스트가 재는 것은
        #   **후보 3개가 병렬로 도는가**지 교정 횟수가 아니다. 안 끄면 가짜 문장
        #   ("문장1 댓글에 '나도'")이 서명을 안 지켜 후보1·2만 call을 2회씩 더 부르고,
        #   가장 느린 후보가 전체 시간을 결정해 병렬인데도 0.9초를 넘긴다.
        #   ⚠️라이브에선 실제 소재 6건 중 보장 발동 0건이었다(생성이 이미 서명을 지킨다).
        ("hapsyo_tail_missing", lambda b, style_name=None: False),
        ("chae_person_missing", lambda b, style_name=None: False),
        ("maison_signature_missing", lambda b, style_name=None: False),
        ("hook_contradicts", lambda b, mat, call: False),
        ("under_budget", lambda b, used, floor=0.85: (False, 0, 0)),
        ("hapsyo_violation", lambda b, style_name=None: False),
        ("hook_opener_missing", lambda b, style_name=None: False),
    ):
        monkeypatch.setattr(real_ss, name, val, raising=False)

    monkeypatch.setattr(
        real_hp, "choose",
        lambda n, material_text="": [("discover", "우연한발견"),
                                     ("y_stop_buy", "이제사지마"),
                                     ("target", "대상호출")], raising=False)
    monkeypatch.setattr(real_hp, "prompt_block", lambda p: "블록", raising=False)

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
    from shopping_shorts import single_source as real_ss
    real = real_ss.parse_beats          # _fixture가 이미 대역으로 바꿔둔 것
    state = {"n": 0}
    import threading as _th
    lock = _th.Lock()

    def flaky(raw=None):
        with lock:                      # 병렬이라 카운터에 락이 필요하다
            state["n"] += 1
            mine = state["n"]
        if mine == 2:                   # 두 번째 호출만 터뜨린다
            raise RuntimeError("모델 응답 깨짐")
        return real(raw)

    monkeypatch.setattr(real_ss, "parse_beats", flaky, raising=False)
    out = edit_plan._single_source_candidates(
        [{"segments": [{"start": 0, "end": 3}], "full_text": "본문", "video_id": "v"}],
        {}, 18.0, 3, call, "generic")
    assert out and len(out["candidates"]) >= 1, f"하나 죽었다고 전멸하면 안 된다: {out}"


def test_품질미달_후보는_1회_재생성한다(monkeypatch):
    """restyle 확정 실패(restyled=False) 후보는 한 번 다시 만든다 — 조용한 원본
    수렴이 '품질 뒤죽박죽'의 원인이었다(2026-08-06). 상한 1회라 무한루프 없음."""
    call = _fixture(monkeypatch, delay=0.0)
    from shopping_shorts import single_source as real_ss
    calls = {"n": 0}
    import threading as _th
    lock = _th.Lock()

    def failing_restyle(beats, call, style_name=None, report=None, **kw):
        with lock:
            calls["n"] += 1
        if report is not None:
            report.update(ok=False, style=style_name, why="테스트 강제 실패")
        return beats

    monkeypatch.setattr(real_ss, "apply_restyle", failing_restyle, raising=False)
    out = edit_plan._single_source_candidates(
        [{"segments": [{"start": 0, "end": 3}], "full_text": "본문", "video_id": "v"}],
        {}, 18.0, 3, call, "generic")
    assert out and len(out["candidates"]) == 3
    # 후보 3개 × (원본 1회 + 재생성 1회) = 6회. 더 돌면 상한이 깨진 것.
    assert calls["n"] == 6, calls["n"]
    assert all(c["restyled"] is False for c in out["candidates"])


def test_품질게이트는_끌_수_있다(monkeypatch):
    """SCRIPT_QUALITY_RETRY=0 → 재생성 없이 종전과 동일(회귀 0)."""
    monkeypatch.setenv("SCRIPT_QUALITY_RETRY", "0")
    call = _fixture(monkeypatch, delay=0.0)
    from shopping_shorts import single_source as real_ss
    calls = {"n": 0}
    import threading as _th
    lock = _th.Lock()

    def failing_restyle(beats, call, style_name=None, report=None, **kw):
        with lock:
            calls["n"] += 1
        if report is not None:
            report.update(ok=False, style=style_name, why="테스트 강제 실패")
        return beats

    monkeypatch.setattr(real_ss, "apply_restyle", failing_restyle, raising=False)
    out = edit_plan._single_source_candidates(
        [{"segments": [{"start": 0, "end": 3}], "full_text": "본문", "video_id": "v"}],
        {}, 18.0, 3, call, "generic")
    assert out and len(out["candidates"]) == 3
    assert calls["n"] == 3, calls["n"]
