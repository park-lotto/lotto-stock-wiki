"""자식 프로세스 실행 한 자리 — 파이썬 쪽 (2026-09-25 B5-a · engine-defects.md D8 · 수강생 윈도우 검은 창 E5).

노드 쪽 `tools/lib/proc.mjs` 와 같은 규약이다. flow/*.py 의 자식 실행(subprocess.run·Popen·check_output …)은 이 모듈로 부른다
(2026-09-25 B5-flow 가 기존 26곳을 옮기고 정적 규칙을 켰다 — tests/flow_proc_test.py RULES · 배선 증명 tests/flow_launch_wiring_test.py).

    import proc
    r = proc.run(["ffmpeg", ...], capture_output=True, text=True, timeout=300)   # subprocess.run 과 같은 모양
    proc.Popen([chrome, url], detached=True, stdout=proc.DEVNULL)                  # 우리보다 오래 사는 것(크롬·에이전트)
    proc.kill_tree(pid)                                                            # 자손 나무째 끝내기

왜:
  · 윈도우: 콘솔 없는(분리된) 부모가 콘솔 프로그램을 창 옵션 없이 띄우면 자식마다 새 콘솔 창이 생기고, 그 창을 닫으면 제작이 죽는다
    (0xC000013A). 파이썬 공식 문서: subprocess.CREATE_NO_WINDOW 「the new process will not create a window」 → 모든 자식에 넣는다.
    CREATE_NEW_CONSOLE 은 거부한다(PROC_WINDOW_FORBIDDEN).
  · 윈도우 창 없는 자식의 표준 핸들(2026-09-25 B5-flow): CREATE_NO_WINDOW 자식은 STARTF_USESTDHANDLES 가 없으면 부모의 표준 핸들이 아니라
    **새 숨은 콘솔**을 받는다(rprichard/win32-console-docs — CreateProcess 표준 핸들 규칙: NewConsoleNoWindow 는 새 콘솔 · STARTF_USESTDHANDLES 의
    STARTUPINFO 핸들이 콘솔 모드보다 먼저). CPython 은 stdin·stdout·stderr 가 셋 다 None 이면 그 플래그를 켜지 않는다(`Popen._get_handles`).
    → 셋 다 안 준 자식에는 부모의 CRT 표준 fd(0·1·2)를 명시해 넘긴다(CPython 이 상속 가능한 사본을 만들고 플래그를 켠다 · 부모 핸들은 그대로).
    그 fd 가 실제 핸들이 아니면(pythonw 처럼 표준 핸들 없음 · EBADF · -2/-1/0) 그 자리는 DEVNULL. 노드(libuv)는 늘 표준 핸들을 명시해 넘기므로 같은 모양이 된다.
    이것이 없으면 flow_episode 1단계(new_topic)·폴백(make_episode) 출력이 작업 로그(logTail = 수강생 실패 이유 원문)에서 사라진다.
  · 분리 실행(detached=True): 윈도우 DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP(student-pc.md 8-2 open_flow_tab) · 그 밖 새 세션(start_new_session).
    Microsoft 「Process Creation Flags」: CREATE_NO_WINDOW 는 DETACHED_PROCESS 와 함께면 무시된다 → 분리 실행에는 넣지 않는다.
    분리하지 않은 자식은 새 세션·그룹을 만들지 않는다 — 감독자(child_supervisor)의 그룹 정리가 닿아야 한다.
  · 제한시간: CPython run 은 제한시간에 직계 자식만 죽인다. 윈도우에서는 그 뒤 communicate() 가 손자가 쥔 파이프 때문에 멈출 수 있다
    (CPython subprocess.run 소스 주석의 그 자리). 여기서는 **자손 나무째** 끝낸 뒤 원래처럼 subprocess.TimeoutExpired 를 올린다
    (`except subprocess.TimeoutExpired` 호출자는 그대로). 나무 정리가 실패하면 삼키지 않고 ProcError("PROC_TREE_KILL_FAILED") —
    SubprocessError 의 하위라 `except (OSError, subprocess.SubprocessError)` 가 그대로 잡는다.
    끝낸 뒤 두 플랫폼 모두 파이프를 PIPE_GRACE_S 만큼 거둬 **글자로 푼** 출력을 예외에 싣는다. 부모 사슬 밖으로 빠진 손자(뿌리·중간이 먼저 끝나
    init 으로 넘어간 것 — 찾을 수 없고, 남의 것일 수 있어 신호를 보내지 않는다)가 파이프를 쥐고 있으면 조용히 넘기지 않고 ProcError("PROC_PIPE_HELD")
    (2026-09-25 B5-flow · B5-a 판 POSIX 는 거두지 않아 그 손자를 알리지 않았고 예외 출력이 bytes 조각이었다 — 노드 runFile PROC_TREE_ESCAPED 와 같은 뜻).
  · 윈도우 communicate 일꾼(2026-09-26 B5-flow 2회차 · B5-a 재검토 minor ②): 윈도우 CPython communicate 는 파이프마다 일꾼 스레드를 띄우고
    (읽기 stdout_thread·stderr_thread · 쓰기 _stdin_thread 는 3.13.x 일부 판 이상 — 이 맥 3.13.13·3.14.7 원문에 있고 3.11.15·3.12.12 에는 없다),
    제한시간·중단이면 일꾼은 막힌 채 남는다. `with Popen` 안에서 예외를 올리면
    Popen.__exit__ 의 close() 가 일꾼이 쥔 버퍼 잠금을 기다려 **파이프를 쥔 프로세스가 끝날 때까지** 멈췄다(PROC_PIPE_HELD 가 쥔 시간만큼 늦게 ·
    PROC_TREE_KILL_FAILED 는 살아남은 자손 수명만큼 · KeyboardInterrupt 도). → 예외로 with 를 떠날 때 아직 그 파이프를 쥔 일꾼에게 파이프를
    맡긴다(_WorkerOwned — 다른 스레드의 close 는 미루고, 일꾼은 끝나면 스스로 닫는다). 쥔 프로세스에는 여전히 신호를 보내지 않는다.
    「일꾼이 아직 쥐나」는 Thread.is_alive() 가 아니라 _worker_holds 한 규칙으로 본다(2026-09-26 수정 1회차 — 3.12 이하에서 신호가 join 을 끊으면
    is_alive() 가 도는 일꾼을 끝났다고 말한다 · 그 함수 설명). 일꾼 이름은 CPython 내부 이름이다 — tests/flow_proc_test.py 가 실행 중인 파이썬의
    subprocess.py 원문에서 확인한다. POSIX 는 스레드가 없어 그대로다.
    3.12 이하 윈도우는 stdin 을 일꾼이 아니라 부른 스레드가 **제한시간 없이** 쓴다 → 그 판에서 input= 과 timeout= 을 함께 주면 자식이 stdin 을
    안 읽을 때 제한시간이 지켜지지 않는다. flow/ 에는 그런 호출이 없다(tests/flow_proc_test.py 정적 시험이 지킨다).
  · 나무 규칙은 tools/lib/process_tree.mjs 의 descendants 범위와 같다: POSIX 는 얼려서(SIGSTOP) 모은 뒤 끝내고, 윈도우는 taskkill /T /F
    (뿌리가 먼저 죽었으면 남은 자손을 하나씩 · 그래도 남으면 TASKKILL_FAILED). 도구는 SystemRoot 절대경로로 부른다(최소 환경에서 이름으로는 ENOENT).
  · 이 모듈은 .cmd/.bat 해석·최소 환경을 하지 않는다(설계가 파이썬 쪽에 요구한 것은 창·분리·나무 종료) — 윈도우 CreateProcess 는 이름으로 .exe 만 찾는다.
    flow/ 가 부르는 agy·ffmpeg·ffprobe·node 는 모두 .exe 다.
근거: work/_maintenance/student-fixes-20260923/design/engine-defects.md D8 · notes/B5-a.md.
"""
import os, signal, subprocess, threading

