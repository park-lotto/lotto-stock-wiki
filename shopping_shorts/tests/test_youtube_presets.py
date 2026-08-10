from shopping_shorts import youtube_category_presets as p


def test_category_keys_match_ctypes():
    # UI 버튼 key(CTYPES)와 1:1 — 빠지거나 남으면 '전체=버튼 합'이 깨진다
    assert set(p.CATEGORY_KEYWORDS) == {"홈템", "비법형", "제품형", "혼합형", "기타"}


def test_every_category_has_keywords():
    for key, kws in p.CATEGORY_KEYWORDS.items():
        assert kws and all(isinstance(k, str) and k.strip() for k in kws), key


def test_preset_keywords_all():
    # None → 전 카테고리 union, 중복 없음
    allk = p.preset_keywords(None)
    flat = [k for kws in p.CATEGORY_KEYWORDS.values() for k in kws]
    assert set(allk) == set(flat)
    assert len(allk) == len(set(allk))          # 중복 제거됨


def test_preset_keywords_scoped():
    assert p.preset_keywords(["혼합형"]) == p.CATEGORY_KEYWORDS["혼합형"]


def test_preset_keywords_unknown_key():
    assert p.preset_keywords(["없는카테고리"]) == []
