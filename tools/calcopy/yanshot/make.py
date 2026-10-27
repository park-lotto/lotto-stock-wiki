# -*- coding: utf-8 -*-
"""얜샷템 한 명령 제작 — 벤치 쇼츠 URL → 바탕화면(칼카피영상/얜샷템) 완성본 (관제 097, 2026-10-17).

    PYTHONUTF8=1 py tools/calcopy/yanshot/make.py <벤치 URL> --slug <소재> [--until bench|trace|script|plan|make|check] [--redo <단계>]

단계(각 단계 = 함수 하나): bench → trace → script → plan → make → check. 단계 결과는 작업 폴더
C:/숏템_칼카피/yanshottem/<소재>/{bench,trace,script,plan,make,check}.json 에 남고, 있으면 건너뛴다(TTS 재과금 0).
--redo <단계> 는 그 단계부터 다시. 단계별 소요 초 = 작업 폴더 make_log.json. 실패하면 이유를 찍고 멈춘다(rc=1).
편 문서(대본.json·재료.json·근거.md·계획.md·계획 시트·B표.md·1초 시트)는 작업 폴더 doc/ + 사본 tools/calcopy/yanshot/runs/<소재>/.
"""
from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tools.calcopy.yanshot.common import ROOT, WORK_BASE, StageError, Timer, jload  # noqa: E402

STAGES = ["bench", "trace", "script", "plan", "make", "check"]
OUT = {"bench": "bench.json", "trace": "trace.json", "script": "script.json", "plan": "plan.json", "make": "make.json", "check": "check.json"}
EXTRA = {"plan": ["look.json"], "make": ["render/narr_mina.mp3"]}   # --redo 때 같이 지울 캐시(미나 mp3 는 make 를 redo 할 때만)


def run(url: str, slug: str, until: str = "check", redo: str | None = None, log=print) -> dict:
    from tools.calcopy.yanshot import bench as st_bench, check as st_check, plan as st_plan, render as st_make, script as st_script, trace as st_trace
    from tools.calcopy.engine import gemini_free as G
    W = WORK_BASE / slug
    W.mkdir(parents=True, exist_ok=True)
    if redo:
        for s in STAGES[STAGES.index(redo):]:
            for f in [OUT[s]] + (EXTRA.get(s, []) if s == redo else []):
                p = W / f
                if p.exists():
                    p.unlink()
    tm = Timer(W / "make_log.json")
    tm.cur.update({"url": url, "slug": slug, "until": until, "redo": redo})
    ctx: dict = {}
    for s in STAGES:
        out = W / OUT[s]
        t0 = time.time()
        n0 = len(G.CALLS)
        if out.exists():
            ctx[s] = jload(out)
            tm.done(s, 0.0, "캐시")
        else:
            try:
                if s == "bench":
                    ctx[s] = st_bench.bench(url, W, log=log)
                elif s == "trace":
                    ctx[s] = st_trace.trace(ctx["bench"], W, log=log)
                elif s == "script":
                    ctx[s] = st_script.script(ctx["bench"], ctx["trace"], W, log=log)
                    (W / "doc").mkdir(exist_ok=True)
                    st_script.write_grounds(ctx["bench"], ctx["trace"], ctx[s], W / "doc" / "근거.md")
                elif s == "plan":
                    ctx[s] = st_plan.plan(ctx["bench"], ctx["trace"], ctx["script"], W, log=log)
                elif s == "make":
                    ctx[s] = st_make.make(ctx["bench"], ctx["trace"], ctx["script"], ctx["plan"], W, log=log)
                elif s == "check":
                    ctx[s] = st_check.check(ctx["bench"], ctx["trace"], ctx["script"], ctx["plan"], ctx["make"], W, slug, log=log)
            except StageError as e:
                tm.done(s, time.time() - t0, f"실패: {e}")
                copy_docs(W, slug)
                raise
            tm.done(s, time.time() - t0)
            tm.cur["stages"][s]["gemini"] = [{k: c.get(k) for k in ("tag", "model", "sec", "ok", "failed")} for c in G.CALLS[n0:]]
            tm.save()
            log(f"[{s}] {time.time() - t0:.0f}초 (제미나이 {sum(1 for c in G.CALLS[n0:] if c.get('ok'))}회 {sum(c.get('sec') or 0 for c in G.CALLS[n0:]):.0f}초)")
        if s == until:
            break
    copy_docs(W, slug)
    log(f"[끝] 단계별 초 {({k: v['sec'] for k, v in tm.cur['stages'].items()})} · 합 {tm.cur['total_sec']}초 · 기록 {W / 'make_log.json'}")
    return ctx


def copy_docs(W: Path, slug: str):
    """편 문서 사본(커밋용) — 영상·소리 파일은 복사하지 않는다."""
    dst = ROOT / "tools/calcopy/yanshot/runs" / slug
    doc = W / "doc"
    if not doc.exists():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for f in list(doc.glob("*.json")) + list(doc.glob("*.md")) + list(doc.glob("*.jpg")) + list((doc / "plan").glob("*")):
        rel = f.relative_to(doc)
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst / rel)
    for f in ("make_log.json",):
        if (W / f).exists():
            shutil.copy2(W / f, dst / f)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--until", default="check", choices=STAGES)
    ap.add_argument("--redo", choices=STAGES)
    a = ap.parse_args(argv)
    try:
        run(a.url, a.slug, a.until, a.redo)
    except StageError as e:
        print(f"[멈춤] {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
