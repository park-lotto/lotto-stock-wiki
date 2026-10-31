# -*- coding: utf-8 -*-
"""버퍼 대기 영상에 '광고' 표시 입히기(사장님 2026-10-31 "광고 안 붙은 건 지나치지 말고 쿠팡 인포크할 때 다시 재렌더").
표시 모양·인코더는 판단 주인 ad_mark.apply_inplace 하나(GPU 있으면 NVENC). 여기는 드라이브에서 안전하게 바꾸는 일만 한다.

    py tools/buffer_badge.py "<드라이브 계정 폴더>" "<영상.mp4>"

① 내 PC 임시 폴더로 복사 → ② 표시 입힘 → ③ 길이·소리 대조 → ④ 원본은 폴더 `_원본\\` 으로, 새 영상은 같은 이름으로.
어느 단계든 실패하면 드라이브 원본은 그대로다. 이미 표식(ad_mark)이 있으면 아무것도 안 한다.
'광고' 글자를 눈으로 본 영상에는 부르지 마라 — 옛 영상은 글자가 있어도 표식이 없다.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools.calcopy.engine import ad_mark  # noqa: E402

ORIG = "_원본"
MAX_DRIFT = 0.15       # 입히기 전후 길이 차이 허용(초)
CHUNK = 256 * 1024
MAX_STALLS = 20        # 조금도 못 읽고 연속으로 끊긴 횟수 한도


def _length(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type", "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    words = (r.stdout or "").split()
    nums = [float(w) for w in words if w.replace(".", "", 1).isdigit()]
    return (nums[-1] if nums else 0.0), ("audio" in words)


def _fetch(src, dst, log=print):
    """드라이브에서 내려받기. 인터넷이 느리면 읽기가 끊긴다(OSError 22, 10-31 초당 14KB) — 받은 자리부터 이어서 받는다."""
    size = Path(src).stat().st_size
    done = stalls = 0
    with open(dst, "wb") as out:
        while done < size:
            try:
                with open(src, "rb") as f:
                    f.seek(done)
                    while b := f.read(CHUNK):
                        out.write(b)
                        done += len(b)
                        stalls = 0
            except OSError as e:
                stalls += 1
                if stalls > MAX_STALLS:
                    raise RuntimeError(f"드라이브 읽기 {stalls}번 연속 실패({done}/{size}): {e}")
                log(f"[buffer_badge] 읽기 끊김 {done}/{size} — 이어서({stalls})")
                time.sleep(min(60, 5 * stalls))


def apply(folder, video, log=print):
    """영상 하나에 표시를 입힌다. 반환 = {applied, why}."""
    d = Path(folder)
    src = d / video
    if not src.is_file():
        raise FileNotFoundError(src)
    if ad_mark.MARK in ad_mark._probe(src)[2]:
        return {"applied": False, "why": "이미 있음"}
    keep = d / ORIG / video
    if keep.exists():
        raise RuntimeError(f"{ORIG}\\ 에 같은 이름이 이미 있다 — 옛 원본을 덮지 않는다: {video}")
    size = src.stat().st_size
    with tempfile.TemporaryDirectory(prefix="buffer_badge_") as tmp:
        work = Path(tmp) / "in.mp4"
        _fetch(src, work, log)
        if work.stat().st_size != size:
            raise RuntimeError(f"복사 크기 어긋남: {video}")
        before, had_audio = _length(work)
        ad_mark.apply_inplace(work, log=log)
        after, has_audio = _length(work)
        if abs(after - before) > MAX_DRIFT or had_audio != has_audio:
            raise RuntimeError(f"입힌 뒤 어긋남: 길이 {before:.2f}→{after:.2f} 소리 {had_audio}→{has_audio}")
        part = d / (video + ".part")                # .mp4 가 아니라 buffer_post 가 집지 않는다
        shutil.copyfile(work, part)
        if part.stat().st_size != work.stat().st_size:
            part.unlink(missing_ok=True)
            raise RuntimeError(f"드라이브 쓰기 크기 어긋남: {video}")
        keep.parent.mkdir(exist_ok=True)
        shutil.move(str(src), str(keep))
        part.rename(src)
    log(f"[buffer_badge] {video} {before:.1f}초 → 표시 입힘 · 원본은 {ORIG}\\")
    return {"applied": True, "why": ""}


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    print(apply(sys.argv[1], sys.argv[2]))
