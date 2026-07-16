"""I-2 잔여: 구조분석 실패에 음성캐싱이 없어 캐시히트마다 Gemini를 다시 부르던 문제.

Task 8이 동기 호출을 BackgroundTasks로 미뤄 '재클릭 즉시화'(클릭당 최대 120s×3)는
이미 해소했다. 남은 건 비용 — 구조분석이 실패하는 영상은 클릭할 때마다 백그라운드에서
Gemini를 또 부른다(원 주석: "다음 클릭이 재시도").

해법: 실패도 시도했다는 표식(structure_analyzed_at)만 남기고 structure_json은 NULL로
둔다. 그러면 ①대화형 경로는 재호출을 멈추고 ②daily_batch의 extracts_missing_structure는
structure_json IS NULL로 고르므로 재시도 책임을 그대로 가져간다({}를 저장하면 백필에서
영구 제외되므로 절대 쓰지 않는다).
"""
import json

from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.app import app
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app), Store(db)


def test_backfill_marks_attempt_on_failure_but_keeps_backfill_eligible(monkeypatch, tmp_path):
    """실패 시: structure_json은 NULL 유지(=daily_batch가 계속 재시도 가능),
    structure_analyzed_at만 찍힌다(=대화형 경로는 이제 안 부른다)."""
    db = tmp_path / "t.db"
    store = Store(db)
    store.save_script("ABC", {"full_text": "원본 대본", "segments": []}, category="레시피")

    monkeypatch.setattr(app_module, "analyze_structure", lambda text: {})  # 실패 재현

    app_module._backfill_extract_structure(db, "ABC", "원본 대본")

    cached = store.get_extract("ABC")
    assert cached["structure"] is None, "실패인데 {}가 저장되면 백필에서 영구 제외된다"
    assert cached["structure_analyzed_at"], "시도 표식이 없으면 클릭마다 Gemini를 또 부른다"
    # daily_batch가 여전히 집어가야 한다(재시도 책임은 배치에 있다)
    assert "ABC" in {t["shortcode"] for t in store.extracts_missing_structure(limit=10)}


def test_cache_hit_does_not_reschedule_analysis_after_a_failed_attempt(monkeypatch, tmp_path):
    """이미 시도해서 실패한 영상은 캐시히트해도 Gemini를 다시 부르지 않는다(I-2 핵심)."""
    client, store = _client(monkeypatch, tmp_path)
    store.save_script("ABC", {"full_text": "원본 대본", "segments": []}, category="레시피")
    store.mark_structure_attempted("ABC")  # 앞선 시도가 실패했던 상태

    calls = []
    monkeypatch.setattr(app_module, "analyze_structure",
                        lambda text: calls.append(text) or {})

    r = client.post("/api/produce/extract_from_url",
                    json={"url": "https://www.instagram.com/reel/ABC/", "shortcode": "ABC"})
    assert r.status_code == 200
    assert r.json()["cached"] is True
    assert calls == [], f"실패 이력이 있는데 또 호출함({len(calls)}회) — 클릭마다 쿼터 소모"


def test_cache_hit_still_schedules_analysis_when_never_attempted(monkeypatch, tmp_path):
    """한 번도 시도 안 한 영상은 종전대로 백그라운드 분석을 예약한다(회귀 가드)."""
    client, store = _client(monkeypatch, tmp_path)
    store.save_script("NEW", {"full_text": "새 대본", "segments": []}, category="레시피")

    monkeypatch.setattr(app_module, "analyze_structure",
                        lambda text: {"hook_type": "공감형"})

    r = client.post("/api/produce/extract_from_url",
                    json={"url": "https://www.instagram.com/reel/NEW/", "shortcode": "NEW"})
    assert r.status_code == 200
    # BackgroundTasks는 TestClient 응답 후 실행된다 — 결과가 저장돼 있어야 한다
    assert store.get_extract("NEW")["structure"] == {"hook_type": "공감형"}
