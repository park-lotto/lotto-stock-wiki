"""발굴 추가 / 죽은채널 제외 store 메서드 테스트."""
import pytest
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_add_discovered_and_list(store):
    store.add_discovered("newch", "새채널")
    got = store.discovered_channels()
    assert got == [{"name": "새채널", "username": "newch", "followers": 0, "inpock": ""}]


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


def test_remove_channel_drops_from_discovered(store):
    store.add_discovered("ch", "x")
    store.remove_channel("ch", "x")
    assert store.discovered_channels() == []
