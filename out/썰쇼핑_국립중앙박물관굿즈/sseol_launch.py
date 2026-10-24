#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 썰쇼핑 실행기 스크립트 — 서버(volcano-mcp src/sseol/runner_script.py)가 내린 본문.
# 한 글자도 고치지 마세요. stdout 에는 JSON 한 덩어리만 나옵니다(로그는 stderr).
import hashlib, json, os, shutil, subprocess, sys

def log(*a):
    print(*a, file=sys.stderr, flush=True)

_ANSWERED = []
ENGINE_ENDS = (SystemExit, KeyboardInterrupt, GeneratorExit)

def answered():
    """emit 이 답을 냈다 — 그 뒤의 끝(sys.exit(0))은 입구가 그대로 내보낸다(서버 runner_entry.py 한 자리)."""
    _ANSWERED.append(1)

def engine_exit(e):
    """답을 내기 전의 끝(엔진 코드의 sys.exit(N)·Ctrl+C) → 사유·트레이스백 답. 이미 답을 냈으면 그 끝을 그대로 다시 던진다."""
    if _ANSWERED:
        raise e
    import traceback
    return {"ok": False, "code": "ENGINE_EXIT",
            "why": "엔진 코드가 답 없이 %s(%r) 로 끝냈습니다" % (type(e).__name__, getattr(e, "code", None)),
            "traceback": traceback.format_exc()[-2000:]}

def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()
    answered(); sys.exit(0)

def _child_env(extra=None):
    """자식 파이썬 환경 — ★윈도우 파이썬 기본 인코딩은 cp949 다. UTF-8 모드를 켜야 한글 경로·출력이 안 깨진다."""
    e = dict(os.environ)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    e.update(extra or {})
    return e

def venv_exe(vdir):
    """vdir 가상환경의 python 경로(윈도우 Scripts/python.exe · 맥 bin/python3) — 없으면 None. 돌려주는 경로는 쓴 그대로이고,
    윈도우에서 260자를 넘는 자리는 확장 경로(앞에 «두 역슬래시 ? 역슬래시»)로 있는지만 본다(작업 이름에 그 표기를 남기지 않는다)."""
    for rel in (("Scripts", "python.exe"), ("bin", "python3"), ("bin", "python")):
        p = os.path.join(vdir, *rel)
        if os.path.isfile(p):
            return p
        if os.name == "nt":
            a = os.path.abspath(p)
            if not a.startswith(chr(92) * 2) and os.path.isfile(chr(92) * 2 + "?" + chr(92) + a):
                return p
    return None

def venv_with_pip(base, vdir, timeout=900, on_timeout=None):
    """pip 를 부를 수 있는 가상환경 python — (경로, None) 또는 (None, 사유 글). 서버 runner_venv.py 한 자리.
    python 은 있는데 pip 를 못 부르는 것은 만들다 끊긴 가상환경이다 — --clear 로 한 번 새로 만든다(상한 1).
    시간을 넘긴 단계는 _run 이 예외로 던지든(run_or_raise) 결과로 돌려주든(run_bounded) 여기서 사람 글로 바꾼다 —
    on_timeout(단계 이름, 초, 글)을 주면 그것을 부른다(채널 고유 멈춤 코드용)."""
    def step(argv, sec, what):
        try:
            r = _run(argv, timeout=sec)
        except subprocess.TimeoutExpired as e:
            tail = e.stderr or e.output or ""
            r = subprocess.CompletedProcess(argv, None, "", tail.decode("utf-8", "replace") if isinstance(tail, bytes) else tail)
            r.timed_out = True
        if not getattr(r, "timed_out", False):
            return r, None
        msg = ("%s(%s)가 %g초 안에 끝나지 않아 멈췄습니다 — 보통 1분 안에 끝납니다. 백신·보안 프로그램이 새 파이썬 파일을 붙잡고 있는지 "
               "확인한 뒤 다시 부르세요(만들다 만 폴더는 다음 점검에서 지우고 새로 만듭니다).\n" % (what, vdir, sec)
               + (r.stderr or r.stdout or "")[-500:])
        if on_timeout is not None:
            on_timeout(what, sec, msg)
        return r, msg
    py = venv_exe(vdir)
    if py is not None:
        r, late = step([py, "-m", "pip", "--version"], 300, "가상환경 pip 확인")
        if late:   # 느린 것(백신 검사 등)은 끊긴 것이 아니다 — 지우지 않고 사유를 돌려준다
            return None, late
        if r.returncode == 0:
            return py, None
        log("가상환경이 만들다 끊긴 채 남아 있습니다(pip 를 못 부름) — 새로 만듭니다(내려받은 부품뿐이라 작업은 그대로입니다).")
    else:
        log("가상환경을 만듭니다:", vdir)
    r, late = step(list(base) + ["-m", "venv", "--clear", vdir], timeout, "가상환경 만들기")
    if late:
        return None, late
    py = venv_exe(vdir)
    if r.returncode != 0 or py is None:
        return None, (r.stderr or r.stdout or "(출력 없음)")[-600:]
    r, late = step([py, "-m", "pip", "--version"], 300, "새 가상환경 pip 확인")
    if late:
        return None, late
    if r.returncode != 0:
        return None, "새로 만든 가상환경에서도 pip 를 못 부릅니다 — " + (r.stderr or r.stdout or "")[-500:]
    return py, None

