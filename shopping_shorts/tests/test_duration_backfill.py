"""영상 길이 백필(duration_backfill) — 캐시·포기 카운터·백필 흐름 검증."""
import json

from shopping_shorts import duration_backfill
from shopping_shorts.store import Store


def _mkstore(tmp_path):
    return Store(tmp_path / "t.db")


def test_duration_cache_roundtrip(tmp_path):
    s = _mkstore(tmp_path)
    s.set_reel_duration("AAA", 12.5)
    assert s.duration_map(["AAA", "BBB"]) == {"AAA": 12.5}
    assert s.duration_fail_map(["AAA"]) == {}


def test_fail_count_bumps_and_resets(tmp_path):
    s = _mkstore(tmp_path)
    s.bump_duration_fail("X")
    s.bump_duration_fail("X")
    assert s.duration_fail_map(["X"]) == {"X": 2}
    assert s.duration_map(["X"]) == {}          # 실패만 있으면 길이 없음
    s.set_reel_duration("X", 30)                # 성공하면 fail_count 리셋
    assert s.duration_fail_map(["X"]) == {}
    assert s.duration_map(["X"]) == {"X": 30}


def _seed_last_run(store, items):
    with store._conn() as c:
        c.execute("INSERT INTO last_run(items_json, collected_at) VALUES(?,datetime('now'))",
                  (json.dumps(items),))


def test_manifest_duration_parses_dash():
    node = {"video_dash_manifest": 'x mediaPresentationDuration="PT0H1M34.966S" y'}
    assert abs(duration_backfill._manifest_duration(node) - 94.966) < 0.001
    assert duration_backfill._manifest_duration({}) is None
    assert duration_backfill._manifest_duration(None) is None


class _FakeCtx:
    def __enter__(self):
        return "ctx"

    def __exit__(self, *a):
        return False


def test_run_backfill_fills_missing_and_respects_cache(tmp_path, monkeypatch):
    dbp = tmp_path / "t.db"
    s = Store(dbp)
    _seed_last_run(s, [{"shortcode": "DbkpMkcRfkJ"}, {"shortcode": "Dbi9c1YNsSc"},
                       {"shortcode": "DbmA3aZzieb", "duration": 9}])
    s.set_reel_duration("Dbi9c1YNsSc", 20)                # 캐시 적중 → 조회 안 함
    calls = []

    from shopping_shorts import instagram_playwright as ipw
    monkeypatch.setattr(ipw, "_detail_context", _FakeCtx)

    def fake_detail(ctx, pk, code=""):
        calls.append(code)
        return {"video_dash_manifest": 'mediaPresentationDuration="PT0H0M15S"'} \
            if code == "DbkpMkcRfkJ" else None

    monkeypatch.setattr(ipw, "_fetch_reel_detail", fake_detail)
    out = duration_backfill.run_backfill(db_path=dbp, sleep_s=0)
    assert calls == ["DbkpMkcRfkJ"]                       # B=캐시, C=이미 길이 있음
    assert s.duration_map(["DbkpMkcRfkJ"]) == {"DbkpMkcRfkJ": 15.0}
    assert "성공 1" in out


def test_run_backfill_gives_up_after_max_fail(tmp_path, monkeypatch):
    dbp = tmp_path / "t.db"
    s = Store(dbp)
    _seed_last_run(s, [{"shortcode": "DEAD"}])
    for _ in range(duration_backfill.MAX_FAIL):
        s.bump_duration_fail("DEAD")
    from shopping_shorts import instagram_playwright as ipw
    monkeypatch.setattr(ipw, "_detail_context",
                        lambda: (_ for _ in ()).throw(AssertionError("호출되면 안 됨")))
    out = duration_backfill.run_backfill(db_path=dbp, sleep_s=0)
    assert "성공 0" in out and "실패 0" in out


# ── 아카이브(역대 히트작) 백필 확장 (2026-08-06) ──────────────────────────
# 사장님 요청으로 히트작 카드에 ⏱ 길이를 붙이려는데, _targets()가 last_run(지금 랭킹 화면)만
# 훑어서 **아카이브 릴스는 영원히 대상이 안 됐다**(실측: 78,265개 중 길이 아는 것 205개 =
# 랭킹에 우연히 겹친 것뿐). 아카이브를 대상에 넣되, 78,265개를 한 번에 몰아치면 429 사고
# (2026-07-30)가 재발하므로 **조회수 상위부터** 조금씩 채운다.

def _seed_archive(store, rows):
    with store._conn() as c:
        for u, sc, views in rows:
            c.execute("INSERT INTO channel_archive(username, shortcode, url, thumbnail, "
                      "views, likes, comments, posted_at, first_seen, last_seen) "
                      "VALUES(?,?,?,?,?,0,0,'','','')", (u, sc, "u", "t", views))


def test_targets_include_archive_top_views(tmp_path):
    """★아카이브가 대상에 들어온다 — 안 들어오면 히트작 ⏱은 영원히 안 채워진다."""
    s = Store(tmp_path / "t.db")
    _seed_last_run(s, [])
    _seed_archive(s, [("ch", "ARCH_HI", 900), ("ch", "ARCH_LO", 5)])
    codes = [sc for _, sc in duration_backfill._targets(s)]
    assert "ARCH_HI" in codes, "아카이브 릴스가 백필 대상에 없다"


def test_archive_targets_are_ordered_by_views(tmp_path):
    """전부 채우는 데 몇 달 걸리므로(회당 상한이 있다) **많이 본 것부터** 채운다 —
    사장님이 실제로 보는 건 상위 카드다."""
    s = Store(tmp_path / "t.db")
    _seed_last_run(s, [])
    _seed_archive(s, [("ch", "LOW", 1), ("ch", "TOP", 999), ("ch", "MID", 50)])
    codes = [sc for _, sc in duration_backfill._targets(s) if sc.isupper()]
    assert codes.index("TOP") < codes.index("MID") < codes.index("LOW"), \
        f"조회수 상위부터가 아니다: {codes}"


def test_last_run_still_comes_first(tmp_path):
    """랭킹(지금 보는 화면)이 아카이브보다 먼저다 — 기존 동작을 아카이브가 밀어내면 안 된다."""
    s = Store(tmp_path / "t.db")
    _seed_last_run(s, [{"shortcode": "RANKED"}])
    _seed_archive(s, [("ch", "ARCHV", 10 ** 9)])
    codes = [sc for _, sc in duration_backfill._targets(s)]
    assert codes.index("RANKED") < codes.index("ARCHV")


def test_archive_slice_is_bounded(tmp_path):
    """429 계보(2026-07-30 하루 950건 → 수집 급감)를 의식해 한 번에 다 담지 않는다."""
    s = Store(tmp_path / "t.db")
    _seed_last_run(s, [])
    _seed_archive(s, [("ch", f"A{i:05d}", 1000 - i) for i in range(900)])
    codes = [sc for _, sc in duration_backfill._targets(s)]
    assert len(codes) <= duration_backfill.ARCHIVE_SCAN_LIMIT, \
        f"아카이브를 통째로 담았다({len(codes)}건) — 상한이 없다"
