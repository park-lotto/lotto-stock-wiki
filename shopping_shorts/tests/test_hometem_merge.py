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


# ── 2차 병합: '가전' → '홈템' (2026-07-31, 사장님 결정) ────────────────────
# 왜: 살림템과 가전을 가르는 기준이 실무에 없다(에어프라이어·믹서기는 주방살림이자 가전).
# 실측에서 '에스프레소 머신'이 레시피로 새는 등 경계가 계속 흔들렸고, 합치기 직전
# 라이브 분포가 홈템 258 vs 가전 5로 가전은 이미 거의 안 잡히는 버킷이었다.
def test_gajeon_is_gone_from_vocabulary():
    assert "가전" not in KEYWORDS, "합친 어휘가 남아 있으면 통제 어휘가 갈라진다"
    assert "가전" not in NAME_KEYWORDS


def test_hometem_absorbs_appliance_keywords():
    """가전 키워드를 홈템이 다 흡수해야 한다 — 안 그러면 그 영상들이 '기타'로 샌다."""
    for cap in ("최신 로봇청소기 언박싱", "에어프라이어 추천", "밥솥 하나로 끝",
                "믹서기 후기", "제습기 대신 가습기"):
        assert categorize("", cap) == "홈템", cap


def test_appliance_topic_no_longer_maps_to_a_ctype():
    """ctype_of는 모르는 topic을 '기타'로 떨어뜨린다 — 옛 '가전'은 이제 없는 topic이다."""
    from shopping_shorts.categorize import TOPIC_CTYPE
    assert "가전" not in TOPIC_CTYPE
    assert ctype_of("가전") == "기타"


def test_migration_script_moves_old_labels(tmp_path, monkeypatch):
    """★코드만 바꾸면 DB의 옛 '가전'이 고아 버킷이 된다(1차 병합에서 겪은 문제).
    이관 스크립트가 last_run 스냅샷(JSON 안)까지 고치는지 잠근다."""
    import json
    from shopping_shorts import config
    db = tmp_path / "t.db"
    st = Store(db)
    st.save_last_run([{"shortcode": "A", "category": "가전"},
                      {"shortcode": "B", "category": "레시피"}], "2026-07-31T00:00:00")
    monkeypatch.setattr(config, "DB_PATH", db)
    import scripts.merge_gajeon_into_hometem as mig
    monkeypatch.setattr(mig, "DB_PATH", db)

    assert mig.main([]) == 0

    items, _ = Store(db).load_last_run()
    assert [i["category"] for i in items] == ["홈템", "레시피"]
