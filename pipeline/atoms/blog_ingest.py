"""블로그 인제스트 오케스트레이터 (telegram_ingest 패턴 차용).

사용법:
    python -m pipeline.atoms.blog_ingest --all [--date YYYY-MM-DD] [--limit N] [--dry-run]
    python -m pipeline.atoms.blog_ingest raw/blog/2026-06-21_0900_바이오.md
"""
import re
import sys
import json
import argparse
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .db import init_db, migrate_db, insert_atom, get_conn
from .vector_db import embed_and_store
from .blog_questionnaire import extract_blog, blog_trust
from .telegram_questionnaire import questionnaire_to_atoms_tg
from .telegram_stance import deactivate_prior_stance

_ROOT = Path(__file__).parent.parent.parent
_BLOG_DIR = _ROOT / "raw" / "blog"
_Q_ROOT = _ROOT / "raw" / "blog_q"

_FNAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d+_(.+)$")


def _parse_blog_header(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    title = md_path.stem
    blogger = re.search(r"\*\*출처\*\*[:\s]+(.+)", text)
    date = re.search(r"\*\*날짜\*\*[:\s]+(\d{4}-\d{2}-\d{2})", text)
    link = re.search(r"\*\*링크\*\*.*?(https?://[^\)\s]+)", text)
    b = blogger.group(1).strip() if blogger else title
    b = re.sub(r"\s*블로그$", "", b).strip()  # "pokara61 블로그" → "pokara61"
    d = date.group(1) if date else ""
    if not d:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", md_path.name)
        d = m.group(1) if m else ""
    return {"blogger": b, "date": d, "link": link.group(1) if link else "", "title": title}


def get_done_blog_files() -> set[str]:
    """이미 처리된 블로그 파일 basename 집합.

    raw_file이 상대/절대 경로 어느 형태로 저장됐든 파일명만으로 비교한다."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT raw_file FROM atoms WHERE source_type='blog'"
    ).fetchall()
    conn.close()
    return {Path(r[0]).name for r in rows if r[0]}


def get_pending_blog(date_filter: str = None) -> list[Path]:
    if not _BLOG_DIR.exists():
        return []
    done = get_done_blog_files()
    files = []
    for f in sorted(_BLOG_DIR.glob("*.md")):
        if "_analysis" in f.name:
            continue
        m = _FNAME.match(f.stem)
        if date_filter and (not m or m.group(1) != date_filter):
            continue
        if f.name in done:
            continue
        files.append(f)
    return sorted(files, reverse=True)


def _save_artifact(q: dict, date: str, title: str) -> None:
    out = _Q_ROOT / (date or "unknown")
    out.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w가-힣]+", "_", title)[:60]
    (out / f"{safe}.json").write_text(
        json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


def ingest_blog(md_path: Path) -> int:
    h = _parse_blog_header(md_path)
    q = extract_blog(md_path)
    if not q or not q.get("target_kind"):
        print(f"  [WARN] 빈/미라우팅 질문지: {md_path.name}")
        return 0
    _save_artifact(q, h["date"], h["title"])
    meta = {
        "date": h["date"], "channel": h["blogger"], "type": q["target_kind"],
        "source_type": "blog", "trust": blog_trust(h["blogger"]),
        "raw_file": str(md_path),
    }
    atoms = questionnaire_to_atoms_tg(q, meta)
    for a in atoms:
        if a.get("stance_key"):
            deactivate_prior_stance(a["stance_key"], keep_id=a["id"])
        insert_atom(a)
        try:
            embed_and_store(a)
        except Exception as e:
            print(f"  [WARN] embed 실패: {e}")
    return len(atoms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--date", default=None)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    init_db(); migrate_db()

    if args.file:
        targets = [Path(args.file)]
    elif args.all:
        targets = get_pending_blog(args.date)[: args.limit]
        print(f"미처리 블로그: {len(targets)}개\n")
    else:
        print("file 또는 --all 필요")
        return

    if args.dry_run:
        for f in targets:
            print(f"  {f.name} → {_parse_blog_header(f)['blogger']}")
        return

    total = 0
    for i, f in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {f.name}")
        n = ingest_blog(f)
        total += n
        print(f"  → {n}개 원자")
    print(f"\n완료: {len(targets)}개 포스트, {total}개 원자")


if __name__ == "__main__":
    main()
