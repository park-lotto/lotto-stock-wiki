from pathlib import Path
import scripts.card_render as cr

DATA = {"date": "2026-06-28", "headline": "반도체 강세 지속",
        "lead_sectors": ["반도체", "조선"], "lines": ["코스피 강보합", "순환매"]}

def test_render_contains_card_and_content(tmp_path):
    hero = tmp_path / "hero.png"; hero.write_bytes(b"\x89PNG")
    html = cr.render_briefing_card(DATA, hero)
    assert 'class="card"' in html          # 캡처 대상 요소 존재
    assert "반도체 강세 지속" in html        # 헤드라인
    assert "코스피 강보합" in html           # 시나리오 라인
    assert "2026-06-28" in html             # 날짜
    assert "width:420px" in html.replace(" ", "")  # 폭 고정

def test_render_embeds_hero_as_file_uri(tmp_path):
    hero = tmp_path / "hero.png"; hero.write_bytes(b"\x89PNG")
    html = cr.render_briefing_card(DATA, hero)
    assert hero.as_uri() in html

def test_save_card_html(tmp_path):
    p = cr.save_card_html("<html>x</html>", tmp_path / "c.html")
    assert p.exists() and "x" in p.read_text(encoding="utf-8")

def test_render_escapes_special_chars(tmp_path):
    hero = tmp_path / "hero.png"; hero.write_bytes(b"\x89PNG")
    data = {"date": "2026-06-28", "headline": "코스피 > 3000 & 강세",
            "lead_sectors": ["반도체"], "lines": ["저항 < 돌파"]}
    html_output = cr.render_briefing_card(data, hero)
    assert "&gt;" in html_output and "&amp;" in html_output and "&lt;" in html_output
    assert "> 3000 &" not in html_output  # raw unescaped must not appear