PIPE, DEVNULL, STDOUT = subprocess.PIPE, subprocess.DEVNULL, subprocess.STDOUT
TimeoutExpired, CalledProcessError = subprocess.TimeoutExpired, subprocess.CalledProcessError
CompletedProcess, SubprocessError = subprocess.CompletedProcess, subprocess.SubprocessError

# Microsoft 「Process Creation Flags」 값 — 윈도우 파이썬에서는 subprocess 의 상수와 같다(비윈도우 파이썬에는 상수가 없어 문서 값을 쓴다).
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
CREATE_NEW_PROCESS_GROUP = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

WINDOWS_TOOL_TIMEOUT_S = 60      # tools/lib/process_tree.mjs 와 같은 상한(느린 PC 의 PowerShell·WMI 콜드스타트 15초+ — child_supervisor 주석)
PS_TIMEOUT_S = 2                 # 감독자와 같은 ps 상한
PIPE_GRACE_S = 2.0               # 나무를 끝낸 뒤 파이프를 거둘 여유(우리 프로세스 정리 시간 — 외부 서비스 숫자가 아니다)
FREEZE_ROUNDS = 50               # 얼리기 반복 상한(얼린 프로세스는 새 자식을 못 만들어 보통 2~3회에 멈춘다)
WINDOWS_TABLE_SCRIPT = 'Get-CimInstance Win32_Process | ForEach-Object { "$($_.ProcessId) $($_.ParentProcessId)" }'


