"""
wiki_update.py — 원자 DB 최신 신호 → wiki/L5_섹터/ 자동 반영

기존 sector_*.md 파일에 '📡 원자 DB 최신 신호' 섹션을 추가/업데이트.
섹터 파일이 없으면 건너뜀 (자동 생성 금지 — ingest_rules §1 준수).

사용법:
    python -m pipeline.atoms.wiki_update                # 모든 섹터
    python -m pipeline.atoms.wiki_update --sector 반도체  # 단일 섹터
    python -m pipeline.atoms.wiki_update --days 14      # 최근 14일 원자 사용
    python -m pipeline.atoms.wiki_update --dry-run      # 파일 변경 없이 미리보기
"""
import sys
import argparse
from pathlib import Path
from datetime import date, timedelta
from textwrap import shorten

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from .db import get_conn, init_db

ROOT = Path(__file__).parent.parent.parent
WIKI_SECTOR = ROOT / "wiki" / "L5_섹터"

# atom DB 섹터명 → wiki 폴더명 매핑
SECTOR_MAP: dict[str, str] = {
    "반도체": "반도체",
    "AI소프트웨어": "AI소프트웨어",
    "AI Software": "AI소프트웨어",
    "바이오": "바이오",
    "자동차": "자동차",
    "automotive": "자동차",
    "조선": "조선",
    "shipping": "조선",
    "방산": "방산",
    "2차전지": "2차전지ESS",
    "전력": "전력",
    "전력기기": "전력기기",
    "로봇": "로봇",
    "소비내수": "소비내수",
    "철강": "철강",
    "화장품": "화장품",
    "에너지": "신재생",
    "금융": None,   # wiki 폴더 없음 → 건너뜀
    "기타": None,
    "macro": None,
    "market": None,
}

_SIGNAL_KO = {
    "bullish": "🔼 상승",
    "bearish": "🔽 하락",
    "neutral": "⚪ 중립",
    "risk": "⚠️ 리스크",
    "catalyst": "⚡ 촉매",
    "conflict": "⚡ 충돌",
    "data": "📊 데이터",
}
_TRUST_KO = {"A": "리포트", "B": "텔레/YT", "C": "블로그", "D": "뉴스"}

_SECTION_START = "<!-- ATOM_SIGNAL_START -->"
_SECTION_END = "<!-- ATOM_SIGNAL_END -->"


def get_sector_atoms(wiki_sector: str, days: int = 7, limit: int = 5) -> list[dict]:
    """wiki 섹터명으로 최신 원자 조회."""
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    # atom DB의 섹터명 역매핑
    db_sectors = [k for k, v in SECTOR_MAP.items() if v == wiki_sector]
    if not db_sectors:
        db_sectors = [wiki_sector]

    conn = get_conn()
    placeholders = ",".join("?" * len(db_sectors))
    rows = conn.execute(f"""
        SELECT date, sector, asset, signal, source_trust, source_name, content, strength_score
        FROM atoms
        WHERE is_active=1
          AND sector IN ({placeholders})
          AND source_trust IN ('A','B')
          AND date >= ?
          AND LENGTH(content) >= 40
        ORDER BY strength_score DESC, date DESC
        LIMIT ?
    """, (*db_sectors, cutoff, limit)).fetchall()
    conn.close()

    return [
        {
            "date": r[0], "sector": r[1], "asset": r[2],
            "signal": r[3], "trust": r[4], "source": r[5],
            "content": r[6], "score": r[7],
        }
        for r in rows
    ]


def build_section(wiki_sector: str, atoms: list[dict], today: str) -> str:
    """원자 목록 → 마크다운 섹션 문자열."""
    lines = [
        _SECTION_START,
        f"## 📡 원자 DB 최신 신호 ({today} 자동 갱신)",
        "",
    ]
    if not atoms:
        lines += ["> 최근 7일 A/B 등급 원자 없음.", ""]
    else:
        for a in atoms:
            sig = _SIGNAL_KO.get(a["signal"], a["signal"])
            trust = _TRUST_KO.get(a["trust"], a["trust"])
            asset = f"/{a['asset']}" if a["asset"] and a["asset"] != wiki_sector else ""
            summary = shorten(a["content"], width=120, placeholder="…")
            lines.append(f"- **[{a['date']}]** {sig} `{trust}`{asset}")
            lines.append(f"  > {summary}")
            lines.append("")
    lines += ["---", "", _SECTION_END]
    return "\n".join(lines)


def update_sector_file(sector_md: Path, section: str, dry_run: bool = False) -> bool:
    """sector_*.md 파일에 섹션 추가 또는 교체. 변경됐으면 True."""
    content = sector_md.read_text(encoding="utf-8")

    # 기존 섹션 교체
    if _SECTION_START in content and _SECTION_END in content:
        start = content.index(_SECTION_START)
        end = content.index(_SECTION_END) + len(_SECTION_END)
        new_content = content[:start] + section + content[end:]
    else:
        # 없으면 파일 맨 위에 삽입 (첫 줄 # 제목 다음)
        lines = content.split("\n")
        insert_at = 1  # 기본은 첫 줄 다음
        for i, line in enumerate(lines):
            if line.startswith("# "):
                insert_at = i + 1
                break
        lines.insert(insert_at, "\n" + section + "\n")
        new_content = "\n".join(lines)

    if new_content == content:
        return False

    if not dry_run:
        sector_md.write_text(new_content, encoding="utf-8")
    return True


def run(sector_filter: str = None, days: int = 7, dry_run: bool = False):
    init_db()
    today = date.today().isoformat()
    updated = 0
    skipped = 0

    # wiki 폴더에서 sector_*.md 파일 탐색
    for folder in sorted(WIKI_SECTOR.iterdir()):
        if not folder.is_dir():
            continue
        wiki_sector = folder.name
        if sector_filter and wiki_sector != sector_filter:
            continue

        sector_files = list(folder.glob("sector_*.md"))
        if not sector_files:
            skipped += 1
            continue

        atoms = get_sector_atoms(wiki_sector, days=days)
        section = build_section(wiki_sector, atoms, today)

        for sf in sector_files:
            changed = update_sector_file(sf, section, dry_run=dry_run)
            tag = "[DRY]" if dry_run else ""
            if changed:
                print(f"  {tag}갱신: {sf.relative_to(ROOT)} — 원자 {len(atoms)}개")
                updated += 1
            else:
                print(f"  변경없음: {sf.relative_to(ROOT)}")

    print(f"\n완료: 갱신 {updated}개 | sector 파일 없어 건너뜀 {skipped}개")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="원자 DB 최신 신호 → wiki 섹터 파일 자동 반영")
    parser.add_argument("--sector", default=None, help="단일 섹터 (wiki 폴더명)")
    parser.add_argument("--days", type=int, default=7, help="최근 N일 원자 사용 (기본 7)")
    parser.add_argument("--dry-run", action="store_true", help="파일 변경 없이 미리보기")
    args = parser.parse_args()
    run(sector_filter=args.sector, days=args.days, dry_run=args.dry_run)
