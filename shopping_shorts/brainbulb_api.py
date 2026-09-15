# -*- coding: utf-8 -*-
"""뇌전구 제작소 화면이 쓰는 API(2026-09-15 신설). **관리자 전용**(사장님 지시).

만드는 일은 전부 `brainbulb/pipeline.py`에 있고 여기는 **일을 시키고 상태를 알려주는 창구**다
(0순위-B: 같은 판단을 두 군데 적지 않는다 — 단계 배열·판정·재시작 규칙은 저쪽에만 있다).

★상태를 메모리에 두지 않는다. `job.json`이 이미 작업폴더에 있고 pipeline이 원자 저장한다
  (longform_api는 메모리 사전을 쓰는데, 그건 서버가 재시작되면 진행 상태가 사라진다).
  화면은 그 파일을 읽어서 그린다 → 서버를 껐다 켜도, 창을 닫았다 열어도 이어서 보인다.

★돈이 나가는 경로다(EvoLink 이미지·Typecast 음성·Claude 대본). 더블클릭·새로고침으로
  두 번 돌면 두 번 과금된다 → `_RUNNING`으로 **응답을 보내기 전에 동기적으로** 선점한다.
  (mix_render가 겪은 TOCTOU 사고와 같은 모양 — app.py:6266 주석 참고. pipeline.Lock은
   프로세스 안에서만 보므로 예약 자체를 여기서 막아야 한다.)
"""
from __future__ import annotations

import os
import re
import threading
import traceback
import time
from pathlib import Path

from fastapi import BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse

from shopping_shorts.brainbulb import pipeline

# 작업 폴더 뿌리. CLI(`--workdir out/brainbulb/<이름>`)와 같은 자리를 쓴다 —
# 화면에서 만든 것을 CLI로 이어서 손보거나 그 반대가 된다.
_ROOT = Path(__file__).resolve().parent.parent / "out" / "brainbulb"

# 지금 돌고 있는 잡. {job_id: 시작시각}. 예약 중복만 막으면 되므로 메모리로 충분하다
# (서버가 죽으면 비는 게 맞다 — 그 잡은 어차피 안 돌고 있다).
_RUNNING: dict[str, float] = {}
_LOCK = threading.Lock()

# 화면에 보일 단계 이름. pipeline.STEPS(13개)와 **같은 축**이다.
# ★단계 번호를 문구에 손으로 쓰지 않는다(produce.html:3528 실사고 — 9단계 개편 때 16곳이
#   전부 거짓말이 됐다). 화면은 이 목록만 보고 그린다.
STEP_LABELS = {
    "setup":    "소재 읽기",
    "script":   "대본 쓰기",
    "layout":   "줄 나누기",
    "lint":     "대본 검사",
    "prompts":  "그림 주문서",
    "images":   "그림 만들기",
    "voice":    "성우 녹음",
    "timing":   "컷 시간표",
    "subtitle": "자막 만들기",
    "sfx":      "효과음 배치",
    "frames":   "화면 붙이기",
    "render":   "영상 굽기",
    "review":   "완성 검사",
}

# 단계바에 박히는 짧은 이름. 13칸이 나란히 서면 한 칸이 53px뿐이라 위 이름은 **전부 두 줄로
# 접힌다**(실측 1600px 창에서 13/13). produce.html의 STEP_SHORT와 같은 장치 —
# 도크에는 이것을, 안내 문구·기록에는 위의 긴 이름을 쓴다.
STEP_SHORT = {
    "setup": "소재", "script": "대본", "layout": "줄", "lint": "검사",
    "prompts": "주문서", "images": "그림", "voice": "성우", "timing": "시간표",
    "subtitle": "자막", "sfx": "효과음", "frames": "화면", "render": "굽기",
    "review": "완성",
}

_SAFE_NAME = re.compile(r"[^0-9A-Za-z가-힣_\-]+")


def _slug(name: str) -> str:
    """작업 이름 → 폴더 이름. 경로 탈출(`..`·슬래시)을 원천 차단한다."""
    s = _SAFE_NAME.sub("_", (name or "").strip())[:60].strip("_")
    return s or time.strftime("job_%m%d_%H%M%S")


def _workdir(job_id: str) -> Path:
    """job_id는 폴더 이름 그 자체다. 밖으로 나가는 이름은 여기서 막는다."""
    d = (_ROOT / _slug(job_id)).resolve()
    if not str(d).startswith(str(_ROOT.resolve())):
        raise ValueError("작업 폴더가 범위를 벗어났습니다")
    return d


def _running(job_id: str) -> bool:
    with _LOCK:
        return job_id in _RUNNING


def _claim(job_id: str) -> bool:
    """예약 선점. 이미 돌고 있으면 False — **응답 전에** 동기적으로 부른다."""
    with _LOCK:
        if job_id in _RUNNING:
            return False
        _RUNNING[job_id] = time.time()
        return True


def _release(job_id: str) -> None:
    with _LOCK:
        _RUNNING.pop(job_id, None)


