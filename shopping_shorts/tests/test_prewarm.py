"""담기 시 사전분석 예열(2026-07-30) — 설계 §5 검증항목.

여기서 못 박는 것:
  · 워커 TASKS에 "prewarm"이 있다(배선 누락 방지 — 없으면 큐에 쌓이고 아무도 안 집는다).
  · 유효 캐시가 있으면 추출을 안 태운다(제미니 재과금 방지).
  · 래치(produce_autoload)가 걸린 영상은 스킵한다(무한루프·크레딧 소모 사고 계보).
  · full_text가 비면 저장하지 않는다(빈 대본 영구 캐시 사고 방지).
  · 일일 상한을 넘으면 스킵한다(담기 남발 방어).
  · 성공 시 script_extracts 캐시 + 구조분석이 둘 다 채워진다(제작소 1단계가 읽는 것).
  · 큐 중복 방지(queue_has_pending).
"""
import pytest

from shopping_shorts import prewarm, worker
from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "t.db")


@pytest.fixture()
def gate(monkeypatch):
    """유료게이트를 통과시키는 스텁 + 환불 호출 기록."""
    calls = {"refund": 0, "count": 0}

    def _count(cid, op):
        calls["count"] += 1
        return True

    def _refund(cid, op):
        calls["refund"] += 1

    monkeypatch.setattr(prewarm, "_gate",
                        lambda: (_count, _refund, lambda op: None, lambda op: False))
    return calls


def _stub_pipeline(monkeypatch, full_text="여름에 이거 하나면 끝나요", structure=None):
    """다운로드·추출·구조분석을 전부 스텁한다(실제 ffmpeg·제미니 없이)."""
    import shopping_shorts.media_download as md
    import shopping_shorts.script_extract as se
    import shopping_shorts.structure_analyze as sa
    monkeypatch.setattr(md, "download_any", lambda url, d: ("/tmp/x.mp4", ""))
    monkeypatch.setattr(se, "extract_auto", lambda p, code, caption="": {
        "full_text": full_text, "segments": [{"seg_id": f"{code}-0", "start": 0.0,
                                              "end": 1.0, "text": full_text}]})
    monkeypatch.setattr(sa, "analyze_structure",
                        lambda t: structure if structure is not None else {"hook_type": "공감형"})


def test_worker_has_prewarm_task():
    """배선 누락 방지 — 큐에 넣는 task 이름과 워커 키가 일치해야 한다."""
    assert "prewarm" in worker.TASKS


def test_prewarm_fills_extract_cache_and_structure(store, gate, monkeypatch):
    _stub_pipeline(monkeypatch)
    st = prewarm.run_prewarm("sc1", "https://www.instagram.com/reel/a/",
                             db_path=_p(store), customer_id="0")
    assert st == "done"
    ex = store.get_extract("sc1")
    assert (ex or {}).get("full_text")
    assert (ex or {}).get("structure") == {"hook_type": "공감형"}
    assert gate["refund"] == 0


def test_prewarm_skips_when_cache_valid(store, gate, monkeypatch):
    """이미 대본이 있으면 추출을 태우지 않는다 — 태우면 예외로 터뜨려 잡는다."""
    store.save_script("sc2", {"full_text": "있음", "segments": []})
    import shopping_shorts.media_download as md
    monkeypatch.setattr(md, "download_any",
                        lambda *a, **k: pytest.fail("캐시가 있는데 다운로드를 태웠다"))
    _stub_pipeline(monkeypatch)
    monkeypatch.setattr(md, "download_any",
                        lambda *a, **k: pytest.fail("캐시가 있는데 다운로드를 태웠다"))
    assert prewarm.run_prewarm("sc2", "https://x/", db_path=_p(store)) == "already"
    assert gate["count"] == 0