import signal, subprocess, tempfile, time

def kill_tree(proc, grace=30):
    """proc 를 손주까지 끝낸다(서버 runner_proc.py 한 자리) — 다 끝났으면 None, grace 초 안에 안 끝난 것이 남으면 그 pid."""
    if os.name == "nt":
        try:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=grace)
        except (OSError, subprocess.TimeoutExpired) as e:
            print("taskkill 실패:", type(e).__name__, e, file=sys.stderr, flush=True)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError as e:
            print("killpg 실패:", e, file=sys.stderr, flush=True)
    if proc.poll() is None:
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.wait(timeout=grace)
        return None
    except subprocess.TimeoutExpired:
        return proc.pid

def run_bounded(argv, cwd=None, env=None, timeout=None, stderr_inherit=False):
    """자식 하나 — 모든 대기에 끝이 있다(서버 runner_proc.py 한 자리). 출력은 임시 파일로 · 입력은 비움 · 시간을 넘기면 손주까지 끝냄.
    시간을 넘기면 예외 대신 returncode None · timed_out True · left_pid(못 끝낸 pid 또는 None)."""
    env = dict(os.environ if env is None else env)
    # pip 은 가장 새 판에 이 기계용 바퀴(wheel)가 아직 없으면 소스 빌드로 떨어진다(CMake·컴파일러 없는 회원 PC 에서 실패).
    #   새 판은 소스(sdist)가 먼저 올라오고 바퀴가 수십 분 뒤 붙는다 — 그 틈에 깐 회원이 멈췄다(신고 10-21 컬투·팟캐스트 · 윈도우 ·
    #   kiwipiepy 0.24.1 sdist 16:08Z · win_amd64 바퀴 16:35Z · 실패 16:17Z·16:31Z). 공식 옵션 --prefer-binary(환경 PIP_PREFER_BINARY)
    #   은 바퀴가 있는 가장 새 판을 고른다. 판을 못박은 것(==)·--no-binary 는 그대로다. 회원이 따로 정했으면 그 값을 둔다.
    env.setdefault("PIP_PREFER_BINARY", "1")
    kw = {"cwd": cwd, "env": env, "stdin": subprocess.DEVNULL}
    if os.name != "nt":
        kw["start_new_session"] = True
    started = time.monotonic()
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(argv, stdout=out, stderr=None if stderr_inherit else err, **kw)
        rc, left = None, None
        try:
            rc = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            left = kill_tree(proc)
        finally:
            if proc.poll() is None and left is None:   # Ctrl+C 등으로 빠져나갈 때도 자식을 남기지 않는다
                left = kill_tree(proc)
        out.seek(0)
        err.seek(0)
        so = out.read().decode("utf-8", "replace")
        se = None if stderr_inherit else err.read().decode("utf-8", "replace")
    if rc is None:
        se = (se or "") + "\n[%d초 안에 끝나지 않아 끊었습니다]" % int(timeout or 0)
    elif rc != 0 and not so.strip() and not (se or "").strip():
        # 아무 말 없이 실패한 자식(밖에서 끊김 · 신호 · 보안 프로그램) — 회원 화면에 «(출력 없음)» 만 남지 않게 종료 코드를 적는다(신고 10-22 플리).
        if rc < 0:
            try:
                how = "신호 %s 로 끊겼습니다(밖에서 끝냄 · 메모리 부족 등)" % signal.Signals(-rc).name
            except ValueError:
                how = "신호 %d 로 끊겼습니다" % -rc
        else:
            how = "종료 코드 %d (0x%08X) · 출력 없음" % (rc, rc & 0xFFFFFFFF)
        se = "[%s 가 %s — %s초 만에]" % (os.path.basename(str(argv[0])) if argv else "?", how, round(time.monotonic() - started, 1))
    r = subprocess.CompletedProcess(argv, rc, so, se)
    r.timed_out = rc is None
    r.left_pid = left
    r.elapsed = round(time.monotonic() - started, 1)
    return r

