#!/usr/bin/env python3
"""
ingest_record.py — 텔레그램 + wisereport → db/insights.json

기준: 증권사 TP·의견·리포트가 있는 것만 저장
중복: 같은 날 같은 종목 → broker_count 누적

사용:
  python ingest_record.py                      # 오늘 전체
  python ingest_record.py --date 2026-06-05    # 특정 날짜
  python ingest_record.py --tg-only            # 텔레그램만
  python ingest_record.py --wise-only          # wisereport만
  python ingest_record.py --dry                # 미리보기 (저장 안 함)
"""

import sys, os, json, re, argparse
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')

BASE      = Path(__file__).parent
DB_FILE   = BASE / "db" / "insights.json"
RAW_TG    = BASE / "raw" / "telegram"
RAW_WISE  = BASE / "raw" / "wisereport"
CRAWL_BOT = Path(r"C:\Users\TheRose\crawling_bot_data")

SECTOR_MAP     = json.loads((BASE / "sector_map.json").read_text(encoding='utf-8'))
NAME_TO_SECTOR = {k: v['섹터'] for k, v in SECTOR_MAP.items()}
CODE_TO_SECTOR = {v['코드']: v['섹터'] for v in SECTOR_MAP.values() if '코드' in v}


# ─── Gemini
def get_gemini():
    from google import genai
    env = BASE / '.env'
    cfg = {}
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    api_key = cfg.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('.env에 GEMINI_API_KEY 없음')
    return genai.Client(api_key=api_key)


# ─── DB
def load_db():
    DB_FILE.parent.mkdir(exist_ok=True)
    if not DB_FILE.exists():
        return {"records": []}
    return json.loads(DB_FILE.read_text(encoding='utf-8'))

def save_db(db):
    DB_FILE.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding='utf-8')


# ─── 유틸
def make_id(date_str, sector, name, existing_ids):
    sector = sector or '기타'
    name   = name   or 'unknown'
    slug   = re.sub(r'[^\w가-힣]', '', f"{date_str.replace('-','')}_{sector[:4]}_{name[:6]}")
    for i in range(1, 200):
        uid = f"{slug}_{i:03d}"
        if uid not in existing_ids:
            return uid
    return f"{slug}_999"

def tp_int(s):
    try:
        return int(str(s).replace(',', '').replace('원', '').strip())
    except:
        return 0

def parse_ticker(raw):
    m = re.match(r'^(.+?)\[(\d+)\]$', raw.strip())
    return (m.group(1).strip(), m.group(2)) if m else (raw.strip(), None)

def parse_broker(raw):
    m = re.match(r'^(.{2,8}(?:증권|투자|자산|리서치|운용|금융|캐피탈|은행))', raw)
    return m.group(1) if m else raw.split(',')[0][:8]

def tp_signal(tp_dir):
    return {'▲': '강세', '▼': '약세'}.get(tp_dir, '중립')


# ─── 중복 병합: 같은 날 + 같은 종목이면 broker_count 누적
def merge_or_append(records, new_r):
    key_date   = new_r['date']
    key_ticker = (new_r.get('ticker') or '').strip()
    key_name   = new_r.get('ticker_name', '').strip()

    for r in records:
        if r['date'] != key_date:
            continue
        match = (key_ticker and key_ticker == (r.get('ticker') or '').strip()) or \
                (key_name and key_name == r.get('ticker_name', '').strip())
        if match:
            r['broker_count'] = r.get('broker_count', 1) + 1
            brokers = r.get('broker', '')
            new_broker = new_r.get('broker', '')
            if new_broker and new_broker not in brokers:
                r['broker'] = f"{brokers} · {new_broker}" if brokers else new_broker
            return  # 기존 레코드 업데이트
    records.append(new_r)


