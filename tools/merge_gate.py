"""병합 게이트 — 병합이 **기존보다 더** 깨뜨렸는지만 본다.

`git merge --no-ff --no-commit`으로 커밋 없이 병합만 한 상태에서 돌린다.
통과해야만 `git commit` — 커밋하는 순간 post-commit 훅이 무조건 push하므로
게이트는 커밋 이전에 끝나야 의미가 있다.

## 왜 'green'이 아니라 '기준선'인가

현재 전체 pytest에 이미 25 failed가 있다(정체 미규명, 별건). 게이트가
"전부 green"을 요구하면 **모든 병합이 영구히 막힌다**. 그래서 병합 전
스냅샷을 찍어두고 병합 후와 비교해 **새로 깨진 것만** 막는다.
기존 실패는 통과시키되 `baseline_warnings()`로 남긴다 — 조용히 넘기면
게이트가 눈뜬장님이 된 걸 아무도 모른다.

사용:
    py tools/merge_gate.py snapshot --out before.json   # 병합 전
    py tools/merge_gate.py check --baseline before.json # 병합 후 (exit 0=통과)
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
TARGET = "shopping_shorts"

# "FAILED id - 메시지" / "FAILED id" / "ERROR path - ImportError"
# id에 공백이 든 파라미터(test_p[a b c])가 있어 \S+로는 못 자른다.
_FAIL_RE = re.compile(r"^(?:FAILED|ERROR)\s+(.+?)(?:\s+-\s+.*)?$")

# pytest 종료코드: 0=전부통과 1=테스트실패 → 정상 범위.
# 2=수집오류 3=내부오류 4=사용법오류 5=수집0 → 게이트가 못 본 것.
_PYTEST_SANE_RC = (0, 1)


def make_output_safe():
    """Windows 콘솔은 cp949라 이모지를 인코딩 못 해 print가 UnicodeEncodeError로 터진다.

    실측(2026-07-16 드라이런): 게이트가 기준선을 수집하고도 'ℹ️'를 찍다가 크래시해
    **한 번도 완주하지 못했다.** 출력 장식 때문에 게이트가 죽으면 안 된다.
    인코딩은 그대로 두고(한글은 cp949에서 멀쩡하다) 못 찍는 문자만 '?'로 바꾼다.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, OSError, ValueError):
            pass  # 리다이렉트·파이프 등 reconfigure 못 하는 스트림이면 그냥 둔다


def norm_test_id(tid):
    """비교용 정규화 — 비ASCII(한글 이름)와 깨진 글자(?·�)를 한 기호로. 인코딩이 달라도 같은 테스트는 같게 본다."""
    import re as _re
    return _re.sub(r"[^ ->@-~]+", "?", str(tid or "")).strip()   # '?'(0x3f)도 깨진 글자로 본다


def parse_failed(output):
    """pytest 출력에서 실패한 테스트 id 집합을 뽑는다(정규화된 id)."""
    failed = set()
    for line in output.splitlines():
        m = _FAIL_RE.match(line.strip())
        if m:
            failed.add(norm_test_id(m.group(1)))
    return failed


