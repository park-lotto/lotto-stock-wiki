#!/usr/bin/env python3
"""플로우 쪽(파이썬) agy 호출 **한 자리** — make_subs_ai(자막 끊기) · agy_review(검수)가 이것만 부른다 (2026-09-25 B6-P · C9 · K13-b · K14).

agy-provider.md 3-1~3-3 호출 계약의 파이썬 판(JS 는 tools/lib/agy.mjs — 코드 표·도구 머리말·신호는 ref/agy_codes.json 한 파일을 같이 읽는다):
  · 모양: <agy> [--add-dir D]… --input-format stream-json --output-format stream-json --model <M> --print-timeout <T>s --log-file <임시>/agy.log
          [--json-schema <임시>/schema-<sha16>.json] -p ""   · 표준입력 한 줄 {"event":"user","message":{"role":"user","content":…}}
    프롬프트를 명령줄에 싣지 않는다 — 윈도우 CreateProcess 명령줄 한도 32,767자(P9d: 표준입력 48,099자 통과 실측).
  · 최소 환경(K6 · pc_env.agy_child_env) · 윈도우 창 없음·제한시간 나무 종료(flow/proc.py · K13-b) · 셸 권한(--dangerously-skip-permissions) 절대 없음(전역 규칙 6-1).
  · 로그인 풀림: 로그 파일에 코드 표 signals.authLog 줄이 보이면 **몇 초 안에** 나무째 끝내고 AGY_NOT_SIGNED_IN(win-01: 60초 OAuth 대기를 기다리지 않는다).
  · 시간 초과는 예외가 아니라 코드(AGY_TIMEOUT) — `--print-timeout` 초과는 종료 0·빈 답·stderr 한 줄(P10), 강제 종료는 제한+30초.
  · 스키마 호출의 정본 = structured_output(P3). 없는 완료 응답의 response 는 전체가 같은 스키마를 엄격히 만족할 때만 로컬 복원한다(toolAction·toolSummary 같은 여분 속성은 거부). text = JSON 문자열.
  · 로그 파일은 사실(판·모델 라벨)만 뽑고 임시 폴더째 지운다 — 로그에 계정 이메일이 찍힌다(P1).
  · 기계 전체 동시 16(K14 · 전역 규칙 6-1): <slotsDir>/slot-<0..15>.lock — tools/lib/production_lock.mjs acquireFileLock 과 같은 규약
    (O_EXCL 로 만든 JSON {version:1, token, pid, host, boot, at, owner} · 주인 pid 가 죽었거나 부팅이 바뀌었으면 rename 으로 회수) → JS agy.mjs 와 같은 칸을 나눠 쓴다.
    이 프로세스 안에서도 같은 칸을 지난다(스레드마다 다른 파일). 칸을 기다린 시간은 결과 waitedSlotS 에 싣는다(K14 「기다린 시간을 적는다」).
  · 어느 agy 인가(K8 · 2026-09-26 수정 1회차): 이 편의 글 공급자 결정(text_provider.json)이 있으면 그 agy.bin **하나만** — 사라졌으면 AGY_NOT_INSTALLED 이고
    다른 후보로 넘어가지 않는다(JS 이어 하기와 같은 규칙). 결정이 없을 때만 찾기(pc_env.agy_exe). 한 호출(재시도·/usage 다시 보기)은 한 agy 로 끝난다.
  · 다시 부르기: tries(부르는 쪽 값) 안에서 코드 표 retry=true 인 코드만 · 간격 2초×회차(agy-provider.md 3-3 · vox/agy.py 와 같은 값 — **공식 숫자 없음**).
시험: tests/agy_client_test.py(가짜 agy tests/fixtures/pc_env/fake_agy.py — 머리 400자에 info3d-fake-agy 표식 · 진짜 agy 호출 0).
"""
import hashlib, json, os, re, socket, sys, tempfile, threading, time, uuid
from contextlib import contextmanager

HERE = os.path.dirname(os.path.abspath(__file__))
import agy_transport_proc as proc      # noqa: E402  자식 실행 한 자리(flow/proc.py)
import agy_transport_refusal as RUN_REFUSAL
import agy_transport_pc_env as PC   # noqa: E402  agy 찾기·최소 환경·코드 표(한 자리)

STDERR_KEEP = 2000
LOCAL_POLL_S = 0.2           # 로그·칸을 다시 보는 이 컴퓨터 안 간격(외부 요청 간격이 아니다)
HARD_KILL_GRACE_S = 30       # --print-timeout 뒤 강제 종료까지(agy-provider.md 3-1 「프로세스 강제 종료는 그 +30초」)
#: 결과 사건(result) 한 줄이 stdout 에 줄바꿈까지 다 쓰인 뒤 agy 가 스스로 끝나기를 기다리는 상한(★10-19 서버 신고 #305 · 13명).
#:   agy 1.4.0 은 답을 다 쓴 뒤에도 프로세스가 서 있는 일이 있다(longformmovie 10-16 G1 실측: «Stream goroutine exited … sending completion
#:   signal» 뒤 텔레메트리 전송 실패 줄을 찍고 4~5분). 옛 통로는 «프로세스가 끝나기»만 기다려 받은 답을 AGY_TIMEOUT 으로 버렸다.
#:   이 컴퓨터 안 정책이다(외부 서비스 숫자 아님 · agy 공식 문서에 종료 지연 숫자 없음) — longformmovie agy_client.RESULT_EXIT_GRACE_S 와 같은 값.
RESULT_EXIT_GRACE_S = 5.0
BOOT_SLACK_S = 5             # 부팅 시각 비교 여유 — tools/lib/production_lock.mjs BOOT_SLACK_SECONDS 와 같은 자
RETRY_STEP_S = 2             # 다시 부르기 간격 = 2초×회차(agy-provider.md 3-3 · vox/agy.py — 공식 숫자 없음)


class AgyError(Exception):
    def __init__(self, code, message, **detail):
        super().__init__(message)
        self.code, self.detail = code, detail


def table():
    return PC.load_codes()


def retryable(code):
    return bool(((table().get("codes") or {}).get(code) or {}).get("retry"))


# ── 기계 전체 칸(K14) ───────────────────────────────────────────────────
_test_slots = []


def slots_dir(env=None):
    """칸 자리 — env(코드 표 slotsDirEnv) → 코드 표 slotsDir(~/.volcano/info3d/agy.slots · JS agy.mjs 와 같은 자리).
    시험 중(NODE_TEST_CONTEXT)에 재정의가 없으면 이 프로세스 전용 임시 자리 — 시험이 진짜 칸(다른 제작이 쓰는 줄)에 끼어들지 않게."""
    env = PC.env_of(env)
    t = table()
    over = (env.get(t.get("slotsDirEnv") or "INFO3D_AGY_SLOTS_DIR") or "").strip()
    if over:
        return over
    if PC.test_context(env):
        if not _test_slots:
            _test_slots.append(tempfile.mkdtemp(prefix="info3d-agy-slots-test-"))
        return _test_slots[0]
    return os.path.expanduser(t.get("slotsDir") or "~/.volcano/info3d/agy.slots")


def max_parallel():
    return int(table().get("maxParallel") or 16)


def boot_epoch():
    """부팅 시각(초, 반올림) — 노드 os.uptime() 과 같은 자(production_lock bootEpoch = round(now − uptime))."""
    return round(time.time() - _uptime())


def _uptime():
    if sys.platform == "darwin":
        import ctypes, ctypes.util
        libc = ctypes.CDLL(ctypes.util.find_library("c"))

        class TimeVal(ctypes.Structure):
            _fields_ = [("tv_sec", ctypes.c_long), ("tv_usec", ctypes.c_int32)]
        tv, size = TimeVal(), ctypes.c_size_t(ctypes.sizeof(TimeVal))
        if libc.sysctlbyname(b"kern.boottime", ctypes.byref(tv), ctypes.byref(size), None, 0) != 0:
            raise OSError("sysctl kern.boottime 실패")
        return time.time() - (tv.tv_sec + tv.tv_usec / 1e6)
    if os.name == "nt":
        import ctypes
        ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
        return ctypes.windll.kernel32.GetTickCount64() / 1000.0
    with open("/proc/uptime", encoding="ascii") as f:
        return float(f.read().split()[0])


