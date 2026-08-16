"""대본 재료는 **담긴 영상 전부**여야 한다 — 3단계를 안 돌렸어도.

2026-08-16 사장님 제보: 카메라 영상을 담았는데 대본에 '발뒤꿈치 각질' 얘기가 나왔다.
실측 work ba20ea764254의 재료는 세그0 / 20자 / 216자 세 편이었는데, 화면은
"대본 1편(20자)"이라 떴다. 재료가 job(3단계 매칭 결과)에서만 나오는데 1단계에서
담고 바로 2단계로 가면 job이 없어, 씨앗 한 편(하필 20자)만 실렸던 것이다.
모자란 만큼 모델이 지어냈다.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from shopping_shorts.app import _extract_from_work, _sources_for_generate


class _Store:
    def __init__(self, handoff, scripts):
        self._h, self._s = handoff, scripts

    def get_produce_work(self, work_id, customer_id=0):
        return {"state": {"handoff": self._h}}

    def get_script(self, sc):
        return self._s.get(sc)


def test_collects_every_used_video():
    st = _Store(
        [{"shortcode": "a", "useFootage": True},
         {"shortcode": "b", "useFootage": True},
         {"shortcode": "c", "useFootage": False}],          # 화면에 안 쓰는 것은 제외
        {"a": {"full_text": "가" * 20, "segments": [{"text": "가"}]},
         "b": {"full_text": "나" * 216, "segments": [{"text": "나"}]},
         "c": {"full_text": "다" * 50}},
    )
    got = _extract_from_work("w1", 0, st)
    assert set(got) == {"a", "b"}


def test_skips_unanalyzed():
    """분석이 아직 안 된 영상은 넣지 않는다(빈 재료가 자리만 차지하면 안 된다)."""
    st = _Store([{"shortcode": "a", "useFootage": True},
                 {"shortcode": "z", "useFootage": True}],
                {"a": {"segments": [{"text": "가"}], "full_text": "가"}, "z": {}})
    assert set(_extract_from_work("w1", 0, st)) == {"a"}


def test_sources_use_all_collected_material():
    """모은 재료가 실제로 생성 입력에 들어간다 — 여기서 끊기면 앞이 다 헛일이다."""
    item = {"full_text": "씨앗", "structure": {}, "category": "홈템"}
    job = {"extract": {"a": {"full_text": "가" * 20}, "b": {"full_text": "나" * 216}}}
    srcs = _sources_for_generate(item, job)
    texts = [s["full_text"] for s in srcs]
    assert "나" * 216 in texts, "긴 재료가 빠지면 모델이 지어낸다"
    assert len(texts) >= 2


def test_missing_work_id_is_harmless():
    """실패해도 생성은 막지 않는다(재료가 줄 뿐)."""
    class Boom:
        def get_produce_work(self, *a, **k):
            raise RuntimeError("DB 오류")
    assert _extract_from_work("w1", 0, Boom()) == {}
