import errno, json, math, os, re, shutil, sys, tempfile, time, urllib.error, urllib.request


from datetime import datetime


HERE = os.path.dirname(os.path.abspath(__file__))


import agy_transport_proc as proc   # noqa: E402  자식 실행 한 자리(flow/proc.py — 윈도우 창 없음·분리 실행·제한시간 나무 종료)


ROOT = os.environ.get("INFO3D_ROOT") or os.path.dirname(HERE)


AGY_MODEL_DEFAULT = "gemini-3.8-flash-high"   # make_subs_ai · agy_review · agy_client 의 모델 이름을 이 한 자리로(K9: env INFO3D_AGY_MODEL 이 먼저)


FAKE_AGY_MARK, FAKE_FLOWKIT_MARK, FAKE_BROWSER_MARK = "info3d-fake-agy", "info3d-fake-flowkit", "info3d-fake-browser"


CODES_FILE = os.path.join(HERE, "ref", "agy_codes.json")


class PcEnvError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


_codes_cache = {}


def load_codes(path=None):
    if path is not None:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    from agy_transport_codes import CODES
    return CODES


def code_text(code, codes=None, model=None, env=None):
    """코드의 사람 말(코드 표 text). 표에 없는 코드는 빈 글 — 시험(pc_env_test)이 우리가 내는 코드가 전부 표에 있는지 잰다.
    표 글은 모델 이름을 표의 model 칸 값으로 적어 두었다(표는 info3d ref/agy_codes.json 을 내보낸 것 — 여기서 고치지 않는다) →
    실제로 쓰는 모델(model 인자, 없으면 agy_model(env): env INFO3D_AGY_MODEL 이 먼저)로 바꿔 짓는다(2026-10-23 신고 «코드 표 문구에 모델이 박혀 있다»)."""
    table = codes or load_codes()
    row = (table.get("codes") or {}).get(code) or (table.get("guards") or {}).get(code) or {}
    text, named = row.get("text", ""), table.get("model")
    return text.replace(named, model or agy_model(env)) if named and named in text else text


def env_of(env):
    return os.environ if env is None else env


def agy_model(env=None):
    return (env_of(env).get("INFO3D_AGY_MODEL") or "").strip() or AGY_MODEL_DEFAULT


def test_context(env=None):
    """시험 중인가 — node --test 가 자식에게 NODE_TEST_CONTEXT 를 준다(파이썬 시험 파일은 스스로 넣는다). 실제 제작에는 없는 변수다.
    넘겨받은 env 와 **이 프로세스의 환경 둘 다** 본다 — 시험이 env={"PATH": …} 처럼 좁힌 dict 를 넘겨도 보호가 꺼지지 않게
    (2026-09-25 B6-P 구현 중 실측: 좁힌 env 로 부른 시험에서 보호가 꺼져 HOME 기본 자리의 진짜 agy 가 떴다 — notes/B6-P.md §3)."""
    return bool(env_of(env).get("NODE_TEST_CONTEXT") or os.environ.get("NODE_TEST_CONTEXT"))


def is_marked(path, mark):
    try:
        with open(path, "rb") as f:
            return mark.encode() in f.read(400)
    except OSError:
        return False


