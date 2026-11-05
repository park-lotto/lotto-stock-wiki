# -*- coding: utf-8 -*-
"""뜨거운사람들 단계 — channelkit.pipeline 이 spec.STEP_HANDLERS 로 부른다. 계약: fn(job, d, wd, kw) -> None | 응답 dict.

kw 에서 쓰는 것: source_text(=씨앗 "이름 | 주제"), llm(대본), reviewer(=장면 고르는 reader: call(prompt,[png…])), log.
★import 는 함수 안에서 — 맨 위에 두면 channel_presets.hotpeople.spec ↔ steps 순환(뇌전구 steps와 같은 이유).
"""
import os
import shutil


def _need(step, what):
    from shopping_shorts.channelkit.pipeline import _resp
    return _resp("need_input", step, step, need=[what])


def _fail(step, why, fix):
    from shopping_shorts.channelkit.pipeline import _resp
    return _resp("failed", step, step, fail={"where": step, "why": why, "fix": fix, "retry_ok": True})


def setup(job, d, wd, kw):
    from . import spec
    seed = (kw.get("source_text") or "").strip()
    if not seed:
        return _need("setup", "source_text (씨앗: '인물명 | 주제')")
    miss = [p for p in (spec.SUB_FONT, spec.LOGO_NAME_FONT) if not os.path.isfile(p)]
    miss += [b for b in ("ffmpeg", "ffprobe", "yt-dlp") if not shutil.which(b)]
    from shopping_shorts.channelkit import vision
    miss += vision.models_missing()                 # 소스 자·후보 태깅·내용 관문이 쓰는 얼굴/글자 모델
    if miss:
        return _fail("setup", f"없는 것: {miss}", "글꼴은 shopping_shorts/static/fonts, 도구는 PATH에")
    d["setup"] = {"seed": seed}


def research(job, d, wd, kw):
    from . import research as R
    r = R.fetch(d["setup"]["seed"], log=kw["log"])
    if len(r["text"]) < 800:
        return _fail("research", f"원문이 너무 짧다({len(r['text'])}자)", "인물 표기를 바꿔 setup부터")
    d["research"] = r


def script(job, d, wd, kw):
    from shopping_shorts.channelkit import lint
    from . import script as S
    if kw.get("llm") is None:
        return _need("script", "llm (call(prompt)->str)")
    s, issues, attempts = S.generate(d["research"], kw["llm"], log=kw["log"])
    d["script"] = {"script": s, "attempts": attempts, "issues": [i.__dict__ for i in issues],
                   "by": getattr(kw["llm"], "tag", "")}
    rej = lint.rejects(issues)
    if rej:
        return _fail("script", f"재작성 {attempts}회 뒤에도 반려 {len(rej)}건", lint.feedback(issues)[:1500])


def footage(job, d, wd, kw):
    from . import footage as F
    d["footage"] = F.collect(d["script"]["script"], wd, reader=kw.get("reviewer"), log=kw["log"])


def render(job, d, wd, kw):
    from . import render as R
    from . import review as V
    V.clear_out(wd)                                 # 지난 완성본이 새 결과 옆에 남지 않게(out/ 은 review 가 맡는다)
    d["render"] = R.build(wd, d["script"]["script"], d["footage"], log=kw["log"])


def review(job, d, wd, kw):
    from . import review as V
    rep = V.run(d["render"]["mp4"], d["render"], wd, script=d["script"]["script"], footage=d["footage"])
    rep["final"] = V.finalize(rep, wd, d["render"]["mp4"])     # ★통과해야만 out/final.mp4, 막히면 out/FAILED.json
    d["review"] = rep
    if not rep["ok"]:
        bad = [c for c in rep["checks"] if not c["ok"] and c.get("block", True)]
        return _fail("review", ", ".join(f"{c['name']} (값 {c.get('got')})" for c in bad)[:1500],
                     f"out/FAILED.json · 검수 시트 {rep.get('sheet')} 보고 해당 단계부터 — final.mp4 는 만들지 않았다")


HANDLERS = {"setup": setup, "research": research, "script": script, "footage": footage, "render": render, "review": review}
