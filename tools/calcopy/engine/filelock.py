# -*- coding: utf-8 -*-
"""작은 파일 잠금(프로세스 사이, 윈도우·리눅스 공통) — 읽기-수정-쓰기를 원자적으로 (관제 097, 2026-10-18).

왜: 10-18 한혜진 편 — name_check 두 목소리를 동시에 돌려 name_dict.json 을 서로 덮어썼고, checks 두 판 동시엔 stage_log.json 줄이 사라졌다.
잠금 파일 <대상>.lock 을 O_EXCL 로 만든 쪽이 주인. STALE_SEC 넘은 잠금은 죽은 프로세스 것으로 보고 치운다.

    from tools.calcopy.engine.filelock import locked
    with locked(path):            # path 는 보호할 파일(잠금 파일은 path + ".lock")
        d = read(); d[...] = ...; write(d)
"""
from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path

STALE_SEC = 120.0


@contextlib.contextmanager
def locked(path, timeout: float = 60.0):
    lk = Path(str(path) + ".lock")
    lk.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    while True:
        try:
            fd = os.open(str(lk), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode()); os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lk.stat().st_mtime > STALE_SEC:
                    lk.unlink()
                    continue
            except OSError:
                continue
            if time.time() - t0 > timeout:
                raise TimeoutError(f"잠금 대기 초과: {lk}")
            time.sleep(0.05 + (time.time() * 1000 % 50) / 1000)
    try:
        yield
    finally:
        try:
            lk.unlink()
        except OSError:
            pass
