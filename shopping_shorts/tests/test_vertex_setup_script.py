"""버텍스 원클릭 설정 스크립트(관제 096) — 클라우드 셸에서 `curl … | bash`로 도는 파일의 모양 검사.

진짜 검사는 새 구글 계정 클라우드 셸에서 끝까지 돌려 나온 키로 「확인하고 연결」이 통과하는 것이다.
여기서는 그 전에 깨지면 안 되는 것만 본다: 줄바꿈(LF), 문법, 반쪽 실행 방지, 키 붙여넣기 칸과 짝.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "static" / "landing" / "vertex_setup.sh"


def test_lf_only():
    # CRLF면 클라우드 셸 bash가 `$'\r': command not found`로 죽는다
    assert b"\r" not in SCRIPT.read_bytes()


def test_runs_only_after_full_download():
    # 받다 끊기면 main이 정의만 되고 안 불린다 — 마지막 줄이 호출이어야 한다
    lines = [l for l in SCRIPT.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines[-1].strip() == 'main "$@"'
    assert lines[1].startswith("#") and "main() {" in SCRIPT.read_text(encoding="utf-8")


@pytest.mark.skipif(not shutil.which("bash"), reason="bash 없음")
def test_bash_syntax():
    r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")


def test_output_is_what_register_accepts():
    # 마지막에 찍는 한 줄 JSON을 vertex_route.validate_sa가 받는지 — 모양이 같은 가짜 키로
    import json
    from shopping_shorts import vertex_route
    fake = {"type": "service_account", "project_id": "shorts-261003-1234",
            "client_email": "shortsmaker@shorts-261003-1234.iam.gserviceaccount.com",
            "private_key": "-----BEGIN PRIVATE KEY-----\nAAA\n-----END PRIVATE KEY-----\n"}
    one_line = json.dumps(fake, separators=(",", ":"))
    info, err = vertex_route.validate_sa(one_line)
    assert err == "" and info["project_id"] == fake["project_id"]
    assert "separators=(\",\",\":\")" in SCRIPT.read_text(encoding="utf-8")
