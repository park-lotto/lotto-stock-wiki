"""발굴 추가 / 죽은채널 제외 store 메서드 테스트."""
import pytest
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_add_discovered_and_list(store):
    store.add_discovered("newch", "새채널")
    got = store.discovered_channels()
    assert len(got) == 1
    # collect union이 쓰는 핵심 키(2026-07-24: 관리페이지 표시용 added_at 키가 추가됨 —
    # 추가 키라 collect union은 무시한다. exact 비교 대신 핵심 키만 검증).
    assert {k: got[0][k] for k in ("name", "username", "followers", "inpock")} == \
        {"name": "새채널", "username": "newch", "followers": 0, "inpock": ""}
    assert "added_at" in got[0]  # 관리페이지가 등록일 표시에 쓴다


def test_add_discovered_defaults_name_to_username(store):
    store.add_discovered("nameless")
    assert store.discovered_channels()[0]["name"] == "nameless"


def test_remove_channel_soft_delete(store):
    store.remove_channel("Dead1", "죽음")
    assert store.removed_usernames() == {"dead1"}  # 정규화 소문자
    assert store.removed_list()[0]["username"] == "Dead1"


def test_restore_channel(store):
    store.remove_channel("dead", "x")
    store.restore_channel("dead")
    assert store.removed_usernames() == set()


def test_add_discovered_clears_removal(store):
    store.remove_channel("ch", "x")
    store.add_discovered("ch", "부활")
    assert store.removed_usernames() == set()
    assert store.discovered_channels()[0]["name"] == "부활"


def test_discovery_feed_save_load(store):
    assert store.load_discovery_feed() == ([], None)
    store.save_discovery_feed([{"username": "a"}, {"username": "b"}])
    items, updated = store.load_discovery_feed()
    assert [i["username"] for i in items] == ["a", "b"]
    assert updated is not None
    store.save_discovery_feed([{"username": "c"}])  # 덮어쓰기
    assert [i["username"] for i in store.load_discovery_feed()[0]] == ["c"]


def test_remove_channel_drops_from_discovered(store):
    store.add_discovered("ch", "x")
    store.remove_channel("ch", "x")
    assert store.discovered_channels() == []
