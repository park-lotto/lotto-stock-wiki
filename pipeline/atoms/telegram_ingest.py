"""텔레그램 인제스트 오케스트레이터.

사용법:
    python -m pipeline.atoms.telegram_ingest --all [--date YYYY-MM-DD] [--limit N] [--dry-run]
    python -m pipeline.atoms.telegram_ingest raw/telegram/2026-06-19_하나반도체.md
"""
import re
import json
import argparse
from pathlib import Path

from .db import init_db, migrate_db, insert_atom
from .vector_db import embed_and_store
from .telegram_registry import channel_info, is_excluded
from .telegram_questionnaire import extract_telegram, questionnaire_to_atoms_tg
from .telegram_stance import deactivate_prior_stance

_ROOT = Path(__file__).parent.parent.parent
_TG_DIR = _ROOT / "raw" / "telegram"
_Q_ROOT = _ROOT / "raw" / "telegram_q"

_FNAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)$")


def _parse_filename(fname: str) -> tuple[str, str]:
    stem = Path(fname).stem
    m = _FNAME.match(stem)
    return (m.group(1), m.group(2)) if m else ("", stem)


def _is_image_file(fname: str) -> bool:
    return Path(fname).suffix.lower() in {".png", ".jpg", ".jpeg", ".gif"}


def _save_artifact(q: dict, date: str, channel: str) -> None:
    out = _Q_ROOT / date
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{channel}.json").write_text(
        json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


def ingest_telegram(md_path: Path) -> int:
    date, channel = _parse_filename(md_path.name)
    if _is_image_file(md_path.name) or is_excluded(channel) or "_digest" in md_path.name:
        return 0
    info = channel_info(channel)
    if not info:
        print(f"  [SKIP] 미등록 채널: {channel}")
        return 0

    q = extract_telegram(md_path, info["type"])
    if not q:
        print(f"  [WARN] 빈 질문지: {channel}")
        return 0

    _save_artifact(q, date, channel)
    meta = {"date": date, "channel": channel, "type": info["type"],
            "sector": info.get("sector"), "trust": info["trust"],
            "raw_file": str(md_path)}
    atoms = questionnaire_to_atoms_tg(q, meta)
    for a in atoms:
        if a.get("stance_key"):
            deactivate_prior_stance(a["stance_key"], keep_id=a["id"])
        insert_atom(a)
        try:
            embed_and_store(a)
        except Exception:
            pass
    return len(atoms)


def get_pending_telegram(date_filter: str = None) -> list[Path]:
    files = []
    for f in sorted(_TG_DIR.glob("*.md")):
        if "_digest" in f.name:
            continue
        date, channel = _parse_filename(f.name)
        if date_filter and date != date_filter:
            continue
        if is_excluded(channel) or not channel_info(channel):
            continue
        files.append(f)
    return sorted(files, reverse=True)


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
        targets = get_pending_telegram(args.date)[: args.limit]
        print(f"미처리 텔레그램: {len(targets)}개\n")
    else:
        print("file 또는 --all 필요")
        return

    if args.dry_run:
        for f in targets:
            d, c = _parse_filename(f.name)
            info = channel_info(c)
            print(f"  {f.name} → type={info['type'] if info else '?'}")
        return

    total = 0
    for i, f in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {f.name}")
        n = ingest_telegram(f)
        total += n
        print(f"  → {n}개 원자")
    print(f"\n완료: {len(targets)}개 채널, {total}개 원자")


if __name__ == "__main__":
    main()
