# -*- coding: utf-8 -*-
"""어미 변형 통합 (대본퀄 v6, 2026-08-05) — canonical 정규화 + 병합 스크립트."""
import pytest

from shopping_shorts.store import Store, _normalize_canonical
from shopping_shorts.scripts.merge_pattern_variants import merge


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_canonical_tilde_and_spelling_unified():
    # 물결 접두·더라구/더라고 표기가 같은 키로 접힌다
    assert _normalize_canonical("~더라고요") == _normalize_canonical("더라고요")
    assert _normalize_canonical("~더라구요") == _normalize_canonical("더라고요")
    assert _normalize_canonical("~거든요") == _normalize_canonical("거든요")


def test_canonical_ending_bucket_collapses_short_deora():
    # ending 버킷에서만 '하더라고요'류 짧은 변형이 '더라고요'로 접힌다
    assert _normalize_canonical("하더라고요", "ending") == "더라고요"
    assert _normalize_canonical("~하더라고요", "ending") == "더라고요"
    # 긴 서술어는 안 접는다 (별개 부품)
    assert _normalize_canonical("잡아주더라고요", "ending") == "잡아주더라고요"
    # ending 밖에서는 축약 안 함
    assert _normalize_canonical("하더라고요", "hook") == "하더라고요"


def test_add_pattern_item_dedups_new_variants(store):
    # 강화된 canonical로 신규 적재부터 변형이 한 행에 쌓인다 (재발 차단)
    i1 = store.add_pattern_item("ending", "~더라고요")
    i2 = store.add_pattern_item("ending", "하더라고요")
    i3 = store.add_pattern_item("ending", "~더라구요")
    assert i1 == i2 == i3
    items = store.list_pattern_items(bucket="ending")
    assert len(items) == 1 and items[0]["freq"] == 3


def test_merge_collapses_legacy_rows_reversibly(store):
    # 옛 canonical로 이미 갈라져 쌓인 행들을 병합 — 삭제 아닌 status='merged'
    ids = []
    for text, canon, freq in [("~하더라고요", "~하더라고요", 74),
                              ("하더라고요", "하더라고요", 69),
                              ("~더라고요", "~더라고요", 38),
                              ("~더라구요", "~더라구요", 18)]:
        iid = store.add_pattern_item("ending", text, canonical=canon)
        with store._conn() as c:
            c.execute("UPDATE pattern_item SET freq=?, status='approved' WHERE id=?",
                      (freq, iid))
        ids.append(iid)

    n = merge(store, bucket="ending", apply=False, out=lambda *a: None)
    assert n == 3  # dry-run은 개수만 보고
    approved = store.list_pattern_items(bucket="ending", status="approved")
    assert len(approved) == 4  # dry-run이라 무변경

    merge(store, bucket="ending", apply=True, out=lambda *a: None)
    approved = store.list_pattern_items(bucket="ending", status="approved")
    assert len(approved) == 1
    keeper = approved[0]
    assert keeper["freq"] == 74 + 69 + 38 + 18
    assert keeper["canonical"] == "더라고요"
    merged = store.list_pattern_items(bucket="ending", status="merged")
    assert len(merged) == 3  # 복구 가능하게 남아 있다
