"""텔레그램 뉴스릴레이 채널(news_relay 타입) 전용 필터+매칭 — 순수함수만.
raw/telegram/{date}_{채널}.md 표준 포맷을 읽어 시장 관련 뉴스만 골라내고
섹터/종목에 매칭한다. 실제 크롤링(원본 md 생성)은 이 모듈 밖(외부 크롤봇)에서
일어난다 — 이 모듈은 그 결과를 소비만 한다.
"""
import re


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


def is_market_relevant(text: str, stock_names: set[str]) -> bool:
    """종목명이 직접 언급되면 무조건 관련. 아니면 시장 키워드가 있고
    노이즈 키워드(연예/스포츠/정치 등)가 없어야 관련으로 본다."""
    if any(name in text for name in stock_names if len(name) >= 2):
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
    """stock_sector_map.json의 종목명 중 본문에 등장하는 것들. 1글자 종목명은
    오탐이 너무 많아 제외."""
    return [name for name in stock_names if len(name) >= 2 and name in text]


def filter_and_match(messages: list[dict], stock_names: set[str],
                      sector_keywords: dict) -> list[dict]:
    """parse_telegram_md() 결과를 받아 시장무관 뉴스는 버리고, 남은 것에
    headline/sectors/stocks를 채워 반환."""
    out = []
    for m in messages:
        text = m.get("text", "")
        if not is_market_relevant(text, stock_names):
            continue
        out.append({
            "ts": m.get("ts"),
            "headline": extract_headline(text),
            "text": text,
            "urls": m.get("urls", []),
            "sectors": match_sectors(text, sector_keywords),
            "stocks": match_stocks(text, stock_names),
        })
    return out
