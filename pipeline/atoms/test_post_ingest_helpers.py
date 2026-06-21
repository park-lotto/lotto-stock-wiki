import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.post_ingest import _parse_post_header, get_done_post_files


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    yield


def test_parse_header_blog_label(tmp_path):
    p = tmp_path / "2026-06-21_0900_바이오.md"
    p.write_text(
        "# 바이오\n- **출처**: pokara61 블로그\n- **날짜**: 2026-06-21\n"
        "- **링크**: [원문](https://blog.naver.com/pokara61/1)\n## 본문\n내용",
        encoding="utf-8")
    h = _parse_post_header(p, "출처")
    assert h["source_name"] == "pokara61"
    assert h["date"] == "2026-06-21"
    assert "blog.naver.com/pokara61/1" in h["link"]


def test_parse_header_youtube_label(tmp_path):
    p = tmp_path / "2026-06-05_0905_주식.md"
    p.write_text(
        "# 주식\n- **채널**: UP_CYCLE_STOCK\n- **날짜**: 2026-06-05\n"
        "- **링크**: [유튜브](https://www.youtube.com/watch?v=abc)\n## 핵심 요약\n내용",
        encoding="utf-8")
    h = _parse_post_header(p, "채널")
    assert h["source_name"] == "UP_CYCLE_STOCK"
    assert h["date"] == "2026-06-05"
    assert "youtube.com/watch?v=abc" in h["link"]


def test_get_done_post_files_by_source_type(tmp_path):
    dbmod.init_db(); dbmod.migrate_db()
    import uuid
    from datetime import datetime
    conn = dbmod.get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO atoms (id,date,source_type,source_name,source_trust,"
        "raw_file,layer,sector,asset,asset_level,signal,event_type,magnitude,"
        "content_type,strength_score,content,relations,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), "2026-06-05", "youtube", "UP_CYCLE_STOCK", 3,
         "raw/yt/2026-06-05_0905_주식.md", "L5", "반도체", "반도체", "sector",
         "neutral", "report", "minor", "fact", 2, "x", "[]", datetime.now().isoformat()),
    )
    conn.commit(); conn.close()
    done = get_done_post_files("youtube")
    assert "2026-06-05_0905_주식.md" in done
