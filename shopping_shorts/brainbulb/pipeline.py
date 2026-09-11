# -*- coding: utf-8 -*-
"""단계 배열 상태기계 — 볼케이노 `next_step` 원리. 화면·호출자는 `next()`가 주는 다음 걸음만 따른다.

STEPS = setup → script → layout → lint → voice → timing → subtitle → sfx → render → review   (합의 §5)
- 상태는 작업폴더 `job.json` 하나 (아스트라 (5)). 원자 저장(tmp→rename), `lock` 파일로 중복 실행 방지.
- 검사 단계(lint·review)는 입력을 수정하지 않는다. 반려는 사유와 함께 `need_input`.
- 바뀐 입력의 후속 산출물은 무효화한다(`_invalidate_after`).
- 사람 자리는 setup 입력뿐. script·voice의 외부 호출기(LLM·TTS)는 주입한다.
"""
import hashlib
import json
import os
import tempfile
import time

from . import spec, prompt, lint, layout, voice, timing, ass_gen, sfx, render, review, measure

STEPS = ["setup", "script", "layout", "lint", "voice", "timing", "subtitle", "sfx", "render", "review"]


def _job_path(wd):
    return os.path.join(wd, "job.json")


def load(wd):
    p = _job_path(wd)
    if not os.path.exists(p):
        return {"step_done": None, "history": [], "data": {}}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save(wd, job):
    os.makedirs(wd, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=wd, prefix="job.", suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(job, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, _job_path(wd))


def _invalidate_after(job, step):
    """step 이후 단계 산출물을 버린다 — 입력이 바뀌면 뒤가 무효."""
    i = STEPS.index(step)
    for s in STEPS[i + 1:]:
        job["data"].pop(s, None)
    job["step_done"] = step


def _resp(status, step, next_step=None, **kw):
    return {"status": status, "step": step, "next_step": next_step, **kw}


class Lock:
    def __init__(self, wd):
        self.p = os.path.join(wd, "lock")

    def __enter__(self):
        os.makedirs(os.path.dirname(self.p), exist_ok=True)
        try:
            fd = os.open(self.p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise RuntimeError(f"pipeline: 다른 실행이 진행 중 ({self.p}) — 끝났는데 남아 있으면 지우고 다시")
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
        return self

    def __exit__(self, *a):
        try:
            os.remove(self.p)
        except OSError:
            pass


def _digest(obj):
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def run_step(wd, step, *, source_text=None, llm=None, tts=None, sfx_dir=None, bg_image=None, fonts_dir=None, log=print):
    """한 단계만 실행. → 응답 dict {status: ok|need_input|failed, step, next_step, fail?, need?}"""
    job = load(wd)
    d = job["data"]
    try:
        if step == "setup":
            if not source_text:
                return _resp("need_input", step, "setup", need=["source_text"])
            fp = measure.font_probe(fonts_dir)
            bad = [k for k, v in fp.items() if not v["ok"]]
            if bad:
                return _resp("failed", step, "setup", fail={"where": "setup.font_probe", "why": f"폰트가 안 잡힘: {bad}",
                                                             "fix": f"{spec.FONTS_DIR}에 ttf 4종이 있는지", "retry_ok": True})
            d["setup"] = {"source_text": source_text, "source_hash": _digest(source_text), "fonts": fp, "at": time.time()}
            _invalidate_after(job, "setup")

        elif step == "script":
            if llm is None:
                return _resp("need_input", step, "script", need=["llm (call(prompt)->str)"])
            script, issues, attempts = prompt.generate(d["setup"]["source_text"], llm, fonts_dir=fonts_dir, log=log)
            rej = lint.rejects(issues)
            d["script"] = {"script": script, "attempts": attempts,
                           "issues": [i.__dict__ for i in issues]}
            _invalidate_after(job, "script")
            if rej:
                save(wd, job)
                return _resp("failed", step, "script", fail={"where": "script.lint", "why": f"재작성 {attempts}회 뒤에도 반려 {len(rej)}건",
                                                              "fix": lint.feedback(issues), "retry_ok": True})

        elif step == "layout":
            groups, fails = layout.layout_groups(d["script"]["script"]["groups"], fonts_dir)
            d["layout"] = {"groups": groups, "fails": fails}
            _invalidate_after(job, "layout")

        elif step == "lint":
            s = dict(d["script"]["script"]); s["groups"] = d["layout"]["groups"]
            issues, _ = lint.lint(s, source_text=d["setup"]["source_text"], do_layout=False)
            issues += lint.r_layout(s, {"layout_fails": d["layout"]["fails"]})
            rej = lint.rejects(issues)
            d["lint"] = {"issues": [i.__dict__ for i in issues], "ok": not rej}
            _invalidate_after(job, "lint")
            if rej:
                save(wd, job)
                return _resp("failed", step, "lint", fail={"where": "lint", "why": f"반려 {len(rej)}건", "fix": lint.feedback(issues), "retry_ok": True})

        elif step == "voice":
            if tts is None:
                return _resp("need_input", step, "voice", need=["tts (synth(text,out_path))"])
            s = dict(d["script"]["script"]); s["groups"] = d["layout"]["groups"]
            d["voice"] = voice.synth_all(s, wd, tts, log=log)
            _invalidate_after(job, "voice")

        elif step == "timing":
            v = d["voice"]
            d["timing"] = timing.build(v["card_sec"], v["cut_secs"], d["layout"]["groups"])
            _invalidate_after(job, "timing")

        elif step == "subtitle":
            s = d["script"]["script"]
            text = ass_gen.build(s["title"], s["title"]["card"], d["timing"], fonts_dir=fonts_dir)
            p = os.path.join(wd, "sub.ass")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            d["subtitle"] = {"path": p, "lines": len(ass_gen.dialogue_lines(text))}
            _invalidate_after(job, "subtitle")

        elif step == "sfx":
            d["sfx"] = {"plan": sfx.plan(d["timing"]["groups"])}
            _invalidate_after(job, "sfx")

        elif step == "render":
            r = render.build(wd, d["timing"], d["subtitle"]["path"], d["voice"]["files"], d["sfx"]["plan"],
                             sfx_dir=sfx_dir, bg_image=bg_image, fonts_dir=fonts_dir, log=log)
            d["render"] = r
            _invalidate_after(job, "render")

        elif step == "review":
            rep = review.run(d["render"]["mp4"], d["subtitle"]["path"], d["render"]["narr"], d["timing"], fonts_dir=fonts_dir)
            d["review"] = rep
            _invalidate_after(job, "review")
            if not rep["ok"]:
                save(wd, job)
                bad = [c for c in rep["checks"] if not c["ok"]]
                return _resp("failed", step, None, fail={"where": "review", "why": ", ".join(c["name"] for c in bad),
                                                          "fix": "해당 단계 산출물을 고치고 그 단계부터 다시", "retry_ok": True, "detail": bad})
        else:
            raise ValueError(f"모르는 단계: {step}")
    except Exception as e:  # noqa: BLE001 — 원인·처방을 응답에 담아 올린다(실패 문구 원인 뭉개기 금지)
        job["history"].append({"step": step, "error": repr(e)[:300], "at": time.time()})
        save(wd, job)
        return _resp("failed", step, step, fail={"where": step, "why": repr(e)[:300], "fix": "로그의 where부터 확인", "retry_ok": True})
    job["history"].append({"step": step, "ok": True, "at": time.time()})
    save(wd, job)
    i = STEPS.index(step)
    nxt = STEPS[i + 1] if i + 1 < len(STEPS) else None
    return _resp("ok", step, nxt)


def next_step(wd):
    job = load(wd)
    done = job.get("step_done")
    if done is None:
        return "setup"
    i = STEPS.index(done)
    return STEPS[i + 1] if i + 1 < len(STEPS) else None


def run_all(wd, **kw):
    """setup부터 review까지 관통. 멈추면 그 응답을 그대로 돌려준다(볼케이노 need_input/failed와 같은 모양)."""
    with Lock(wd):
        step = next_step(wd) or "setup"
        while step:
            r = run_step(wd, step, **kw)
            if r["status"] != "ok":
                return r
            step = r["next_step"]
        return _resp("ok", "review", None, done=True, job=load(wd))
