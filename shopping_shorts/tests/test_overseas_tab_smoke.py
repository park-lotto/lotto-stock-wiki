import os

INDEX = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")


def test_overseas_entry_present():
    html = open(INDEX, encoding="utf-8").read()
    assert "해외HOT" in html
    assert "/api/overseas/feed" in html
    assert "/api/overseas/update" in html
    assert "renderOverseas" in html
    assert "toggleOverseas" in html
