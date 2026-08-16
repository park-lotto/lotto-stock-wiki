# -*- coding: utf-8 -*-
"""쿠팡 상품 재료 선수집 (2026-08-17 사장님 설계).

1단계에서 영상 분석이 끝난 자리에 상세·리뷰 수집을 걸어둔다 — 대본 만들 때 긁으면
2~3분을 그 자리에서 기다리게 되기 때문이다.

★조용히 안 도는 것이 이 기능의 유일한 실패 방식이다(큐에만 들어가고 아무도 모름).
  그래서 '언제 걸리고 언제 안 걸리는지'를 여기서 못 박는다.
"""
import json

from shopping_shorts import coupang_relay
from shopping_shorts.app import _queue_product_prefetch


class _Store:
    def __init__(self, settings=None):
        self.settings = dict(settings or {})

    def get_setting(self, k, default=None):
        return self.settings.get(k, default)

    def set_setting(self, k, v):
        self.settings[k] = v


def _done(category, product, code="v1", status="added"):
    return [{"status": status, "code": code, "category": category,
             "script": {"source_brief": {"product": product}}}]


def _drain():
    """큐를 비우고 들어간 일감을 돌려준다(테스트끼리 안 섞이게)."""
    out = []
    while True:
        j = coupang_relay.QUEUE.take(0)
        if j is None:
            return out
        out.append(j)


class TestQueueProductPrefetch:
    def setup_method(self):
        _drain()

    def test_홈템은_큐에_걸린다(self):
        st = _Store()
        _queue_product_prefetch(st, _done("홈템", "실리콘 접이식 도마"), cid=0)
        jobs = _drain()
        assert len(jobs) == 1
        assert jobs[0].kind == "detail"
        assert jobs[0].payload["product"] == "실리콘 접이식 도마"
        assert st.get_setting("product_prefetch_v1") == "queued"

    def test_레시피_뷰티는_건너뛴다(self):
        """사장님 지시 — 상품 관련만. 팔 물건이 없는 콘텐츠는 긁을 이유가 없다."""
        for cat in ("레시피", "뷰티"):
            _queue_product_prefetch(_Store(), _done(cat, "치아바타"), cid=0)
        assert _drain() == []

    def test_제품명을_못_잡았으면_안_건다(self):
        _queue_product_prefetch(_Store(), _done("홈템", ""), cid=0)
        assert _drain() == []

    def test_분석_실패한_영상은_안_건다(self):
        _queue_product_prefetch(_Store(), _done("홈템", "도마", status="failed_empty"), cid=0)
        assert _drain() == []

    def test_같은_영상을_두_번_긁지_않는다(self):
        """쿠팡을 반복해 두들기면 소프트 차단에 걸린다(검색 쪽에서 이미 겪은 함정)."""
        st = _Store({"product_prefetch_v1": "queued"})
        _queue_product_prefetch(st, _done("홈템", "도마"), cid=0)
        assert _drain() == []


class TestRelayQueueAsync:
    def setup_method(self):
        _drain()

    def test_결과가_오면_콜백이_돈다(self):
        got = {}
        coupang_relay.QUEUE.submit_async(
            "detail", {"shortcode": "abc"}, q="도마",
            on_done=lambda payload, meta: got.update(payload=payload, meta=meta))
        job = coupang_relay.QUEUE.take(0)
        assert job is not None
        coupang_relay.QUEUE.complete(job.id, {"ok": True, "facts": {"specs": ["20cm"]}})
        assert got["payload"]["facts"]["specs"] == ["20cm"]
        assert got["meta"]["shortcode"] == "abc"

    def test_콜백이_터져도_릴레이는_계속_간다(self):
        """저장 실패로 릴레이를 세우면 뒤 일감이 통째로 막힌다."""
        def _boom(payload, meta):
            raise RuntimeError("저장 실패")
        coupang_relay.QUEUE.submit_async("detail", {}, q="x", on_done=_boom)
        job = coupang_relay.QUEUE.take(0)
        assert coupang_relay.QUEUE.complete(job.id, {"ok": True}) is True

    def test_검색_일감은_종전대로(self):
        """회귀 0 — kind를 안 주면 search다."""
        import threading
        res = {}

        def _run():
            res["r"] = coupang_relay.QUEUE.submit("도마", 5, timeout=3)
        t = threading.Thread(target=_run)
        t.start()
        job = None
        for _ in range(20):
            job = coupang_relay.QUEUE.take(0)
            if job:
                break
        assert job is not None and job.kind == "search" and job.q == "도마"
        coupang_relay.QUEUE.complete(job.id, {"ok": True, "items": [1]})
        t.join(timeout=3)
        assert res["r"]["items"] == [1]


class TestPrefetchedFactsForJob:
    def test_캐시에서_꺼낸다(self):
        from shopping_shorts.app import _prefetched_facts_for_job
        st = _Store({"product_facts_lens_tiktok_123":
                     json.dumps({"facts": {"specs": ["볼펜 65자루"]}}, ensure_ascii=False)})
        job = {"urls": ["https://www.tiktok.com/@a/video/123"]}
        assert _prefetched_facts_for_job(job, st)["specs"] == ["볼펜 65자루"]

    def test_없으면_빈_dict(self):
        from shopping_shorts.app import _prefetched_facts_for_job
        assert _prefetched_facts_for_job({"urls": ["https://x/1"]}, _Store()) == {}

    def test_깨진_캐시는_무시(self):
        from shopping_shorts.app import _prefetched_facts_for_job
        st = _Store({"product_facts_123": "{깨진"})
        assert _prefetched_facts_for_job({"urls": ["https://www.tiktok.com/@a/video/123"]}, st) == {}
