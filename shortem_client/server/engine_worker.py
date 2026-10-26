"""숏템 설정 화면 상주 워커(관제 266) — 엔진 preview_request 를 한 프로세스에 띄워 두고 줄마다 부른다.

  python engine_worker.py <엔진 폴더>   (회원 PC engine_bridge.engineTool · 서버 claude_studio._Worker 공용)
  표준입력 한 줄 = {"op": "catalog"|"check"|"preview"|"look", ...} → 표준출력 한 줄 = 결과 JSON

왜: 클릭마다 엔진 프로세스를 새로 띄우면 import 만 1~5초(10-25 실측 클릭 1번 10.8초).
    띄워 둔 프로세스는 preview 0.004초(서버 실측). 판단은 엔진(preview_request) 그대로 — 여기는 부르기만 한다.
"""
from __future__ import annotations

import json
import sys


def main(engine: str) -> int:
    sys.path.insert(0, engine)
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    from tools.calcopy import preview_request as P   # 엔진 묶음의 것(고객 PC 와 같은 코드)
    cat = None
    print(json.dumps({"ready": True}), flush=True)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            op = req.get("op")
            if op == "catalog":
                cat = cat or P.catalog()
                out = {"catalog": cat}
            elif op == "check":
                cat = cat or P.catalog()
                out = {"errors": P.check(req.get("pack") or {}, cat)}
            elif op == "preview":
                out = P.preview(req)
            elif op == "banned":   # 회원 PC 에서 못 쓰는 목소리(엔진 voices.BANNED_VOICES 한 곳 — 필재 등). 옛 묶음엔 없을 수 있다
                try:
                    from tools.calcopy.engine.voices import BANNED_VOICES
                except ImportError:
                    BANNED_VOICES = {}
                out = {"banned": sorted(BANNED_VOICES)}
            elif op == "look":   # 꾸민 모양 검사 = 엔진 판 scene_style(칼카피 틀 customFrame 을 설명서 규칙으로 따로 검사한다 — 렌더러와 같은 판)
                from shopping_shorts import scene_style as SS
                try:
                    out = {"snapshot": SS.validate_snapshot(req.get("snapshot"))}
                except ValueError as e:
                    out = {"invalid": str(e)}
            else:
                out = {"error": f"모르는 일: {op}"}
        except Exception as e:  # noqa: BLE001 — 화면에 이유 한 줄(조용한 실패 금지), 워커는 계속 산다
            out = {"error": f"{type(e).__name__}: {e}"}
        print(json.dumps(out, ensure_ascii=False, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
