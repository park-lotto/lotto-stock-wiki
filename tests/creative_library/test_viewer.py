import json
from pathlib import Path

from creative_library.viewer import build_viewer


def test_viewer_escapes_catalog_text_and_never_overwrites(tmp_path):
    import pytest
    base = tmp_path / "repo" / "shopping_shorts" / "static"
    base.mkdir(parents=True)
    (base / "fonts.json").write_text(json.dumps([{
        "name": "</script><script>alert(1)</script>", "file": "Missing.ttf", "css": "Missing",
    }]), encoding="utf-8")
    out = build_viewer(tmp_path / "repo", tmp_path / "index.html")
    html = out.read_text(encoding="utf-8")
    assert "</script><script>alert(1)</script>" not in html
    assert "\\u003c/script>" in html
    assert "Missing.ttf" in html
    with pytest.raises(FileExistsError):
        build_viewer(tmp_path / "repo", out)


def test_real_browser_search_font_audio_detail_and_mobile():
    """Real file-backed UI smoke test, manually selected for local verification."""
    import os
    import pytest
    root = os.environ.get("CREATIVE_VIEWER_TEST_REPO")
    if not root:
        pytest.skip("Set CREATIVE_VIEWER_TEST_REPO for real local browser verification")
    playwright = pytest.importorskip("playwright.sync_api")
    out = build_viewer(Path(root))
    errors = []
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(out.as_uri())
        assert page.locator("article.card").count() == 140
        page.locator('[data-domain="font"]').click()
        assert page.locator("article.card").count() == 40
        page.evaluate("document.fonts.ready")
        assert page.evaluate("[...document.fonts].every(f => f.status === 'loaded')")
        page.screenshot(path=str(out.parent / "library.png"), full_page=False)
        page.locator("#query").fill("프리텐다드")
        assert page.locator("article.card").count() > 0
        page.locator(".detail").first.click()
        assert page.locator("dialog").is_visible()
        assert "프리텐다드" in page.locator("#detail-title").inner_text()
        page.locator("#close").click()
        page.locator("#query").fill("")
        page.locator('[data-domain="voice"]').click()
        assert page.locator("audio").count() == 65
        page.locator("audio").first.evaluate("a => {a.load(); return a.play();}")
        page.wait_for_function("document.querySelector('audio').currentTime > 0")
        page.locator("audio").first.evaluate("a => a.pause()")
        page.set_viewport_size({"width": 390, "height": 844})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#query").fill("zzzz不存在")
        assert page.locator(".empty").is_visible()
        assert not errors
        browser.close()
    print(json.dumps({"viewer": str(out), "screenshot": str(out.parent / "library.png")}, ensure_ascii=False))
