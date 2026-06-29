"""
유튜브 크롤 md → 원자 DB 파이프라인 (B단계)

사용법:
  python -m pipeline.atoms.youtube_ingest                 # 오늘 날짜
  python -m pipeline.atoms.youtube_ingest --date 2026-06-28
  python -m pipeline.atoms.youtube_ingest --file path/to/video.md
"""
import re
import sys
import argparse
from pathlib import Path
from datetime import date as _date

from pipeline.atoms.atomizer import atomize_youtube_highlights
from pipeline.atoms.db import insert_atom, migrate_db

CRAWL_ROOT = Path(r"C:\Users\TheRose\crawling_bot_data")

_TS_PAT = re.compile(r"^\[(\d{1,2}:\d{2}(?::\d{2})?)\]")
_LINK_PAT = re.compile(r"\[유튜브 바로가기\]\((https?://[^\)]+)\)")
_YT_URL_PAT = re.compile(r"https?://(?:www\.)?youtube\.com/watch\?v=[\w\-]+|https?://youtu\.be/[\w\-]+")
_CHANNEL_PAT = re.compile(r"\*\*채널\*\*:\s*(.+)")


def _parse_md(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")

    # URL: [유튜브 바로가기](URL) 우선, 없으면 헤더 어디서든 YouTube URL 추출
    link_m = _LINK_PAT.search(text)
    if link_m:
        url = link_m.group(1).strip()
    else:
        yt_m = _YT_URL_PAT.search(text)
        if not yt_m:
            return None
        url = yt_m.group(0).strip()

    # 채널명: **채널** 값이 URL/날짜면 파일명 stem 사용
    ch_m = _CHANNEL_PAT.search(text)
    raw_ch = ch_m.group(1).strip() if ch_m else ""
    if raw_ch and not _YT_URL_PAT.match(raw_ch) and not re.match(r"\d{4}-\d{2}-\d{2}", raw_ch):
        channel = raw_ch
    else:
        channel = path.stem.split("_")[-1]  # 파일명 마지막 세그먼트

    highlights = []
    in_section = False
    for line in text.splitlines():
        if "## 주요 발언" in line:
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            stripped = line.strip().lstrip("- ").strip()
            if _TS_PAT.match(stripped):
                highlights.append(stripped)

    return {"url": url, "channel": channel, "highlights": highlights, "path": path}


def ingest_file(md_path: Path, date_str: str) -> int:
    info = _parse_md(md_path)
    if not info or not info["highlights"]:
        print(f"  skip (발언 없음): {md_path.name}")
        return 0

    print(f"  처리: {md_path.name} | 발언 {len(info['highlights'])}개")
    atoms = atomize_youtube_highlights(
        highlights=info["highlights"],
        video_url=info["url"],
        source_name=info["channel"],
        source_trust="B",
        raw_file=str(md_path),
        date=date_str,
    )

    for atom in atoms:
        insert_atom(atom)

    print(f"  저장: {len(atoms)}개 원자 → atoms.db")
    return len(atoms)


def ingest_date(date_str: str) -> int:
    yt_dir = CRAWL_ROOT / date_str / "youtube"
    if not yt_dir.exists():
        print(f"폴더 없음: {yt_dir}")
        return 0

    migrate_db()
    total = 0
    for md in sorted(yt_dir.glob("*.md")):
        total += ingest_file(md, date_str)
    print(f"\n완료: {total}개 원자 저장")
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=str(_date.today()))
    parser.add_argument("--file", default=None)
    args = parser.parse_args()

    if args.file:
        p = Path(args.file)
        migrate_db()
        ingest_file(p, args.date)
    else:
        ingest_date(args.date)


if __name__ == "__main__":
    main()
