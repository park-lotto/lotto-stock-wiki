"""수집→대본은행 자동 적재(2026-07-22): 밀도+속도 종합점수 상위 N건만, 한국어 캡션,
캡션 지문 중복 학습 필터. Gemini는 ingest_fn 주입으로 회피."""
from shopping_shorts import pattern_bank


class _FakeStore:
    def __init__(self, existing_full_texts=()):
        self._existing = [{"full_text": t} for t in existing_full_texts]

    def list_pattern_sources(self, limit=1000):
        return self._existing


def _mk(caption, score, url):
    return {"caption": caption, "score": score, "url": url,
            "category": "레시피", "comments": 10, "likes": 5, "views": 100}


def _fake_ingest(store, text, source="collect", url="", product_category=None,
                 category_source=None, perf=None, call=None):
    # 실제 extract_buckets(Gemini) 대신 훅 1개 뽑았다고 가정.
    _fake_ingest.calls.append(text)
    return {"source_id": len(_fake_ingest.calls), "added": 1, "buckets": {"hook": ["훅"]}}


def _run(store, items, **kw):
    _fake_ingest.calls = []
    return pattern_bank.ingest_collected(store, items, ingest_fn=_fake_ingest,
                                         perf_fn=lambda it: None, **kw)


_KR = "이거 진짜 대박인데요 이렇게만 하면 끝나요 여러분 꼭 보세요"   # 한국어 20자+


def test_top_n_by_score():
    items = [_mk(_KR + str(i), score=i / 10, url=f"u{i}") for i in range(5)]
    rep = _run(_FakeStore(), items, top_n=2)
    assert rep["added_sources"] == 2                     # 상위 2건만
    # 점수 높은 순(u4, u3)이 먼저 적재됐다.
    assert _fake_ingest.calls[0].endswith("4")
    assert _fake_ingest.calls[1].endswith("3")


def test_short_or_foreign_caption_skipped():
    items = [_mk("짧음", score=1.0, url="a"),            # 한국어 3자 → 스킵
             _mk("hello world foreign only", score=1.0, url="b"),  # 한글 0 → 스킵
             _mk(_KR, score=0.5, url="c")]
    rep = _run(_FakeStore(), items, top_n=10)
    assert rep["added_sources"] == 1
    assert rep["skipped_short"] == 2


def test_dedup_against_existing_bank():
    # 이미 은행에 같은 내용이 있으면(지문 일치) 재적재 안 함 — CDN url 달라도.
    items = [_mk(_KR, score=1.0, url="new-cdn-url")]
    rep = _run(_FakeStore(existing_full_texts=[_KR]), items, top_n=10)
    assert rep["added_sources"] == 0
    assert rep["skipped_dup"] == 1


def test_dedup_within_batch():
    items = [_mk(_KR, score=0.9, url="u1"), _mk(_KR, score=0.8, url="u2")]  # 같은 캡션
    rep = _run(_FakeStore(), items, top_n=10)
    assert rep["added_sources"] == 1                     # 하나만
    assert rep["skipped_dup"] == 1


def test_by_bucket_aggregated():
    items = [_mk(_KR + "a", 0.9, "u1"), _mk(_KR + "b", 0.8, "u2")]
    rep = _run(_FakeStore(), items, top_n=10)
    assert rep["by_bucket"]["hook"] == 2                 # 소스당 훅 1개 × 2
    assert rep["added_items"] == 2


def _flaky_ingest(store, text, source="collect", url="", product_category=None,
                  category_source=None, perf=None, call=None):
    # 홀수 호출은 Gemini 실패(source_id None) 흉내 → 검열 성공률 측정 검증용.
    _flaky_ingest.n += 1
    if _flaky_ingest.n % 2 == 1:
        return {"source_id": None, "added": 0}          # 429 등으로 빈손
    return {"source_id": _flaky_ingest.n, "added": 3,
            "buckets": {"hook": ["훅"], "spine": {"beat_chain": ["a", "b", "c"]},
                        "adverb": ["진짜", "완전"], "cta": ["댓글"], "ending": ["돼요", "예요"]},
            "hook_bait_blocked": 0}


def test_gemini_audit_success_rate():
    _flaky_ingest.n = 0
    items = [_mk(_KR + str(i), score=i / 10, url=f"u{i}") for i in range(4)]
    rep = pattern_bank.ingest_collected(_FakeStore(), items, ingest_fn=_flaky_ingest,
                                        perf_fn=lambda it: None, top_n=10)
    aud = rep["gemini_audit"]
    assert aud["attempted"] == 4                          # 4건 다 호출
    assert aud["succeeded"] == 2 and aud["failed"] == 2   # 절반만 성공
    assert abs(aud["success_rate"] - 0.5) < 1e-9
    assert aud["health"]["level"] == "🟢"                 # 0.5는 통과선


def test_gemini_audit_hook_spam_ratio():
    def baity(store, text, **kw):
        return {"source_id": 1, "added": 1,
                "buckets": {"hook": ["진짜훅", "댓글에 남겨주세요"],  # 2개 중 1개 스팸
                            "spine": {"beat_chain": ["a", "b", "c"]},
                            "adverb": ["아주"], "cta": ["c"], "ending": ["요"]},
                "hook_bait_blocked": 1}
    items = [_mk(_KR, score=1.0, url="u1")]
    rep = pattern_bank.ingest_collected(_FakeStore(), items, ingest_fn=baity,
                                        perf_fn=lambda it: None, top_n=10)
    aud = rep["gemini_audit"]
    assert aud["hook_total"] == 2 and aud["hook_bait"] == 1
    assert abs(aud["hook_spam_ratio"] - 0.5) < 1e-9
    assert aud["health"]["level"] == "🟡"                 # 스팸 50% > 15%