def run_or_raise(argv, cwd=None, env=None, timeout=None, stderr_inherit=False):
    """run_bounded 와 같고, 시간을 넘기면(손주까지 끝낸 뒤) subprocess.TimeoutExpired 를 던진다 — 예전 subprocess.run(timeout=) 계약."""
    r = run_bounded(argv, cwd=cwd, env=env, timeout=timeout, stderr_inherit=stderr_inherit)
    if r.timed_out:
        raise subprocess.TimeoutExpired(argv, timeout, output=r.stdout, stderr=r.stderr)
    return r

def _run(argv, cwd=None, timeout=None):
    return run_or_raise(argv, cwd=cwd, env=_child_env(), timeout=timeout)

def root_of(cfg):
    return os.path.abspath(cfg["root"])

def venv_dir(cfg):
    return os.path.join(root_of(cfg), ".venv")

def venv_python(cfg):
    return venv_exe(venv_dir(cfg))

def _py_hint():
    if sys.platform == "win32":
        return "winget install -e --id Python.Python.3.12  (설치 뒤 터미널을 새로 연다)"
    return "brew install python@3.12"

def _ffmpeg_hint():
    if sys.platform == "win32":
        return "winget install -e --id Gyan.FFmpeg  (설치 뒤 터미널을 새로 연다 · PATH 에 ffmpeg 와 ffprobe 가 잡혀야 한다)"
    return "brew install ffmpeg  (ffmpeg 와 ffprobe 가 PATH 에 잡혀야 한다)"

def _agy_hint():
    return ("구글 Antigravity CLI(agy)를 설치하고 로그인한다(구독 계정) — 설치 뒤 터미널을 새로 열어 `agy --version` 이 되어야 한다")

def _read_json(path):
    try:
        with open(path, encoding="utf-8-sig") as fh:
            v = json.load(fh)
        return v if isinstance(v, (dict, list)) else None
    except (OSError, ValueError):
        return None

