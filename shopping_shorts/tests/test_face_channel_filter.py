"""인물(연예인·본인출연) 채널 자동등록 제외 — 2026-08-02 사장님 지시.

썸네일 만장일치(3/3)일 때만 제외한다. 애매한 채널은 남겨 랭킹 지표로 밀리게 한다
— 표본을 넓히는 게 목적이라 '억울한 제외'가 '놓친 제외'보다 비싸다.
판정 실패(None)는 제외하지 않는다 — 키가 잠긴 날 통째로 걸러내는 사고 방지.
"""
import shopping_shorts.discover_jobs as dj
from shopping_shorts import discovery


class _FakeVision:
    """face_forward_vision을 썸네일 URL → 판정으로 흉내낸다."""

    def __init__(self, verdicts):
        self.verdicts = verdicts
        self.calls = 0

    def fetch_thumb_bytes(self, url):
        return b"img" if url else None

    def face_forward_vision(self, img, **kw):
        v = self.verdicts[self.calls]
        self.calls += 1
        return v


def _patch(monkeypatch, verdicts):
    fake = _FakeVision(verdicts)
    monkeypatch.setattr("shopping_shorts.video_analysis.fetch_thumb_bytes",
                        fake.fetch_thumb_bytes, raising=False)
    monkeypatch.setattr("shopping_shorts.video_analysis.face_forward_vision",
                        fake.face_forward_vision, raising=False)
    return fake


def _item(n=3):
    return {"username": "u1", "sample_thumbs": [f"t{i}.jpg" for i in range(n)]}


def test_all_face_is_excluded(monkeypatch):
    """3장 전부 인물 → 제외."""
    _patch(monkeypatch, [True, True, True])
    assert dj._is_face_channel(_item()) is True


def test_majority_face_is_kept(monkeypatch):
    """2/3만 인물이면 남긴다 — 실측 toyland.kr(제품1·얼굴2) 같은 혼합 채널 보호."""
    _patch(monkeypatch, [True, True, False])
    assert dj._is_face_channel(_item()) is False


def test_product_channel_is_kept(monkeypatch):
    _patch(monkeypatch, [False, False, False])
    assert dj._is_face_channel(_item()) is False


def test_vision_failure_never_excludes(monkeypatch):
    """판정 실패(None)가 섞이면 제외하지 않는다 — 키 잠긴 날 전량 제외 방지."""
    _patch(monkeypatch, [True, None, True])
    assert dj._is_face_channel(_item()) is False


def test_single_sample_never_excludes(monkeypatch):
    """표본 1장으로는 채널을 자르지 않는다."""
    _patch(monkeypatch, [True])
    assert dj._is_face_channel(_item(n=1)) is False


def test_no_thumbs_never_excludes(monkeypatch):
    _patch(monkeypatch, [])
    assert dj._is_face_channel({"username": "u1"}) is False


def test_two_samples_unanimous_excludes(monkeypatch):
    """표본이 2장뿐이어도 둘 다 인물이면 제외(만장일치 기준 유지)."""
    _patch(monkeypatch, [True, True])
    assert dj._is_face_channel(_item(n=2)) is True


# ── 표본 수집(_rank_reels) ────────────────────────────────
def test_rank_reels_attaches_sample_thumbs():
    """채널당 썸네일이 대표 릴스에 여러 장 실린다 — _one_per_channel이 1개로
    줄이기 전에 모아야 인물판정 표본이 생긴다."""
    now = discovery.datetime.now(discovery.timezone.utc)
    reels = [{"ownerUsername": "u1", "shortcode": f"s{i}", "commentsCount": 10 - i,
              "displayUrl": f"t{i}.jpg",
              "timestamp": now.isoformat()} for i in range(4)]
    items = discovery._rank_reels(reels, lambda *a, **k: None, lambda *a, **k: None,
                                  now, 48, {})
    assert len(items) == 1                                  # 채널당 1개로 접힘
    assert len(items[0]["sample_thumbs"]) == discovery.FACE_SAMPLE_N   # 표본은 3장
