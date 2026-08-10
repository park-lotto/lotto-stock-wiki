"""find_work 회귀 테스트 — 손 관리 목록이 썩어 53개 기록을 못 찾던 문제(2026-08-09).

이 도구의 존재 이유가 "목록을 손으로 관리하지 않는다"이므로, 테스트도
**실제 파일을 만들어** 검색되는지 본다(목록 자료구조를 검사하지 않는다).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tools.find_work as fw           # noqa: E402


@pytest.fixture
def fake_tree(tmp_path, monkeypatch):
    """handoff/·wiki/log.d/ 를 흉내낸 임시 트리로 갈아끼운다."""
    ho = tmp_path / "handoff"
    lg = tmp_path / "wiki" / "log.d"
    ho.mkdir(parents=True)
    lg.mkdir(parents=True)
    (ho / "카테고리분류.md").write_text(
        "# 카테고리 분류 정확도\n키워드 54% vs Gemini 77%\n", encoding="utf-8")
    (ho / "보이스.md").write_text(
        "# 보이스 프리셋\nElevenLabs 권한 함정\n", encoding="utf-8")
    (lg / "카테고리분류.md").write_text(
        "- 2026-07-18 카테고리 작업 로그\n", encoding="utf-8")
    monkeypatch.setattr(fw, "BASE", tmp_path)
    monkeypatch.setattr(fw, "SEARCH_DIRS", [ho, lg])
    monkeypatch.setattr(fw, "EXTRA_FILES", [])
    monkeypatch.setattr(fw, "_MEM", None)
    return tmp_path


def test_finds_by_keyword(fake_tree):
    """주제어만 알면 파일명을 몰라도 찾아야 한다 — 이게 핵심 요구다."""
    hits = fw.search(["카테고리"])
    names = [h[3].name for h in hits]

    assert "카테고리분류.md" in names
    assert "보이스.md" not in names, "무관한 트랙이 섞이면 안 된다"


def test_filename_match_ranks_first(fake_tree):
    """파일명에 낱말이 있으면 위로 — 트랙 이름이 곧 주제인 경우가 많다."""
    hits = fw.search(["카테고리"])

    assert hits[0][3].name == "카테고리분류.md"


def test_all_terms_beat_partial(fake_tree, tmp_path):
    """낱말을 다 포함한 문서가 일부만 포함한 문서보다 위여야 한다."""
    (tmp_path / "handoff" / "둘다.md").write_text(
        "카테고리와 보이스를 함께 다룬다\n", encoding="utf-8")

    hits = fw.search(["카테고리", "보이스"])

    assert hits[0][3].name == "둘다.md"


def test_no_hits_is_not_an_error(fake_tree):
    """기록이 없으면 '새 작업'이라고 알려주면 된다 — 실패가 아니다."""
    assert fw.search(["존재하지않는주제zzz"]) == []


def test_reads_cp949_files(fake_tree, tmp_path):
    """옛 파일이 cp949로 저장돼 있어도 검색돼야 한다(윈도우 환경)."""
    p = tmp_path / "handoff" / "옛파일.md"
    p.write_bytes("# 레거시 카테고리 메모\n".encode("cp949"))

    names = [h[3].name for h in fw.search(["카테고리"])]

    assert "옛파일.md" in names


def test_collect_includes_both_dirs(fake_tree):
    """핸드오프와 로그를 **둘 다** 본다 — 로그에만 남은 사건이 있다."""
    hits = fw.search(["카테고리"])
    parents = {h[3].parent.name for h in hits}

    assert parents == {"handoff", "log.d"}
