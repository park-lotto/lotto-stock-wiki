"""태깅 순서를 '전체 조회수순'으로 + 만료 썸네일 재크롤 (2026-08-09 사장님 지시).

## 왜 바꿨나 — 태깅 순서

종전은 2단이었다: `archived_usernames()`(미태깅 많이 남은 채널 순) → 그 채널 안에서
조회수순. 그래서 **전체 조회수 순위와 무관하게** 돌았다. 실측:
  - 미태깅 144,594건 중 **51%가 조회수 1만 미만**
  - 미태깅 최고 조회수는 398만인데 아직 안 됨 / 태깅완료엔 조회수 9짜리가 있음

이 기능의 목적은 "오늘 터진 영상 → 옛 히트작 매칭"이라 터진 영상부터 태그가 붙어야
값이 나온다. 상위 16,193건(10만+)이면 하루 한도로 2~3일이다.

## 왜 바꿨나 — 만료 썸네일

인스타 CDN 썸네일 URL의 `oe` 서명은 **약 4일**이면 만료돼 403이 된다. 그런데
`pick_targets`가 done 채널을 영구 제외해서, 8-03에 크롤한 채널의 썸네일이 8-07쯤
죽은 뒤 **아무도 되살리지 않았다** — 역대 히트작 첫 페이지 상위 12건 중 4건이
검게 죽어 있었다(상위 200건 중 55건, 전부 8-03 크롤분).

재크롤이 답인 걸 실측으로 확인했다: vibe_item 재크롤 → 만료가 2026-08-14로 갱신.
`channel_archive`는 (username, shortcode) 충돌 시 thumbnail을 덮어쓰므로 URL만
새로 들어가고, `vision_tags`는 shortcode가 PK라 **이미 붙은 태그는 유지**된다.
"""
import sqlite3

from shopping_shorts import archive_tagger, channel_archive
from shopping_shorts.store import Store


def _seed(tmp_path, rows):
    """rows: (username, shortcode, views, tagged) → 테스트용 DB."""
    store = Store(str(tmp_path / "t.db"))
    with store._conn() as c:
        for u, sc, views, tagged in rows:
            c.execute(
                "INSERT INTO channel_archive(username, shortcode, url, thumbnail, "
                " views, likes, comments, posted_at, first_seen, last_seen) "
                "VALUES(?,?,?,?,?,0,0,'','','')",
                (u, sc, f"http://x/{sc}", f"http://cdn/{sc}.jpg", views))
            if tagged:
                c.execute(
                    "INSERT INTO vision_tags(shortcode, subject, keywords_json, created_at) "
                    "VALUES(?,?,?,datetime('now'))", (sc, "s", "[]"))
    return store


# ── 태깅 순서: 채널 무시하고 전체 조회수순 ────────────────────────────────
def test_global_batch_is_ordered_by_views_across_channels(tmp_path):
    """작은 채널의 1위가 큰 채널의 하위보다 조회수가 높으면 **먼저** 나와야 한다."""
    store = _seed(tmp_path, [
        ("big", "b1", 5_000, False),      # 미태깅 많은 채널이지만 조회수는 낮다
        ("big", "b2", 4_000, False),
        ("big", "b3", 3_000, False),
        ("small", "s1", 900_000, False),  # 채널은 작아도 조회수 최상위
    ])

    got = [it["shortcode"] for it in archive_tagger.pick_global_batch(store, 2)]

    assert got == ["s1", "b1"], "채널이 아니라 조회수가 순서를 정해야 한다"


def test_global_batch_skips_already_tagged(tmp_path):
    """이미 태깅된 건 다시 집지 않는다 — 커서 없이도 진행되는 근거."""
    store = _seed(tmp_path, [
        ("c", "hit", 999_999, True),      # 최상위지만 이미 태깅됨
        ("c", "next", 10, False),
    ])

    got = [it["shortcode"] for it in archive_tagger.pick_global_batch(store, 5)]

    assert got == ["next"], "태깅 완료분은 NOT EXISTS로 빠져야 한다"


