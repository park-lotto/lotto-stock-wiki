"""auto_deploy.sh 재시작 연기·재시도 검증(2026-07-30).

왜 실행 테스트인가: 이건 배포 스크립트라 **finish 게이트가 못 잡는다**(파이썬이 아니다).
그리고 여기서 틀리면 증상이 "라이브가 옛 코드로 조용히 돈다"라서 눈에 안 보인다 —
실제로 2026-07-30 14:21에 그 일이 났고(worker 연기 후 재시도 없음), 이 파일이 그 재발을 막는다.

방법: 스크립트를 그대로 실행하되 git·systemctl·python 조회를 가짜 실행파일(PATH 앞)로
바꿔치기하고, 경로 상수(REPO/LOG/PENDING/SINCE/DB)를 sed로 tmp로 돌린다. 즉 **스크립트의
분기 로직 자체**를 검증한다(주석이나 grep이 아니라).

bash가 없는 환경(윈도우 순수 파이썬)에서는 스킵한다 — 서버·git-bash에서는 돌아간다.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "deploy" / "auto_deploy.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(not BASH or not SRC.exists(),
                               reason="bash 또는 auto_deploy.sh 없음")


def _harness(tmp_path, *, local="aaa", remote="bbb", changed="shopping_shorts/app.py",
             users_online=False, worker_busy=False, pending=None, since_epoch=None):
    """스크립트를 tmp 환경으로 복제하고 가짜 git/systemctl/python3을 심는다."""
    root = tmp_path
    bin_dir = root / "bin"
    bin_dir.mkdir()
    repo = root / "repo"
    (repo / "shopping_shorts" / "data").mkdir(parents=True)
    log = root / "deploy.log"
    pend = root / "pending"
    since = root / "since"
    calls = root / "calls.txt"

    # 가짜 git: rev-parse HEAD/origin-main만 답하고 나머지는 성공 처리
    (bin_dir / "git").write_text(f"""#!/usr/bin/env bash
case "$*" in
  *"rev-parse HEAD"*) echo "{local}" ;;
  *"rev-parse origin/main"*) echo "{remote}" ;;
  *"rev-parse --short"*) echo "{remote[:7]}" ;;
  *"diff --name-only"*) printf '%s\\n' {changed!r} ;;
  *"reset --hard"*) echo "git reset" >>"{calls}" ;;
  *) : ;;
esac
exit 0
""", encoding="utf-8")

    # 가짜 sudo/systemctl: 어떤 유닛을 재시작했는지 기록
    (bin_dir / "sudo").write_text(f"""#!/usr/bin/env bash
shift 2 2>/dev/null   # 'systemctl restart' 두 토큰 제거
echo "restart:$1" >>"{calls}"
exit 0
""", encoding="utf-8")

    # 가짜 python3: 첫 인자가 DB면 heredoc 내용에 따라 답한다 → 여기선 호출 순서로 구분하지 않고
    # 환경변수로 강제한다(스크립트가 두 조회에 같은 python3을 쓰므로 heredoc 본문으로 가른다).
    (bin_dir / "python3").write_text(f"""#!/usr/bin/env bash
body=$(cat)                      # heredoc 본문을 읽어 무슨 조회인지 판별
if echo "$body" | grep -q job_queue; then
  echo "check:worker" >>"{calls}"
  exit {0 if worker_busy else 1}
fi
if echo "$body" | grep -q customers; then
  echo "check:users" >>"{calls}"
  exit {0 if users_online else 1}