def _registry_path(platform=sys.platform):
    """윈도우 사용자·시스템 PATH 를 레지스트리에서 새로 읽는다 — `agy install` 이 PATH 를 고친 뒤 다시 켜지 않은
    창(클로드 코드)의 PATH 는 낡아 있다(진단 본문: 4명이 회차마다 찾음/못찾음)."""
    if platform != "win32":
        return ""
    import winreg
    out = []
    for hive, sub in ((winreg.HKEY_CURRENT_USER, r"Environment"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")):
        try:
            with winreg.OpenKey(hive, sub) as key:
                raw, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        out += [os.path.expandvars(d) for d in str(raw).split(";") if d.strip()]
    return os.pathsep.join(out)


def agy_candidates(env=None, platform=sys.platform, registry_path=None):
    """(경로, 출처) — 이 순서로 본다. 있는지·도는지는 agy_status 가 본다."""
    env = env_of(env)
    out = []

    def add(path, source):
        if path and all(os.path.normcase(path) != os.path.normcase(p) for p, _ in out):
            out.append((path, source))
    add((env.get("INFO3D_AGY_BIN") or "").strip(), "env INFO3D_AGY_BIN")
    add(shutil.which("agy", path=env.get("PATH", "")), "PATH")
    if platform == "win32":
        if registry_path is None and not test_context(env):
            registry_path = _registry_path(platform)
        if registry_path:
            add(shutil.which("agy", path=registry_path), "레지스트리 PATH")
        if env.get("LOCALAPPDATA"):
            add(os.path.join(env["LOCALAPPDATA"], "agy", "bin", "agy.exe"), "설치기 기본 자리(install.ps1)")
    else:
        home = env.get("HOME") or ("" if test_context(env) else os.path.expanduser("~"))
        if home:
            add(os.path.join(home, ".local", "bin", "agy"), "설치기 기본 자리(install.sh)")
    return out


def _signal(name, default):
    """코드 표 signals 의 값(표가 없거나 깨졌으면 load_codes 가 던진다 — 기본값은 표에 그 칸이 없을 때만)."""
    return load_codes().get("signals", {}).get(name, default)


def agy_argv(path):
    """agy 실행 앞부분. 진짜 agy 는 네이티브 실행 파일(Go)이다. 시험의 가짜 agy(.py)는 지금 파이썬으로 띄운다(JS 설계의 .mjs → node 와 같은 규칙)."""
    return [sys.executable, path] if str(path).lower().endswith(".py") else [path]


AGY_ENV_KEEP = {"win32": ("USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA", "SystemRoot", "ComSpec", "PATHEXT", "TEMP", "TMP",
                          "SystemDrive", "USERNAME", "PATH"),
                "posix": ("HOME", "PATH", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR")}


AGY_PROXY_ENV = ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY", "https_proxy", "http_proxy", "no_proxy", "all_proxy")


def agy_child_env(env=None, platform=sys.platform):
    """agy 자식의 최소 환경(K6 · agy-provider.md 3-5) — 우리 열쇠(CUSTOM_*·GEMINI_API_KEY·GOOGLE_API_KEY)는 넘기지 않는다.
    agy 바이너리에 GEMINI_API_KEY·AGY_ADC_AUTH 글자가 있어 키가 보이면 유료 인증으로 바뀔 수 있다(추정) — 구독 인증만 쓰게 막는다.
    넘기는 것: AGY_ENV_KEEP + 프록시 여덟 이름(AGY_PROXY_ENV). 이름 맞추기는 JS agyChildEnv 와 같다 — POSIX 는 글자 그대로(환경 이름이 대소문자를 가린다),
    윈도우는 대소문자 무시(윈도우 환경은 가리지 않는다 — 프록시는 있는 이름 그대로 한 번만, 사본을 만들지 않는다).
    시험의 FAKE_AGY_* · NODE_TEST_CONTEXT 만 예외로 넘긴다."""
    env = env_of(env)
    win = platform == "win32"
    keep = AGY_ENV_KEEP["win32" if win else "posix"]
    upper = {k.upper(): k for k in env} if win else {}
    out = {}
    for name in keep:
        key = name if name in env else upper.get(name.upper())
        if key is not None and isinstance(env[key], str):
            out[name] = env[key]
    proxies = {p.upper() for p in AGY_PROXY_ENV} if win else set(AGY_PROXY_ENV)
    for key, value in env.items():
        if (key.upper() if win else key) in proxies and isinstance(value, str):
            out[key] = value
    if test_context(env):
        out.update({k: v for k, v in env.items() if k.startswith("FAKE_AGY_") and isinstance(v, str)})
        out["NODE_TEST_CONTEXT"] = env.get("NODE_TEST_CONTEXT") or os.environ.get("NODE_TEST_CONTEXT")
    return out


def _run_agy(run, path, args, env, platform, timeout, cwd=None):
    """agy 사전 점검 호출(--version · models · /usage) 한 자리.

    ★출력은 **파이프가 아니라 임시 파일**로 받는다 (2026-10-17 · 윈도우 env «AGY_VERSION_FAILED(--version TimeoutExpired)»·
      «AGY_MODELS_FAILED(PROC_PIPE_HELD — 부모 사슬 밖 자손이 파이프를 쥠)»·«AGY_UNRESPONSIVE» 오늘 17지문 · agy 1.4.0).
      agy 는 뒤에 오래 사는 자식(언어 서버)을 남기고 그 자식이 물려받은 표준 출력 핸들을 쥔다 — 파이프로 받으면 agy 본체가 끝나도
      `communicate()` 가 그 파이프가 닫히기를 기다려 제한시간까지 서 있다(본체가 답을 다 썼는데도 «실패»). 실제 호출 자리
      (agy_transport_client.invoke)는 처음부터 파일로 받는다 — 점검만 파이프였다. 파일이면 본체가 끝나는 순간 `wait()` 가 돌아온다.
      본체가 정말 멈춘 것이면 예전처럼 제한시간에 나무째 끝내고 TimeoutExpired 다(판정은 그대로).
    ★임시 폴더 정리는 실제 호출 자리(agy_transport_client.invoke 의 `shutil.rmtree(work, ignore_errors=True)`)와 같은 규칙이다
      (2026-10-21 실제 Windows 실측): 그 뒤에 남는 자식이 물려받은 out/err 파일 핸들을 아직 쥐고 있으면 윈도우는 그 파일을 못 지운다
      (WinError 32). `TemporaryDirectory` 의 정리가 그 PermissionError 를 던져, 본체 답을 다 받아 놓고도 점검 전체가 죽었다.
      답은 이미 읽었고 남는 것은 빈 폴더 하나 몫의 파일뿐이라 정리 실패가 판정을 바꾸지 않는다 — 판정·예외는 그대로 두고 지우기만 최선으로.
    ★시험이 넣는 가짜 `run` 은 예전 모양(capture_output)으로 부른다 — 가짜는 파이프를 쓰지 않는다."""
    argv = agy_argv(path) + list(args)
    kw = dict(timeout=timeout, env=agy_child_env(env, platform), cwd=cwd)
    if run is not proc.run:
        return run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    tmp = tempfile.mkdtemp(prefix="agy-probe-")
    try:
        out_p, err_p = os.path.join(tmp, "out.txt"), os.path.join(tmp, "err.txt")
        with open(out_p, "wb") as fo, open(err_p, "wb") as fe:
            r = proc.run(argv, stdin=proc.DEVNULL, stdout=fo, stderr=fe, **kw)
        with open(out_p, encoding="utf-8", errors="replace") as f:
            r.stdout = f.read()
        with open(err_p, encoding="utf-8", errors="replace") as f:
            r.stderr = f.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return r


def _finite(value):
    """JS Number.isFinite 와 같은 뜻(참·거짓은 수가 아니다)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _epoch_ms(text):
    """ISO 8601 글자 → epoch ms(JS Date.parse 와 같은 뜻: 끝의 Z·오프셋은 그대로 · 날짜만이면 UTC 자정 · 오프셋 없는 날짜+시각은 이 컴퓨터 시각). 못 읽으면 None."""
    if not isinstance(text, str) or not text.strip():
        return None
    t = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        t += "T00:00:00+00:00"
    elif t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        return int(datetime.fromisoformat(t).timestamp() * 1000)
    except (ValueError, OverflowError, OSError):
        return None


def parse_usage(stdout):
    """`agy -p /usage --output-format json` 봉투 → {buckets, exhausted[{id, resetAt}], resetAt, resetAtEpochMs} · 모양이 다르면 None(짐작하지 않는다).
    **JS tools/lib/agy_bin.mjs parseAgyUsage 와 같은 규칙**(K5 · 사례표 tests/fixtures/pc_env/agy_cases.json 으로 대조): 마지막 비지 않은 줄이 JSON 이고
    command.data.groups 가 배열이어야 읽은 것 · 묶음 = groups[].buckets[] 중 id 가 글자인 것(P11 실측 모양) · 제미나이 묶음(signals.quotaBuckets) 중
    remaining_fraction ≤ 0 이면 소진 · 풀리는 시각은 소진 묶음 reset_time 중 가장 늦은 것."""
    lines = [ln for ln in re.split(r"\r?\n", str(stdout or "").strip()) if ln]
    try:
        data = json.loads(lines[-1]) if lines else None
    except ValueError:
        return None
    node = data
    for key in ("command", "data", "groups"):
        node = node.get(key) if isinstance(node, dict) else None
    if not isinstance(node, list):
        return None
    buckets = [b for g in node if isinstance(g, dict) and isinstance(g.get("buckets"), list) for b in g["buckets"]
               if isinstance(b, dict) and isinstance(b.get("id"), str)]
    watched = set(_signal("quotaBuckets", ["gemini-5h", "gemini-weekly"]))
    empty = [b for b in buckets if b["id"] in watched and _finite(b.get("remaining_fraction")) and b["remaining_fraction"] <= 0]
    resets = [(_epoch_ms(b.get("reset_time")), b.get("reset_time")) for b in empty]
    resets = [r for r in resets if r[0] is not None]
    latest = max(resets) if resets else (None, None)
    return {"buckets": [{"id": b["id"], "remaining": b.get("remaining_fraction") if _finite(b.get("remaining_fraction")) else None,
                         "resetAt": b.get("reset_time")} for b in buckets],
            "exhausted": [{"id": b["id"], "resetAt": b.get("reset_time")} for b in empty],
            "resetAtEpochMs": latest[0], "resetAt": latest[1]}


def error_code(e):
    """OSError → errno 이름(EISDIR · EACCES · ENOENT …) — JS fs 오류의 e.code 와 같은 글자(두 판의 기록이 같은 말을 쓴다). errno 가 없으면 예외 이름."""
    return errno.errorcode.get(getattr(e, "errno", None) or -1) or type(e).__name__


def read_log(path):
    """agy --log-file 을 읽는다. 파일이 **없으면**(ENOENT — agy 가 로그를 쓰기 전에 끝남 · 아직 안 씀) None.
    그 밖의 읽기 오류(로그 자리가 폴더 EISDIR · 권한 EACCES …)는 **올린다** — 로그인 안 됨 줄(signals.authLog)을 못 본 채 「사실 없음」으로 넘어가면
    판정할 수 없는 것을 준비됨·성공으로 치게 된다(2026-09-26 B6-P 이어 수리 · 10-설계보정 §7-추가 7 ② · JS tools/lib/agy.mjs·agy_bin.mjs 와 같은 규칙)."""
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return None


def _usage_log_facts(path):
    """/usage 의 --log-file 에서 사실만(판 · 로그인 안 됨 줄 — 코드 표 signals.logFacts·authLog). 계정 이메일은 가져오지 않는다.
    파일이 없으면 빈 사실 · 있는데 못 읽으면 OSError 를 올린다(read_log — 옛 판은 모든 OSError 를 빈 사실로 삼켰다)."""
    text = read_log(path)
    if text is None:
        return {}
    mark = ((load_codes().get("signals") or {}).get("logFacts") or {}).get("version")
    version = next((ln.split(mark, 1)[1].strip().split()[0] for ln in text.splitlines() if mark and mark in ln and ln.split(mark, 1)[1].strip()), None)
    return {"cliVersion": version, "notSignedIn": any(line in text for line in _signal("authLog", []))}


def agy_usage(path, env=None, platform=sys.platform, run=proc.run, timeout=60):
    """`agy -p /usage --output-format json --log-file <임시>/agy.log`(토큰 0 · P11 · cwd = 그 임시 폴더 — JS agy_bin.mjs agyUsageProbe 와 같은 호출 모양) → 한도 보고.
    판정(K5 · 통합 담당 판정 2026-09-25 23:1x — _critic K5 「/usage 는 한도만 맡는다」 · notes/B6-P.md §2-8; JS agyReadiness 도 같은 규칙으로 맞춘다):
      준비 안 됨은 둘뿐 — ① 로그에 로그인 안 됨 줄(signals.authLog) → AGY_NOT_SIGNED_IN(K3 이름 — AGY_LOGIN_REQUIRED 는 버린 이름) ·
      ② 제미나이 묶음(signals.quotaBuckets) remaining_fraction ≤ 0 → AGY_QUOTA(풀리는 시각 = 소진 묶음 reset_time 중 가장 늦은 것).
      /usage 가 시간 초과·실행 실패·종료≠0·모양이 다름이면 **준비는 그대로 · 한도 모름**(known False + 까닭 why) — 로그인·모델은 models 가 이미 판정했다.
      한도를 모르는 것은 호출이 status ERROR 를 내면 agy_client 가 /usage 로 다시 가른다.
    로그(계정 이메일이 찍힌다 · agy-provider.md 3-7)는 사실만 읽고 폴더째 지운다. 돌려주는 값: {code, known, why?, detail?, buckets, exhausted, resetAt, resetAtEpochMs, facts}."""
    folder = tempfile.mkdtemp(prefix="info3d-agy-usage-")
    log = os.path.join(folder, "agy.log")
    try:
        timed_out, status, stdout, why = False, None, "", None
        try:
            r = _run_agy(run, path, ["-p", "/usage", "--output-format", "json", "--log-file", log], env, platform, timeout, cwd=folder)
            status, stdout = r.returncode, r.stdout or ""
        except proc.TimeoutExpired:
            timed_out = True
        except (OSError, proc.SubprocessError) as e:
            why = f"{type(e).__name__}: {e}"
        facts = _usage_log_facts(log)
        if facts.get("notSignedIn"):
            return {"code": "AGY_NOT_SIGNED_IN", "detail": "agy /usage 로그에 로그인 안 됨 줄이 있다", "known": False, "facts": facts}
        if timed_out:
            return {"code": None, "known": False, "why": f"/usage 가 {timeout:g}초 안에 끝나지 않았다", "facts": facts}
        usage = parse_usage(stdout) if status == 0 else None
        if usage is None:
            return {"code": None, "known": False, "facts": facts,
                    "why": f"/usage 답을 읽지 못했다(종료 {status if status is not None else why})"}
        if usage["exhausted"]:
            return dict(usage, code="AGY_QUOTA", known=True, facts=facts,
                        detail=f"{','.join(b['id'] for b in usage['exhausted'])} 소진 · {usage['resetAt'] or '풀리는 시각 모름'} 까지")
        return dict(usage, code=None, known=True, facts=facts)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


AGY_TIMEOUTS_S = {"version": 30, "models": 60, "usage": 60}    # 우리 쪽 상한(공식 숫자 없음 · JS agyReadiness 기본값과 같다 — models 는 win-01 실측 0.8초)


def agy_status(env=None, platform=sys.platform, run=proc.run, model=None, usage=True, registry_path=None, timeouts=None):
    """agy 를 **써도 되는지**(K5 — JS agyReadiness 와 같은 순서·같은 코드 · 사례표로 대조). 돌려주는 값: {ok, code, message, path, source, version,
    signedIn, model, models, quota, resetAt?, tried}. code 는 ref/agy_codes.json 의 이름이다. timeouts = {version, models, usage} 초(JS timeouts 와 같은 칸)."""
    env = env_of(env)
    model = model or agy_model(env)
    lim = dict(AGY_TIMEOUTS_S, **(timeouts or {}))
    tried, version_failed, version_slow = [], False, False
    for path, source in agy_candidates(env, platform, registry_path):
        if not os.path.isfile(path):
            tried.append(f"{path}: 없음 ({source})")
            continue
        if test_context(env) and not is_marked(path, FAKE_AGY_MARK):
            tried.append(f"{path}: 시험 중에는 진짜 agy 를 부르지 않는다(AGY_FORBIDDEN_IN_TESTS)")
            continue
        try:
            v = _run_agy(run, path, ["--version"], env, platform, lim["version"])
        except proc.TimeoutExpired:
            # 시간 초과는 «깨진 설치» 가 아니라 «지금 답이 늦다» 다 — models 시간 초과(AGY_UNRESPONSIVE)와 같은 부류.
            #   10-21 인물형 롱폼 cb86d7(윈도우): 앞 실행의 점검이 196.6초 걸리며 agy 가 1.4.3 → 1.4.4 로 바뀐 직후 두 번 «--version
            #   30초 초과» → «다시 설치하라» 로 막혔고, 75분 뒤 같은 PC 에서 9.9초로 통과했다(진단 agy_preflight.version·seconds).
            tried.append(f"{path}: --version TimeoutExpired({lim['version']:g}초)")
            version_slow = True
            continue
        except (OSError, proc.SubprocessError) as e:
            tried.append(f"{path}: --version {type(e).__name__}")
            version_failed = True
            continue
        if v.returncode != 0:
            tried.append(f"{path}: --version 종료 {v.returncode}")
            version_failed = True
            continue
        rep = {"ok": False, "path": path, "source": source, "version": ((v.stdout or "").strip().splitlines() or [""])[0][:40],
               "model": model, "tried": tried}
        try:
            m = _run_agy(run, path, ["models"], env, platform, lim["models"])
        except proc.TimeoutExpired:
            return dict(rep, code="AGY_UNRESPONSIVE", message=f"agy models 가 {lim['models']:g}초 안에 끝나지 않았다")
        except (OSError, proc.SubprocessError) as e:
            return dict(rep, code="AGY_MODELS_FAILED", message=f"agy models 실행 실패: {type(e).__name__}: {e}")
        models = [ln.split()[0] for ln in (m.stdout or "").splitlines() if ln.strip()]      # 코드 표 signals.modelsLine = 첫 낱말
        if m.returncode != 0 or not models:
            said = "\n".join(x for x in (m.stderr, m.stdout) if x).strip()       # 둘 다 본다(JS agyReadiness `${stderr}\n${stdout}` 와 같다 — 사례표로 대조)
            code = "AGY_NOT_SIGNED_IN" if any(x in said.lower() for x in _signal("notSignedIn", ["sign in"])) else "AGY_MODELS_FAILED"
            return dict(rep, signedIn=False if code == "AGY_NOT_SIGNED_IN" else None, code=code, message=said[-240:] or f"agy models 종료 {m.returncode}")
        rep.update(signedIn=True, models=len(models))
        if model not in models:
            return dict(rep, code="AGY_MODEL_UNAVAILABLE", message=f"{model} 이 이 계정의 agy 모델 목록에 없다(보이는 모델 {len(models)}개)")
        if usage:
            q = agy_usage(path, env, platform, run, timeout=lim["usage"])
            rep["quota"] = {k: v for k, v in q.items() if k != "facts"}
            if q.get("code"):
                extra = {"resetAt": q.get("resetAt"), "resetAtEpochMs": q.get("resetAtEpochMs")} if q["code"] == "AGY_QUOTA" else {}
                return dict(rep, code=q["code"], message=f"{code_text(q['code']) or q['code']} — {q.get('detail')}", **extra)
        unknown = f" · 한도 모름({rep['quota']['why']})" if usage and not rep["quota"].get("known") else ""
        return dict(rep, ok=True, code=None, message=f"agy {rep['version']} · 로그인 · {model}{unknown}")
    if version_slow:
        return {"ok": False, "code": "AGY_UNRESPONSIVE", "tried": tried,
                "message": f"agy --version 이 {lim['version']:g}초 안에 끝나지 않았다(설치가 깨진 것이 아니라 답이 늦다 — 갱신 직후 첫 실행 등): "
                           + "; ".join(tried)[-300:]}
    if version_failed:
        return {"ok": False, "code": "AGY_VERSION_FAILED", "tried": tried, "message": "agy 를 찾았지만 --version 이 실패했다: " + "; ".join(tried)[-300:]}
    return {"ok": False, "code": "AGY_NOT_INSTALLED", "tried": tried, "message": "agy 를 찾지 못했다"}


def agy_exe(env=None, platform=sys.platform):
    """엔진 안의 agy 호출 자리(agy_client)가 쓰는 한 경로. 판정은 하지 않는다(판정은 agy_status · 편 결정 text_provider.json)."""
    env = env_of(env)
    for path, _ in agy_candidates(env, platform):
        if os.path.isfile(path):
            if test_context(env) and not is_marked(path, FAKE_AGY_MARK):
                continue
            return path
    raise PcEnvError("AGY_NOT_INSTALLED", "agy 를 찾지 못했다" + (" (시험 중에는 표식 있는 가짜 agy 만 쓴다)" if test_context(env) else ""))


def agy_settings_path(env=None, platform=sys.platform):
    env = env_of(env)
    home = env.get("USERPROFILE") if platform == "win32" else env.get("HOME")
    return os.path.join(home or os.path.expanduser("~"), ".gemini", "antigravity-cli", "settings.json")


def _under(folder, base):
    f, b = os.path.normcase(os.path.realpath(folder)), os.path.normcase(os.path.realpath(os.path.expanduser(base)))
    return f == b or f.startswith(b.rstrip("\\/") + os.sep)


def read_allowed(folder, settings):
    """vox/agy.py read_allowed 이식 — allow 에 이 폴더(또는 상위)를 여는 read_file 규칙이 있나."""
    with open(settings, encoding="utf-8") as f:
        allow = ((json.load(f).get("permissions") or {}).get("allow")) or []
    return any(isinstance(rule, str) and rule.startswith("read_file(") and rule.endswith(")") and _under(folder, rule[len("read_file("):-1])
               for rule in allow)
