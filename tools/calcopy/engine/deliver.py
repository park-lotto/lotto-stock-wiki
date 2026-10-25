# -*- coding: utf-8 -*-
"""납품 자물쇠 — 완성본을 구글 드라이브에 올리는 **유일한** 길(2026-10-25).

    PYTHONUTF8=1 py -m tools.calcopy.engine.deliver <final.mp4> <드라이브 폴더> <NN_english_name.mp4> [--doc <대본 폴더>] [--check]

받는 조건(하나라도 아니면 올리지 않는다):
  ① 봉인(engine/finalize.seal) 그대로 — 봉인 없음·봉인 뒤 바뀜·봉인 때 기본 검사(광고 표시·크기·소리·길이) 실패면 거절
  ② 대본이 렌더 뒤 바뀌지 않았다 — 봉인의 대본 md5 = 지금 대본.json md5
  ③ 관문 렌더 길(GATED: render_bench·preset_make·이름 없는 master_guard 봉인)이면 <doc>/품질관문/<봉인 md5>.json 이 ok — 그 판을 잰 결과여야 한다(마지막 결과 덮어쓰기 금지)
  ④ 파일 이름 = NN_영어 소문자·숫자·밑줄.mp4(칼카피_시작 §0-2) · 드라이브 칼카피영상 아래 이미 있는 폴더 · 같은 이름 없음(새 판은 옛 파일을 _이전판으로 옮긴 뒤)
올리기 = PowerShell Copy-Item(드라이브 G: 는 Bash cp 금지 — 폴더를 파일로 덮은 사고) → 올린 파일 md5 대조 → <doc>/납품.json 에 쌓기.
왜: 10-25 전 편 감사 — 광고 없음 7편·검사 × 판 납품(잇템로그 04)·대본 판 불일치가 전부 '아무 파일이나 손으로 올릴 수 있어서' 나갔다.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tools.calcopy.engine import finalize as FZ  # noqa: E402

DRIVE_ROOT = Path("G:/내 드라이브/칼카피영상")
NAME_RE = re.compile(r"^\d{2}_[a-z0-9]+(?:_[a-z0-9]+)*\.mp4$")      # 칼카피_시작 §0-2: NN_영어소문자(_MMDD_HHMM·_confirm·_hybrid) — 한글 금지
GATED = {"render_bench", "preset_make", "master_guard"}      # 관문 기록(<doc>/품질관문/<md5>.json)이 있어야 나가는 렌더 길 —
# render_bench = quality_gate · preset_make = preset_gates.record(10-25: 렌더 전 관문 0건인 채 남의 글자·멈춤 편이 나갔다) ·
# master_guard = 렌더러 이름 없이 encode_final 로 봉인된 판(10-25 전 preset_make 판·render_spr) — 기록이 없으니 다시 렌더해야 나간다


def check(final, dest_dir, name: str, doc=None, drive_root: Path = DRIVE_ROOT) -> tuple[bool, list[str], dict | None]:
    """올려도 되나 — (ok, 거절 이유들, 봉인). 파일은 건드리지 않는다."""
    why = []
    ok, msg, rec = FZ.verify(final)
    if not ok:
        why.append(msg)
    if not NAME_RE.match(name):
        why.append(f"이름 규칙 밖: {name} — NN_영어 소문자·숫자·밑줄.mp4(한글·대문자·빈칸 금지)")
    dest_dir = Path(dest_dir)
    try:
        dest_dir.resolve().relative_to(Path(drive_root).resolve())
    except ValueError:
        why.append(f"드라이브 칼카피영상 폴더 밖: {dest_dir}")
    if not dest_dir.is_dir():
        why.append(f"없는 폴더: {dest_dir} (새 폴더는 만들지 않는다)")
    elif (dest_dir / name).exists():
        why.append(f"같은 이름이 이미 있다: {dest_dir / name} — 덮지 않는다(옛 판은 _이전판으로 먼저 옮긴다)")
    if rec:
        sc = rec.get("script")
        if sc and Path(sc).exists() and rec.get("script_md5") and FZ.md5(sc) != rec["script_md5"]:
            why.append(f"렌더 뒤 대본이 바뀌었다({Path(sc).name}) — 지금 대본으로 다시 렌더")
        if rec.get("renderer") in GATED:
            if not doc:
                why.append("품질 관문 기록을 볼 --doc 가 없다")
            else:
                gp = Path(doc) / "품질관문" / f"{rec['md5']}.json"
                if not gp.exists():
                    why.append(f"이 판을 잰 품질 관문 기록이 없다({gp.name}) — render_bench 판은 봉인된 이 파일로 quality_gate 를, preset_make 판은 preset_make 로 다시 만들어(관문 기록이 같이 남는다) 올린다")
                else:
                    g = json.loads(gp.read_text(encoding="utf-8"))
                    if not g.get("ok"):
                        bad = [f"{r['what']}({r['value']})" for r in g.get("rows", []) if r.get("ok") is False and not r.get("ref")]
                        why.append("품질 관문 ×: " + ", ".join(bad[:6]))
    return not why, why, rec


def to_drive(final, dest_dir, name: str, doc=None, log=print, drive_root: Path = DRIVE_ROOT) -> dict:
    """(판단 주인) 조건을 다 채운 완성본만 드라이브에 올린다. 반환 = {ok, why, dest, md5}."""
    final, dest_dir = Path(final), Path(dest_dir)
    ok, why, rec = check(final, dest_dir, name, doc, drive_root)
    if not ok:
        for w in why:
            log(f"[납품 거절] {w}")
        return {"ok": False, "why": why}
    dst = dest_dir / name
    r = subprocess.run(["powershell", "-NoProfile", "-Command", "Copy-Item -LiteralPath $env:SRC -Destination $env:DST"],
                       env={**__import__("os").environ, "SRC": str(final), "DST": str(dst)}, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
    if r.returncode or not dst.exists():
        log(f"[납품 실패] 복사 실패: {(r.stderr or '')[-300:]}")
        return {"ok": False, "why": ["복사 실패"]}
    got = FZ.md5(dst)
    if got != rec["md5"]:
        log(f"[납품 실패] 올린 파일 md5 다름({got[:8]} ≠ {rec['md5'][:8]}) — 드라이브 파일을 확인할 것")
        return {"ok": False, "why": ["올린 파일 md5 다름"], "dest": str(dst)}
    row = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "dest": str(dst), "md5": got, "final": str(final), "renderer": rec.get("renderer"),
           "gate": str(Path(doc) / "품질관문" / f"{got}.json") if doc and rec.get("renderer") in GATED else None}
    book = (Path(doc) if doc else final.parent) / "납품.json"
    rows = json.loads(book.read_text(encoding="utf-8")) if book.exists() else []
    book.write_text(json.dumps(rows + [row], ensure_ascii=False, indent=1), encoding="utf-8")
    log(f"[납품] {dst} · md5 {got[:8]} 일치 · 기록 {book}")
    __import__("tools.calcopy.work_log", fromlist=["x"]).from_delivery(final, dst, rec, doc, drive_root, log)   # 작업 기록지 1줄(관제 263/265) — 주인 work_log, 실패해도 납품은 그대로
    return {"ok": True, "why": [], "dest": str(dst), "md5": got}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("final"); ap.add_argument("dest_dir"); ap.add_argument("name"); ap.add_argument("--doc")
    ap.add_argument("--check", action="store_true", help="올리지 않고 조건만 본다")
    a = ap.parse_args()
    if a.check:
        ok, why, _ = check(a.final, a.dest_dir, a.name, a.doc)
        print("○ 올려도 된다" if ok else "× " + "\n× ".join(why))
        sys.exit(0 if ok else 1)
    sys.exit(0 if to_drive(a.final, a.dest_dir, a.name, a.doc)["ok"] else 1)