class ProcError(subprocess.SubprocessError):
    """코드가 붙은 실행 규약 오류(PROC_WINDOW_FORBIDDEN · PROC_TREE_PID_INVALID · PROC_TREE_KILL_FAILED · TASKKILL_FAILED …)."""

    def __init__(self, code, message, **detail):
        super().__init__(message)
        self.code, self.detail = code, detail


def on_windows():
    """플랫폼 판별 한 자리 — 시험이 이 함수를 바꿔 윈도우 갈래를 모의한다(tools/lib/platform.mjs 와 같은 생각)."""
    return os.name == "nt"


def _env_get(env, name):
    """윈도우 env 이름은 대소문자를 가리지 않는다 — 평범한 dict 로 받은 env 에서도 그렇게 찾는다."""
    if name in env:
        return env[name]
    upper = name.upper()
    for key, value in env.items():
        if key.upper() == upper:
            return value
    return None


def windows_system_tool(name, env=None):
    """tools/lib/platform.mjs windowsSystemTool 과 같은 규칙: SystemRoot 아래 실제 파일 · 없으면 이름 그대로."""
    env = os.environ if env is None else env
    root = _env_get(env, "SystemRoot") or _env_get(env, "windir") or "C:\\Windows"
    path = (os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe") if name == "powershell"
            else os.path.join(root, "System32", name + ".exe"))
    return path if os.path.isfile(path) else name


STD_NAMES = (("stdin", 0), ("stdout", 1), ("stderr", 2))


def _inherited_std(fd):
    """윈도우: 부모의 CRT 표준 fd 가 실제 핸들이면 그 fd(CPython 이 msvcrt.get_osfhandle → 상속 가능한 사본), 아니면 DEVNULL.
    -2 는 CRT 의 「콘솔 없음」 표시이자 GetCurrentThread 의 가짜 핸들 값이라, 넘기면 CPython 이 엉뚱한 핸들을 복제한다. 0·-1 은 핸들이 아니다."""
    try:
        import msvcrt
        handle = msvcrt.get_osfhandle(fd)
    except (ImportError, OSError):
        return DEVNULL
    return fd if isinstance(handle, int) and handle > 0 else DEVNULL


