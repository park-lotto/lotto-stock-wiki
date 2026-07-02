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


def _insert_telegram_atom(raw_file: str):
    import uuid
    from datetime import datetime
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
            str(uuid.uuid4()), "2026-06-19", "telegram", "하나반도체", 3, raw_file,
            "L5", "반도체", "하나반도체", "sector",
            "bullish", "analysis", "medium", "text", 70,
            "테스트 내용", "[]",
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def test_get_done_telegram_files_dedup():
    """이미 DB에 기록된 텔레그램 파일은 basename으로 done set에 포함되어야 한다."""
    dbmod.init_db()
    dbmod.migrate_db()
    _insert_telegram_atom("raw/telegram/2026-06-19_하나반도체.md")
    done = get_done_telegram_files()
    assert "2026-06-19_하나반도체.md" in done


def test_dedup_matches_regardless_of_path_form():
    """상대경로로 저장돼도 절대경로 파일과 basename으로 매칭돼야 한다 (재처리 방지)."""
    dbmod.init_db()
    dbmod.migrate_db()
    # 상대경로로 저장 (단일파일 인제스트 케이스)
    _insert_telegram_atom("raw/telegram/2026-06-19_하나반도체.md")
    done = get_done_telegram_files()
    # 절대경로 형태의 파일도 같은 basename → done에 잡힘
    abs_name = "C:/Users/x/raw/telegram/2026-06-19_하나반도체.md"
    from pathlib import Path
    assert Path(abs_name).name in done


def test_insight_leading_sectors_and_noise_ratio_preserved():
    import json
    from pipeline.atoms.telegram_questionnaire import questionnaire_to_atoms_tg
    q = {
        "leading_sectors": ["반도체", "2차전지"],
        "stance": [], "methods": [], "stocks_mentioned": [],
        "noise_ratio": 0.4,
        "quote": "지금은 반도체 순환매가 핵심이다",
    }
    meta = {"date": "2026-07-02", "channel": "요약하는 고잉", "type": "insight",
            "source_type": "telegram", "trust": "C", "raw_file": "x.md"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    summary = [a for a in atoms if a["asset_level"] == "insight_summary"]
    assert len(summary) == 1, f"insight_summary 원자가 안 만들어짐: {[a['id'] for a in atoms]}"
    sf = json.loads(summary[0]["structured_fields"])
    assert sf["leading_sectors"] == ["반도체", "2차전지"]
    assert sf["noise_ratio"] == 0.4
    assert sf["quote"] == "지금은 반도체 순환매가 핵심이다"


def test_insight_summary_skipped_when_all_empty():
    from pipeline.atoms.telegram_questionnaire import questionnaire_to_atoms_tg
    q = {"stance": [], "methods": [], "stocks_mentioned": []}
    meta = {"date": "2026-07-02", "channel": "요약하는 고잉", "type": "insight",
            "source_type": "telegram", "trust": "C", "raw_file": "x.md"}
    atoms = questionnaire_to_atoms_tg(q, meta)
    assert not any(a["asset_level"] == "insight_summary" for a in atoms)
