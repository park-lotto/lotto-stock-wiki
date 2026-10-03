"""트랙별 작업 폴더 — 시작 / 끝 / 목록.

설계: docs/superpowers/specs/2026-07-15-트랙폴더-병합게이트-design.md

한 PC에서 6개 세션이 같은 폴더·같은 인덱스로 일하면 먼저 커밋하는 세션이
남의 미완성 코드를 **물리적으로** 자기 커밋에 담는다(흡수). 락으로는 못 막는다
— 락은 '언제 커밋하나'만 조율하고 '파일 안에 뭐가 들었나'는 못 바꾼다.
그래서 트랙마다 자기 폴더(worktree)+자기 브랜치를 준다.

폴더를 나누면 흡수는 사라지지만 **의미적 충돌**이 커진다(A가 함수명을 바꾸고
B가 옛 버전을 보고 그 함수를 부르면, 텍스트가 안 겹쳐 깨끗이 병합되고 main이
ImportError). 그래서 병합에 게이트가 붙는다 — merge_gate.py.

★ post-commit이 무조건 `git push`다. 그래서 병합은 반드시
  `merge --no-ff --no-commit`(커밋 없음 → 훅 안 돎) → 게이트 → 통과해야 commit.
  순진하게 merge하면 게이트가 돌기 전에 이미 라이브다.

사용:
    py tools/track.py start 보이스
    py tools/track.py finish 보이스
    py tools/track.py list
"""
import argparse
import contextlib
import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import control as _control
import merge_gate
import video_gate as _video_gate

BRANCH_PREFIX = "track/"
MAIN_BRANCH = "main"

# 세션 6개가 동시에 finish하면 각자 전체 pytest 게이트를 병렬로 돌려 서로 CPU를 뺏어
# 전부 기어간다(2026-07-24 실측: 5개 동시 → 20분+ 지연). 게이트는 CPU 포화라 병렬이
# 오히려 손해 → 한 번에 하나만 돌게 줄 세운다. OS 파일락이라 프로세스가 죽으면 커널이
# 자동 해제(스테일락 없음). 락은 트랙별이 아니라 **전역 1개**(모든 finish가 같은 파일).
_FINISH_LOCK = Path(tempfile.gettempdir()) / "stockbrain_track_finish.lock"
# ★영상 관문 전용 락(2026-10-02, 카드 075): 서버 영상 비교(10~25분)는 로컬 CPU 를 안 쓴다 → 전역 finish 락을 놓고
#   이 락으로만 줄 세운다(서버에서 비교 두 개가 겹치지 않게). 그동안 다른 트랙의 pytest·병합은 진행한다.
_VIDEO_LOCK = Path(tempfile.gettempdir()) / "stockbrain_video_gate.lock"


def _lock_path(env_key, default):
    """시험 중엔 개별 락(전역 락을 잡으면 게이트 안에서 교착한다). 환경변수가 주면 그것."""
    v = os.environ.get(env_key)
    if v:
        return Path(v)
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return Path(tempfile.gettempdir()) / ("%s_test_%d.lock" % (default.stem, os.getpid()))
    return default


def _finish_lock_path():
    return _lock_path("TRACK_FINISH_LOCK", _FINISH_LOCK)


def _video_lock_path():
    return _lock_path("TRACK_VIDEO_LOCK", _VIDEO_LOCK)


# ★자원 관문(2026-10-03 카드 092 — 사장님 "병합이 한 번에 다 같이 들어가서 CPU 많이 쓰는 거 아닌가 / 근본 방법으로").
#   종전(088) '칸 2개 × 병렬 8' = 시험 프로세스 16개 → 코어를 다 쓰고(09-21 사장님 "게이트 돌 때마다 PC 버벅" 으로 정한
#   '코어 절반'을 깼다), 메모리도 한 판 4.0~4.5GB(실측)라 두 판이 8.5GB → 남은 메모리 2.7GB, Claude 가 작업을 강제 종료.
#   이제 **시험 프로세스 표(GATE_WORKER_TOKENS)** 를 병합 전체가 나눠 쓴다: 합계 8개 이하(코어 절반) + 남은 메모리로 더 줄인다.
#   몰리면 한 판씩 전속력(-n 8 376초)으로 — 둘이 반씩(-n 4 각 727초)보다 먼저 끝난다(카드 081 실측).
GATE_WORKER_TOKENS = 8           # 동시에 도는 시험 프로세스 합계 상한(16코어의 절반)
GATE_WORKER_MB = 550             # 시험 프로세스 1개 메모리(실측: -n 8 한 판 4,027~4,501MB / 13~14개)
GATE_RESERVE_MB = 2500           # 다른 프로그램(크롬·Claude 세션)을 위해 남기는 메모리
GATE_MIN_WORKERS = 2


def _free_mb():
    """지금 남은 물리 메모리(MB). 못 재면 큰 값(막지 않는다)."""
    try:
        import ctypes

        class _MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = _MS()
        m.dwLength = ctypes.sizeof(_MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return int(m.ullAvailPhys / 2 ** 20)
    except Exception:  # noqa: BLE001
        return 10 ** 6


def _gate_target_workers(free_mb):
    """남은 메모리로 돌릴 수 있는 시험 프로세스 수(최대 GATE_WORKER_TOKENS). 최소치도 안 되면 0(기다린다)."""
    n = (int(free_mb) - GATE_RESERVE_MB) // GATE_WORKER_MB
    n = min(GATE_WORKER_TOKENS, n)
    return n if n >= GATE_MIN_WORKERS else 0


@contextlib.contextmanager
def _gate_slot():
    """시험 프로세스 표를 잡는다 → 쓸 병렬 수(n)를 돌려준다(GATE_XDIST_N 으로 merge_gate 에 넘긴다).
    표가 모자라거나 메모리가 모자라면 기다린다. 프로세스가 죽으면 커널이 표를 놓는다(파일락)."""
    import msvcrt
    base = _finish_lock_path()
    held, waited, last_why = [], False, ""
    while True:
        target = _gate_target_workers(_free_mb())
        if target:
            for i in range(GATE_WORKER_TOKENS):
                if len(held) >= target:
                    break
                f = open(base.parent / ("%s_worker%d.lock" % (base.stem, i)), "a+")
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    held.append(f)
                except OSError:
                    f.close()
            if len(held) >= target:
                break
            why = "다른 병합이 시험 프로세스 표를 쓰는 중(%d/%d 확보)" % (len(held), target)
        else:
            why = "남은 메모리 %dMB — 최소 %d개분(%dMB+여유 %dMB) 모자람" % (
                _free_mb(), GATE_MIN_WORKERS, GATE_MIN_WORKERS * GATE_WORKER_MB, GATE_RESERVE_MB)
        for f in held:                       # 다 못 잡았으면 쥔 것도 놓고 기다린다(조금씩 쥐고 버티면 서로 굶는다)
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                f.close()
        held = []
        if not waited or why != last_why:
            print("[대기] 시험 자원 대기 — %s (줄과 별개 — 줄은 안 막는다)" % why)
            waited, last_why = True, why
        time.sleep(5)
    n = len(held)
    prev = os.environ.get("GATE_XDIST_N")
    os.environ["GATE_XDIST_N"] = str(n)
    print("시험 자원: 병렬 %d (남은 메모리 %dMB)" % (n, _free_mb()))
    try:
        yield n
    finally:
        if prev is None:
            os.environ.pop("GATE_XDIST_N", None)
        else:
            os.environ["GATE_XDIST_N"] = prev
        for f in held:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                f.close()


class _FileLock:
    """OS 파일락(프로세스가 죽으면 커널이 자동 해제). 같은 객체로 놓았다 다시 잡을 수 있다(release/acquire).
    queue=True: **선착순 번호표**(2026-10-02 카드 081) — 종전엔 3초마다 '지금 잡히나'를 찔러 먼저 찌른 쪽이 들어가
    오늘 최대 2시간 26분을 기다린 세션이 있었다. 번호표 = <락 이름>_queue/<시각ns>_<pid>_<객체id>, 맨 앞만 락을 시도.
    죽은 프로세스의 번호표는 지나가는 쪽이 치운다. 옛 판본 finish(번호표 모름)는 끼어들 수 있다 — 전환기만."""

    def __init__(self, path, wait_msg, queue=False):
        self.path, self.wait_msg, self.fh = Path(path), wait_msg, None
        self.queue, self._ticket = queue, None

    def _qdir(self):
        return self.path.parent / (self.path.stem + "_queue")

    def _new_ticket(self, priority=False):
        q = self._qdir()
        q.mkdir(parents=True, exist_ok=True)
        stamp = ("0" * 20) if priority else ("%020d" % time.time_ns())
        t = q / ("%s_%d_%d" % (stamp, os.getpid(), id(self)))
        t.write_text("", encoding="utf-8")
        return t

    def _my_turn(self):
        live = []
        for t in sorted(self._qdir().glob("*_*_*")):
            try:
                pid = int(t.name.split("_")[1])
            except (IndexError, ValueError):
                continue
            if pid != os.getpid() and not _pid_alive(pid):
                try:
                    t.unlink()                      # 죽은 프로세스의 번호표
                except OSError:
                    pass
                continue
            live.append(t)
        if live and live[0].name != self._ticket.name:
            return False, live.index(self._ticket) if self._ticket in live else len(live)
        return True, 0

    def acquire(self, priority=False):
        if self.queue and self._ticket is None:
            self._ticket = self._new_ticket(priority=priority)
        self.fh = open(self.path, "a+")
        if os.name == "nt":
            import msvcrt
            waited = False
            while True:
                turn, ahead = self._my_turn() if self.queue else (True, 0)
                if turn:
                    try:
                        msvcrt.locking(self.fh.fileno(), msvcrt.LK_NBLCK, 1)
                        return self
                    except OSError:
                        pass
                if not waited:
                    print(self.wait_msg + ((" (앞에 %d명)" % ahead) if self.queue and ahead else ""))
                    waited = True
                time.sleep(1 if turn else 3)
        import fcntl
        try:
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print(self.wait_msg)
            fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX)
        return self

    def release(self):
        if self.fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self.fh.seek(0)
                msvcrt.locking(self.fh.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            self.fh.close()
            self.fh = None
            if self._ticket is not None:
                try:
                    self._ticket.unlink()
                except OSError:
                    pass
                self._ticket = None


@contextlib.contextmanager
def _finish_gate_lock(prepared=None):
    """finish 전역 직렬화 락. 이미 다른 finish가 게이트 중이면 풀릴 때까지 대기(순번제). → 락 객체(영상 관문 동안 놓는다).
    prepared: 번호표를 미리 받아 둔 락(선검사 동안 줄을 서 둔 것)."""
    lk = (prepared or _FileLock(_finish_lock_path(),
                                "[대기] 다른 트랙이 finish 게이트 중 - 선착순 대기(동시 실행이 더 느려서 줄 세운다)",
                                queue=True)).acquire()
    try:
        yield lk
    finally:
        lk.release()


def _run_video_gate_unlocked(lk, video_gate, stage, br):
    """영상 관문을 **전역 finish 락 밖**에서 돌린다 — 영상 락만 쥔다. 끝나면 finish 락을 다시 잡고 돌아온다.
    lk 가 None 이면(옛 호출) 그대로 돌린다."""
    if lk is None:
        # 줄 밖에서 부른 경우(카드 088) — 영상 락만 쥔다(서버 비교는 한 번에 하나).
        if video_gate is _video_gate.run_video_gate:
            try:
                if not _video_gate.gate_decision(stage)[2] or os.environ.get("VIDEO_GATE_SKIP", "").strip():
                    return video_gate(stage, br)
            except Exception:  # noqa: BLE001
                pass
            vlk = _FileLock(_video_lock_path(), "[대기] 다른 트랙의 영상 관문이 서버에서 도는 중 - 순번 대기...").acquire()
            try:
                return video_gate(stage, br)
            finally:
                vlk.release()
        return video_gate(stage, br)
    if video_gate is _video_gate.run_video_gate:
        # 건너뛸 병합이면 락을 놓지 않는다 — 놓았다 다시 잡는 사이 다른 트랙이 가져가면 그쪽 pytest 를 통째로 기다린다.
        try:
            if not _video_gate.gate_decision(stage)[2] or os.environ.get("VIDEO_GATE_SKIP", "").strip():
                return video_gate(stage, br)
        except Exception:  # noqa: BLE001 — 판정을 못 하면 종전대로(락 놓고) 돈다
            pass
    lk.release()
    print("  (영상 관문은 전역 병합 락 밖에서 돈다 — 그동안 다른 트랙 finish 는 진행한다)")
    vlk = _FileLock(_video_lock_path(), "[대기] 다른 트랙의 영상 관문이 서버에서 도는 중 - 순번 대기...").acquire()
    try:
        return video_gate(stage, br)
    finally:
        vlk.release()
        lk.acquire(priority=True)        # 이미 줄을 섰던 병합 — 번호표 맨 앞으로(카드 081)


def _stage_owner_file(stage):
    stage = Path(stage)
    return stage.parent / (stage.name + ".owner")


def _mark_stage_owner(stage):
    """이 stage 를 쓰는 프로세스를 적는다 — 영상 관문 동안 락을 놓아도 다른 finish 의 청소가 지우지 않게."""
    try:
        _stage_owner_file(stage).write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass


def _pid_alive(pid):
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            code = ctypes.c_ulong()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(code))) and code.value == 259   # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)                                  # posix 만 — 윈도에서 0 은 CTRL_C_EVENT 라 쓰면 안 된다
        return True
    except OSError:
        return False