def launch_kwargs(kw=None, *, detached=False):
    """subprocess 에 넘길 kwargs(부른 쪽 dict 는 바꾸지 않는다). 규칙은 모듈 머리말."""
    kw = dict(kw or {})
    flags = kw.pop("creationflags", 0) or 0
    if on_windows():
        if flags & CREATE_NEW_CONSOLE:
            raise ProcError("PROC_WINDOW_FORBIDDEN", "CREATE_NEW_CONSOLE 은 금지다 — 윈도우에 콘솔 창이 뜨고, 그 창을 닫으면 제작이 죽는다(2026-09-23 E5)")
        flags |= (DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP) if detached else CREATE_NO_WINDOW
        kw["creationflags"] = flags
        if (not detached and all(kw.get(name) is None for name, _ in STD_NAMES)
                and not kw.get("capture_output") and kw.get("input") is None):
            # 창 없는 자식이 새 숨은 콘솔이 아니라 부모의 표준 핸들을 받게(모듈 머리말) — 분리 실행(DETACHED)은 부르는 쪽이 정한다.
            # capture_output(→ stdout·stderr)·input(→ stdin)은 CPython 이 핸들을 정해 이미 STARTF_USESTDHANDLES 를 켠다 — 함께 주면
            # ValueError 다(2026-10-23 win-main · 실행기 `_spawn` 이 이 규약을 쓰며 드러남). 그때는 채우지 않는다.
            for name, fd in STD_NAMES:
                kw[name] = _inherited_std(fd)
    else:
        if flags:
            kw["creationflags"] = flags        # 파이썬이 ValueError 로 거절한다 — 가리지 않는다
        if detached:
            kw["start_new_session"] = True
    return kw


def Popen(*args, detached=False, **kw):
    """subprocess.Popen 과 같다(돌려주는 것도 subprocess.Popen). detached=True 는 우리보다 오래 살 자식(크롬·에이전트)."""
    return subprocess.Popen(*args, **launch_kwargs(kw, detached=detached))


# 윈도우 CPython communicate 의 일꾼 스레드 — (파이프 속성, 일꾼 속성). Lib/subprocess.py Popen._communicate 의 `if _mswindows:` 갈래:
# 읽기 stdout_thread·stderr_thread(_readerthread: fh.read() 뒤 fh.close()) · 쓰기 _stdin_thread(3.13.x 일부 판 이상 — 이 맥 3.13.13·3.14.7 원문 ·
# _writerthread → _stdin_write: 다 쓰고 self.stdin.close() — 속성으로 다시 찾으므로 파이프를 None 으로 떼면 일꾼이 AttributeError 로 죽는다).
# 3.12 이하(3.11.15·3.12.12 원문)는 stdin 일꾼이 없다(부른 스레드가 씀 — 맡길 것 없음). POSIX 는 selector 로 읽어 일꾼이 없다.
COMMUNICATE_WORKERS = (("stdout", "stdout_thread"), ("stderr", "stderr_thread"), ("stdin", "_stdin_thread"))


def _worker_holds(stream, worker):
    """communicate 일꾼이 아직 그 파이프를 쥐나(read/write 안 — 버퍼 잠금을 쥠 — 이고, 끝나면 스스로 닫는가). 맡기기와 미룬 close 가 이 한 규칙을 쓴다.
    끝남 표시 둘 중 하나면 쥐지 않는다:
      ① 일꾼이 스스로 닫았다 — stream.closed(읽기 일꾼 fh.close() · 쓰기 일꾼 self.stdin.close()).
      ② 일꾼 스레드가 threading.enumerate() 에 없다 — 일꾼의 run() 이 끝나 _bootstrap_inner 의 finally 가 _delete() 로 뺐다
         (예외로 죽어 닫지 못한 일꾼도 여기서 끝난 것으로 본다 — ①만 보면 그 파이프는 아무도 안 닫아 GC 까지 샌다).
    Thread.is_alive() 를 쓰지 않는다: CPython 3.12 이하(3.11.15·3.12.12 threading.py _wait_for_tstate_lock)는 신호 처리기가 올린 예외
    (KeyboardInterrupt 등)가 join() 을 끊으면 `except:` 갈래가 lock.locked() — 아직 도는 일꾼이 쥔 tstate 잠금 — 를 보고 그 잠금을 풀고 _stop() 해
    is_alive() 가 False 가 된다(3.13 부터 join 새 구현 · 윈도우는 3.14 부터 잠금 기다림이 신호로 끊기지만, 제한시간 있는 join 은 기다림이 끝난 직후
    그 try 안에서 처리기가 돌 수 있다 — 원문으로 본 추론 · 윈도우 실측 안 함). _active(= enumerate)는 일꾼 스스로 빼므로 그 경우에도 맞다.
    남는 틈: 예외로 죽는 일꾼이 _delete() 에 이르기 전(excepthook 도는 중)에 재면 쥔 것으로 보고 미룬다 — 그 파이프는 Popen 객체가 풀릴 때 닫힌다(멈춤 아님)."""
    return not stream.closed and worker in threading.enumerate()


