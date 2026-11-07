# -*- coding: utf-8 -*-
"""꾸러미 실행기 — 서버 없이 이 PC 에서 단계를 진행한다.
  python run.py start <영상주소> [제품이름]   새 편 시작
  python run.py go                         막힐 때까지 진행
  python run.py pending                    Claude 가 답할 질문 목록
  python run.py answer <질문id> <답.json>   답 넣기
  python run.py approve | retry            사람 확인 통과 · 멈춘 단계 다시
  python run.py revise "L3=고칠 문장"        완성 뒤 줄 고치기
  python run.py status                     지금 상태
"""
import json, os, re, subprocess, sys, time, uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / "engine"
HOME = ROOT / "data"
AI = HOME / "ai"
JOBS = HOME / "jobs"
VERSION = json.loads((ROOT / "pack.json").read_text(encoding="utf-8"))["version"]
KEY_ENV = {"typecast": "TYPECAST_API_KEY", "elevenlabs": "ELEVENLABS_API_KEY", "coupang_access": "COUPANG_ACCESS_KEY", "coupang_secret": "COUPANG_SECRET_KEY",
           "vmake": "VMAKE_API_KEY", "speechmatics": "SPEECHMATICS_API_KEY"}
TOOLDIRS = ["tools/ffmpeg", "tools/ytdlp", "tools/python", "tools/python/Scripts"]


def engine_env():
    e = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONPATH=str(ENGINE), CALCOPY_GEMINI_BACKEND="client", CALCOPY_CUSTOMER_MODE="1",
             SHORTEM_LLM_QUEUE=str(AI / "_runner"), CALCOPY_DATA_DIR=str(HOME / "store"), CALCOPY_PACK_ROOT=str(HOME / "packs"), SHORTEM_HOME=str(HOME),
             CHANNEL_FIND_CACHE=str(HOME / "cache"), YTDLP_PROXY_SLOTS="0", INSTAGRAM_SCRAPER="playwright", SHORTEM_BROWSER_OFFSCREEN="1")
    e["PATH"] = os.pathsep.join(str(ROOT / d) for d in TOOLDIRS if (ROOT / d).exists()) + os.pathsep + e.get("PATH", "")
    for name, env in KEY_ENV.items():
        p = HOME / "keys" / name
        if p.exists(): e[env] = p.read_text(encoding="utf-8").strip()
    if e.get("SPEECHMATICS_API_KEY"): e["SHORTEM_ASR"] = "speechmatics"
    c = HOME / "sessions" / "cookies.txt"
    if c.exists():
        e["YTDLP_COOKIES_YOUTUBE"] = e["YTDLP_COOKIES_TIKTOK"] = str(c)
        e["YTDLP_COOKIES_INSTAGRAM"] = str(c)
    w = ROOT / "models" / "whisper"
    if w.exists(): e["SHORTEM_WHISPER_DIR"] = str(w)
    return e


ENV = engine_env()
os.environ.update(ENV)   # 판단(flow)과 실행(runner)이 같은 환경을 본다
for d in (AI / "_runner", JOBS, HOME / "keys", HOME / "sessions", HOME / "store", HOME / "packs", HOME / "cache"):
    d.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ENGINE))
os.chdir(ENGINE)


def cur_path():
    return HOME / "current.json"


def load():
    if not cur_path().exists(): sys.exit("진행 중인 편이 없습니다. run.py start <영상주소>")
    return json.loads(cur_path().read_text(encoding="utf-8"))


def save(f):
    tmp = cur_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(f, ensure_ascii=False), encoding="utf-8")
    tmp.replace(cur_path())


def req_id(tag):
    return re.sub(r"[^0-9A-Za-z가-힣_-]", "_", str(tag))[:60] + "-" + uuid.uuid4().hex[:6]


def post_review(f, rv):
    """review 하나 → 질문 폴더. 그림은 복사하고 글은 그대로 둔다."""
    job = JOBS / f["sid"] / "job"
    d = AI / ("flow_" + f["sid"]) / (time.strftime("%Y%m%d-%H%M%S-") + req_id(rv["id"]))
    d.mkdir(parents=True, exist_ok=True)
    parts, n = [], 0
    for s in rv.get("show") or []:
        if s.get("text"):
            parts.append({"kind": "text", "text": str(s["text"])})
        elif s.get("file"):
            src = (job / s["file"]).resolve()
            if src.is_file() and str(src).startswith(str(job.resolve())):
                name = f"p{n:02d}{src.suffix or '.jpg'}"; n += 1
                (d / name).write_bytes(src.read_bytes()); parts.append({"kind": "image", "file": name})
            else:
                parts.append({"kind": "text", "text": "(그림을 준비하지 못함)"})
    req = {"id": d.name, "tag": rv["id"], "tier": rv.get("model") or "opus", "prompt": rv.get("ask"), "parts": parts, "need": rv.get("need") or [], "made_at": time.time()}
    if rv.get("meta"): req["meta"] = rv["meta"]
    (d / "request.tmp").write_text(json.dumps(req, ensure_ascii=False), encoding="utf-8")
    (d / "request.tmp").replace(d / "request.json")
    return {"rid": rv["id"], "dir": str(d), "need": req["need"], "bad": 0}


def collect(f):
    out = {}
    for q in f.get("asks") or []:
        a = Path(q["dir"]) / "answer.json"
        if not a.exists(): return None
        try:
            j = json.loads(a.read_text(encoding="utf-8"))
        except ValueError:
            j = None
        miss = [k for k in q["need"] if k not in j] if isinstance(j, dict) else ["JSON 객체"]
        if miss and q["bad"] < 2:
            q["bad"] += 1
            a.rename(a.with_name(f"answer.bad{q['bad']}.json"))
            (a.parent / "error.json").write_text(json.dumps({"why": "답에 칸이 없다: " + ", ".join(miss)}, ensure_ascii=False), encoding="utf-8")
            save(f)
            return None
        out[q["rid"]] = j or {}
    for q in f.get("asks") or []:
        (Path(q["dir"]) / "done").write_text("", encoding="utf-8")
    return out


