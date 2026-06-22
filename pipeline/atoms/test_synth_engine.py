from pipeline.atoms.synth_engine import _build_prompt


def test_prompt_includes_page_atoms_and_rules():
    page = "# SK하이닉스\n## 최신 이벤트\n| 날짜 | 내용 | 출처 | 신호 |\n"
    atoms = [{"content": "12단 HBM4E 샘플 출하", "date": "2026-06-19",
              "sources": ["raw/telegram/a.md"], "certainty": "관측"}]
    p = _build_prompt(page, atoms)
    assert "12단 HBM4E" in p
    assert "raw/telegram/a.md" in p          # 실존 출처 전달
    assert "날조" in p or "실존" in p          # 출처 날조 금지 규칙
    assert "위키에 없" in p or "지어내" in p    # 정직 규칙
