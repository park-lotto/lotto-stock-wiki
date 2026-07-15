import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import log_view


def test_parse_entries_extracts_date_and_line():
    text = "- 2026-07-15 — 꾸미기 완료\n- 2026-07-14 — 카드 작업\n"
    entries = log_view.parse_entries(text, "꾸미기")
    assert len(entries) == 2
    assert entries[0]["date"] == "2026-07-15"
    assert entries[0]["track"] == "꾸미기"
    assert "꾸미기 완료" in entries[0]["line"]


def test_parse_entries_ignores_non_entry_lines():
    text = "# 제목\n\n> 소유 트랙: 꾸미기\n- 2026-07-15 — 진짜 항목\n"
    entries = log_view.parse_entries(text, "꾸미기")
    assert len(entries) == 1
    assert "진짜 항목" in entries[0]["line"]


def test_collect_reads_all_track_files(tmp_path):
    d = tmp_path / "log.d"
    d.mkdir()
    (d / "꾸미기.md").write_text("- 2026-07-15 — 꾸미기 것\n", encoding="utf-8")
    (d / "보이스.md").write_text("- 2026-07-14 — 보이스 것\n", encoding="utf-8")
    entries = log_view.collect(d)
    assert len(entries) == 2
    assert {e["track"] for e in entries} == {"꾸미기", "보이스"}


def test_collect_skips_readme(tmp_path):
    d = tmp_path / "log.d"
    d.mkdir()
    (d / "README.md").write_text("- 2026-07-15 — 이건 규칙문서\n", encoding="utf-8")
    (d / "꾸미기.md").write_text("- 2026-07-15 — 진짜\n", encoding="utf-8")
    entries = log_view.collect(d)
    assert len(entries) == 1
    assert entries[0]["track"] == "꾸미기"


def test_render_sorts_newest_first_and_tags_track():
    entries = [
        {"date": "2026-07-14", "track": "보이스", "line": "- 2026-07-14 — 보이스 것"},
        {"date": "2026-07-15", "track": "꾸미기", "line": "- 2026-07-15 — 꾸미기 것"},
    ]
    out = log_view.render(entries)
    assert out.index("꾸미기 것") < out.index("보이스 것")
    assert "[꾸미기]" in out
