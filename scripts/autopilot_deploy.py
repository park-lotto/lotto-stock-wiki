"""배포 실행 — 오케스트레이터가 서버와 같은 박스에서 도니 SSH/SCP 없이 로컬 파일시스템+git.
target=local: /home/ubuntu/lotto-stock-wiki에서 git commit+push, allowlist 파일이면 서비스 재시작.
target=remote_crawler: /home/ubuntu/kmong/crawling_bot 파일 직접 교체(백업 먼저)+서비스 재시작."""
import os
import shutil
import subprocess
import time

SERVER_SYNCED_PATHS = ("server.py", "dashboard/")


def _run(cmd, cwd=None, timeout=30):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, encoding="utf-8",
                           errors="replace", timeout=timeout)


def needs_service_restart(changed_paths, allowlist=SERVER_SYNCED_PATHS):
    return any(p.startswith(prefix) for p in changed_paths for prefix in allowlist)


def deploy_local(repo_root, commit_message, changed_paths):
    """git add -A+commit+push. 커밋 해시 반환(실패 시 None). allowlist 경로가 바뀌었으면
    stockbrain 재시작까지."""
    _run(["git", "add", "-A"], cwd=repo_root)
    commit = _run(["git", "commit", "-m", commit_message], cwd=repo_root)
    if commit.returncode != 0:
        return None
    push = _run(["git", "push", "origin", "main"], cwd=repo_root, timeout=60)
    if push.returncode != 0:
        return None
    log = _run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    commit_hash = log.stdout.strip()
    if needs_service_restart(changed_paths):
        _run(["sudo", "systemctl", "restart", "stockbrain"], timeout=20)
    return commit_hash


def rollback_local(repo_root, commit_hash, changed_paths):
    revert = _run(["git", "revert", "--no-edit", commit_hash], cwd=repo_root, timeout=30)
    if revert.returncode != 0:
        return False
    push = _run(["git", "push", "origin", "main"], cwd=repo_root, timeout=60)
    if push.returncode != 0:
        return False
    if needs_service_restart(changed_paths):
        _run(["sudo", "systemctl", "restart", "stockbrain"], timeout=20)
    return True


def backup_remote_files(crawler_root, relative_paths, backup_root):
    """수정 전 원본을 backup_root/<timestamp>/에 복사. {상대경로: 백업절대경로} 반환."""
    ts = str(int(time.time()))
    dest_dir = os.path.join(backup_root, ts)
    os.makedirs(dest_dir, exist_ok=True)
    backups = {}
    for rel in relative_paths:
        src = os.path.join(crawler_root, rel)
        if not os.path.exists(src):
            continue
        dst = os.path.join(dest_dir, rel.replace(os.sep, "__").replace("/", "__"))
        shutil.copy2(src, dst)
        backups[rel] = dst
    return backups


def deploy_remote_crawler(crawler_root):
    """파일은 apply_fix()가 이미 직접 수정해뒀다고 가정 — 여기선 서비스 재시작만 담당."""
    result = _run(["sudo", "systemctl", "restart", "crawlingbot"], timeout=20)
    return result.returncode == 0


def rollback_remote_crawler(crawler_root, backups):
    for rel, backup_path in backups.items():
        shutil.copy2(backup_path, os.path.join(crawler_root, rel))
    return deploy_remote_crawler(crawler_root)


def health_check(service_name, retries=3, delay=2.0):
    for _ in range(retries):
        r = _run(["systemctl", "is-active", service_name], timeout=10)
        if r.stdout.strip() == "active":
            return True
        time.sleep(delay)
    return False


def append_wiki_log(repo_root, line):
    """wiki/log.md 맨 위(최신순 관례)에 한 줄 추가. 자동수정 성공 시 오케스트레이터가 호출."""
    path = os.path.join(repo_root, "wiki", "log.md")
    try:
        with open(path, encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = ""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n" + existing)
