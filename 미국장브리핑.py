"""
미국장브리핑.py — 미국장 뉴스 요약 → 텔레그램 + 아침노트

사용법:
  1. raw/미국장/오늘.txt 에 미국장 뉴스 붙여넣기
  2. python 미국장브리핑.py [--tg] [--note]

  --tg    텔레그램 발송
  --note  out/미국장_YYYYMMDD.md 저장 (아침노트 피드용)
"""
import sys, os, argparse, json, urllib.request, urllib.parse
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')

BASE    = Path(__file__).parent
TODAY   = date.today().strftime('%Y-%m-%d')
IN_FILE = BASE / 'raw' / '미국장' / '오늘.txt'
OUT_DIR = BASE / 'out'

EXTRACT_PROMPT = """
아래는 미국 주식시장 관련 뉴스·시황 텍스트다.
다음 항목을 JSON으로 추출하라. 없으면 null.

{
  "indices": {
    "dow": "+0.36%",
    "sp500": "+0.02%",
    "nasdaq": "+0.07%",
    "russell2000": "-0.02%",
    "vix": "16.29 (-4.23%)"
  },
  "macro": {
    "wti": "88.68달러 (-5.6%)",
    "us10y": "4.48%",
    "dxy": "99.20",
    "usdkrw": "1,500원",
    "fed_stance": "동결 유지 / 매파 발언 증가"
  },
  "key_news": [
    "이란-미 MOU 보도 → WTI 5% 급락, 백악관 부인 — 협상 낙관론은 유지",
    "메타 AI 유료 구독 월 7.99달러 출시 → +3.74%",
    "마이크론 목표주가 675→1,175 (바클레이즈) → +3.63%",
    "골드만 S&P500 연말 전망 7,600→8,000 상향"
  ],
  "korea_today": "한 줄 전망 (지수 방향 + 주요 테마)",
  "korea_risk": "오늘 가장 큰 리스크 한 줄",
  "korea_opportunity": "오늘 가장 큰 기회 한 줄",
  "korea_sectors": [
    {"sector": "반도체부품", "signal": "🔴", "stocks": "삼성전기·LG이노텍", "reason": "대장주 쉬는 날 부품주 순환매"},
    {"sector": "항공", "signal": "🔴", "stocks": "대한항공·제주항공", "reason": "WTI -5.6% 비용 수혜"},
    {"sector": "바이오", "signal": "🟠", "stocks": "녹십자·셀트리온", "reason": "4600억 성과·신약비전 개별이슈"},
    {"sector": "조선", "signal": "🟠", "stocks": "삼성중공업·HD현대중공업", "reason": "LNG 수주 모멘텀, 협상 결과 주시"},
    {"sector": "전력기기", "signal": "🟠", "stocks": "두산에너빌·효성중공업", "reason": "미국·일본 수주, 수급 복귀 대기"},
    {"sector": "방산", "signal": "🟡", "stocks": "한화에어로·LIG넥스원", "reason": "이란협상 진전시 모멘텀 약화 주의"},
    {"sector": "2차전지", "signal": "🟡", "stocks": "SKIET 등", "reason": "구조조정 국면, 배터리 화재 리스크"}
  ],
  "one_line": "미국 3대지수 사상최고, 이란협상 기대 유가급락 — 반도체 쉬는 타이밍 순환매 장세"
}

규칙:
- JSON만 출력. 설명 없이.
- korea_sectors: signal은 🔴(주목)/🟠(관심)/🟡(관망) 중 선택. stocks는 국내 대표 종목명.
- korea_today / korea_risk / korea_opportunity 반드시 채울 것.
- 없는 수치는 null.

[텍스트]
"""


def load_env() -> dict:
    cfg = {}
    env = BASE / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    return cfg


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if '```' in raw:
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
    return json.loads(raw.strip())


def extract_with_gemini(text: str) -> dict:
    from google import genai
    cfg = load_env()
    api_key = cfg.get('GEMINI_API_KEY') or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError('.env에 GEMINI_API_KEY 없음')

    client = genai.Client(api_key=api_key)
    resp = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=EXTRACT_PROMPT + text,
    )
    return _parse_json(resp.text)


def extract_with_claude(text: str) -> dict:
    import anthropic
    cfg = load_env()
    api_key = cfg.get('ANTHROPIC_API_KEY') or os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        raise ValueError('.env에 ANTHROPIC_API_KEY 없음')

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=1500,
        messages=[{'role': 'user', 'content': EXTRACT_PROMPT + text}]
    )
    return _parse_json(msg.content[0].text)