def test_prewarm_respects_latch(store, gate, monkeypatch):
    """상한(3회)까지 시도한 영상은 다시 태우지 않는다 — 1회는 재시도 허용.

    2026-08-04: 임계 1→3. 인스타 일시 실패 1번으로 영구 래치돼 재담기가
    조용히 스킵되던 실사고(DQohOUqgdRt) 재발 방지."""
    for _ in range(prewarm._PREWARM_MAX_ATTEMPTS):
        store.autoload_mark_attempt("sc3")
    _stub_pipeline(monkeypatch)
    assert prewarm.run_prewarm("sc3", "https://x/", db_path=_p(store)) == "skipped_latched"
    assert gate["count"] == 0
    # 상한 미만이면 재시도된다(= skipped_latched가 아니다)
    store.autoload_mark_attempt("sc3b")
    assert prewarm.run_prewarm("sc3b", "https://x/", db_path=_p(store)) != "skipped_latched"


def test_prewarm_does_not_save_empty_text(store, gate, monkeypatch):
    """전사 결과가 비면 저장 금지 — 저장하면 '대본 없음'이 영구 캐시된다."""
    _stub_pipeline(monkeypatch, full_text="   ")
    assert prewarm.run_prewarm("sc4", "https://x/", db_path=_p(store)) == "failed_empty"
    assert store.get_extract("sc4") is None
    assert gate["refund"] == 1               # 실패는 환불


def test_prewarm_daily_cap(store, gate, monkeypatch):
    """담기 남발 방어 — 상한을 넘으면 스킵."""
    monkeypatch.setattr(prewarm, "_PREWARM_DAILY_CAP", 1)
    _stub_pipeline(monkeypatch)
    assert prewarm.run_prewarm("sc5", "https://x/", db_path=_p(store)) == "done"
    assert prewarm.run_prewarm("sc6", "https://x/", db_path=_p(store)) == "skipped_cap"


def test_prewarm_structure_failure_is_harmless(store, gate, monkeypatch):
    """구조분석(제미니)이 죽어도 대본 캐시는 남는다 — 로딩 절감의 대부분이 여기 있다."""
    _stub_pipeline(monkeypatch)
    import shopping_shorts.structure_analyze as sa

    def _boom(t):
        raise RuntimeError("503")
    monkeypatch.setattr(sa, "analyze_structure", _boom)
    assert prewarm.run_prewarm("sc7", "https://x/", db_path=_p(store)) == "done"
    assert (store.get_extract("sc7") or {}).get("full_text")


def test_queue_has_pending_dedupes(store):
    store.enqueue("prewarm", {"shortcode": "dup1", "url": "u"})
    assert store.queue_has_pending("prewarm", "shortcode", "dup1") is True
    assert store.queue_has_pending("prewarm", "shortcode", "other") is False
    assert store.queue_has_pending("mix", "shortcode", "dup1") is False


def _p(store):
    """테스트 Store가 쓰는 DB 경로(생성자 인자 그대로)."""
    return store.db_path


def test_silent_video_cache_hits(store, gate, monkeypatch):
    """★무자막(말 없음·화면 태깅만) 저장본도 유효 캐시다(2026-08-16 리뷰에서 발견).

    저장 기준은 has_usable_result(말 **또는** 화면)로 바뀌었는데 캐시 판정이
    full_text만 보면, 무자막 영상은 저장돼 있어도 매번 캐시미스로 제미니를 다시
    태우고 시도 횟수만 쌓여 결국 영구 래치된다(서버 실측: lens_tiktok_1cfb55 —
    태깅 저장본이 있는데 attempts=2까지 다시 탔다).
    """
    store.save_script("sil1", {"full_text": "", "segments": [
        {"seg_id": "sil1-0", "start": 0.0, "end": 1.0, "text": "",
         "scene_desc": "제품을 눌러 보여준다"}]})

    import shopping_shorts.media_download as md

    def boom(*a, **k):
        raise AssertionError("유효 캐시가 있는데 다운로드·추출을 다시 태웠다")

    monkeypatch.setattr(md, "download_any", boom)
    got = prewarm.run_prewarm("sil1", "https://x", db_path=store.db_path)
    assert got == "already"
    assert gate["count"] == 0, "캐시 히트에 크레딧이 나가면 안 된다"
