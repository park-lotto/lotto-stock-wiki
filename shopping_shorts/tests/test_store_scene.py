import pytest
from shopping_shorts.store import Store, LEGACY_CUSTOMER_ID


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def _asset(**over):
    a = {"asset_type": "clip", "render_mode": "cutaway",
         "media_path": "data/scene_assets/abc.mp4", "poster_path": "data/scene_assets/abc.jpg",
         "duration": 2.5, "keep_original_audio": 1, "title": "가루 한스푼",
         "scene_desc": "흰 가루를 숟가락으로 떠 그릇에 넣음", "role": "비법공개",
         "category": "레시피", "subject": "가루(밀가루·설탕류)", "tone": "비밀스러운·궁금",
         "keywords": ["숟가락", "가루", "클로즈업"], "source_kind": "reference",
         "source_ref": "ABC123"}
    a.update(over)
    return a


def test_add_returns_id_and_get_roundtrips(store):
    aid = store.add_scene_asset(_asset())

    assert isinstance(aid, int) and aid > 0
    got = store.get_scene_asset(aid)
    assert got["title"] == "가루 한스푼"
    assert got["asset_type"] == "clip"
    assert got["render_mode"] == "cutaway"
    assert got["duration"] == 2.5
    assert got["keywords"] == ["숟가락", "가루", "클로즈업"]  # 콤마문자열 → list 복원
    assert got["created_at"]  # datetime('now')로 자동 채움


def test_list_filters_by_type_category_role(store):
    store.add_scene_asset(_asset(title="A", asset_type="clip", category="레시피", role="비법공개"))
    store.add_scene_asset(_asset(title="B", asset_type="sfx", category="레시피", role="반응"))
    store.add_scene_asset(_asset(title="C", asset_type="clip", category="가전", role="비법공개"))

    assert {a["title"] for a in store.list_scene_assets()} == {"A", "B", "C"}
    assert {a["title"] for a in store.list_scene_assets(asset_type="clip")} == {"A", "C"}
    assert {a["title"] for a in store.list_scene_assets(category="레시피")} == {"A", "B"}
    assert {a["title"] for a in store.list_scene_assets(role="비법공개")} == {"A", "C"}
    assert {a["title"] for a in store.list_scene_assets(asset_type="clip", category="레시피")} == {"A"}


def test_customer_isolation(store):
    mine = store.add_scene_asset(_asset(title="내것"), customer_id=7)
    store.add_scene_asset(_asset(title="남것"), customer_id=8)

    assert [a["title"] for a in store.list_scene_assets(customer_id=7)] == ["내것"]
    assert store.get_scene_asset(mine, customer_id=8) is None       # 남의 것 못 읽음
    assert store.update_scene_asset(mine, {"title": "탈취"}, customer_id=8) is False
    assert store.delete_scene_asset(mine, customer_id=8) is False   # 남의 것 못 지움
    assert store.get_scene_asset(mine, customer_id=7)["title"] == "내것"  # 그대로


def test_update_changes_only_given_tags(store):
    aid = store.add_scene_asset(_asset())

    assert store.update_scene_asset(aid, {"title": "설탕 한스푼", "keywords": ["설탕"]}) is True

    got = store.get_scene_asset(aid)
    assert got["title"] == "설탕 한스푼"
    assert got["keywords"] == ["설탕"]
    assert got["scene_desc"] == "흰 가루를 숟가락으로 떠 그릇에 넣음"  # 안 준 필드는 유지
    assert got["media_path"] == "data/scene_assets/abc.mp4"          # 미디어 필드는 편집 대상 아님


def test_update_ignores_unknown_and_protected_fields(store):
    aid = store.add_scene_asset(_asset())

    # media_path/customer_id/id는 태그 편집으로 못 바꾼다(경로 조작 차단)
    store.update_scene_asset(aid, {"media_path": "../../etc/passwd", "customer_id": 99,
                                   "id": 12345, "존재안함": "x", "title": "정상"})

    got = store.get_scene_asset(aid)
    assert got["media_path"] == "data/scene_assets/abc.mp4"
    assert got["id"] == aid
    assert got["title"] == "정상"


def test_delete_removes(store):
    aid = store.add_scene_asset(_asset())

    assert store.delete_scene_asset(aid) is True
    assert store.get_scene_asset(aid) is None
    assert store.delete_scene_asset(aid) is False  # 두 번째는 False


def test_sfx_has_null_render_mode(store):
    aid = store.add_scene_asset(_asset(asset_type="sfx", render_mode=None, poster_path=None))

    got = store.get_scene_asset(aid)
    assert got["render_mode"] is None
    assert got["poster_path"] is None


def test_add_scene_asset_stores_source_start_frame_and_origin(store):
    aid = store.add_scene_asset(_asset(source_start_frame=124, source_origin="짜집기"))

    got = [a for a in store.list_scene_assets() if a["id"] == aid][0]
    assert got["source_start_frame"] == 124
    assert got["source_origin"] == "짜집기"


def test_add_scene_asset_defaults_origin_to_모름(store):
    """★기본값은 '모름'이다. 라우트가 '모름'을 막는다(설계 §7.2) —
    남의 촬영분이 라이브에 들어가는 쪽이 짤 하나 잃는 것보다 훨씬 나쁘다."""
    aid = store.add_scene_asset(_asset(title="t2"))

    got = [a for a in store.list_scene_assets() if a["id"] == aid][0]
    assert got["source_origin"] == "모름"
    assert got["source_start_frame"] is None
