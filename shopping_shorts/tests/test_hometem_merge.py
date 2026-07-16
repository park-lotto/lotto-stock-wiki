"""옛 '인테리어'+'생활용품' → '홈템' 병합(2026-07-16, 사장님 결정).

왜: 둘을 가르는 기준이 실무에 없었다(인테리어 소품 = 생활용품). 실측으로 Gemini
오답 3건 중 2건이 정확히 이 경계에서 났고, 합치면 같은 13건 정확도가 77% → 92%.

코드만 바꾸면 DB의 옛 라벨이 통제 어휘 밖으로 떨어져(고아 버킷) 학습에서 조용히
빠지므로 기존 데이터도 함께 이관해야 한다. 병합은 비가역이라(합치면 어느 쪽이었는지
정보가 사라진다) 실행 전 서버 백업을 떴다: /tmp/hometem_backup/pre_merge.json
"""
from shopping_shorts.categorize import KEYWORDS, NAME_KEYWORDS, categorize, ctype_of
from shopping_shorts.store import Store


def test_vocabulary_has_hometem_and_not_the_old_pair():
    assert "홈템" in KEYWORDS
    assert "인테리어" not in KEYWORDS, "옛 어휘가 남아 있으면 통제 어휘가 갈라진다"
    assert "생활용품" not in KEYWORDS
    assert "홈템" in NAME_KEYWORDS and "인테리어" not in NAME_KEYWORDS


def test_hometem_absorbs_keywords_from_both_sides():
    """양쪽 키워드를 다 흡수해야 한다 — 한쪽만 남으면 그쪽 영상만 잡힌다."""
    assert categorize("", "셀프인테리어로 집꾸미기 했어요") == "홈템"   # 옛 인테리어
    assert categorize("", "다이소 주방 살림템 추천") == "홈템"          # 옛 생활용품


def test_ctype_of_hometem_is_mixed():
    """옛 인테리어=비법형·생활용품=제품형으로 정반대였다 → 합치면 혼합형이 정직하다."""
    assert ctype_of("홈템") == "혼합형"
    assert ctype_of("레시피") == "비법형"
    assert ctype_of("가전") == "제품형"


def test_migration_moves_old_labels_to_hometem(tmp_path):
    """기존 DB의 옛 라벨이 홈템으로 이관된다(안 하면 학습에서 조용히 빠진다)."""
    db = tmp_path / "t.db"
    s = Store(db)
    s.save_script("A", {"full_text": "집꾸미기", "segments": []}, category="인테리어")
    s.save_script("B", {"full_text": "살림템", "segments": []}, category="생활용품")
    s.save_script("C", {"full_text": "감자요리", "segments": []}, category="레시피")

    Store(db)  # 재기동 = 마이그레이션 재실행

    assert s.get_extract("A")["category"] == "홈템"
    assert s.get_extract("B")["category"] == "홈템"
    assert s.get_extract("C")["category"] == "레시피", "무관한 카테고리를 건드리면 안 된다"


def test_migration_drops_stale_stat_buckets(tmp_path):
    """옛 버킷을 지운다 — 남겨두면 통제 어휘 밖 버킷이 학습 화면에 계속 뜬다.
    (배치가 홈템으로 재계산해 채운다.)"""
    db = tmp_path / "t.db"
    Store(db)
    with Store(db)._conn() as c:
        for cat in ("인테리어", "생활용품", "레시피"):
            c.execute("INSERT INTO element_category_stats "
                      "(product_category, element, category_label, description, "
                      " examples_json, sample_count, computed_at) "
                      "VALUES (?,?,?,?,?,?,?)",
                      (cat, "hook", "라벨", "설명", "[]", 5, "2026-07-15"))

    Store(db)  # 재기동

    with Store(db)._conn() as c:
        left = {r[0] for r in c.execute("SELECT DISTINCT product_category "
                                        "FROM element_category_stats")}
    assert left == {"레시피"}, f"옛 버킷이 안 지워짐: {left}"