def _stage_in_use(stage):
    try:
        pid = int(_stage_owner_file(stage).read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return pid != os.getpid() and _pid_alive(pid)


def _sh(cmd, cwd):
    """cwd가 없어도 크래시하지 않는다 — 지워진 트랙 폴더를 가리킬 수 있다(finish 직후 등).
    subprocess는 없는 cwd에 NotADirectoryError를 던지는데, 그건 호출자가 다룰 수 없다."""
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except (NotADirectoryError, FileNotFoundError) as e:
        return 127, str(e)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main_worktree(cwd=None):
    """이 저장소의 **main 워크트리**를 찾는다 — git에게 물어서.

    ★`__file__` 기준으로 잡으면 안 된다. 트랙 폴더에는 tools/track.py의 복사본이 있어서,
    거기서 부르면 BASE가 그 트랙 폴더가 되고 `worktree_path`가 존재하지도 않는
    `.tracks/<이름>/.tracks/<이름>`을 가리킨다 → finish가 "트랙 폴더가 없다"로 깨진다
    (2026-07-16 실측). CLAUDE.md에 "finish는 main 폴더에서"라는 우회를 적어둬야 했던 이유.

    `git rev-parse --git-common-dir`는 링크된 워크트리에서도 **공유 .git**을 가리킨다
    → 그 부모가 main 워크트리다.
    """
    start = Path(cwd) if cwd else Path(__file__).resolve().parent
    rc, out = _sh(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], start)
    if rc == 0 and out.strip():
        return Path(out.strip()).resolve().parent
    return Path(__file__).resolve().parent.parent      # git이 없거나 구버전이면 옛 방식


BASE = main_worktree()

# 트랙 폴더는 프로젝트 **안**에 둔다 — 사장님이 찾기 쉬운 곳.
# 점(.)으로 시작하는 이유 2가지:
#   ① 이 폴더는 옵시디언 볼트고 .md가 11,120개다. 점 폴더는 옵시디언이 인덱싱에서
#      자동 제외하므로, 트랙마다 볼트에 중복 노트 1만여 개가 생기는 걸 막는다.
#   ② .gitignore(/.tracks/)와 짝 — main 워킹트리가 트랙 폴더를 untracked로 보지 않는다.
TRACKS_DIR = ".tracks"
STAGE_PREFIX = "_merge-"
# 병합 폴더에 푸는 경로(카드 081) — 시험·관문이 읽는 것. 큰 데이터(raw·productions·channel·wiki 본문)는 뺀다.
STAGE_SPARSE = ("/*", "/shopping_shorts/", "/tools/", "/pipeline/", "/dashboard/", "/scripts/", "/deploy/",
                "/extension/", "/docs/", "/out/", "/관제/", "/wiki/rules/", "/handoff/", "/.claude/", "/.github/")

# 봇 산출물·런타임 파일 — main 폴더에 이게 더러워도 병합을 막지 않는다.
# (크롤봇이 raw/에 계속 쓴다. 이걸로 막으면 게이트가 영원히 안 돈다.)
_IGNORABLE = ("raw/", "out/", "wiki/log.d/", ".fablize/", ".superpowers/", ".tracks/")
_IGNORABLE_PARTS = ("/data/", "__pycache__/")
_IGNORABLE_SUFFIX = (".db", ".db-journal", ".db-wal", ".pyc", ".log")


class TrackError(Exception):
    """사람에게 그대로 보여줄 중단 사유."""


def _git_env_for(cwd):
    """cwd 가 .tracks 안이면 git 이 그 위(= main 폴더)로 올라가지 못하게 막는다(GIT_CEILING_DIRECTORIES).
    ★2026-10-03 실측(카드 093): 다른 finish 의 청소가 막 만든 병합 폴더를 지우자, 그 폴더에서 돈 `git merge` 가 상위의
    main 폴더 저장소를 찾아 **main 폴더에서 병합**했다 → MERGE_HEAD 가 남아 main 폴더 동기화가 2시간 멈췄다."""
    try:
        cp = Path(cwd).resolve()
    except OSError:
        return None
    for anc in [cp] + list(cp.parents):
        if anc.name == TRACKS_DIR:
            return dict(os.environ, GIT_CEILING_DIRECTORIES=str(anc))
    return None


def run(cmd, cwd, check=False):
    p = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=_git_env_for(cwd),
    )
    out = (p.stdout or "") + (p.stderr or "")
    if check and p.returncode != 0:
        raise TrackError(f"명령 실패: {' '.join(cmd)}\n{out}")
    return p.returncode, out


def validate_name(name):
    """폴더·브랜치 이름이 될 것이므로 경로를 벗어나는 이름을 막는다."""
    if not name or not name.strip():
        raise TrackError("트랙 이름이 비었다")
    bad = set('/\\:*?"<>| \t')
    if any(c in bad for c in name) or ".." in name or name.startswith("."):
        raise TrackError(
            f"트랙 이름에 쓸 수 없는 문자: {name!r}\n"
            "경로 구분자·공백·'..'는 폴더와 브랜치를 깨뜨린다."
        )
    return name


def branch_name(name):
    return f"{BRANCH_PREFIX}{name}"


# ── 디스크 병목 막기(2026-09-27 사장님 "세션들이 작업할 때 병목 안 생기게") ─────────────
# 실측: 트랙 1개 1.8GB × 51개 = C 드라이브 63GB → 여유 9GB에서 finish가 임시 병합 폴더를 만들다
#   중간에 끊기고(_merge-* 잔해 1.8GB씩), npm 업데이트까지 깨졌다(코덱스 사고).
# ① 트랙은 코드가 안 읽는 무거운 폴더를 디스크에 풀지 않는다(sparse). raw/ 481MB·productions/ 132MB.
#    raw/는 크롤봇이 **main 폴더에만** 쓰는 원본이라 트랙 쪽 사본은 어차피 낡았다(CLAUDE.md).
#    ★게이트 임시 폴더(stage)는 그대로 전체 — 기준선·병합 뒤 둘 다 같은 조건이어야 비교가 정직하다.
# ② 오래 안 쓴 트랙은 '주차'(브랜치 보존·원격 백업 뒤 폴더만 제거) — 되살리기 1분.
# ③ 디스크 경보·거절: 여유가 모자라면 시작 전에 말하고, finish는 임시 폴더를 만들다 끊기기 전에 멈춘다.
# ④ finish 락을 잡은 순간 남은 _merge-* 잔해는 전부 죽은 것 — 치운다.
SPARSE_EXCLUDE = ("/raw/", "/productions/")
DISK_WARN_GB = 15
DISK_REFUSE_GB = 3          # stage(전체 체크아웃 ~1.8GB) + pytest 임시를 못 담는 수준
IDLE_PARK_DAYS = 7


def disk_free_gb(path=BASE):
    try:
        return shutil.disk_usage(str(path)).free / 1024 ** 3
    except OSError:
        return None


