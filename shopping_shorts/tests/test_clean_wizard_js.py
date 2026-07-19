import os
import re
import subprocess
import tempfile

HTML = os.path.join(os.path.dirname(__file__), "..", "static", "produce.html")


def _script_src():
    src = open(HTML, encoding="utf-8").read()
    return "\n".join(re.findall(r"<script>(.*?)</script>", src, re.S))


def test_clean_preview_markers_present():
    html = open(HTML, encoding="utf-8").read()
    assert 'id="btnCleanPreview"' in html
    assert 'id="cleanPreview"' in html
    js = _script_src()
    assert "function startCleanPreview" in js
    assert "function pollClean" in js
    assert "/api/produce/mix/clean" in js
    assert "clean_thumb" in js


def test_script_still_parses():
    js = _script_src()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js); path = f.name
    try:
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True,
                           stdin=subprocess.DEVNULL)
        assert r.returncode == 0, r.stderr
    finally:
        os.unlink(path)
