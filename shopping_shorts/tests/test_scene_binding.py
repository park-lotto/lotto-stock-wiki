"""장면싱크 v7(_pin_screens, 2026-08-10) — 모델 화면 배정 존중 관문.

계약: 불변식(①primary ②비트 간 중복 0 ③같은 소스 시간 비역전 ④인벤토리 안)을
전부 지키면 모델 배정 그대로, 하나라도 어긋나면 _assign_timeline 폴백(종전 100% 동일).
SCENE_BINDING=0이면 무조건 종전 동작.
"""
from pathlib import Path

from shopping_shorts import edit_plan as ep


def _seg(sid, video, start, end, desc="장면"):
    return {"seg_id": sid, "video_id": video, "start": start, "end": end,
            "scene_desc": desc, "text": ""}


def _groups():
    return [
        [_seg("a-0", "a", 0.0, 2.0), _seg("a-1", "a", 2.0, 4.0)],
        [_seg("b-0", "b", 0.0, 2.0), _seg("b-1", "b", 2.0, 4.0)],
        [_seg("a-2", "a", 4.0, 6.0), _seg("b-2", "b", 4.0, 6.0)],
    ]


def _beat(primary, alts=(), narr="대사"):
    return {"beat_idx": 0, "narration": narr, "primary": dict(primary),
            "alternates": [dict(a) for a in alts]}


def _valid_beats():
    return [
        _beat(_seg("a-0", "a", 0.0, 2.0), [_seg("a-1", "a", 2.0, 4.0)]),
        _beat(_seg("b-0", "b", 0.0, 2.0)),
        _beat(_seg("a-2", "a", 4.0, 6.0), [_seg("b-2", "b", 4.0, 6.0)]),
    ]


def test_valid_binding_ok():
    assert ep._model_binding_ok(_valid_beats(), _groups()) is True


def test_duplicate_seg_across_beats_fails():
    beats = _valid_beats()
    beats[1]["alternates"] = [_seg("a-1", "a", 2.0, 4.0)]   # 비트0이 이미 씀
    assert ep._model_binding_ok(beats, _groups()) is False


def test_time_reversal_same_source_fails():
    beats = _valid_beats()
    beats[0]["primary"] = _seg("a-2", "a", 4.0, 6.0)
    beats[2]["primary"] = _seg("a-0", "a", 0.0, 2.0)        # a: 4.0 → 0.0 역전
    assert ep._model_binding_ok(beats, _groups()) is False


def test_seg_outside_inventory_fails():
    beats = _valid_beats()
    beats[1]["primary"] = _seg("zzz-9", "z", 0.0, 2.0)
    assert ep._model_binding_ok(beats, _groups()) is False


def test_missing_primary_fails():
    beats = _valid_beats()
    beats[1]["primary"] = None
    assert ep._model_binding_ok(beats, _groups()) is False
    assert ep._model_binding_ok([], _groups()) is False
    assert ep._model_binding_ok(_valid_beats(), []) is False


def test_pin_screens_keeps_model_binding(monkeypatch):
    monkeypatch.delenv("SCENE_BINDING", raising=False)
    beats = _valid_beats()
    before = [b["primary"]["seg_id"] for b in beats]
    out = ep._pin_screens(beats, _groups())
    assert [b["primary"]["seg_id"] for b in out] == before   # 모델 배정 그대로


def test_pin_screens_falls_back_on_violation(monkeypatch):
    monkeypatch.delenv("SCENE_BINDING", raising=False)
    beats = _valid_beats()
    beats[1]["alternates"] = [_seg("a-0", "a", 0.0, 2.0)]    # 중복 → 폴백
    out = ep._pin_screens(beats, _groups())
    ref = ep._assign_timeline([dict(b, alternates=list(b["alternates"]))
                               for b in _fallback_input()], _groups())
    assert [b["primary"]["seg_id"] for b in out] == [b["primary"]["seg_id"] for b in ref]


def _fallback_input():
    beats = _valid_beats()
    beats[1]["alternates"] = [_seg("a-0", "a", 0.0, 2.0)]
    return beats


def test_env_kill_switch_forces_legacy(monkeypatch):
    monkeypatch.setenv("SCENE_BINDING", "0")
    beats = _valid_beats()
    out = ep._pin_screens(beats, _groups())
    ref = ep._assign_timeline(_valid_beats(), _groups())
    assert [b["primary"]["seg_id"] for b in out] == [b["primary"]["seg_id"] for b in ref]


def test_pin_screens_idempotent(monkeypatch):
    # 2차 호출부(재못박기)가 다시 지나가도 배정이 안 바뀐다.
    monkeypatch.delenv("SCENE_BINDING", raising=False)
    beats = ep._pin_screens(_valid_beats(), _groups())
    again = ep._pin_screens(beats, _groups())
    assert [b["primary"]["seg_id"] for b in again] == [b["primary"]["seg_id"] for b in beats]


def test_wiring_locked():
    src = Path(ep.__file__).read_text(encoding="utf-8")
    assert src.count("_pin_screens(plan[") >= 2          # 두 호출부 모두 관문 경유
    assert "if ping_pong" in src                          # ping_pong은 종전 유지
