"""종목명 → 코드 맵.

소스 1 (우선): pipeline/atoms/krx_codes.json — KRX 전종목 (~2600종목, HTTP)
소스 2 (보완): raw/wisereport/*_parsed.json — 리포트에 나온 종목명 기준

krx_codes.json 없거나 7일 이상 경과 시 KRX에서 자동 갱신.
수동 갱신: python -m pipeline.atoms.codemap --refresh
조회:      python -m pipeline.atoms.codemap LIG디펜스앤에어로스페이스
"""
import io
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests

_WISE = Path(__file__).parent.parent.parent / "raw" / "wisereport"
_KRX_CACHE_FILE = Path(__file__).parent / "krx_codes.json"
_CACHE: dict[str, str] = {}
_REFRESH_DAYS = 7

_KRX_MARKETS = {
    "KOSPI": "stockMkt",
    "KOSDAQ": "kosdaqMkt",
}
_KRX_BASE = (
    "http://kind.krx.co.kr/corpgeneral/corpList.do"
    "?method=download&searchType=13&marketType={market}"
)
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "http://kind.krx.co.kr/"}


def _fetch_krx_market(market_key: str) -> dict[str, str]:
    import pandas as pd  # pandas는 선택적 의존

    url = _KRX_BASE.format(market=market_key)
    r = requests.get(url, headers=_HEADERS, timeout=30)
    r.raise_for_status()
    text = r.content.decode("cp949")
    df = pd.read_html(io.StringIO(text), header=0)[0]
    m: dict[str, str] = {}
    for _, row in df.iterrows():
        name = str(row.iloc[0]).strip()
        code = str(row.iloc[2]).strip().zfill(6)
        if re.match(r"^\d{6}$", code) and name and name != "nan":
            m[name] = code
    return m


def refresh_krx_cache() -> dict[str, str]:
    """KRX KOSPI+KOSDAQ 전종목 다운로드 → krx_codes.json 저장."""
    print("  [codemap] KRX 전종목 갱신 중...", end=" ", flush=True)
    m: dict[str, str] = {}
    for label, key in _KRX_MARKETS.items():
        try:
            chunk = _fetch_krx_market(key)
            m.update(chunk)
        except Exception as e:
            print(f"\n  [WARN] {label} 조회 실패: {e}")
    _KRX_CACHE_FILE.write_text(
        json.dumps(
            {"updated": datetime.now().strftime("%Y-%m-%d"), "codes": m},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"{len(m)}종목 → {_KRX_CACHE_FILE.name}")
    return m


def _load_krx_cache() -> dict[str, str]:
    """캐시 읽기. 없거나 7일+ 경과 시 자동 갱신."""
    if _KRX_CACHE_FILE.exists():
        try:
            data = json.loads(_KRX_CACHE_FILE.read_text(encoding="utf-8"))
            updated = datetime.strptime(data.get("updated", "2000-01-01"), "%Y-%m-%d")
            if datetime.now() - updated < timedelta(days=_REFRESH_DAYS):
                return data.get("codes", {})
        except (json.JSONDecodeError, ValueError):
            pass
    return refresh_krx_cache()


def _build_wisereport() -> dict[str, str]:
    """raw/wisereport/*_parsed.json에서 종목명→코드 추출 (보완 소스)."""
    m: dict[str, str] = {}
    for f in _WISE.glob("*_parsed.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for row in data.get("corp", []):
            if len(row) < 2:
                continue
            mt = re.match(r"\s*(.+?)\s*\[(\d{6})\]", str(row[1]))
            if mt:
                m[mt.group(1).strip()] = mt.group(2)
    return m


def _build() -> dict[str, str]:
    """wisereport(베이스) + KRX(덮어씀) 합성."""
    result = _build_wisereport()   # 낮은 우선순위 먼저 (옛 종목명 포함)
    result.update(_load_krx_cache())  # KRX 공식 현재명이 덮어씀
    return result


def _ensure() -> None:
    if not _CACHE:
        _CACHE.update(_build())


def code_for(name: str) -> str | None:
    if not name:
        return None
    _ensure()
    return _CACHE.get(name.strip())


def is_korean_stock(name: str) -> bool:
    return code_for(name) is not None


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh_krx_cache()
    else:
        name = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
        _ensure()
        print(f"총 {len(_CACHE)}종목 로드됨")
        if name:
            code = code_for(name)
            print(f"  {name} → {code or '없음'}")