fi
exit 1
""", encoding="utf-8")

    for f in ("git", "sudo", "python3"):
        os.chmod(bin_dir / f, 0o755)

    if pending is not None:
        pend.write_text("".join(f"{p}\n" for p in pending), encoding="utf-8")
    if since_epoch is not None:
        since.write_text(str(since_epoch), encoding="utf-8")

    script = root / "auto_deploy.sh"
    text = SRC.read_text(encoding="utf-8")
    text = text.replace("REPO=/home/ubuntu/lotto-stock-wiki", f'REPO="{repo}"')
    text = text.replace("LOG=/tmp/auto_deploy.log", f'LOG="{log}"')
    text = text.replace("PENDING=/tmp/ss_pending_restart", f'PENDING="{pend}"')
    text = text.replace("SINCE=/tmp/ss_pending_since", f'SINCE="{since}"')
    text = text.replace("exec 9>/tmp/auto_deploy.lock", f'exec 9>"{root}/lock"')
    # git-bash에는 flock이 없어 그 줄에서 스크립트가 그냥 종료된다(실측). 락은 서버에서만
    # 의미가 있으므로 테스트에서만 통과시킨다 — 스크립트 본문은 그대로 둔다.
    text = text.replace("flock -n 9 || exit 0", "true   # 테스트 하네스: flock 없음")
    script.write_text(text, encoding="utf-8")
    os.chmod(script, 0o755)

    env = dict(os.environ, PATH=f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    subprocess.run([BASH, str(script)], env=env, cwd=str(root),
                   capture_output=True, timeout=60)
    return {
        "calls": calls.read_text(encoding="utf-8") if calls.exists() else "",
        "log": log.read_text(encoding="utf-8") if log.exists() else "",
        "pending": pend.read_text(encoding="utf-8") if pend.exists() else "",
        "since_exists": since.exists(),
    }


def test_no_users_restarts_web_and_worker(tmp_path):
    """아무도 없고 작업도 없으면 웹·워커 둘 다 즉시 재시작, 대기 목록은 비워진다."""
    r = _harness(tmp_path)
    assert "restart:shopping-shorts" in r["calls"]
    assert "restart:shopping-shorts-worker" in r["calls"]
    assert r["pending"] == ""
    assert not r["since_exists"]          # 대기가 끝나면 시각 파일도 사라진다


def test_web_restart_deferred_while_users_online(tmp_path):
    """고객 접속 중이면 웹 재시작을 미루고 대기 목록에 남긴다(워커는 한가하니 재시작)."""
    r = _harness(tmp_path, users_online=True)
    assert "restart:shopping-shorts\n" not in r["calls"]
    assert "웹 재시작 연기" in r["log"]
    assert "shopping-shorts\n" in r["pending"]
    assert "restart:shopping-shorts-worker" in r["calls"]


def test_worker_restart_deferred_while_job_running(tmp_path):
    """작업 진행 중이면 워커 재시작을 미룬다 — 재시작하면 그 렌더가 죽는다."""
    r = _harness(tmp_path, worker_busy=True)
    assert "restart:shopping-shorts-worker" not in r["calls"]
    assert "worker 재시작 연기" in r["log"]
    assert "shopping-shorts-worker\n" in r["pending"]


def test_pending_is_retried_without_new_commit(tmp_path):
    """★핵심 회귀방지: 새 커밋이 없어도(LOCAL==REMOTE) 대기 목록을 다시 시도한다.
    예전 코드는 여기서 곧바로 종료해 연기한 재시작이 영원히 실행되지 않았다."""
    r = _harness(tmp_path, local="same", remote="same",
                 pending=["shopping-shorts-worker"], since_epoch=1)
    assert "restart:shopping-shorts-worker" in r["calls"]
    assert r["pending"] == ""


def test_nothing_happens_when_idle_and_no_pending(tmp_path):
    """새 커밋도 대기도 없으면 아무것도 하지 않는다(3분마다 헛일 금지)."""
    r = _harness(tmp_path, local="same", remote="same")
    assert r["calls"] == ""


def test_force_restart_after_max_defer(tmp_path):
    """무한 연기 방지 — 30분 넘으면 고객이 접속 중이어도 웹을 강제 재시작한다.
    '배포가 영영 안 감'이 이 repo 최악 사고라, 끊김 몇 초보다 그게 더 위험하다."""
    r = _harness(tmp_path, local="same", remote="same", users_online=True,
                 pending=["shopping-shorts"], since_epoch=1)   # 1970년 = 아주 오래 전
    assert "restart:shopping-shorts" in r["calls"]
    assert "강제 재시작" in r["log"]


def test_worker_never_force_restarted(tmp_path):
    """워커는 강제하지 않는다 — 강제하면 진행 중인 사용자 렌더가 죽는다."""
    r = _harness(tmp_path, local="same", remote="same", worker_busy=True,
                 pending=["shopping-shorts-worker"], since_epoch=1)
    assert "restart:shopping-shorts-worker" not in r["calls"]
    assert "shopping-shorts-worker\n" in r["pending"]
