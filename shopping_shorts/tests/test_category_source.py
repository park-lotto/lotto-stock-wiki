"""카테고리 출처(category_source)와 Gemini 승격 — I-3 실체 대응(2026-07-16).

배경(라이브 실측): categorize()의 키워드 추측 정확도가 13건 중 7건(54%)인데,
그 추측이 학습 코퍼스의 다수를 차지한다(생활용품 79%·인테리어 80%·가전 100%가
추측). element_raw_values가 script_wiki UNION script_extracts로 둘 다 읽기 때문.
같은 13건에 Gemini를 물으니 10건(77%) — 키워드가 틀린 6건 중 4건을 바로잡았다.

Gemini는 이미 analyze_structure로 같은 full_text를 보고 있으므로, 그 호출에
product_category를 얹으면 추가 비용이 사실상 0이다.

우선순위: user > gemini > keyword.
- 사용자가 고른 값은 무엇도 덮지 않는다(교정이 최종 권위).
- 키워드 추측은 Gemini 결과가 오면 승격된다.
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.app import app
from shopping_shorts.store import Store


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app), Store(db)


def test_gemini_category_upgrades_a_keyword_guess(monkeypatch, tmp_path):
    """키워드 추측은 Gemini 결과로 승격된다(54%→77% 이득을 실제로 먹는 지점)."""
    db = tmp_path / "t.db"
    store = Store(db)
    store.save_script("ABC", {"full_text": "감자 으깨서 튀겨요", "segments": []}, category="인테리어")
    store.update_extract_category("ABC", "인테리어", source="keyword")

    monkeypatch.setattr(app_module, "analyze_structure",
                        lambda text: {"hook_type": "공감형", "product_category": "레시피"})

    app_module._backfill_extract_structure(db, "ABC", "감자 으깨서 튀겨요")

    cached = store.get_extract("ABC")
    assert cached["category"] == "레시피", "키워드 추측이 Gemini 결과로 안 바뀜"
    assert cached["category_source"] == "gemini"


def test_gemini_never_overwrites_a_user_choice(monkeypatch, tmp_path):
    """사용자가 고른 값은 Gemini가 덮지 않는다 — 교정이 최종 권위다."""
    db = tmp_path / "t.db"
    store = Store(db)
    # 픽스처는 살아있는 어휘로 — 옛 '생활용품'을 쓰면 홈템 마이그레이션이 값을 바꿔
    # 이 테스트가 엉뚱한 이유로 죽는다(2026-07-16 실제로 겪음).
    store.save_script("ABC", {"full_text": "감자 으깨서 튀겨요", "segments": []}, category="가전")
    store.update_extract_category("ABC", "가전", source="user")

    monkeypatch.setattr(app_module, "analyze_structure",
                        lambda text: {"hook_type": "공감형", "product_category": "레시피"})

    app_module._backfill_extract_structure(db, "ABC", "감자 으깨서 튀겨요")

    cached = store.get_extract("ABC")
    assert cached["category"] == "가전", "사용자 교정을 AI가 덮었다 — 교정 경로가 무의미해짐"
    assert cached["category_source"] == "user"


def test_body_category_from_user_is_marked_as_user_source(monkeypatch, tmp_path):
    """모달 드롭다운으로 넘어온 값은 user로 기록된다(그래야 위 보호가 걸린다)."""
    client, store = _client(monkeypatch, tmp_path)
    store.save_script("ABC", {"full_text": "원본", "segments": []}, category=None)

    r = client.post("/api/produce/extract_from_url",
                    json={"url": "https://www.instagram.com/reel/ABC/",
                          "shortcode": "ABC", "category": "뷰티"})
    assert r.status_code == 200
    assert store.get_extract("ABC")["category_source"] == "user"


def test_unknown_gemini_category_is_ignored(monkeypatch, tmp_path):
    """통제 어휘 밖 값은 무시한다 — 고아 학습 버킷을 만들지 않는다(I-4와 같은 취지)."""
    db = tmp_path / "t.db"
    store = Store(db)
    store.save_script("ABC", {"full_text": "원본", "segments": []}, category="레시피")
    store.update_extract_category("ABC", "레시피", source="keyword")

    monkeypatch.setattr(app_module, "analyze_structure",
                        lambda text: {"hook_type": "공감형", "product_category": "요리"})

    app_module._backfill_extract_structure(db, "ABC", "원본")

    cached = store.get_extract("ABC")
    assert cached["category"] == "레시피", "통제 어휘 밖 값이 DB에 들어감"
    assert cached["category_source"] == "keyword"
