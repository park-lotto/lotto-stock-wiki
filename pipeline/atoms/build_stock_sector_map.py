"""종목 → 섹터 맵 생성기.

소스:
1. wiki/L5_섹터/{섹터}/stock/stock_*.md  — 큐레이션된 종목 분류 (고신뢰)
2. atoms DB 자기학습 — 같은 종목이 비-기타 섹터로 일관 분류된 이력

폴더명이 택소노미(sectors.json)와 다른 경우 _FOLDER_ALIAS로 정렬.
택소노미에 매핑 안 되는 폴더(LNG·우주·테마이벤트)는 제외.

실행: python -m pipeline.atoms.build_stock_sector_map
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

from .db import get_conn
from .sector_classify import sectors_list

_ROOT = Path(__file__).parent.parent.parent
_WIKI_SECTOR = _ROOT / "wiki" / "L5_섹터"
_OUT = Path(__file__).parent / "stock_sector_map.json"

# wiki 폴더명 → 택소노미 섹터 (불일치 정렬)
_FOLDER_ALIAS = {
    "이차전지": "2차전지",
    "전력기기": "전력",
    "화장품": "화장품미용",
    "미용": "화장품미용",
    "AI소프트웨어": "IT",
    "엔터": "소비내수",
}
# 택소노미에 없어 제외할 폴더
_SKIP_FOLDERS = {"LNG", "우주", "테마이벤트"}


def _folder_to_sector(folder: str) -> str | None:
    if folder in _SKIP_FOLDERS:
        return None
    sec = _FOLDER_ALIAS.get(folder, folder)
    return sec if sec in sectors_list() else None


def from_wiki() -> dict[str, str]:
    """wiki stock 폴더 → {종목명: 섹터}."""
    out: dict[str, str] = {}
    if not _WIKI_SECTOR.exists():
        return out
    for folder in _WIKI_SECTOR.iterdir():
        sd = folder / "stock"
        if not sd.is_dir():
            continue
        sec = _folder_to_sector(folder.name)
        if not sec:
            continue
        for f in sd.glob("stock_*.md"):
            name = f.stem.replace("stock_", "").strip()
            if name:
                out.setdefault(name, sec)  # 첫 등장 우선
    return out


def from_db(min_count: int = 2, dominance: float = 0.8) -> dict[str, str]:
    """DB에서 비-기타로 일관 분류된 종목만 학습.

    min_count: 최소 등장 횟수, dominance: 최빈 섹터 점유율 임계."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT asset, sector FROM atoms WHERE is_active=1 AND asset!='' AND asset IS NOT NULL"
    ).fetchall()
    conn.close()
    counts: dict[str, Counter] = defaultdict(Counter)
    for asset, sector in rows:
        if sector and sector != "기타":
            counts[asset.strip()][sector] += 1
    out: dict[str, str] = {}
    for asset, c in counts.items():
        total = sum(c.values())
        sec, n = c.most_common(1)[0]
        if total >= min_count and n / total >= dominance:
            out[asset] = sec
    return out


def build() -> dict[str, str]:
    """wiki(우선) + DB 자기학습 병합."""
    m = from_db()
    m.update(from_wiki())  # wiki가 충돌 시 우선
    return dict(sorted(m.items()))


def load_map() -> dict[str, str]:
    if _OUT.exists():
        return json.loads(_OUT.read_text(encoding="utf-8"))
    return {}


if __name__ == "__main__":
    m = build()
    _OUT.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"종목→섹터 맵 생성: {len(m)}개 → {_OUT.relative_to(_ROOT)}")
    from collections import Counter as _C
    dist = _C(m.values())
    for sec, n in dist.most_common():
        print(f"  {sec}: {n}개")
