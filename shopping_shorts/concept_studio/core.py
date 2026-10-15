# -*- coding: utf-8 -*-
"""컨셉 스튜디오 핵심 — 판단의 주인은 이 파일 하나(관제 213, 0순위-C).

  load_concept / list_concepts  컨셉 프리셋 읽기
  resolve_settings              컨셉 기본값 ⊕ 고객 내 팩
  start_job / submit_script / confirm_script / status   작업 진행(Claude형·버텍스형 공용)

작업은 고객 PC의 ~/.shottem/jobs/<id>/ 에서 돈다. 무거운 단계(소재·렌더)는 따로 뜬
작업 프로세스(`python -m shopping_shorts.concept_studio.core run <id>`)가 하고,
MCP 도구는 상태 파일만 읽고 쓴다 — Claude 데스크톱 도구 호출 시간 제한에 안 걸린다.

대본은 '손님 AI'(Claude형: 고객 Claude)가 쓴다. 엔진이 대본을 청하면 HostLLM 이
그 요청을 host_pending.json 에 남기고 멈춘다 → Claude가 submit_script 로 답을 넣으면
같은 요청 지문으로 답을 찾아 이어 간다. 엔진의 반려(린터)도 그대로 다음 요청이 된다.

★시험 단계(P0): 엔진(channelkit·hotpeople)은 아직 트랙 `칼카피숏템엔진`에만 있다.
  SHOTTEM_ENGINE_ROOT(기본: 이웃 트랙 폴더)를 sys.path 앞에 둔다. 상품화 때 설치팩에 묶는다.
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PRESETS = os.path.join(HERE, "presets")
HOME = os.environ.get("SHOTTEM_HOME") or os.path.join(os.path.expanduser("~"), ".shottem")
JOBS = os.path.join(HOME, "jobs")
SETTINGS = os.path.join(HOME, "studio.json")      # 웹 스튜디오가 내려줄 '내 설정'의 자리(P0은 로컬 파일)


class NeedHost(Exception):
    """엔진이 손님 AI에게 글을 청한다 — 요청은 host_pending.json 에 있다."""


# ── 엔진 ──────────────────────────────────────────────────────────────
def engine_root():
    r = os.environ.get("SHOTTEM_ENGINE_ROOT")
    if not r:
        r = os.path.normpath(os.path.join(HERE, "..", "..", "..", "칼카피숏템엔진"))
    return r


def _engine():
    # 엔진도 같은 패키지 이름(shopping_shorts)이라 sys.path 앞에 넣으면 concept_studio 가 가려진다
    # → 패키지 검색 경로(__path__) 뒤에 엔진 쪽 폴더를 덧붙인다(없는 모듈만 엔진에서 찾는다).
    import shopping_shorts
    p = os.path.join(engine_root(), "shopping_shorts")
    if not os.path.isdir(os.path.join(p, "channelkit")):
        raise RuntimeError(f"엔진을 못 찾았다: {p} (SHOTTEM_ENGINE_ROOT 확인)")
    if p not in shopping_shorts.__path__:
        shopping_shorts.__path__.append(p)
    from shopping_shorts.channelkit import pipeline, providers, registry  # noqa: E402
    return pipeline, providers, registry


# ── 웹 컨셉 스튜디오와 동기화 ─────────────────────────────────────────
SYNCED = os.path.join(HOME, "concepts")          # 서버에서 받은 컨셉(있으면 동봉본보다 먼저)
PACKS = os.path.join(HOME, "packs")              # 서버에서 받은 팩 파일 <종류>/<이름>


def studio_conn():
    """(주소, 연결 코드) — 설치팩 설정 칸(환경변수)에서. 둘 중 하나라도 없으면 동기화 없이 동봉본으로 돈다."""
    return (os.environ.get("SHOTTEM_STUDIO_URL", "").rstrip("/"), os.environ.get("SHOTTEM_STUDIO_TOKEN", "").strip())


def _get(path, stream=False):
    import requests
    url, tok = studio_conn()
    r = requests.get(url + path, headers={"X-Studio-Token": tok}, timeout=120, stream=stream)
    if r.status_code == 401:
        raise PermissionError("연결 코드가 틀렸거나 만료됐다 — 웹 컨셉 스튜디오에서 새 코드를 받아 설치팩 설정에 넣으세요")
    r.raise_for_status()
    return r


def sync(kinds=("font", "sfx", "bgm", "meme")):
    """웹 스튜디오의 컨셉·내 설정·팩을 고객 PC로 받는다. 지문(sha256)이 같은 파일은 다시 안 받는다."""
    url, tok = studio_conn()
    if not (url and tok):
        return {"ok": False, "why": "스튜디오 주소·연결 코드가 설치팩 설정에 없다 — 동봉 컨셉으로만 돈다"}
    me = _get("/api/studio/mcp/me").json()
    os.makedirs(SYNCED, exist_ok=True)
    for c in me.get("concepts") or []:
        _wj(os.path.join(SYNCED, f"{c['id']}.json"), c)
    _wj(SETTINGS, me.get("settings") or {})
    packs = _get("/api/studio/mcp/packs").json().get("packs") or {}
    got, same = 0, 0
    for kind in kinds:
        d = os.path.join(PACKS, kind)
        os.makedirs(d, exist_ok=True)
        for e in packs.get(kind) or []:
            p = os.path.join(d, os.path.basename(e["name"]))
            if os.path.exists(p) and os.path.getsize(p) == e["bytes"] and _file_sha(p) == e["sha256"]:
                same += 1
                continue
            r = _get(e["url"], stream=True)
            h = hashlib.sha256()
            with open(p + ".part", "wb") as fh:
                for b in r.iter_content(1 << 20):
                    fh.write(b)
                    h.update(b)
            if h.hexdigest() != e["sha256"]:
                os.remove(p + ".part")
                raise IOError(f"받은 파일 지문이 다르다: {kind}/{e['name']}")
            os.replace(p + ".part", p)
            got += 1
    return {"ok": True, "customer_id": me.get("customer_id"), "concepts": [c["id"] for c in me.get("concepts") or []],
            "downloaded": got, "unchanged": same, "packs": {k: len(packs.get(k) or []) for k in kinds}}


def _file_sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def hello():
    """일 시작 점검 — 무엇이 준비됐고 무엇이 빠졌나(빠진 것은 고칠 방법과 함께). 그다음 설정·팩 받기."""
    import shutil
    checks = []

    def ck(name, ok, fix=""):
        checks.append({"항목": name, "ok": bool(ok), **({"고칠 것": fix} if not ok else {})})
    url, tok = studio_conn()
    ck("웹 스튜디오 연결 정보", url and tok, "설치팩 설정(Claude 설정 → 확장 프로그램 → 숏템 컨셉 스튜디오 → 구성)에 주소·연결 코드")
    ck("제미니 키", os.environ.get("GEMINI_API_KEY", "").strip(), "설치팩 설정에 제미니 API 키")
    ck("ffmpeg", shutil.which("ffmpeg") and shutil.which("ffprobe"), "설치팩을 다시 켜면 처음 한 번 받는다")
    ck("yt-dlp", shutil.which("yt-dlp"), "설치팩을 다시 켜면 설치된다")
    try:
        _engine()
        ck("영상 엔진", True)
    except Exception as e:  # noqa: BLE001
        ck("영상 엔진", False, repr(e)[:150])
    synced = {"ok": False, "why": "연결 정보 없음"}
    if url and tok:
        try:
            synced = sync()
        except Exception as e:  # noqa: BLE001 — 받기 실패는 이유를 그대로 보여 준다(동봉 컨셉으로는 계속 된다)
            synced = {"ok": False, "why": str(e)[:200]}
        ck("설정·팩 받기", synced.get("ok"), synced.get("why", ""))
    jobs = sorted(os.listdir(JOBS), reverse=True)[:3] if os.path.isdir(JOBS) else []
    recent = []
    for j in jobs:
        try:
            s = status(j)
            recent.append({"job_id": j, "seed": s.get("seed"), "state": s.get("state")})
        except Exception:  # noqa: BLE001
            pass
    return {"ready": all(c["ok"] for c in checks), "checks": checks,
            "packs": synced.get("packs"), "concepts": list_concepts(), "recent_jobs": recent}


# ── 컨셉·설정 ─────────────────────────────────────────────────────────
def _concept_files():
    """{id: 경로} — 동봉본 위에 서버에서 받은 것을 덮는다(서버가 최신)."""
    out = {}
    for d in (PRESETS, SYNCED):
        if os.path.isdir(d):
            for f in sorted(os.listdir(d)):
                if f.endswith(".json"):
                    out[f[:-5]] = os.path.join(d, f)
    return out


def list_concepts():
    out = []
    for cid in _concept_files():
        c = load_concept(cid)
        out.append({k: c.get(k) for k in ("id", "name", "description", "source_kind", "source_hint")})
    return out


def load_concept(cid):
    p = _concept_files().get(cid, "")
    if not os.path.exists(p):
        raise KeyError(f"없는 컨셉: {cid} (있는 것: {[x['id'] for x in list_concepts()]})")
    with open(p, encoding="utf-8") as fh:
        c = json.load(fh)
    for k in ("id", "source_kind", "engine"):
        if k not in c:
            raise ValueError(f"컨셉 {cid}: '{k}' 칸이 없다")
    return c


def my_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return {}


def choose_bgm(settings, seed):
    """내 팩 배경음 → (경로, 시작초) 또는 None. 판단 주인은 여기 하나(엔진의 pick_bgm 자리에 끼운다).
    settings.bgm: 곡 id(예 'beggin') / 'auto'(받은 곡 중 소재 글자로 하나) / 'off'·없음(엔진 기본)."""
    want = (settings or {}).get("bgm") or ""
    d = os.path.join(PACKS, "bgm")
    if want in ("", "off") or not os.path.isdir(d):
        return None
    have = sorted(f for f in os.listdir(d) if f.endswith(".mp3"))
    if not have:
        return None
    if want == "auto":
        import random
        f = random.Random(seed or "").choice(have)
    else:
        f = want + ".mp3"
        if f not in have:
            return None
    return _looped(os.path.join(d, f)), 0.0


BGM_MIN_SEC = 240   # 엔진은 영상을 배경음 길이에서 끊는다 — 팩 곡은 17~60초라 반복해 늘려 넘긴다
                    # (실측 2026-10-15: 17초 곡을 골라 63초 영상이 17.4초로 잘렸다)


def _looped(src):
    out = os.path.join(PACKS, "bgm_loop", os.path.splitext(os.path.basename(src))[0] + f"_{BGM_MIN_SEC}s.wav")
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(src):
        return out
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-stream_loop", "-1", "-i", src, "-t", str(BGM_MIN_SEC),
                        "-ar", "48000", "-ac", "2", out + ".tmp.wav"], capture_output=True, text=True, timeout=300)
    if r.returncode or not os.path.exists(out + ".tmp.wav"):
        raise RuntimeError(f"배경음 늘리기 실패: {r.stderr[-200:]}")
    os.replace(out + ".tmp.wav", out)
    return out


def resolve_settings(concept, mine=None):
    """컨셉 기본값 위에 고객 내 팩을 얹는다 — 고객이 바꿀 수 있는 칸만."""
    mine = (mine if mine is not None else my_settings()).get("packs", {}).get(concept["id"], {})
    s = dict(concept.get("defaults") or {})
    for k in concept.get("customer_can_change") or []:
        if k in mine:
            s[k] = mine[k]
    return s


# ── 손님 AI ──────────────────────────────────────────────────────────
def _key(prompt):
    return hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:16]


def _rj(p, default=None):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default


def _wj(p, obj):
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


class HostLLM:
    tag = "host"

    def __init__(self, wd):
        self.wd = wd

    def __call__(self, prompt):
        ans = _rj(os.path.join(self.wd, "host_answers.json"), {})
        k = _key(prompt)
        if k in ans:
            return ans[k]
        _wj(os.path.join(self.wd, "host_pending.json"), {"key": k, "prompt": prompt, "at": time.time()})
        raise NeedHost(k)


# ── 작업 ─────────────────────────────────────────────────────────────
def _wd(job_id):
    return os.path.join(JOBS, job_id)


def _set(job_id, **kv):
    p = os.path.join(_wd(job_id), "studio_status.json")
    st = _rj(p, {})
    st.update(kv, updated=time.time())
    _wj(p, st)
    return st


def start_job(concept_id, seed):
    c = load_concept(concept_id)
    if not seed or not str(seed).strip():
        raise ValueError(f"소재가 비었다 — {c.get('source_hint', '')}")
    job_id = time.strftime("%m%d_%H%M%S_") + uuid.uuid4().hex[:4]
    os.makedirs(_wd(job_id), exist_ok=True)
    _wj(os.path.join(_wd(job_id), "studio_job.json"),
        {"concept": c["id"], "seed": seed, "settings": resolve_settings(c), "created": time.time()})
    _set(job_id, state="queued", step=None, concept=c["id"], seed=seed)
    _spawn(job_id)
    return job_id


def _real_path(p):
    """스토어(MSIX)판 Claude 데스크톱은 %APPDATA% 를 앱 안에서만 보이게 가상화한다 — 실제 파일은
    %LOCALAPPDATA%\\Packages\\<앱>\\LocalCache\\Roaming\\… 에 있다. 앱 밖(WMI)에서 띄울 땐 실제 경로를 줘야 한다.
    (실측 2026-10-15: 가상 경로로 띄우자 Win32_Process.Create 가 8 을 돌려줬다)"""
    if os.name != "nt":
        return p
    ap = os.environ.get("APPDATA", "")
    if not ap or not os.path.normcase(p).startswith(os.path.normcase(ap)):
        return p
    rel = os.path.relpath(p, ap)
    import glob
    for cand in glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", "*", "LocalCache", "Roaming", rel)):
        return cand
    return p


def _spawn(job_id):
    """작업 프로세스를 MCP 연결과 **분리해서** 띄운다.

    ★MCP 클라이언트(mcp SDK·Claude 데스크톱)는 서버를 'KILL_ON_JOB_CLOSE 작업 개체'에 넣는다.
      그 안에서 Popen 한 자식은 연결이 끝나는 순간 같이 죽는다 — DETACHED·BREAKAWAY 플래그로도
      안 빠졌다(실측 2026-10-15: pid 가 1초 안에 사라지고 worker.log 0줄).
      → 윈도우에선 WMI(Win32_Process.Create)로 띄운다. WMI 서비스가 만든 프로세스라 작업 개체 밖이다.
    """
    wd = _wd(job_id)
    logp = os.path.join(wd, "worker.log")
    root = os.path.normpath(os.path.join(HERE, "..", ".."))
    exe = sys.executable          # WMI 로 띄우면 작업 개체 밖이라 venv 런처도 산다 — 의존성이 있는 이 파이썬 그대로
    # 키·설정은 명령줄(프로세스 목록에 보인다) 대신 작업 폴더 파일로 넘긴다 → run() 첫 줄이 읽는다
    _wj(os.path.join(wd, ".worker_env.json"),
        {k: os.pathsep.join(_real_path(x) for x in v.split(os.pathsep)) for k, v in os.environ.items()
         if k.startswith(_PASS_ENV + ("SHORTEM_",))})
    with open(logp, "a", encoding="utf-8") as log:
        log.write(f"[spawn] {time.strftime('%H:%M:%S')} exe={exe}\n")
    inside_app = os.name == "nt" and _real_path(HERE) != HERE
    if os.name != "nt" or inside_app:
        # 스토어판 Claude 데스크톱 안: 파일이 가상 폴더라 앱 밖(WMI)에선 못 띄운다(실측 코드 8).
        # 데스크톱의 MCP 서버는 앱이 켜진 동안 살아 있으니 그 자식으로 띄운다(앱을 끄면 같이 멈춤 → studio_resume).
        env = dict(os.environ, PYTHONUTF8="1", PYTHONPATH=root + os.pathsep + os.environ.get("PYTHONPATH", ""))
        flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW) if os.name == "nt" else 0
        subprocess.Popen([exe, "-m", "shopping_shorts.concept_studio.core", "run", job_id], cwd=root,
                         stdout=open(logp, "a", encoding="utf-8"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         env=env, creationflags=flags, **({} if os.name == "nt" else {"start_new_session": True}))
        with open(logp, "a", encoding="utf-8") as log:
            log.write("[spawn] 앱 안에서 띄움\n")
        return
    eng = _real_path(os.environ.get("SHOTTEM_ENGINE_ROOT", ""))
    exe, root = _real_path(exe), _real_path(root)
    cmd = (f'cmd /c "set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& set PYTHONPATH={root}&& set SHOTTEM_HOME={HOME}&& '
           + (f'set SHOTTEM_ENGINE_ROOT={eng}&& ' if eng else "")
           + f'"{exe}" -m shopping_shorts.concept_studio.core run {job_id} >> "{logp}" 2>&1"')
    ps = ("$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments "
          "@{CommandLine=$env:SHOTTEM_CMD; CurrentDirectory=$env:SHOTTEM_CWD}; "
          "Write-Output ($r.ReturnValue.ToString() + ' ' + $r.ProcessId)")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                       capture_output=True, text=True, timeout=60,
                       env=dict(os.environ, SHOTTEM_CMD=cmd, SHOTTEM_CWD=root),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    out = (r.stdout or "").strip()
    with open(logp, "a", encoding="utf-8") as log:
        log.write(f"[spawn] wmi → {out or r.stderr.strip()[:300]}\n")
    if not out.startswith("0 "):
        _set(job_id, state="failed", fail={"where": "spawn", "why": (out or r.stderr)[:300]})
        raise RuntimeError(f"작업 프로세스를 못 띄웠다: {out or r.stderr[:200]}")


def submit_script(job_id, text):
    wd = _wd(job_id)
    pend = _rj(os.path.join(wd, "host_pending.json"))
    if not pend:
        raise ValueError("지금 대본을 기다리는 중이 아니다 — status 로 상태를 보라")
    ans = _rj(os.path.join(wd, "host_answers.json"), {})
    ans[pend["key"]] = text
    _wj(os.path.join(wd, "host_answers.json"), ans)
    os.remove(os.path.join(wd, "host_pending.json"))
    _set(job_id, state="queued", prompt=None)
    _spawn(job_id)


def reset_to(job_id, step):
    """이 단계부터 다시. ★엔진 단계표는 채널마다 다르다 — 채널을 먼저 고르지 않으면 기본(뇌전구) 표로
    되돌려 다음 단계 계산이 깨진다(실측 2026-10-15: 'frames' is not in list)."""
    pipeline, _, registry = _engine()
    job = _rj(os.path.join(_wd(job_id), "studio_job.json"))
    registry.use(load_concept(job["concept"])["engine"]["channel"])
    pipeline.reset_to(_wd(job_id), step)


def confirm_script(job_id, ok=True, note=""):
    st = status(job_id)
    if st.get("state") != "confirm_script":
        raise ValueError(f"대본 확인 단계가 아니다(지금: {st.get('state')})")
    if not ok:
        # 다시 쓰기: 대본 단계부터 되돌리고 메모를 손님 AI 요청에 붙인다
        reset_to(job_id, "script")
        _wj(os.path.join(_wd(job_id), "host_answers.json"), {})
        _set(job_id, state="queued", confirmed=False, rewrite_note=note)
    else:
        _set(job_id, state="queued", confirmed=True)
    _spawn(job_id)


ALIVE_SEC = 60          # 작업 프로세스가 15초마다 숨을 쉰다 — 60초 안에 쉬었으면 살아 있는 것


def _alive(job_id):
    """살아 있는 작업 프로세스의 pid 또는 None. ★이어 돌리기·새로 띄우기는 이걸 보고 겹치지 않게 한다
    (실측 2026-10-15: 소재 수집이 느린 걸 '멈춤'으로 보고 이어 돌려 같은 작업에 프로세스 2개가 돌았다)."""
    a = _rj(os.path.join(_wd(job_id), "worker.alive"))
    if a and time.time() - a.get("at", 0) < ALIVE_SEC:
        return a.get("pid")
    return None


def _heartbeat(job_id):
    import threading

    def beat():
        while True:
            _wj(os.path.join(_wd(job_id), "worker.alive"), {"pid": os.getpid(), "at": time.time()})
            time.sleep(15)
    threading.Thread(target=beat, daemon=True).start()


def _progress(job_id):
    """단계 안의 진행 — 상태 파일은 단계가 바뀔 때만 갱신돼 '22분째 그대로 = 멈춤'으로 오해됐다(실측 2026-10-15:
    그동안 소재 영상 9편을 받고 얼굴 분석 중이었다). 작업 폴더에서 가장 최근에 만들어진 파일 시각과 개수로 보여 준다."""
    wd = _wd(job_id)
    newest, n_vid, n_scan = 0.0, 0, 0
    for dp, _, fs in os.walk(wd):
        for f in fs:
            if f in ("studio_status.json", "worker.alive", "worker.log") or f.endswith(".tmp"):
                continue
            try:
                newest = max(newest, os.path.getmtime(os.path.join(dp, f)))
            except OSError:
                continue
            if f.endswith(".mp4") and os.path.basename(dp) == "videos":
                n_vid += 1
            elif f.endswith(".faces.npz"):
                n_scan += 1
    ago = int(time.time() - newest) if newest else None
    return {"last_file_sec_ago": ago, "videos_downloaded": n_vid, "videos_scanned": n_scan,
            "hint": "새 파일이 계속 생기면 진행 중이다(소재 영상 1편 받기·분석에 수 분)" if ago is not None else ""}


def resume(job_id):
    st = status(job_id)
    if st.get("alive"):
        return dict(st, note="이미 돌고 있다 — 멈춘 게 아니라 진행 중이다(다시 띄우지 않았다)")
    _set(job_id, state="queued")
    _spawn(job_id)
    return status(job_id)


def status(job_id):
    st = _rj(os.path.join(_wd(job_id), "studio_status.json"))
    if st is None:
        raise KeyError(f"없는 작업: {job_id}")
    pid = _alive(job_id)
    st["alive"] = bool(pid)
    st["progress"] = _progress(job_id)
    if st.get("state") in ("running", "queued"):
        st["note"] = ("진행 중(작업 프로세스 살아 있음) — 소재 수집·렌더는 수 분~십수 분 걸린다. 다시 띄우지 마라"
                      if pid else "작업 프로세스가 없다 — 앱을 껐다 켰으면 studio_resume")
    return st


def _script_view(script):
    t = script.get("title") or {}
    lines = [f"[헤드라인] {' / '.join(str(v) for v in t.values() if isinstance(v, str))}"]
    for i, g in enumerate(script.get("groups") or [], 1):
        lines.append(f"{i:02d}. {g.get('text', '')}")
    return "\n".join(lines)


_PASS_ENV = ("SHOTTEM_", "GEMINI_", "GOOGLE_", "TYPECAST_", "HOTPEOPLE_", "BRAINBULB_", "PATH")


def run(job_id):
    """작업 프로세스 본체 — 멈출 자리(대본 요청·대본 확인·실패·완료)까지 단계를 민다."""
    for k, v in (_rj(os.path.join(_wd(job_id), ".worker_env.json"), {}) or {}).items():
        os.environ[k] = v
    other = _alive(job_id)
    if other and other != os.getpid():
        print(f"[run] 이미 pid {other} 가 이 작업을 돌리는 중 — 겹치지 않게 그냥 끝낸다")
        return 0
    _heartbeat(job_id)
    pipeline, providers, registry = _engine()
    wd = _wd(job_id)
    job = _rj(os.path.join(wd, "studio_job.json"))
    c = load_concept(job["concept"])
    registry.use(c["engine"]["channel"])
    if c["engine"]["channel"] == "hotpeople":
        # 배경음은 내 팩에서(웹 스튜디오 설정). 고를 게 없으면 엔진 기본(원본 곡 폴더)으로 둔다.
        from shopping_shorts.channel_presets.hotpeople import render as _hr
        _orig = _hr.pick_bgm
        _hr.pick_bgm = lambda seed_text, _s=job.get("settings"), _o=_orig: choose_bgm(_s, seed_text) or _o(seed_text)
    st = status(job_id)
    llm = HostLLM(wd)
    note = st.get("rewrite_note")
    if note:
        base = llm

        def llm(prompt, _b=base, _n=note):            # 확인 단계에서 받은 고칠 점을 요청 끝에 붙인다
            return _b(prompt + "\n\n[고객이 고쳐 달라고 한 점] " + _n)
    try:
        reviewer = [providers.gemini_reader(), providers.gemini_reader("gemini-2.5-flash")]
    except Exception as e:  # noqa: BLE001 — 키가 없으면 장면 고르기 단계에서 멈추게 이유를 남긴다
        reviewer = None
        _set(job_id, warn=f"제미니 키 없음: {e!r}"[:200])
    while True:
        step = pipeline.next_step(wd)
        if step is None:
            d = pipeline.load(wd)["data"]
            rv = d.get("review") or {}
            _set(job_id, state="done", step=None, final=rv.get("final"), duration=rv.get("duration"),
                 sheet=rv.get("sheet"))
            return 0
        if step == "footage" and not status(job_id).get("confirmed"):
            s = pipeline.load(wd)["data"]["script"]["script"]
            _set(job_id, state="confirm_script", step=step, script=_script_view(s))
            return 0
        _set(job_id, state="running", step=step)
        r = pipeline.run_step(wd, step, source_text=job["seed"], llm=llm, reviewer=reviewer,
                              channel=c["engine"]["channel"])
        if r["status"] == "ok":
            continue
        pend = _rj(os.path.join(wd, "host_pending.json"))
        if pend and "NeedHost" in json.dumps(r.get("fail") or {}, ensure_ascii=False):
            _set(job_id, state="need_script", step=step, prompt=pend["prompt"])
            return 0
        _set(job_id, state="failed", step=step, fail=r.get("fail") or r.get("need"))
        return 1


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "run":
        sys.exit(run(sys.argv[2]))
    print("사용: python -m shopping_shorts.concept_studio.core run <job_id>")
