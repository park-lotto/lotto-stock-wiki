"""KRX 업종·주요제품 → 테마 택소노미 키워드 매핑.

KRX 업종(GICS식)은 테마 택소노미(방산·로봇·2차전지)와 직접 안 맞으므로,
업종+주요제품 텍스트에서 고신뢰 키워드만 추출해 섹터 부여.
금융·지주·건설 등 모호 분류는 매핑 안 함(기타 유지) → 정밀도 우선.

캐시: krx_industry.json (회사명 → "업종 | 주요제품")
실행: python -m pipeline.atoms.krx_industry --refresh   # KRX 재다운로드
"""
import io
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

_CACHE = Path(__file__).parent / "krx_industry.json"
_REFRESH_DAYS = 30
_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "http://kind.krx.co.kr/"}
_BASE = (
    "http://kind.krx.co.kr/corpgeneral/corpList.do"
    "?method=download&searchType=13&marketType={m}"
)

# 키워드 → 택소노미 섹터 (위에서부터 우선, 첫 매칭 채택)
# 고신뢰 키워드만. 모호어(전지·화학·소재 단독)는 배제.
_KEYWORD_RULES: list[tuple[tuple[str, ...], str]] = [
    (("반도체",), "반도체"),
    (("이차전지", "2차전지", "리튬이온전지", "양극재", "음극재", "전해액", "분리막"), "2차전지"),
    (("조선", "선박", "해양플랜트"), "조선"),
    # '무기'는 '무기화합물'(inorganic)과 충돌 → 제외. '무기체계'만 허용.
    (("방위", "방산", "국방", "무기체계", "무기류", "총포", "탄약", "미사일",
      "유도무기", "전투지휘", "함정", "잠수함", "전차", "장갑차", "자주포",
      "군용", "열영상", "탐지추적", "감시정찰", "방산전자"), "방산"),
    # 일반 '위성'은 통신·미디어(위성DMB·위성서비스)와 충돌 → 군사위성만.
    (("항공기", "우주선", "우주발사체", "발사체", "군사위성", "정찰위성"), "방산"),
    (("로봇",), "로봇"),
    (("원자력", "원전"), "원전"),
    (("태양광", "풍력", "신재생", "수소연료", "연료전지"), "신재생"),
    (("의약", "제약", "바이오", "헬스케어", "백신", "진단", "세포치료", "항체"), "바이오"),
    (("화장품", "뷰티"), "화장품미용"),
    (("이동통신", "통신서비스", "유선통신", "무선통신"), "통신"),
    (("철강", "제철", "강관", "특수강"), "철강"),
    (("자동차용", "자동차 부품", "자동차부품"), "자동차"),
    (("백화점", "편의점", "대형마트", "홈쇼핑", "면세", "종합 소매", "종합소매",
      "소매업", "식료품", "음식료", "식음료", "주류", "담배", "의류", "패션",
      "외식", "프랜차이즈", "생활용품"), "소비내수"),
]

# 모호/제외 키워드 — 매칭돼도 섹터 부여 안 함 (오분류 방지)
_BLOCK = ("지주", "은행", "보험", "증권", "금융지원", "신탁", "리스",
          "건설", "건축", "토목", "부동산", "임대")


def _scan(text: str) -> str | None:
    for kws, sec in _KEYWORD_RULES:
        if any(kw in text for kw in kws):
            return sec
    return None


def _match_keyword(text: str) -> str | None:
    """주요제품(더 구체적) 우선 → 업종 순으로 키워드 매칭.

    업종 코드는 부정확할 수 있음(예: 태양광 업체가 '반도체 제조업'으로 등재)."""
    if any(b in text for b in _BLOCK):
        strong = any(kw in text for kws, _ in _KEYWORD_RULES[:11] for kw in kws)
        if not strong:
            return None
    industry, _, product = text.partition("|")
    return _scan(product) or _scan(industry)


def _fetch() -> dict[str, str]:
    import pandas as pd
    import requests

    out: dict[str, str] = {}
    for mk in ("stockMkt", "kosdaqMkt"):
        r = requests.get(_BASE.format(m=mk), headers=_HEADERS, timeout=30)
        r.raise_for_status()
        df = pd.read_html(io.StringIO(r.content.decode("cp949")), header=0)[0]
        for _, row in df.iterrows():
            nm = str(row.get("회사명", "")).strip()
            up = str(row.get("업종", "")).strip()
            pr = str(row.get("주요제품", "")).strip()
            if nm and nm != "nan":
                out[nm] = f"{up} | {pr}"
    return out


def refresh() -> dict[str, str]:
    print("  [krx_industry] KRX 업종 갱신 중...", end=" ", flush=True)
    data = _fetch()
    _CACHE.write_text(
        json.dumps({"updated": datetime.now().strftime("%Y-%m-%d"), "info": data},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"{len(data)}종목")
    return data


def _load_raw() -> dict[str, str]:
    if _CACHE.exists():
        try:
            d = json.loads(_CACHE.read_text(encoding="utf-8"))
            updated = datetime.strptime(d.get("updated", "2000-01-01"), "%Y-%m-%d")
            if datetime.now() - updated < timedelta(days=_REFRESH_DAYS):
                return d.get("info", {})
        except (json.JSONDecodeError, ValueError):
            pass
    return refresh()


def industry_sector_map() -> dict[str, str]:
    """회사명 → 섹터 (고신뢰 키워드 매칭만)."""
    raw = _load_raw()
    out: dict[str, str] = {}
    for name, text in raw.items():
        sec = _match_keyword(text)
        if sec:
            out[name] = sec
    return out


if __name__ == "__main__":
    if "--refresh" in sys.argv:
        refresh()
    m = industry_sector_map()
    print(f"KRX 업종 키워드 매칭: {len(m)}종목")
    from collections import Counter
    for sec, n in Counter(m.values()).most_common():
        print(f"  {sec}: {n}개")