class _WorkerOwned:
    """아직 막혀 있는 communicate 일꾼이 쥔 파이프. 다른 스레드(Popen.__exit__)의 close() 는 일꾼에게 미룬다 — 일꾼은 읽기/쓰기가 끝나면
    스스로 닫는다. 일꾼 자신의 close()(_stdin_write 의 self.stdin.close())와 일꾼이 더는 쥐지 않을 때의 close() 는 진짜로 닫는다(_worker_holds).
    나머지는 그대로 넘긴다."""

    __slots__ = ("_stream", "_worker")

    def __init__(self, stream, worker):
        self._stream, self._worker = stream, worker

    def close(self):
        if threading.current_thread() is self._worker or not _worker_holds(self._stream, self._worker):
            self._stream.close()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def _leave_pipes_to_workers(process):
    """예외로 `with Popen` 을 떠나기 직전: 아직 파이프를 쥔 일꾼에게 그 파이프를 맡긴다(모듈 머리말 「윈도우 communicate 일꾼」 · 판정 _worker_holds).
    일꾼이 없거나(POSIX · 3.12 이하 윈도우 stdin) 더는 쥐지 않으면 그대로 둔다 — __exit__ 가 막히지 않고 닫는다."""
    for name, attr in COMMUNICATE_WORKERS:
        stream, worker = getattr(process, name, None), getattr(process, attr, None)
        if stream is not None and not isinstance(stream, _WorkerOwned) and isinstance(worker, threading.Thread) and _worker_holds(stream, worker):
            setattr(process, name, _WorkerOwned(stream, worker))


def _end_after_timeout(process, exc):
    try:
        kill_tree(process.pid)
    except Exception as e:
        # 정리 실패는 삼키지 않는다 — 직계 자식만이라도 끝내 무한 대기를 막고, 코드로 올린다.
        process.kill()
        process.wait()
        raise ProcError("PROC_TREE_KILL_FAILED", f"제한시간({exc.timeout}s) 초과 뒤 자손 나무 정리를 확인하지 못했다: {e}", timeout=exc.timeout) from e
    # 두 플랫폼 같게(2026-09-25 B5-flow): 끝낸 뒤 남은 출력을 거둬 예외에 싣는다(communicate 는 제한시간 뒤 다시 불러도 출력을 잃지 않는다 — 파이썬 문서).
    # 잡지 못한 자손(부모 사슬 밖)이 파이프를 쥐고 있으면 여유 뒤 알린다 — 그 프로세스에는 신호를 보내지 않는다(남의 것일 수 있다).
    try:
        exc.stdout, exc.stderr = process.communicate(timeout=PIPE_GRACE_S)
    except subprocess.TimeoutExpired as late:
        raise ProcError("PROC_PIPE_HELD", f"제한시간({exc.timeout}s) 초과로 나무를 끝냈지만 파이프가 {PIPE_GRACE_S}s 안에 닫히지 않았다 — "
                        "부모 사슬 밖으로 빠진 자손이 쥐고 있다(끝내지 않았다)", timeout=exc.timeout) from late


