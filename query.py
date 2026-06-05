#!/usr/bin/env python3
"""
query.py — db/insights.json 조회

사용:
  python query.py                          # 오늘 전체 요약
  python query.py --sector 반도체          # 섹터 필터
  python query.py --ticker LG이노텍        # 종목 검색
  python query.py --days 7                 # 최근 7일
  python query.py --signal 강세            # 신호 필터 (강세|약세|중립)
  python query.py --video                  # 영상 소재 후보만
  python query.py --top                    # 고득점 top10
  python query.py --summary                # 섹터별 강세/약세 카운트
  python query.py 마이크론                 # 자유 텍스트 검색

  # 복합
  python query.py --sector 반도체 --days 7 --signal 강세
  python query.py --video --days 3
"""

import sys, json, argparse, re
from pathlib import Path
from datetime import date, timedelta

sys.stdout.reconfigure(encoding='utf-8')

BASE    = Path(__file__).parent
DB_FILE = BASE / "db" / "insights.json"


def load_records():
    if not DB_FILE.exists():
        print("db/insights.json 없음 — ingest_record.py 먼저 실행")
        sys.exit(1)
    db = json.loads(DB_FILE.read_text(encoding='utf-8'))
    return db.get('records', [])


def fmt(r, show_content=False):
    sig  = {'강세': '🔴', '약세': '🔵', '중립': '⬜'}.get(r.get('signal', ''), '  ')
    cnt  = r.get('broker_count', 1)
    cnt_str = f"[{cnt}곳]" if cnt > 1 else "      "
    name = r.get('ticker_name', '')
    if r.get('ticker'):
        name = f"{name}({r['ticker']})"
    tp  = f" TP{r['tp_direction']}{r['tp_price']:,}" if r.get('tp_price') and r.get('tp_direction') not in (None, 'null', '유지') else ''
    up  = f"(+{r['upside_pct']}%)" if r.get('upside_pct') and r['upside_pct'] > 0 else ''
    line = f"  {sig}{cnt_str} [{r['sector']}] {name}{tp}{up} — {r['title']}"
    if show_content and r.get('content'):
        for l in r['content'].strip().splitlines():
            line += f"\n      {l.strip()}"
    if show_content and r.get('user_comment'):
        line += f"\n      💬 {r['user_comment']}"
    return line


def sort_records(records):
    sig_order = {'강세': 0, '중립': 1, '약세': 2}
    return sorted(records,
                  key=lambda r: (-r.get('broker_count', 1),
                                 sig_order.get(r.get('signal', '중립'), 1)))

def apply_filters(records, args, free_text=None):
    today     = date.today()
    cutoff    = (today - timedelta(days=args.days)).isoformat() if args.days else None

    result = []
    for r in records:
        if not r.get('active', True):
            continue
        if cutoff and r.get('date', '') < cutoff:
            continue
        if args.sector and args.sector not in r.get('sector', ''):
            continue
        if args.ticker and args.ticker.lower() not in (r.get('ticker_name', '') + r.get('ticker', '')).lower():
            continue
        if args.signal and r.get('signal') != args.signal:
            continue
        if args.video and not r.get('video_candidate'):
            continue
        if args.type and args.type not in r.get('type', ''):
            continue
        if free_text:
            hay = ' '.join([
                r.get('ticker_name', ''), r.get('title', ''),
                r.get('content', ''), ' '.join(r.get('tags', []))
            ]).lower()
            if free_text.lower() not in hay:
                continue
        result.append(r)

    return sort_records(result)


def print_records(records, show_content=False, limit=None):
    shown = records[:limit] if limit else records
    for r in shown:
        print(fmt(r, show_content))
    if limit and len(records) > limit:
        print(f"  ... 외 {len(records)-limit}건 (--all 로 전체 조회)")


