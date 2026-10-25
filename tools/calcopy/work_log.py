# -*- coding: utf-8 -*-
"""작업 기록지 — 만든 편 한 줄씩(관제 263/265, 사장님 10-25 "작업된 건 못 볼 수 있으니 기록지를 따로. 회원은 어디에 저장할지 모르니. 날짜·채널 등등").

판단 주인: 이 파일 한 곳이 기록지의 꼴(칸)·쓰기·찾기를 정한다.
  · 엔진(사장님 PC) 기록지 = channel/작업기록.jsonl  — engine/deliver.to_drive 가 납품 성공 직후 from_delivery() 로 1줄
  · 회원 PC 기록지       = ~/.shortem/작업기록.jsonl — 숏템 회원 실행기(shortem_client/server/work_log.js)가 같은 꼴로 1줄
  · 이미 만든 편 검사(done_list.py)는 둘 다 읽는다(list(member=True)).

한 줄 = 한 편:
  date(KST ISO) · bench_channel · our_channel · style(판) · person · product · bench_url · origin_url ·
  final_path · final_md5 · drive_path · duration · made_by(owner|member:<id>) · status(delivered|stopped|made) · note
  status: delivered = 드라이브 납품됨 / stopped = 멈춘 편(note 에 이유 — '이미 만듦'으로 치지 않는다) /
          made = 완성본은 있으나 납품 기록이 없다(소급에서만 쓴다)
모르는 칸은 null — 추측으로 채우지 않는다.

  PYTHONUTF8=1 py tools/calcopy/work_log.py list
  PYTHONUTF8=1 py tools/calcopy/work_log.py find 박세리 선크림
  PYTHONUTF8=1 py tools/calcopy/work_log.py add --status stopped --person 박세리 --product 선크림 --our-channel kitchit --note "원본 못 찾음"
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG = ROOT / "channel" / "작업기록.jsonl"
KST = timezone(timedelta(hours=9))
FIELDS = ("date", "bench_channel", "our_channel", "style", "person", "product", "bench_url", "origin_url",
          "final_path", "final_md5", "drive_path", "duration", "made_by", "status", "note")
STATUS = ("delivered", "stopped", "made")
INFO_FILE = "작업정보.json"     # 편 doc 폴더에 두면 from_delivery 가 칸을 채운다(bench_channel·person·product·style·bench_url·origin_url·our_channel)


def member_log() -> Path:
    """회원 PC 기록지 — 숏템 실행기와 같은 자리(SHORTEM_HOME 이 있으면 그 아래)."""
    home = os.environ.get("SHORTEM_HOME") or str(Path.home() / ".shortem")
    return Path(home) / "작업기록.jsonl"


def now_kst() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def _norm(s) -> str:
    return re.sub(r"[\s_\-·./\\]+", "", str(s or "")).lower()


def _clean(rec: dict) -> dict:
    bad = set(rec) - set(FIELDS)
    if bad:
        raise ValueError(f"모르는 칸: {sorted(bad)} — 칸은 {FIELDS}")
    out = {k: rec.get(k) for k in FIELDS}
    out["date"] = out["date"] or now_kst()
    out["made_by"] = out["made_by"] or "owner"
    out["status"] = out["status"] or "delivered"
    if out["status"] not in STATUS:
        raise ValueError(f"status 는 {STATUS} 중 하나: {out['status']}")
    if not (out["made_by"] == "owner" or str(out["made_by"]).startswith("member:")):
        raise ValueError(f"made_by 는 owner 또는 member:<id>: {out['made_by']}")
    if out["status"] == "stopped" and not out["note"]:
        raise ValueError("멈춘 편(stopped)은 note 에 이유를 적어야 한다")
    if out["duration"] is not None:
        out["duration"] = round(float(out["duration"]), 3)
    return out


def read(path: Path) -> list[dict]:
    path = Path(path)
    if not path.is_file():
        return []
    rows = []
    for i, ln in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not ln.strip():
            continue
        try:
            rows.append(json.loads(ln))
        except json.JSONDecodeError:
            print(f"[작업기록] 깨진 줄 건너뜀 {path.name}:{i}", file=sys.stderr)
    return rows


def append(rec: dict, path: Path | None = None) -> dict:
    """(판단 주인) 한 편 한 줄 쓰기. 같은 final_md5+drive_path(+status) 줄이 이미 있으면 다시 쓰지 않고 그 줄을 돌려준다."""
    from tools.calcopy.engine.filelock import locked
    path = Path(path or LOG)
    row = _clean(rec)
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked(path):
        if row["final_md5"]:
            for r in read(path):
                if r.get("final_md5") == row["final_md5"] and r.get("drive_path") == row["drive_path"] and r.get("status") == row["status"]:
                    return r
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def list_(path: Path | None = None, member: bool = False) -> list[dict]:
    """기록지 전부. member=True 면 이 PC 의 회원 기록지(~/.shortem/작업기록.jsonl)도 붙인다."""
    rows = read(path or LOG)
    if member:
        mp = member_log()
        if mp.resolve() != Path(path or LOG).resolve():
            rows += read(mp)
    return rows


def _text(r: dict) -> str:
    return _norm(" ".join(str(r.get(k) or "") for k in ("person", "product", "note", "final_path", "drive_path", "our_channel", "bench_url", "origin_url")))


def find(person: str | None = None, product: str | None = None, *more: str, path: Path | None = None, member: bool = True) -> list[dict]:
    """낱말(인물·제품…)이 전부 들어 있는 줄 — 인물·제품 칸뿐 아니라 파일 경로·note 도 본다(소급 줄은 이름이 경로에만 있다)."""
    ws = [_norm(w) for w in (person, product, *more) if w]
    if not ws:
        return []
    return [r for r in list_(path, member) if all(w in _text(r) for w in ws)]


def _dur_from_seal(rec: dict | None):
    for c in (rec or {}).get("checks") or []:
        m = re.search(r"영상\s+([\d.]+)", str(c.get("value") or "")) if c.get("what") == "영상=소리 길이" else None
        if m:
            return float(m.group(1))
    return None


def from_delivery(final, dst, seal: dict | None, doc=None, drive_root=None, log=print, path: Path | None = None) -> dict | None:
    """engine/deliver.to_drive 가 납품(복사·md5 대조) 성공 직후 부른다. 납품을 막지 않는다 — 실패는 [작업기록 실패]로 알린다."""
    try:
        dst = Path(dst)
        info = {}
        if doc and (Path(doc) / INFO_FILE).is_file():
            info = json.loads((Path(doc) / INFO_FILE).read_text(encoding="utf-8"))
        our = None
        if drive_root:
            try:
                our = dst.resolve().relative_to(Path(drive_root).resolve()).parts[0]
            except (ValueError, IndexError):
                our = None
        keep = ("bench_channel", "our_channel", "style", "person", "product", "bench_url", "origin_url", "note")
        rec = {"our_channel": our, **{k: info[k] for k in keep if info.get(k) is not None},
               "final_path": str(final), "final_md5": (seal or {}).get("md5"), "drive_path": str(dst),
               "duration": _dur_from_seal(seal), "made_by": "owner", "status": "delivered"}
        if not rec.get("note"):
            rec["note"] = f"doc={Path(doc).name}" if doc else None
        row = append(rec, path)
        log(f"[작업기록] {(path or LOG).name} · {dst.name}")
        return row
    except Exception as e:  # noqa: BLE001 — 기록이 깨져도 납품은 끝났다. 조용히 넘기지 않고 알린다
        log(f"[작업기록 실패] {type(e).__name__}: {e} — py tools/calcopy/work_log.py add 로 손으로 남길 것")
        return None


def main(argv: list[str]) -> int:
    import argparse
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="work_log.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    fp = sub.add_parser("find"); fp.add_argument("words", nargs="+")
    a = sub.add_parser("add")
    for k in FIELDS:
        a.add_argument("--" + k.replace("_", "-"), dest=k)
    a.add_argument("--log", help="기록지 파일(기본 channel/작업기록.jsonl)")
    ns = ap.parse_args(argv)
    if ns.cmd == "list":
        for r in list_(member=True):
            print(json.dumps(r, ensure_ascii=False))
        return 0
    if ns.cmd == "find":
        hits = find(*ns.words)
        for r in hits:
            print(json.dumps(r, ensure_ascii=False))
        return 1 if hits else 0
    rec = {k: getattr(ns, k) for k in FIELDS if getattr(ns, k) is not None}
    try:
        row = append(rec, Path(ns.log) if ns.log else None)
    except ValueError as e:
        print(f"× 기록 안 함: {e}")
        return 2
    print(json.dumps(row, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main(sys.argv[1:]))
