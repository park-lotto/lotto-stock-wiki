"""관문 메모리 실측기 (관제 336) — 관문과 같은 조건(merge_gate.snapshot)으로 전체 시험을 돌리며 메모리를 잰다.

    py tools/gate_mem_probe.py --out <폴더> [--n 2] [--chunk 100]

5초마다: 관문 트리(루트+자식 전부) private 메모리 합 · 가장 큰 프로세스 · 남은 커밋 · 남은 물리 메모리 → <폴더>/mem.csv
끝나면 <폴더>/snapshot.json(실패 목록 포함)·summary.json. 안전장치는 관문 자체 감시(3000MB)에 맡기고, 2500MB 아래로 가면 '못 막음'으로 기록한다.
끝나면 관문 임시 폴더(TMP/gate_child_*)를 지운다(강제로 끄면 GB 단위로 남는다).
"""
import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parent.parent
KILL_COMMIT_MB = 2500


def _mem_status():
    import ctypes

    class _MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = _MS()
    m.dwLength = ctypes.sizeof(_MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    mb = 2 ** 20
    return int(m.ullAvailPageFile / mb), int(m.ullAvailPhys / mb), int(m.ullTotalPageFile / mb)


def _tree_private(root):
    total, biggest = 0, 0
    try:
        procs = [root] + root.children(recursive=True)
    except psutil.Error:
        return 0, 0, 0
    for p in procs:
        try:
            v = p.memory_info().private
        except psutil.Error:
            continue
        total += v
        biggest = max(biggest, v)
    mb = 2 ** 20
    return int(total / mb), int(biggest / mb), len(procs)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", default="2")
    ap.add_argument("--chunk", default="")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, GATE_XDIST_N=a.n, PYTHONIOENCODING="utf-8")
    if a.chunk:
        env["GATE_CHUNK_FILES"] = a.chunk
    code = ("import sys, json; sys.path.insert(0, 'tools'); import merge_gate; "
            "s = merge_gate.snapshot(cwd='.'); "
            f"json.dump(s, open(r'{out / 'snapshot.json'}', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)")
    t0 = time.time()
    proc = subprocess.Popen([sys.executable, "-c", code], cwd=str(ROOT), env=env)
    root = psutil.Process(proc.pid)
    peak_tree = peak_one = 0
    min_commit = min_phys = 10 ** 9
    killed = None
    with open(out / "mem.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sec", "tree_mb", "biggest_mb", "procs", "commit_free_mb", "phys_free_mb"])
        while proc.poll() is None:
            tree, one, n = _tree_private(root)
            commit, phys, _ = _mem_status()
            peak_tree, peak_one = max(peak_tree, tree), max(peak_one, one)
            min_commit, min_phys = min(min_commit, commit), min(min_phys, phys)
            w.writerow([int(time.time() - t0), tree, one, n, commit, phys])
            f.flush()
            if commit < KILL_COMMIT_MB and not killed:
                # 관문 자체 감시(merge_gate GATE_ABORT_FREE_MB=3000)가 먼저 끈다 — 여기는 기록만
                killed = f"커밋 여유 {commit}MB < {KILL_COMMIT_MB}MB (관문 감시가 못 막음)"
            time.sleep(5)
    proc.wait()
    removed = 0
    for p in Path(tempfile.gettempdir()).glob("gate_child_*"):
        shutil.rmtree(p, ignore_errors=True)
        removed += 1
    summary = {"sec": int(time.time() - t0), "rc": proc.returncode, "peak_tree_mb": peak_tree,
               "peak_one_mb": peak_one, "min_commit_free_mb": min_commit, "min_phys_free_mb": min_phys,
               "commit_total_mb": _mem_status()[2], "killed": killed, "temp_removed": removed,
               "xdist_n": a.n, "chunk": a.chunk or "기본"}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
