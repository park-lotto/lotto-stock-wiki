"""베스트 플래그 — 순서와 배지를 한 필드로(설계 §4.1).

★이 파일이 존재하는 이유: 카드 순서가 `voice_presets.json`의 배열 순서라고 **틀리게**
적었다가 실측으로 뒤집혔다. 진짜 순서는 `ORDER BY created_at`(DB 삽입 시각)이라 파일만
재배열하면 화면은 그대로다. 그 전제를 테스트로 못박는다.
"""
import pytest
from shopping_shorts.store import Store


def _p(pid, best=False, gid=None):
    return {"preset_id": pid, "group_id": gid or pid, "variant": "stable",
            "name": pid, "lang": "KR", "base_voice_id": "v1",
            "voice_settings": {"stability": 0.5}, "best": best}


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_best_roundtrips(store):
    store.upsert_voice_preset(_p("a", best=True))
    store.upsert_voice_preset(_p("b", best=False))
    got = {r["preset_id"]: r["best"] for r in store.list_voice_presets(lang="KR")}
    assert got == {"a": True, "b": False}


def test_best_defaults_false(store):
    """기존 42개 프리셋은 best를 안 적는다 — 빠지면 False여야 한다."""
    p = _p("a"); del p["best"]
    store.upsert_voice_preset(p)
    assert store.list_voice_presets(lang="KR")[0]["best"] is False


def test_best_sorts_first(store):
    """★핵심 — 베스트가 앞. 나중에 넣어도 앞으로 온다(created_at을 이긴다)."""
    store.upsert_voice_preset(_p("first_inserted", best=False))
    store.upsert_voice_preset(_p("later_but_best", best=True))
    assert [r["preset_id"] for r in store.list_voice_presets(lang="KR")] == [
        "later_but_best", "first_inserted"]


def test_created_at_still_breaks_ties(store):
    """베스트끼리는 기존 순서(created_at) 유지 — 정렬이 통째로 뒤집히면 안 된다.

    ★리뷰 실측(Task 2 리뷰): b1을 먼저, b2를 나중에 삽입 순서 그대로 created_at을
    박으면(=삽입 순서와 created_at 순서가 같으면) `ORDER BY best DESC`만으로도
    ['b1','b2']가 나온다 — SQLite 정렬기가 `USE TEMP B-TREE FOR ORDER BY`에서
    내부적으로 rowid로 동점을 깨는데, 그 rowid 순서가 삽입 순서와 우연히 같기
    때문이다. 즉 tie-break 절(`, created_at`)을 지워도 이 테스트가 안 죽는
    항구적 토톨로지였다(42행으로 늘려도 동일, 뮤테이션 실측 완료).

    그래서 created_at을 **삽입 순서와 반대로** 심는다: 먼저 넣은 b1에 더 늦은
    시각을, 나중에 넣은 b2에 더 이른 시각을 준다. 이러면 rowid 순서(b1,b2)와
    created_at 순서(b2,b1)가 어긋나므로 두 정렬 기준이 실제로 갈라진다:
    - 올바른 코드(`best DESC, created_at`) → created_at 기준 ['b2','b1']
    - 뮤턴트(`best DESC`만)            → rowid 기준 ['b1','b2']
    이래야 tie-break 절을 지우면 이 테스트가 진짜로 죽는다(뮤테이션으로 확인 완료).
    """
    store.upsert_voice_preset(_p("b1", best=True))
    store.upsert_voice_preset(_p("b2", best=True))
    with store._conn() as c:
        c.execute("UPDATE voice_presets SET created_at=? WHERE preset_id=?",
                  ("2026-07-16T09:00:00+00:00", "b1"))
        c.execute("UPDATE voice_presets SET created_at=? WHERE preset_id=?",
                  ("2026-07-16T08:00:00+00:00", "b2"))
    assert [r["preset_id"] for r in store.list_voice_presets(lang="KR")] == ["b2", "b1"]


def test_best_updates_on_reupsert(store):
    """같은 preset_id로 다시 upsert하면 best도 덮여야 한다(ON CONFLICT에서 안 빠지는지)."""
    store.upsert_voice_preset(_p("a", best=False))
    store.upsert_voice_preset(_p("a", best=True))
    assert store.get_voice_preset("a")["best"] is True


def test_migration_adds_column_to_existing_db(store):
    """옛 DB(best 컬럼 없음)에 컬럼을 붙여도 기존 행이 살아있다."""
    with store._conn() as c:
        c.execute("ALTER TABLE voice_presets DROP COLUMN best")
        # voice_settings_json·created_at은 NOT NULL(기본값 없음) — 브리프 원문엔 빠져있어
        # IntegrityError로 죽었다(실측). 마이그레이션과 무관한 스키마 제약이라 여기만 보강.
        c.execute("INSERT INTO voice_presets(preset_id, name, lang, base_voice_id, "
                  "group_id, variant, voice_settings_json, created_at) "
                  "VALUES('old','old','KR','v1','old','stable','{}','2026-07-16T00:00:00+00:00')")
    s2 = Store(store.db_path)          # 재기동 = 마이그레이션 재실행
    rows = {r["preset_id"]: r["best"] for r in s2.list_voice_presets(lang="KR")}
    assert rows["old"] is False
