# -*- coding: utf-8 -*-
"""숏클 회원 판 게시 — 무대(설치본 폴더)를 묶어 서버에 올리고 등록한다(숏클cs팀 절차 4단계).

  py -X utf8 tools/shortcl_cs/publish.py <판 번호> "<한 줄 설명>" [--stage C:/t/build134/win-x64/Shortem]
    예) py -X utf8 tools/shortcl_cs/publish.py 1.0.103 "자막 겹침 수리"

엔진 트랙 폴더(.tracks/칼카피숏템엔진)에서 실행한다(tools.claude_portal 을 그 폴더에서 읽는다).
게시 뒤 묶음 확인은 check_zip, 확인이 끝나면 묶음 파일을 지운다(C 드라이브 공간 — 묶음 약 306MB).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("note")
    ap.add_argument("--stage", default="C:/t/build134/win-x64/Shortem")
    ap.add_argument("--out", default="C:/t")
    a = ap.parse_args()
    from tools.claude_portal import upload_release as U
    from tools.claude_portal.publish_update import make_zip
    stage = Path(a.stage)
    (stage / "app_version.json").write_text(json.dumps({"version": a.version}))
    b = make_zip(stage, a.version)
    uz = Path(a.out) / f"shortem-app-{a.version}.zip"
    uz.write_bytes(b)
    sha = U.sha256(uz)
    print("zip MB", round(len(b) / 1e6, 1), sha[:12])
    U.ssh(f"mkdir -p {U.UPLOAD}")
    U.scp([uz], f"{U.UPLOAD}/")
    note = a.note.replace("'", "")[:80]
    reg = ("from pathlib import Path;from shopping_shorts import claude_portal as cp;"
           f"p=Path('{U.UPLOAD}/shortem-app-{a.version}.zip');sha,size=cp.put_blob(p);p.unlink();"
           f"cp.update_register('{a.version}',sha,size,'{note}');print(sha)")
    got = U.ssh(f"cd {U.REPO} && echo {base64.b64encode(reg.encode()).decode()} | base64 -d | /usr/bin/python3 -").strip().splitlines()[-1]
    print("서버 sha 일치", got == sha)
    print("묶음:", uz)


if __name__ == "__main__":
    main()
