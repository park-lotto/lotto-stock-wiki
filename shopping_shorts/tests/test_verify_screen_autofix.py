"""자동 교체(2026-09-10) — 어긋난 칸을 맞는 화면으로 바꿔준다.

사장님: "한 칸 옆에꺼를 먼저 배치하는 걸로 왜 안 하는 건데? 답을 알고 두 번 수동으로 하는 거야?"
실측 근거: 어긋난 22칸 중 21칸(95%)은 맞는 화면이 같은 영상 안에 이미 있었다.
"""
import pytest
from shopping_shorts import edit_plan as _ep


class _Store:
    def __init__(self, **kw):
        self._s = kw

    def get_setting(self, k, d=""):
        return self._s.get(k, d)


def _beats():
    return [{"beat_idx": 0, "narration": "스마트폰까지 거치돼서 영화관이 돼요",
             "primary": {"video_id": "v1", "seg_id": "a", "start": 1.0, "end": 2.0,
                         "scene_desc": "빈 뒷좌석"},
             "alternates": [{"seg_id": "b"}], "fit": 5}]


def _seg_map():
    return {"a": {"video_id": "v1", "seg_id": "a", "start": 1.0, "end": 2.0, "scene_desc": "빈 뒷좌석"},
            "b": {"video_id": "v1", "seg_id": "b", "start": 2.0, "end": 3.0, "scene_desc": "폰이 꽂힌 거치대"}}


def _calls(oks):
    """seg_id 순서대로 ok를 돌려주는 가짜 모델. 호출부 형태 그대로(prompt, schema, image)."""
    seen = {"i": 0}

    def image_call(prompt, schema, image):
        v = oks[min(seen["i"], len(oks) - 1)]
        seen["i"] += 1
        return {"ok": v, "why": "테스트"}
    return image_call


@pytest.fixture
def frames(monkeypatch):
    monkeypatch.setattr("shopping_shorts.screen_verify.frame",
                        lambda seg, sid, work: b"\xff\xd8jpeg")


def test_기본은_교체하지_않는다(frames):
    """검증만 켜고 교체는 꺼진 상태 — 종전대로 빨간불만 뜬다(회귀 0)."""
    out = _ep.verify_beat_screens(_beats(), _seg_map(), call=lambda *a: {"ok": True, "why": ""},
                                  store=_Store(screen_verify_enabled="1"),
                                  work=None, image_call=_calls([False]))
    assert out[0].get("auto_swap") is None
    assert out[0]["fit_evidence"] == "verify_failed"


def test_켜면_맞는_화면으로_바꾸고_원본을_남긴다(frames):
    out = _ep.verify_beat_screens(_beats(), _seg_map(), call=lambda *a: {"ok": True, "why": ""},
                                  store=_Store(screen_verify_enabled="1",
                                               screen_verify_autofix="1"),
                                  work=None, image_call=_calls([False, True]))
    b = out[0]
    assert b["primary"]["seg_id"] == "b"            # 후보로 바뀌었다
    assert b["auto_swap"]["from"]["seg_id"] == "a"  # 되돌릴 원본이 남아 있다
    assert "fit_evidence" not in b                  # 고쳤으니 빨간불은 걷힌다


def test_맞는_화면이_없으면_종전대로_빨간불(frames):
    out = _ep.verify_beat_screens(_beats(), _seg_map(), call=lambda *a: {"ok": True, "why": ""},
                                  store=_Store(screen_verify_enabled="1",
                                               screen_verify_autofix="1"),
                                  work=None, image_call=_calls([False]))
    assert out[0].get("auto_swap") is None
    assert out[0]["fit_evidence"] == "verify_failed"
    assert out[0]["primary"]["seg_id"] == "a"       # 화면은 그대로 둔다


def test_이미_쓰는_화면은_후보에서_뺀다():
    """같은 그림이 두 번 나오면 고친 것보다 나쁘다."""
    from shopping_shorts import screen_verify as sv
    cands = sv.candidates(_beats()[0], _seg_map(), used_ids={"b"})
    assert [c["seg_id"] for c in cands] == []
