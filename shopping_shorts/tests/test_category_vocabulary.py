"""Task 8 — 카테고리를 보이고 고칠 수 있게(I-3·I-4) + 구조분석 백그라운드화(I-2) 검증(2026-07-15).

- /api/wiki/categories: 통제 어휘(categorize.KEYWORDS 키 + DB 실측값) 반환
- Store.update_extract_category: category만 UPDATE, script_json은 절대 안 건드림
  (C-1 사고 — save_script(code, cached, category=...)로 원본을 통째로 재기록하는
  패턴이 원본 소실을 일으켰다. 이번엔 UPDATE 전용 메서드로 원본 보존을 못박는다.)
- 캐시히트 시 analyze_structure가 응답 경로에서 동기 호출되지 않는다(BackgroundTasks로 미룸).
"""
from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "reference.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


# ---------------------------------------------------------------------------
# /api/wiki/categories — 통제 어휘
# ---------------------------------------------------------------------------

def test_categories_endpoint_returns_controlled_vocabulary(monkeypatch, tmp_path):
    client, st = _client(monkeypatch, tmp_path)
    r = client.get("/api/wiki/categories")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] is True
    cats = set(d["categories"])
    # categorize.py의 KEYWORDS 키 — 통제 어휘 실측(브리프 §통제 어휘)
    assert {"인테리어", "레시피", "생활용품", "가전", "뷰티"} <= cats


def test_categories_endpoint_includes_db_values_not_in_keywords(monkeypatch, tmp_path):
    """DB에 옛 값('기타' 등 KEYWORDS 밖 값)이 있어도 목록에 포함돼 선택 가능해야 한다."""
    client, st = _client(monkeypatch, tmp_path)
    st.save_script("OLD", {"full_text": "본문", "segments": []}, category="기타")
    r = client.get("/api/wiki/categories")
    assert r.status_code == 200, r.text
    assert "기타" in r.json()["categories"]


def test_categories_endpoint_sorted_no_duplicates(monkeypatch, tmp_path):
    client, st = _client(monkeypatch, tmp_path)
    st.save_script("A", {"full_text": "", "segments": []}, category="레시피")  # KEYWORDS와 중복
    r = client.get("/api/wiki/categories")
    cats = r.json()["categories"]
    assert cats == sorted(cats)
    assert len(cats) == len(set(cats))


# ---------------------------------------------------------------------------
# Store.update_extract_category — 원본 텍스트 보존(C-1 회귀방지)
# ---------------------------------------------------------------------------

def test_update_extract_category_preserves_script_json(tmp_path):
    """category만 바뀌고 script_json(원본 대본 텍스트)은 글자 하나도 안 바뀐다."""
    st = Store(tmp_path / "t.db")
    original = {"full_text": "감자전 만드는 법, 아주 자세한 원본 대본입니다.",
                "segments": [{"text": "감자전 만드는 법", "start": 0.0, "end": 1.2}]}
    st.save_script("ABC", original, category=None)

    st.update_extract_category("ABC", "레시피")

    saved = st.get_extract("ABC")
    assert saved["category"] == "레시피"
    assert saved["full_text"] == original["full_text"]
    assert saved["segments"] == original["segments"]


def test_update_extract_category_does_not_touch_structure(tmp_path):
    """구조분석 결과도 건드리지 않는다 — UPDATE 대상은 category 컬럼뿐."""
    st = Store(tmp_path / "t.db")
    st.save_script("ABC", {"full_text": "본문", "segments": []}, category="기타")
    st.save_extract_structure("ABC", {"hook": "질문형"})

    st.update_extract_category("ABC", "가전")

    saved = st.get_extract("ABC")
    assert saved["category"] == "가전"
    assert saved["structure"] == {"hook": "질문형"}


def test_update_extract_category_on_unknown_shortcode_is_noop(tmp_path):
    """존재하지 않는 shortcode는 조용히 무시(UPDATE는 매치 0건이면 아무 일도 안 함)."""
    st = Store(tmp_path / "t.db")
    st.update_extract_category("NOPE", "레시피")  # 예외 없이 통과해야 함
    assert st.get_extract("NOPE") is None


# ---------------------------------------------------------------------------
# I-2 — 캐시히트 시 analyze_structure는 응답 경로에서 동기 호출되지 않는다
# ---------------------------------------------------------------------------

def test_cache_hit_does_not_call_analyze_structure_synchronously(monkeypatch, tmp_path):
    """캐시히트인데 structure가 없는 경우, analyze_structure를 BackgroundTasks로
    미룬다 — TestClient가 add_task 자체를 실행하기 전에 가로채 호출 여부를 확인한다.
    (BackgroundTasks.add_task를 패치해 실제 태스크 실행을 막고, 대신 우리가 원하는
    함수가 '나중에 하도록 등록됐는지'만 검증 — 응답 생성 시점엔 analyze_structure가
    호출되지 않았어야 한다.)"""
    calls = []

    def _boom(*a, **kw):
        calls.append((a, kw))
        raise AssertionError("analyze_structure가 응답 경로에서 동기 호출됨(I-2 위반)")
    monkeypatch.setattr(app_module, "analyze_structure", _boom)

    captured_tasks = []

    def _fake_add_task(self, func, *a, **kw):
        captured_tasks.append((func, a, kw))
    monkeypatch.setattr(app_module.BackgroundTasks, "add_task", _fake_add_task)

    client, st = _client(monkeypatch, tmp_path)
    st.save_script("NOSTRUCT", {"full_text": "본문", "segments": []}, category="레시피")

    r = client.post("/api/produce/extract_from_url",
                     json={"url": "https://x/reel/NOSTRUCT", "shortcode": "NOSTRUCT"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["cached"] is True
    assert d["structure"] is None          # 응답은 즉시(구조분석 기다리지 않음)
    assert calls == []                     # analyze_structure는 응답 경로에서 호출 안 됨
    assert len(captured_tasks) == 1        # 대신 백그라운드로 등록됨
    assert captured_tasks[0][0] is app_module._backfill_extract_structure


def test_cache_hit_with_existing_structure_never_schedules_backfill(monkeypatch, tmp_path):
    """이미 구조분석이 돼 있으면 백그라운드 태스크조차 등록하지 않는다(불필요한 재분석 방지)."""
    captured_tasks = []

    def _fake_add_task(self, func, *a, **kw):
        captured_tasks.append((func, a, kw))
    monkeypatch.setattr(app_module.BackgroundTasks, "add_task", _fake_add_task)

    client, st = _client(monkeypatch, tmp_path)
    st.save_script("HAS", {"full_text": "본문", "segments": []}, category="레시피")
    st.save_extract_structure("HAS", {"hook": "훅"})

    r = client.post("/api/produce/extract_from_url",
                     json={"url": "https://x/reel/HAS", "shortcode": "HAS"})
    assert r.status_code == 200, r.text
    assert r.json()["structure"] == {"hook": "훅"}
    assert captured_tasks == []
