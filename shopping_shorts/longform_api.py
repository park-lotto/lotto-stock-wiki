# -*- coding: utf-8 -*-
"""롱폼→쇼츠 화면이 쓰는 API(2026-08-15 신설).

계산은 전부 longform_shorts.py에 있고 여기는 **일을 시키고 상태를 알려주는 창구**다
(0순위-B: 같은 판단을 두 군데 적지 않는다 — 자르는 규칙·프롬프트는 저쪽에만 있다).

작업 상태는 메모리 사전에 둔다. 서버가 재시작되면 진행 중이던 작업은 사라진다 —
결과 mp4·설계 JSON은 디스크에 남으므로 유실은 아니고 "다시 눌러야 한다" 수준이다.
(mix_pipeline처럼 DB에 넣는 편이 낫지만, 그건 이 화면이 실제로 쓰이는 걸 본 뒤에 한다.)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import threading
import traceback
import uuid
from pathlib import Path

from fastapi import BackgroundTasks, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse

from shopping_shorts import longform_shorts as lf

_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
_ROOT = Path(tempfile.gettempdir()) / "longform_shorts"
_ROOT.mkdir(parents=True, exist_ok=True)


def _set(job_id, **kw):
    with _LOCK:
        _JOBS.setdefault(job_id, {}).update(kw)


def _get(job_id):
    with _LOCK:
        return dict(_JOBS.get(job_id) or {})


def _analyze(job_id, video_path, n_shorts):
    """전사 → 설계. 오래 걸리므로 배경에서 돈다(전사만 몇 분)."""
    try:
        _set(job_id, status="transcribing", message="영상을 조각내어 받아쓰는 중…")
        segs = lf.transcribe_longform(video_path, work_dir=_ROOT / job_id / "work")
        if not segs:
            _set(job_id, status="failed", message="받아쓰기 결과가 비었습니다(음성 없음·API 실패)")
            return
        _set(job_id, status="planning", message=f"{len(segs)}개 구간에서 쇼츠감을 고르는 중…",
             segments=len(segs))
        (_ROOT / job_id / "segments.json").write_text(
            json.dumps(segs, ensure_ascii=False), encoding="utf-8")
        plan = lf.plan_shorts(segs, n_shorts=n_shorts)
        shorts = plan.get("shorts") or []
        for i, sh in enumerate(shorts):
            sh["idx"] = i
            _thumb(video_path, sh, _ROOT / job_id / f"thumb{i}.jpg")
        (_ROOT / job_id / "plan.json").write_text(
            json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        _set(job_id, status="ready", message=f"쇼츠 후보 {len(shorts)}편", shorts=shorts)
    except Exception as exc:                      # noqa: BLE001 — 화면에 이유를 보여준다
        traceback.print_exc()
        _set(job_id, status="failed", message=f"{type(exc).__name__}: {exc}"[:300])


def _thumb(video_path, sh, dst):
    """구간 대표 프레임 — 카드에서 '이 구간 화면이 볼 만한가'를 눈으로 판단하게."""
    at = float(sh["start"]) + (float(sh["end"]) - float(sh["start"])) / 2.0
    try:
        subprocess.run(["ffmpeg", "-y", "-ss", str(at), "-i", str(video_path),
                        "-frames:v", "1", "-vf", "scale=360:-2", str(dst), "-loglevel", "error"],
                       check=True)
    except Exception:                             # noqa: BLE001 — 썸네일은 없어도 진행된다
        pass


def register(app, require_login):
    """app.py에서 한 번 부른다. require_login(request)는 막을 때 응답을, 통과면 None을 준다."""

    @app.post("/api/longform/analyze")
    async def _analyze_api(request: Request, background: BackgroundTasks,
                           file: UploadFile = File(None), url: str = Form(""),
                           n_shorts: int = Form(5)):
        denied = require_login(request)
        if denied:
            return denied
        job_id = uuid.uuid4().hex[:12]
        d = _ROOT / job_id
        d.mkdir(parents=True, exist_ok=True)
        src = d / "source.mp4"
        if file is not None and file.filename:
            with src.open("wb") as fp:
                shutil.copyfileobj(file.file, fp)
        elif url.strip():
            # 링크로 받는 경로는 기존 다운로더를 그대로 쓴다(유튜브·인스타 등 동일 처리).
            from shopping_shorts.media_download import download_any
            got, _cap = download_any(url.strip(), str(d))
            if not got:
                return JSONResponse({"error": "영상을 받지 못했습니다"}, status_code=422)
            shutil.move(str(got), str(src))
        else:
            return JSONResponse({"error": "영상 파일이나 링크가 필요합니다"}, status_code=422)
        _set(job_id, status="queued", message="대기 중", source=str(src))
        background.add_task(_analyze, job_id, str(src), int(n_shorts))
        return {"job_id": job_id}

    @app.get("/api/longform/status")
    def _status(request: Request, job_id: str):
        denied = require_login(request)
        if denied:
            return denied
        st = _get(job_id)
        if not st:
            return JSONResponse({"error": "없는 작업입니다"}, status_code=404)
        st.pop("source", None)                    # 서버 경로는 화면에 안 보낸다
        return st

    @app.get("/api/longform/thumb")
    def _thumb_api(request: Request, job_id: str, idx: int):
        denied = require_login(request)
        if denied:
            return denied
        p = _ROOT / job_id / f"thumb{idx}.jpg"
        if not p.exists():
            return JSONResponse({"error": "no thumb"}, status_code=404)
        return FileResponse(str(p), media_type="image/jpeg")

    @app.post("/api/longform/render")
    def _render(request: Request, job_id: str = Form(...), idx: int = Form(...),
                template: str = Form(lf.DEFAULT_TEMPLATE), channel_name: str = Form("")):
        denied = require_login(request)
        if denied:
            return denied
        st = _get(job_id)
        if st.get("status") != "ready":
            return JSONResponse({"error": "아직 분석이 끝나지 않았습니다"}, status_code=409)
        shorts = st.get("shorts") or []
        if not (0 <= idx < len(shorts)):
            return JSONResponse({"error": "없는 구간입니다"}, status_code=404)
        src = (_ROOT / job_id / "source.mp4")
        out = _ROOT / job_id / f"short{idx}_{template}.mp4"
        try:
            info = lf.render_short(str(src), shorts[idx], str(out), template=template,
                                   channel_name=channel_name,
                                   work_dir=_ROOT / job_id / f"r{idx}")
        except Exception as exc:                  # noqa: BLE001
            traceback.print_exc()
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:300]}, status_code=500)
        return {"ok": True, "download": f"/api/longform/file?job_id={job_id}&idx={idx}"
                                        f"&template={template}", **info}

    @app.get("/api/longform/file")
    def _file(request: Request, job_id: str, idx: int, template: str = lf.DEFAULT_TEMPLATE):
        denied = require_login(request)
        if denied:
            return denied
        p = _ROOT / job_id / f"short{idx}_{template}.mp4"
        if not p.exists():
            return JSONResponse({"error": "아직 없습니다"}, status_code=404)
        return FileResponse(str(p), media_type="video/mp4",
                            filename=f"shorts_{job_id}_{idx}.mp4")

    @app.get("/api/longform/templates")
    def _templates(request: Request):
        denied = require_login(request)
        if denied:
            return denied
        return {"templates": [{"id": k, "label": v["label"]} for k, v in lf.TEMPLATES.items()],
                "default": lf.DEFAULT_TEMPLATE}
