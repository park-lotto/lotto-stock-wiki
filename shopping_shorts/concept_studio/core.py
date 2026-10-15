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


# ── 컨셉·설정 ─────────────────────────────────────────────────────────
def list_concepts():
    out = []
    for f in sorted(os.listdir(PRESETS)):
        if f.endswith(".json"):
            c = load_concept(f[:-5])
            out.append({k: c.get(k) for k in ("id", "name", "description", "source_kind", "source_hint")})
    return out


def load_concept(cid):
    p = os.path.join(PRESETS, f"{cid}.json")
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
    exe = getattr(sys, "_base_executable", "") or sys.executable
    with open(logp, "a", encoding="utf-8") as log:
        log.write(f"[spawn] {time.strftime('%H:%M:%S')} exe={exe}\n")
    if os.name != "nt":
        env = dict(os.environ, PYTHONUTF8="1", PYTHONPATH=root + os.pathsep + os.environ.get("PYTHONPATH", ""))
        subprocess.Popen([exe, "-m", "shopping_shorts.concept_studio.core", "run", job_id], cwd=root,
                         stdout=open(logp, "a"), stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         start_new_session=True, env=env)
        return
    eng = os.environ.get("SHOTTEM_ENGINE_ROOT", "")
    cmd = (f'cmd /c "set PYTHONUTF8=1&& set PYTHONIOENCODING=utf-8&& set PYTHONPATH={root}&& '
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


def confirm_script(job_id, ok=True, note=""):
    st = status(job_id)
    if st.get("state") != "confirm_script":
        raise ValueError(f"대본 확인 단계가 아니다(지금: {st.get('state')})")
    if not ok:
        # 다시 쓰기: 대본 단계부터 되돌리고 메모를 손님 AI 요청에 붙인다
        pipeline, _, _ = _engine()
        pipeline.reset_to(_wd(job_id), "script")
        _wj(os.path.join(_wd(job_id), "host_answers.json"), {})
        _set(job_id, state="queued", confirmed=False, rewrite_note=note)
    else:
        _set(job_id, state="queued", confirmed=True)
    _spawn(job_id)


def resume(job_id):
    status(job_id)
    _set(job_id, state="queued")
    _spawn(job_id)


def status(job_id):
    st = _rj(os.path.join(_wd(job_id), "studio_status.json"))
    if st is None:
        raise KeyError(f"없는 작업: {job_id}")
    return st


def _script_view(script):
    t = script.get("title") or {}
    lines = [f"[헤드라인] {' / '.join(str(v) for v in t.values() if isinstance(v, str))}"]
    for i, g in enumerate(script.get("groups") or [], 1):
        lines.append(f"{i:02d}. {g.get('text', '')}")
    return "\n".join(lines)


def run(job_id):
    """작업 프로세스 본체 — 멈출 자리(대본 요청·대본 확인·실패·완료)까지 단계를 민다."""
    pipeline, providers, registry = _engine()
    wd = _wd(job_id)
    job = _rj(os.path.join(wd, "studio_job.json"))
    c = load_concept(job["concept"])
    registry.use(c["engine"]["channel"])
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
