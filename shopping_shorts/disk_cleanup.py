"""디스크 자동 정리 — 완성본은 남기고 중간 재료만 버린다(2026-08-22).

## 왜 필요한가 (실측)

서버 디스크 309GB 중 182GB가 차 있었고(59%), 그중 101GB가 /tmp의 옛 실험
찌꺼기였다. 그건 손으로 지웠다. 문제는 **계속 자라는 쪽**이다:

    mix_jobs   26GB / 322건  = 작업 1건당 82MB
    thumb_cache 18GB / 158,002장

1기 회원 100명이 하루 1편씩만 만들어도 **하루 8.2GB, 한 달 246GB**가 쌓인다.
여유 226GB가 한 달을 못 버틴다. 디스크가 차면 렌더·수집이 통째로 죽는다.

## 무엇을 지우고 무엇을 남기나

**남긴다(절대 안 지움)**
  - `final.mp4` — 완성본. 고객의 결과물이다.
  - `preview.mp4` / `clean_preview.mp4` — 화면이 다시 열 때 쓴다.
  - `thumb.png`·`cover.*` 등 완성 썸네일
  - DB, 로그, 진행 중인 작업 폴더 전체

**지운다(오래된 것만)**
  - `s0`,`s1`,… — 소스 클립 원본. 렌더가 끝나면 완성본 안에 이미 들어가 있다.
  - `seg_thumbs`, `tts`, `frames`, `tmp` — 중간 산출물
  - 썸네일 캐시 — 상한을 넘으면 **오래 안 쓴 것부터**(LRU)

## 안전장치 (이 순서로 지킨다)

1. **진행 중인 작업은 손대지 않는다.** 상태가 done/failed가 아니거나,
   최근에 수정됐으면 건너뛴다 — 렌더 도중 재료를 빼면 그 작업이 깨진다.
2. **보관 기간(기본 14일)** 안의 작업은 손대지 않는다. 고객이 그 사이
   다시 열어 편집할 수 있다.
3. **DB가 아는 파일만 보호 목록에 넣지 않는다** — 반대다. 지울 대상을
   이름으로 **화이트리스트**하고, 모르는 파일은 **남긴다**. 지우는 쪽이
   보수적이어야 한다(모르면 안 지운다).
4. `--dry-run`이 기본값이 아니라 **명시 인자**다. 대신 실행 결과를 항상
   로그로 남긴다 — 조용히 지우면 나중에 "왜 없어졌지"가 된다.

⚠️ 경로는 반드시 mix_jobs / thumb_cache 아래인지 확인하고 지운다. 상위로
   빠져나가는 경로(심볼릭 링크·`..`)는 건너뛴다.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

# ── 정책 값 — 운영 중 바꿔야 할 수 있으니 환경변수로 연다 ──────────────
# 보관 기간: 이 기간 안의 작업은 재료까지 그대로 둔다(고객이 다시 편집할 수 있다).
RETENTION_DAYS = int(os.getenv("SHORTS_KEEP_DAYS", "14"))
# 썸네일 캐시 상한(GB). 넘으면 오래 안 쓴 것부터 지운다.
THUMB_CACHE_MAX_GB = float(os.getenv("SHORTS_THUMB_CACHE_GB", "8"))

# 지워도 되는 중간 산출물 — **이름으로 화이트리스트**. 여기 없는 건 안 지운다.
_JUNK_DIR_EXACT = {"seg_thumbs", "tts", "frames", "tmp", "work", "audio", "parts"}
_JUNK_DIR_PREFIX = ("s",)        # s0, s1, … 소스 클립 폴더

# 절대 지우지 않는 파일 이름(완성본·미리보기·썸네일)
_KEEP_FILES = {"final.mp4", "preview.mp4", "clean_preview.mp4",
               "thumb.png", "thumb.jpg", "cover.png", "cover.jpg"}


def _is_junk_dir(name: str) -> bool:
    """이 하위 폴더가 '중간 재료'인가. 애매하면 False(남긴다)."""
    if name in _JUNK_DIR_EXACT:
        return True
    # s0, s12 처럼 s + 숫자만. 's'로 시작한다고 다 지우면 'scripts' 같은 걸 날린다.
    for p in _JUNK_DIR_PREFIX:
        if name.startswith(p) and name[len(p):].isdigit():
            return True
    return False


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _inside(child: Path, parent: Path) -> bool:
    """child가 정말 parent 아래인가(심볼릭 링크·'..' 탈출 차단)."""
    try:
        return parent.resolve() in child.resolve().parents
    except OSError:
        return False


def _job_is_settled(store, job_id: str) -> bool:
    """이 작업이 '끝난' 상태인가. 모르면 False(안 지운다).

    진행 중인 작업의 재료를 빼면 그 작업이 깨진다 — 판단이 안 서면 남긴다.
    """
    try:
        row = store.get_mix_job(job_id)
    except Exception:      # noqa: BLE001 — DB가 흔들려도 정리 때문에 죽지 않는다
        return False
    if not row:
        # DB에 없는 폴더 = 옛 작업이 지워진 뒤 남은 껍데기. 나이 조건은 호출부가 본다.
        return True
    return (row.get("status") or "") in ("done", "failed")


def clean_mix_jobs(data_dir, store=None, keep_days=None, dry_run=False):
    """완료된 옛 작업의 **중간 재료만** 지운다. (지운 바이트, 건드린 작업 수) 반환."""
    keep_days = RETENTION_DAYS if keep_days is None else keep_days
    root = Path(data_dir) / "mix_jobs"
    if not root.is_dir():
        return 0, 0
    cutoff = time.time() - keep_days * 86400
    freed = 0
    touched = 0
    for job_dir in root.iterdir():
        if not job_dir.is_dir() or job_dir.is_symlink():
            continue
        try:
            if job_dir.stat().st_mtime > cutoff:
                continue                      # 아직 보관 기간 안 — 손대지 않는다
        except OSError:
            continue
        if store is not None and not _job_is_settled(store, job_dir.name):
            continue                          # 진행 중이거나 알 수 없다 — 남긴다
        for child in job_dir.iterdir():
            if child.is_symlink() or not child.is_dir():
                continue                      # 파일은 안 건드린다(_KEEP_FILES 보호)
            if not _is_junk_dir(child.name):
                continue
            if not _inside(child, root):
                continue                      # 경로가 밖을 가리키면 건너뛴다
            size = _dir_size(child)
            if not dry_run:
                shutil.rmtree(child, ignore_errors=True)
            freed += size
            touched += 1
    return freed, touched


def trim_thumb_cache(data_dir, max_gb=None, dry_run=False):
    """썸네일 캐시를 상한까지 줄인다 — **오래 안 쓴 것부터**(atime 없으면 mtime).

    캐시는 정의상 다시 만들 수 있다. 그래서 나이가 아니라 **총량**으로 자른다.
    """
    max_gb = THUMB_CACHE_MAX_GB if max_gb is None else max_gb
    root = Path(data_dir) / "thumb_cache"
    if not root.is_dir():
        return 0, 0
    limit = int(max_gb * 1024 ** 3)
    files = []
    total = 0
    for root_dir, _dirs, names in os.walk(root):
        for n in names:
            p = Path(root_dir) / n
            try:
                st = p.stat()
            except OSError:
                continue
            files.append((st.st_atime or st.st_mtime, st.st_size, p))
            total += st.st_size
    if total <= limit:
        return 0, 0
    files.sort()                              # 오래된 접근 순
    freed = 0
    removed = 0
    for _atime, size, p in files:
        if total - freed <= limit:
            break
        if not _inside(p, root):
            continue
        if not dry_run:
            try:
                p.unlink()
            except OSError:
                continue
        freed += size
        removed += 1
    return freed, removed


def _gb(n):
    return f"{n / 1024 ** 3:.2f}GB"


def run(data_dir, store=None, dry_run=False):
    """크론·daily_batch 엔트리포인트. 사람이 읽을 한 줄을 반환한다."""
    j_bytes, j_dirs = clean_mix_jobs(data_dir, store=store, dry_run=dry_run)
    t_bytes, t_files = trim_thumb_cache(data_dir, dry_run=dry_run)
    tag = "[모의]" if dry_run else ""
    return (f"디스크정리{tag}: 작업재료 {_gb(j_bytes)}({j_dirs}폴더) · "
            f"썸네일캐시 {_gb(t_bytes)}({t_files}장) · "
            f"보관 {RETENTION_DAYS}일 · 캐시상한 {THUMB_CACHE_MAX_GB}GB")


if __name__ == "__main__":       # python -m shopping_shorts.disk_cleanup [--dry-run]
    import sys

    from shopping_shorts.config import DB_PATH
    from shopping_shorts.store import Store

    dry = "--dry-run" in sys.argv
    data = Path(DB_PATH).parent
    print(run(data, store=Store(DB_PATH), dry_run=dry))
