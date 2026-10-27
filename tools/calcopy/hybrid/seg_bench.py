# -*- coding: utf-8 -*-
"""대본 쓰기 → 장면 맞추기 구간만 반복 시험 + 기록(10-27 사장님 "그 구간들만 계속 · 규칙을 바꾸면서 안 좋아지면 안 된다").

    PYTHONUTF8=1 py -m tools.calcopy.hybrid.seg_bench run <재료까지 받은 작업 폴더> --name <편 이름> [--label "<무엇을 바꿨나>"]
    PYTHONUTF8=1 py -m tools.calcopy.hybrid.seg_bench table [--name <편 이름>]

run = 작업 폴더를 <폴더>_seg<n> 으로 복사 → 대본 단계로 되돌림 → flow_dev --resume --approve --stop-at thumb(장면 맞추기 통과 직후 멈춤, 렌더 안 함)
     → 잰 값 한 줄을 기록(channel/칼카피_제작순서/구간시험.jsonl)에 쌓고 같은 편 직전 줄과 비교(나빠진 칸 표시).
잰 값: 대본 판정 수 · 장면 판정 수 · 장면 반려 수 · 첫 장면 반려에 걸린 문제 수 · 대본·장면 분 · 장면 통과 여부 · 커밋.
검사 기준(문턱)은 이 도구가 바꾸지 않는다 — 통과는 언제나 같은 관문을 넘은 것이다."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LEDGER = ROOT / "channel" / "칼카피_제작순서" / "구간시험.jsonl"
RESET = ("script", "approved", "_redo", "stopped", "_asker", "watch_keys", "_msheets", "auto", "look", "eye_pack", "_fix_bad",
         "redo_hist", "_n_cuts", "_shown_stage", "watch_last")
WORSE = ("script_n", "plan_n", "plan_rej", "first_rej_items", "min")     # 클수록 나쁜 칸


def prep(src: Path) -> Path:
    n = 1
    while (dst := src.parent / f"{src.name}_seg{n}").exists():
        n += 1
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("reviews", "flow_log.jsonl", "run_stdout.txt", "runner_stderr.txt", "pending.json"))
    sp = dst / "flow_state.json"
    s = sp.read_text(encoding="utf-8").replace(src.name.join(("/", "/")), dst.name.join(("/", "/"))).replace(src.name.join(("\\\\", "\\\\")), dst.name.join(("\\\\", "\\\\")))
    d = json.loads(s)
    st = d.get("state", d)
    st["phase"], st["tries"] = "script", {}
    for k in [k for k in st if k.startswith("_plan") or k in RESET]:
        st.pop(k, None)
    sp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return dst


def import_member(flow_dir: Path, dst: Path) -> Path:
    """회원 PC 편(…/home/창고/flow/<sid>: flow.json 의 서명 payload = 지시서 상태 · job = 실행기 폴더) → flow_dev 작업 폴더(flow_state.json + job).
    서로 다른 소재로 시험 세트를 넓힌다(10-27 사장님 '같은 주제 영상으로만 하면 의미 있어?')."""
    import base64
    import zlib
    raw = json.loads((flow_dir / "flow.json").read_text(encoding="utf-8"))["payload"].split(".", 3)[2]
    st = json.loads(zlib.decompress(base64.urlsafe_b64decode(raw.encode())).decode("utf-8"))
    dst.mkdir(parents=True, exist_ok=True)
    if not (dst / "job").exists():
        shutil.copytree(flow_dir / "job", dst / "job", ignore=shutil.ignore_patterns("reviews"))
    (dst / "flow_state.json").write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    (dst / "flow_log.jsonl").write_text("", encoding="utf-8")
    return dst


def score(W: Path) -> dict:
    rows = [json.loads(l) for l in (W / "flow_log.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rv = [r for r in rows if "review" in r and isinstance(r.get("review"), str)]
    sn = sum(1 for r in rv if r["review"].startswith("script_"))
    pn = sum(1 for r in rv if r["review"].startswith("plan_"))
    asks = sorted((W / "job" / "reviews").glob("*plan_*/ask.txt"))
    rej = [a for a in asks if "멈춘 이유(재료를 고쳐라)" in a.read_text(encoding="utf-8")]
    first = 0
    if rej:
        t = rej[0].read_text(encoding="utf-8")
        body = t.split("멈춘 이유(재료를 고쳐라):", 1)[1].split("★한 번에 다 고쳐라")[0]
        first = len([x for x in body.split("; ") if x.strip()])
    secs = [r["t"] for r in rows if "t" in r]
    h = lambda t: int(t[:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8])    # noqa: E731
    passed = any(str(r.get("phase") or "").startswith("thumb") for r in rows)     # 장면 맞추기 통과 = 다음 단계(thumb) 에 닿음
    return {"script_n": sn, "plan_n": pn, "plan_rej": len(rej), "first_rej_items": first,
            "min": round((h(secs[-1]) - h(secs[0])) / 60, 1) if secs else None, "passed": passed}


def seed(W: Path, name: str, label: str) -> dict:
    """이미 돌린 작업 폴더(대본 단계부터 돌린 것)를 기록에 한 줄로 — 기준선."""
    row = {"name": name, "at": time.strftime("%m-%d %H:%M"), "commit": "", "label": label, "work": str(W), **score(W)}
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("work")
    r.add_argument("--name", required=True)
    r.add_argument("--label", default="")
    t = sub.add_parser("table")
    t.add_argument("--name")
    im = sub.add_parser("import")
    im.add_argument("flow_dir")
    im.add_argument("dst")
    a = ap.parse_args(argv)
    if a.cmd == "import":
        print(import_member(Path(a.flow_dir), Path(a.dst)))
        return 0
    if a.cmd == "table":
        for l in LEDGER.read_text(encoding="utf-8").splitlines() if LEDGER.exists() else []:
            o = json.loads(l)
            if not a.name or o["name"] == a.name:
                print(json.dumps(o, ensure_ascii=False))
        return 0
    src = Path(a.work)
    st0 = json.loads((src / "flow_state.json").read_text(encoding="utf-8"))
    st0 = st0.get("state", st0)
    W = prep(src)
    env = {**os.environ, "PYTHONUTF8": "1"}
    cmd = [sys.executable, str(ROOT / "tools/calcopy/hybrid/flow_dev.py"), "--work", str(W), "--ref", st0["ref"], "--version", st0["version"],
           "--resume", "--approve", "--stop-at", "thumb"]
    with (W / "run_stdout.txt").open("w", encoding="utf-8") as f:
        subprocess.run(cmd, cwd=str(ROOT), env=env, stdout=f, stderr=subprocess.STDOUT)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), capture_output=True, text=True).stdout.strip()
    row = {"name": a.name, "at": time.strftime("%m-%d %H:%M"), "commit": commit, "label": a.label, "work": str(W), **score(W)}
    prev = None
    if LEDGER.exists():
        prev = next((json.loads(l) for l in reversed(LEDGER.read_text(encoding="utf-8").splitlines()) if json.loads(l)["name"] == a.name), None)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps(row, ensure_ascii=False))
    if prev:
        worse = [k for k in WORSE if row.get(k) is not None and prev.get(k) is not None and row[k] > prev[k]]
        if prev.get("passed") and not row["passed"]:
            worse.append("passed")
        print("직전 대비 나빠진 칸: " + (", ".join(f"{k} {prev.get(k)}→{row.get(k)}" for k in worse) if worse else "없음"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
