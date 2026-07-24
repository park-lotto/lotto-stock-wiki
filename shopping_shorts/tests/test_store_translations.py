"""번역 캐시(2026-07-24) — 한→중 소재 번역 저장/조회."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_save_and_get(store):
    assert store.get_translation("빵") is None
    store.save_translation("빵", "面包")
    assert store.get_translation("빵") == "面包"


def test_save_overwrites(store):
    store.save_translation("빵", "")
    store.save_translation("빵", "面包")
    assert store.get_translation("빵") == "面包"


def test_empty_zh_is_cached_not_none(store):
    # 번역 실패(빈 zh)도 저장 — 반복 호출 방지. get은 "" 반환(None 아님).
    store.save_translation("희귀소재", "")
    assert store.get_translation("희귀소재") == ""


def test_translations_map_batch(store):
    store.save_translation("빵", "面包")
    store.save_translation("오이", "黄瓜")
    m = store.translations_map(["빵", "오이", "없음"])
    assert m == {"빵": "面包", "오이": "黄瓜"}  # 없는 건 빠진다


def test_translations_map_empty(store):
    assert store.translations_map([]) == {}
    assert store.translations_map(None) == {}
