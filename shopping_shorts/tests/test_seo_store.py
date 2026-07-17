import json
import pytest
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def _job(store):
    job_id = "seojob01"
    store.create_mix_job(job_id, ["https://x/1"], 20, "free")
    return job_id


def test_seo_roundtrip(store):
    """seo dict를 저장하면 get_mix_job이 파싱된 dict로 돌려준다."""
    job_id = _job(store)
    seo = {"title": "테스트 제목", "tags": ["a", "b"],
           "keyword_stats": [{"keyword": "a", "verdict": "blue"}]}
    store.update_mix_job(job_id, seo=seo)
    got = store.get_mix_job(job_id)["seo"]
    assert got == seo


def test_seo_defaults_to_none(store):
    """저장 전엔 None(빈 dict가 아니다 — 미생성과 빈 생성을 구분해야 한다)."""
    job_id = _job(store)
    assert store.get_mix_job(job_id)["seo"] is None


def test_seo_clearable(store):
    """None을 주면 지워진다. 중간 상태를 확인해야 '애초에 안 써진 것'과 구분된다."""
    job_id = _job(store)
    store.update_mix_job(job_id, seo={"title": "x"})
    assert store.get_mix_job(job_id)["seo"] == {"title": "x"}   # 먼저 써졌나
    store.update_mix_job(job_id, seo=None)
    assert store.get_mix_job(job_id)["seo"] is None             # 그 다음 지워졌나


def test_seo_does_not_disturb_neighbors(store):
    """seo 저장이 옆 컬럼을 밟지 않는다 — row 인덱스 밀림 사고 방지."""
    job_id = _job(store)
    store.update_mix_job(job_id, preview_status="ready", fx_status="done",
                         given_script=None)
    store.update_mix_job(job_id, seo={"title": "x"})
    got = store.get_mix_job(job_id)
    assert got["preview_status"] == "ready"
    assert got["fx_status"] == "done"
    assert got["seo"] == {"title": "x"}


def test_seo_korean_not_escaped(store):
    """ensure_ascii=False 관례 — DB에 한글이 그대로 들어간다."""
    job_id = _job(store)
    store.update_mix_job(job_id, seo={"title": "한글제목"})
    with store._conn() as c:
        raw = c.execute("SELECT seo_json FROM mix_jobs WHERE job_id=?", (job_id,)).fetchone()[0]
    assert "한글제목" in raw


from datetime import datetime, timedelta, timezone


_STAT = {"keyword": "빨대텀블러", "region": "KR", "views_median": 320000,
         "small_ratio": 0.4, "sample_n": 20,
         "top_titles": ["a", "b", "c"], "verdict": "blue"}


def test_keyword_stats_roundtrip(store):
    store.put_keyword_stats(_STAT)
    got = store.get_keyword_stats("빨대텀블러")
    assert got["views_median"] == 320000
    assert got["small_ratio"] == 0.4
    assert got["top_titles"] == ["a", "b", "c"]
    assert got["verdict"] == "blue"


def test_keyword_stats_miss_returns_none(store):
    assert store.get_keyword_stats("없는키워드") is None


def test_keyword_stats_upsert(store):
    """같은 키워드를 다시 재면 덮어쓴다(행이 늘지 않는다)."""
    store.put_keyword_stats(_STAT)
    store.put_keyword_stats({**_STAT, "views_median": 999})
    assert store.get_keyword_stats("빨대텀블러")["views_median"] == 999
    with store._conn() as c:
        n = c.execute("SELECT COUNT(*) FROM seo_keyword_stats").fetchone()[0]
    assert n == 1


def test_keyword_stats_ttl_expired(store):
    """TTL 지난 건 없는 것으로 친다 — 낡은 측정치로 근거를 만들면 안 된다."""
    store.put_keyword_stats(_STAT)
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    with store._conn() as c:
        c.execute("UPDATE seo_keyword_stats SET checked_at=?", (old,))
    assert store.get_keyword_stats("빨대텀블러", ttl_days=7) is None


def test_keyword_stats_ttl_boundary_fresh(store):
    """6일된 건 아직 유효(경계 off-by-one 방지)."""
    store.put_keyword_stats(_STAT)
    recent = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
    with store._conn() as c:
        c.execute("UPDATE seo_keyword_stats SET checked_at=?", (recent,))
    assert store.get_keyword_stats("빨대텀블러", ttl_days=7) is not None


def test_keyword_stats_region_separate(store):
    """같은 키워드라도 지역이 다르면 다른 행."""
    store.put_keyword_stats(_STAT)
    store.put_keyword_stats({**_STAT, "region": "US", "views_median": 111})
    assert store.get_keyword_stats("빨대텀블러", region="KR")["views_median"] == 320000
    assert store.get_keyword_stats("빨대텀블러", region="US")["views_median"] == 111
