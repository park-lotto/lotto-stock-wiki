"""옛 캐시(change 필드 없음) 승격 판정 — mix_pipeline 캐시 재사용 조건과 같은 규칙.

왜: change가 생기기 전 script_extracts 행은 영상의 진짜 포인트를 안 갖고 있다.
그대로 재사용하면 도서관에 쌓인 옛 영상만 영원히 옛 품질로 남는다(2026-07-31).
"""


def _reusable(segs):
    """mix_pipeline._extract의 캐시 채택 조건과 동일한 판정(순수함수 복제)."""
    if segs and not any("change" in s for s in segs):
        segs = None
    return bool(segs and all(s.get("seg_id") for s in segs))


def test_old_cache_without_change_is_rejected():
    assert not _reusable([{"seg_id": "v-0"}, {"seg_id": "v-1"}])


def test_new_cache_with_change_is_reused():
    assert _reusable([{"seg_id": "v-0", "change": "프린팅이 갈라져 있다"},
                      {"seg_id": "v-1", "change": ""}])


def test_empty_change_is_still_new_schema():
    """모델이 '변화 없음'으로 판단한 구간(빈 문자열)은 정상 결과 — 재추출하지 않는다."""
    assert _reusable([{"seg_id": "v-0", "change": ""}])


def test_missing_seg_id_still_rejected():
    assert not _reusable([{"seg_id": "v-0", "change": "x"}, {"change": "y"}])


def test_empty_cache_rejected():
    assert not _reusable([])


def test_mix_pipeline_has_the_guard():
    import inspect
    from shopping_shorts import mix_pipeline
    src = inspect.getsource(mix_pipeline.run_mix_job)
    assert 'not any("change" in s for s in segs)' in src
