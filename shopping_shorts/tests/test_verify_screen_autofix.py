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


def test_다른칸이_쓰는_화면은_빼되_자기_대안은_남긴다():
    """같은 그림이 두 번 나오면 고친 것보다 나쁘다. 단 **자기 칸의 대안**은
    이 칸을 위해 대본이 골라둔 후보라 빼면 안 된다(2026-09-10 페이블 검토 뒤 보정)."""
    from shopping_shorts import screen_verify as sv
    segs = _seg_map()
    segs["c"] = {"video_id": "v1", "seg_id": "c", "start": 3.0, "end": 4.0, "scene_desc": "다른 칸이 씀"}
    cands = [c["seg_id"] for c in sv.candidates(_beats()[0], segs, used_ids={"c"})]
    assert "c" not in cands          # 다른 칸이 쓰는 화면은 뺀다
    assert cands[0] == "b"           # 자기 대안은 첫 후보로 남는다


def test_두번_떨어져도_최초원본으로_되돌아간다(frames):
    """아스트라 검토(2026-09-10): 교체본이 다음 회차에 또 떨어지면 auto_swap.from을
    덮어써 **최초 원본을 잃는다**. 되돌리기가 가리키는 곳은 언제나 사람이 처음 본 화면이다."""
    segs = _seg_map()
    segs["c"] = {"video_id": "v1", "seg_id": "c", "start": 3.0, "end": 4.0, "scene_desc": "세 번째"}
    b = _beats()[0]
    b["auto_swap"] = {"from": {"seg_id": "a", "video_id": "v1"}, "why": "처음", "to_why": ""}
    b["primary"] = dict(b["primary"], seg_id="b")
    out = _ep.verify_beat_screens([b], segs, call=lambda *a: {"ok": True, "why": ""},
                                  store=_Store(screen_verify_enabled="1",
                                               screen_verify_autofix="1"),
                                  work=None, image_call=_calls([False, True]))
    assert out[0]["auto_swap"]["from"]["seg_id"] == "a"     # 최초 원본이 지켜졌다


def test_교체하면_길이보장을_다시_돌린다(frames, monkeypatch):
    """교체는 store의 길이 보정(_fill_beat_screen_time) **뒤에** 일어난다 —
    짧은 컷으로 바뀌면 '화면 길이 >= 대사 길이'가 조용히 깨진다."""
    called = []
    real = _ep._fill_beat_screen_time
    monkeypatch.setattr(_ep, "_fill_beat_screen_time",
                        lambda beats, sm: called.append(1) or real(beats, sm))
    _ep.verify_beat_screens(_beats(), _seg_map(), call=lambda *a: {"ok": True, "why": ""},
                            store=_Store(screen_verify_enabled="1", screen_verify_autofix="1"),
                            work=None, image_call=_calls([False, True]))
    assert called, "화면을 바꿨으면 길이 보장을 다시 돌려야 한다"


def test_계정별로_켤_수_있다(frames):
    """사장님 "내꺼만 다 켜서 해보면 안 되나" — 'cid:0'이면 그 계정에만 걸린다."""
    calls = []

    def img(*a):
        calls.append(1)
        return {"ok": True, "why": ""}

    st = _Store(screen_verify_enabled="cid:0")
    _ep.verify_beat_screens(_beats(), _seg_map(), call=lambda *a: {"ok": True},
                            store=st, work=None, image_call=img, customer_id=7)
    assert calls == [], "다른 계정은 건드리지 않는다"
    _ep.verify_beat_screens(_beats(), _seg_map(), call=lambda *a: {"ok": True},
                            store=st, work=None, image_call=img, customer_id=0)
    assert calls, "지정한 계정에서는 검사한다"
