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
    """None을 주면 지워진다."""
    job_id = _job(store)
    store.update_mix_job(job_id, seo={"title": "x"})
    store.update_mix_job(job_id, seo=None)
    assert store.get_mix_job(job_id)["seo"] is None


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