# ── 사전 점검 ──────────────────────────────────────────────────────────────
def preflight(cfg):
    root = root_of(cfg)
    missing, warnings = [], []
    # tools/review.py = 굽기 전 agy 판정(2026-10-22) · tools/scenes.py = 영상마다 한 대화 소재 고르기(2026-10-23) — 그것이 없는 옛 팩이면
    # «안 풀림» 으로 assets 에서 새 팩을 받게 한다.
    need = [os.path.join(root, "preset.py"), os.path.join(root, "tools", "render.py"), os.path.join(root, "tools", "review.py"),
            os.path.join(root, "tools", "scenes.py"),
            os.path.join(root, "config.json"), os.path.join(root, "requirements.txt"),
            os.path.join(root, *(cfg.get("skill") or "순서_안내.md").split("/"))]
    gone = [p for p in need if not os.path.isfile(p)]
    if gone:
        missing.append({"what": "썰쇼핑 파이프라인 팩이 안 풀렸습니다(없는 파일: " + " · ".join(gone[:4]) + ")", "pack": True})
        return {"ok": False, "missing": missing, "warnings": warnings}
    lo = tuple(cfg.get("min_python") or (3, 10))
    if tuple(sys.version_info[:2]) < lo:
        missing.append({"what": "파이썬 %s 은 너무 낮습니다(%d.%d 이상)" % (sys.version.split()[0], lo[0], lo[1]),
                        "how": _py_hint()})
        return {"ok": False, "missing": missing, "warnings": warnings}

    # 외부 도구 — 영상·소리 처리는 ffmpeg, 장면 고르기·재연 그림·검수는 agy(구글 Antigravity CLI 구독).
    for t in cfg.get("need_tools") or []:
        if not shutil.which(t):
            missing.append({"what": "%s 가 PATH 에 없습니다" % t,
                            "how": _agy_hint() if t == "agy" else _ffmpeg_hint()})

    # 전용 가상환경 — 시스템 파이썬을 더럽히지 않는다(맥 기본 파이썬은 pip 를 막는다).
    py = venv_python(cfg)

    mods = list(cfg.get("need_modules") or [])
    probe = "import " + ", ".join(mods) if mods else "pass"
    r = _run([py, "-c", probe], timeout=300) if py is not None else None
    if r is None or r.returncode != 0:
        # 부품을 깔아야 한다 — pip 를 부를 수 있는 가상환경부터(만들다 끊긴 venv 는 새로 · 서버 runner_venv.py · 신고 10-20)
        py, why = venv_with_pip([sys.executable], venv_dir(cfg))
        if py is None:
            missing.append({"what": "가상환경을 못 만들었습니다", "how": why})
            return {"ok": False, "missing": missing, "warnings": warnings}
        log("파이썬 의존을 깝니다 — 처음 한 번 잠깐 걸립니다(numpy · opencv-python · pillow · yt-dlp).")
        r2 = _run([py, "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r",
                   os.path.join(root, "requirements.txt")], timeout=3600)
        if r2.returncode != 0:
            missing.append({"what": "파이썬 의존 설치가 실패했습니다", "how": (r2.stderr or r2.stdout or "")[-900:]})
            return {"ok": False, "missing": missing, "warnings": warnings}
        r = _run([py, "-c", probe], timeout=300)
        if r.returncode != 0:
            missing.append({"what": "의존을 깔았는데도 import 가 안 됩니다", "how": (r.stderr or "")[-900:]})
            return {"ok": False, "missing": missing, "warnings": warnings}

    # 글꼴 — 팩 글꼴이 풀렸는지(조용히 대체하지 않는다).
    fdir = os.path.join(root, "assets", "fonts")
    have = set(os.listdir(fdir)) if os.path.isdir(fdir) else set()
    for f in cfg.get("fonts") or []:
        if f.get("file") not in have:
            # 제 받는 길(how)이 있는 글꼴은 사람이 깐다 · 없으면 팩 글꼴이다 — 서버가 assets 로 한 번 되돌린다(launch_pack_refetch).
            missing.append({"what": "글꼴 %s 가 없습니다" % f.get("file"), "how": f["how"]} if f.get("how")
                           else {"what": "글꼴 %s 가 없습니다" % f.get("file"), "pack": True})

    # 파이프라인 자신의 점검 — 프리셋과 **같은 자**로 잰다(도구·글꼴·효과음·열쇠 있는지 — 열쇠 값은 안 본다).
    r = _run([py, os.path.join(root, "preset.py"), "status"], cwd=root, timeout=300)
    try:
        st = json.loads(r.stdout) if (r.stdout or "").strip() else None
    except ValueError:
        st = None
    rows = []
    if not isinstance(st, dict):
        missing.append({"what": "점검(preset.py status)이 끝까지 못 돌았습니다",
                        "how": ((r.stderr or "") + (r.stdout or ""))[-900:]})
    else:
        if st.get("fonts") != "ok":
            missing.append({"what": "글꼴을 못 찾았습니다: %s" % st.get("fonts"), "pack": True})
        if not st.get("sfx"):
            missing.append({"what": "효과음(assets/sfx)이 없습니다", "pack": True})
        bad_mod = [m for m, ok in (st.get("modules") or {}).items() if not ok]
        if bad_mod:
            missing.append({"what": "파이썬 모듈이 없습니다: %s" % ", ".join(bad_mod), "how": "전용 가상환경에서 pip install -r requirements.txt"})
        for k, label in (("typecast_key", "타입캐스트(내레이션)"), ("speechmatics_key", "Speechmatics(자막 시각)")):
            if st.get(k) != "found":
                missing.append({"what": "%s 열쇠가 없습니다" % label,
                                "how": "사용자 홈 ~/.volcano/keys/%s 파일에 키 값만 넣는다(열쇠 값은 어디에도 적지 않는다)" % k.split("_")[0]})
        rows = [{"name": k, "value": str(st.get(k))[:80]} for k in ("python", "ffmpeg", "ffprobe", "agy", "typecast_key", "speechmatics_key")]
    return {"ok": not missing, "missing": missing, "warnings": warnings, "python": py, "root": root, "rows": rows}

