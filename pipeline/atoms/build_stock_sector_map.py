"""종목 → 섹터 맵 생성기.

소스 (우선순위 높은 순):
1. wiki/L5_섹터/{섹터}/stock/stock_*.md  — 큐레이션된 종목 분류 (최고신뢰)
2. atoms DB 자기학습 — 같은 종목이 비-기타 섹터로 일관 분류된 이력
3. KRX 업종·주요제품 키워드 매칭 — 광범위 보강 (최저신뢰)

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
# 사람이 검수해 손으로 고치는 파일 — 최우선, 자동 생성이 절대 안 덮어씀.
_OVERRIDE = Path(__file__).parent / "stock_sector_overrides.json"
_REVIEW = Path(__file__).parent / "stock_sector_review.md"

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


def from_krx() -> dict[str, str]:
    """KRX 업종·주요제품 키워드 매칭 (최저신뢰 보강). 네트워크 실패 시 빈 dict."""
    try:
        from .krx_industry import industry_sector_map
        return industry_sector_map()
    except Exception as e:
        print(f"  [WARN] KRX 업종 보강 생략: {e}")
        return {}


def from_override() -> dict[str, str]:
    """사람이 검수한 수동 교정 (최우선). {종목: 섹터} 또는 {종목: ""}(=제외)."""
    if _OVERRIDE.exists():
        return json.loads(_OVERRIDE.read_text(encoding="utf-8"))
    return {}


def build() -> dict[str, str]:
    """KRX(보강) → DB 자기학습 → wiki → 수동검수(override) 순으로 덮어씀."""
    m = from_krx()          # 최저 우선순위 먼저
    m.update(from_db())     # DB 자기학습이 덮어씀
    m.update(from_wiki())   # wiki가 그 위
    for name, sec in from_override().items():  # 사람 검수가 최종
        if sec:             # 섹터 지정 → 교정
            m[name] = sec
        else:               # 빈 문자열 → 맵에서 제외(기타로)
            m.pop(name, None)
    return dict(sorted(m.items()))


def write_review(m: dict[str, str]) -> None:
    """섹터별로 묶은 검수용 markdown 생성."""
    from collections import defaultdict
    by_sec: dict[str, list[str]] = defaultdict(list)
    for name, sec in m.items():
        by_sec[sec].append(name)
    lines = ["# 종목→섹터 맵 검수\n",
             "잘못된 게 보이면 `stock_sector_overrides.json`에 "
             "`\"종목명\": \"올바른섹터\"` 추가 (섹터 없애려면 빈 문자열 `\"\"`).\n",
             f"총 {len(m)}종목 / {len(by_sec)}섹터\n"]
    for sec in sorted(by_sec, key=lambda s: -len(by_sec[s])):
        names = sorted(by_sec[sec])
        lines.append(f"\n## {sec} ({len(names)})\n")
        lines.append(", ".join(names) + "\n")
    _REVIEW.write_text("".join(lines), encoding="utf-8")


def load_map() -> dict[str, str]:
    if _OUT.exists():
        return json.loads(_OUT.read_text(encoding="utf-8"))
    return {}


if __name__ == "__main__":
    m = build()
    _OUT.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    write_review(m)
    ov = len(from_override())
    print(f"종목→섹터 맵 생성: {len(m)}개 (수동교정 {ov}건 반영) → {_OUT.relative_to(_ROOT)}")
    print(f"검수파일: {_REVIEW.relative_to(_ROOT)}")
    from collections import Counter as _C
    dist = _C(m.values())
    for sec, n in dist.most_common():
        print(f"  {sec}: {n}개")
