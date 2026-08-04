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
