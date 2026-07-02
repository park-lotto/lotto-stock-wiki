"""sortino_data.py — 소라티노(ETF 상대강도) 오늘의 주도섹터 Top.

etf상대강도데이터.xlsx를 scan_sortino의 검증된 로직으로 랭킹 → 오늘 강한
ETF/섹터/종목 Top N. funnel의 '주도섹터(소라티노)' 축에 쓴다.
파일 없으면 available=False (funnel graceful 처리).
"""
import sys
import glob
from pathlib import Path

_ROOT = Path(__file__).parent.parent.parent
_EXCEL_DIR = _ROOT / "raw" / "매일 엑셀넣을것"
_CACHE = {}  # (mtime) -> result


def _find_file():
    for pat in ("etf상대강도데이터.xlsx", "소라티노ETF상대강도"):
        hits = sorted(glob.glob(str(_EXCEL_DIR / f"*{pat.split('.')[0]}*")))
        if hits:
            return hits[-1]
    return None


# ETF 접두/접미어 제거 → 섹터 키워드
_STRIP = ["KODEX", "TIGER", "SOL", "RISE", "PLUS", "ACE", "KBSTAR", "HANARO",
          "액티브", "ETF", "TOP3플러스", "&ESS", "인프라"]


def _sector_kw(name: str) -> str:
    s = name
    for t in _STRIP:
        s = s.replace(t, "")
    return s.strip()


def load_sortino_top(n: int = 12):
    """{available, date, names[Top N], sectors[섹터 키워드 set]}."""
    path = _find_file()
    if not path or not Path(path).exists():
        return {"available": False, "date": None, "names": [], "sectors": []}
    mtime = Path(path).stat().st_mtime
    if _CACHE.get("key") == (path, mtime, n):
        return _CACHE["val"]

    sys.path.insert(0, str(_ROOT / "scripts"))
    import scan_sortino as ss
    df = ss.load_etf_data()
    ranked = ss.rank_sortino(df, top_n=n)
    # 최신일 행의 Top1..N (None 제외)
    last = ranked.iloc[-1]
    names = [str(v).strip() for v in last.tolist() if v and str(v) != "None"]
    date = str(ranked.index[-1].date())
    sectors = sorted({_sector_kw(nm) for nm in names if _sector_kw(nm)})
    out = {"available": True, "date": date, "names": names, "sectors": sectors}
    _CACHE["key"] = (path, mtime, n)
    _CACHE["val"] = out
    return out


if __name__ == "__main__":
    import io
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    r = load_sortino_top()
    print(f"소라티노 Top ({r['date']}): available={r['available']}")
    print("  Top:", " · ".join(r["names"]))
    print("  섹터:", " · ".join(r["sectors"]))