def run(*popenargs, input=None, capture_output=False, timeout=None, check=False, **kwargs):
    """subprocess.run 과 같은 모양·같은 예외. 다른 점은 제한시간에 자손 나무째 끝낸다는 것뿐이다."""
    if input is not None:
        if kwargs.get("stdin") is not None:
            raise ValueError("stdin and input arguments may not both be used.")
        kwargs["stdin"] = PIPE
    if capture_output:
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout and stderr arguments may not be used with capture_output.")
        kwargs["stdout"] = kwargs["stderr"] = PIPE
    with subprocess.Popen(*popenargs, **launch_kwargs(kwargs)) as process:
        try:
            try:
                stdout, stderr = process.communicate(input, timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                _end_after_timeout(process, exc)
                raise
            except BaseException as exc:
                # CPython 은 여기서 직계 자식만 죽인다(KeyboardInterrupt 등). 원래 예외가 주인공이다 — 정리 실패는 그 예외에 덧붙여 알린다.
                try:
                    kill_tree(process.pid)
                except Exception as cleanup:
                    process.kill()
                    if hasattr(exc, "add_note"):
                        exc.add_note(f"자손 나무 정리 실패: {cleanup}")
                raise
        except BaseException:
            # 예외로 with 를 떠나는 모든 길(PROC_PIPE_HELD · PROC_TREE_KILL_FAILED · TimeoutExpired · KeyboardInterrupt …) 한 자리:
            # 윈도우 일꾼이 아직 막혀 있는 파이프는 그 일꾼에게 맡긴다 — __exit__ 가 쥔 프로세스를 기다리지 않게(모듈 머리말).
            _leave_pipes_to_workers(process)
            raise
        retcode = process.poll()
        if check and retcode:
            raise CalledProcessError(retcode, process.args, output=stdout, stderr=stderr)
    return CompletedProcess(process.args, retcode, stdout, stderr)


def call(*popenargs, timeout=None, **kwargs):
    return run(*popenargs, timeout=timeout, **kwargs).returncode


def check_call(*popenargs, **kwargs):
    retcode = call(*popenargs, **kwargs)
    if retcode:
        cmd = kwargs.get("args") or (popenargs[0] if popenargs else None)
        raise CalledProcessError(retcode, cmd)
    return 0


def check_output(*popenargs, timeout=None, **kwargs):
    for kw in ("stdout", "check"):
        if kw in kwargs:
            raise ValueError(f"{kw} argument not allowed, it will be overridden.")
    if "input" in kwargs and kwargs["input"] is None:
        # CPython 과 같이: input=None 을 명시하면 빈 입력(표준입력을 닫아 자식이 기다리지 않게)
        text = kwargs.get("universal_newlines") or kwargs.get("text") or kwargs.get("encoding") or kwargs.get("errors")
        kwargs["input"] = "" if text else b""
    return run(*popenargs, stdout=PIPE, timeout=timeout, check=True, **kwargs).stdout


# ── 자손 나무 ──────────────────────────────────────────────────
def _descendants(rows, root):
    """부모 사슬 너비 우선(뿌리는 살아 있으면 포함 · 좀비 제외 · 순환 안전). rows = (pid, ppid[, state])."""
    zombie = lambda r: len(r) > 2 and isinstance(r[2], str) and r[2].startswith("Z")
    found, seen, queue = [], {root}, [root]
    if any(r[0] == root and not zombie(r) for r in rows):
        found.append(root)
    while queue:
        parent = queue.pop(0)
        for r in rows:
            if r[1] == parent and r[0] not in seen:
                seen.add(r[0])
                queue.append(r[0])
                if not zombie(r):
                    found.append(r[0])
    return found


def _run_tool(argv, timeout):
    """나무 도구(ps·PowerShell·taskkill) 실행 — 이 모듈의 창 규칙을 그대로 쓴다."""
    # 받는 쪽 표준 핸들을 launch_kwargs 에 알린다 — 셋 다 안 준 것으로 보이면 윈도우에서 부모 표준 fd 를 채워 capture_output 과 부딪친다
    return subprocess.run(argv, text=True, encoding="utf-8", errors="replace", timeout=timeout, **launch_kwargs({"stdout": PIPE, "stderr": PIPE}))


def _posix_table():
    r = _run_tool(["ps", "-axo", "pid=,ppid=,state="], PS_TIMEOUT_S)
    if r.returncode != 0:
        raise ProcError("PROC_TREE_TABLE_FAILED", f"ps 실패({r.returncode}): {(r.stderr or '').strip()[-300:]}")
    rows = []
    for line in r.stdout.splitlines():
        f = line.split()
        if len(f) >= 3 and f[0].isdigit() and f[1].isdigit():
            rows.append((int(f[0]), int(f[1]), f[2]))
    return rows


def _windows_table(env, run_cmd):
    r = run_cmd([windows_system_tool("powershell", env), "-NoProfile", "-NonInteractive", "-Command", WINDOWS_TABLE_SCRIPT], timeout=WINDOWS_TOOL_TIMEOUT_S)
    if r.returncode != 0:
        raise ProcError("PROC_TREE_TABLE_FAILED", f"PowerShell 프로세스 표 실패({r.returncode}): {(r.stderr or '').strip()[-300:]}")
    rows = []
    for line in (r.stdout or "").splitlines():
        f = line.split()
        if len(f) >= 2 and f[0].isdigit() and f[1].isdigit():
            rows.append((int(f[0]), int(f[1])))
    return rows


def _kill_windows_tree(root, env, run_cmd, table):
    taskkill = windows_system_tool("taskkill", env)
    first = run_cmd([taskkill, "/T", "/F", "/PID", str(root)], timeout=WINDOWS_TOOL_TIMEOUT_S)
    if first.returncode == 0:
        return [root]
    # 뿌리가 이미 죽었으면 taskkill /T 는 「찾을 수 없음」으로 실패한다 — 남은 자손(고아)을 하나씩. 성패는 표를 다시 읽어 가린다.
    members = _descendants(table(), root)
    if not members:
        return []
    attempts = []
    for pid in members:
        r = run_cmd([taskkill, "/T", "/F", "/PID", str(pid)], timeout=WINDOWS_TOOL_TIMEOUT_S)
        if r.returncode != 0:
            attempts.append({"pid": pid, "returncode": r.returncode, "stderr": (r.stderr or "").strip()[-200:]})
    remaining = _descendants(table(), root)
    if not remaining:
        return members
    raise ProcError("TASKKILL_FAILED", f"taskkill 뒤에도 자손 {len(remaining)}개가 남았다: {remaining[:10]}",
                    remaining=remaining, attempts=attempts, first=(first.stderr or "").strip()[-200:])


def _freeze_kill(root, sig, table, kill):
    seen, stopped, stable = set(), [], False
    try:
        for _ in range(FREEZE_ROUNDS):
            fresh = [p for p in _descendants(table(), root) if p not in seen and p != os.getpid()]
            if not fresh:
                stable = True
                break
            for pid in fresh:
                seen.add(pid)
                try:
                    kill(pid, signal.SIGSTOP)
                    stopped.append(pid)
                except ProcessLookupError:
                    pass
    finally:
        # 얼린 것은 어떤 경우에도 끝낸다(얼린 채 남기지 않는다). SIGKILL 이 아니면 신호가 닿도록 다시 깨운다.
        for pid in stopped:
            try:
                kill(pid, sig)
            except ProcessLookupError:
                pass
        if sig != signal.SIGKILL:
            for pid in stopped:
                try:
                    kill(pid, signal.SIGCONT)
                except ProcessLookupError:
                    pass
    if not stable:
        raise ProcError("PROC_TREE_UNSTABLE", f"{FREEZE_ROUNDS}번 읽는 동안 새 자손이 계속 나왔다 — 얼린 {len(stopped)}개는 끝냈다", pids=stopped)
    return stopped


def kill_tree(pid, *, sig=None, env=None, run_cmd=None, table=None, kill=None):
    """pid 와 그 자손을 나무째 끝낸다. @return 끝내려고 신호를 보낸 pid 목록(윈도우 taskkill /T 가 한 번에 끝냈으면 [pid]).
    pid 가 정수가 아니거나 1 이하이거나 이 프로세스이면 PROC_TREE_PID_INVALID. run_cmd·table·kill 은 시험 주입 자리."""
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1 or pid == os.getpid():
        raise ProcError("PROC_TREE_PID_INVALID", f"자손 나무의 뿌리 pid 가 올바르지 않다: {pid!r} (정수 · 2 이상 · 이 프로세스가 아님)")
    if on_windows():
        env = os.environ if env is None else env
        run_cmd = run_cmd or _run_tool
        return _kill_windows_tree(pid, env, run_cmd, table or (lambda: _windows_table(env, run_cmd)))
    return _freeze_kill(pid, signal.SIGKILL if sig is None else sig, table or _posix_table, kill or os.kill)
