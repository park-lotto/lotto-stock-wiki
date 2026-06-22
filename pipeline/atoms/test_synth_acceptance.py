"""질문 7종 수용 테스트: 페이지 구조 검증 (LLM 비결정성 없음)."""
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
SK = ROOT / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md"

def test_q1_q7_structure_present():
    md = SK.read_text(encoding="utf-8")
    assert "## 종합 스토리" in md          # Q1 현재
    assert "증권사 컨센서스" in md          # Q2 히스토리
    assert "출처" in md                     # Q3 근거
    assert "충돌" in md or "모순" in md      # Q7 충돌

def test_no_fabricated_source_merge():
    # 날조 = 두 파일명을 ·로 합쳐 '하나의 .md'로 만든 것 (예: 태린이아빠·하나반도체.md).
    # 정당한 다중출처(a.md · b.md, 각자 .md)는 허용 — 각 파일이 실존하므로 추적 가능.
    md = SK.read_text(encoding="utf-8")
    import re
    bad = re.findall(r"[가-힣A-Za-z]{2,}·[가-힣A-Za-z]{2,}\.md", md)
    assert not bad, f"날조 의심 출처(한 .md에 합침): {bad}"