def _state(job_id: str) -> dict:
    """job.json을 화면이 그릴 모양으로 옮긴다. **판정은 여기서 새로 하지 않는다** —
    pipeline이 남긴 것을 읽기만 한다(0순위-B)."""
    wd = _workdir(job_id)
    job = pipeline.load(str(wd))
    d = job.get("data") or {}
    done = job.get("step_done")
    done_i = pipeline.STEPS.index(done) if done in pipeline.STEPS else -1
    nxt = pipeline.next_step(str(wd))

    steps = []
    for i, s in enumerate(pipeline.STEPS):
        if i <= done_i:
            # ★"지나왔다"가 아니라 **산출물이 있나**로 본다(produce.html:4035 실사고 —
            #   빈 산출물에 초록 체크가 켜졌다).
            st = "done" if d.get(s) is not None else "empty"
        elif _running(job_id) and s == nxt:
            st = "running"
        else:
            st = "wait"
        steps.append({"key": s, "label": STEP_LABELS.get(s, s),
                      "short": STEP_SHORT.get(s, STEP_LABELS.get(s, s)), "state": st})

    out = {
        "job_id": job_id,
        "running": _running(job_id),
        "step_done": done,
        "next_step": nxt,
        "steps": steps,
        "history": (job.get("history") or [])[-40:],
        "fail": job.get("last_fail"),
        "tts_spent_chars": job.get("tts_spent_chars", 0),
    }
    # 완성본이 있으면 재생 주소를 준다.
    mp4 = ((d.get("render") or {}).get("mp4")) if isinstance(d.get("render"), dict) else None
    if mp4 and os.path.exists(mp4):
        out["mp4"] = f"/api/brainbulb/file?job_id={job_id}"
        out["mp4_size"] = os.path.getsize(mp4)
    t = d.get("timing") or {}
    if t:
        out["total_sec"] = t.get("total")
        out["cuts"] = len(t.get("groups") or [])
    sc = d.get("script") or {}
    if sc:
        out["attempts"] = sc.get("attempts")
        out["title"] = ((sc.get("script") or {}).get("title") or {}).get("h1")
    return out


def _run(job_id: str, source_text: str, opts: dict) -> None:
    """배경에서 끝까지 돌린다. 멈추면 그 사유를 job.json에 적어 화면이 읽게 한다."""
    wd = str(_workdir(job_id))
    lines: list[str] = []

    def _log(*a):
        msg = " ".join(str(x) for x in a)
        lines.append(msg[:500])
        print("[brainbulb]", msg)

    try:
        from shopping_shorts.brainbulb import providers, images as _images
        imagegen = None if opts.get("no_images") else _images.evolink_imagegen()
        r = pipeline.run_all(
            wd,
            source_text=source_text,
            llm=providers.script_llm(opts.get("model") or "gemini-3.1-flash-lite",
                                     which=opts.get("script_llm")),
            tts=providers.typecast_synth(_voices(), tempo=opts.get("tempo") or 1.3),
            imagegen=imagegen,
            sfx_dir=opts.get("sfx_dir"), meme_dir=opts.get("meme_dir"),
            reviewer=None if (opts.get("no_review") or imagegen is None)
            else providers.gemini_reviewer(),
            log=_log,
        )
        job = pipeline.load(wd)
        job["last_fail"] = None if r.get("status") == "ok" else r.get("fail")
        job["last_log"] = lines[-60:]
        pipeline.save(wd, job)
    except Exception as exc:                        # noqa: BLE001 — 화면에 이유를 보여준다
        traceback.print_exc()
        try:
            job = pipeline.load(wd)
            job["last_fail"] = {"where": "run", "why": f"{type(exc).__name__}: {exc}"[:300],
                                "fix": "서버 로그의 where부터 확인", "retry_ok": True}
            job["last_log"] = lines[-60:]
            pipeline.save(wd, job)
        except Exception:                           # noqa: BLE001
            traceback.print_exc()
    finally:
        _release(job_id)


def _voices():
    from shopping_shorts.brainbulb import spec
    return dict(spec.POLICY_VOICES)


