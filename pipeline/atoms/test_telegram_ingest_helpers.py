import pytest
import pipeline.atoms.db as dbmod
from pipeline.atoms.telegram_ingest import _parse_filename, _is_image_file, get_done_telegram_files


@pytest.fixture(autouse=True)
def _temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "t.db")
    yield


def test_parse_filename():
    date, channel = _parse_filename("2026-06-19_하나반도체.md")
    assert date == "2026-06-19"
    assert channel == "하나반도체"


def test_image_file_skipped():
    assert _is_image_file("스크린샷 2026-06-06 002815.png") is True
    assert _is_image_file("2026-06-19_하나반도체.md") is False


def test_get_done_telegram_files_dedup():
    """이미 DB에 기록된 텔레그램 raw_file은 done set에 포함되어야 한다."""
    dbmod.init_db()
    dbmod.migrate_db()

    # 임시 atom 삽입 (source_type='telegram')
    import uuid
    from datetime import datetime
    raw = "raw/telegram/2026-06-19_하나반도체.md"
    conn = dbmod.get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO atoms
        (id, date, source_type, source_name, source_trust, raw_file,
         layer, sector, asset, asset_level,
         signal, event_type, magnitude, content_type, strength_score,
         content, relations, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            str(uuid.uuid4()), "2026-06-19", "telegram", "하나반도체", 3, raw,
            "L5", "반도체", "하나반도체", "sector",
            "bullish", "analysis", "medium", "text", 70,
            "테스트 내용", "[]",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()

    done = get_done_telegram_files()
    assert raw.replace("\\", "/") in done
