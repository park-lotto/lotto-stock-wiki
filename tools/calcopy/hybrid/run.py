# -*- coding: utf-8 -*-
"""얜샷템 하이브리드 — 단계 실행기(다시 이어 돌릴 수 있음 · 단계별 소요 초 장부) (관제 097, 2026-10-18).

    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> status                       # 어디까지 됐나 · 다음 할 일(누가: 도구/소넷/오푸스)
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> init --source <원본 유튜브 URL> --product "테클라 수건" --keywords 테클라,tekla --queries "tekla towel" "테클라 수건"
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> candidates                   # 검색(yt-dlp + 서버 유튜브 API) → screen/candidates.json
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> screen                       # 메타·자동자막·360p 토막 시트 → screen.json (소넷이 chosen 적음)
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> download                     # screen.json chosen 만 1080p + 원본 영상
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> asr                          # 원본 후보 구간 받아쓰기(서버 제미나이 2모델, 병렬) → asr/*.json
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> plan [--version 잇썸홈판|재미썸홈판|both]   # 대본·재료 → 계획 시트(TTS 전)
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> name_check                   # 이름 발음 사전 점검(이름 구절만 합성·받아쓰기) → 대본 tts 에 반영
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> render [--version …] [--parallel]   # TTS 1회 + 렌더(두 판 동시 가능) → render/final.mp4
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> checks [--version …]         # B표 초안 + 썸네일 JPG + 얼굴 검사(--no-asr 로 받아쓰기 생략)
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> deliver [--version …]        # 바탕화면 칼카피영상/얜샷템/하이브리드/ 로 mp4+jpg (자동 검사 통과한 판만)
    PYTHONUTF8=1 py tools/calcopy/hybrid/run.py <연예인> all [--until <단계>]          # 되는 데까지 이어 돌림(사람 몫 단계에서 멈추고 브리프 경로를 찍음)

폴더: 작업 W = C:/숏템_칼카피/yanshottem/하이브리드_<연예인>/ (src·screen·asr·<판>/render) · 문서 D = channel/yanshottem/하이브리드_<연예인>/ (조사·<판>/대본.json·재료.json·B표…)
상태: W/pipeline.json(단계 완료 표식·시각) · W/stage_log.json(단계별 초). 단계 결과 파일이 있으면 건너뛴다(--redo <단계> 로 다시).
누가 하나: 도구(기계적) = candidates·download·asr·render·checks·deliver / 소넷 워커(briefs/*.md 브리프) = research·screen 고르기·script 초안 / 오푸스 = 대본 확정·B표 판정.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.hybrid.common import DESK_DIR, DOC_BASE, WORK_BASE, StageError, Timer, jload, jsave, md5  # noqa: E402

VERSIONS = ("잇썸홈판", "재미썸홈판")
STAGES = ["init", "research", "candidates", "screen", "download", "asr", "script", "plan", "name_check", "render", "checks", "deliver"]
HUMAN = {"research": "briefs/research.md", "screen_pick": "briefs/screen_pick.md", "script": "briefs/script.md", "review": "briefs/review.md"}
BRIEFS = Path(__file__).with_name("briefs")


class Ctx:
    def __init__(self, celeb: str):
        self.celeb = celeb
        self.W = WORK_BASE / f"하이브리드_{celeb}"
        self.D = DOC_BASE / f"하이브리드_{celeb}"
        self.W.mkdir(parents=True, exist_ok=True)
        self.state_p = self.W / "pipeline.json"
        self.state = jload(self.state_p) if self.state_p.exists() else {"celeb": celeb, "done": {}, "cfg": {}}
        self.tm = Timer(self.W / "stage_log.json")

    def save(self):
        jsave(self.state_p, self.state)

    def mark(self, stage: str, **info):
        self.state["done"][stage] = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), **info}
        self.save()

    def cfg(self, k, default=None):
        return self.state.get("cfg", {}).get(k, default)


def _timed(ctx: Ctx, stage: str, fn, *a, **kw):
    t0 = time.time()
    try:
        r = fn(*a, **kw)
        ctx.tm.done(stage, time.time() - t0)
        return r
    except Exception as e:
        ctx.tm.done(stage, time.time() - t0, f"실패: {str(e)[:200]}")
        raise


# ── 단계들 ───────────────────────────────────────────────────────────────
def st_init(ctx: Ctx, a):
    ctx.state["cfg"].update({k: v for k, v in {"source": a.source, "product": a.product, "keywords": a.keywords.split(",") if a.keywords else None,
                                               "queries": a.queries, "exclude": a.exclude.split(",") if a.exclude else None}.items() if v})
    (ctx.D / "조사").mkdir(parents=True, exist_ok=True)
    for v in VERSIONS:
        (ctx.D / v).mkdir(exist_ok=True)
    ctx.mark("init")
    print(f"[init] {ctx.W} · {ctx.D} · cfg {json.dumps(ctx.state['cfg'], ensure_ascii=False)}")


def st_candidates(ctx: Ctx, a):
    from tools.calcopy.hybrid import screen
    qs = ctx.cfg("queries") or []
    if not qs:
        raise StageError("검색어가 없다 — init --queries 로 넣어라(연예인 원본 조사 뒤 소넷이 적는다)")
    r = screen.search(ctx.W, qs, n=a.n, exclude=ctx.cfg("exclude"), server=not a.no_server)
    ctx.mark("candidates", n=len(r))


def st_screen(ctx: Ctx, a):
    from tools.calcopy.hybrid import screen
    kws = ctx.cfg("keywords") or []
    if not kws:
        raise StageError("키워드(제품명)가 없다 — init --keywords")
    r = screen.screen(ctx.W, kws, top=a.top)
    ctx.mark("screen", n=len(r["rows"]))
    print(f"[screen] 다음 = 소넷 워커가 {ctx.W / 'screen.json'} 의 chosen 을 채운다 (브리프 {BRIEFS / 'screen_pick.md'})")


def st_download(ctx: Ctx, a):
    from tools.calcopy.hybrid import screen
    sj = jload(ctx.W / "screen.json")
    chosen = sj.get("chosen") or []
    if not chosen:
        raise StageError(f"screen.json chosen 이 비었다 — 소넷 워커가 시트를 보고 고른 뒤 다시 (브리프 {BRIEFS / 'screen_pick.md'})")
    ids = [c if isinstance(c, str) else c["id"] for c in chosen]
    secs = {c["id"]: [tuple(s) for s in c.get("sections", [])] for c in chosen if isinstance(c, dict)}
    out = []
    for vid in ids:
        out += screen.download(ctx.W, [vid], secs.get(vid) or None, prefix=ctx.cfg("product_prefix") or "")
    src = ctx.cfg("source")
    if src:
        from tools.calcopy.hybrid.screen import vid_of
        out += screen.download(ctx.W, [vid_of(src)], None, prefix="")
    ctx.mark("download", files=[str(p) for p in out])


def st_asr(ctx: Ctx, a):
    """원본(연예인) 영상의 후보 구간 받아쓰기 — asr/spans.json([{src, a, b, tag}]) 을 소넷/오푸스가 적어 두면 서버 2모델로 병렬 받아쓴다."""
    from tools.calcopy.hybrid import gemini_server as G
    sp = ctx.W / "asr" / "spans.json"
    if not sp.exists():
        raise StageError(f"받아쓰기 구간 파일이 없다: {sp} — [{{\"src\": \"src/xxx.mp4\", \"a\": 224.8, \"b\": 231.0, \"tag\": \"O1\"}}] 꼴로 적어라")
    spans = jload(sp)
    files = [(str(ctx.W / s["src"]), s["a"], s["b"]) for s in spans]
    from tools.calcopy.hybrid.server_ai import ASR_MODELS   # flash-latest 서버 멈춤(10-18) — 하이브리드 받아쓰기 모델은 server_ai 한 곳
    r = G.asr(files, models=ASR_MODELS)
    for s, job in zip(spans, r["jobs"]):
        s["heard"] = G.texts(job); s["ok_models"] = job["ok_models"]
    jsave(ctx.W / "asr" / "result.json", {"sec": r["sec"], "spans": spans})
    short = [s["tag"] for s in spans if len(s["ok_models"]) < 2]
    ctx.mark("asr", n=len(spans), sec=r["sec"], cross_short=short)
    print(f"[asr] {len(spans)}구간 {r['sec']}초 · 교차 확인 모자람 {short or 0} → {ctx.W / 'asr' / 'result.json'}")


def _versions(a):
    return list(VERSIONS) if a.version in (None, "both") else [a.version]


def _renderer(v):
    from tools.calcopy.hybrid import render_itssum, render_jaemi
    return render_itssum if v == "잇썸홈판" else render_jaemi


def _need_docs(ctx: Ctx, v):
    for f in ("대본.json", "재료.json"):
        if not (ctx.D / v / f).exists():
            raise StageError(f"{ctx.D / v / f} 가 없다 — 대본·재료는 오푸스가 적는다(브리프 {BRIEFS / 'script.md'})")


def st_plan(ctx: Ctx, a):
    for v in _versions(a):
        _need_docs(ctx, v)
        _renderer(v).render(ctx.D / v, ctx.W / v, plan_only=True)
        ctx.mark(f"plan:{v}")


def st_name_check(ctx: Ctx, a):
    from tools.calcopy.hybrid import name_check
    out = {}
    for v in _versions(a):
        _need_docs(ctx, v)
        S = jload(ctx.D / v / "대본.json")
        voice = S["voice"]["voice_id"]
        r = name_check.check(ctx.celeb, voice, ctx.W / "name_check" / voice, S["voice"].get("tempo"))
        sp = r["tts"]
        changed = 0
        from tools.calcopy.engine import name_dict as ND
        for l in S["lines"]:
            if l.get("tts") and ctx.celeb in l["tts"] and sp != ctx.celeb:
                new = ND.apply(l["tts"], ctx.celeb, voice)   # 이미 표기면 그대로(10-18 한혜진 '씨 씨가')
                if new != l["tts"]:
                    l["tts"] = new; changed += 1
        if changed:
            jsave(ctx.D / v / "대본.json", S)
        out[v] = {"tts": sp, "lines_changed": changed}
        ctx.mark(f"name_check:{v}", **out[v])
    print(f"[name_check] {json.dumps(out, ensure_ascii=False)}")


def st_render(ctx: Ctx, a):
    vs = _versions(a)
    for v in vs:
        _need_docs(ctx, v)

    def one(v):
        return v, _timed(ctx, f"render:{v}", _renderer(v).render, ctx.D / v, ctx.W / v)
    if a.parallel and len(vs) > 1:
        with ThreadPoolExecutor(max_workers=len(vs)) as ex:
            res = list(ex.map(one, vs))
    else:
        res = [one(v) for v in vs]
    for v, info in res:
        rep = info.get("report") or info
        ctx.mark(f"render:{v}", final=rep.get("final"), dur=rep.get("final_dur") or rep.get("dur"))


def st_checks(ctx: Ctx, a):
    from tools.calcopy.hybrid import checks, thumb
    for v in _versions(a):
        r = _timed(ctx, f"checks:{v}", checks.check, ctx.D / v, ctx.W / v, asr=not a.no_asr, bench_median=a.bench_median)
        try:
            th = _timed(ctx, f"thumb:{v}", thumb.make_thumb, ctx.D / v, ctx.W / v)
        except StageError as e:
            th = {"error": str(e)}
        ctx.mark(f"checks:{v}", ok_auto=r["ok_auto"], draft=r["draft"], thumb=th.get("jpg"), thumb_error=th.get("error"))
        print(f"[checks:{v}] 자동 {'○' if r['ok_auto'] else '×'} · 썸네일 {th.get('jpg') or th.get('error')} → 오푸스가 B표 초안 판정 칸을 채운다 (브리프 {BRIEFS / 'review.md'})")


def st_deliver(ctx: Ctx, a):
    slug = ctx.cfg("slug") or ctx.celeb
    for v in _versions(a):
        done = ctx.state["done"].get(f"checks:{v}")
        if not done or not done.get("ok_auto"):
            if not a.force:
                raise StageError(f"{v}: 자동 검사 통과 표식이 없다 — checks 먼저(또는 사장님 판정 뒤 --force)")
        final = ctx.W / v / "render" / "final.mp4"
        jpg = ctx.W / v / "render" / "final.jpg"
        DESK_DIR.mkdir(parents=True, exist_ok=True)
        dst = DESK_DIR / f"칼카피_얜샷템_{slug}_{v}.mp4"
        shutil.copy(final, dst)
        same = md5(final) == md5(dst)
        if jpg.exists():
            shutil.copy(jpg, dst.with_suffix(".jpg"))
        for f in ("B표_draft.md", "final_sheet_1s.jpg", "thumb.jpg", "frame_A.json"):
            if (ctx.D / v / f).exists():
                pass
        ctx.mark(f"deliver:{v}", dst=str(dst), md5_same=same)
        print(f"[deliver:{v}] {dst} MD5 {'같음' if same else '다름!'} · 썸네일 {dst.with_suffix('.jpg') if jpg.exists() else '없음'}")


def st_status(ctx: Ctx, a):
    d = ctx.state["done"]
    print(f"# {ctx.celeb} — {ctx.W}")
    for s in STAGES:
        keys = [k for k in d if k == s or k.startswith(s + ":")]
        print(f"  {'○' if keys else '·'} {s:12s} " + " ".join(f"{k}@{d[k]['at'][5:16]}" for k in keys))
    nxt = next((s for s in STAGES if not any(k == s or k.startswith(s + ":") for k in d)), None)
    who = {"research": "소넷(briefs/research.md)", "screen": "도구 → 소넷 고르기(briefs/screen_pick.md)", "script": "오푸스(briefs/script.md)", "checks": "도구 → 오푸스 판정(briefs/review.md)"}
    print(f"  다음: {nxt} — {who.get(nxt, '도구')}")
    if (ctx.W / "stage_log.json").exists():
        rows = jload(ctx.W / "stage_log.json")["stages"]
        print("  소요(초): " + " · ".join(f"{r['stage']} {r['sec']}" for r in rows[-12:]))


def st_research(ctx: Ctx, a):
    p = ctx.D / "조사" / "조사.md"
    if p.exists() and p.stat().st_size > 500:
        ctx.mark("research", path=str(p)); return
    raise StageError(f"조사.md 가 없다 — 소넷 워커 브리프 {BRIEFS / 'research.md'} 로 {p} 를 쓰게 한다(원본 URL {ctx.cfg('source')})")


def st_script(ctx: Ctx, a):
    for v in _versions(a):
        _need_docs(ctx, v)
    ctx.mark("script")


FN = {"init": st_init, "research": st_research, "candidates": st_candidates, "screen": st_screen, "download": st_download, "asr": st_asr, "script": st_script,
      "plan": st_plan, "name_check": st_name_check, "render": st_render, "checks": st_checks, "deliver": st_deliver, "status": st_status}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("celeb"); ap.add_argument("stage", choices=list(FN) + ["all"])
    ap.add_argument("--source"); ap.add_argument("--product"); ap.add_argument("--keywords"); ap.add_argument("--queries", nargs="*"); ap.add_argument("--exclude", default="")
    ap.add_argument("--n", type=int, default=12); ap.add_argument("--top", type=int, default=12); ap.add_argument("--no-server", action="store_true")
    ap.add_argument("--version", choices=list(VERSIONS) + ["both"]); ap.add_argument("--parallel", action="store_true"); ap.add_argument("--no-asr", action="store_true")
    ap.add_argument("--bench-median", type=float); ap.add_argument("--force", action="store_true"); ap.add_argument("--until"); ap.add_argument("--redo")
    a = ap.parse_args()
    ctx = Ctx(a.celeb)
    if a.redo:
        for k in [k for k in ctx.state["done"] if k == a.redo or k.startswith(a.redo + ":")]:
            del ctx.state["done"][k]
        ctx.save()
    if a.stage != "all":
        if a.stage != "status":
            _timed(ctx, a.stage, FN[a.stage], ctx, a) if a.stage not in ("render", "checks") else FN[a.stage](ctx, a)
        else:
            FN[a.stage](ctx, a)
        return
    for s in STAGES[1:]:
        if any(k == s or k.startswith(s + ":") for k in ctx.state["done"]):
            continue
        try:
            FN[s](ctx, a)
        except StageError as e:
            print(f"[멈춤 @{s}] {e}")
            return 1
        if a.until == s:
            return
    st_status(ctx, a)


if __name__ == "__main__":
    sys.exit(main() or 0)
