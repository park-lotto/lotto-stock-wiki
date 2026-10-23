# -*- coding: utf-8 -*-
"""볼케이노형 회원 라인 **개발 완주 도구**(관제 234·097 2026-10-21) — 서버 지시서(flow)를 같은 프로세스에서, 실행기(runner_ops)는 따로 띄우고,
판정(review)은 Claude CLI 가 회원 Claude 처럼 답한다. MCP·서버 HTTP 를 빼고 지시서·실행기·판정 고리만 끝까지 본다(진짜 회원 경로 = shortem_client live_episode).

    PYTHONUTF8=1 py tools/calcopy/hybrid/flow_dev.py --ref <벤치 URL> --version 키치잇판 --work <작업 폴더> [--cache <소스 캐시>] [--approve]
    → <작업 폴더>/flow_state.json · flow_log.jsonl · reviews/<id>/(질문·그림·답)
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


def answer(W: Path, rv: dict, log) -> dict:
    """review 하나 → Claude CLI(회원 Claude 대신). 그림은 파일로 두고 Read 로 보게 한다(회원 PC 는 MCP 이미지로 싣는다)."""
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
    a = ap.parse_args()
    W = Path(a.work); W.mkdir(parents=True, exist_ok=True)
    logf = W / "flow_log.jsonl"

    def log(o):
        o = {"t": time.strftime("%H:%M:%S"), **o}
        with logf.open("a", encoding="utf-8") as f:
            f.write(json.dumps(o, ensure_ascii=False) + "\n")
        print(json.dumps(o, ensure_ascii=False)[:300], flush=True)
    sp = W / "flow_state.json"
    st = json.loads(sp.read_text(encoding="utf-8")) if a.resume and sp.exists() else flow.start(a.ref, a.version, uuid.uuid4().hex[:12])
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "CALCOPY_CUSTOMER_MODE": "1", "SHORTEM_DEV": "1", "SHORTEM_YT_PROFILES": os.environ.get("SHORTEM_YT_PROFILES") or "mcp"}
    if a.cache:
        env["SHORTEM_SOURCE_CACHE"] = str(Path(a.cache).resolve())
    measure, replies, user = {}, {}, {}
    if a.resume and (W / "pending.json").exists():
        pend = json.loads((W / "pending.json").read_text(encoding="utf-8"))
        measure, replies = pend.get("measure") or {}, pend.get("replies") or {}
    calls, t_all = 0, time.time()
    while True:
        res = flow.step(st, measure, replies, user)
        calls += 1
        st = json.loads(json.dumps(res.pop("state"), ensure_ascii=False))      # 서버 payload 왕복과 같게(직렬화되는 것만)
        sp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
        log({"call": calls, "status": res["status"], "msg": res.get("message"), "phase": st.get("phase"),
             "do": [d["cmd"] for d in res.get("do") or []], "review": [r["id"] for r in res.get("review") or []], "reject": res.get("reject")})
        measure, replies, user = {}, {}, {}
        if res["status"] in ("done", "stop"):
            log({"end": res["status"], "why": res.get("why"), "fix": res.get("fix"), "video": res.get("video"), "calls": calls,
                 "min": round((time.time() - t_all) / 60, 1)})
            break
        if res["status"] == "execute":
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
                replies[rv["id"]] = answer(W / "job", rv, log)
        elif res["status"] == "wait_user":
            (W / "sign.json").write_text(json.dumps(res.get("wait"), ensure_ascii=False, indent=1), encoding="utf-8")
            if not a.approve:
                log({"wait": "사인 대기 — --resume --approve 로 이어 간다"})
                break
            user = {"approve": True}
        (W / "pending.json").write_text(json.dumps({"measure": measure, "replies": replies}, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