# ─── wisereport 처리
def ingest_wisereport(date_str, existing_ids):
    f = RAW_WISE / f"{date_str}_parsed.json"
    if not f.exists():
        print(f"  [wisereport] {f.name} 없음, 스킵")
        return []

    data    = json.loads(f.read_text(encoding='utf-8'))
    records = []

    for group in ('corp', 'sector'):
        for item in data.get(group, []):
            if len(item) < 7:
                continue
            broker_raw, ticker_raw = item[0], item[1]
            opinion_dir, opinion, tp_dir = item[2], item[3], item[4]
            tp_raw, price_raw = item[5], item[6]
            title   = item[7] if len(item) > 7 else ''
            content = item[8][:300] if len(item) > 8 else ''

            ticker_name, ticker = parse_ticker(ticker_raw)
            tp    = tp_int(tp_raw)
            price = tp_int(price_raw)
            sector = NAME_TO_SECTOR.get(ticker_name) \
                  or (CODE_TO_SECTOR.get(ticker) if ticker else None) \
                  or '기타'
            broker = parse_broker(broker_raw)

            # TP 상승여력
            upside_pct = round((tp - price) / price * 100, 1) if tp > 0 and price > 0 else None
            signal = tp_signal(tp_dir)

            uid = make_id(date_str, sector, ticker_name, existing_ids)
            existing_ids.add(uid)

            new_r = {
                'id':           uid,
                'date':         date_str,
                'sector':       sector,
                'ticker':       ticker,
                'ticker_name':  ticker_name,
                'type':         'TP변경',
                'title':        title or f"{broker} {ticker_name} {opinion} TP{tp_dir}{tp_raw}",
                'content':      content,
                'signal':       signal,
                'broker':       broker,
                'broker_count': 1,
                'tp_price':     tp if tp > 0 else None,
                'tp_direction': {'▲': '상향', '▼': '하향', '=': '유지'}.get(tp_dir, '유지'),
                'upside_pct':   upside_pct,
                'active':       True,
                'valid_type':   'TP변경',
                'valid_until':  None,
                'user_comment': '',
                'source':       f"wisereport {date_str}",
                'tags':         [ticker_name, sector, broker]
            }
            merge_or_append(records, new_r)

    print(f"  [wisereport] {len(records)}건 추출")
    return records


# ─── 텔레그램 처리 (Gemini 추출)
TG_PROMPT = """\
다음은 텔레그램 투자 채널({channel}, {date}) 내용이다.

**증권사(투자은행·리서치센터)가 직접 제시한 것만 추출:**
- 증권사 목표주가(TP) 제시 또는 변경
- 증권사 투자의견(매수/매도/중립 등)
- 증권사 리포트 핵심 내용
- 기업 공시 수주·기술이전·MOU 등 하드 이벤트

**제외:**
- 단순 뉴스 전달·시황 설명·매크로 지표
- 개인 의견·예측
- 주가 등락 언급
- 증권사 출처 없는 내용

---
{content}
---

JSON 배열만 출력 (없으면 []):
[
  {{
    "broker": "증권사명 (없으면 null)",
    "sector": "반도체|바이오|로봇|전력|조선|방산|엔터|AI소프트웨어|2차전지|통신|소재|자동차|기타",
    "ticker": "종목코드6자리 또는 null",
    "ticker_name": "종목명",
    "type": "TP변경|수주/기술이전|실적|섹터리포트",
    "title": "20자 이내 한줄 제목",
    "content": "핵심 내용 2~3줄 (수치 포함)",
    "signal": "강세|약세|중립",
    "tp_price": 목표주가숫자또는null,
    "tp_direction": "상향|하향|유지|신규|null"
  }}
]
"""

def extract_json(raw):
    raw = raw.strip()
    raw = re.sub(r'```json\s*', '', raw)
    raw = re.sub(r'```', '', raw)
    m = re.search(r'\[[\s\S]*\]', raw)
    return m.group(0) if m else '[]'