def pid_alive(pid):
    """살아 있는지. 확인할 수 없으면 True(빼앗지 않는다 — production_lock 「확인할 수 없으면 존재한다로 본다」)."""
    if not isinstance(pid, int) or pid <= 1:
        return False
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        handle = k32.OpenProcess(0x1000, False, pid)            # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.GetLastError() == 5                     # ERROR_ACCESS_DENIED = 있다(남의 것) · 그 밖(87 등) = 없다
        try:
            code = ctypes.c_ulong()
            if not k32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259                              # STILL_ACTIVE
        finally:
            k32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def _owner_present(saved):
    if not isinstance(saved, dict):
        return True                                               # 판단할 수 없는 내용 — 빼앗지 않는다(그 칸은 건너뛴다)
    if saved.get("version") != 1:
        return pid_alive(saved.get("pid")) if isinstance(saved.get("pid"), int) else True
    if not isinstance(saved.get("pid"), int) or saved.get("host") != socket.gethostname():
        return True
    if isinstance(saved.get("boot"), int):
        try:
            if abs(saved["boot"] - boot_epoch()) > BOOT_SLACK_S:
                return False
        except OSError:
            pass
    return pid_alive(saved["pid"])


def _slot_file(path, *, create=False):
    """Share-delete readers and an owned delete-on-close Windows slot lease.

    Microsoft CreateFileW FILE_FLAG_DELETE_ON_CLOSE explicitly requires every
    subsequent opener to share delete. Old readers cannot pin a new lease;
    their existing unknown-owner behavior correctly treats it as occupied.
    https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
    """
    if os.name != "nt":
        return open(path, "x" if create else "r", encoding="utf-8")
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    call = kernel.CreateFileW
    call.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                     wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    call.restype = wintypes.HANDLE
    path = os.path.abspath(path)
    if not path.startswith("\\\\?\\"):
        path = "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path
    # GENERIC_WRITE | DELETE, CREATE_NEW, DELETE_ON_CLOSE; readers need only READ.
    handle = call(path, 0x40010000 if create else 0x80000000, 3 if create else 7, None,
                  1 if create else 3, 0x04000080 if create else 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        fd = msvcrt.open_osfhandle(handle, (os.O_WRONLY if create else os.O_RDONLY) | os.O_BINARY)
    except BaseException:
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        kernel.CloseHandle(handle)
        raise
    try:
        return os.fdopen(fd, "w" if create else "r", encoding="utf-8")
    except BaseException:
        os.close(fd)
        raise


def _read(path):
    try:
        with _slot_file(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _try_slot_unlocked(path, body):
    """칸 하나를 O_EXCL 로 만든다. 성공 True · 남이 쥠 False. 죽은 주인의 칸은 rename 으로 회수하고 한 번 더."""
    for attempt in range(3):
        try:
            lease = _slot_file(path, create=True)
        except FileExistsError:
            saved = _read(path)
            if saved is None:
                return False                                      # 쓰는 중이거나 잔재 — 다음 칸을 본다(잔재 정리는 JS production_lock 규약 쪽이 한다)
            if _owner_present(saved):
                return False
            try:
                aside = f"{path}.stale.{uuid.uuid4()}"
                os.replace(path, aside)
                os.remove(aside)
            except FileNotFoundError:
                pass
            except OSError as error:
                if getattr(error, "winerror", None) in (5, 32, 303):
                    return False  # A live/delete-pending kernel lease cannot be reclaimed.
                raise
            continue
        except OSError as error:
            # A share-delete reader can keep an already released lease pending
            # removal. Windows reports access/sharing/delete-pending here, not
            # necessarily FILE_EXISTS. Only a confirmed existing regular slot
            # is occupied; real directory/ACL failures are still surfaced.
            if getattr(error, "winerror", None) in (5, 32, 303):
                import stat
                try:occupied = stat.S_ISREG(os.stat(path).st_mode)
                except FileNotFoundError:
                    # The observed delete-pending owner may close between
                    # CREATE_NEW and stat. Recheck via CREATE_NEW, never assume
                    # capacity or hide a persistent ACL error.
                    if attempt < 2:continue
                    raise error
                except OSError:occupied = False
                if occupied:return False
            raise
        try:
            if lease.write(body) != len(body):raise OSError("Incomplete AGY slot identity")
            lease.flush()
        except BaseException as failure:
            try:
                if os.name != "nt":
                    # Only our just-created slot inode; no provider was called.
                    try:
                        if os.path.samestat(os.fstat(lease.fileno()), os.stat(path)):
                            os.unlink(path)
                    except FileNotFoundError:
                        pass
            except OSError as cleanup:
                if hasattr(failure, "add_note"):
                    failure.add_note("AGY slot cleanup failed: " + str(cleanup))
            finally:
                lease.close()
            raise
        if os.name == "nt":return lease
        lease.close()
        return True
    return False


class _PosixSlotLease:
    def __init__(self, guard, path, token):
        self.guard, self.path, self.token = guard, path, token
    def close(self):
        if self.guard is None:
            return
        guard, self.guard = self.guard, None
        try:
            saved = _read(self.path)
            if isinstance(saved, dict) and saved.get("token") == self.token:
                try:os.unlink(self.path)
                except FileNotFoundError:pass
        finally:
            guard.close()


def _try_slot(path, body):
    if os.name == "nt":
        return _try_slot_unlocked(path, body)
    import fcntl
    # Permanent inode: unlinking the guard would split flock ownership. The
    # kernel releases it on process death. Both updated adapters use this guard.
    guard = open(str(path) + ".guard", "a+b")
    try:
        try:
            fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            guard.close()
            return False
        if not _try_slot_unlocked(path, body):
            guard.close()
            return False
        return _PosixSlotLease(guard, path, json.loads(body)["token"])
    except BaseException:
        guard.close()
        raise


@contextmanager
def agy_slot(env=None, owner=None, cancel=None):
    """기계 전체 agy 칸 하나(16). 돌려주는 값: {'slot': i, 'waitedS': 초}. cancel() 이 참이면 기다리기를 멈추고 AgyError(AGY_TIMEOUT)."""
    folder = slots_dir(env)
    os.makedirs(folder, exist_ok=True)
    token = str(uuid.uuid4())
    try:
        boot = boot_epoch()
    except OSError:
        boot = None
    body = json.dumps({"version": 1, "token": token, "pid": os.getpid(), "host": socket.gethostname(), "boot": boot,
                       "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "owner": dict(owner or {}, tool="flow/agy_client.py")})
    t0, held = time.monotonic(), None
    while held is None:
        for i in range(max_parallel()):
            path = os.path.join(folder, f"slot-{i}.lock")
            lease = _try_slot(path, body)
            if lease:
                held = (i, path, lease)
                break
        if held is None:
            if cancel and cancel():
                raise AgyError("AGY_TIMEOUT", f"agy 칸({folder})을 기다리다 제한 시간이 지났다")
            time.sleep(LOCAL_POLL_S)
    state = {"slot": held[0], "waitedS": round(time.monotonic() - t0, 3)}
    try:
        yield state
    finally:
        try:
            if hasattr(held[2], "close"):
                # Close the exact file object we created, never another owner's pathname.
                held[2].close()
            else:
                saved = _read(held[1])
                if isinstance(saved, dict) and saved.get("token") == token:
                    try:os.remove(held[1])
                    except FileNotFoundError:pass
        except OSError as error:
            # A known model answer must survive a cleanup failure. The uncleared
            # slot remains occupied; do not free someone else's slot or resend.
            state["release_error"] = {"type":type(error).__name__,"errno":error.errno,
                                      "winerror":getattr(error,"winerror",None),"message":str(error)}


# ── 응답 해석 ───────────────────────────────────────────────────────────
def schema_problems(value, schema, path="$"):
    """스키마 부분집합 검사(type — 이름 하나 또는 이름 목록 · required·properties·additionalProperties:false·items·minItems·maxItems·enum)
    — vox/agy.py schema_problems 와 같은 범위. null 을 받는 칸은 JSON Schema 표준 합집합 {"type": [T, "null"]} 로 적는다:
    agy 의 finish 도구 검사기는 OpenAPI 의 `nullable` 을 모른다(1.4.4 실측 2026-10-22 «got null, want array» — 답이 거부되면 모델이
    다시 답해야 턴이 끝난다 · subject_focus.FOCUS_ANSWER_SCHEMA 주석). 그래서 `nullable` 은 여기서도 받지 않는다 — agy 가 거부하는 답을
    우리만 통과시키지 않는다(두 검사기가 같은 말을 한다)."""
    out = []
    if not isinstance(schema, dict):
        return out
    kinds = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
    def fits(want):
        if want == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if want == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        return isinstance(value, kinds[want]) if want in kinds else True
    want = schema.get("type")
    ok = any(fits(w) for w in want) if isinstance(want, list) else fits(want)
    if not ok:
        return [f"{path}: {want} 가 아니다"]
    if "enum" in schema and value not in schema["enum"]:
        out.append(f"{path}: 허용 값이 아니다")
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        out += [f"{path}.{k}: 빠짐" for k in schema.get("required") or [] if k not in value]
        if isinstance(schema.get("properties"), dict) or schema.get("additionalProperties") is False:
            out += [f"{path}.{k}: 스키마에 없는 키" for k in value if k not in props]
        for k, v in value.items():
            if k in props:
                out += schema_problems(v, props[k], f"{path}.{k}")
    if isinstance(value, list):
        if isinstance(schema.get("minItems"), int) and len(value) < schema["minItems"]:
            out.append(f"{path}: 항목 {len(value)} < {schema['minItems']}")
        if isinstance(schema.get("maxItems"), int) and len(value) > schema["maxItems"]:
            out.append(f"{path}: 항목 {len(value)} > {schema['maxItems']}")
        for i, v in enumerate(value):
            out += schema_problems(v, schema.get("items"), f"{path}[{i}]")
    return out


def parse_stream(stdout):
    """stream-json 사건 줄들 → (init, result, 도구 사건 목록). 모양(실측 P6·P8b): {"event":"init","init":{model,…}} ·
    {"event":"step_update","step_update":{step_type,tool_name,tool_info…}} · {"event":"result","result":{status,response,structured_output,denied_actions,…}}."""
    init, result, tools = None, None, []
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        kind = ev.get("event")
        if kind == "init" and isinstance(ev.get("init"), dict):
            init = ev["init"]
        elif kind == "result" and isinstance(ev.get("result"), dict):
            result = ev["result"]
        elif kind == "step_update" and isinstance(ev.get("step_update"), dict):
            step = ev["step_update"]
            # DONE(성공)과 ERROR(거부·실패 — error 칸이 있다) 둘 다 남긴다. ERROR 기록은 «무엇을 시도했다 거부됐나» 의 증거다
            #   (agy 1.4.4 실측 10-22: 요청 밖 파일 read_file 거부는 state ERROR · parameters.Path · error.message «permission check failed»).
            #   «열었다» 판정(opened_exactly)은 error 있는 기록을 세지 않는다.
            if step.get("step_type") == "tool" and step.get("state") in ("DONE", "ERROR"):
                info = step.get("tool_info") or {}
                tools.append({"name": step.get("tool_name"), "parameters": info.get("parameters"), "error": info.get("error")})
    return init, result, tools


# ── 도구 기록 → «무엇을 열었나» (판정 한 자리) ─────────────────────────────────
#: 파일 읽기 도구 이름 → 경로 칸 이름. 모델의 말이 아니라 이 도구 기록이 «원본을 직접 열었다» 의 증거다.
#:   · 옛 판: view_file {"AbsolutePath": …}
#:   · 2026-10-18~20 부터: read_file {"Path": …} — view_file 은 모델에게 없다(«view_file 을 불러라» 하면 «view_file 도구는 존재하지
#:     않습니다» · 수강생 신고: 1.4.2(10-18 갱신)·1.4.3(10-20 13:41 무렵 갱신) 둘 다). 판 번호가 아니라 도구 기록의 이름·칸으로 가른다.
#:     성공은 state DONE·error 없음, 실패는 state ERROR·error{type,message}.
#:     영상(화면+소리)·그림 판독 답은 그대로 맞다. 근거: 이 맥 agy 1.4.3 실측 2026-10-20(stream-json step_update.tool_info ·
#:     flash-low/medium/high·argon-medium 넷 다 같음 · tests/fixtures/agy_tools_1_4_3_*.jsonl). init.tools 목록은 1.4.3 에서도 view_file 을
#:     적으므로 목록이 아니라 실제 도구 기록을 본다. CLI 내장 공식 변경 기록(`agy changelog` 1.4.3)에는 이 변경이 적혀 있지 않다.
#:   대화 기록 DB(미국경찰 실행기 runner_script)도 같은 이름·칸을 쓴다 — 그쪽은 서버가 이 표를 본문에 실어 보낸다(사본을 손으로 적지 않는다).
FILE_READ_TOOLS = {"view_file": "AbsolutePath", "read_file": "Path"}


def forbidden_tool_only(denied, tools=None, paths=()):
    """denied_actions 가 전부 «그 요청에서 모델이 우리가 시키지 않은 일을 시도한 것» 인가 — 그 요청 하나의 실패(서비스 거부 아님).

    실측 모양 ①(agy 1.4.3 · 맥미니24g 2026-10-21 · tests/fixtures/agy_denied_command_1_4_3.jsonl): 모델이 RunCommand 를 시도하면
    result.status SUCCESS · response "" · denied_actions [{"action": "command", "display_name": "RunCommand"}] ·
    stderr «a tool required the "command" permission that headless mode cannot prompt for».
    실측 모양 ②(agy 1.4.4 · 맥미니24g 2026-10-22 · tests/fixtures/agy_denied_read_outside_1_4_4.jsonl): 모델이 **요청 밖 파일**을
    read_file 로 열려 하면 denied_actions [{"action": "read_file", "display_name": "ReadFile"}] · 그 시도는 도구 기록에 state ERROR ·
    parameters.Path(그 밖의 파일) · error «permission check failed». 모델이 헤맨 모양이다(쇼핑 한 패스 ls·
    영화 롱폼 ls 와 같은 뿌리) — 우리 설정 문제가 아니고, 다른 요청은 그 사실과 무관하다.
    그래서 파일 읽기 거부는 **증거로** 가른다: 거부된 읽기 기록(error 있는 read_file·view_file)이 있고 그 경로가 전부 요청한 파일
    (paths) 밖일 때만 이 요청 하나의 실패다. 요청한 파일 자체의 읽기가 거부됐거나(허락 폴더·경로 문제 — 모든 요청에 같다 · 10-15
    \\\\?\\ 경로 사건) 거부된 읽기 기록을 못 찾으면(모양 모름) False — 지금처럼 이 실행을 멈춘다."""
    if not isinstance(denied, list) or not denied:
        return False
    required = {same_file_key(p) for p in paths or ()}
    tried = []                                   # 거부·실패한 파일 읽기 시도의 경로(한 번 훑기)
    for tool in tools or []:
        if isinstance(tool, dict) and tool.get("error") and tool.get("name") in FILE_READ_TOOLS:
            tried.append(read_path(tool))
    for entry in denied:
        name = entry.get("action") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            return False
        if name in FILE_READ_TOOLS:
            if not tried or any(p is None or same_file_key(p) in required for p in tried):
                return False
    return True


def read_path(tool):
    """도구 기록 한 줄이 파일 읽기면 그 경로 글자, 아니면 None(실패 여부는 보지 않는다 — 부르는 쪽 opened_exactly 가 본다)."""
    if not isinstance(tool, dict):
        return None
    field = FILE_READ_TOOLS.get(tool.get("name"))
    params = tool.get("parameters")
    if field is None or not isinstance(params, dict):
        return None
    path = params.get(field)
    return path if isinstance(path, str) and path else None


def same_file_key(path):
    """대조 글자 — agy 가 받은 긴 경로 머리 없는 글자(plain_path)를 realpath·normcase 로."""
    return os.path.normcase(os.path.realpath(plain_path(path)))


def opened_exactly(tools, paths, *, allowed=()):
    """도구 기록으로 «paths 를 전부 성공적으로 열었고, 그 밖의 파일·도구가 성공한 기록이 없다» 를 판정한다.

    돌려줌 (사유, 쓴 allowed 이름 집합) — 사유 None 이면 인정. 사유 낱말:
      shape(모양 모르는 기록) · other_tool(파일 읽기도 allowed 도 아닌 도구가 성공) · path_missing(읽기 도구인데 경로 칸이 없다) ·
      outside(요청 밖 파일을 성공적으로 열었다) · missing(요청 파일 중 성공적으로 연 기록이 없는 것이 있다).
    실패·거부된 시도(error 가 있는 기록)는 아무것도 읽지 못했으므로 세지 않는다(10-06 subject_agy_run 결정 — 권한 거부된 시도 하나로
    멀쩡한 답을 버렸다). 한 번 훑기(경로 집합 대조) — 기록 수에 비례한다.
    """
    required = {same_file_key(p) for p in paths}
    seen, used = set(), set()
    for tool in tools or []:
        if not isinstance(tool, dict):
            return "shape", used
        if tool.get("error"):
            continue
        name = tool.get("name")
        if name in allowed:
            used.add(name)
            continue
        path = read_path(tool)
        if path is None:
            return ("path_missing" if name in FILE_READ_TOOLS else "other_tool"), used
        actual = same_file_key(path)
        if actual not in required:
            return "outside", used
        seen.add(actual)
    return (None if seen == required else "missing"), used


class ResultWatch:
    """agy stdout 파일을 **늘어난 만큼만** 읽어 결과 사건(event=result) 한 줄이 줄바꿈까지 다 쓰였는지 본다(longformmovie
    agy_client.ResultWatch 와 같은 계약). 감시 간격마다 파일 전체를 다시 읽지 않는다(전역 6-00 ④). 줄바꿈 없는 끝 조각은 쓰는 중인
    줄이라 결과로 보지 않고 다음 읽기 앞에 붙인다."""

    def __init__(self, path):
        self.path, self.pos, self.tail, self.done = path, 0, b"", False

    def poll(self):
        if self.done:
            return True
        try:
            with open(self.path, "rb") as f:
                f.seek(self.pos)
                new = f.read()
        except FileNotFoundError:
            return False
        if not new:
            return False
        self.pos += len(new)
        lines = (self.tail + new).split(b"\n")
        self.tail = lines.pop()
        for raw in lines:
            if b'"result"' not in raw:
                continue
            try:
                ev = json.loads(raw.decode("utf-8", errors="replace").strip())
            except ValueError:
                continue
            if isinstance(ev, dict) and ev.get("event") == "result" and isinstance(ev.get("result"), dict):
                self.done = True
                return True
        return False


class LogWatch:
    """agy --log-file 을 **늘어난 만큼만** 읽어 찾는 글(signals.authLog — 로그인 요구)이 나왔는지 본다(longformmovie agy_client.LogWatch 와
    같은 방식 · 옛 판은 0.2초마다 로그 전체를 다시 읽었다 — 전역 6-00 ④). 찾는 글은 한 줄 안에 있다 — 줄바꿈 없는 끝 조각을 다음 읽기 앞에
    붙여 다시 본다. 로그가 아직 없는 것(ENOENT)만 «아직»이고, 그 밖의 읽기 오류는 **올린다**(PC.read_log 와 같은 규칙 — 부르는 쪽이 코드를 남긴다)."""

    def __init__(self, path, needles):
        self.path, self.needles = path, tuple(n.encode("utf-8") for n in needles if n)
        self.pos, self.tail = 0, b""

    def poll(self):
        try:
            with open(self.path, "rb") as f:
                f.seek(self.pos)
                new = f.read()
        except FileNotFoundError:
            return False
        if not new:
            return False
        self.pos += len(new)
        seen = self.tail + new
        self.tail = seen.rpartition(b"\n")[2]
        return any(n in seen for n in self.needles)


def log_facts(log_text):
    """로그에서 판·모델 라벨만(계정 이메일은 가져오지 않는다)."""
    facts, marks = {}, (table().get("signals") or {}).get("logFacts") or {}
    for line in (log_text or "").splitlines():
        for key in ("version", "label"):
            mark = marks.get(key)
            if mark and mark in line and key not in facts:
                facts[key] = line.split(mark, 1)[1].strip().strip('"').split('"')[0][:60]
    return facts


def interpret(returncode, stdout, stderr, *, model, schema=None, auth_failed=False, killed=False, closed_after_result=False):
    """관측 → (code|None, 결과 dict). agy-provider.md 3-3 표를 그대로 옮긴 순수 함수(시험 대상).
    closed_after_result = 결과 사건 한 줄이 다 쓰인 뒤 스스로 끝나지 않아 우리가 끝낸 것(★10-19 #305) — 그때의 0 아닌 종료 코드는 우리가
    끝낸 흔적이지 agy 의 실패가 아니다. 답은 그 결과 사건으로만 가른다(SUCCESS·모델·스키마·거부 규칙은 그대로)."""
    sig = table().get("signals") or {}
    err = stderr or ""
    init, result, tools = parse_stream(stdout)
    base = {"text": "", "json": None, "denied": (result or {}).get("denied_actions") or [], "tools": tools, "error": (result or {}).get("error"), "model": (init or {}).get("model"), "status": (result or {}).get("status")}
    if result and result.get("status") == "ERROR":
        # Keep the terminal provider evidence before the error branches return.
        # Partial output is diagnostic-only: text/json stay empty, and the media
        # bridge still requires SUCCESS, exit 0 and complete tool/identity proof.
        # provider_evidence scrubs this nested data before persisting the receipt.
        base["failure_diagnostics"] = {
            key: result[key] for key in
            ("response", "structured_output", "usage", "num_turns", "duration_seconds")
            if key in result
        }
    if auth_failed:
        return "AGY_NOT_SIGNED_IN", dict(base, message="agy 가 로그인을 요구했다(로그 감시) — 브라우저 로그인을 기다리지 않고 멈췄다")
    if any(x in err for x in sig.get("invocationInvalid") or []) or returncode == 2:
        return "AGY_INVOCATION_INVALID", dict(base, message=err[-300:] or f"agy 종료 {returncode}")
    if killed and not closed_after_result:
        return "AGY_TIMEOUT", dict(base, message="agy 가 제한 시간 + 30초 안에 끝나지 않아 나무째 끝냈다")
    if result is None:
        return "AGY_ERROR", dict(base, message=f"agy 가 결과 사건 없이 끝났다(종료 {returncode}): {err[-300:]}")
    if result.get("denied_actions"):
        return "AGY_TOOL_DENIED", dict(base, message="AGY headless denied a tool; preserve this attempt: "
                                       + json.dumps(result.get("denied_actions"), ensure_ascii=False)[:200])
    if returncode != 0 and not closed_after_result:
        return "AGY_ERROR", dict(base, message=f"agy exited {returncode}; response cannot be accepted")
    if result.get("status") == "ERROR":
        said = str(result.get("error") or "")
        if (sig.get("invalidModel") or "invalid model selection") in said:
            return "AGY_MODEL_INVALID", dict(base, message=said[:300])
        return "AGY_ERROR", dict(base, message=said[:300] or "status ERROR")
    if init and init.get("model") and init["model"] != model:
        return "AGY_MODEL_INVALID", dict(base, message=f"요청 모델 {model} 인데 agy 가 {init['model']} 로 시작했다")
    text = str(result.get("response") or "")
    denied = result.get("denied_actions") or []
    structured = result.get("structured_output")
    base.update(denied=denied, usage=result.get("usage"), numTurns=result.get("num_turns"), durationS=result.get("duration_seconds"))
    if (sig.get("printTimeout") or "print timeout after") in err:
        return "AGY_TIMEOUT", dict(base, message=err.strip()[-200:])
    if denied and not text.strip() and structured is None:
        return "AGY_TOOL_DENIED", dict(base, message="agy 가 허락되지 않은 도구를 쓰려다 거부당해 빈 답: " + json.dumps(denied, ensure_ascii=False)[:200])
    if schema is not None:
        if structured is None:
            # A completed CLI result may omit the optional structured_output
            # while its response is one complete schema-valid JSON value.
            # Validate it locally instead of spending another subscription call.
            if ("structured_output" not in result and result.get("status") == "SUCCESS"
                    and returncode == 0 and not denied and not result.get("error")
                    and (init or {}).get("model") == model and text.strip()):
                invalid_json = object()
                try:
                    parsed = json.loads(text)
                except (ValueError, TypeError):
                    parsed = invalid_json
                if parsed is not invalid_json and not schema_problems(parsed, schema):
                    return None, dict(base, text=json.dumps(parsed, ensure_ascii=False), json=parsed,
                                      recoveredFrom="response", message="")
            return "AGY_SCHEMA_MISSING", dict(base, text=text, message="스키마를 준 호출인데 structured_output 이 없다")
        problems = schema_problems(structured, schema)
        if problems:
            return "AGY_SCHEMA_MISMATCH", dict(base, text=json.dumps(structured, ensure_ascii=False), message="; ".join(problems[:5]))
        return None, dict(base, text=json.dumps(structured, ensure_ascii=False), json=structured, message="")
    if not text.strip():
        return "AGY_EMPTY", dict(base, message="agy 가 SUCCESS 로 빈 답을 냈다")
    return None, dict(base, text=text, message="")


# ── 부르기 ─────────────────────────────────────────────────────────────
def plain_path(path):
    """agy 에 넘기는 로컬 경로 — 절대경로 · 윈도우 긴 경로 머리(`\\\\?\\` · `\\\\?\\UNC\\`)를 뗀 평범한 글자.

    ■ 왜(2026-10-15 수강생 쇼핑 04편) — 실행기는 윈도우 긴 경로를 위해 `\\\\?\\C:\\…` 로 파일을 연다. 그 글자가
      `--add-dir`·안내문·작업 폴더로 그대로 agy 에 가면 agy 는 허락된 폴더(`C:\\…`)와 다른 경로로 보고
      화면 없는 모드에서 read_file 을 자동 거부했다(«a tool required the read_file permission that headless
      mode cannot prompt for»). agy 에 넘기는 모든 경로는 이 한 자리를 지난다. 파이썬 쪽 읽기·해시는 긴 경로 그대로 둔다.
    """
    text = os.path.abspath(os.fspath(path))
    if os.name == "nt":
        if text.startswith("\\\\?\\UNC\\"):
            text = "\\\\" + text[8:]
        elif text.startswith("\\\\?\\"):
            text = text[4:]
    return text


def preface(kind, files=()):
    p = table().get("prefaces") or {}
    if kind == "view":
        return p.get("view", "").replace("{files}", ", ".join(json.dumps(plain_path(f), ensure_ascii=False) for f in files))
    return p.get(kind, "") if kind else ""


def _once(prompt, *, path, kind, files, add_dirs, schema, model, timeout_s, cwd, env, owner):
    env = PC.env_of(env)
    work = tempfile.mkdtemp(prefix="info3d-agy-")
    log = os.path.join(work, "agy.log")
    out_path, err_path = os.path.join(work, "stdout.jsonl"), os.path.join(work, "stderr.txt")
    args = []
    for d in dict.fromkeys(plain_path(x) for x in list(add_dirs) + [os.path.dirname(plain_path(f)) for f in files]):
        args += ["--add-dir", d]
    args += ["--input-format", "stream-json", "--output-format", "stream-json", "--model", model,
             "--print-timeout", f"{int(max(1, timeout_s))}s", "--log-file", log]
    if schema is not None:
        body = json.dumps(schema, ensure_ascii=False, sort_keys=True)
        schema_file = os.path.join(work, f"schema-{hashlib.sha256(body.encode()).hexdigest()[:16]}.json")
        with open(schema_file, "w", encoding="utf-8") as f:
            f.write(body)
        args += ["--json-schema", schema_file]
    args += ["-p", ""]
    head = preface(kind, files)
    content = (head + "\n\n" + prompt) if head else prompt
    line = json.dumps({"event": "user", "message": {"role": "user", "content": content}}, ensure_ascii=False) + "\n"
    auth = (table().get("signals") or {}).get("authLog") or []
    started = time.monotonic()
    deadline = started + timeout_s + HARD_KILL_GRACE_S
    def cancelled():
        RUN_REFUSAL.assert_allowed(env)
        return time.monotonic() > deadline
    try:
        with agy_slot(env, owner, cancel=cancelled) as slot:
            RUN_REFUSAL.assert_allowed(env)
            t_run = time.monotonic()
            with open(out_path, "wb") as fo, open(err_path, "wb") as fe:
                RUN_REFUSAL.assert_allowed(env)
                child = proc.Popen(PC.agy_argv(path) + args, stdin=proc.PIPE, stdout=fo, stderr=fe, cwd=plain_path(cwd) if cwd else work,
                                   env=PC.agy_child_env(env))
                try:
                    child.stdin.write(line.encode("utf-8"))
                    child.stdin.close()
                except (BrokenPipeError, OSError):
                    pass
                auth_failed = killed = closed_after_result = False
                watch_error = None                        # 감시 중 ENOENT 밖의 읽기 오류(errno 이름) — JS agy.mjs logWatchError 와 같은 칸
                result_watch = ResultWatch(out_path)      # 결과 사건 한 줄이 다 쓰였나(늘어난 만큼만 · ★10-19 #305)
                log_watch = LogWatch(log, auth)           # 로그인 요구 줄(늘어난 만큼만)
                t_result = None                           # 결과 사건을 본 시각 — 그 뒤 RESULT_EXIT_GRACE_S 안에 스스로 끝나기를 기다린다
                while child.poll() is None:
                    try:
                        RUN_REFUSAL.assert_allowed(env)
                    except RUN_REFUSAL.RunServiceRefused:
                        proc.kill_tree(child.pid)
                        child.wait()
                        raise
                    time.sleep(LOCAL_POLL_S)
                    if watch_error is None:
                        # 로그가 아직 없는 것(ENOENT)만 「아직」이다. 다른 읽기 오류는 감시를 멈추고 그 코드를 결과에 남긴다(2026-09-26 §7-추가 7 ② —
                        # 옛 판은 `except OSError: pass` 로 버렸다). 이른 로그인 판정만 잃고, 끝난 뒤 로그 읽기가 같은 오류면 그 자리에서 올린다.
                        try:
                            if log_watch.poll():
                                auth_failed = True
                        except OSError as e:
                            watch_error = PC.error_code(e)
                    if t_result is None and result_watch.poll():
                        t_result = time.monotonic()
                    lingered = t_result is not None and time.monotonic() > t_result + RESULT_EXIT_GRACE_S
                    if auth_failed or lingered or time.monotonic() > t_run + timeout_s + HARD_KILL_GRACE_S:
                        # 답을 다 쓴 뒤 매달린 것(lingered)은 시간 초과가 아니다 — 끝내고 그 답을 읽는다(interpret 이 결과 사건으로 가른다)
                        killed = not auth_failed and not lingered
                        closed_after_result = lingered or (killed and result_watch.poll())   # 제한 직전에 다 쓰인 답도 버리지 않는다
                        try:
                            proc.kill_tree(child.pid)
                        except Exception as e:                    # 정리 실패는 삼키지 않는다 — 직계만이라도 끝내고 알린다
                            child.kill()
                            child.wait()
                            raise AgyError("AGY_ERROR", f"agy 나무를 끝내지 못했다: {e}") from e
                        child.wait()
                        break
            with open(out_path, encoding="utf-8", errors="replace") as f:
                stdout = f.read()
            with open(err_path, encoding="utf-8", errors="replace") as f:
                stderr = f.read()
            # 끝난 뒤의 로그: 없으면(ENOENT — agy 가 로그를 쓰기 전에 끝남) 사실 없음. 있는데 못 읽으면 **올린다**(AGY_ERROR — JS agy.mjs 와 같은 규칙):
            # 옛 판은 `except OSError: facts = {}` 로 「로그인 안 됨」 사실을 잃은 채 성공 판정을 냈다(2026-09-26 §7-추가 7 ②).
            try:
                facts = log_facts(PC.read_log(log) or "")
            except OSError as e:
                raise AgyError("AGY_ERROR", f"agy 로그를 읽지 못했다({PC.error_code(e)}: {e}) — 로그인 안 됨 줄을 볼 수 없어 판정하지 않는다", logError=PC.error_code(e)) from e
            code, res = interpret(child.returncode, stdout, stderr, model=model, schema=schema, auth_failed=auth_failed, killed=killed,
                                  closed_after_result=closed_after_result)
            res.update(code=code, ok=code is None, cliVersion=facts.get("version"), modelLabel=facts.get("label"),
                       waitedSlotS=slot["waitedS"], slotRelease=slot, seconds=round(time.monotonic() - t_run, 2), stderrTail=stderr[-STDERR_KEEP:],
                       returncode=child.returncode, promptChars=len(content))
            if watch_error:
                res["logWatchError"] = watch_error
            if closed_after_result:
                res["closedAfterResult"] = True           # 답을 다 쓴 뒤 스스로 끝나지 않아 우리가 끝냈다(얼마나 자주인지 남긴다)
            return res
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)                  # 로그(계정 이메일이 찍힌다)는 사실만 뽑고 지운다


def _dns_lookup_failure(result):
    # Observed AGY terminal error: Go's DNS lookup failed before an HTTP response.
    # Match the whole error, not a mention of DNS inside a denial/429 response.
    # This is diagnostic classification only: never accept output or retry it.
    error = result.get("error")
    return (result.get("status") == "ERROR" and result.get("code") == "AGY_ERROR"
            and not result.get("denied") and isinstance(error, str)
            and re.fullmatch(
                r'(?:API error \(attempt [1-9]\d*\): )?'
                r'(?:(?:Get|Post) "https://[^"\r\n]+": )?'
                r'dial tcp: lookup [A-Za-z0-9.-]+: no such host', error) is not None)


_RATE_OR_QUOTA_WORDS = re.compile(
    r"\b429\b|rate[ _-]?limit|resource[ _-]?exhausted|too many requests|quota"
    # agy 자신이 내는 한도·용량 거부 글(2026-10-06 이 맥 ~/.local/bin/agy 실행 파일에서 grep -a 로 확인한 원문 —
    # «Your AI credits balance is too low to continue.» · «Limit of concurrent requests reached (%d), try again later.» ·
    # «MODEL_CAPACITY_EXHAUSTED» · «PREFILL_QUEUE_OVERLOADED»·«Overloaded prefill queue»). 이것도 거부다(전역 규칙 6-2 — 모든 요청 즉시 멈춤).
    # 빠져 있으면 'per_request_evidence' 에서 /usage 확인까지 실패할 때 진짜 한도 소진이 «그 컷의 실패» 로 새어 나가
    # 남은 컷 전부에 요청이 계속 나갔다(10-06 검토 재현: 컷 6개 · AGY 6회 · 거부 표식 없음 ↔ 9fa632ea 1회 · 표식).
    r"|credits balance is too low|capacity[ _-]?exhausted|prefill[ _-]?queue[ _-]?overloaded|overloaded prefill queue"
    r"|limit of concurrent requests", re.I)
_QUOTA_WORDS = re.compile(r"quota|credits balance is too low", re.I)


# Go 네트워크 오류(DNS 밖) — 오류 글 전체가 이 모양일 때만(429·거부 글 안에 섞인 낱말을 잡지 않게 _dns_lookup_failure 와 같은 방식).
# 문구는 Go 표준 라이브러리의 오류 글이고 agy 실행 파일에도 그대로 있다(10-06 grep -a: dial tcp · i/o timeout · connection refused ·
# network is unreachable · no route to host · connection reset by peer · TLS handshake timeout · connectex · wsarecv).
# 윈도우는 connectex·wsarecv·wsasend 뒤에 윈도우 설명 글이 붙는다(학생 대부분이 윈도우).
_NET_ERROR = re.compile(
    r'(?:API error \(attempt [1-9]\d*\): )?'
    r'(?:(?:Get|Post) "https://[^"\r\n]+": )?'
    r'(?:dial tcp(?: \S+)?: (?:i/o timeout'
    r'|connect: (?:connection refused|network is unreachable|no route to host|connection timed out)'
    r'|connectex: [^\r\n]+'
    r'|lookup [A-Za-z0-9.-]+(?: on \S+)?: (?:no such host|i/o timeout|server misbehaving))'
    r'|(?:read|write) tcp \S+: (?:read|write|wsarecv|wsasend): [^\r\n]+'
    r'|net/http: TLS handshake timeout)')


def _network_failure(result):
    """이 PC 의 네트워크가 끊긴 오류인가(DNS 실패는 _dns_lookup_failure 가 따로 가른다) — 거부가 아니고, 그 컷의 실패로 굳히면
    연결을 고친 뒤에도 확대가 영영 빠지므로 환경 문제로 막는다(subject_agy_run._environment_failure · 10-06 검토 major)."""
    error = result.get("error")
    return (result.get("status") == "ERROR" and result.get("code") == "AGY_ERROR"
            and not result.get("denied") and isinstance(error, str)
            and _NET_ERROR.fullmatch(error) is not None)


def refusal_kind(res):
    """거부로 올린 결과 → 거부 종류 한 이름(2026-10-06 · 부르는 쪽이 종류로 가른다 — 롱폼 피사체는 한도·속도·로그인만 멈추지 않는다).
    증거로 가른 이름(refused_as · status ERROR 의 한도·속도·로그인) → 도구 거부(denied · AGY_TOOL_DENIED) → 그 결과의 코드(AGY_QUOTA·
    AGY_MODEL_INVALID 등). 모르면 None."""
    if not isinstance(res, dict):
        return None
    if res.get("refused_as"):
        return str(res["refused_as"])
    if res.get("denied") or res.get("code") == "AGY_TOOL_DENIED":
        return "AGY_TOOL_DENIED"
    return str(res["code"]) if res.get("code") else None


def _status_error_refusal(res, path, env, unknown_refuses=True):
    """status_error='per_request'·'per_request_evidence' 의 판정 — (거부로 볼 이름 또는 None, /usage 요약).

    거부 = 한도·속도·로그인의 증거: ① 오류 글에 속도 제한·한도 낱말 ② 곧바로 잰 /usage 가 한도 소진·로그인 풀림이라고 말함.
    /usage 를 확인하지 못한 것(시간 초과·종료≠0·모양 다름·로그를 못 읽음)은
      unknown_refuses=True('per_request' · 검수 다리 — 10-05 그대로): 거부 쪽(전부 멈춤)으로 간다.
      unknown_refuses=False('per_request_evidence' · 인물형 롱폼 피사체 — 2026-10-06): 증거가 아니다 → None(그 요청 하나의 실패 ·
        거부 표식 없음). 학생 실측: 길어서 끝이 잘린 답(오류 글 «exceeded the output token limit»)이 /usage 확인 실패로 «서비스 거부» 가
        되어 실행 전체가 멈추고 거부 표식이 남았다(최근 24시간 막힌 사람의 provider_refused 10·not_started_after_refusal 5).
        확인 못 한 사실(known False · why)은 요약에 남는다.
    """
    said = str(res.get("error") or "") + "\n" + str(res.get("message") or "")
    if _RATE_OR_QUOTA_WORDS.search(said):
        return ("AGY_QUOTA" if _QUOTA_WORDS.search(said) else "AGY_RATE_LIMIT"), None
    try:
        q = PC.agy_usage(path, env)
    except OSError as e:                                         # /usage 로그를 못 읽음(read_log) — 삼키지 않고 판정에 넘긴다(사유를 남긴다)
        unknown = {"known": False, "why": f"/usage 확인 실패: {type(e).__name__}: {e}"[:200]}
        return ("AGY_ERROR" if unknown_refuses else None), unknown
    summary = {"known": bool(q.get("known")), "code": q.get("code"), "why": q.get("why"),
               "buckets": [{"id": b.get("id"), "remaining": b.get("remaining")}
                           for b in (q.get("buckets") or []) if isinstance(b, dict)]}
    if q.get("code") in ("AGY_QUOTA", "AGY_NOT_SIGNED_IN"):
        return q["code"], summary
    if not q.get("known") and unknown_refuses:
        return "AGY_ERROR", summary
    return None, summary


def _openapi_nullable(schema):
    """스키마 어디에든 `nullable` 칸이 있나. agy(1.4.4)의 finish 도구 검사기는 그 칸을 모른 채 null 을 «want array» 로 거부한다(2026-10-22
    510306 실측 — 모델은 지시문대로 null 을 쓰고, 거부되면 다시 답해야 턴이 끝난다). null 은
    {"type": [T, "null"]} 로 적는다. 보내기 전에 막는다 — 부르는 쪽 코드의 잘못이지 agy 결과가 아니다."""
    if isinstance(schema, dict):
        return "nullable" in schema or any(_openapi_nullable(v) for v in schema.values())
    return isinstance(schema, list) and any(_openapi_nullable(v) for v in schema)


def invoke(prompt, *, kind="text", files=(), add_dirs=(), schema=None, model=None, timeout_s=300, cwd=None, env=None, tries=1, owner=None, decided_file=None, status_error="refuse"):
    """agy 한 번(또는 tries 번). 돌려주는 값: {ok, code, message, text, json, denied, tools, attempts[{code, message}], …}.
    kind: 'text' · 'search' · 'view'(files 의 절대경로를 머리말에) · None(부르는 쪽 프롬프트가 이미 도구 머리말을 갖는다 — agy_review 의 NO_SHELL).
    decided_file = 이 편의 글 공급자 결정(<편>/text_provider.json — env INFO3D_TEXT_PROVIDER_FILE 이 없을 때). 결정이 있으면 그 agy.bin 하나만 띄운다(agy_path).
    예외를 내지 않는다(찾기 실패·시간 초과·로그인 풀림도 code) — make_subs_ai 는 이 코드로 종료 3/4 를 가른다(K8).
    status_error: 'refuse'(기본 · 모든 부르는 쪽의 지금 동작 그대로) — status ERROR 를 거부로 보고 이 실행의 모든 요청을 멈춘다.
      'per_request' — 부르는 쪽이 고른 경로만(인물형 롱폼 피사체 판독 · 2026-10-05 사장님 결정 5-1 «그 컷만 실패, 나머지 계속»).
      status ERROR(code AGY_ERROR · 도구 거부 아님)를 받으면 ① 오류 글에 속도 제한·한도 표시(429·rate limit·resource exhausted·
      too many requests·quota)가 있거나 ② 곧바로 잰 /usage(토큰 0)가 한도 소진·로그인 풀림이거나 ③ /usage 로 한도를 확인하지
      못하면 → 지금과 같이 거부(전부 멈춤). 셋 다 아니면(한도·로그인이 남아 있는 오류) 거부 표식을 남기지 않고
      failure_kind='status_error' · retryable False 로 돌려준다 — 그 요청 하나만 실패이고 자동 재시도는 하지 않는다.
      'per_request_evidence'(2026-10-06 · 인물형 롱폼 피사체만) — 'per_request' 와 같되 ③ /usage 를 확인하지 못한 것은 거부의 증거가
      아니다 → 그 요청 하나의 실패(거부 표식 없음). 거부는 ①·② 의 증거가 있을 때만(_status_error_refusal).
      두 'per_request' 값 모두: 모델이 금지 도구(RunCommand 등)를 시도해 헤드리스가 막은 AGY_TOOL_DENIED(forbidden_tool_only)는
      거부 표식 없이 failure_kind='forbidden_tool' · retryable False 로 돌려준다(2026-10-21). 파일 읽기 권한 거부는 그대로 멈춘다."""
    if schema is not None and _openapi_nullable(schema):
        raise ValueError('agy 스키마에 `nullable` 이 있다 — agy 검사기가 모른다. null 은 {"type": [T, "null"]} 로 적는다')
    env = PC.env_of(env)
    RUN_REFUSAL.assert_allowed(env)
    model = model or PC.agy_model(env)
    try:
        path = agy_path(env, decided_file)                        # 한 호출(재시도·/usage 다시 보기 포함)은 한 agy 로 — 도중에 다른 후보로 바뀌지 않는다
    except (PC.PcEnvError, AgyError) as e:
        return {"ok": False, "code": e.code, "message": str(e), "attempts": [{"code": e.code, "message": str(e)[:200]}], "text": "", "json": None}
    limit = int(table().get("fileLimitBytes") or 104857600)
    for f in files:
        try:
            size = os.path.getsize(f)
        except OSError as e:
            return {"ok": False, "code": "AGY_ERROR", "message": f"판독할 파일이 없다: {f} ({e})", "attempts": [], "text": "", "json": None}
        if size > limit:
            return {"ok": False, "code": "AGY_FILE_TOO_LARGE", "message": f"{os.path.basename(f)} {size}B > {limit}B", "attempts": [], "text": "", "json": None}
    attempts = []
    res = None
    for k in range(max(1, int(tries))):
        RUN_REFUSAL.assert_allowed(env)
        try:
            res = _once(prompt, path=path, kind=kind, files=files, add_dirs=add_dirs, schema=schema, model=model, timeout_s=timeout_s, cwd=cwd, env=env, owner=owner)
        except PC.PcEnvError as e:
            res = {"ok": False, "code": e.code, "message": str(e), "text": "", "json": None}
        except AgyError as e:
            res = {"ok": False, "code": e.code, "message": str(e), "text": "", "json": None}
        except (OSError, proc.SubprocessError) as e:
            res = {"ok": False, "code": "AGY_ERROR", "message": f"agy 실행 실패: {type(e).__name__}: {e}", "text": "", "json": None}
        if _dns_lookup_failure(res):
            # Preserve the failed attempt for client-review recovery. A later
            # invocation must not silently spend quota again; the bridge keeps
            # its attempted receipt. No service-refusal marker is justified.
            res["failure_kind"] = "dns_lookup"
            res["retryable"] = False
            attempts.append({"code": res.get("code"), "message": str(res.get("message") or "")[:200]})
            break
        if status_error == "per_request_evidence" and _network_failure(res):
            # 피사체 경로만(10-06 검토 major): 네트워크 끊김은 거부가 아니고(거부 표식 없음 · /usage 도 안 부른다) 그 컷의 실패로
            # 굳히지도 않는다 — 부르는 쪽(subject_agy_run)이 환경 문제로 막아 연결을 고친 뒤 다시 재게 한다. 다른 부르는 쪽은 그대로다.
            res["failure_kind"] = "network"
            res["retryable"] = False
            attempts.append({"code": res.get("code"), "message": str(res.get("message") or "")[:200]})
            break
        if (status_error in ("per_request", "per_request_evidence") and res.get("status") == "ERROR"
                and res.get("code") == "AGY_ERROR" and not res.get("denied")):
            refused_as, usage = _status_error_refusal(res, path, env, unknown_refuses=status_error == "per_request")
            if refused_as is None:
                res["failure_kind"] = "status_error"
                res["retryable"] = False
                res["usage_after_error"] = usage
                attempts.append({"code": res.get("code"), "message": str(res.get("message") or "")[:200]})
                break
            res["refused_as"] = refused_as
            res["usage_after_error"] = usage
        if (status_error in ("per_request", "per_request_evidence") and res.get("code") == "AGY_TOOL_DENIED"
                and res.get("status") != "ERROR" and forbidden_tool_only(res.get("denied"), res.get("tools"), files)):
            # 모델이 금지 도구(RunCommand 등)·요청 밖 파일 읽기를 시도해 헤드리스가 막은 것 — 서비스 거부가 아니다(forbidden_tool_only).
            # 거부 표식 없이 그 요청 하나의 실패로 돌려준다 · 자동 재시도 없음. 요청한 파일의 읽기 거부·status ERROR 는 아래 그대로 멈춘다.
            res["failure_kind"] = "forbidden_tool"
            res["retryable"] = False
            attempts.append({"code": res.get("code"), "message": str(res.get("message") or "")[:200]})
            break
        if res.get("denied") or res.get("code") == "AGY_TOOL_DENIED" or res.get("status") == "ERROR":
            RUN_REFUSAL.mark_refusal(env=env, kind=refusal_kind(res))
            failure = RUN_REFUSAL.RunServiceRefused()
            failure.provider_result = res
            raise failure
        if res.get("code") in ("AGY_QUOTA", "AGY_NOT_SIGNED_IN", "AGY_RATE_LIMIT"):
            RUN_REFUSAL.mark_refusal(env=env, kind=refusal_kind(res))
            failure = RUN_REFUSAL.RunServiceRefused()
            failure.provider_result = res
            raise failure
        attempts.append({"code": res.get("code"), "message": str(res.get("message") or "")[:200]})
        if res.get("ok") or not retryable(res.get("code")) or k + 1 >= max(1, int(tries)):
            break
        time.sleep(RETRY_STEP_S * (k + 1))
    res["attempts"] = attempts
    return res


def decision(env=None, decided_file=None):
    """이 편의 글 공급자 결정(K8 · tools/lib/text_provider.mjs 가 쓴다) → (파일, agy 칸 dict) · 결정이 없으면 (None, None).
    env INFO3D_TEXT_PROVIDER_FILE(부모 make_episode 가 모든 단계 자식에 준 결정 — **가리켰으면 읽혀야 한다**: 못 읽는 것을 「결정 없음」으로 치면
    결정 밖의 agy 가 찾기로 끼어든다 → AgyError(AGY_ERROR)) → decided_file(<편>/text_provider.json — 있을 때만 · 손으로 돌린 flow_episode).
    결정에 agy 칸이 없으면 빈 dict(= agy 준비 안 됨 — 결정 밖 agy 를 끼우지 않는다)."""
    env = PC.env_of(env)
    pinned = (env.get("INFO3D_TEXT_PROVIDER_FILE") or "").strip()
    path = pinned or (decided_file if decided_file and os.path.isfile(decided_file) else "")
    if not path:
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise AgyError("AGY_ERROR", f"편 결정 {path} 를 읽지 못했다({type(e).__name__}: {e}) — 결정 밖의 agy 로 넘어가지 않는다")
    agy = data.get("agy") if isinstance(data, dict) else None
    return path, (agy if isinstance(agy, dict) else {})


def _decided_bin(path, agy, env):
    """결정의 agy 칸 → 띄울 실행 파일 하나(아니면 PC.PcEnvError). 준비됨이 아니면 그 코드(코드 표에 있을 때 — 아니면 AGY_NOT_INSTALLED) ·
    bin 이 없거나 절대경로가 아니거나 파일이 없으면 AGY_NOT_INSTALLED. 다른 후보(INFO3D_AGY_BIN·PATH·설치 기본 자리)로 넘어가지 않는다."""
    name = os.path.basename(path)
    if agy.get("ready") is not True:
        code = agy.get("code") if agy.get("code") in (table().get("codes") or {}) else "AGY_NOT_INSTALLED"
        raise PC.PcEnvError(code, f"편 결정({name}): agy 준비 안 됨 — {agy.get('code') or agy.get('reason') or '결정에 agy 칸 없음'}")
    exe = agy.get("bin")
    if not isinstance(exe, str) or not os.path.isabs(exe) or not os.path.isfile(exe):
        raise PC.PcEnvError("AGY_NOT_INSTALLED", f"편 결정({name})의 agy 실행 파일이 없다: {exe!r} — 다른 agy 로 바꾸지 않는다"
                                                 "(agy 를 다시 깔았으면 새 편에서 다시 정한다)")
    if PC.test_context(env) and not PC.is_marked(exe, PC.FAKE_AGY_MARK):
        raise PC.PcEnvError("AGY_NOT_INSTALLED", f"시험 중에는 표식 있는 가짜 agy 만 쓴다(AGY_FORBIDDEN_IN_TESTS): {exe}")
    return exe


def agy_path(env=None, decided_file=None):
    """이 호출이 띄울 agy 실행 파일 **하나** — 편 결정이 있으면 그 agy.bin 만(JS 와 같은 규칙: B6-J 수정 1회차 ③ 「이어 하기는 저장된 bin 하나만 ·
    결정의 agy 를 조용히 빼지 않음」 · 2026-09-26 B6-P 수정 1회차 · 검토 minor ④ — 옛 판은 결정의 ready 만 보고 실행은 찾기 사슬로 해, 결정된 bin 이
    사라지면 PATH 의 다른 agy 로 조용히 바뀌었다). 결정이 없을 때만 pc_env.agy_exe(찾기: INFO3D_AGY_BIN → PATH → 설치 기본 자리)."""
    env = PC.env_of(env)
    path, agy = decision(env, decided_file)
    if path is None:
        return PC.agy_exe(env)
    return _decided_bin(path, agy, env)


def status(env=None, decided_file=None):
    """agy 를 쓸 수 있나 — K8: 편 결정 `text_provider.json`(env INFO3D_TEXT_PROVIDER_FILE → 부른 쪽이 준 <편>/text_provider.json)이 있으면 그 agy 칸
    (준비됨 + 그 agy.bin 이 있음 — 호출이 띄울 것과 같은 한 파일), 없으면 pc_env.agy_status(찾기 → --version → models · /usage 는 호출 때 ERROR 가 나면 본다).
    돌려주는 값: (ok, 까닭, 코드)."""
    env = PC.env_of(env)
    try:
        path, agy = decision(env, decided_file)
    except AgyError as e:
        return False, str(e), e.code
    if path is not None:
        if agy.get("ready") is not True:
            return False, f"편 결정(text_provider.json): agy 준비 안 됨 — {agy.get('code') or agy.get('reason') or '결정에 agy 칸 없음'}", agy.get("code") or "AGY_NOT_INSTALLED"
        try:
            exe = _decided_bin(path, agy, env)
        except PC.PcEnvError as e:
            return False, str(e), e.code
        return True, f"편 결정(text_provider.json): agy {agy.get('cliVersion') or ''} 준비됨 ({exe})".replace("  ", " "), None
    st = PC.agy_status(env, usage=False)
    return bool(st.get("ok")), (st.get("message") or "") + (f" ({st['path']})" if st.get("path") else ""), st.get("code")