def build_telegram(d: dict) -> str:
    idx      = d.get('indices', {})
    mac      = d.get('macro', {})
    news     = d.get('key_news', [])
    sectors  = d.get('korea_sectors', [])

    def v(src, key): return src.get(key) or '—'

    lines = [
        f"📊 <b>미국장 브리핑</b>  {TODAY}",
        "",
        "🌐 <b>지수</b>",
        f"  다우 {v(idx,'dow')} | S&P {v(idx,'sp500')} | 나스닥 {v(idx,'nasdaq')}",
        f"  VIX {v(idx,'vix')}  |  러셀 {v(idx,'russell2000')}",
        "",
        "🛢 <b>매크로</b>",
        f"  WTI {v(mac,'wti')}  |  10년물 {v(mac,'us10y')}",
        f"  달러원 {v(mac,'usdkrw')}  |  DXY {v(mac,'dxy')}",
        f"  연준: {v(mac,'fed_stance')}",
        "",
        "🔥 <b>핵심 뉴스</b>",
    ]
    for n in news[:4]:
        lines.append(f"  · {n}")

    lines += [
        "",
        "🇰🇷 <b>오늘 한국장</b>",
        f"  📌 {d.get('korea_today','—')}",
        f"  ⚠️ 리스크: {d.get('korea_risk','—')}",
        f"  💡 기회: {d.get('korea_opportunity','—')}",
        "",
        "  <b>섹터 신호</b>",
    ]
    for s in sectors:
        sig  = s.get('signal', '·')
        name = s.get('sector', '')
        stk  = s.get('stocks', '')
        why  = s.get('reason', '')
        lines.append(f"  {sig} <b>{name}</b> ({stk})")
        lines.append(f"      └ {why}")

    lines += ["", f"<i>{d.get('one_line','')}</i>"]
    return "\n".join(lines)


def build_note(d: dict) -> str:
    idx     = d.get('indices', {})
    mac     = d.get('macro', {})
    news    = d.get('key_news', [])
    sectors = d.get('korea_sectors', [])

    def v(src, key): return src.get(key) or '—'

    lines = [
        f"# 미국장 브리핑 {TODAY}",
        "",
        f"> {d.get('one_line','')}",
        "",
        "## 지수",
        "| 다우 | S&P500 | 나스닥 | 러셀2000 | VIX |",
        "|------|--------|--------|----------|-----|",
        f"| {v(idx,'dow')} | {v(idx,'sp500')} | {v(idx,'nasdaq')} | {v(idx,'russell2000')} | {v(idx,'vix')} |",
        "",
        "## 매크로",
        f"- WTI: {v(mac,'wti')}",
        f"- 미 10년물: {v(mac,'us10y')}",
        f"- 달러원: {v(mac,'usdkrw')}",
        f"- DXY: {v(mac,'dxy')}",
        f"- 연준: {v(mac,'fed_stance')}",
        "",
        "## 핵심 뉴스",
    ]
    for n in news:
        lines.append(f"- {n}")

    lines += [
        "",
        "## 오늘 한국장",
        f"- 📌 {d.get('korea_today','—')}",
        f"- ⚠️ 리스크: {d.get('korea_risk','—')}",
        f"- 💡 기회: {d.get('korea_opportunity','—')}",
        "",
        "## 섹터 신호",
        "| 신호 | 섹터 | 종목 | 근거 |",
        "|------|------|------|------|",
    ]
    for s in sectors:
        lines.append(
            f"| {s.get('signal','—')} | {s.get('sector','—')} "
            f"| {s.get('stocks','—')} | {s.get('reason','—')} |"
        )

    return "\n".join(lines)


def send_telegram(text: str):
    cfg = load_env()
    token   = cfg.get('BOT_TOKEN', '')
    chat_id = cfg.get('CHAT_ID', '')
    if not token or not chat_id:
        print('텔레그램 설정 없음 (.env)')
        return
    url  = f'https://api.telegram.org/bot{token}/sendMessage'
    data = urllib.parse.urlencode(
        {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}).encode()
    with urllib.request.urlopen(
            urllib.request.Request(url, data), timeout=10) as resp:
        if json.loads(resp.read()).get('ok'):
            print('텔레그램 전송 완료')


def main():
    parser = argparse.ArgumentParser(description='미국장 브리핑')
    parser.add_argument('--tg',    action='store_true', help='텔레그램 발송')
    parser.add_argument('--note',  action='store_true', help='아침노트 MD 저장')
    parser.add_argument('--file',  default=str(IN_FILE), help='입력 파일 경로')
    parser.add_argument('--model', default='gemini', choices=['gemini', 'claude'], help='요약 모델 선택')
    args = parser.parse_args()

    src = Path(args.file)
    if not src.exists():
        print(f'파일 없음: {src}')
        print(f'→ raw/미국장/오늘.txt 에 뉴스 내용을 붙여넣고 다시 실행하세요')
        sys.exit(1)

    text = src.read_text(encoding='utf-8')
    print(f'[{TODAY}] 미국장 브리핑 생성 중... ({len(text):,}자)')

    model_label = 'Gemini' if args.model == 'gemini' else 'Claude'
    print(f'{model_label} 요약 중...')
    try:
        if args.model == 'gemini':
            data = extract_with_gemini(text)
        else:
            data = extract_with_claude(text)
    except Exception as e:
        print(f'요약 실패: {e}')
        sys.exit(1)

    tg_msg = build_telegram(data)
    note   = build_note(data)

    # 콘솔 미리보기
    print()
    print(tg_msg.replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '').replace('<code>', '').replace('</code>', ''))

    if args.tg:
        print()
        send_telegram(tg_msg)

    if args.note:
        OUT_DIR.mkdir(exist_ok=True)
        out_path = OUT_DIR / f'미국장_{TODAY}.md'
        out_path.write_text(note, encoding='utf-8')
        print(f'노트 저장: {out_path}')

    # 구조화 데이터 저장 (아침노트 통합용)
    json_path = BASE / 'raw' / '미국장' / f'{TODAY}_parsed.json'
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'파싱 데이터: {json_path}')


if __name__ == '__main__':
    main()
