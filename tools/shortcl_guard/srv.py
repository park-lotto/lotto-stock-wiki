# 돌려쓰기 차단 시험 서버(관제 296) — 임시 DB, 회원 7번. e2e.py 와 짝. 준비: C:/t/guard/client 에 shortem_client/server 복사 후 npm ci --omit=dev
import os
import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parents[2])
sys.path.insert(0, ROOT)
os.environ.update(CLAUDE_STORE_DIR=r"C:\t\guard\store", CLAUDE_LICENSE_SECRET="guard-test-secret", DASH_PASS="")
from shopping_shorts import app as a  # noqa: E402
from shopping_shorts import claude_portal as cp  # noqa: E402
from shopping_shorts.store import Store  # noqa: E402
import uvicorn  # noqa: E402

a.DB_PATH = Path(r"C:\t\guard\t.db")
st = Store(a.DB_PATH)
st.set_setting("claude_portal_enabled", "1")
orig = a._claude_me
a._claude_me = lambda request: (7, Store(a.DB_PATH), None)   # 회원 페이지 = 7번 회원
key = cp.issue_license(7, st)["key"]
Path(r"C:\t\guard\key.txt").write_text(key, encoding="ascii")
uvicorn.run(a.app, host="127.0.0.1", port=18871, log_level="warning")