def register(app, require_admin):
    """app.py에서 한 번 부른다. require_admin(request)는 막을 때 응답을, 통과면 None을 준다."""

    @app.post("/api/brainbulb/start")
    def _start(request: Request, background: BackgroundTasks, body: dict):
        denied = require_admin(request)
        if denied:
            return denied
        url = (body.get("url") or "").strip()
        text = (body.get("text") or "").strip()
        if not url and not text:
            return JSONResponse({"error": "기사 링크나 본문이 필요합니다"}, status_code=422)

        name = body.get("name") or ""
        # ★이름을 안 주면 URL 끝을 쓰지 않는다(2026-09-16 실사고). URL 끝은 기사마다
        #   비슷하거나 빈 값이라 남의 폴더와 부딪힌다 → 시각으로 반드시 새 폴더를 판다.
        job_id = _slug(name) if name.strip() else time.strftime("편_%m%d_%H%M%S")
        wd = _workdir(job_id)

        # ★이미 만든 편에 **말없이 덮어쓰지 않는다**(2026-09-16 실사고 — 박위 편 폴더에
        #   제로카레 대본이 얹혀 옛 사진이 그대로 남은 영상이 나왔고 요금도 다시 나갔다).
        #   덮어쓸 생각이면 화면이 overwrite=true를 명시해 보낸다.
        if wd.exists() and (wd / "job.json").exists() and not body.get("overwrite"):
            return JSONResponse({"error": f"「{job_id}」은(는) 이미 있는 작업입니다. "
                                          f"다른 이름을 쓰거나, 그 편을 이어서 하려면 목록에서 여세요.",
                                 "exists": job_id}, status_code=409)
        wd.mkdir(parents=True, exist_ok=True)

        # ★예약을 **응답 전에** 선점한다. 안 하면 더블클릭 두 건이 둘 다 통과해
        #   같은 폴더에 두 번 돌고 유료 API가 두 번 나간다.
        if not _claim(job_id):
            return {"ok": True, "job_id": job_id, "already": True}

        try:
            if url:
                from shopping_shorts.brainbulb import providers
                src = providers.fetch_article(url)
                text = src["text"]
            (wd / "source.txt").write_text(text, encoding="utf-8")
        except Exception as exc:                    # noqa: BLE001
            _release(job_id)
            return JSONResponse({"error": f"기사를 읽지 못했습니다 — {exc}"[:300]}, status_code=422)

        opts = {k: body.get(k) for k in
                ("no_images", "no_review", "script_llm", "model", "tempo", "sfx_dir", "meme_dir")}
        background.add_task(_run, job_id, text, opts)
        return {"ok": True, "job_id": job_id, "chars": len(text)}

    @app.get("/api/brainbulb/status")
    def _status(request: Request, job_id: str):
        denied = require_admin(request)
        if denied:
            return denied
        try:
            return _state(job_id)
        except Exception as exc:                    # noqa: BLE001
            return JSONResponse({"error": str(exc)[:300]}, status_code=400)

    @app.get("/api/brainbulb/jobs")
    def _jobs(request: Request):
        denied = require_admin(request)
        if denied:
            return denied
        out = []
        if _ROOT.exists():
            for d in sorted(_ROOT.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if not (d / "job.json").exists():
                    continue
                try:
                    st = _state(d.name)
                except Exception:                   # noqa: BLE001 — 한 건이 깨져도 목록은 보인다
                    continue
                out.append({k: st.get(k) for k in
                            ("job_id", "step_done", "running", "mp4", "total_sec", "cuts", "title")})
                if len(out) >= 50:
                    break
        return {"jobs": out}

    @app.post("/api/brainbulb/retry")
    def _retry(request: Request, background: BackgroundTasks, body: dict):
        """이 단계부터 다시. 뒤 산출물은 pipeline.reset_to가 무효화한다."""
        denied = require_admin(request)
        if denied:
            return denied
        job_id = body.get("job_id") or ""
        step = body.get("step") or ""
        if step not in pipeline.STEPS:
            return JSONResponse({"error": f"모르는 단계: {step}"}, status_code=422)
        wd = _workdir(job_id)
        if not (wd / "source.txt").exists():
            return JSONResponse({"error": "없는 작업입니다"}, status_code=404)
        if not _claim(job_id):
            return {"ok": True, "job_id": job_id, "already": True}
        try:
            pipeline.reset_to(str(wd), step)
        except Exception as exc:                    # noqa: BLE001
            _release(job_id)
            return JSONResponse({"error": str(exc)[:300]}, status_code=400)
        text = (wd / "source.txt").read_text(encoding="utf-8")
        opts = {k: body.get(k) for k in
                ("no_images", "no_review", "script_llm", "model", "tempo", "sfx_dir", "meme_dir")}
        background.add_task(_run, job_id, text, opts)
        return {"ok": True, "job_id": job_id, "from": step}

    @app.get("/api/brainbulb/file")
    def _file(request: Request, job_id: str):
        denied = require_admin(request)
        if denied:
            return denied
        wd = _workdir(job_id)
        d = (pipeline.load(str(wd)).get("data") or {})
        mp4 = ((d.get("render") or {}).get("mp4")) if isinstance(d.get("render"), dict) else None
        if not mp4 or not os.path.exists(mp4):
            return JSONResponse({"error": "아직 완성본이 없습니다"}, status_code=404)
        return FileResponse(mp4, media_type="video/mp4", filename=f"{job_id}.mp4")

    @app.get("/api/brainbulb/steps")
    def _steps(request: Request):
        denied = require_admin(request)
        if denied:
            return denied
        return {"steps": [{"key": s, "label": STEP_LABELS.get(s, s),
                           "short": STEP_SHORT.get(s, STEP_LABELS.get(s, s))}
                          for s in pipeline.STEPS]}
