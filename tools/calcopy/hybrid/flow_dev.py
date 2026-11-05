# -*- coding: utf-8 -*-
"""단계형 회원 라인 **개발 완주 도구**(관제 234·097 2026-10-21) — 서버 지시서(flow)를 같은 프로세스에서, 실행기(runner_ops)는 따로 띄우고,
판정(review)은 Claude CLI 가 회원 Claude 처럼 답한다. MCP·서버 HTTP 를 빼고 지시서·실행기·판정 고리만 끝까지 본다(진짜 회원 경로 = shortem_client live_episode).

    PYTHONUTF8=1 py tools/calcopy/hybrid/flow_dev.py --ref <벤치 URL> --version 키치잇판 --work <작업 폴더> [--cache <소스 캐시>] [--approve]
    → <작업 폴더>/flow_state.json · flow_log.jsonl · reviews/<id>/(질문·그림·답)

형식(관제 263 08): --fmt 를 주면 프리셋 장부(channel/프리셋.json)의 형식과 같은지 확인만 한다(다르면 flow.start 가 거절). 없으면 장부에서.
돈 0(--no-paid): 실행기에 SHORTEM_NO_PAID=1 — TTS 는 캐시만(없으면 계획·렌더가 멈춤), 스피치매틱스·VMake 안 부름.
  --tts-seed <렌더 폴더>: 그 폴더의 narr_full.mp3(+.tts.json)를 작업 폴더 <판>/render/ 로 미리 복사(같은 글이면 합성 0).
  --replay <폴더>: review id 가 '<파일 이름 앞부분>' 으로 시작하면 그 파일(JSON)을 답으로 쓴다 — Claude 에게도 묻고(answer_live.json) 쓰는 답은 replay
    (대본 답을 승인본으로 고정해 TTS 캐시를 쓰는 시험용. 묻는 질문·검사는 그대로).
사보타주: QG_FORCE_FAIL=1 을 환경에 주면 실행기가 품질 관문 결과를 강제로 ×(flow 가 고치기 2회 뒤 멈추는지).
"""
from __future__ import annotations

import argparse
import json
import re
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import flow  # noqa: E402

CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")


def ask_claude(prompt: str, cwd: Path, add_dir: Path, model: str, need, on_err=None) -> tuple:
    """Claude CLI 한 번(모양이 틀리면 한 번 더) → (JSON 객체 또는 None, 원문). review 답(answer)·엔진 줄 답하기(_queue_answerer)가 같이 부른다."""
    txt, a = "", None
    for _ in range(2):
        try:
            r = subprocess.run([CLAUDE, "-p", "--model", model, "--allowedTools", "Read,Glob,Grep,WebSearch,WebFetch", "--add-dir", str(add_dir),   # 작업 폴더 전체를 열어 볼 수 있게(10-27 '두뇌가 재료 없이 다시만')
                                "--output-format", "json", "--max-turns", "30"],
                               input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(cwd), timeout=1800)
            try:
                txt = json.loads(r.stdout).get("result") or ""
            except Exception:  # noqa: BLE001
                txt = r.stdout
        except Exception as e:  # noqa: BLE001
            txt = ""
            if on_err:
                on_err(f"{type(e).__name__}: {e}"[:300])
        s, e = txt.find("{"), txt.rfind("}")
        try:
            a = json.loads(txt[s:e + 1]) if s >= 0 else None
        except Exception:  # noqa: BLE001
            a = None
        if isinstance(a, dict) and all(k in a for k in need or []):
            break
    return (a if isinstance(a, dict) else None), txt


