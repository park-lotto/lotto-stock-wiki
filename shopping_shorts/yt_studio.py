"""유튜브제작 — 사장님 유튜브 영상(광고·설명) 제작 관리판 (관제 185, 관리자 전용).

씬마다 대사·준비 체크·자료(사진·영상·음성)·녹음·TTS를 한곳에 모은다.
상태는 git 밖 data/yt_studio/state.json 한 파일, 올린 파일은 data/yt_studio/files/.
판단(상태 바꾸기·기록 남기기)은 apply_op 한 곳에서만 한다 — 화면은 op 이름만 보낸다.
"""
import json
import re
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

_DIR = Path(__file__).parent / "data" / "yt_studio"
_SEED = Path(__file__).parent / "yt_studio_seed.json"
_LOCK = threading.Lock()
STATUSES = ("todo", "doing", "done", "skip")
_SAFE_NAME = re.compile(r"[^\w가-힣.\-() ]+")
MAX_UPLOAD = 300 * 1024 * 1024
_LOG_KEEP = 3000


def _now():
    return datetime.now().isoformat(timespec="seconds")


def files_dir():
    d = _DIR / "files"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_path():
    return _DIR / "state.json"


def load():
    p = _state_path()
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    st = json.loads(_SEED.read_text(encoding="utf-8")) if _SEED.exists() else {}
    for k in ("items", "scripts", "files", "requests", "log"):
        st.setdefault(k, [])
    return st


def _save(st):
    _DIR.mkdir(parents=True, exist_ok=True)
    tmp = _state_path().with_suffix(".tmp")
    tmp.write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    tmp.replace(_state_path())


def _log(st, project, text):
    st["log"].append({"at": _now(), "project": project, "text": text})
    if len(st["log"]) > _LOG_KEEP:
        st["log"] = st["log"][-_LOG_KEEP:]


def _find(rows, rid):
    for r in rows:
        if r.get("id") == rid:
            return r
    raise ValueError("없는 항목입니다")


def apply_op(op, b):
    """화면이 보낸 변경 하나를 적용하고 새 상태를 돌려준다."""
    with _LOCK:
        st = load()
        if op == "status":
            it = _find(st["items"], b.get("id"))
            s = b.get("status")
            if s not in STATUSES:
                raise ValueError("상태 값이 이상합니다")
            it["status"], it["updatedAt"] = s, _now()
            _log(st, it["project"], f"[{it['scene']}] {it['title']} → {_KO[s]}")
        elif op == "memo":
            it = _find(st["items"], b.get("id"))
            v = str(b.get("memo") or "")[:4000]
            if v != it.get("memo"):
                it["memo"], it["updatedAt"] = v, _now()
                _log(st, it["project"], f"[{it['scene']}] {it['title']} 메모: {v[:40]}")
        elif op == "add_item":
            title = str(b.get("title") or "").strip()[:300]
            if not title:
                raise ValueError("내용을 적어 주세요")
            scene, project = str(b.get("scene")), str(b.get("project"))
            orders = [i["order"] for i in st["items"] if i["scene"] == scene] or [0]
            st["items"].append({"id": "i" + uuid.uuid4().hex[:10], "project": project, "scene": scene,
                                "order": max(orders) + 0.01, "title": title, "detail": "", "owner": "사장님",
                                "status": "todo", "memo": "", "updatedAt": _now()})
            _log(st, project, f"[{scene}] 추가: {title}")
        elif op == "script":
            sc = _find(st["scripts"], b.get("id"))
            v = str(b.get("text") or "")[:60000]
            if v != sc.get("text"):
                sc["text"], sc["updatedAt"] = v, _now()
                _log(st, sc["project"], f"[{sc['scene']}] 대사 수정 ({len(v)}자)")
        elif op == "pick":
            f = _find(st["files"], b.get("id"))
            on = not f.get("pick")
            for o in st["files"]:
                if o["project"] == f["project"] and o["scene"] == f["scene"] and o["type"].startswith("audio/"):
                    o["pick"] = False
            f["pick"] = on
            _log(st, f["project"], f"[{f['scene']}] 음성 {'채택' if on else '채택 해제'}: {f['name']}")
        elif op == "delete_file":
            f = _find(st["files"], b.get("id"))
            st["files"].remove(f)
            try:
                (files_dir() / f["stored"]).unlink()
            except FileNotFoundError:
                pass
            _log(st, f["project"], f"[{f['scene']}] 자료 삭제: {f['name']}")
        else:
            raise ValueError("모르는 작업입니다")
        _save(st)
        return st


_KO = {"todo": "할 일", "doing": "진행 중", "done": "완료", "skip": "안 씀"}