# ── 결과 확인 ──────────────────────────────────────────────────────────────
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def _out_dir(ep, final_name):
    """편 출력 폴더 — 받은 것이 파일이면 그 부모, 폴더에 최종 영상이 없으면 `out/` 도 본다."""
    ep = os.path.abspath(ep)
    if os.path.isfile(ep):
        ep = os.path.dirname(ep)
    for cand in (ep, os.path.join(ep, "out")):
        if os.path.isfile(os.path.join(cand, final_name)):
            return cand
    return ep

def _open_path(p):
    """폴더를 탐색기 · 파인더로 연다(한 편이 끝났을 때). ★시험은 환경변수 SSEOL_OPEN_LOG 파일에 적기만 한다."""
    if not p or not os.path.isdir(p):
        return False
    try:
        rec = os.environ.get("SSEOL_OPEN_LOG")
        if rec:
            with open(rec, "a", encoding="utf-8") as fh:
                fh.write(p + "\n")
        elif sys.platform == "win32":
            os.startfile(p)
        elif sys.platform == "darwin":
            subprocess.run(["open", p], capture_output=True, timeout=30)
        else:
            subprocess.run(["xdg-open", p], capture_output=True, timeout=30)
        return True
    except Exception:
        return False

def check(cfg):
    ep = str(cfg.get("episode") or "")
    if not ep:
        return {"state": "failed", "why": ["편 프로젝트 폴더 경로가 비었습니다"]}
    fname, rname, cname = cfg.get("final_name") or "out.mp4", cfg.get("report_name") or "sseol_check.json", cfg.get("receipt_name") or "render_receipt.json"
    out = _out_dir(ep, fname)
    why = []
    mp4 = os.path.join(out, fname)
    if not os.path.isfile(mp4):
        why.append("최종 영상이 없습니다: %s — `python preset.py render <프로젝트>` 를 돌리세요" % fname)
        mp4 = None
    rep = _read_json(os.path.join(out, rname))
    if not isinstance(rep, dict):
        rep = None
        why.append("검사 기록이 없습니다: %s — `python preset.py check <프로젝트>` 를 돌리세요" % rname)
    receipt_ok = os.path.isfile(os.path.join(out, cname))
    if not receipt_ok:
        why.append("렌더 영수증이 없습니다: %s" % cname)
    sha = _sha256(mp4) if mp4 else None
    rows = []
    if rep:
        for r in rep.get("checks") or []:
            if isinstance(r, dict):
                rows.append({"id": r.get("id"), "name": str(r.get("name") or ""), "status": str(r.get("status") or "")})
    res = {"state": "failed", "work_dir": out, "final_mp4": mp4, "bytes": os.path.getsize(mp4) if mp4 else None,
           "video_sha256": sha, "report_sha256": (rep or {}).get("sha256"), "receipt": (rep or {}).get("receipt"),
           "checks": rows, "summary": (rep or {}).get("summary"), "technical_pass": (rep or {}).get("technical_pass"),
           "ready_for_delivery": (rep or {}).get("ready_for_delivery"), "why": why}
    # ★여기서는 «파일을 다 찾았나» 만 말한다 — 검사 칸이 통과인지는 서버가 다시 센다.
    res["state"] = "collected" if (mp4 and rep and not why) else "failed"
    by = {r["id"]: r["status"] for r in rows}
    clean = bool(rows) and all(v == "pass" for v in by.values())
    if res["state"] == "collected" and clean and cfg.get("open_done"):
        res["opened"] = _open_path(out)
    return res

# ── 진입 ──────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) < 2:
        emit({"ok": False, "why": "설정 파일 경로가 없습니다"})
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, ValueError) as e:
        emit({"ok": False, "why": "설정 파일을 못 읽었습니다: %s" % e})
    mode = cfg.get("mode")
    try:
        if mode == "preflight":
            emit(preflight(cfg))
        if mode == "check":
            emit(check(cfg))
        emit({"ok": False, "why": "모르는 mode: %r" % mode})
    except ENGINE_ENDS as e:   # 엔진 코드의 sys.exit(N)·Ctrl+C 도 답으로(src/runner_entry.py 한 자리)
        emit(engine_exit(e))
    except Exception as e:
        import traceback
        emit({"ok": False, "state": "failed", "why": "%s: %s" % (type(e).__name__, e),
              "traceback": traceback.format_exc()[-2000:]})

main()