def _disk_guard(repo, action):
    """여유가 모자라면 경고(+주차 후보 안내), 아주 모자라면 finish를 거절한다."""
    free = disk_free_gb(repo)
    if free is None:
        return
    if action == "finish" and free < DISK_REFUSE_GB:
        raise TrackError(
            f"디스크 여유 {free:.1f}GB — 병합용 임시 폴더(약 1.8GB)를 만들다 중간에 끊겨 잔해가 남는다.\n"
            f"먼저 공간을 비워라: py tools/track.py park-idle  (오래 안 쓴 트랙 폴더만 치움, 브랜치 보존)")
    if free < DISK_WARN_GB:
        print(f"⚠️ 디스크 여유 {free:.1f}GB (<{DISK_WARN_GB}GB). 오래 안 쓴 트랙 폴더를 치우면 트랙당 1~2GB가 돌아온다:")
        print("   py tools/track.py park-idle        (브랜치·원격 백업 보존, 미커밋 있으면 건너뜀)")


def _apply_sparse(wt):
    """트랙 폴더에 무거운 폴더를 풀지 않는다. 실패하면 전체 체크아웃 그대로 두고 **말한다**(조용히 넘기지 않음)."""
    patterns = ["/*"] + ["!" + p for p in SPARSE_EXCLUDE]
    rc, out = run(["git", "sparse-checkout", "set", "--no-cone"] + patterns, wt)
    if rc != 0:
        print(f"⚠️ 가벼운 트랙(sparse) 설정 실패 — 전체 폴더로 계속한다:\n{out.strip()[:200]}")
        return False
    print(f"   가벼운 트랙: {', '.join(SPARSE_EXCLUDE)} 는 풀지 않음(필요하면: git sparse-checkout disable)")
    return True


STAGE_YOUNG_SEC = 1800          # 이보다 젊은 주인 없는 병합 폴더는 청소하지 않는다


def _clean_dead_stages(repo, keep=None):
    """finish 락을 쥔 뒤에만 부른다 — 락이 있으니 지금 살아 있는 stage는 없다(있다면 keep 하나)."""
    root = tracks_dir(repo)
    if not root.exists():
        return []
    removed = []
    for d in root.iterdir():
        if d.is_dir() and d.name.startswith(STAGE_PREFIX) and d.name != keep:
            if _stage_in_use(d):
                continue                 # 영상 관문 동안 락을 놓은 다른 finish 의 살아 있는 stage(2026-10-02, 카드 075)
            if not _stage_owner_file(d).exists():
                try:
                    if time.time() - d.stat().st_mtime < STAGE_YOUNG_SEC:
                        continue         # 주인 표시 없는 막 생긴 폴더 — 옛 판본 finish 가 만드는 중일 수 있다(카드 093)
                except OSError:
                    continue
            run(["git", "worktree", "remove", "--force", str(d)], repo)
            try:
                _stage_owner_file(d).unlink()
            except OSError:
                pass
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
            removed.append(d.name)
    if removed:
        run(["git", "worktree", "prune"], repo)
        print(f"🧹 끊긴 병합 임시 폴더 {len(removed)}개 정리: {', '.join(removed)}")
    return removed


def tracks_dir(repo=BASE):
    return Path(repo).resolve() / TRACKS_DIR


def worktree_path(name, repo=BASE):
    """`<프로젝트>/.tracks/<이름>` — 프로젝트 안. gitignore + 옵시디언 자동제외로 안전."""
    return tracks_dir(repo) / name


def is_ignorable(path):
    p = path.replace("\\", "/")
    return (
        p.startswith(_IGNORABLE)
        or any(part in p for part in _IGNORABLE_PARTS)
        or p.endswith(_IGNORABLE_SUFFIX)
    )


def parse_status(porcelain):
    """git status --porcelain → 경로 목록."""
    paths = []
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:  # rename
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip('"'))
    return paths


def dirty_code_files(repo):
    """봇 산출물을 뺀 '진짜' 더러운 파일."""
    _, out = run(["git", "status", "--porcelain"], repo)
    return [p for p in parse_status(out) if not is_ignorable(p)]


def current_branch(repo):
    _, out = run(["git", "branch", "--show-current"], repo)
    return out.strip()


def worktree_exists(name, repo=BASE):
    return worktree_path(name, repo).exists()