def test_global_batch_requires_thumbnail(tmp_path):
    """썸네일이 없으면 태깅할 재료가 없다 — 후보에서 뺀다."""
    store = _seed(tmp_path, [("c", "nothumb", 500_000, False)])
    with store._conn() as c:
        c.execute("UPDATE channel_archive SET thumbnail='' WHERE shortcode='nothumb'")

    assert archive_tagger.pick_global_batch(store, 5) == []


# ── 만료 썸네일: done이어도 오래됐으면 다시 크롤 대상 ──────────────────────
def test_stale_done_channels_are_returned_for_refresh(tmp_path):
    """4일 넘게 안 본 done 채널은 썸네일이 만료됐다고 보고 재크롤 목록에 넣는다."""
    store = Store(str(tmp_path / "s.db"))
    with store._conn() as c:
        c.execute("INSERT INTO archive_state(username, status, reels, note, updated_at) "
                  "VALUES('old','done',10,'',datetime('now','-6 days'))")
        c.execute("INSERT INTO archive_state(username, status, reels, note, updated_at) "
                  "VALUES('recent','done',10,'',datetime('now','-1 days'))")

    stale = store.archive_stale_usernames(older_than_days=4)

    assert "old" in stale, "6일 전 크롤 = 썸네일 만료 → 갱신 대상"
    assert "recent" not in stale, "1일 전 크롤은 아직 살아있다 — 재크롤 낭비"


def test_gone_channels_never_come_back(tmp_path, monkeypatch):
    """삭제된 채널은 오래됐어도 되살리지 않는다(페이지가 없으니 크롤 낭비)."""
    store = Store(str(tmp_path / "g.db"))
    with store._conn() as c:
        c.execute("INSERT INTO archive_state(username, status, reels, note, updated_at) "
                  "VALUES('deleted','gone',0,'',datetime('now','-30 days'))")

    monkeypatch.setattr(channel_archive, "load_channels", lambda: [])
    targets = channel_archive.pick_targets(store)

    assert "deleted" not in targets


def test_fresh_channels_come_before_refresh(tmp_path, monkeypatch):
    """아직 한 번도 안 본 채널이 **먼저** — 갱신 때문에 신규 수집이 밀리면 안 된다."""
    store = Store(str(tmp_path / "o.db"))
    with store._conn() as c:
        c.execute("INSERT INTO archive_state(username, status, reels, note, updated_at) "
                  "VALUES('stale','done',10,'',datetime('now','-9 days'))")
    monkeypatch.setattr(channel_archive, "load_channels",
                        lambda: [{"username": "brandnew", "followers": 100}])

    targets = channel_archive.pick_targets(store)

    assert targets.index("brandnew") < targets.index("stale")


def test_refresh_can_be_disabled(tmp_path, monkeypatch):
    """갱신을 끄면 종전 동작 그대로(신규만) — 롤백 경로를 남긴다."""
    store = Store(str(tmp_path / "d.db"))
    with store._conn() as c:
        c.execute("INSERT INTO archive_state(username, status, reels, note, updated_at) "
                  "VALUES('stale','done',10,'',datetime('now','-9 days'))")
    monkeypatch.setattr(channel_archive, "load_channels", lambda: [])

    assert channel_archive.pick_targets(store, refresh_stale=False) == []


def test_recrawl_overwrites_thumbnail_but_keeps_tags(tmp_path):
    """재크롤은 썸네일 URL만 갱신하고 이미 붙은 비전태그는 건드리지 않는다.

    이게 성립해야 '갱신해도 태깅을 처음부터 다시 하지 않는다'가 보장된다.
    """
    store = _seed(tmp_path, [("c", "sc1", 100, True)])
    store.archive_upsert_many("c", [{"shortcode": "sc1", "url": "http://x/sc1",
                                     "thumbnail": "http://cdn/NEW.jpg", "views": 200}],
                              "2026-08-09T00:00:00")

    with store._conn() as c:
        thumb, = c.execute("SELECT thumbnail FROM channel_archive "
                           "WHERE shortcode='sc1'").fetchone()
        tags = c.execute("SELECT COUNT(*) FROM vision_tags "
                         "WHERE shortcode='sc1'").fetchone()[0]

    assert thumb == "http://cdn/NEW.jpg", "만료 URL이 새 URL로 갱신돼야 한다"
    assert tags == 1, "이미 붙은 태그는 그대로 — 재태깅 비용 0"