def _run(cmd, cwd):
    # ★자식(pytest)도 UTF-8로 쓰게 못박는다(2026-10-01 실측): 세션마다 `py`/`py -X utf8`가 섞여 한글 테스트 이름이
    #   한쪽은 제대로, 한쪽은 '?'로 저장돼 **같은 실패가 '새로 깨짐'으로 오판**됐다(기준선 캐시 vs 병합 후 비교).
    import os as _os
    env = {**_os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
    # ★자원 관문이 정한 병렬 수(GATE_XDIST_N)는 **이 프로세스의 pytest 인자**로만 쓴다 — 자식(시험)에 새면 그 값을 검사하는
    #   시험이 게이트 안에서만 깨지고, 칸 밖 재확인에선 통과해 '우연한 실패'로 덮였다(2026-10-03 092 병합 실측 4건).
    env.pop("GATE_XDIST_N", None)
    # ★게이트가 띄운 pytest 는 **개별 락**을 쓴다(2026-10-02, 카드 075): tools/test_video_gate.py 의 finish 시험이
    #   게이트가 이미 쥔 전역 finish 락을 다시 기다리면 영원히 멈춘다(교착). 락 경로는 track._finish_lock_path 가 읽는다.
    import tempfile as _tf
    _priv = Path(_tf.gettempdir()) / ("gate_child_%d" % _os.getpid())
    env.setdefault("TRACK_FINISH_LOCK", str(_priv) + "_finish.lock")
    env.setdefault("TRACK_VIDEO_LOCK", str(_priv) + "_video.lock")
    # ★임시 폴더 자체를 따로 준다(2026-10-02 실측 교착): 기준선은 **main 코드**로 찍는데, 그 코드의 track.py 는 위 환경변수를
    #   모른다 → main 의 finish 시험이 바깥 finish 가 쥔 전역 락(tempfile.gettempdir()/stockbrain_track_finish.lock)을 기다려
    #   워커 4개가 CPU 0 으로 멈췄다. 락 경로가 gettempdir() 에서 나오므로 TMP/TEMP 를 바꾸면 **어느 판본 코드든** 개별 락이 된다.
    _priv.mkdir(parents=True, exist_ok=True)
    for _k in ("TMP", "TEMP", "TMPDIR"):
        env[_k] = str(_priv)
    limit = gate_timeout()
    low = []
    stop = None
    try:
        p = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             encoding="utf-8", errors="replace", env=env)
        stop = _watch_free_memory(p, low)
        try:
            out, err = p.communicate(timeout=limit)
            rc = p.returncode
            if low:
                # ★관문 자원 부족(관제 336, 11-07): 시험 일꾼이 메모리를 쌓아 PC 커밋이 바닥나면 같은 PC 의 Claude 세션·훅이
                #   'malloc failed' 로 죽었다(14일 고갈 경보 102건 중 77건이 관문 중). 남은 메모리가 바닥 아래로 가면 시험 트리를 끝내고
                #   실패 한 줄을 넣는다 → 병합은 거절·라이브 무사·PC 는 산다.
                rc = GATE_LOW_MEMORY_RC
                err = (err or "") + ("\nFAILED GATE_LOW_MEMORY::merge_gate_free_%dMB - 관문 자원 부족: 남은 메모리가 %dMB 아래라 "
                                     "시험 프로세스를 끝냄(merge_gate.gate_abort_free_mb) — 다른 창이 메모리를 비운 뒤 다시 finish\n"
                                     % (low[0], gate_abort_free_mb()))
        except subprocess.TimeoutExpired:
            # ★관문 시간 한도(관제 318, 11-04): 한도가 없어 시험 하나가 멈추면 병합 줄 전체가 끝없이 멈췄다
            #   (10-26 1시간 반 · 11-02 1시간 40분 · 11-02 16:36~ 34시간 — 실제 영상 ffmpeg 파이프 교착, 작업자 2개 CPU 0).
            #   넘으면 그 프로세스 트리(xdist 작업자·ffmpeg 까지)를 끝내고 '관문 시간 초과' 실패 한 줄을 넣는다 → 병합은 거절·라이브 무사·줄은 다음으로.
            kill_tree(p.pid)
            try:
                out, err = p.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                out, err = "", ""
            rc = 124
            err = (err or "") + f"\nFAILED GATE_TIMEOUT::merge_gate_{limit}s - 관문 시간 초과: 멈춘 시험이 있어 시험 프로세스를 끝냄(merge_gate.gate_timeout)\n"
    finally:
        if stop is not None:
            stop.set()
        # ★만든 곳이 치운다(관제 107): pytest 임시 파일이 이 폴더에 쌓여 한 번에 1.4~2.4GB — 안 지워서 하루 7개(11GB)가
        #   C 를 채워 finish 가 「No space left」로 죽었다(2026-10-03). 락·번호표 형제 폴더(gate_child_<pid>_*)도 함께.
        clean_gate_temp(_os.getpid())
    return rc, (out or "") + (err or "")


