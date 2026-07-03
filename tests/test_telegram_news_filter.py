import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from telegram_news_filter import (
    parse_telegram_md, extract_headline, is_market_relevant,
    match_sectors, match_stocks, filter_and_match,
    group_by_sector_and_stock, load_today_news_relay,
)


_SAMPLE_MD = """# 텔레그램 - 그로쓰리서치특징주 - 2026-07-03


---


**16:03**

[중국 특징주] AI 스타트업 '조인', 앤트그룹 주도 펀딩서 1130억 조달 (뉴스핌)

https://www.newspim.com/news/view/20260703000817

조이인(慕享智能科技) 가정용 동반자 로봇 스타트업이 앤트그룹 주도 Pre-A 투자
라운드에서 5억 위안(≈1130억원)을 조달해 총 10억 위안을 확보했다.

---

**16:34**

[속보] 개그우먼 박은영, 5세 연하와 5일 결혼

https://n.news.naver.com/mnews/article/000/0000000001

---
"""


def test_parse_telegram_md_extracts_ts_and_body():
    out = parse_telegram_md(_SAMPLE_MD)
    assert len(out) == 2
    assert out[0]["ts"] == "16:03"
    assert "조인" in out[0]["text"]
    assert out[0]["urls"] == ["https://www.newspim.com/news/view/20260703000817"]
    assert out[1]["ts"] == "16:34"


def test_extract_headline_strips_markdown_and_emoji():
    text = "[중국 특징주] AI 스타트업 '조인', 앤트그룹 주도 펀딩서 1130억 조달 (뉴스핌)\n\n다음줄"
    assert extract_headline(text) == "[중국 특징주] AI 스타트업 '조인', 앤트그룹 주도 펀딩서 1130억 조달 (뉴스핌)"


def test_is_market_relevant_true_for_known_stock_mention():
    assert is_market_relevant("오늘 삼성전자 주가가 급등했다", {"삼성전자", "SK하이닉스"}) is True


def test_is_market_relevant_true_for_market_keyword_without_noise():
    assert is_market_relevant("[속보] 코스피 오늘 사상 최고가 경신", set()) is True


def test_is_market_relevant_false_for_celebrity_noise():
    assert is_market_relevant("[속보] 개그우먼 박은영, 5세 연하와 5일 결혼", set()) is False


def test_is_market_relevant_false_for_sports_noise():
    assert is_market_relevant("[속보] 박지성 이영표 박주호가 '밑바닥' 한국 축구판 바꾸나", set()) is False


def test_match_sectors_finds_must_keyword_hit():
    kw = {"091160": {"sector": "반도체", "must": ["반도체", "HBM"]},
          "445290": {"sector": "로봇", "must": ["로봇", "휴머노이드"]}}
    assert match_sectors("오늘 HBM 수요 폭증 소식", kw) == ["반도체"]
    assert match_sectors("휴머노이드 로봇 신제품 공개", kw) == ["로봇"]
    assert match_sectors("무관한 뉴스입니다", kw) == []


def test_match_stocks_finds_known_names_and_excludes_short_names():
    names = {"삼성전자", "SK하이닉스", "S"}
    out = match_stocks("삼성전자와 SK하이닉스가 동반 상승했다", names)
    assert set(out) == {"삼성전자", "SK하이닉스"}


def test_filter_and_match_drops_noise_and_enriches_relevant():
    messages = parse_telegram_md(_SAMPLE_MD)
    kw = {"445290": {"sector": "로봇", "must": ["로봇"]}}
    out = filter_and_match(messages, {"조인"}, kw)
    assert len(out) == 1   # 결혼 뉴스는 필터링됨
    assert out[0]["ts"] == "16:03"
    assert "로봇" in out[0]["sectors"]
    assert "조인" in out[0]["stocks"]
    assert out[0]["urls"] == ["https://www.newspim.com/news/view/20260703000817"]


def test_group_by_sector_and_stock_buckets_correctly():
    matched = [
        {"ts": "16:03", "headline": "제목1", "urls": ["https://a.com"],
         "sectors": ["로봇"], "stocks": ["조인"]},
        {"ts": "16:10", "headline": "제목2", "urls": [],
         "sectors": ["로봇", "AI"], "stocks": []},
    ]
    by_sector, by_stock = group_by_sector_and_stock(matched)
    assert len(by_sector["로봇"]) == 2
    assert by_sector["로봇"][0]["title"] == "제목1"
    assert by_sector["로봇"][0]["url"] == "https://a.com"
    assert by_sector["로봇"][0]["source"] == "telegram"
    assert by_sector["AI"][0]["title"] == "제목2"
    assert by_stock["조인"][0]["title"] == "제목1"


def test_load_today_news_relay_skips_channels_with_no_file_and_wrong_type(tmp_path):
    raw_dir = str(tmp_path)
    (tmp_path / "2026-07-03_주식픽.md").write_text(_SAMPLE_MD, encoding="utf-8")
    channels = {
        "주식픽": {"type": "news_relay", "url": "https://t.me/stockinfo7"},
        "대신시황": {"type": "market", "url": "https://t.me/daishinstrategy"},
        "실시간주식뉴스": {"type": "news_relay", "url": "https://t.me/realtime_stock_news"},
    }
    kw = {"445290": {"sector": "로봇", "must": ["로봇"]}}
    by_sector, by_stock = load_today_news_relay(
        raw_dir, channels, {"조인"}, kw, date_str="2026-07-03")
    assert "로봇" in by_sector   # 주식픽 파일만 있고, market 타입/파일없는 채널은 무시됨
    assert "조인" in by_stock
