# -*- coding: utf-8 -*-
"""채널 대본 백필 — 대상 선정·부분 실패 계속·저장 배선(실 다운로드 없이 주입)."""
from unittest.mock import patch

import pytest

from shopping_shorts.store import Store
from shopping_shorts.scripts.backfill_channel_scripts import backfill


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.db")
    with s._conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS channel_archive (
            username TEXT, shortcode TEXT, url TEXT, thumbnail TEXT, views INTEGER,
            likes INTEGER, comments INTEGER, posted_at TEXT, first_seen TEXT, last_seen TEXT)""")
        for sc, v in [("AAA", 100), ("BBB", 900), ("CCC", 500), ("DDD", 50)]:
            c.execute("INSERT INTO channel_archive (username, shortcode, views) VALUES (?,?,?)",
                      ("maison_homedino", sc, v))
    s.save_script("CCC", {"segments": [], "full_text": "이미 있음"})  # 스킵 대상
    return s


def test_backfill_targets_topviews_missing_only_and_saves(store):
    calls = []

    def fake_download(url, dest):
        calls.append(url)
        if "AAA" in url:
            raise RuntimeError("다운로드 실패")  # 부분 실패 — 멈추지 않아야 한다
        return "/tmp/fake.mp4", "캡션"

    def fake_extract(path, code, caption=""):
        return {"segments": [], "full_text": f"{code} 대본"}

    with patch("shopping_shorts.media_download.download_any", fake_download), \
         patch("shopping_shorts.script_extract.extract_auto", fake_extract):
        ok, fail = backfill(store, "maison_homedino", limit=2, sleep_s=0,
                            out=lambda *a: None)

    # 조회수 상위 2 = BBB(900)·CCC(500)인데 CCC는 대본 있어 제외 → BBB·AAA
    assert [("BBB" in c) or ("AAA" in c) for c in calls] == [True, True]
    assert ok == 1 and fail == 1
    assert store.get_script("BBB")["full_text"] == "BBB 대본"
    assert store.get_script("AAA") is None
