from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CSS = (BASE / "static" / "theme.css").read_text(encoding="utf-8")
HTML = (BASE / "static" / "produce.html").read_text(encoding="utf-8")


def test_theme_tokens_defined():
    for tok in ("--bg:#070b14", "--mint:#3ee0bf", "--aurora", "--gold:#facc6b"):
        assert tok in CSS, tok


def test_theme_component_classes():
    for cls in (".orbbar", ".orb", ".skm-card", ".cta-shine", ".stat-tile", ".strip", ".thea", ".aurora-bg"):
        assert cls in CSS, cls


def test_produce_links_theme_and_brands():
    assert 'href="theme.css' in HTML          # 링크(캐시버전 ?v= 허용)
    assert "숏템메이커" in HTML                 # 리브랜딩
    assert 'class="aurora-bg"' in HTML         # 배경 요소