def cmd_summary(records, days):
    today  = date.today()
    cutoff = (today - timedelta(days=days)).isoformat()
    recent = [r for r in records if r.get('date', '') >= cutoff and r.get('active', True)]

    # 섹터별 집계
    sectors = {}
    for r in recent:
        s = r.get('sector', '기타')
        if s not in sectors:
            sectors[s] = {'강세': 0, '약세': 0, '중립': 0, 'top': None}
        sig = r.get('signal', '중립')
        sectors[s][sig] += 1
        if sectors[s]['top'] is None or r.get('broker_count', 1) > sectors[s]['top'].get('broker_count', 1):
            sectors[s]['top'] = r

    print(f"\n[ 섹터 요약 — 최근 {days}일 / {len(recent)}건 ]\n")
    print(f"  {'섹터':<14} {'강세':>4} {'약세':>4} {'중립':>4}  베스트 인사이트")
    print(f"  {'-'*70}")
    for s, v in sorted(sectors.items(), key=lambda x: x[1]['강세'], reverse=True):
        top = v['top']
        top_str = f"{top['title'][:28]}  (★{top['score']})" if top else ''
        bull = f"🔴{v['강세']}" if v['강세'] else f"   {v['강세']}"
        bear = f"🔵{v['약세']}" if v['약세'] else f"   {v['약세']}"
        print(f"  {s:<14} {bull:>6} {bear:>6} {v['중립']:>4}  {top_str}")


def cmd_today(records):
    today = date.today().isoformat()
    tod   = [r for r in records if r.get('date') == today]
    if not tod:
        print(f"오늘({today}) 데이터 없음")
        return
    tod_sorted = sorted(tod, key=lambda x: x.get('score', 0), reverse=True)

    print(f"\n[ 오늘 {today} — {len(tod)}건 ]\n")

    # 영상 소재
    vids = [r for r in tod_sorted if r.get('video_candidate')]
    if vids:
        print("  🎬 영상 소재 후보:")
        for r in vids:
            print(fmt(r))
        print()

    # 강세 상위
    bulls = [r for r in tod_sorted if r.get('signal') == '강세']
    if bulls:
        print("  🔴 강세:")
        print_records(bulls, limit=8)
        print()

    # 약세
    bears = [r for r in tod_sorted if r.get('signal') == '약세']
    if bears:
        print("  🔵 약세:")
        print_records(bears, limit=5)
        print()


def main():
    ap = argparse.ArgumentParser(description='인사이트 레코드 조회')
    ap.add_argument('free',        nargs='?',            help='자유 텍스트 검색')
    ap.add_argument('--sector',    default='',           help='섹터 필터 (부분일치)')
    ap.add_argument('--ticker',    default='',           help='종목명/코드 검색')
    ap.add_argument('--signal',    default='',           help='강세|약세|중립')
    ap.add_argument('--type',      default='',           help='TP변경|이벤트/수주|섹터방향성 ...')
    ap.add_argument('--days',      type=int, default=0,  help='최근 N일 (기본=전체)')
    ap.add_argument('--video',     action='store_true',  help='영상 소재 후보만')
    ap.add_argument('--top',       action='store_true',  help='고득점 top10')
    ap.add_argument('--summary',   action='store_true',  help='섹터별 요약')
    ap.add_argument('--today',     action='store_true',  help='오늘 데이터만')
    ap.add_argument('--detail',    action='store_true',  help='내용 상세 출력')
    ap.add_argument('--all',       action='store_true',  help='전체 출력 (limit 해제)')
    args = ap.parse_args()

    records = load_records()

    # 오늘 요약 (인자 없을 때 기본)
    if args.today or (not any([args.sector, args.ticker, args.signal, args.type,
                                args.days, args.video, args.top, args.summary, args.free])):
        cmd_today(records)
        return

    # 섹터 요약
    if args.summary:
        days = args.days or 7
        cmd_summary(records, days)
        return

    # top10
    if args.top:
        days = args.days or 14
        cutoff = (date.today() - timedelta(days=days)).isoformat()
        top = sort_records(
            [r for r in records if r.get('date', '') >= cutoff and r.get('active', True)]
        )[:10]
        print(f"\n[ Top {len(top)} — 최근 {days}일 ]\n")
        print_records(top, show_content=args.detail)
        return

    # 일반 필터
    if not args.days:
        args.days = 30  # 기본 30일
    filtered = apply_filters(records, args, free_text=args.free)

    # 헤더
    parts = []
    if args.free:       parts.append(f'"{args.free}"')
    if args.sector:     parts.append(f'섹터={args.sector}')
    if args.ticker:     parts.append(f'종목={args.ticker}')
    if args.signal:     parts.append(f'{args.signal}만')
    if args.video:      parts.append('영상소재')
    if args.type:       parts.append(f'유형={args.type}')
    label = ' + '.join(parts) or '전체'
    print(f"\n[ {label} — 최근 {args.days}일 / {len(filtered)}건 ]\n")

    limit = None if args.all else 20
    print_records(filtered, show_content=args.detail, limit=limit)


if __name__ == '__main__':
    main()
