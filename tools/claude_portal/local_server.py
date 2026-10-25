# -*- coding: utf-8 -*-
"""클로드형 로컬 시험 서버(관제 234 — 라이브 배포 전 회원 경로를 끝까지 돌려 보는 곳, 0순위-A1c).
진짜 app(shopping_shorts.app)을 127.0.0.1 에 띄우고, 시험 DB·시험 비밀·스위치·라이선스 키를 준비한다. 지시서는 엔진 트랙(CLAUDE_FLOW_ENGINE).

    PYTHONUTF8=1 py tools/claude_portal/local_server.py --engine <엔진 트랙> --dir <시험 폴더> [--port 18849]
    → <시험 폴더>/license.key (값은 출력하지 않는다) · 서버는 이 프로세스가 끝날 때까지 돈다
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--port", type=int, default=18849)
    ap.add_argument("--channel-root", default="", help="프리셋 틀(channel/<slug>/preset) 뿌리 — 기본 = --engine. 라이브 서버 흉내(엔진 묶음엔 channel/ 이 없다)는 저장소 뿌리를 준다")
    a = ap.parse_args()
    d = Path(a.dir); d.mkdir(parents=True, exist_ok=True)
    sf = d / "secret.txt"                            # 서버를 다시 켜도 같은 비밀값 — 진행 중 편의 서명 payload 가 이어지게(이어 가기 시험)
    if not sf.exists():
        sf.write_text("local-test-" + os.urandom(8).hex(), encoding="utf-8")
    os.environ.update(CLAUDE_CHANNEL_ROOT=str(Path(a.channel_root or a.engine).resolve()), CLAUDE_FLOW_ENGINE=str(Path(a.engine).resolve()),
                      CLAUDE_STORE_DIR=str(d / "store"), CLAUDE_LICENSE_SECRET=sf.read_text(encoding="utf-8").strip())
    sys.path.insert(0, str(ROOT))
    from shopping_shorts import app as A, claude_portal as cp
    from shopping_shorts.store import Store
    A.DB_PATH = d / "test.db"                        # 시험 DB(라이브 DB 아님)
    st = Store(A.DB_PATH)
    for k, v in (("claude_portal_enabled", "1"), ("claude_assets_enabled", "1")):
        st.set_setting(k, v)
    if not (d / "license.key").exists():
        (d / "license.key").write_text(cp.issue_license(1, st)["key"], encoding="utf-8")
    print(f"[local_server] http://127.0.0.1:{a.port} 프리셋 {len(cp.presets(st))}개 · 키 파일 {d / 'license.key'}", flush=True)
    import uvicorn
    uvicorn.run(A.app, host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
