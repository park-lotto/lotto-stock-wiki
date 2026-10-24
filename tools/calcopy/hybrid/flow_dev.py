# -*- coding: utf-8 -*-
"""볼케이노형 회원 라인 **개발 완주 도구**(관제 234·097 2026-10-21) — 서버 지시서(flow)를 같은 프로세스에서, 실행기(runner_ops)는 따로 띄우고,
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
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import flow  # noqa: E402

CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or str(Path.home() / ".local" / "bin" / "claude.exe")


def answer(W: Path, rv: dict, log, replay: Path | None = None) -> dict:
    """review 하나 → Claude CLI(회원 Claude 대신). 그림은 파일로 두고 Read 로 보게 한다(회원 PC 는 MCP 이미지로 싣는다).
    replay 폴더에 이 review id 앞부분 이름의 JSON 이 있으면 Claude 답은 answer_live.json 으로 남기고 그 JSON 을 답으로 쓴다."""
    d = W / "reviews" / f"{time.strftime('%H%M%S')}_{rv['id'][:40]}"
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
    model = {"opus": "opus", "sonnet": "sonnet"}.get(rv.get("model") or "opus", "opus")
    t0 = time.time()
    txt = ""
    for _ in range(2):
        try:
            r = subprocess.run([CLAUDE, "-p", "--model", model, "--allowedTools", "Read,WebSearch,WebFetch", "--output-format", "json", "--max-turns", "30"],
                               input=prompt, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(d), timeout=1800)
            try:
                txt = json.loads(r.stdout).get("result") or ""
            except Exception:  # noqa: BLE001
                txt = r.stdout
        except Exception as e:  # noqa: BLE001
            txt = ""
            log({"review_error": rv["id"], "why": f"{type(e).__name__}: {e}"[:300]})
        s, e = txt.find("{"), txt.rfind("}")
        try:
            a = json.loads(txt[s:e + 1]) if s >= 0 else None
        except Exception:  # noqa: BLE001
            a = None
        if isinstance(a, dict) and all(k in a for k in rv.get("need") or []):
            break
    a = a if isinstance(a, dict) else {"_raw": txt[:2000]}
    rf = next((f for f in sorted((replay or Path("/nonexistent")).glob("*.json"), key=lambda f: -len(f.stem)) if rv["id"].startswith(f.stem)), None) if replay else None
    if rf:
        (d / "answer_live.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
        a = json.loads(rf.read_text(encoding="utf-8"))
        log({"replay": rv["id"], "file": rf.name, "live_head": json.dumps(json.loads((d / "answer_live.json").read_text(encoding="utf-8")), ensure_ascii=False)[:160]})
    (d / "answer.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")
    log({"review": rv["id"], "model": model, "sec": round(time.time() - t0), "imgs": len(imgs), "head": json.dumps(a, ensure_ascii=False)[:200]})
    return a


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--version", default="키치잇판")
    ap.add_argument("--work", required=True)
    ap.add_argument("--cache")
    ap.add_argument("--approve", action="store_true", help="대본 사인을 자동으로(개발)")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--fmt", help="형식(연예인형·해외원본형·쇼핑형·레시피형) — 프리셋 장부와 다르면 거절")
    ap.add_argument("--no-paid", action="store_true", help="돈 드는 호출 0(TTS 캐시만·스피치매틱스·VMake 안 부름)")
    ap.add_argument("--tts-seed", help="narr_full.mp3(+.tts.json) 가 있는 렌더 폴더 — 작업 폴더 <판>/render/ 로 복사")
    ap.add_argument("--replay", help="review 답 고정 폴더(<review id 앞부분>.json)")
    ap.add_argument("--max-calls", type=int, default=400)
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
    st = json.loads(sp.read_text(encoding="utf-8")) if a.resume and sp.exists() else flow.start(a.ref, a.version, uuid.uuid4().hex[:12], fmt=a.fmt)
    log({"start": st.get("fmt"), "slug": st.get("slug"), "version": a.version, "ref": a.ref, "stages": [t for _, t in flow.FORMAT_STAGES.get(st.get("fmt") or "연예인형", flow.STAGES)]})
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "CALCOPY_CUSTOMER_MODE": "1", "SHORTEM_DEV": "1", "SHORTEM_YT_PROFILES": os.environ.get("SHORTEM_YT_PROFILES") or "mcp"}
    if a.cache:
        env["SHORTEM_SOURCE_CACHE"] = str(Path(a.cache).resolve())
    if a.no_paid:
        env["SHORTEM_NO_PAID"] = "1"
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
    if a.resume and (W / "pending.json").exists():
        pend = json.loads((W / "pending.json").read_text(encoding="utf-8"))
        measure, replies = pend.get("measure") or {}, pend.get("replies") or {}
    calls, t_all = 0, time.time()
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