def start_runner(f, do):
    job = JOBS / f["sid"] / "job"; job.mkdir(parents=True, exist_ok=True)
    w = JOBS / f["sid"]
    (w / "do.json").write_text(json.dumps(do, ensure_ascii=False), encoding="utf-8")
    for n in ("out.json", "err.log"):
        if (w / n).exists(): (w / n).unlink()
    p = subprocess.Popen([sys.executable, "-X", "utf8", "-m", "tools.calcopy.hybrid.runner_ops", str(job), str(w / "do.json")], cwd=ENGINE, env=ENV,
                         stdout=open(w / "out.json", "w", encoding="utf-8"), stderr=open(w / "err.log", "w", encoding="utf-8"), creationflags=0x00000200 if os.name == "nt" else 0)
    f["pid"] = p.pid


def alive(pid):
    if os.name == "nt":
        return str(pid) in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, errors="replace").stdout
    try:
        os.kill(pid, 0); return True
    except OSError:
        return False


def pending():
    out = []
    for d in sorted(AI.glob("*/*")):
        if d.is_dir() and (d / "request.json").exists() and not (d / "answer.json").exists() and not (d / "done").exists():
            try:
                r = json.loads((d / "request.json").read_text(encoding="utf-8"))
            except ValueError:
                continue
            err = d / "error.json"
            out.append({"id": d.name, "dir": str(d), "tag": r.get("tag"), "need": r.get("need"), "retry_why": json.loads(err.read_text(encoding="utf-8")).get("why") if err.exists() else None})
    return out


def show(f):
    print(json.dumps({k: f.get(k) for k in ("status", "message", "stage", "wait", "video", "title", "note", "why", "fix") if f.get(k)}, ensure_ascii=False, indent=1))
    p = pending()
    if p: print(f"질문 {len(p)}건 — run.py pending")


def absorb(f, res):
    st = res.pop("state", None)
    if st is not None:
        (JOBS / f["sid"] / "state.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    f.update(status=res.get("status"), message=res.get("message") or f.get("message"), stage=res.get("stage") or f.get("stage"), asks=None, wait=None)
    s = f["status"]
    if s == "execute":
        start_runner(f, res.get("do") or [])
    elif s in ("review", "reject"):
        f["asks"] = [post_review(f, r) for r in res.get("review") or []]
    elif s == "wait_user":
        f["wait"] = res.get("wait")
    elif s == "done":
        f.update(video=res.get("video"), title=res.get("title"), note=res.get("note"))
    else:
        f.update(why=res.get("why") or res.get("message") or "멈췄습니다", fix=res.get("fix") or "")
    save(f)


def call(f, measure=None, replies=None, user=None):
    from tools.calcopy.hybrid import flow
    st = json.loads((JOBS / f["sid"] / "state.json").read_text(encoding="utf-8"))
    u = {"approve": False, "retry": False, "reclean": False, "revise": ""}
    u.update(user or {})
    absorb(f, flow.step(st, measure or {}, replies or {}, u))


def go(deadline=600):
    f = load(); t0 = time.time()
    for _ in range(400):
        s = f.get("status")
        if s == "execute":
            if alive(f.get("pid")):
                if pending() or time.time() - t0 > deadline: break
                time.sleep(3); continue
            w = JOBS / f["sid"]
            raw = (w / "out.json").read_text(encoding="utf-8", errors="replace").strip()
            try:
                m = json.loads(raw.splitlines()[-1]) if raw else {}
            except ValueError:
                m = {}
            if not m:
                tail = (w / "err.log").read_text(encoding="utf-8", errors="replace")[-1500:]
                f.update(status="error", why="실행 단계가 끝까지 못 갔습니다", fix="run.py retry", log=tail); save(f); break
            call(f, measure=m)
        elif s in ("review", "reject"):
            r = collect(f)
            if r is None: break
            call(f, replies=r)
        else:
            break
    f = load(); show(f)


def main():
    a = sys.argv[1:] or ["status"]
    c = a[0]
    if c == "start":
        from tools.calcopy.hybrid import flow
        url = a[1]; product = a[2] if len(a) > 2 else ""
        why = flow.source_url_problem(url)
        if why: sys.exit(why)
        sid = uuid.uuid4().hex[:12]; f = {"sid": sid, "url": url, "status": "start"}
        (JOBS / sid / "job").mkdir(parents=True, exist_ok=True)
        st = flow.start(url, VERSION, sid, product) if product else flow.start(url, VERSION, sid)
        (JOBS / sid / "state.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
        save(f); call(f); go()
    elif c == "go": go()
    elif c == "pending": print(json.dumps(pending(), ensure_ascii=False, indent=1))
    elif c == "answer":
        d = next((Path(p["dir"]) for p in pending() if p["id"] == a[1]), None)
        if d is None: sys.exit("그 질문이 없습니다")
        j = json.loads(Path(a[2]).read_text(encoding="utf-8"))
        (d / "answer.tmp").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        (d / "answer.tmp").replace(d / "answer.json")
        print("넣음", d.name)
    elif c == "approve": f = load(); call(f, user={"approve": True}); go()
    elif c == "retry": f = load(); call(f, user={"retry": True}); go()
    elif c == "revise": f = load(); call(f, user={"revise": " ".join(a[1:])[:500]}); go()
    else: show(load())


if __name__ == "__main__":
    main()