def ingest_telegram(date_str, client, existing_ids):
    tg_dir = RAW_TG / date_str
    files  = sorted(tg_dir.glob("*_요약.md")) if tg_dir.exists() else []

    if not files:
        bot_dir = CRAWL_BOT / date_str / "telegram"
        if bot_dir.exists():
            files = sorted(bot_dir.glob(f"{date_str}_*.md"))
            print(f"  [telegram] 크롤링봇 원본 사용 ({len(files)}개 채널)")
        else:
            print(f"  [telegram] {date_str} 데이터 없음, 스킵")
            return []

    all_records = []
    for f in files:
        try:
            stem    = f.stem
            channel = stem.replace('_요약', '') if stem.endswith('_요약') \
                      else stem.split('_', 1)[1] if '_' in stem else stem

            content = f.read_text(encoding='utf-8', errors='replace')
            print(f"  [telegram] {channel} ...", end=' ')

            prompt = (TG_PROMPT
                      .replace('{channel}', channel)
                      .replace('{date}', date_str)
                      .replace('{content}', content[:4000]))
            resp     = client.models.generate_content(model='gemini-3-flash-preview', contents=prompt)
            raw_json = extract_json(resp.text)
            items    = json.loads(raw_json)
        except Exception as e:
            print(f"오류 ({e}), 스킵")
            continue

        count = 0
        for item in items:
            try:
                if not isinstance(item, dict):
                    continue
                sector_val = item.get('sector') or '기타'
                name_val   = item.get('ticker_name') or ''
                uid = make_id(date_str, sector_val, name_val, existing_ids)
                existing_ids.add(uid)

                new_r = {
                    'id':           uid,
                    'date':         date_str,
                    'sector':       sector_val,
                    'ticker':       item.get('ticker'),
                    'ticker_name':  name_val,
                    'type':         item.get('type') or 'TP변경',
                    'title':        item.get('title') or '',
                    'content':      item.get('content') or '',
                    'signal':       item.get('signal') or '중립',
                    'broker':       item.get('broker') or channel,
                    'broker_count': 1,
                    'tp_price':     item.get('tp_price'),
                    'tp_direction': item.get('tp_direction'),
                    'upside_pct':   None,
                    'active':       True,
                    'valid_type':   item.get('type') or 'TP변경',
                    'valid_until':  None,
                    'user_comment': '',
                    'source':       f"{channel} {date_str}",
                    'tags':         []
                }
                merge_or_append(all_records, new_r)
                count += 1
            except Exception as e:
                print(f"    item오류: {e}")
                continue

        print(f"{count}건")

    return all_records


# ─── 출력
def fmt_record(r):
    sig  = {'강세': '🔴', '약세': '🔵', '중립': '⬜'}.get(r.get('signal', ''), '  ')
    cnt  = r.get('broker_count', 1)
    cnt_str = f"[{cnt}곳]" if cnt > 1 else "     "
    tp   = f" TP{r['tp_direction']}{r['tp_price']:,}" if r.get('tp_price') and r.get('tp_direction') not in (None, 'null') else ''
    up   = f" (+{r['upside_pct']}%)" if r.get('upside_pct') and r['upside_pct'] > 0 else ''
    return f"  {sig}{cnt_str} [{r['sector']}] {r['ticker_name']} —{tp}{up} {r['title']}"


# ─── main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date',      default=date.today().strftime('%Y-%m-%d'))
    ap.add_argument('--tg-only',   action='store_true')
    ap.add_argument('--wise-only', action='store_true')
    ap.add_argument('--dry',       action='store_true')
    args = ap.parse_args()

    date_str = args.date
    print(f"\n{'='*40}\n ingest_record — {date_str}\n{'='*40}")

    db           = load_db()
    existing_ids = {r['id'] for r in db.get('records', [])}
    new_records  = []

    if not args.tg_only:
        new_records += ingest_wisereport(date_str, existing_ids)

    if not args.wise_only:
        try:
            client = get_gemini()
            tg_recs = ingest_telegram(date_str, client, existing_ids)
            # 텔레그램 결과도 wisereport와 병합
            for r in tg_recs:
                merge_or_append(new_records, r)
        except Exception as e:
            print(f"  [telegram] 오류: {e}")

    if not new_records:
        print("\n추출된 레코드 없음")
        return

    # 정렬: broker_count 내림차순 → 강세 먼저
    def sort_key(r):
        sig_order = {'강세': 0, '중립': 1, '약세': 2}
        return (-r.get('broker_count', 1), sig_order.get(r.get('signal', ''), 1))

    new_records.sort(key=sort_key)

    print(f"\n[ 추출 결과 — {len(new_records)}건 ]")
    for r in new_records:
        print(fmt_record(r))

    if args.dry:
        print("\n--dry 모드: 저장 안 함")
        return

    db.setdefault('records', []).extend(new_records)
    save_db(db)
    print(f"\n✅ db/insights.json에 {len(new_records)}건 저장")


if __name__ == '__main__':
    main()