# ── 관문 메모리(관제 336, 2026-11-07) ─────────────────────────────────────────────────────────────
#  실측: 관문 명령 그대로(-n 2) 전체 시험을 한 pytest 로 돌리면 xdist 일꾼이 시험마다 남긴 메모리(캐시·모델·배열)를 놓지 않아
#  4.3·4.9GB 로 커지고(합 9.2GB) 69% 에서 커밋 여유 5.6GB — 같은 시각 Windows 고갈 경보에 python 8.8GB, 훅 'malloc failed(1MB)',
#  Claude 세션 2개가 꺼졌다. 시작 때 일꾼 수만 정하는 예산(track.GATE_WORKER_MB)으로는 못 막는다.
#  → ① 시험 파일을 묶음으로 나눠 묶음마다 새 pytest(끝나면 메모리 반납) ② 돌면서 남은 메모리를 보고 바닥 아래면 끝낸다.
GATE_CHUNK_FILES = 100       # 한 pytest 프로세스가 돌 시험 파일 수 — 환경변수 GATE_CHUNK_FILES 로 바꾼다
GATE_ABORT_FREE_MB = 3000    # 관문 중 남은 메모리(물리·커밋 중 작은 쪽)가 이 아래면 시험 트리를 끝낸다 — Claude Code 는 2.5GB 근처에서 백그라운드 작업을 끈다
GATE_MEM_POLL_SEC = 3        # 남은 메모리 재는 간격
GATE_LOW_MEMORY_RC = 125     # 자원 부족으로 끝냈을 때 종료코드(124 = 시간 초과)


def free_mb():
    """(판단 주인 — 지금 쓸 수 있는 메모리 MB) = min(남은 물리 메모리, 남은 커밋). 못 재면 큰 값(막지 않는다).
    ★커밋이 먼저 찬다(10-26 RAM 15GB 남았는데 커밋 38.7/39.9GB 로 새 할당 실패, 관제 275). track 의 자원 관문도 이걸 부른다."""
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
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return 10 ** 6
        return int(min(m.ullAvailPhys, m.ullAvailPageFile) / 2 ** 20)
    except Exception:  # noqa: BLE001 — 윈도 밖(서버 등)은 재지 않는다
        return 10 ** 6


def _env_int(name, default, low=1):
    try:
        v = int(os.environ.get(name) or default)
    except ValueError:
        v = default
    return max(low, v)


def gate_abort_free_mb() -> int:
    """(판단 주인 — 관문을 끝낼 남은 메모리 바닥 MB). 환경변수 GATE_ABORT_FREE_MB 로 바꾼다."""
    return _env_int("GATE_ABORT_FREE_MB", GATE_ABORT_FREE_MB, low=0)


def gate_chunk_files() -> int:
    """(판단 주인 — pytest 한 번이 돌 시험 파일 수)."""
    return _env_int("GATE_CHUNK_FILES", GATE_CHUNK_FILES)


def _watch_free_memory(p, low, measure=None, poll=None):
    """p 가 도는 동안 남은 메모리를 재다가 바닥(gate_abort_free_mb) 아래면 p 의 트리를 끝내고 low 에 그 값을 넣는다.
    돌려주는 Event 를 set 하면 감시를 멈춘다."""
    import threading
    measure = measure or free_mb
    poll = GATE_MEM_POLL_SEC if poll is None else poll
    stop = threading.Event()

    def _loop():
        while not stop.wait(poll):
            if p.poll() is not None:
                return
            f = measure()
            if f < gate_abort_free_mb():
                low.append(int(f))
                kill_tree(p.pid)
                return
    threading.Thread(target=_loop, name="gate-mem-watch", daemon=True).start()
    return stop


GATE_TIMEOUT_SEC = 2400      # 관문 한 번(전체 pytest 보통 7~10분)의 한도 — 넘으면 멈춘 것으로 본다. 환경변수 GATE_TIMEOUT_SEC 로 바꾼다


