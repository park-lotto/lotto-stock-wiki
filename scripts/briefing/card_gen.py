"""
card_gen.py — 운영자 판단이 담긴 아침 브리핑 HTML 카드 생성

사용:
  python scripts/briefing/card_gen.py          # 운영자 답변 기반
  python scripts/briefing/card_gen.py --auto   # 자동 초안 (워터마크 포함)
"""
import sys, io, json, argparse, os
from datetime import date, datetime
from pathlib import Path
from dotenv import load_dotenv

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ROOT       = Path(__file__).parent.parent.parent
STATE_PATH = ROOT / 'pipeline' / 'briefing_state.json'
OUT_DIR    = ROOT / 'out'
load_dotenv(ROOT / '.env')

VERDICT_BADGE = {
    'A':    ('#00e5c6', 'rgba(0,229,198,0.15)', '✓'),
    'B':    ('#ff2244', 'rgba(255,34,68,0.15)',  '✗'),
    'AUTO': ('#ffe500', 'rgba(255,229,0,0.15)',  '⚠'),
}

def load_state() -> dict:
    return json.loads(STATE_PATH.read_text(encoding='utf-8'))

def save_state(s: dict):
    STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')

def build_insight(state: dict, auto: bool) -> tuple:
    """(insight_text, badge_label, color_hex, bg_color, symbol) 반환"""
    if auto:
        issue = state['issues'][0] if state['issues'] else {}
        sector = issue.get('sector', '시장')
        headline = issue.get('headline', '오늘의 핵심 이슈')
        insight = f"{sector} 섹터 — {headline}에 주목해요. 자동 생성 초안입니다."
        verdict = 'AUTO'
        badge_label = '자동초안'
    else:
        idx = state['selected_index'] or 0
        issue = state['issues'][idx] if state['issues'] else {}
        sector = issue.get('sector', '시장')
        verdict = state.get('verdict', 'FREE')
        reason = state.get('reason', '')

        if verdict == 'FREE':
            # 자유 텍스트 판단 — 운영자 말 그대로
            insight = reason if reason else f"{sector} — 오늘의 판단을 확인하세요."
            badge_label = sector[:8]
            return insight, badge_label, '#00e5c6', 'rgba(0,229,198,0.15)', '💬'
        else:
            pivot = issue.get('pivot_a', '') if verdict == 'A' else issue.get('pivot_b', '')
            insight = f"{sector} — {reason}." if reason else f"{sector} {pivot}으로 봐요."
            badge_label = pivot[:12]

    color_hex, bg_color, symbol = VERDICT_BADGE.get(verdict, VERDICT_BADGE['AUTO'])
    return insight, badge_label, color_hex, bg_color, symbol

def get_sector_data(state: dict, auto: bool) -> list:
    """Gemini로 선택 섹터 핵심 팩트 3개 추출"""
    from google import genai
    from google.genai import types as gtypes

    idx = 0 if auto else (state['selected_index'] or 0)
    issue = state['issues'][idx] if state['issues'] else {}
    sector = issue.get('sector', '')

    wiki_path = ROOT / 'wiki' / 'L5_섹터'
    sector_files = []
    if wiki_path.exists():
        for d in wiki_path.iterdir():
            if not d.is_dir():
                continue
            if sector in d.name:
                sector_files = list(d.glob('sector_*.md')) + list(d.glob('*index.md'))
                break

    if not sector_files:
        print(f'[card_gen] 위키 파일 없음 — 섹터: {sector}, 팩트 생략')
        return []

    content = sector_files[0].read_text(encoding='utf-8')[-3000:]
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    resp = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=f"""아래 {sector} 섹터 위키에서 오늘 가장 중요한 수치/팩트 3개를 JSON 배열로 추출하라.
형식: [{{"label":"브로드컴", "value":"-11.8%", "note":"AI 가이던스는 상향"}}]
JSON만, 3개 정확히.

{content}""",
        config=gtypes.GenerateContentConfig(temperature=0)
    )
    text = resp.text.strip()
    if '```' in text:
        text = text.split('```')[1].lstrip('json').strip()
    try:
        return json.loads(text)[:3]
    except Exception as e:
        print(f'[card_gen] Gemini 파싱 실패: {e}')
        return []

def render_html(state: dict, auto: bool) -> str:
    today = state['date'] or str(date.today())
    dt = datetime.strptime(today, '%Y-%m-%d')
    date_label = f"{dt.month}월 {dt.day}일 {'월화수목금토일'[dt.weekday()]}요일"

    insight, badge_label, color_hex, bg_color, symbol = build_insight(state, auto)
    sector_data = get_sector_data(state, auto)

    idx = 0 if auto else (state['selected_index'] or 0)
    sector = state['issues'][idx]['sector'] if state['issues'] else '시장'

    data_items_html = ''
    for d in sector_data:
        data_items_html += f"""
        <div class="data-item">
          <span class="dl">{d.get('label','')}</span>
          <span class="dv" style="color:{color_hex}">{d.get('value','')}</span>
          <span class="dn">{d.get('note','')}</span>
        </div>"""

    if not data_items_html:
        data_items_html = '<div class="data-item"><span class="dn" style="color:#64748b">위키 데이터 없음 — 섹터 파일 추가 후 재생성하세요</span></div>'

    watermark = '<div class="watermark">⚠️ 자동생성 초안</div>' if auto else ''

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#03030c;font-family:'Pretendard','Apple SD Gothic Neo',sans-serif;
     display:flex;justify-content:center;padding:24px;}}
