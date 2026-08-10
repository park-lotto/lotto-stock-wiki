# -*- coding: utf-8 -*-
"""추출 커버리지 재시도 (2026-08-06).

★사장님 제보: "결과물이 11/14/16초밖에 안 나온다" + "왜 소스가 없나? 원본 순서만
바꾸는 건데" — 맞는 지적이었다. 원본 21.1초가 멀쩡히 있고(오디오도 끝까지 -17.4dB)
담아둔 캐시도 있었는데, **추출이 11.6초까지만 잡아** 뒤 45%가 통째로 날아갔다.

실측(Dbjk5BXToB7 21.1초, 같은 조건 5회): 67% / 95% / 55% / 55% / 55% — 평균 65%.
같은 영상·같은 조건인데 **모델 출력이 확률적으로 흔들린다**(한때 '장면전환 힌트가
범인'이라고 봤으나 표본 1개짜리 오판이었다 — 35.8초 영상은 힌트가 있어야 103%다).

수정: 기준 0.55 → 0.75, 재시도 1회 → 3회(조건을 힌트 on/off로 바꿔가며, 가장 좋은 것 채택).
실측 검증: 수정 후 같은 영상 3회 = 92% / 94% / 94%.
"""
import pytest

from shopping_shorts import mix_pipeline as mp


def test_기준이_절반보다_높다():
    """0.55는 영상 **절반이 날아가도 통과**시키는 기준이었다.
    하필 실패값이 정확히 55.0%(11.6/21.1=0.549)로 찍혀 경계 회색지대에 걸렸다."""
    assert mp._MIN_COVERAGE >= 0.7, "절반 넘게 날아간 추출을 통과시키면 안 된다"


def test_재시도가_한번보다_많다():
    """편차가 55~95%라 한 번 더 뽑는 것만으론 부족하다(실측 분포상 55%가 5회 중 3회)."""
    assert mp._EXTRACT_RETRIES >= 2


def _cov(segs, dur):
    return mp._extract_coverage({"segments": segs}, dur)


def test_커버리지_계산(tmp_path, monkeypatch):
    """구간 합계 / 영상 길이."""
    monkeypatch.setattr(mp, "_video_seconds", lambda p: 20.0)
    segs = [{"start": 0.0, "end": 5.0}, {"start": 5.0, "end": 10.0}]
    assert _cov(segs, "x") == pytest.approx(0.5)


def test_길이를_못재면_판정_생략(monkeypatch):
    """판정 불가를 실패로 오인해 무한 재추출하면 안 된다."""
    monkeypatch.setattr(mp, "_video_seconds", lambda p: None)
    assert _cov([{"start": 0.0, "end": 5.0}], "x") is None


def test_재시도는_조건을_바꿔가며_한다():
    """★같은 조건으로 다시 부르면 같은 실패를 반복한다 — 실측 job 76658a1e71c8은
    재추출에 27초를 쓰고도 55% 그대로였다(순수 낭비)."""
    import inspect
    src = inspect.getsource(mp.run_mix_job)
    assert "use_boundaries=bool(_try % 2)" in src, "재시도마다 조건을 바꿔야 한다"
    assert "_EXTRACT_RETRIES" in src, "여러 번 재시도해야 한다"


def test_더_좋아질_때만_교체():
    """재추출이 더 나쁘면 원래 것을 지켜야 한다(개악 방지)."""
    import inspect
    src = inspect.getsource(mp.run_mix_job)
    assert "cov2 is not None and cov2 > (cov or 0)" in src, \
        "재추출 결과가 더 나을 때만 채택해야 한다"


def test_use_boundaries_인자가_있다():
    """힌트를 끄고 자율 분할로 뽑는 경로가 있어야 재시도가 조건을 바꿀 수 있다."""
    import inspect
    from shopping_shorts import script_extract
    sig = inspect.signature(script_extract.extract_script)
    assert "use_boundaries" in sig.parameters


def test_힌트를_꺼도_cuts를_계산한다():
    """★UnboundLocalError로 추출이 통째로 빈 결과가 됐던 자리 — 모션레벨 계산이
    _cuts·_fps를 쓰므로 힌트를 끄더라도 계산은 해야 한다(실제로 한 번 밟았다)."""
    import inspect
    from shopping_shorts import script_extract
    src = inspect.getsource(script_extract.extract_script)
    head = src.split("base_prompt", 1)[0]
    assert "boundary_hint, _cuts, _fps = _boundary_hint(video_path)" in head, \
        "_boundary_hint는 분기 밖에서 항상 호출해야 한다"