def answer(W: Path, rv: dict, log, replay: Path | None = None) -> dict:
    """review 하나 → Claude CLI(회원 Claude 대신). 그림은 파일로 두고 Read 로 보게 한다(회원 PC 는 MCP 이미지로 싣는다).
    replay 폴더에 이 review id 앞부분 이름의 JSON 이 있으면 Claude 답은 answer_live.json 으로 남기고 그 JSON 을 답으로 쓴다."""
    d = W / "reviews" / f"{time.strftime('%H%M%S')}_{re.sub(r'[^0-9A-Za-z가-힣._-]', '_', rv['id'])[:40]}"   # 소재 2편 칸 id 's1:ref_read' — ':' 는 윈도우 폴더 이름에 못 쓴다(10-27)
    d.mkdir(parents=True, exist_ok=True)
    texts, imgs = [], []
    for s in rv.get("show") or []:
        if s.get("text"):
            texts.append(s["text"])
        elif s.get("file") and (W / s["file"]).exists():
            dst = d / Path(s["file"]).name
            shutil.copyfile(W / s["file"], dst)
            imgs.append(str(dst))
    prompt = (rv["ask"] + ("\n\n" + "\n".join(texts) if texts else "") + ("\n\n그림 파일(Read 로 열어 본다):\n" + "\n".join(imgs) if imgs else "") +
              "\n\n답은 JSON 객체 하나만, 다른 글 없이.")
    (d / "ask.txt").write_text(prompt, encoding="utf-8")
    model = {"opus": "opus", "sonnet": "sonnet"}.get(os.environ.get("FLOW_DEV_MODEL") or rv.get("model") or "opus", "opus")   # FLOW_DEV_MODEL = 전 질문 모델 강제(opus|sonnet — 하이쿠 금지, 사장님 11-05)
    t0 = time.time()
    a, txt = ask_claude(prompt, d, W, model, rv.get("need") or [], lambda why: log({"review_error": rv["id"], "why": why}))
    a = a if isinstance(a, dict) else {"_raw": txt[:2000]}
    rf = next((f for f in sorted((replay or Path("/nonexistent")).glob("*.json"), key=lambda f: -len(f.stem)) if rv["id"].startswith(f.stem)), None) if replay else None
    if rf:
        (d / "answer_live.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
        a = json.loads(rf.read_text(encoding="utf-8"))
        log({"replay": rv["id"], "file": rf.name, "live_head": json.dumps(json.loads((d / "answer_live.json").read_text(encoding="utf-8")), ensure_ascii=False)[:160]})
    (d / "answer.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    log({"review": rv["id"], "model": model, "sec": round(time.time() - t0), "imgs": len(imgs), "head": json.dumps(a, ensure_ascii=False)[:200]})
    return a


# ── 회원 과제(채널 벤치마킹 2판 시험 편, review meta.kind=member_task) — 회원 PC 의 shortem_make 를 대신하는 손(개발 도구 몫, 관제 319) ──
#   회원 PC 길(shortem_client make_flow.js 내 프리셋 → 엔진 make.py · flow_driver.trialIn)과 같은 꼴: 임시 프리셋으로 엔진 길(calcopy_make start→choose→approve)을
#   이 시험기 프로세스에서 끝까지 돌리고, 결과 폴더(remake 출력 = 엔진 창고 make/<sid>/work/<topic_id>/제작)를 W/trial/t<try>_<sid> 로 옮겨 work_dir 로 답한다.
#   엔진의 AI 질문(CALCOPY_GEMINI_BACKEND=client → SHORTEM_LLM_QUEUE)은 _queue_answerer 가 Claude CLI 로 답한다(회원 Claude 대신).
#   목소리 = 대본 purpose=calcopy(voices.tts_for — 피쉬 차분한 해설가) · 소재 = 과제 source.channel(1판 규칙) · 사인 = 고객(--approve 처럼 자동).
#   서버(flow·flow_bench)·회원 경로(shortem_client) 코드는 안 바꾼다(Jev 해결 0.77·위험 0.21).
MAKE_PY = ROOT / "tools" / "calcopy" / "make.py"


def _run_make(args: list, env: dict) -> dict:
    """엔진 입구 make.py --json 한 번 → 마지막 줄 JSON(세션 status 또는 {error, code})."""
    r = subprocess.run([sys.executable, str(MAKE_PY), "--json", *args], cwd=str(ROOT), env=env, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    last = (r.stdout.strip().splitlines() or [""])[-1]
    try:
        out = json.loads(last)
    except ValueError:
        out = {"error": f"make.py 출력 없음(rc={r.returncode}): " + (r.stderr or last)[-400:], "code": "no_json"}
    return out if isinstance(out, dict) else {"error": f"make.py 출력 꼴: {last[:200]}", "code": "no_json"}


def _queue_prompt(d: Path, req: dict) -> str:
    texts = [x["text"] for x in req.get("parts") or [] if x.get("kind") == "text" and x.get("text")]
    imgs = [str(d / x["file"]) for x in req.get("parts") or [] if x.get("kind") == "image" and x.get("file") and (d / x["file"]).exists()]
    why = ""
    if (d / "error.json").exists():
        try:
            why = "\n\n앞 답이 틀렸다(다시 답하라): " + str(json.loads((d / "error.json").read_text(encoding="utf-8")).get("why"))[:400]
        except (OSError, ValueError):
            why = ""
    return (str(req.get("prompt") or "") + ("\n\n" + "\n".join(texts) if texts else "") +
            ("\n\n그림 파일(Read 로 열어 본다):\n" + "\n".join(imgs) if imgs else "") + why + "\n\n답은 JSON 객체 하나만, 다른 글 없이.")


def _queue_answer_one(d: Path, log, ask=None) -> bool:
    """줄 요청 하나(request.json) → Claude CLI → answer.json(임시 이름 → 바꿔 달기, client_llm._wait 가 다 써진 뒤 읽는다). 답을 썼으면 True."""
    try:
        req = json.loads((d / "request.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    model = {"opus": "opus", "sonnet": "sonnet"}.get(os.environ.get("FLOW_DEV_MODEL") or req.get("tier") or "opus", "opus")    # 하이쿠 금지 — 모르는 등급은 opus
    t0 = time.time()
    a, txt = (ask or ask_claude)(_queue_prompt(d, req), d, d, model, [])
    a = a if isinstance(a, dict) else {"_raw": txt[:2000]}
    tmp = d / "answer.json.tmp"
    tmp.write_text(json.dumps(a, ensure_ascii=False), encoding="utf-8")
    tmp.replace(d / "answer.json")
    log({"engine_ask": req.get("tag"), "model": model, "sec": round(time.time() - t0), "head": json.dumps(a, ensure_ascii=False)[:160]})
    return True


def _queue_answerer(q: Path, stop: threading.Event, log, workers: int = 2, ask=None):
    """엔진 줄 폴더(SHORTEM_LLM_QUEUE)를 지켜 새 요청·다시 묻기(error.json 이 새로 생김)를 Claude CLI 로 답한다 — 회원 PC 에서 회원 Claude 가 하던 일."""
    busy: set = set()
    seen: dict = {}        # 폴더 이름 → 마지막으로 답한 때의 error.json 시각(0 = 첫 답)
    lock = threading.Lock()

    def job(d: Path, key):
        try:
            _queue_answer_one(d, log, ask)
        except Exception as e:  # noqa: BLE001 — 답 못 한 이유를 남긴다(엔진은 client_timeout 으로 멈춘다)
            log({"engine_ask_error": d.name, "why": f"{type(e).__name__}: {e}"[:300]})
        finally:
            with lock:
                busy.discard(d.name)
                seen[d.name] = key

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while not stop.is_set():
            for d in (sorted(q.glob("*")) if q.is_dir() else []):
                if not (d / "request.json").exists() or (d / "done").exists() or (d / "answer.json").exists():
                    continue
                ef = d / "error.json"
                key = ef.stat().st_mtime if ef.exists() else 0
                with lock:
                    if d.name in busy or seen.get(d.name) == key:
                        continue
                    busy.add(d.name)
                pool.submit(job, d, key)
            stop.wait(1.0)


def _bench_ids(job: Path) -> list:
    """시험기 상태(W/flow_state.json bm.videos)의 벤치 편 id — 소재·재료에서 뺄 것(G10)."""
    try:
        st = json.loads((job.parent / "flow_state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(v["id"]) for v in ((st.get("bm") or {}).get("videos") or []) if v.get("id")]


def _bench_in_materials(work: Path, bench_ids: list) -> list:
    """재료.json 컷·샷의 src 중 벤치 편(G10 · rules._bench_src 한 곳)."""
    from tools.calcopy.hybrid import rules as RU
    try:
        M = json.loads((work / "재료.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    srcs = {str(x.get("src") or "") for x in (M.get("shots") or []) if isinstance(x, dict)}
    srcs |= {str(c.get("src") or "") for v in (M.get("cuts") or {}).values() for c in (v if isinstance(v, list) else [v]) if isinstance(c, dict)}
    return sorted(x for x in srcs if x and RU._bench_src(x, bench_ids))


def member_task(job: Path, rv: dict, log, env: dict, run=None, answerer=None, eng_root: Path | None = None) -> dict:
    """회원 과제 한 건 → 엔진 길로 1편 → {work_dir: 'trial/t<try>_<sid>', ok: True} / {work_dir: '', ok: False, why}."""
    run = run or _run_make
    answerer = answerer or _queue_answerer
    m = rv.get("meta") or {}
    pr = m.get("preset") or {}
    n_try = int(m.get("try") or 0)

    def bad(why):
        log({"member_task": "fail", "why": str(why)[:300]})
        return {"work_dir": "", "ok": False, "why": str(why)[:300]}
    if m.get("kind") != "member_task" or not pr.get("dir") or pr.get("dir") != f"channel/{pr.get('slug')}/preset/{pr.get('style')}":
        return bad("과제의 프리셋 칸 꼴이 다르다")
    pdir = (job / pr["dir"]).resolve()
    if not (pdir / "frame.json").exists() or not (pdir / "manifest.json").exists():
        return bad(f"작업 폴더에 프리셋이 없다: {pr['dir']}")
    data = job.parent / "trial_data"
    q = data / "_q"
    q.mkdir(parents=True, exist_ok=True)
    env2 = {**env, "CALCOPY_GEMINI_BACKEND": "client", "CALCOPY_CUSTOMER_MODE": "1", "SHORTEM_LLM_QUEUE": str(q), "CALCOPY_DATA_DIR": str(data)}
    ch = str((m.get("source") or {}).get("channel") or "")
    if ch:          # 회원 PC make_flow.originalsFile 과 같은 꼴 — 벤치 채널이 소재 채널(영상 파일은 안 넣는다)
        of = data / "originals.json"
        # 벤치 채널 = 클립 채널(role bench) — G10 원본 추적을 통과한 편만 후보, 벤치 편 id 는 소재·재료에서 뺀다(관제 319, topic_find.channel_candidates)
        bench_ids = _bench_ids(job)
        of.write_text(json.dumps({"note": "시험 편 소재 채널(flow_dev 회원 과제) — 벤치 클립 채널", "bench_ids": bench_ids,
                                  "channels": [{"platform": "youtube", "url": ch, "role": "bench"}]}, ensure_ascii=False), encoding="utf-8")
        env2["CALCOPY_ORIGINALS_FILE"] = str(of)
    # 회원 PC 프리셋 빌리기(preset_rent.js)와 같은 꼴 — 내 프리셋 폴더 channel/<slug> 통째를 엔진 루트 channel/<slug> 로 복사하고 상대 경로로 돌린 뒤 지운다.
    #   manifest 의 뜯기 경로가 엔진 루트 기준 상대 경로라 W/job 절대 경로로 주면 load_preset 이 뜯기를 못 찾는다(11-06 실측 '프리셋에 뜯기/틀 없음', Jev 0.96·해결 0.51)
    eng = Path(eng_root or ROOT)
    rent = eng / "channel" / pr["slug"]
    if rent.exists():
        return bad(f"엔진 루트에 같은 이름 프리셋 폴더가 이미 있다(남의 것일 수 있어 덮지 않는다): {rent}")
    shutil.copytree(job / "channel" / pr["slug"], rent)
    (rent / ".flow_dev_rent").write_text(str(job), encoding="utf-8")      # 이 시험기가 빌린 표식 — 지울 때 이것만 지운다
    stop = threading.Event()
    th = threading.Thread(target=answerer, args=(q, stop, log), daemon=True)
    th.start()
    t0 = time.time()
    try:
        S = run(["start", "--preset", pr["dir"], "--pack", "1"], env2)
        log({"member_task": "start", "state": S.get("state"), "sid": S.get("sid"), "n_cand": len(S.get("candidates") or []), "error": S.get("error")})
        if S.get("error") and not S.get("sid"):
            return bad("시작 못 함: " + str(S["error"]))
        if S.get("state") == "candidates":
            if not S.get("candidates"):
                return bad("소재 후보 0개(채널 " + ch + ")")
            S = run(["choose", S["sid"], "1"], env2)      # 회원이 안 고르면 1번(지침 5장 — 10분 답 없으면 1번)
            log({"member_task": "choose", "state": S.get("state"), "topic": S.get("topic_id"), "error": S.get("error")})
        if S.get("state") != "plan_review":
            return bad(f"계획까지 못 감({S.get('state')}): {S.get('error') or (S.get('log') or [''])[-1]}")
        work = Path(S["merged_preset"]).parent / "work" / str(S["topic_id"]) / "제작"
        sp = work / "대본.json"
        if not sp.exists():
            return bad(f"대본이 없다: {sp}")
        sj = json.loads(sp.read_text(encoding="utf-8"))
        sj["purpose"] = m.get("purpose") or "calcopy"      # 과제 지시 '대본 purpose=calcopy' — 목소리는 voices.tts_for 한 곳이 정한다
        sp.write_text(json.dumps(sj, ensure_ascii=False, indent=1), encoding="utf-8")
        bad_src = _bench_in_materials(work, _bench_ids(job))
        if bad_src:
            return bad(f"벤치 편이 재료에 들어 있다(원본에서만 규칙): {bad_src}")
        sid = S["sid"]
        S = run(["approve", sid, "--by", "고객"], env2)
        log({"member_task": "approve", "state": S.get("state"), "error": S.get("error"), "min": round((time.time() - t0) / 60, 1)})
        if not (work / "final.mp4").exists():
            return bad(f"완성본 없음({S.get('state')}): {S.get('error') or (S.get('log') or [''])[-1]}")
        T = job / "trial"
        shutil.rmtree(T, ignore_errors=True)         # 늘 한 벌(flow_driver.trialIn 과 같다)
        T.mkdir(parents=True, exist_ok=True)
        leaf = f"t{n_try}_{sid}"
        shutil.move(str(work), str(T / leaf))
        log({"member_task": "done", "work_dir": f"trial/{leaf}", "min": round((time.time() - t0) / 60, 1)})
        return {"work_dir": f"trial/{leaf}", "ok": True}
    finally:
        stop.set()
        th.join(timeout=5)
        if (rent / ".flow_dev_rent").exists():
            shutil.rmtree(rent, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", help="프리셋 제작의 벤치 URL(--bench 가 없을 때 필수)")
    ap.add_argument("--bench", help="채널 벤치마킹 2판(관제 319) — 채널 주소. 서버 claude_flow bench_start 와 같은 flow.start_bench 로 시작")
    ap.add_argument("--bench-name", default="내 프리셋")
    ap.add_argument("--bench-n", type=int, default=3)
    ap.add_argument("--version", default="키치잇판")
    ap.add_argument("--work", required=True)
    ap.add_argument("--cache")
    ap.add_argument("--approve", action="store_true", help="대본 사인을 자동으로(개발)")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--retry", action="store_true", help="멈춘 편(stopped)을 다시 시도(서버 retry 와 같다 — 멈춘 단계부터)")
    ap.add_argument("--fmt", help="형식(연예인형·해외원본형·쇼핑형·레시피형) — 프리셋 장부와 다르면 거절")
    ap.add_argument("--single", action="store_true", help="둘째 소재 없이 그 소재 하나만(원본 찾기 워커 of_worker)")
    ap.add_argument("--no-paid", action="store_true", help="돈 드는 호출 0(TTS 캐시만·스피치매틱스·VMake 안 부름)")
    ap.add_argument("--tts-seed", help="narr_full.mp3(+.tts.json) 가 있는 렌더 폴더 — 작업 폴더 <판>/render/ 로 복사")
    ap.add_argument("--replay", help="review 답 고정 폴더(<review id 앞부분>.json)")
    ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--stop-at", default="", help="이 세부 단계(쉼표 목록)에 닿으면 멈춤 — 예 thumb = 장면 맞추기 통과 직후(10-27 사장님 '원본·대본·장면 구간만 계속')")
    ap.add_argument("--from-plan", help="(시험) 대본 답 JSON {대본, 재료, 근거_md} — --resume 상태에 대본 검사 없이 넣고 계획부터(TTS 캐시가 있는 승인본으로 렌더·검사)")
    a = ap.parse_args()
    W = Path(a.work); W.mkdir(parents=True, exist_ok=True)
    logf = W / "flow_log.jsonl"

    def log(o):
        o = {"t": time.strftime("%H:%M:%S"), **o}
        with logf.open("a", encoding="utf-8") as f:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
        print(json.dumps(o, ensure_ascii=False)[:300], flush=True)
    sp = W / "flow_state.json"
    if not a.ref and not a.bench and not (a.resume and sp.exists()):
        raise SystemExit("--ref 또는 --bench 가 필요합니다")
    if a.resume and sp.exists():
        st = json.loads(sp.read_text(encoding="utf-8"))
    elif a.bench:
        st = flow.start_bench(a.bench, [], a.bench_name, uuid.uuid4().hex[:12], a.bench_n)
    else:
        st = flow.start(a.ref, a.version, uuid.uuid4().hex[:12], fmt=a.fmt)
    log({"start": st.get("fmt"), "slug": st.get("slug"), "version": a.version, "ref": a.ref or a.bench, "stages": [t for _, t in flow.FORMAT_STAGES.get(st.get("fmt") or "연예인형", flow.STAGES)]})
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "CALCOPY_CUSTOMER_MODE": "1", "SHORTEM_DEV": "1", "SHORTEM_YT_PROFILES": os.environ.get("SHORTEM_YT_PROFILES") or "mcp"}
    if a.cache:
        env["SHORTEM_SOURCE_CACHE"] = str(Path(a.cache).resolve())
    if a.no_paid:
        env["SHORTEM_NO_PAID"] = "1"
    if a.single:
        env["SHORTEM_SINGLE_SOURCE"] = "1"
    if a.tts_seed:
        rd = W / "job" / a.version / "render"
        rd.mkdir(parents=True, exist_ok=True)
        for n in ("narr_full.mp3", "narr_full.mp3.tts.json"):
            if (Path(a.tts_seed) / n).exists() and not (rd / n).exists():
                shutil.copyfile(Path(a.tts_seed) / n, rd / n)
    replay = Path(a.replay) if a.replay else None
    counts = {"do": 0, "review": 0, "calls": 0}
    if a.from_plan:
        if not a.resume:
            raise SystemExit("--from-plan 은 --resume 과 같이(원본·샷 표가 있는 상태 위에)")
        do = flow.dev_inject_script(st, json.loads(Path(a.from_plan).read_text(encoding="utf-8")))
        (W / "_do.json").write_text(json.dumps(do, ensure_ascii=False), encoding="utf-8")
        r = subprocess.run([sys.executable, "-m", "tools.calcopy.hybrid.runner_ops", str(W / "job"), str(W / "_do.json")], cwd=str(ROOT), env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        log({"from_plan": a.from_plan, "write": (r.stdout.strip().splitlines() or [""])[-1][:200]})
        sp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        measure, replies = {}, {}
    measure, replies, user = {}, {}, {}
    if a.resume and not a.from_plan and (W / "pending.json").exists():
        pend = json.loads((W / "pending.json").read_text(encoding="utf-8"))
        measure, replies = pend.get("measure") or {}, pend.get("replies") or {}
    calls, t_all = 0, time.time()
    if a.retry:
        user = {"retry": True}
    while True:
        res = flow.step(st, measure, replies, user)
        calls += 1
        if calls > a.max_calls:
            log({"end": "max_calls", "calls": calls}); break
        st = json.loads(json.dumps(res.pop("state"), ensure_ascii=False))      # 서버 payload 왕복과 같게(직렬화되는 것만)
        sp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        log({"call": calls, "status": res["status"], "msg": res.get("message"), "phase": st.get("phase"),
             "do": [d["cmd"] for d in res.get("do") or []], "review": [r["id"] for r in res.get("review") or []], "reject": res.get("reject")})
        measure, replies, user = {}, {}, {}
        if any(str(st.get("phase") or "").startswith(x) for x in a.stop_at.split(",") if x):     # 앞부분 맞춤 — thumb = thumb_sheet·thumb_got(10-27 정확히 같은 이름만 봐서 렌더까지 감)
            log({"end": "stop_at", "phase": st.get("phase"), "calls": calls, "min": round((time.time() - t_all) / 60, 1),
                 "do_n": counts["do"], "review_n": counts["review"]})
            break
        if res["status"] in ("done", "stop"):
            log({"end": res["status"], "why": res.get("why"), "fix": res.get("fix"), "video": res.get("video"), "calls": calls,
                 "min": round((time.time() - t_all) / 60, 1), "do_n": counts["do"], "review_n": counts["review"], "stage": res.get("stage")})
            break
        if res["status"] == "execute":
            counts["do"] += len(res["do"])
            dof = W / "_do.json"
            dof.write_text(json.dumps(res["do"], ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable, "-m", "tools.calcopy.hybrid.runner_ops", str(W / "job"), str(dof)], cwd=str(ROOT), env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace")
            (W / "runner_stderr.txt").open("a", encoding="utf-8").write(r.stderr[-20000:])
            last = (r.stdout.strip().splitlines() or ["{}"])[-1]
            try:
                measure = json.loads(last)
            except ValueError:
                measure = {d["id"]: {"error": "실행기 출력 없음: " + r.stderr[-300:]} for d in res["do"]}
            log({"measure": {k: (v.get("error") if isinstance(v, dict) and v.get("error") else "ok") for k, v in measure.items()}})
        elif res["status"] in ("review", "reject"):
            for rv in res.get("review") or []:
                counts["review"] += 1
                if (rv.get("meta") or {}).get("kind") == "member_task":      # 회원 과제 = 회원 PC 의 shortem_make 를 대신(엔진 길 1편)
                    replies[rv["id"]] = member_task(W / "job", rv, log, env)
                else:
                    replies[rv["id"]] = answer(W / "job", rv, log, replay)
        elif res["status"] == "wait_user":
            (W / "sign.json").write_text(json.dumps(res.get("wait"), ensure_ascii=False, indent=1), encoding="utf-8")
            if not a.approve:
                log({"wait": "사인 대기 — --resume --approve 로 이어 간다"})
                break
            user = {"approve": True}
        (W / "pending.json").write_text(json.dumps({"measure": measure, "replies": replies}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
