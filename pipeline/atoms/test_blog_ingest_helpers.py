import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.blog_ingest import _parse_blog_header, get_done_blog_files


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    yield


def test_parse_blog_header(tmp_path):
    p = tmp_path / "2026-06-21_0900_바이오 주식.md"
    p.write_text(
        "# 바이오 주식과 코스닥 승강제에 대해서\n"
        "- **출처**: pokara61 블로그\n"
        "- **날짜**: 2026-06-21\n"
        "- **링크**: [원문](https://blog.naver.com/pokara61/123)\n"
        "## 본문\n내용",
        encoding="utf-8",
    )
    h = _parse_blog_header(p)
    assert h["blogger"] == "pokara61"        # "블로그" 접미사 제거
    assert h["date"] == "2026-06-21"
    assert "blog.naver.com/pokara61/123" in h["link"]


def test_get_done_blog_files_basename(tmp_path):
    dbmod.init_db(); dbmod.migrate_db()
    import uuid
    from datetime import datetime
    conn = dbmod.get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO atoms (id,date,source_type,source_name,source_trust,"
        "raw_file,layer,sector,asset,asset_level,signal,event_type,magnitude,"
        "content_type,strength_score,content,relations,created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4()), "2026-06-21", "blog", "pokara61", 3,
         "raw/blog/2026-06-21_0900_바이오.md", "L5", "바이오", "바이오", "sector",
         "neutral", "report", "minor", "fact", 2, "x", "[]", datetime.now().isoformat()),
    )
    conn.commit(); conn.close()
    done = get_done_blog_files()
    assert "2026-06-21_0900_바이오.md" in done
