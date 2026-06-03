from pathlib import Path
from scripts.channel_pipeline.models import WikiDecision
from scripts.channel_pipeline.wiki_writer import apply_decisions


def test_append_to_existing_section(tmp_wiki):
    decisions = [
        WikiDecision(
            claim_id="tg_001",
            action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 협상 본격화 (태린이아빠/텔레그램)",
        )
    ]
    apply_decisions(decisions, root=tmp_wiki)
    content = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    assert "- [2026-06-04] HBM4 협상 본격화" in content
    # 새 줄이 기존 이벤트 위에 있어야 함 (최상단 추가)
    new_idx = content.index("- [2026-06-04]")
    old_idx = content.index("- [2026-05-01]")
    assert new_idx < old_idx


def test_flag_adds_conflict_note(tmp_wiki):
    decisions = [
        WikiDecision(
            claim_id="rp_001",
            action="flag",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] HBM4 공급과잉 우려 (KB증권/리포트)",
            conflict_note="태린이아빠(bullish)와 방향 상충",
        )
    ]
    apply_decisions(decisions, root=tmp_wiki)
    content = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    assert "⚠️ 태린이아빠(bullish)와 방향 상충" in content


def test_skip_does_not_modify(tmp_wiki):
    decisions = [
        WikiDecision(claim_id="yt_001", action="skip",
                     wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md")
    ]
    original = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    apply_decisions(decisions, root=tmp_wiki)
    after = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    assert original == after


def test_creates_section_if_missing(tmp_wiki):
    f = tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_삼성전자.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("# 삼성전자\n\n## 기본 정보\n테스트\n", encoding="utf-8")
    decisions = [
        WikiDecision(
            claim_id="tg_002",
            action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_삼성전자.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] 갤럭시 AI 출하 (테스트)",
        )
    ]
    apply_decisions(decisions, root=tmp_wiki)
    content = f.read_text(encoding="utf-8")
    assert "## 최신 이벤트" in content
    assert "- [2026-06-04] 갤럭시 AI 출하" in content


def test_creates_file_if_missing(tmp_wiki):
    decisions = [
        WikiDecision(
            claim_id="tg_003",
            action="append",
            wiki_file="wiki/L5_섹터/조선/stock/stock_HD현대중공업.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] LNG선 수주 (태린이아빠)",
        )
    ]
    apply_decisions(decisions, root=tmp_wiki)
    f = tmp_wiki / "wiki/L5_섹터/조선/stock/stock_HD현대중공업.md"
    assert f.exists()
    assert "## 최신 이벤트" in f.read_text(encoding="utf-8")


def test_dry_run_no_write(tmp_wiki):
    decisions = [
        WikiDecision(
            claim_id="tg_001",
            action="append",
            wiki_file="wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md",
            section="## 최신 이벤트",
            line="- [2026-06-04] dry-run 테스트",
        )
    ]
    original = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    modified = apply_decisions(decisions, root=tmp_wiki, dry_run=True)
    after = (tmp_wiki / "wiki/L5_섹터/반도체/stock/stock_SK하이닉스.md").read_text(encoding="utf-8")
    assert original == after           # 파일 변경 없음
    assert len(modified) == 1          # 반환값은 수정 예정 파일 목록
