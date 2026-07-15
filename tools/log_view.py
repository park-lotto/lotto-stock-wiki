"""wiki/log.d/<트랙>.md 조각을 합쳐 최신순으로 보여준다 (읽기 전용).

어떤 파일도 쓰지 않는다. 파일을 쓰면 동시 세션이 서로 덮어쓴다
— 그게 이 도구가 존재하는 이유다.

사용: py tools/log_view.py [--days 7]
"""
import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOG_DIR = BASE / "wiki" / "log.d"

_ENTRY_RE = re.compile(r"^-\s*(\d{4}-\d{2}-\d{2})\s")


def parse_entries(text, track):
    entries = []
    for line in text.splitlines():
        m = _ENTRY_RE.match(line.strip())
        if not m:
            continue
        entries.append({"date": m.group(1), "track": track, "line": line.rstrip()})
    return entries


def collect(log_dir):
    entries = []
    for f in sorted(Path(log_dir).glob("*.md")):
        if f.stem == "README":
            continue
        entries.extend(parse_entries(f.read_text(encoding="utf-8"), f.stem))
    return entries


def render(entries):
    rows = sorted(entries, key=lambda e: e["date"], reverse=True)
    out = []
    for e in rows:
        body = e["line"].lstrip("- ").strip()
        out.append(f"- [{e['track']}] {body}")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=0,
                        help="최근 N일만 (0=전체)")
    args = parser.parse_args(argv)
    entries = collect(LOG_DIR)
    if args.days > 0:
        cutoff = (date.today() - timedelta(days=args.days - 1)).isoformat()
        entries = [e for e in entries if e["date"] >= cutoff]
    print(render(entries))


if __name__ == "__main__":
    main(sys.argv[1:])
