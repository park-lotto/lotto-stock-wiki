"""윈도 작업 스케줄러 등록 — 관제 도구가 쓰는 예약 작업 명령은 여기 한 곳에서만 만든다(관제 107).

왜 한 곳인가(2026-10-03 실측): storage.py·live_check.py 가 같은 명령을 각자 적으면서 둘 다 따옴표를 `\\"` 로 감쌌다.
cmd.exe 는 `\\"` 를 모른다 → `cd /d \\"C:\\...\\"` 가 「파일 이름 구문이 잘못됨」으로 실패 → 뒤 명령·로그 리디렉션까지
통째로 안 돎. 그래서 **04:40 저장층 정리(C→D 이동)와 매시간 라이브 실측이 등록된 날부터 한 번도 돌지 않았고**(Last Result 1,
로그 파일 0개) C 드라이브가 계속 찼다.

cmd /c 규칙: 따옴표가 셋 이상이면 cmd 는 **맨 앞과 맨 뒤 따옴표 하나씩만** 벗긴다 → 바깥을 한 겹 더 감싸고 안쪽은 평범한 " 로 둔다.
"""
import shutil
import subprocess
import sys
from pathlib import Path


def task_command(repo, script_args, log_path, python=None):
    """작업 스케줄러 /TR 에 넣을 문자열. script_args 예: ["tools\\\\storage.py", "apply", "--auto"]."""
    py = python or shutil.which("python") or sys.executable
    inner = 'cd /d "%s" && "%s" %s >> "%s" 2>&1' % (repo, py, " ".join(script_args), log_path)
    return 'cmd /c "%s"' % inner


def register(name, schedule_args, repo, script_args, log_path, printer=print):
    """schedule_args 예: ["/SC", "DAILY", "/ST", "04:40"]. 성공하면 True."""
    cmd = task_command(repo, script_args, Path(log_path))
    r = subprocess.run(["schtasks", "/Create", "/F", *schedule_args, "/TN", name, "/TR", cmd],
                       capture_output=True, text=True, encoding="cp949", errors="replace")
    ok = r.returncode == 0
    printer(("✅ 작업 스케줄러 등록: %s" % name) if ok else ("❌ 등록 실패: " + (r.stdout + r.stderr).strip()[:200]))
    return ok