.card{{width:800px;background:linear-gradient(160deg,#0d0d1c,#0a0a16,#080810);
       border-radius:16px;border:1px solid rgba(0,229,198,0.15);
       box-shadow:0 0 60px rgba(0,229,198,0.10),0 60px 120px rgba(0,0,0,0.8);
       overflow:hidden;position:relative;}}
.card::before{{content:'';position:absolute;top:0;left:0;right:0;height:2px;
               background:linear-gradient(90deg,transparent 5%,rgba(0,229,198,0.5) 35%,
               #00e5c6 50%,rgba(0,229,198,0.5) 65%,transparent 95%);}}
.hdr{{display:flex;justify-content:space-between;align-items:center;
      padding:18px 24px;border-bottom:1px solid rgba(255,255,255,0.06);}}
.brand{{font-size:11px;font-weight:900;letter-spacing:5px;color:#00e5c6;}}
.hdr-r{{display:flex;align-items:center;gap:10px;}}
.ch{{font-size:11px;color:#8896aa;}}
.db{{background:#00e5c6;color:#000;font-size:11px;font-weight:700;
     padding:4px 10px;border-radius:20px;}}
.body{{padding:20px 24px;display:flex;flex-direction:column;gap:16px;}}
.ib{{background:rgba(0,229,198,0.05);border-left:3px solid #00e5c6;
     border-radius:0 8px 8px 0;padding:14px 16px;}}
.ih{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}}
.il{{font-size:10px;font-weight:700;letter-spacing:3px;color:#00e5c6;}}
.vb{{font-size:11px;font-weight:700;padding:3px 10px;border-radius:12px;
     color:{color_hex};background:{bg_color};border:1px solid {color_hex}40;}}
.it{{font-size:13px;color:#ddeeff;line-height:1.75;}}
.st{{font-size:10px;font-weight:700;letter-spacing:3px;color:#8896aa;margin-bottom:10px;}}
.dg{{display:flex;flex-direction:column;gap:8px;}}
.data-item{{display:flex;align-items:center;gap:12px;padding:10px 14px;
            background:rgba(255,255,255,0.03);border-radius:8px;}}
.dl{{font-size:12px;color:#c8d8ec;font-weight:600;min-width:80px;}}
.dv{{font-size:15px;font-weight:900;}}
.dn{{font-size:11px;color:#8896aa;flex:1;}}
.watermark{{position:absolute;top:14px;right:24px;font-size:11px;color:#ffe500;
            background:rgba(255,229,0,0.1);padding:3px 8px;border-radius:8px;
            border:1px solid rgba(255,229,0,0.3);}}
.ft-bar{{padding:12px 24px;border-top:1px solid rgba(255,255,255,0.06);
         display:flex;justify-content:space-between;}}
.ft{{font-size:10px;color:#64748b;}}
</style>
</head>
<body>
<div class="card">
  {watermark}
  <div class="hdr">
    <div class="brand">STOCK BRAIN</div>
    <div class="hdr-r">
      <span class="ch">로또의 주식인사이트</span>
      <span class="db">{date_label}</span>
    </div>
  </div>
  <div class="body">
    <div class="ib">
      <div class="ih">
        <span class="il">⚡ TODAY'S 인사이트</span>
        <span class="vb">{symbol} {badge_label}</span>
      </div>
      <div class="it">{insight}</div>
    </div>
    <div>
      <div class="st">📊 {sector} 핵심 데이터</div>
      <div class="dg">{data_items_html}</div>
    </div>
  </div>
  <div class="ft-bar">
    <span class="ft">STOCK BRAIN · 로또의 주식인사이트</span>
    <span class="ft">아침 브리핑 · {today}</span>
  </div>
</div>
</body>
</html>"""

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true')
    args = parser.parse_args()

    state = load_state()
    html = render_html(state, args.auto)

    suffix = '_auto' if args.auto else ''
    fname = f"briefing_아침{suffix}_{(state['date'] or str(date.today())).replace('-','')}.html"
    out_path = OUT_DIR / fname
    OUT_DIR.mkdir(exist_ok=True)
    out_path.write_text(html, encoding='utf-8')
    print(f'[card_gen] 카드 저장: {out_path}')

    state['card_html'] = str(out_path)
    state['stage'] = 'card_done'
    save_state(state)

    import subprocess
    subprocess.Popen(['powershell', '-Command', f'Start-Process "{out_path}"'])
    print('[card_gen] 브라우저 오픈 완료')

if __name__ == '__main__':
    main()
