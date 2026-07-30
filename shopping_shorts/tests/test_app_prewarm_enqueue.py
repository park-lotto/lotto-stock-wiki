"""담기(바구니 토글) → 예열 큐 적재 배선 검증(2026-07-30).

왜 앱 레벨로도 박나: prewarm 모듈만 맞아도 **담기가 큐에 안 넣으면 아무 일도 안 난다**.
오늘 실측한 사고 모양이 정확히 그거였다(설계 ①이 없어 담긴 3개가 그대로 방치).
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _client(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    monkeypatch.setattr(appmod, "DB_PATH", db)
    # 담기의 기존 백그라운드 메타보강은 네트워크라 무력화(이 테스트 관심사 아님).
    monkeypatch.setattr(appmod, "_enrich_grab", lambda *a, **k: None)
    return TestClient(appmod.app), db


def _toggle(c, sc="sc_new", url="https://www.instagram.com/reel/abc/"):
    return c.post("/api/mix/basket/toggle", json={"shortcode": sc, "url": url, "name": "n"})


def test_basket_toggle_enqueues_prewarm(tmp_path, monkeypatch):
    c, db = _client(tmp_path, monkeypatch)
    assert _toggle(c).status_code == 200
    assert Store(db).queue_has_pending("prewarm", "shortcode", "sc_new") is True


def test_basket_toggle_skips_when_cache_exists(tmp_path, monkeypatch):
    """이미 대본이 있으면 큐에 넣지 않는다(제미니 재과금 방지)."""
    c, db = _client(tmp_path, monkeypatch)
    Store(db).save_script("sc_cached", {"full_text": "있음", "segments": []})
    assert _toggle(c, sc="sc_cached").status_code == 200
    assert Store(db).queue_has_pending("prewarm", "shortcode", "sc_cached") is False


def test_basket_toggle_twice_enqueues_once(tmp_path, monkeypatch):
    """담기취소→재담기 연타로 큐가 부풀지 않는다."""
    c, db = _client(tmp_path, monkeypatch)
    _toggle(c)                       # 담김 → 적재
    _toggle(c)                       # 담기취소(in=False) → 적재 없음
    _toggle(c)                       # 재담기 → 이미 pending이라 스킵
    with Store(db)._conn() as conn:
        n = conn.execute("SELECT COUNT(*) FROM job_queue WHERE task='prewarm'").fetchone()[0]
    assert n == 1


def test_basket_toggle_without_url_does_not_enqueue(tmp_path, monkeypatch):
    """URL이 없으면 워커가 다운로드할 게 없다 — 큐를 더럽히지 않는다."""
    c, db = _client(tmp_path, monkeypatch)
    assert _toggle(c, sc="sc_nourl", url="").status_code == 200
    assert Store(db).queue_has_pending("prewarm", "shortcode", "sc_nourl") is False
