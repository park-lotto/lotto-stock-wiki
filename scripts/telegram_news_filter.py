"""텔레그램 뉴스릴레이 채널(news_relay 타입) 전용 필터+매칭 — 순수함수만.
raw/telegram/{date}_{채널}.md 표준 포맷을 읽어 시장 관련 뉴스만 골라내고
섹터/종목에 매칭한다. 실제 크롤링(원본 md 생성)은 이 모듈 밖(외부 크롤봇)에서
일어난다 — 이 모듈은 그 결과를 소비만 한다.
"""
import os
import re
from datetime import datetime

try:
    from news_feed import _STOCK_ABBREV   # 삼전/하닉/삼바 등 언론 관용 약칭(기존 자산 재사용)
except ImportError:
    _STOCK_ABBREV = {}


_GENERIC_NON_STOCK_WORDS = {"종목", "테마", "그룹", "기업", "산업"}


def clean_stock_names(stock_sector_map: dict) -> set[str]:
    """stock_sector_map.json(전체 1057건)에서 실제 개별 종목명만 추린다.
    실채널 검증에서 발견: 이 맵엔 "시장"→"시장", "자동차"→"자동차"처럼
    키==값인 섹터 카테고리 라벨 18개가 섞여있어(반도체/바이오/전력 등),
    그대로 쓰면 "시장"/"자동차" 같은 흔한 단어가 아무 뉴스에나 종목으로
    오탐된다. key==value 항목 + 알려진 일반명사(종목 등)를 제외한다."""
    return {k for k, v in stock_sector_map.items()
            if k != v and k not in _GENERIC_NON_STOCK_WORDS}


def parse_telegram_md(text: str) -> list[dict]:
    """`# 텔레그램 - {채널} - {날짜}` 헤더 + `---`로 구분된 `**HH:MM**` 메시지
    블록들을 파싱. 각 메시지의 원문(text)과 그 안의 URL들을 추출한다."""
    blocks = re.split(r"\n---\n", text)
    out = []
    for block in blocks:
        m = re.search(r"\*\*(\d{2}:\d{2})\*\*", block)
        if not m:
            continue
        ts = m.group(1)
        body = block[m.end():].strip()
        urls = re.findall(r"https?://\S+", body)
        out.append({"ts": ts, "text": body, "urls": urls})
    return out


