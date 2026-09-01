# -*- coding: utf-8 -*-
"""훅 감탄사 켜고 끄기 (2026-09-01 사장님 "그냥 모든 대본에 앞에 감탄사 켜고 끄기 버튼").

코드가 대본 첫 문장 앞에 "와, "(서술형 절반) / "여러분 "(권유형)을 얹는다
(single_source.add_hook_opener — 프롬프트로는 안 돼서 코드로 옮긴 이력이 있다).
그걸 관리자가 전역으로 끌 수 있게 한다.

계약:
  · 설정이 없으면 **켬**(종전과 100% 같다 — 회귀 0)
  · off면 어떤 스타일이든 안 붙인다(모델이 스스로 쓴 감탄사는 그대로 — 코드 강제만 끈다)
  · 판정은 hook_opener_on 한 곳(0순위-B). DB는 60초 캐시로 읽는다
"""
import pytest

from shopping_shorts import single_source as S


@pytest.fixture(autouse=True)
def _clear_cache():
    S._HOOK_OPENER_CACHE.update(t=0.0, on=True)
    yield
    S._HOOK_OPENER_CACHE.update(t=0.0, on=True)


def _beats():
    return [{"narration": "다이소에서 이걸 봤어요."}]


def test_켠_상태면_감탄사가_붙는다(monkeypatch):
    monkeypatch.setattr(S, "hook_opener_on", lambda: True)
    b = _beats()
    if S.hook_opener_missing(b):
        b = S.add_hook_opener(b)
    # 서술형은 대본 해시로 절반만 붙는다 — 붙었거나 원문 그대로거나 둘 중 하나
    assert b[0]["narration"].startswith(("와, ", "다이소"))


def test_끈_상태면_어떤_스타일이든_안_붙는다(monkeypatch):
    monkeypatch.setattr(S, "hook_opener_on", lambda: False)
    for style in (None, "maison", "hometerior", "standard", "chae"):
        assert S.hook_opener_missing(_beats(), style) is False, f"{style}에서 아직 붙는다"


def test_설정이_없으면_켬이_기본(monkeypatch):
    """읽기 실패·미설정은 종전 동작(켬)으로 떨어져야 한다 — 회귀 0."""
    class _Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("DB 없음")
    monkeypatch.setattr("shopping_shorts.store.Store", _Boom)
    S._HOOK_OPENER_CACHE.update(t=0.0)
    assert S.hook_opener_on() is True


def test_판정은_한_곳뿐이다():
    """호출부가 제 나름대로 판정하면 두 벌이 된다(0순위-B)."""
    import inspect
    src = inspect.getsource(S.hook_opener_missing)
    assert "hook_opener_on()" in src, "스위치를 안 본다"


# ── 고객별 설정(2026-09-01 사장님 "3번") ────────────────────────────────────
def test_고객이_정하면_그_값이_이긴다(monkeypatch):
    """① 고객 설정 → ② 사장님 기본값 → ③ 켬. 고객 값이 있으면 기본값을 안 본다."""
    monkeypatch.setattr(S, "hook_opener_default", lambda: True)

    class _St:
        def __init__(self, *a, **k): pass
        def get_pref(self, key, customer_id=None, default=None): return "off"
    monkeypatch.setattr("shopping_shorts.store.Store", _St)
    S._HOOK_OPENER_CACHE.update(t=0.0)
    assert S.hook_opener_on(customer_id=7) is False


def test_고객이_안_정했으면_사장님_기본값을_따른다(monkeypatch):
    monkeypatch.setattr(S, "hook_opener_default", lambda: False)

    class _St:
        def __init__(self, *a, **k): pass
        def get_pref(self, key, customer_id=None, default=None): return None   # 안 정함
    monkeypatch.setattr("shopping_shorts.store.Store", _St)
    assert S.hook_opener_on(customer_id=7) is False


def test_부르는_쪽이_정한_값이_그대로_쓰인다():
    """생성 중 DB를 여러 번 읽지 않게 위에서 한 번 판정해 내려보낸다."""
    b = [{"narration": "다이소에서 이걸 봤어요."}]
    assert S.hook_opener_missing(b, None, on=False) is False
    assert S.hook_opener_missing(b, None, on=True) is True


def test_배선이_끊기지_않았다():
    """mix_pipeline → build_scene_first_plan → _single_source_candidates → hook_opener_missing.
    한 군데만 빠져도 고객 설정이 조용히 무시된다."""
    import inspect
    from shopping_shorts import edit_plan, mix_pipeline
    assert "hook_opener=_hook_opener" in inspect.getsource(mix_pipeline._plan_and_tts)
    assert "hook_opener=None" in inspect.getsource(edit_plan.build_scene_first_plan)
    assert "hook_opener=hook_opener" in inspect.getsource(edit_plan.build_scene_first_plan)
    assert "on=hook_opener" in inspect.getsource(edit_plan._single_source_candidates)


# ── 대본을 끄면 음성도 같이 꺼진다(2026-09-01 사장님 "동시에 꺼지고 켜지고") ──────────
# ★감탄사를 붙이는 자리가 **두 곳**이었다:
#     ① 대본  single_source.add_hook_opener   → "와, " / "여러분 "   (자막에 남는다)
#     ② 음성  naturalize fillers(훅 칸만)     → 와/오/우와/헐/이야   (자막에 안 남는다)
#   ①만 끄면 ②가 다시 붙여 **자막에 없는 말이 들린다**(실측으로 확인한 뒤 묶었다).
def test_스위치를_끄면_TTS_추임새도_안_붙는다():
    import copy
    from shopping_shorts.narration_naturalize import merge_profile, naturalize_detail
    prof = copy.deepcopy(merge_profile(None))
    prof["fillers"]["on"] = False            # synthesize_line이 스위치 off일 때 하는 일
    d = naturalize_detail("다이소에서 봤어요.", prof, beat_role="훅")
    assert d["applied"].get("fillers", 0) == 0, d["text"]
    assert "와," not in d["text"], d["text"]


def test_스위치가_켜져_있으면_종전대로_붙는다():
    from shopping_shorts.narration_naturalize import naturalize_detail
    d = naturalize_detail("다이소에서 봤어요.", None, beat_role="훅")
    assert d["applied"].get("fillers", 0) == 1, d["text"]


def test_대본이_이미_부름말로_열었으면_음성이_또_안_붙인다():
    """실측: 대본 "여러분 다이소…"에 TTS가 "와, 여러분 다이소…"를 만들었다.
    멱등 가드가 **1~2자+쉼표**만 봐서 "여러분 "(3자+공백)을 못 잡았다."""
    from shopping_shorts.narration_naturalize import naturalize_detail
    d = naturalize_detail("여러분 다이소 가면 이거 무조건 사오세요.", None, beat_role="훅")
    assert d["applied"].get("fillers", 0) == 0, d["text"]
    assert not d["text"].replace("[curious] ", "").startswith("와"), d["text"]


def test_음성쪽_배선이_끊기지_않았다():
    import inspect
    from shopping_shorts import mix_pipeline
    src = inspect.getsource(mix_pipeline.synthesize_line)
    assert "hook_opener=None" in inspect.signature(mix_pipeline.synthesize_line).__str__() \
        or "hook_opener" in src, "음성 쪽이 스위치를 안 본다"
    assert '["on"] = False' in src, "스위치를 꺼도 fillers가 안 꺼진다"
