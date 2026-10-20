# -*- coding: utf-8 -*-
"""부품 렌더 — 판단 주인 render_part (관제 244).
폴더 준비(조각 + brand 복사) → HyperFrames 0.8.105 렌더(mp4) → ffprobe → 프레임 시트(12칸) → renders.jsonl 에 시간 기록.
산출물 폴더: shopping_shorts/data/mograph/renders/<slug>/ (data/ 는 git 밖) — out.mp4 · sheet.png · status.json
실측(2026-10-20 이 PC, rx-morph-ui 12초·360프레임): hyperframes 17.4초(설정 3.9·캡처 9.7·인코딩 3.3), 벽시계 22.8초(npx 기동 포함)."""
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

from shopping_shorts.mograph import ledger, sources

HF_VERSION = "0.8.105"
RENDERS_DIR = Path(__file__).resolve().parents[1] / "data" / "mograph" / "renders"
LOG = RENDERS_DIR.parent / "renders.jsonl"
SHEET_TILES = 12
_RUNNING = {}
_LOCK = threading.Lock()


def out_dir(slug):
    return RENDERS_DIR / slug


def status(slug):
    p = out_dir(slug) / "status.json"
    if not p.exists():
        return {"slug": slug, "state": "none"}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:       # noqa: BLE001 — 쓰는 도중 읽힘
        return {"slug": slug, "state": "running"}


def _put(slug, **kw):
    d = out_dir(slug)
    d.mkdir(parents=True, exist_ok=True)
    st = status(slug)
    st.update(kw)
    st["slug"] = slug
    st["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = d / "status.json.tmp"
    tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, d / "status.json")
    return st


def _run(cmd, cwd, timeout):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout, shell=(os.name == "nt"))


def probe(mp4):
    r = _run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
              "stream=width,height,r_frame_rate,nb_frames:format=duration", "-of", "json", str(mp4)], mp4.parent, 60)
    try:
        j = json.loads(r.stdout)
        s = (j.get("streams") or [{}])[0]
        return {"w": s.get("width"), "h": s.get("height"), "fps": s.get("r_frame_rate"), "frames": s.get("nb_frames"),
                "duration": float((j.get("format") or {}).get("duration") or 0)}
    except Exception:       # noqa: BLE001
        return {"error": (r.stderr or r.stdout)[-400:]}


def contact_sheet(mp4, png, duration_s, tiles=SHEET_TILES):
    """영상 전체를 tiles 칸으로 고르게 뽑은 시트(4열). iart-ai/motion-skills 의 contact-sheet 와 같은 용도 — 규격만 잰다, 품질은 눈."""
    step = max(duration_s / tiles, 1 / 30)
    cols = 4
    rows = -(-tiles // cols)
    vf = "fps=1/%.4f,scale=320:-1,tile=%dx%d:padding=4:margin=4" % (step, cols, rows)
    r = _run(["ffmpeg", "-y", "-v", "error", "-i", str(mp4), "-vf", vf, "-frames:v", "1", str(png)], mp4.parent, 120)
    return png.exists() and png.stat().st_size > 0, (r.stderr or "")[-400:]


def prepare(slug, rec):
    """렌더 폴더 만들기 — scene 은 원본 조각 + brand 복사. overlay 는 아직 렌더 길이 없다(2차: HyperFrames 래퍼)."""
    if rec.get("kind") != "scene":
        raise ValueError("지금은 scene(원본 HTML 조각)만 렌더한다 — overlay 는 편집기 렌더 길(check_countdown.py)로")
    impl = rec.get("impl") or {}
    piece = sources.piece_dir(impl.get("pack"), impl.get("folder"))
    brand = sources.brand_dir(impl.get("pack"))
    if not piece or not brand:
        raise FileNotFoundError("원본 폴더 없음: %s/%s (MOGRAPH_REF_DIR=%s)" % (impl.get("pack"), impl.get("folder"), sources.ref_dir()))
    src = out_dir(slug) / "src"
    if src.exists():
        shutil.rmtree(src)
    shutil.copytree(piece, src)
    shutil.copytree(brand, src / "brand", dirs_exist_ok=True)
    return src


def render_part(slug, fps=30, quality="looks"):
    """동기 렌더(주인). 되돌려 주는 값 = status dict. 작업대는 render_async 로 부른다."""
    is_work = slug.startswith("work-")          # 작업물(compose.build_work 가 src 를 이미 만들어 둠)
    rec = None if is_work else ledger.find_part(slug)
    if not is_work and not rec:
        raise KeyError("없는 부품: %s" % slug)
    t0 = time.time()
    _put(slug, state="running", step="prepare", started=time.strftime("%Y-%m-%d %H:%M:%S"))
    try:
        if is_work:
            src = out_dir(slug) / "src"
            if not (src / "index.html").exists():
                raise FileNotFoundError("작업물 폴더 없음: %s" % src)
        else:
            src = prepare(slug, rec)
        d = out_dir(slug)
        mp4 = d / "out.mp4"
        if mp4.exists():
            mp4.unlink()
        _put(slug, step="hyperframes")
        t1 = time.time()
        r = _run(["npx", "-y", "hyperframes@" + HF_VERSION, "render", "src", "--quality", quality, "--fps", str(fps), "-o", "out.mp4"],
                 d, 1800)
        hf_s = round(time.time() - t1, 1)
        (d / "render.log").write_text((r.stdout or "") + "\n--- stderr ---\n" + (r.stderr or ""), encoding="utf-8")
        if r.returncode != 0 or not mp4.exists():
            raise RuntimeError("hyperframes rc=%s — render.log 참고: %s" % (r.returncode, (r.stderr or r.stdout)[-300:]))
        _put(slug, step="probe")
        pr = probe(mp4)
        _put(slug, step="sheet")
        ok, err = contact_sheet(mp4, d / "sheet.png", pr.get("duration") or ((rec or {}).get("duration_ms", 0) / 1000) or 1)
        if not ok:
            raise RuntimeError("프레임 시트 실패: " + err)
        total = round(time.time() - t0, 1)
        st = _put(slug, state="done", step="done", hyperframes_s=hf_s, elapsed_s=total, probe=pr,
                  mp4_bytes=mp4.stat().st_size, files={"mp4": "out.mp4", "sheet": "sheet.png", "log": "render.log"},
                  hf_version=HF_VERSION, fps=fps, quality=quality)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"at": st["updated"], "slug": slug, "elapsed_s": total, "hyperframes_s": hf_s,
                                "duration": pr.get("duration"), "frames": pr.get("frames"), "mp4_bytes": st["mp4_bytes"]},
                               ensure_ascii=False) + "\n")
        return st
    except Exception as e:      # noqa: BLE001 — 실패도 status 에 남긴다(조용한 실패 금지)
        return _put(slug, state="error", error=str(e)[:600], elapsed_s=round(time.time() - t0, 1))


def render_async(slug):
    """백그라운드 스레드 1개(같은 slug 중복 시작 안 함). 되돌려 주는 값 = 시작했나."""
    with _LOCK:
        th = _RUNNING.get(slug)
        if th and th.is_alive():
            return False
        th = threading.Thread(target=render_part, args=(slug,), daemon=True, name="mograph-render-" + slug)
        _RUNNING[slug] = th
        th.start()
        return True


def recent(limit=50):
    if not LOG.exists():
        return []
    rows = [json.loads(ln) for ln in LOG.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return rows[-limit:]