def extract_headline(text: str) -> str:
    """메시지 본문에서 첫 줄(마크다운 굵게/이모지 제거)을 헤드라인으로."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        line = re.sub(r"\*\*", "", line)
        line = re.sub(r"^[^\w\[가-힣]+", "", line)   # 앞쪽 이모지 제거
        line = line.strip()
        if line:
            return line
    return ""


_NOISE_KEYWORDS = (
    "축구", "야구", "농구", "배구", "골프", "연예", "결혼", "이혼", "출산",
    "음란", "성폭행", "국회", "여야", "탄핵", "판결", "구속영장", "검찰 수사",
)
_MARKET_KEYWORDS = (
    "코스피", "코스닥", "증시", "주가", "실적", "영업이익", "매출", "상한가",
    "하한가", "상장", "공모", "특징주", "속보", "IPO", "인수", "M&A",
)


def _abbrev_to_full() -> dict:
    """{약칭: 정식종목명} 역인덱스 — _STOCK_ABBREV({정식명:[약칭들]})에서 구성."""
    out = {}
    for full, abbrevs in _STOCK_ABBREV.items():
        for a in abbrevs:
            out[a] = full
    return out


_ABBREV_TO_FULL = _abbrev_to_full()


def is_market_relevant(text: str, stock_names: set[str]) -> bool:
    """종목명(약칭 포함, 예: 삼전/하닉)이 직접 언급되면 무조건 관련. 아니면
    시장 키워드가 있고 노이즈 키워드(연예/스포츠/정치 등)가 없어야 관련으로 본다."""
    if any(name in text for name in stock_names if len(name) >= 2):
        return True
    if any(a in text for a in _ABBREV_TO_FULL):
        return True
    if any(k in text for k in _NOISE_KEYWORDS):
        return False
    return any(k in text for k in _MARKET_KEYWORDS)


def match_sectors(text: str, sector_keywords: dict) -> list[str]:
    """sector_news_keywords.json 형식({code: {sector, must:[...]}})의 must
    키워드 중 하나라도 본문에 있으면 그 섹터로 매칭. 중복 섹터명은 한 번만."""
    hits = []
    for entry in sector_keywords.values():
        if not isinstance(entry, dict):
            continue
        sector = entry.get("sector")
        must = entry.get("must") or []
        if sector and sector not in hits and any(kw in text for kw in must):
            hits.append(sector)
    return hits


def match_stocks(text: str, stock_names: set[str]) -> list[str]:
    """stock_sector_map.json의 종목명(+news_feed._STOCK_ABBREV 언론관용약칭,
    예: 삼전→삼성전자) 중 본문에 등장하는 것들. 정식명으로 통일해서 반환하므로
    "삼전"만 나온 기사도 "삼성전자"로 집계된다. 1글자 종목명은 오탐이 너무
    많아 제외."""
    hits = {name for name in stock_names if len(name) >= 2 and name in text}
    for abbrev, full in _ABBREV_TO_FULL.items():
        if abbrev in text:
            hits.add(full)
    return list(hits)


def filter_and_match(messages: list[dict], stock_names: set[str],
                      sector_keywords: dict) -> list[dict]:
    """parse_telegram_md() 결과를 받아 시장무관 뉴스는 버리고, 남은 것에
    headline/sectors/stocks를 채워 반환."""
    out = []
    seen_headlines = set()
    for m in messages:
        text = m.get("text", "")
        if not is_market_relevant(text, stock_names):
            continue
        headline = extract_headline(text)
        norm = re.sub(r"\s+", "", headline)   # 재게시 시 공백만 다른 경우도 잡음
        if norm in seen_headlines:
            continue   # 같은 뉴스 재게시(속보 채널 특성상 흔함) — 처음 것만 남김
        seen_headlines.add(norm)
        out.append({
            "ts": m.get("ts"),
            "headline": headline,
            "text": text,
            "urls": m.get("urls", []),
            "sectors": match_sectors(text, sector_keywords),
            "stocks": match_stocks(text, stock_names),
        })
    return out


def group_by_sector_and_stock(matched: list[dict], date_str: str) -> tuple[dict, dict]:
    """filter_and_match() 결과를 {섹터명: [뉴스아이템]} / {종목명: [뉴스아이템]}
    로 묶는다. 히트맵의 sector_news/stock_news 병합 지점에서 바로 쓸 수 있는
    {title, url, ts, date} 형태로 각 아이템을 변환한다(sector_news_keywords
    매칭 결과와 같은 필드명을 맞춰서 프론트가 소스 구분 없이 렌더링 가능).
    date는 news_feed._fmt_rss와 같은 "MM/DD HH:MM" 포맷 — dashboard/server.py의
    AI요약 "오늘자만" 필터(date.startswith(MM/DD))가 이 포맷을 기대하므로, 없으면
    텔레그램 뉴스가 전부 그 필터에서 누락된다(실사용 발견 버그)."""
    mmdd = f"{date_str[5:7]}/{date_str[8:10]}"
    by_sector: dict[str, list] = {}
    by_stock: dict[str, list] = {}
    for item in matched:
        url = item["urls"][0] if item["urls"] else None
        news_item = {"title": item["headline"], "url": url, "ts": item["ts"],
                     "date": f"{mmdd} {item['ts']}", "source": "telegram"}
        for sector in item["sectors"]:
            by_sector.setdefault(sector, []).append(news_item)
        for stock in item["stocks"]:
            by_stock.setdefault(stock, []).append(news_item)
    return by_sector, by_stock


def load_today_news_relay(raw_telegram_dir: str, channels: dict,
                           stock_names: set[str], sector_keywords: dict,
                           date_str: str | None = None) -> tuple[dict, dict]:
    """channels(telegram_channels.json 로드결과)에서 type=='news_relay'인
    채널들의 오늘자 raw/telegram/{date}_{채널}.md를 전부 읽어 필터+매칭한
    뒤 섹터/종목별로 합쳐서 반환. 파일이 없는 채널(아직 크롤 안 됨)은
    조용히 건너뛴다 — 없다고 에러 내지 않는다."""
    date_str = date_str or datetime.now().strftime("%Y-%m-%d")
    all_matched = []
    for name, info in channels.items():
        if not isinstance(info, dict) or info.get("type") != "news_relay":
            continue
        path = os.path.join(raw_telegram_dir, f"{date_str}_{name}.md")
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except Exception:
            continue
        messages = parse_telegram_md(text)
        all_matched.extend(filter_and_match(messages, stock_names, sector_keywords))
    return group_by_sector_and_stock(all_matched, date_str)
