import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "dashboard"))

import server
from fastapi.testclient import TestClient


def test_catalysts_page_serves_html():
    r = TestClient(server.app).get("/catalysts")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    body = r.text
    assert "다가오는 촉매" in body
    assert "/api/catalysts" in body      # 프론트가 API에 바인딩돼 있어야 함
    assert "/api/watchlist" in body