def gate_timeout() -> int:
    """(판단 주인 — 관문 실행 시간 한도) 초."""
    try:
        v = int(os.environ.get("GATE_TIMEOUT_SEC") or GATE_TIMEOUT_SEC)
    except ValueError:
        v = GATE_TIMEOUT_SEC
    return max(1, v)


def kill_tree(pid: int) -> None:
    """프로세스와 그 자식 전부(xdist 작업자·ffmpeg) — 윈도는 taskkill /T, 그 밖은 자식부터."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, stdin=subprocess.DEVNULL)
        return
    try:
        out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True).stdout.split()
    except OSError:
        out = []
    for c in out:
        kill_tree(int(c))
    try:
        os.kill(pid, 9)
    except OSError:
        pass


GATE_TEMP_PREFIX = "gate_child_"


def _rmtree_force(path):
    """읽기 전용 파일까지 지운다. 시험이 만든 git 저장소의 객체 파일은 윈도에서 읽기 전용이라
    rmtree(ignore_errors) 가 조용히 남겼다(2026-10-04 실측: 게이트마다 467KB 폴더가 남음 — 관제 107)."""
    import shutil as _sh
    import stat as _st

    def _again(func, p, *_):
        try:
            os.chmod(p, _st.S_IWRITE)
            func(p)
        except OSError:
            pass
    try:
        _sh.rmtree(path, onexc=_again)
    except TypeError:                                   # 3.12 미만
        _sh.rmtree(path, onerror=_again)
    except OSError:
        pass


def clean_gate_temp(pid, tmp_root=None):
    """gate_child_<pid> 와 그 형제(gate_child_<pid>_finish_queue·_finish.lock 등)를 지운다. 지운 이름 목록."""
    import shutil as _sh
    import tempfile as _tf
    root = Path(tmp_root or _tf.gettempdir())
    base = "%s%d" % (GATE_TEMP_PREFIX, pid)
    removed = []
    for x in root.glob(base + "*"):
        if x.name != base and not x.name.startswith(base + "_"):
            continue                      # gate_child_12 이 gate_child_123 을 지우지 않게
        if x.is_dir():
            _rmtree_force(x)
        else:
            try:
                x.unlink()
            except OSError:
                continue
        if not x.exists():
            removed.append(x.name)
    return removed


def _xdist_args():
    """pytest-xdist가 있으면 4워커 병렬(-n 4, 원래 -n auto). 전역 finish 락이 한 번에 하나의
    게이트만 돌리므로 CPU 스래싱 없이 그 하나가 16코어를 다 쓴다 — 실측 직렬 312초 →
    병렬 44초(7배), 실패집합 완전 동일(9 failed/2396 passed). 미설치 환경은 직렬 폴백."""
    try:
        import xdist  # noqa: F401
    except Exception:
        return []
    # 사장님(2026-09-21): 16코어를 다 쓸 일이 아니다 — 게이트가 돌 때마다 PC가 버벅였다.
    # 4개로 묶어 나머지 코어는 다른 작업에 남긴다.
    # 2026-10-02 사장님 "병렬도 다 해도 된다" → 실측(같은 코드·같은 실패 15건): -n 4 727초 · -n 8 376초 · -n auto(16) 358초.
    #   16개는 8개보다 18초 빠를 뿐이라 코어 절반을 남기는 8개로(카드 081).
    # ★시험 프로세스 수는 finish 의 자원 관문(track._gate_slot)이 남은 메모리·전체 상한으로 정해 넘긴다(2026-10-03 카드 092).
    n = os.environ.get("GATE_XDIST_N", "").strip()
    return ["-n", n if n.isdigit() and int(n) >= 1 else "8"]


def _tools_test_paths(cwd):
    """게이트가 함께 돌 tools 시험 파일(2026-10-02, 카드 075). 관제·관문 도구(track·control·video_gate·live_check …)가
    tools/ 에 있는데 그 시험이 게이트 밖이라, 도구를 깨뜨린 병합이 그대로 들어갔다(10-02 관제수리 → test_video_gate)."""
    root = Path(cwd)
    found = sorted(root.glob("tools/test_*.py")) + sorted(root.glob("tools/*/test_*.py"))
    return [p.relative_to(root).as_posix() for p in found]


def expand_test_paths(cwd, paths):
    """시험 경로 목록 → 시험 파일 목록(폴더는 그 안 test_*.py 를 정렬해 펼친다, 파일·id 는 그대로, 순서·중복 정리)."""
    root = Path(cwd)
    out = []
    for p in paths:
        d = root / str(p)
        items = ([x.relative_to(root).as_posix() for x in sorted(d.rglob("test_*.py"))
                  if "__pycache__" not in x.parts] if d.is_dir() else [str(p)])
        for x in items:
            if x not in out:
                out.append(x)
    return out


def _merge_rc(rcs):
    """묶음별 pytest 종료코드 → 하나. 이상(2·3·4·124·125…)이 하나라도 있으면 그 첫 값, 실패(1)가 있으면 1,
    전부 수집 0(5)이면 5, 아니면 0. (묶음 하나가 시험 0개여서 5 가 나와도 전체를 망치지 않게)"""
    bad = [r for r in rcs if r not in (0, 1, 5)]
    if bad:
        return bad[0]
    if 1 in rcs:
        return 1
    return 5 if rcs and all(r == 5 for r in rcs) else 0


def run_pytest(cwd, paths, run=_run, workers=None, chunk=None):
    """(판단 주인 — 관문 pytest 실행, 관제 336) 관문의 pytest 는 전부 여기서만 띄운다(snapshot·rerun_ids·track._rerun_on_main).
    시험 파일을 chunk(기본 gate_chunk_files)개씩 나눠 **묶음마다 새 pytest 프로세스**로 돌린다 — 일꾼이 시험마다 남긴
    메모리가 묶음이 끝날 때 돌아온다(한 프로세스로 전부 돌면 일꾼 4~5GB, 11-07 실측). 남은 메모리 감시는 run(_run)이 한다.
    workers: None = 자원 관문 값(_xdist_args) · 0 = 직렬 · n = -n n.
    자원 부족(125)·시간 초과(124)면 남은 묶음을 돌리지 않는다(더 누르지 않는다). 돌려줌 (rc, 묶음 출력 전부)."""
    files = expand_test_paths(cwd, paths)
    if not files:
        return 5, ""
    xd = _xdist_args() if workers is None else (["-n", str(workers)] if workers else [])
    size = max(1, int(chunk or gate_chunk_files()))
    rcs, outs = [], []
    for i in range(0, len(files), size):
        rc, out = run([sys.executable, "-m", "pytest", *files[i:i + size], "-q", "--tb=no", "-rfE",
                       "--continue-on-collection-errors", "-p", "no:cacheprovider", *xd], cwd)
        rcs.append(rc)
        outs.append(out or "")
        if rc in (GATE_LOW_MEMORY_RC, 124):
            break
    return _merge_rc(rcs), "\n".join(outs)


def snapshot(cwd=BASE, run=_run, paths=None):
    """지금 이 워킹트리 상태를 찍는다 (문법·import·pytest — shopping_shorts/tests + tools 시험).
    paths: 그 시험 파일들만(재시도 때 끼어든 코드와 관련된 것만 — 카드 092)."""
    rc_c, out_c = run([sys.executable, "-m", "compileall", TARGET, "-q"], cwd)
    rc_i, out_i = run([sys.executable, "-c", f"import {TARGET}.app"], cwd)
    # ★--continue-on-collection-errors: tools 쪽 시험 파일 하나가 수집에서 죽어도 나머지는 돈다(전체 rc=2 로 게이트 무력화 금지).
    #   -rfE: 수집 오류(ERROR)도 실패 목록에 들어와 '새로 깨짐' 비교를 받는다.
    rc_p, out_p = run_pytest(cwd, list(paths) if paths else [f"{TARGET}/tests", *_tools_test_paths(cwd)], run=run)
    return {
        "compile_ok": rc_c == 0,
        "compile_out": out_c[-4000:],
        "import_ok": rc_i == 0,
        "import_out": out_i[-4000:],
        "pytest_rc": rc_p,
        "pytest_out": out_p[-4000:],
        "failed": sorted(parse_failed(out_p)),
    }


def snapshot_light(cwd=BASE, run=_run):
    """기준선은 **문법·import 만**(2026-10-02 카드 081). 전체 pytest(7~10분)는 병합본에서만 돌리고, 실패한 것만
    main 코드로 다시 돌려 '원래 실패'를 가른다(track._known_main_failures). 실측: 오늘 main 커밋 108개 중 72개가
    관제·핸드오프라 커밋별 기준선 캐시가 거의 안 먹었다(새로 수집 6 · 재사용 2)."""
    rc_c, out_c = run([sys.executable, "-m", "compileall", TARGET, "-q"], cwd)
    rc_i, out_i = run([sys.executable, "-c", f"import {TARGET}.app"], cwd)
    return {"compile_ok": rc_c == 0, "compile_out": out_c[-4000:], "import_ok": rc_i == 0, "import_out": out_i[-4000:],
            "pytest_rc": 0, "pytest_out": "", "failed": [], "light": True}


def test_files_of(ids):
    """시험 id → 그 시험 파일(중복 없이, 순서 유지). 'a.py::b[x]' → 'a.py'. 파일 경로가 오면 그대로."""
    out = []
    for i in ids:
        f = str(i).split("::", 1)[0]
        if f not in out:
            out.append(f)
    return out


def rerun_ids(cwd, ids, run=_run, workers=None):
    """이 폴더 코드로 그 시험들이 든 **파일을 통째로** 다시 돌려, 물어본 id 중 **여전히 깨지는 것**을 돌려준다.
    ★id 하나씩 돌리면 같은 파일 안 다른 시험의 영향(순서·공유 상태)이 사라져 '원래 실패'가 통과로 보였다
    (2026-10-02 실측 15건 — 파일 통째로 main 에서 돌리니 6건 재현, 카드 083). 파일 경로를 주면 그 파일의 실패 전부."""
    ids = list(ids)
    if not ids:
        return set()
    files = test_files_of(ids)
    rc, out = run_pytest(cwd, files, run=run, workers=workers if workers else (None if len(files) > 4 else 0))
    failed = parse_failed(out)
    asked_files = {i for i in ids if "::" not in str(i)}
    return {f for f in failed if f in ids or f.split("::", 1)[0] in asked_files}


def baseline_warnings(before):
    """병합 전부터 깨져 있던 것 — 막지는 않되 반드시 보여준다."""
    warn = []
    if not before["compile_ok"]:
        warn.append("⚠️ 병합 전부터 문법 오류가 있다 — 게이트의 문법 검사는 무력하다")
    if not before["import_ok"]:
        warn.append("⚠️ 병합 전부터 import가 깨져 있다 — 의미적 충돌 검출기가 죽은 상태다")
    if before["pytest_rc"] not in _PYTEST_SANE_RC:
        warn.append(f"⚠️ 병합 전부터 pytest가 비정상 종료(rc={before['pytest_rc']}) — 테스트 검사는 무력하다")
    if before.get("light"):
        warn.append("ℹ️ 기준선: 문법·import 만 — 전체 시험은 병합본에서 한 번, 실패한 것만 main 에서 재확인(카드 081)")
    elif before["failed"]:
        warn.append(f"ℹ️ 병합 전 이미 실패 {len(before['failed'])}건 (기준선으로 통과시킴)")
    return warn


def compare(before, after):
    """기준선 대비 **새로** 깨진 것만 문제로 센다. 빈 리스트 = 통과."""
    problems = []

    if before["compile_ok"] and not after["compile_ok"]:
        problems.append("문법 오류가 새로 생겼다 (compileall 실패)")

    if before["import_ok"] and not after["import_ok"]:
        problems.append(f"import 체인이 새로 깨졌다 (import {TARGET}.app 실패)")

    before_sane = before["pytest_rc"] in _PYTEST_SANE_RC
    after_sane = after["pytest_rc"] in _PYTEST_SANE_RC
    if before_sane and not after_sane:
        problems.append(
            f"pytest가 아예 못 돌았다 (rc={after['pytest_rc']} — 수집 오류 등). "
            "실패 목록이 비어 있어도 통과가 아니다."
        )

    # ★기준선이 비정상이면 실패 목록 비교는 의미가 없다(2026-08-06 실사고).
    #   before가 rc=2(수집 오류)면 pytest가 **한 건도 안 돌아** before["failed"]가 빈다.
    #   그 상태로 빼기를 하면 **원래 있던 실패 전부가 '새로 깨진 것'으로 잡혀**, 하필
    #   그 수집 오류를 고치는 커밋이 막힌다(실측: 기존 실패 22건이 전부 신규로 오탐).
    #   기준선이 깨진 건 이 병합의 잘못이 아니다 — after가 정상으로 돌아왔다면 통과시키고
    #   경고만 남긴다. after까지 비정상이면 위 before_sane 분기가 이미 잡는다.
    if not before_sane:
        if not after_sane:
            # 둘 다 비정상 = 이 병합이 기준선을 고치지 못했다. 실패 목록이 양쪽 다
            # 비어 있어 비교가 무의미하므로, 통과시키면 **검증 없이 나간다**(오늘 실제로
            # 그렇게 병합 1건이 나갔다). 막고 사람이 보게 한다.
            problems.append(
                f"pytest가 병합 전후 모두 비정상이다 (before rc={before['pytest_rc']}, "
                f"after rc={after['pytest_rc']}). 실패 목록이 비어 있어도 통과가 아니다 — "
                "수집 오류부터 고쳐라.")
            return problems
        print("ℹ️ 기준선 pytest가 비정상(rc=%d)이라 실패 비교를 건너뛴다 — 병합 후는 "
              "rc=%d(실패 %d건). 이 병합이 기준선을 고쳤을 수 있다."
              % (before["pytest_rc"], after["pytest_rc"], len(after["failed"])))
        return problems

    # 옛 기준선 저장본(정규화 전 이름)과도 맞게 양쪽 다 정규화해 비교한다
    new_failed = sorted(set(map(norm_test_id, after["failed"])) - set(map(norm_test_id, before["failed"])))
    if new_failed:
        shown = "\n".join(f"    - {t}" for t in new_failed[:20])
        more = f"\n    ... 외 {len(new_failed) - 20}건" if len(new_failed) > 20 else ""
        problems.append(f"새로 깨진 테스트 {len(new_failed)}건:\n{shown}{more}")

    return problems


def _print_report(before, after, problems):
    for w in baseline_warnings(before):
        print(w)
    if problems:
        print("\n❌ 게이트 실패 — 병합이 새로 깨뜨린 것:\n")
        for p in problems:
            print(f"  • {p}")
        if not after["import_ok"]:
            print(f"\n--- import 출력 ---\n{after['import_out']}")
        if after["pytest_rc"] not in _PYTEST_SANE_RC:
            print(f"\n--- pytest 출력 ---\n{after['pytest_out']}")
    else:
        print(f"\n✅ 게이트 통과 — 새로 깨진 것 없음 (기존 실패 {len(before['failed'])}건은 그대로)")


def main(argv=None):
    make_output_safe()
    parser = argparse.ArgumentParser(description="병합 게이트")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_snap = sub.add_parser("snapshot", help="지금 상태를 파일로 찍는다 (병합 전)")
    p_snap.add_argument("--out", required=True)

    p_check = sub.add_parser("check", help="기준선과 비교한다 (병합 후)")
    p_check.add_argument("--baseline", required=True)

    args = parser.parse_args(argv)

    if args.cmd == "snapshot":
        snap = snapshot()
        Path(args.out).write_text(
            json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
        for w in baseline_warnings(snap):
            print(w)
        print(f"기준선 저장: {args.out} (실패 {len(snap['failed'])}건)")
        return 0

    before = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    after = snapshot()
    problems = compare(before, after)
    _print_report(before, after, problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
