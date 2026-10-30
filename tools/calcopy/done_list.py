"""이미 만든 편 목록 — 소재 고르기의 '중복 건너뛰기' 판단 주인(관제 263, 사장님 10-25 "안 한 것 중에 골라야").

10-25 사고: 키치잇 소재가 박세리 선크림을 골랐다 — 이미 만든 편인데 결과물.json·channel/yanshottem 만 봐서 놓쳤다
(실제 작업 폴더 = C:/숏템_칼카피/yanshottem/하이브리드_박세리_선크림). 그래서 네 곳 합집합을 한 함수로 본다:
  ⓪ 작업 기록지 channel/작업기록.jsonl(+이 PC 회원 기록지 ~/.shortem/작업기록.jsonl) — 주인 tools/calcopy/work_log.py
     status=stopped(멈춘 편)는 '이미 만듦'으로 치지 않고 "멈춘 편(이유)"로만 보여 준다
  ① 작업 폴더 C:/숏템_칼카피/<채널들>/ 의 편 폴더 이름  ② 드라이브 G:/내 드라이브/칼카피영상/ 아래 파일·폴더 이름  ③ channel/결과물.json
  ④ channel/<채널>/<편>/대본.json 의 소재(bench id·제목) + 편 폴더 이름 — 10-29 사고: 샥템 회원 시험 소재 QMJtjJz4M6w(모래주머니)가
     이미 만든 1편_STORMBAG(대본.json bench.id 같음)인데 '안 만든 편'으로 나왔다(①이 고정 9채널뿐이라 foreignshowshow 작업 폴더도 안 봤다)

  PYTHONUTF8=1 py tools/calcopy/done_list.py 박세리 선크림        # 이미 만든 편이면 rc=1 + 걸린 곳
  PYTHONUTF8=1 py tools/calcopy/done_list.py --list              # 전부
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy import work_log as WL  # noqa: E402
WORK = Path("C:/숏템_칼카피")
DRIVE = Path("G:/내 드라이브/칼카피영상")
WORK_CHANNELS = ("yanshottem", "kitchit", "kkultemnote", "starpickroom", "mantem", "itemhome", "annapick", "goodletter", "uljimatrot")


def _norm(s: str) -> str:
    return re.sub(r"[\s_\-·.]+", "", str(s)).lower()


def entries() -> list[tuple[str, str]]:
    """(이름, 출처) 전부 — 멈춘 편(stopped)은 빼고(stopped() 가 따로 준다)."""
    out = []
    for r in WL.list_(member=True):
        if r.get("status") != "stopped":
            out.append((_rec_name(r), f"기록지 {r.get('status')} {str(r.get('date') or '')[:10]}"))
    chans = set(WORK_CHANNELS) | ({p.name for p in (ROOT / "channel").iterdir() if p.is_dir()} if (ROOT / "channel").is_dir() else set())
    for ch in sorted(chans):
        d = WORK / ch
        if d.is_dir():
            out += [(p.name, f"작업폴더 {ch}") for p in d.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))]
    if DRIVE.is_dir():
        out += [(p.relative_to(DRIVE).as_posix(), "드라이브") for p in DRIVE.rglob("*") if not p.name.startswith(".")]
    for sc in sorted((ROOT / "channel").glob("*/*/대본.json")):
        ep = f"{sc.parent.parent.name}/{sc.parent.name}"
        out.append((ep, "채널 편 폴더"))
        try:
            d = json.loads(sc.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        b = d.get("bench") if isinstance(d, dict) else None
        b = b if isinstance(b, dict) else {"id": b} if isinstance(b, str) else {}   # 옛 편은 bench 가 주소·id 글자 하나
        for k in ("id", "title", "url"):
            if isinstance(b.get(k), str) and b[k]:
                out.append((b[k], f"대본.json 소재 {ep}"))
    f = ROOT / "channel" / "결과물.json"
    if f.is_file():
        def walk(x):
            if isinstance(x, dict):
                for k in ("title", "name", "인물", "제품", "id", "file", "drive"):
                    if isinstance(x.get(k), str):
                        out.append((x[k], "결과물.json"))
                for v in x.values():
                    walk(v)
            elif isinstance(x, list):
                for v in x:
                    walk(v)
        walk(json.loads(f.read_text(encoding="utf-8")))
    return out


def _rec_name(r: dict) -> str:
    return " · ".join(str(r[k]) for k in ("our_channel", "person", "product", "drive_path", "final_path", "note") if r.get(k))


def stopped(*words: str) -> list[tuple[str, str]]:
    """멈춘 편 — (이름, 이유). 이미 만든 편이 아니다."""
    ws = [_norm(w) for w in words if w]
    rows = [r for r in WL.list_(member=True) if r.get("status") == "stopped"]
    return [(_rec_name(r), str(r.get("note") or "")) for r in rows if all(w in _norm(_rec_name(r)) for w in ws)]


def made(*words: str) -> list[tuple[str, str]]:
    """모든 낱말이 이름에 들어 있는 항목(인물만 주면 인물 전체 편)."""
    ws = [_norm(w) for w in words if w]
    return [(n, s) for n, s in entries() if all(w in _norm(n) for w in ws)]


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not argv or argv == ["--list"]:
        for n, s in entries():
            print(f"{s}\t{n}")
        for n, why in stopped():
            print(f"멈춘 편\t{n}\t({why})")
        return 0
    hits = made(*argv)
    for n, s in hits:
        print(f"이미 만듦 — {s}: {n}")
    for n, why in stopped(*argv):
        print(f"멈춘 편({why}) — {n}")
    if not hits:
        print("안 만든 편")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
