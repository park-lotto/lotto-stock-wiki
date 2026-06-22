from pipeline.atoms.synth_engine import _build_prompt, _build_sector_prompt


def test_prompt_includes_page_atoms_and_rules():
    page = "# SK하이닉스\n## 최신 이벤트\n| 날짜 | 내용 | 출처 | 신호 |\n"
    atoms = [{"content": "12단 HBM4E 샘플 출하", "date": "2026-06-19",
              "sources": ["raw/telegram/a.md"], "certainty": "관측"}]
    p = _build_prompt(page, atoms)
    assert "12단 HBM4E" in p
    assert "raw/telegram/a.md" in p          # 실존 출처 전달
    assert "날조" in p or "실존" in p          # 출처 날조 금지 규칙
    assert "위키에 없" in p or "지어내" in p    # 정직 규칙


def test_sector_prompt_targets_market_section():
    page = "# 반도체 섹터\n## 시장 국면\n"
    atoms = [{"content": "반도체 ETF 1조달러 손실", "date": "2026-06-06",
              "sources": ["raw/news/x.md"], "certainty": "사실"}]
    p = _build_sector_prompt(page, atoms)
    assert "시장 국면" in p
    assert "반도체 ETF" in p
    assert "raw/news/x.md" in p


from pipeline.atoms.synth_engine import validate_synthesis
import pytest

def test_guard_rejects_short_output():
    old = "x" * 1000
    with pytest.raises(ValueError):
        validate_synthesis(old, "x" * 100)  # 10% → 거부

def test_guard_rejects_changelog():
    old = "x" * 1000
    with pytest.raises(ValueError):
        validate_synthesis(old, "갱신 완료. 변경 사항 요약: ..." + "y" * 900)

def test_guard_passes_normal_update():
    old = "x" * 1000
    validate_synthesis(old, "x" * 1050)  # 정상 갱신 → 통과(예외 없음)
