"""캡컷에서 고친 영상(편집본) — 저장·판정을 **이 파일 한 곳에서만** 한다(0순위-B).

왜(2026-09-22 사장님): "캡컷으로 보내서 작업한 걸 버퍼에 다시 올릴 수 있게."
Buffer 예약은 우리가 렌더한 완성본(final.mp4)만 보냈다. 캡컷에서 손본 영상을
다시 넣을 길이 없었다.

작업 폴더 안에 둔다:
  edited.mp4   고객이 올린 편집본(faststart 처리됨)
  edited.json  {name, size, duration, uploaded_at, stale}

★stale — 완성본을 **새로 렌더하면** 옛 편집본은 옛 완성본을 고친 것이라 기본값에서 뺀다.
  그래도 파일은 지우지 않는다: 이미 예약해 둔 게시물은 게시 시점에 이 파일을 가져간다
  (Buffer는 파일을 안 받고 URL을 나중에 읽는다). 지우면 예약이 조용히 실패한다.
"""
import json
import os
import subprocess
import time
from pathlib import Path

VIDEO_NAME = "edited.mp4"
META_NAME = "edited.json"
MAX_BYTES = 500 * 1024 * 1024          # 쇼츠 1편에 넉넉한 상한
MAX_SECONDS = 600


def paths(work_dir):
    d = Path(work_dir)
    return d / VIDEO_NAME, d / META_NAME


def read_meta(work_dir):
    """편집본 정보. 없으면 None."""
    vid, meta = paths(work_dir)
    if not vid.is_file():
        return None
    try:
        m = json.loads(meta.read_text(encoding="utf-8"))
    except Exception:
        m = {}
    m.setdefault("stale", False)
    m["size"] = vid.stat().st_size
    return m


def active_path(work_dir):
    """예약 때 기본으로 나갈 편집본 경로. 없거나 옛 렌더 것이면 None."""
    m = read_meta(work_dir)
    if not m or m.get("stale"):
        return None
    return str(paths(work_dir)[0])


def served_path(work_dir):
    """공개 링크(/api/share/e)가 내줄 파일 — stale이어도 준다(예약된 게시물 보호)."""
    vid, _ = paths(work_dir)
    return str(vid) if vid.is_file() else None


def probe_duration(path):
    """ffprobe로 길이(초). mp4로 안 읽히면 None."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return None
        return float((r.stdout or "").strip().splitlines()[0])
    except Exception:
        return None


def save(work_dir, data, filename, faststart):
    """받은 바이트를 검사해 편집본으로 둔다. (meta, None) 또는 (None, 한국어 오류)."""
    if not data:
        return None, "빈 파일이에요."
    if len(data) > MAX_BYTES:
        return None, "500MB까지 올릴 수 있어요."
    d = Path(work_dir)
    d.mkdir(parents=True, exist_ok=True)
    vid, meta = paths(d)
    tmp = d / "edited.up.mp4"
    tmp.write_bytes(data)
    dur = probe_duration(tmp)
    if not dur or dur <= 0:
        tmp.unlink(missing_ok=True)
        return None, "영상 파일로 읽히지 않아요 — 캡컷에서 MP4로 내보낸 파일을 올려주세요."
    if dur > MAX_SECONDS:
        tmp.unlink(missing_ok=True)
        return None, "10분이 넘는 영상은 올릴 수 없어요."
    # ★Buffer는 moov가 뒤에 있으면 "Video could not be read"로 거절한다(08-30 실측).
    #   캡컷 내보내기가 어느 쪽인지 장담 못 하니 받자마자 앞으로 옮긴다.
    faststart(str(tmp))
    os.replace(str(tmp), str(vid))
    m = {"name": os.path.basename(filename or "")[:80] or VIDEO_NAME,
         "duration": round(dur, 2), "uploaded_at": int(time.time()), "stale": False}
    meta.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    m["size"] = vid.stat().st_size
    return m, None


def remove(work_dir):
    for p in paths(work_dir):
        try:
            p.unlink()
        except FileNotFoundError:
            pass


def mark_stale(work_dir):
    """새 완성본이 나왔다 — 옛 편집본을 기본값에서 뺀다(파일은 남긴다)."""
    _, meta = paths(work_dir)
    m = read_meta(work_dir)
    if not m or m.get("stale"):
        return
    m.pop("size", None)
    m["stale"] = True
    meta.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