def add_file(project, scene, name, ctype, data, source="직접 올림"):
    name = _SAFE_NAME.sub("_", name or "file")[:120] or "file"
    stored = uuid.uuid4().hex + Path(name).suffix.lower()[:8]
    (files_dir() / stored).write_bytes(data)
    with _LOCK:
        st = load()
        st["files"].append({"id": "f" + uuid.uuid4().hex[:10], "project": project, "scene": scene,
                            "name": name, "type": ctype or "application/octet-stream", "stored": stored,
                            "size": len(data), "at": _now(), "pick": False, "source": source})
        _log(st, project, f"[{scene}] 자료 추가: {name}")
        _save(st)
        return st


def file_path(fid):
    st = load()
    f = _find(st["files"], fid)
    return files_dir() / f["stored"], f


# ── TTS ─────────────────────────────────────────────────────────────
# 대사 칸의 [화면: …] 같은 지시 줄·대괄호 꼬리표는 읽지 않는다. 일레븐랩스 한 번에
# 너무 긴 글은 실패하므로 빈 줄 단위로 2,000자 이하 조각으로 나눠 합성한 뒤 이어 붙인다.
_CHUNK = 2000


def tts_text(text):
    lines = [ln for ln in (text or "").splitlines() if not ln.strip().startswith("[")]
    return re.sub(r"\[[^\]]*\]", "", "\n".join(lines)).strip()


def _chunks(text):
    out, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        if cur and len(cur) + len(para) + 2 > _CHUNK:
            out.append(cur)
            cur = ""
        cur = (cur + "\n\n" + para).strip()
    if cur:
        out.append(cur)
    return out


def start_tts(project, scene, voice_id, voice_name):
    with _LOCK:
        st = load()
        sc = next((s for s in st["scripts"] if s["project"] == project and s["scene"] == scene), None)
        if not sc:
            raise ValueError("이 씬에는 대사가 없습니다")
        text = tts_text(sc["text"])
        if not text:
            raise ValueError("읽을 대사가 없습니다")
        rid = "r" + uuid.uuid4().hex[:10]
        st["requests"].append({"id": rid, "project": project, "scene": scene, "at": _now(),
                               "status": "running", "voice": voice_name or voice_id, "note": f"{len(text)}자"})
        _log(st, project, f"[{scene}] TTS 시작 — {voice_name or voice_id}")
        _save(st)
    threading.Thread(target=_run_tts, args=(rid, project, scene, text, voice_id, voice_name), daemon=True).start()
    return rid


def _set_req(rid, **kw):
    with _LOCK:
        st = load()
        for r in st["requests"]:
            if r["id"] == rid:
                r.update(kw)
        if kw.get("status") == "failed":
            r0 = next(r for r in st["requests"] if r["id"] == rid)
            _log(st, r0["project"], f"[{r0['scene']}] TTS 실패 — {kw.get('note', '')}")
        _save(st)


def _run_tts(rid, project, scene, text, voice_id, voice_name):
    from shopping_shorts import tts
    work = _DIR / "tmp" / rid
    work.mkdir(parents=True, exist_ok=True)
    try:
        parts = []
        chunks = _chunks(text)
        for n, c in enumerate(chunks):
            _set_req(rid, note=f"{n + 1}/{len(chunks)} 조각 합성 중")
            p = work / f"{n:03d}.mp3"
            tts.synthesize_tts(c, str(p), voice_id=voice_id, customer_id=0,
                               previous_text=chunks[n - 1][-300:] if n else None,
                               next_text=chunks[n + 1][:300] if n + 1 < len(chunks) else None)
            if not p.exists() or p.stat().st_size < 1000:
                raise RuntimeError("음성 파일이 비었습니다(키 확인 필요)")
            parts.append(p)
        out = work / "out.mp3"
        if len(parts) == 1:
            shutil.copy(parts[0], out)
        else:
            lst = work / "list.txt"
            lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                            "-i", str(lst), "-c", "copy", str(out)], check=True, timeout=300)
        stamp = time.strftime("%m%d_%H%M")
        add_file(project, scene, f"TTS_{scene.split(' ')[0]}_{voice_name or 'voice'}_{stamp}.mp3",
                 "audio/mpeg", out.read_bytes(), source=f"TTS · {voice_name or voice_id}")
        _set_req(rid, status="done", note=f"{len(chunks)}조각 완료")
    except Exception as e:  # 실패는 화면 요청 줄과 기록에 그대로 남긴다(조용히 삼키지 않는다)
        _set_req(rid, status="failed", note=str(e)[:200])
    finally:
        shutil.rmtree(work, ignore_errors=True)