def branch_exists(repo, branch):
    rc, _ = run(["git", "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], repo)
    return rc == 0


# ── start ────────────────────────────────────────────────────────

def _detach_upstream_from_main(wt, br):
    """★ `worktree add -b <br> origin/main`은 upstream을 **origin/main으로 박는다.**

    그러면 트랙 폴더의 커밋마다 post-commit의 인자 없는 `git push`가
    '트랙 브랜치를 main으로 밀어라'가 된다 — 게이트를 통째로 우회하는 경로다.
    지금 사고가 안 나는 건 순전히 `push.default`가 unset(=git 기본 `simple`)이라
    git이 거절해주기 때문이다(실측 2026-07-16). **누가 `push.default=upstream`으로
    바꾸는 순간 트랙 커밋이 곧장 main으로 나간다.** 우연에 기대지 않는다.

    → upstream을 끊고, 자기 이름의 원격 브랜치로 다시 건다(백업 겸용).
      원격에 못 올리면 upstream 없는 채로 둔다 — 그러면 post-commit이
      무해하게 실패할 뿐 main은 안전하다.
    """
    run(["git", "branch", "--unset-upstream"], wt)
    rc, out = run(["git", "push", "-u", "origin", f"HEAD:{br}"], wt)
    if rc != 0:
        print(f"ℹ️ 트랙 브랜치를 origin에 못 올렸다 — 로컬에만 둔다(병합엔 지장 없다).\n   {out.strip()[:200]}")


def _copy_local_secrets(repo, wt):
    """`.env`를 트랙 폴더에 복사한다 — **이게 없으면 트랙에서 AI 작업이 통째로 막힌다.**

    `.env`는 gitignore(비밀키)라 worktree로 안 따라온다. 그런데 `key_vault._ENV_PATH`는
    **모듈 위치 기준**이라 트랙 폴더에선 `.tracks/<이름>/.env`를 찾고, 없으니 키가 0개가 된다
    (2026-07-16 실측: main 45개 / 트랙 0개 → Gemini 영상분석이 "키풀이 비었다"로 죽었다).

    복사가 안전한 이유: 같은 PC·같은 사용자이고, 트랙 폴더에서도 `.env`는 gitignore라
    커밋될 수 없다. 없으면(서버·CI) 조용히 넘어간다.
    """
    src = Path(repo).resolve() / ".env"
    if not src.exists():
        return
    try:
        shutil.copy2(src, wt / ".env")
        print("   .env 복사됨 (트랙에서도 AI 키 사용 가능)")
    except OSError as e:
        print(f"⚠️ .env를 못 복사했다 — 이 트랙에선 AI 작업이 막힌다: {e}")


def upstream_of(wt):
    rc, out = run(["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], wt)
    return out.strip() if rc == 0 else None


def start(name, repo=BASE, full=False, card=None):
    merge_gate.make_output_safe()
    validate_name(name)
    _disk_guard(repo, "start")
    # ★관제(2026-09-28): 카드 없는 트랙은 없다. 관제가 설치된 저장소(origin/main 에 관제/cards)에서만 검사한다.
    run(["git", "fetch", "origin"], repo)
    if _control.installed(repo):
        if card is None:
            raise TrackError(
                "관제 카드 없이는 트랙을 열지 않는다(관제 원칙 1 — 모든 시작은 관제 등록에서).\n"
                "  ① 카드 등록: py tools/control.py new \"<제목>\" --from <제보자> --owner <파일:함수> --done \"<됐다의 기준>\"\n"
                f"  ② 트랙 열기: py tools/track.py start {name} --card <번호>\n"
                "  (있는 카드 보기: py tools/control.py list)")
        if _control.find_card(_control.cards_from_ref(repo), card) is None:
            raise TrackError(f"없는 관제 카드: {card}  (목록: py tools/control.py list)")
    wt = worktree_path(name, repo)
    if wt.exists():
        raise TrackError(
            f"이미 있는 트랙 폴더: {wt}\n"
            "덮어쓰지 않는다. 이어서 쓰려면 그 폴더에서 Claude Code를 열어라."
        )
    if branch_exists(repo, branch_name(name)):
        raise TrackError(
            f"이미 있는 브랜치: {branch_name(name)}\n"
            f"폴더만 없다면 되살릴 수 있다: git worktree add \"{wt}\" {branch_name(name)}"
        )

    run(["git", "fetch", "origin"], repo)
    wt.parent.mkdir(parents=True, exist_ok=True)
    rc, out = run(
        ["git", "worktree", "add", str(wt), "-b", branch_name(name), "origin/main"],
        repo,
    )
    if rc != 0:
        raise TrackError(f"worktree 생성 실패:\n{out}")

    _detach_upstream_from_main(wt, branch_name(name))
    _copy_local_secrets(repo, wt)
    if not full:
        _apply_sparse(wt)
    if card is not None:
        try:
            _control.link_track(repo, card, name)
        except _control.ControlError as e:
            print(f"⚠️ 카드 {card}에 트랙을 못 적었다(트랙은 만들어졌다) — 손으로: py tools/control.py link {card} {name}\n   {e}")

    print(f"✅ 트랙 '{name}' 시작" + (f"  (관제 카드 {card:03d})" if card is not None else ""))
    print(f"   폴더:    {wt}")
    print(f"   브랜치:  {branch_name(name)} (origin/main 기준)")
    print()
    print("   이제 그 폴더에서 Claude Code를 열어라. 여기(main 폴더)에서 일하지 마라 —")
    print("   그러면 흡수가 그대로 재발한다.")
    print()
    print("   ⚠️ shopping_shorts/data/ 는 gitignore라 새 폴더는 빈 DB로 시작한다.")
    print("      로컬 데이터가 필요하면 복사해 오거나 서버에서 확인해라.")
    print(f"   끝나면: py tools/track.py finish {name}")
    return 0


# ── finish ───────────────────────────────────────────────────────

def _preflight(name, repo):
    """트랙 폴더만 본다. **main 폴더는 검사하지도, 건드리지도 않는다** —
    거기선 다른 세션 5개가 계속 일하고 있고, 우리는 그 폴더를 쓰지 않는다."""
    wt = worktree_path(name, repo)
    if not wt.exists():
        raise TrackError(f"트랙 폴더가 없다: {wt}\n먼저: py tools/track.py start {name}")

    _, st = run(["git", "status", "--porcelain"], wt)
    if [p for p in parse_status(st) if not is_ignorable(p)]:
        raise TrackError(
            f"트랙 폴더가 dirty다 — 커밋 먼저 해라.\n\n{st}\n"
            f"(폴더: {wt})"
        )
    return wt


def _open_stage(repo, name):
    """병합·게이트 전용 임시 폴더 (origin/main에 detached).

    ★ 왜 main 폴더에서 안 하나: `merge --no-commit` 후 게이트(pytest)가 도는
    수 분 동안 main 폴더는 '반쯤 병합된' 상태가 된다. 그 창에 다른 세션이
    커밋하면 그 반쪽 병합을 통째로 담아 push한다 — 없애려던 흡수가 바로
    그 자리에서 되살아난다. 게다가 옆 세션의 편집이 게이트 결과를 오염시켜
    없는 실패가 잡힌다(오탐). 전용 폴더는 둘 다 원천 차단한다.
    """
    stage = tracks_dir(repo) / f"{STAGE_PREFIX}{name}"
    stage.parent.mkdir(parents=True, exist_ok=True)
    if stage.exists():
        run(["git", "worktree", "remove", "--force", str(stage)], repo)
    # ★코드 폴더만 푼다(2026-10-02 카드 081 실측: 전체 만들기 45초+지우기 19초·1229MB → 9초+3초·600MB).
    #   병합·관제·영향 지도는 git(index/ref)에서 읽고, 시험이 읽는 폴더(static·userscript·out·deploy·extension·docs)는 아래에 다 있다.
    # ★주인 표시를 **만들기 전에**(카드 093) — 만든 뒤에 쓰던 몇 초 사이 다른 finish 의 청소가 '주인 없는 잔해'로 보고 지웠다(실측).
    _mark_stage_owner(stage)
    rc, out = run(["git", "worktree", "add", "--detach", "--no-checkout", str(stage), "origin/main"], repo)
    if rc != 0:
        raise TrackError(f"병합용 임시 폴더를 못 만들었다:\n{out}")
    rc, out = run(["git", "sparse-checkout", "set", "--no-cone", *STAGE_SPARSE], stage)
    if rc == 0:
        rc, out = run(["git", "checkout"], stage)
    if rc != 0:                                   # 경량 실패 → 전체로(종전) — 병합을 막지 않는다
        print("  ⚠️ 경량 병합 폴더 실패 — 전체로 푼다: " + out.strip()[:200])
        run(["git", "sparse-checkout", "disable"], stage)
        run(["git", "checkout"], stage)
    _mark_stage_owner(stage)
    return stage


def _close_stage(repo, stage):
    run(["git", "worktree", "remove", "--force", str(stage)], repo)
    try:
        _stage_owner_file(stage).unlink()
    except OSError:
        pass


def _select_related_tests(changed, test_texts, limit=60):
    """바뀐 코드 파일과 관련된 시험 파일 — 시험 파일 자체가 바뀌었거나, 본문이 그 모듈 이름을 부르는 것. 많으면(>limit) 빈 목록."""
    stems = set()
    picked = []
    for c in changed:
        c = c.replace("\\", "/")
        if not c.endswith(".py"):
            continue
        if c in test_texts:
            picked.append(c)
            continue
        if c.startswith(("shopping_shorts/", "tools/")):
            stems.add(Path(c).stem)
    if stems:
        pat = re.compile(r"\b(%s)\b" % "|".join(re.escape(x) for x in sorted(stems)))
        for t, txt in sorted(test_texts.items()):
            if t not in picked and pat.search(txt):
                picked.append(t)
    picked = sorted(set(picked))
    return [] if len(picked) > limit else picked


def _precheck(name, repo, wt, br, gate):
    """락을 잡기 **전에** 트랙 폴더에서 관련 시험만 빨리 돌린다(카드 081) — 어차피 막힐 병합이 줄을 서서 남의 시간을 쓰지 않게.
    main 에서도 깨지는 건 빼고, 새로 깨진 게 있으면 여기서 멈춘다. TRACK_PRECHECK=0 이면 건너뛴다."""
    if os.environ.get("TRACK_PRECHECK", "") == "0" or not hasattr(gate, "rerun_ids"):
        return
    rc, out = run(["git", "-c", "core.quotepath=off", "diff", "--name-only", "origin/main..." + br], wt)
    changed = [x.strip() for x in out.splitlines() if x.strip()] if rc == 0 else []
    texts = {}
    for p in list(Path(wt).glob("shopping_shorts/tests/test_*.py")) + list(Path(wt).glob("tools/test_*.py")) \
            + list(Path(wt).glob("tools/*/test_*.py")):
        try:
            texts[p.relative_to(wt).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    sel = _select_related_tests(changed, texts)
    if not sel:
        return
    t0 = time.time()
    print("선검사: 관련 시험 %d개를 트랙 폴더에서 먼저(락 전)..." % len(sel))
    try:
        failed = set(gate.rerun_ids(wt, sel, workers=2))        # 남의 게이트와 CPU 를 나눠 쓰니 병렬 2(카드 083)
    except TypeError:
        failed = set(gate.rerun_ids(wt, sel))
    if failed:
        pre = _known_main_failures(repo, wt, sorted(failed), ref="origin/main")
        failed -= pre
    print("선검사: %.0f초 · 새로 깨진 %d" % (time.time() - t0, len(failed)))
    if failed:
        raise TrackError("❌ 선검사 실패 — 줄 서기 전에 멈춘다(라이브 무사).\n" + "\n".join("  - " + t for t in sorted(failed)[:20])
                         + f"\n고친 뒤 다시: py tools/track.py finish {name}")


_LAUNCHER = r"""
import os, subprocess, sys
log, rcf, cwd, args = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
env = dict(os.environ, TRACK_FINISH_CHILD="1", PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
# ★finish 는 **숨은 콘솔**로, 출력은 로그 파일로 **명시**해 넘긴다(2026-10-02 실측): 명시 안 하면 윈도는 출력을 상속하지 않아 로그가 0바이트였고,
#   콘솔 없는 부모 밑이라 finish 에 **새 콘솔 창**이 따로 떠 그 창이 닫히며 Ctrl+C(0xC000013A)로 6분 만에 죽었다.
code = ("import subprocess,sys;o=open(sys.argv[1],'ab');"
        "r=subprocess.call(sys.argv[3:],stdout=o,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,"
        "creationflags=(0x08000000 if sys.platform=='win32' else 0));open(sys.argv[2],'w').write(str(r))")
out = open(log, "ab")
kw = dict(cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
if os.name == "nt":
    flags = 0x00000008 | 0x00000200 | 0x08000000           # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
    try:
        subprocess.Popen([sys.executable, "-c", code, log, rcf] + args, creationflags=flags | 0x01000000, **kw)   # + BREAKAWAY_FROM_JOB
    except OSError:
        subprocess.Popen([sys.executable, "-c", code, log, rcf] + args, creationflags=flags, **kw)
else:
    subprocess.Popen([sys.executable, "-c", code, log, rcf] + args, start_new_session=True, **kw)
"""


def _finish_detached(name):
    """finish 를 **분리된 프로세스**로 띄우고 로그를 따라 읽는다(카드 081). 이 창(또는 Claude 백그라운드 명령)이 시간 제한으로
    꺼져도 병합은 끝까지 간다 — 10-02 실측: 2시간 줄 서다 Claude 제한에 꺼진 finish. 결과는 로그·rc 파일에 남는다."""
    import subprocess
    logs = tracks_dir(BASE) / "_finish_logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    log, rcf = logs / ("%s_%s.log" % (name, stamp)), logs / ("%s_%s.rc" % (name, stamp))
    me = [sys.executable, "-u", str(Path(__file__).resolve()), "finish", name, "--attached"]
    subprocess.Popen([sys.executable, "-c", _LAUNCHER, str(log), str(rcf), str(Path.cwd())] + me,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=(0x08000000 if os.name == "nt" else 0))
    print("finish 를 분리 실행했다 — 이 창이 꺼져도 끝까지 간다.\n  로그: %s" % log)
    pos = 0
    while True:
        try:
            with open(log, "rb") as f:
                f.seek(pos)
                chunk = f.read()
                pos += len(chunk)
            if chunk:
                sys.stdout.write(chunk.decode("utf-8", "replace"))
                sys.stdout.flush()
        except OSError:
            pass
        if rcf.exists():
            try:
                return int(rcf.read_text(encoding="utf-8").strip() or "1")
            except ValueError:
                return 1
        time.sleep(2)


def finish(name, repo=BASE, gate=merge_gate, attempts=5, video_gate=None):
    """★다 된 것만 줄 선다(2026-10-03 카드 088): 병합·시험·관제·영상 관문은 줄(전역 락) 밖에서,
    줄 안에선 커밋·push 만(몇 초). 그사이 main 에 코드가 들어왔으면 줄에서 빠져 밖에서 다시 잰다."""
    merge_gate.make_output_safe()
    validate_name(name)
    wt = _preflight(name, repo)
    br = branch_name(name)
    run(["git", "fetch", "origin"], repo)
    if os.environ.get("TRACK_PRECHECK", "") == "1":
        _precheck(name, repo, wt, br, gate)        # 시험이 줄 밖에서 돌게 돼 중복 — 원할 때만(카드 088)
    _clean_dead_stages(repo)                        # 살아 있는 남의 stage 는 건너뛴다(주인 pid)
    _disk_guard(repo, "finish")
    prev_base = None
    for attempt in range(1, attempts + 1):
        run(["git", "fetch", "origin"], repo)
        stage = _open_stage(repo, name)
        base_now = run(["git", "rev-parse", "HEAD"], stage)[1].strip()
        try:
            result = _merge_and_gate(name, repo, stage, br, gate, wt, video_gate, lock=None,
                                     push_lock=_finish_gate_lock, prev_base=prev_base)
        finally:
            _close_stage(repo, stage)

        if result == "nothing":
            print(f"\n병합할 것이 없다 (트랙 '{name}'에 새 커밋 없음).")
            return 0
        if result == "pushed":
            _sync_main_folder(repo)
            _level_track_with_main(name, repo, wt, br)
            return 0
        # result == "raced": 시험하는 사이 main 에 코드가 들어왔다 → 줄 밖에서 최신 main 위로 다시.
        #   이 시도는 시험·관문을 **통과**했다('raced' 는 push 단계에서만 나온다) → 다음 시도는 끼어든 코드 관련만 다시(카드 092).
        prev_base = base_now
        print(f"⚠️ 시험하는 사이 main 에 코드가 들어왔다. 줄에서 빠져 최신 main 위에서 다시 잰다 "
              f"({attempt}/{attempts})...")

    raise TrackError(
        f"{attempts}번 시도했는데 매번 다른 트랙이 먼저 들어왔다.\n"
        "지금 병합이 몰리는 중이다. 잠시 뒤 다시: py tools/track.py finish " + name
    )


def _retry_test_subset(stage, prev_base, my_changed, *, half=0.5):
    """재시도(앞 시도 통과) 때 다시 돌릴 시험 파일. [] = 끼어든 게 코드 아님(시험 생략) · None = 너무 많음(전체).
    끼어든 코드 관련 + 내 변경 관련(새 main 위에서 맞물림) — 끼어든 커밋은 이미 제 관문을 통과했다."""
    rc, out = run(["git", "-c", "core.quotepath=off", "diff", "--name-only", prev_base, "HEAD"], stage)
    if rc != 0:
        return None
    inter = [x.strip() for x in out.splitlines() if x.strip()]
    inter_code = [x for x in inter if not _is_non_code(x)]
    if not inter_code:
        return []
    texts = {}
    for p in list(Path(stage).glob("shopping_shorts/tests/test_*.py")) + list(Path(stage).glob("tools/test_*.py")) \
            + list(Path(stage).glob("tools/*/test_*.py")):
        try:
            texts[p.relative_to(stage).as_posix()] = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    want = [x for x in set(inter_code) | {c for c in my_changed if not _is_non_code(c)}]
    sel = _select_related_tests(want, texts, limit=max(1, int(len(texts) * half)))
    if not sel and any(x.endswith(".py") for x in want):
        return None                         # 너무 많아 빈 목록(또는 못 고름) — 전체로
    return sel or None


def _merge_and_gate(name, repo, stage, br, gate, wt, video_gate=None, lock=None, push_lock=None, prev_base=None):
    light = hasattr(gate, "snapshot_light")
    before = gate.snapshot_light(stage) if light else _cached_baseline(repo, stage, gate)
    exact = None
    if light:
        # ★정확한 기준선(카드 083): 이 코드 트리로 병합될 때 저장한 **전체 시험 실패 목록**이 있으면 그것과 비교한다.
        #   관제·핸드오프 커밋은 코드 트리를 안 바꿔 대부분 맞는다. 없으면(다른 PC 의 코드 병합 직후) 파일 단위 재확인으로 가른다.
        exact = _load_full_failures(repo, _code_key(stage))
        if exact is not None:
            before = dict(before, failed=list(exact))
            print("  ℹ️ 기준선: 저장된 전체 실패 %d건(같은 코드 트리) — 정확 비교" % len(exact))
    for w in gate.baseline_warnings(before):
        print(f"  {w}")

    # ★병합 폴더가 진짜 병합 폴더인가(카드 093) — 지워졌으면 git 이 다른 저장소를 잡는다. 아니면 멈춘다(main 폴더 보호).
    _rc_t, _top = run(["git", "rev-parse", "--show-toplevel"], stage)
    if _rc_t != 0 or Path(_top.strip()).resolve() != Path(stage).resolve():
        raise TrackError("병합 폴더가 사라졌거나 다른 저장소를 가리킨다 — main 폴더 보호를 위해 멈췄다(라이브 무사).\n"
                         f"  폴더 {stage} · git 이 본 위치 {_top.strip()[:200]}\n다시: py tools/track.py finish {name}")
    # ★ 커밋 없이 병합만 — 커밋하면 post-commit(git push)이 게이트 전에 라이브로 보낸다
    rc, out = run(["git", "merge", "--no-ff", "--no-commit", br], stage)

    if "Already up to date" in out:
        return "nothing"

    if rc != 0:
        # abort하지 않는다 — stage 자체가 finally에서 통째로 삭제되므로 중복이다.
        # (실측: abort를 지워도 부분 병합이 남지 않는다 — worktree remove --force가 처리)
        raise TrackError(
            f"병합 충돌 — 자동 해결하지 않는다(사람 판단).\n\n{out}\n"
            f"트랙 폴더에서 main을 먼저 받아 충돌을 풀어라:\n"
            f"  cd \"{wt}\"\n"
            f"  git fetch origin && git merge origin/main\n"
            f"  (충돌 해결·커밋 후) py tools/track.py finish {name}"
        )

    _rc_ch, _ch = run(["git", "-c", "core.quotepath=off", "diff", "--cached", "--name-only", "HEAD"], stage)
    changed = [c.strip() for c in _ch.splitlines() if c.strip()] if _rc_ch == 0 else []
    if light and changed and all(_is_non_code(c) for c in changed):
        # ★코드가 없는 병합(핸드오프·관제·문서)은 시험 결과가 달라질 수 없다(카드 081) — 문법·import 만 보고 넘긴다.
        print("게이트: 코드 없는 병합(%d파일) — 시험 생략" % len(changed))
        after = dict(before)
        ran_full = False
    else:
        sub = _retry_test_subset(stage, prev_base, changed) if (light and prev_base) else None
        if sub == []:
            print("재시도: 끼어든 main 커밋에 코드가 없다 — 앞 시도 시험 결과 그대로(시험 생략)")
            after = dict(before)
            ran_full = False
        else:
            with (_gate_slot() if push_lock is not None else contextlib.nullcontext()):
                if sub:
                    print("재시도: 끼어든 코드·내 변경 관련 시험 %d개 파일만 다시(앞 시도 통과 · 줄 밖)..." % len(sub))
                    try:
                        after = gate.snapshot(stage, paths=sub)
                    except TypeError:                         # 옛 게이트 스텁 — 전체
                        after = gate.snapshot(stage)
                    ran_full = False
                else:
                    print("게이트 실행 중 (병합된 상태, 아직 커밋 없음 · 줄 밖)...")
                    after = gate.snapshot(stage)
                    ran_full = True
    problems = gate.compare(before, after)
    # ★새로 깨진 테스트를 origin/main 코드로 다시 돌린다(2026-10-02, 카드 069). 기준선 저장본이 낡거나 환경이 달라지면
    #   main 의 기존 실패가 '새로 깨진 것'으로 잡혀 무관한 트랙을 막았다(10-01 추적대본검색어 실측).
    problems = _classify_new_failures(before, after, problems,
                                      rerun=lambda ids: _known_main_failures(repo, stage, ids), printer=print,
                                      recheck=(lambda ids: gate.rerun_ids(stage, ids)) if hasattr(gate, "rerun_ids") else None)
    # 전체 시험을 **실제로 돌렸을 때만** 저장한다 — 생략한 병합이 빈 목록을 저장해 다음 기준선을 망쳤다(10-02 실측, 카드 083)
    _after_failed_for_store = list(after.get("failed", [])) if ran_full else None

    if problems:
        msg = ["❌ 게이트 실패 — 병합을 버렸다. 라이브는 무사하다.\n"]
        msg += [f"  • {p}" for p in problems]
        if not after["import_ok"]:
            msg.append(f"\n--- import 출력 ---\n{after['import_out']}")
        if after["pytest_rc"] not in merge_gate._PYTEST_SANE_RC:
            msg.append(f"\n--- pytest 출력 ---\n{after['pytest_out']}")
        msg.append(f"\n트랙 폴더는 그대로 있다: {wt}\n고친 뒤 다시: py tools/track.py finish {name}")
        raise TrackError("\n".join(msg))

    print("✅ 게이트 통과" + ("" if light else f" (기존 실패 {len(before['failed'])}건은 그대로)"))

    # ★관제 관문(2026-09-28): 카드 없는 병합 없음 · 고객 화면/과금/데이터 변경은 카드 승인 · 판단 두 벌 새로 생기면 거절.
    #   merge_gate 뒤·영상 관문 앞 — 서버 영상 비교(수십 분)를 돌리기 전에 싼 검사로 먼저 거른다.
    cg = _control.finish_gate(repo, stage, br, name)
    if not cg.ok:
        raise TrackError(
            "❌ 관제 관문 실패 — 병합을 버렸다. 라이브는 무사하다.\n"
            + "\n".join("  • " + f for f in cg.fails)
            + f"\n\n트랙 폴더는 그대로 있다: {wt}\n고친 뒤 다시: py tools/track.py finish {name}")
    _MERGE_CARDS[name] = [c["번호"] for c in cg.cards]

    # ★영상 관문(2026-09-27): 제작 라인(미리보기 굽기·렌더·청소·컷 계산)을 건드린 병합은
    #   서버에서 '편집 화면 vs 완성본' 영상 비교를 통과해야 커밋된다. 해당 변경이 없으면 한 줄 찍고 건너뛴다.
    #   실패하면 여기서 버린다 — 아직 커밋 전이라 라이브는 무사하다(stage는 finally에서 통째로 삭제).
    vg = _run_video_gate_unlocked(lock, (video_gate or _video_gate.run_video_gate), stage, br)
    if not vg.ok:
        raise TrackError(
            "❌ 영상 관문 실패 — 병합을 버렸다. 라이브는 무사하다.\n"
            "(위 report·판정 근거 참고. 기준값: tools/gate_video.json — main 의 값을 쓴다)\n"
            f"트랙 폴더는 그대로 있다: {wt}\n고친 뒤 다시: py tools/track.py finish {name}"
        )

    if push_lock is None:
        return _commit_and_push(name, repo, stage, light, _after_failed_for_store)
    print("검사 끝 — 줄에 선다(줄 안에선 커밋·push 만)")
    with push_lock() as _q:
        return _commit_and_push(name, repo, stage, light, _after_failed_for_store)


def _commit_and_push(name, repo, stage, light, _after_failed_for_store):
    """줄 안: 커밋 → push. main 이 그사이 움직였으면 비코드만 따라잡고, 코드면 'raced'(줄 밖에서 다시)."""
    run(["git", "fetch", "origin", "main"], stage)
    # stage는 detached HEAD라 post-commit의 인자 없는 `git push`는 조용히 실패한다.
    # 그래서 push는 아래에서 우리가 명시적으로 한다 — 즉 **게이트 통과 후에만** 나간다.
    rc, out = run(["git", "commit", "--no-edit"], stage)
    if rc != 0:
        raise TrackError(f"커밋 실패 — 병합을 버렸다(라이브 무사):\n{out}")

    rc, out = run(["git", "push", "origin", "HEAD:main"], stage)
    for _ in range(RACE_CATCHUP_MAX):
        if rc == 0 or not _is_race(out) or not _catch_up_non_code(stage):
            break
        rc, out = run(["git", "push", "origin", "HEAD:main"], stage)
    if rc != 0:
        if _is_race(out):
            return "raced"
        raise TrackError(
            f"push 실패 — main은 안 바뀌었다(라이브 무사):\n{out}"
        )
    print("✅ main에 병합 완료 — push됨. 3분 뒤 서버 반영.")
    if light and _after_failed_for_store is not None:
        try:
            _store_full_failures(repo, _code_key(stage), _after_failed_for_store)   # 다음 finish 의 정확한 기준선(카드 083)
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠️ 전체 실패 목록 저장 실패(병합엔 영향 없음): {e!r}")
    rc, sha = run(["git", "rev-parse", "--short=10", "HEAD"], stage)
    if _MERGE_CARDS.get(name):
        _control.record_merge(repo, _MERGE_CARDS[name], name, sha.strip())
        print("   라이브 실측은 묻지 않아도 자동 — 매시간 tools/live_check.py --all 이 실제 고객 작업으로 영상·소리·자막·캡컷을 재서 카드에 적는다"
              "(기준 미달이면 회귀). 지금 바로: py tools/live_check.py --all")
    return "pushed"


# ── 병합 구조 개선(2026-09-29 사장님 "몇 번째 재시도 병합 이런 거 왜 되냐") ─────────────────
#  실측: 게이트 = 기준선 20분 + 병합 후 20분. 그 사이 잠금 밖 커밋(auto: session changes·관제 카드)이
#  main에 올라오면 push가 거절돼 40분을 처음부터 다시 돌았다(3회 = 2시간, 채널명기본 3/3 실패).
#  ① 끼어든 커밋이 **코드가 아닌 것뿐**이면 테스트 결과가 달라질 수 없다 → 그 위에 합쳐 바로 push.
#  ② 기준선은 origin/main 커밋이 같으면 결과가 같다 → 커밋별로 저장해 재사용.
RACE_CATCHUP_MAX = 5
# 이 경로들만 바뀐 커밋은 게이트 결과(문법·import·pytest)를 바꿀 수 없다. 모르는 경로는 코드로 본다(보수적).
NON_CODE_PREFIXES = ("관제/", "handoff/", "wiki/", "raw/", "docs/", "channel/", "out/", "memory/", "NEXT_SESSION")
NON_CODE_SUFFIXES = (".md", ".txt", ".csv", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".mp4", ".mp3")


def _is_non_code(path):
    p = path.strip().strip('"')
    if p.startswith("shopping_shorts/") and not p.endswith((".md", ".txt")):
        return False
    return p.startswith(NON_CODE_PREFIXES) or p.endswith(NON_CODE_SUFFIXES)


def _catch_up_non_code(stage):
    """push가 거절된 뒤: 새로 들어온 main 커밋이 전부 비코드면 그 위에 합쳐(충돌 없을 때만) True.
    코드가 하나라도 있거나 충돌이면 False — 종전대로 처음부터 게이트를 다시 돈다."""
    run(["git", "fetch", "origin", "main"], stage)
    # 기준 = 내 병합과 새 main의 공통 조상(두 번째 따라잡기에서도 맞다 — HEAD^1은 첫 따라잡기 뒤엔 내 커밋이다)
    rc0, base = run(["git", "merge-base", "HEAD", "origin/main"], stage)
    if rc0 != 0 or not base.strip():
        return False
    rc, files = run(["git", "diff", "--name-only", base.strip(), "origin/main"], stage)
    if rc != 0:
        return False
    changed = [f for f in files.splitlines() if f.strip()]
    code = [f for f in changed if not _is_non_code(f)]
    if code:
        print(f"ℹ️ 끼어든 main 커밋에 코드가 있다({len(code)}개, 예: {code[0]}) — 게이트를 다시 돈다")
        return False
    rc, out = run(["git", "merge", "--no-edit", "origin/main"], stage)
    if rc != 0:
        run(["git", "merge", "--abort"], stage)
        print(f"ℹ️ 끼어든 비코드 커밋과 충돌 — 게이트를 다시 돈다: {out[-300:]}")
        return False
    print(f"⏩ 끼어든 main 커밋이 비코드 {len(changed)}개뿐 — 게이트 결과 그대로 두고 합쳐서 다시 push")
    return True


def _classify_new_failures(before, after, problems, *, rerun, printer=print, recheck=None):
    """'새로 깨진 테스트' 문제를 다시 가른다. ★순서(2026-10-03 카드 091):
    ① 병합본에서 그 시험 파일들을 한 번 더(recheck) — 다시 통과하면 우연한 실패(경고만).
    ② 남은 것만 main 코드로(rerun) — main 에서도 깨지면 기존 실패.
    어느 단계가 예외여도 **다른 단계는 한다** — 종전엔 main 재실행이 예외면 ①까지 건너뛰어 39건 거짓 실패로 막혔다(3단계화면정리 실측)."""
    new_ids = sorted(set(after.get("failed", [])) - set(before.get("failed", [])))
    if not new_ids or not any(p.startswith("새로 깨진 테스트") for p in problems):
        return problems
    left = list(new_ids)
    if recheck is not None:
        try:
            still = set(recheck(left))
            flaky = [t for t in left if t not in still]
            if flaky:
                printer("  ⚠️ 다시 돌리니 통과 — 우연한 실패로 본다 %d건: %s" % (len(flaky), ", ".join(flaky[:6])))
            left = [t for t in left if t in still]
        except Exception as e:  # noqa: BLE001 — 재확인 못 하면 다음 단계로
            printer(f"  ⚠️ 병합본 재확인 건너뜀: {e!r}")
    if left:
        try:
            pre = set(rerun(left))
            if pre:
                printer("  ℹ️ 기존 실패로 분류(병합 전 main 에서도 깨짐) %d건: %s" % (len(pre), ", ".join(sorted(pre)[:6])))
            left = [t for t in left if t not in pre]
        except Exception as e:  # noqa: BLE001 — main 재실행을 못 하면 남은 것은 그대로 문제로 둔다(보수적)
            printer(f"  ⚠️ 기존 실패 분류 건너뜀(main 재실행 실패): {e!r}")
    out = [p for p in problems if not p.startswith("새로 깨진 테스트")]
    if left:
        shown = "\n".join(f"    - {t}" for t in left[:20])
        out.append(f"새로 깨진 테스트 {len(left)}건:\n{shown}")
    return out


def _code_key(cwd, ref="HEAD"):
    """시험 결과를 바꿀 수 있는 코드 트리의 열쇠 — 관제·핸드오프 커밋으로는 안 바뀐다(커밋 번호와 다르다)."""
    parts = []
    for rel in ("shopping_shorts", "tools", "pipeline", "conftest.py", "pytest.ini"):
        rc, out = run(["git", "rev-parse", "%s:%s" % (ref, rel)], cwd)
        parts.append(out.strip() if rc == 0 else "-")
    import hashlib
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def _full_fail_path(repo, key):
    return tracks_dir(repo) / "_gate_cache" / ("full_fail_%s.json" % key)


def _store_full_failures(repo, key, failed):
    """이 코드 트리에서 전체 시험을 돌렸을 때 깨진 목록 — 다음 finish 의 **정확한 기준선**(카드 083)."""
    import json
    f = _full_fail_path(repo, key)
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(sorted(failed), ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _load_full_failures(repo, key):
    import json
    try:
        return json.loads(_full_fail_path(repo, key).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _known_main_failures(repo, stage, ids, ref="HEAD"):
    """그 시험들이 **main 코드에서도** 깨지나 → 깨지는 id 집합. 코드 트리 열쇠별로 기억해 같은 코드면 다시 안 돌린다(카드 081)."""
    import json
    ids = list(ids)
    if not ids:
        return set()
    key = _code_key(stage, ref)
    f = tracks_dir(repo) / "_gate_cache" / ("main_fail_%s.json" % key)
    try:
        known = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        known = {}
    missing = [i for i in ids if i not in known]
    if missing:
        got = set(_rerun_on_main(stage, missing))
        for i in missing:
            known[i] = i in got
        try:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(json.dumps(known, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    else:
        print("  ℹ️ main 재확인 기억 재사용(코드 트리 %s)" % key)
    return {i for i in ids if known.get(i)}


def _rerun_on_main(stage, ids):
    """**병합 폴더의 기준 커밋(HEAD = 병합 전 main)** 코드로 그 시험 파일들만 돌려 거기서도 깨지는 id 집합을 돌려준다.
    ★(2026-10-03 카드 091) 종전엔 origin/main 을 git archive 로 통째(실측 661MB) 풀어 느렸고, 그 압축이 깨져(ReadError)
    분류가 통째로 빠졌다. 그사이 origin/main 이 움직이면 다른 코드로 가르기도 했다 → 같은 경량 폴더(STAGE_SPARSE)를 기준 커밋에 만든다."""
    rc, sha = run(["git", "rev-parse", "HEAD"], stage)
    sha = sha.strip()
    if rc != 0 or not sha:
        raise TrackError("병합 폴더 기준 커밋을 못 읽었다: %s" % sha[:200])
    tmp = Path(tempfile.mkdtemp(prefix="gate_main_"))
    wt = tmp / "wt"
    try:
        rc, out = run(["git", "worktree", "add", "--detach", "--no-checkout", str(wt), sha], stage)
        if rc != 0:
            raise TrackError("main 재실행 폴더를 못 만들었다: %s" % out[-300:])
        rc, out = run(["git", "sparse-checkout", "set", "--no-cone", *STAGE_SPARSE], wt)
        if rc == 0:
            rc, out = run(["git", "checkout"], wt)
        if rc != 0:
            raise TrackError("main 재실행 폴더를 못 풀었다: %s" % out[-300:])
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        # main 코드의 finish 시험이 이 프로세스가 쥔 락을 기다리지 않게 — 임시 폴더를 통째로 따로(카드 075)
        for _k in ("TMP", "TEMP", "TMPDIR"):
            env[_k] = str(tmp)
        # 파일 통째로(카드 083) — id 하나씩이면 같은 파일 안 순서 영향이 사라져 '원래 실패'를 못 가른다
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", "--tb=no", "-rfE"]
                           + merge_gate.test_files_of(ids),
                           cwd=str(wt), capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=900)
        got = merge_gate.parse_failed((r.stdout or "") + (r.stderr or ""))
        return {f for f in got if f in set(ids)}
    finally:
        run(["git", "worktree", "remove", "--force", str(wt)], stage)
        shutil.rmtree(tmp, ignore_errors=True)


def _cached_baseline(repo, stage, gate):
    """기준선(병합 전 origin/main 스냅샷)을 커밋별로 저장·재사용한다. 저장이 깨졌으면 새로 잰다."""
    import json
    rc, sha = run(["git", "rev-parse", "HEAD"], stage)
    sha = sha.strip()
    cache = tracks_dir(repo) / "_gate_cache" / f"{sha}.json"
    if rc == 0 and cache.exists():
        try:
            before = json.loads(cache.read_text(encoding="utf-8"))
            print(f"기준선 재사용 (origin/main {sha[:10]}, 저장본)")
            return before
        except Exception as e:  # noqa: BLE001 — 저장본이 깨졌으면 새로 잰다(경보는 남긴다)
            print(f"⚠️ 기준선 저장본 읽기 실패 — 새로 잰다: {e!r}")
    print("기준선 수집 중 (병합 전 origin/main)...")
    before = gate.snapshot(stage)
    if rc == 0 and sha:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            olds = sorted(cache.parent.glob("*.json"), key=lambda p: p.stat().st_mtime)[:-30]
            for o in olds:
                o.unlink(missing_ok=True)
            cache.write_text(json.dumps(before, ensure_ascii=False), encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 기준선 저장 실패(병합엔 영향 없음): {e!r}")
    return before


# finish_gate 가 찾은 카드 번호 → push 뒤 병합 기록에 쓴다(트랙명별). 한 프로세스가 finish 하나를 돈다.
_MERGE_CARDS = {}


def _is_race(push_output):
    """다른 트랙이 먼저 밀어넣어 거절당했나 (git이 주는 원자적 신호등)."""
    o = push_output.lower()
    return "non-fast-forward" in o or "fetch first" in o or "rejected" in o


def _sync_main_folder(repo):
    """원본 폴더를 새 main으로 당겨준다. 실패해도 병합은 이미 끝났다 — 알리기만."""
    rc, out = run(["git", "merge", "--ff-only", "origin/main"], repo)
    if rc != 0:
        print(f"ℹ️ 원본 폴더는 아직 옛 main이다 (거기서 직접 pull 해라):\n{out.strip()}")


def _level_track_with_main(name, repo, wt, br):
    """병합 후 트랙 브랜치를 새 main 자리로 당긴다. **폴더는 남긴다.**

    ★왜 안 지우나: 설계는 "태스크 단위로 자주 병합"을 요구한다. 병합할 때마다 883MB
    체크아웃을 지웠다 다시 만들면 그 요구와 정면으로 안 맞는다. 게다가 사용자의 터미널이
    그 폴더 안에 있으면 윈도우가 삭제를 거부해 어차피 실패한다(2026-07-16 실측 2회).
    트랙 폴더 = 그 트랙의 작업대다. 태스크가 끝난 거지 트랙이 끝난 게 아니다.
    트랙을 진짜 접을 땐 `close`.

    ★reset --hard가 아니라 ff 병합인 이유: reset은 트랙 폴더의 미추적 산출물·메모를
    날릴 수 있다. 우리 커밋은 방금 main에 병합됐으므로 origin/main은 트랙 브랜치의
    **자손**이다 → ff가 성립한다.
    """
    rc, out = run(["git", "merge", "--ff-only", "origin/main"], wt)
    if rc != 0:
        print(f"ℹ️ 트랙 '{name}' 폴더를 최신 main으로 못 당겼다 — 거기서 직접 pull 해라.\n   {out.strip()[:200]}")
        return
    # ff 결과를 백업 브랜치에도 올린다. 안 올리면 로컬이 자기 upstream보다 앞선 상태가 돼
    # `git branch -d`가 "upstream에 아직 병합 안 됨"이라며 거절한다(HEAD엔 병합됐는데도).
    # 실패해도(오프라인 등) 병합은 이미 끝났으므로 조용히 넘어간다 — close가 -D로 처리한다.
    run(["git", "push", "origin", f"HEAD:{br}"], wt)
    print(f"✅ 트랙 '{name}' 폴더는 그대로 두고 최신 main에 맞췄다 — 바로 다음 작업 가능.")
    print(f"   트랙을 아주 접으려면: py tools/track.py close {name}")


def close(name, repo=BASE):
    """트랙을 접는다 — 폴더·브랜치 삭제. finish와 달리 **파괴적**이라 확인이 붙는다."""
    merge_gate.make_output_safe()
    validate_name(name)
    wt = worktree_path(name, repo)
    br = branch_name(name)
    if not wt.exists() and not branch_exists(repo, br):
        raise TrackError(f"없는 트랙: {name}")

    run(["git", "fetch", "origin"], repo)
    ahead = ahead_count(repo, br) if branch_exists(repo, br) else 0
    if ahead:
        raise TrackError(
            f"트랙 '{name}'에 아직 **병합 안 된 커밋 {ahead}개**가 있다 — 접으면 사라진다.\n"
            f"먼저: py tools/track.py finish {name}\n"
            f"버릴 작정이면: git worktree remove --force \"{wt}\" && git branch -D {br}"
        )
    if wt.exists():
        rc, out = run(["git", "worktree", "remove", str(wt)], repo)
        if rc != 0:
            raise TrackError(
                f"트랙 폴더를 못 지웠다 — 그 폴더 안에 열린 터미널·창이 있나 확인해라"
                f"(윈도우는 사용 중인 폴더 삭제를 거부한다).\n{out.strip()[:200]}"
            )
    run(["git", "push", "origin", "--delete", br], repo)   # 원격 백업 먼저(없으면 조용히 실패)
    # -D인 이유: `-d`는 **upstream**(origin/track/X) 기준으로 판단해서, 로컬이 ff로 앞서 있으면
    # "HEAD엔 병합됐는데도" 거절한다(실측). 우리는 위에서 ahead_count==0으로 **main에 다 들어갔음**을
    # 이미 확인했다 — git의 upstream 휴리스틱보다 정확한 검사다. 그 확인 없이 -D를 쓰면 안 된다.
    rc, out = run(["git", "branch", "-D", br], repo)
    if rc != 0:
        raise TrackError(f"브랜치를 못 지웠다:\n{out.strip()[:200]}")
    if _control.installed(repo):
        _control.release(repo, name)
    print(f"🧹 트랙 '{name}' 접음 (폴더·브랜치 삭제)")
    return 0


# ── park: 폴더만 치우고 브랜치는 보존 ─────────────────────────────

def _last_touch_days(repo, name):
    """트랙이 마지막으로 쓰인 지 며칠 — 브랜치 마지막 커밋과 그 worktree의 git index 수정 시각 중 **늦은 쪽**.
    (커밋이 오래됐어도 지금 누가 그 폴더에서 편집 중이면 index가 갱신돼 '최근'으로 잡힌다)"""
    now = time.time()
    rc, out = run(["git", "log", "-1", "--format=%ct", branch_name(name)], repo)
    t = int(out.strip()) if rc == 0 and out.strip().isdigit() else 0
    rc, gitdir = run(["git", "rev-parse", "--git-dir"], worktree_path(name, repo))
    if rc == 0 and gitdir.strip():
        g = Path(gitdir.strip())
        g = g if g.is_absolute() else worktree_path(name, repo) / g
        for f in (g / "index", g / "HEAD"):
            if f.exists():
                t = max(t, int(f.stat().st_mtime))
    return (now - t) / 86400 if t else None


def park(name, repo=BASE):
    """트랙 폴더만 치운다 — 브랜치(커밋)는 로컬·원격에 **그대로**. 되살리기: git worktree add <폴더> track/<이름>.
    안전장치: ①원격 백업이 로컬과 같은 커밋인지 확인 ②미커밋 파일이 있으면 거절 ③강제 제거 안 함."""
    merge_gate.make_output_safe()
    validate_name(name)
    wt = worktree_path(name, repo)
    br = branch_name(name)
    if not wt.exists():
        raise TrackError(f"트랙 폴더가 없다: {wt}")
    if not branch_exists(repo, br):
        raise TrackError(f"브랜치가 없다: {br} — 폴더를 치우면 작업이 사라진다. 손대지 않는다.")
    run(["git", "push", "origin", f"{br}:{br}"], repo)
    _, loc = run(["git", "rev-parse", br], repo)
    _, rem = run(["git", "ls-remote", "origin", f"refs/heads/{br}"], repo)
    if not loc.strip() or rem.split("\t")[0].strip() != loc.strip():
        raise TrackError(f"원격 백업이 로컬과 다르다({br}) — 폴더를 안 치운다.")
    _, st = run(["git", "status", "--porcelain"], wt)
    dirty = [p for p in parse_status(st) if not is_ignorable(p)]
    if dirty:
        raise TrackError(f"미커밋 파일 {len(dirty)}개 — 커밋하거나 버린 뒤 다시: {', '.join(dirty[:3])}")
    rc, out = run(["git", "worktree", "remove", str(wt)], repo)
    if rc != 0:
        raise TrackError(f"폴더를 못 치웠다(열린 창·터미널이 있나?):\n{out.strip()[:200]}")
    print(f"🅿️ 트랙 '{name}' 주차 — 브랜치 {br} 보존. 되살리기: git worktree add \"{wt}\" {br}")
    return 0


def park_idle(repo=BASE, days=IDLE_PARK_DAYS):
    """days일 넘게 안 쓴 트랙을 전부 주차한다. 하나가 거절돼도 나머지는 계속(이유는 전부 출력)."""
    merge_gate.make_output_safe()
    before = disk_free_gb(repo)
    parked, skipped = [], []
    for br in track_branches(repo):
        name = br[len(BRANCH_PREFIX):]
        if not worktree_path(name, repo).exists():
            continue
        age = _last_touch_days(repo, name)
        if age is None or age < days:
            continue
        try:
            park(name, repo=repo)
            parked.append(name)
        except TrackError as e:
            skipped.append(name)
            print(f"   건너뜀 {name}: {str(e).splitlines()[0]}")
    after = disk_free_gb(repo)
    print(f"\n주차 {len(parked)}개 · 건너뜀 {len(skipped)}개"
          + (f" · 디스크 여유 {before:.1f}GB → {after:.1f}GB" if before is not None and after is not None else ""))
    return 0


# ── list ─────────────────────────────────────────────────────────

def track_branches(repo=BASE):
    _, out = run(["git", "branch", "--list", f"{BRANCH_PREFIX}*", "--format=%(refname:short)"], repo)
    return [b.strip() for b in out.splitlines() if b.strip()]


def ahead_count(repo, branch, base=MAIN_BRANCH):
    rc, out = run(["git", "rev-list", "--count", f"{base}..{branch}"], repo)
    if rc != 0:
        return None
    try:
        return int(out.strip())
    except ValueError:
        return None


def list_tracks(repo=BASE):
    merge_gate.make_output_safe()
    branches = track_branches(repo)
    if not branches:
        print("열린 트랙 없음.  시작: py tools/track.py start <이름>")
        return 0
    print("열린 트랙:\n")
    cards = _control.cards_from_ref(repo) if _control.installed(repo) else []
    for br in branches:
        name = br[len(BRANCH_PREFIX):]
        wt = worktree_path(name, repo)
        n = ahead_count(repo, br)
        mine = _control.cards_for_track(cards, name)
        card_mark = ("  카드 " + ", ".join("%03d" % c["번호"] for c in mine)) if mine else ("  ❗카드 없음" if cards else "")
        mark = ""
        if n is None:
            mark = "  (앞선 커밋 수 계산 실패)"
        elif n >= 10:
            mark = f"  ⚠️⚠️ main보다 {n}커밋 앞섬 — 너무 오래 끌었다. 지금 병합해라."
        elif n >= 5:
            mark = f"  ⚠️ main보다 {n}커밋 앞섬 — 슬슬 병합할 때."
        else:
            mark = f"  main보다 {n}커밋 앞섬"
        exists = "" if wt.exists() else "  ❗폴더 없음(브랜치만 남음)"
        print(f"  {name:<16} {br}{mark}{exists}{card_mark}")
        print(f"  {'':<16} {wt}")
    print("\n끝내기: py tools/track.py finish <이름>")
    return 0


# ── cli ──────────────────────────────────────────────────────────

TOOLS_LATEST = "_tools_latest"


def _latest_tools_track_py():
    """origin/main 에 맞춘 전용 도구 폴더(.tracks/_tools_latest, tools/ 만)의 track.py — main 폴더 상태와 무관(카드 093).
    ★main 폴더는 누가 작업을 걸어 두면(멈춘 병합·스테이징) 동기화가 막혀 낡는다 — 10-03 실측 51커밋·2시간, 그동안 모든
    세션의 finish 가 옛 판본(088)으로 돌아 089·091·092 가 안 먹었다. 갱신은 파일락 하나로 줄 세운다."""
    repo = Path(main_worktree())
    tl = tracks_dir(repo) / TOOLS_LATEST
    lk = _FileLock(Path(tempfile.gettempdir()) / "stockbrain_tools_latest.lock", "[대기] 최신 도구 폴더 갱신 중...").acquire()
    try:
        run(["git", "fetch", "-q", "origin", "main"], repo)
        if not (tl / ".git").exists():
            if tl.exists():
                run(["git", "worktree", "remove", "--force", str(tl)], repo)
                shutil.rmtree(tl, ignore_errors=True)
            rc, out = run(["git", "worktree", "add", "--detach", "--no-checkout", str(tl), "origin/main"], repo)
            if rc != 0:
                raise TrackError("최신 도구 폴더를 못 만들었다: " + out[-200:])
            run(["git", "sparse-checkout", "set", "--no-cone", "/tools/"], tl)
        rc, out = run(["git", "checkout", "-q", "--detach", "--force", "origin/main"], tl)
        if rc != 0:
            raise TrackError("최신 도구 폴더를 못 맞췄다: " + out[-200:])
    finally:
        lk.release()
    return tl / "tools" / "track.py"


def _reexec_latest(argv):
    """main 폴더의 tools/track.py 가 이 파일과 다르면 그걸로 바꿔 실행한다(카드 083). 트랙 폴더 350개 중 349개가
    옛 판본이라, main 에 새 finish 가 들어가도 각 세션은 자기 폴더의 옛 것으로 돌았다(10-02 실측). main 폴더는 병합 때마다 최신.
    → (실행했나, rc)."""
    import subprocess
    if os.environ.get("TRACK_REEXEC"):
        return False, 0
    try:
        latest = _latest_tools_track_py()
        me = Path(__file__).resolve()
        if not latest.exists() or latest.resolve() == me or latest.read_bytes() == me.read_bytes():
            return False, 0
        # ★이 트랙이 track.py 자체를 고치는 중이면 바꾸지 않는다 — 고친 판본으로 병합해야 한다(10-02 실측: 카드 083 finish 가
        #   main 의 옛 판본으로 돌았다). 트랙 폴더 판본이 origin/main 판본과 다르고, 그 차이가 이 트랙의 커밋이면 = 고치는 중.
        rc, base = _sh(["git", "show", "origin/main:tools/track.py"], me.parent)
        if rc == 0 and base.replace("\r\n", "\n") != me.read_text(encoding="utf-8").replace("\r\n", "\n"):
            rc2, ch = _sh(["git", "diff", "--name-only", "origin/main...HEAD", "--", ":/tools/track.py"], me.parent)   # :/ = 저장소 최상위 기준
            if rc2 == 0 and ch.strip():
                return False, 0
    except Exception:  # noqa: BLE001 — 못 정하면 이 판본으로 돈다
        return False, 0
    print("ℹ️ 최신(origin/main) track.py 로 실행한다(이 트랙 폴더 판본은 옛것): %s" % latest, flush=True)
    env = dict(os.environ, TRACK_REEXEC="1")
    return True, subprocess.call([sys.executable, str(latest)] + list(argv), env=env)


class _StampOut:
    """finish 로그 줄마다 시각(HH:MM:SS)을 붙인다(카드 089) — 어느 단계가 몇 분인지 tools/finish_report.py 가 잰다."""

    def __init__(self, inner):
        self.inner, self.bol = inner, True

    def write(self, s):
        out = []
        for part in s.splitlines(True):
            if self.bol and part.strip():
                out.append(time.strftime("%H:%M:%S "))
            out.append(part)
            self.bol = part.endswith("\n")
        return self.inner.write("".join(out))

    def flush(self):
        return self.inner.flush()

    def __getattr__(self, k):
        return getattr(self.inner, k)


def main(argv=None):
    merge_gate.make_output_safe()  # cp949 콘솔에서 ✅·⚠️ 찍다 터지는 것 방지(실측)
    if os.environ.get("TRACK_FINISH_CHILD") and not isinstance(sys.stdout, _StampOut):
        sys.stdout = _StampOut(sys.stdout)
    _done, _rc = _reexec_latest(sys.argv[1:] if argv is None else argv)
    if _done:
        return _rc
    parser = argparse.ArgumentParser(description="트랙별 작업 폴더")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_start = sub.add_parser("start", help="트랙 폴더+브랜치 생성")
    p_start.add_argument("name")
    p_start.add_argument("--full", action="store_true", help="raw/·productions/까지 전부 풀기(기본은 가벼운 트랙)")
    p_start.add_argument("--card", type=int, default=None, help="관제 카드 번호(관제가 설치된 저장소에선 필수)")
    p_claim = sub.add_parser("claim", help="선점 신고 — 이 트랙이 손댈 파일/함수를 관제/claims.json 에")
    p_claim.add_argument("name")
    p_claim.add_argument("card", type=int)
    p_claim.add_argument("targets", nargs="+", help="파일 또는 파일:함수")
    p_park = sub.add_parser("park", help="트랙 폴더만 치움 — 브랜치·원격 백업 보존")
    p_park.add_argument("name")
    p_idle = sub.add_parser("park-idle", help=f"{IDLE_PARK_DAYS}일 넘게 안 쓴 트랙 폴더를 전부 치움(브랜치 보존)")
    p_idle.add_argument("--days", type=float, default=IDLE_PARK_DAYS)
    p_finish = sub.add_parser("finish", help="게이트 통과 시 main에 병합 (폴더는 남는다)")
    p_finish.add_argument("name")
    p_finish.add_argument("--attached", action="store_true",
                          help="이 창에서 직접 돈다(기본은 분리 실행 — Claude 시간 제한·창 닫힘에 안 꺼진다)")
    p_close = sub.add_parser("close", help="트랙을 접는다 — 폴더·브랜치 삭제")
    p_close.add_argument("name")
    sub.add_parser("list", help="열린 트랙과 밀린 정도")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "start":
            return start(args.name, full=args.full, card=args.card)
        if args.cmd == "claim":
            validate_name(args.name)
            _control.claim(BASE, args.name, args.card, args.targets)
            return 0
        if args.cmd == "park":
            return park(args.name)
        if args.cmd == "park-idle":
            return park_idle(days=args.days)
        if args.cmd == "finish":
            if args.attached or os.environ.get("TRACK_FINISH_CHILD"):
                return finish(args.name)
            return _finish_detached(args.name)
        if args.cmd == "close":
            return close(args.name)
        return list_tracks()
    except TrackError as e:
        print(f"\n중단: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
