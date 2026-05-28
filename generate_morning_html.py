"""
generate_morning_html.py — STOCK BRAIN 아침 브리핑 HTML 생성 (다크/화이트 2버전)

사용법:
  python generate_morning_html.py          # 두 버전 모두 생성
  python generate_morning_html.py --open   # 생성 후 브라우저 열기
"""
import sys, os, json, argparse, webbrowser
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import date, timedelta

TODAY  = date.today().strftime('%Y-%m-%d')
TODAY8 = TODAY.replace('-','')
BASE   = Path(__file__).parent
OUT    = BASE / 'out'

WD = ['월','화','수','목','금','토','일']
DATE_KR = f"{date.today().month}월 {date.today().day}일 {WD[date.today().weekday()]}요일"

# ── 섹터 카드 정의 ───────────────────────────
SECTORS = [
    ('반도체',    '🖥', 'semi'),
    ('이차전지',  '🔋', 'battery'),
    ('바이오',    '💊', 'bio'),
    ('전장·로봇', '🤖', 'robot'),
    ('방어주',    '🛡', 'defense'),
    ('에너지',    '⚡', 'energy'),
    ('건설·재건', '🏗', 'construction'),
    ('소비·내수', '🛍', 'consumer'),
]

# ── 데이터 로드 ───────────────────────────────
def load():
    bf_f = BASE / 'raw' / '미국장' / f'{TODAY}_briefing.json'
    mk_f = BASE / 'raw' / '미국장' / f'{TODAY}_market.json'
    if not bf_f.exists():
        print('❌ 브리핑 JSON 없음. morning_briefing.py 먼저 실행하세요.')
        return None, None
    bf = json.loads(bf_f.read_text(encoding='utf-8'))
    mk = json.loads(mk_f.read_text(encoding='utf-8')) if mk_f.exists() else {}
    return bf, mk

def g(d, *keys, default=0):
    for k in keys:
        if not isinstance(d, dict): return default
        d = d.get(k, default)
    return d if d is not None else default

def chg_fmt(v, sign=True):
    try:
        f = float(v)
        return f'{f:+.2f}%' if sign else f'{abs(f):.2f}%'
    except: return '—'

def arrow(v):
    try: return '▲' if float(v) > 0 else ('▼' if float(v) < 0 else '')
    except: return ''

def bullets_for(sector_key, bf):
    rows = []
    kw_map = {
        'semi':        ['반도체','필라','메모리','HBM','마이크론','엔비디아'],
        'battery':     ['이차전지','배터리','2차전지','전기차','EV','리튬'],
        'bio':         ['바이오','제약','헬스','릴리','셀트리온','녹십자'],
        'robot':       ['로봇','자동차','모빌리티','현대모비스','전장'],
        'defense':     ['방산','방어','군','한화','LIG','KAI','우주'],
        'energy':      ['에너지','전력','LNG','ESS','두산','효성','원전'],
        'construction':['건설','재건','철강','포스코','현대건설'],
        'consumer':    ['소비','화장품','유통','여행','항공','크루즈','패션'],
    }
    kws = kw_map.get(sector_key, [])
    for s in (bf.get('us_strong') or []):
        if any(k in (s.get('sector','') + s.get('reason','')) for k in kws):
            rows.append(('up', f"🇺🇸 {s.get('reason','')}"))
    for s in (bf.get('kr_strong') or []):
        if any(k in (s.get('sector','') + s.get('reason','')) for k in kws):
            rows.append(('up', f"🇰🇷 {s.get('reason','')}"))
    for s in (bf.get('us_weak') or []):
        if any(k in (s.get('sector','') + s.get('reason','')) for k in kws):
            rows.append(('dn', f"🇺🇸 {s.get('reason','')}"))
    for s in (bf.get('kr_weak') or []):
        if any(k in (s.get('sector','') + s.get('reason','')) for k in kws):
            rows.append(('dn', f"🇰🇷 {s.get('reason','')}"))
    for lk in (bf.get('korea_links') or []):
        txt = lk.get('from','') + lk.get('to','') + lk.get('comment','')
        if any(k in txt for k in kws):
            rows.append(('link', f"{lk.get('signal','🟠')} {lk.get('comment','')}"))
    if not rows:
        rows = [('mid', '모니터링 — 관련 이슈 없음')]
    return rows[:3]


# ── 스파크라인 5일 데이터 수집 ────────────────────
def fetch_sparklines():
    import yfinance as yf
    syms = {
        'dow':    '^DJI',
        'nasdaq': '^IXIC',
        'sp500':  '^GSPC',
        'phlx':   '^SOX',
    }
    result = {}
    for key, sym in syms.items():
        try:
            h = yf.Ticker(sym).history(period='7d')
            closes = [round(float(v), 2) for v in h['Close'].tail(5)]
            result[key] = closes
        except:
            result[key] = []
    return result


# ════════════════════════════════════════════════
# DARK 버전 HTML
# ════════════════════════════════════════════════
def build_dark(bf, mk, sparks=None):
    us = mk.get('us', {})
    kr = mk.get('kr', {})
    spark_js = sparks or {}

    M  = '#00FFD0'   # 민트
    M2 = 'rgba(0,255,208,0.12)'
    MB = 'rgba(0,255,208,0.07)'
    RD = '#FF4455'
    YL = '#FFD600'

    def val(key):   return g(us, key, 'price', default=0)
    def chg(key):   return g(us, key, 'chg',   default=0)
    def kchg(key):  return g(kr, key, 'chg',   default=0)

    def idx_cell(name, spark_id, v, c):
        col = M if c >= 0 else RD
        return f'''<div style="flex:1;padding:10px 8px;border-right:1px solid rgba(0,255,208,0.07);">
          <div style="font-size:10px;color:#555;font-weight:700;margin-bottom:2px;">{name}</div>
          <div id="{spark_id}" style="height:36px;"></div>
          <div style="font-size:14px;font-weight:900;color:#fff;margin-top:2px;">{v:,.2f}</div>
          <div style="font-size:11px;font-weight:700;color:{col};">{arrow(c)}{abs(c):.2f}%</div>
        </div>'''

    def stat(label, val_str, chg_v=None):
        if chg_v is not None:
            col = M if chg_v >= 0 else RD
            chg_s = f'<span style="color:{col};font-size:10px;margin-left:4px;">{arrow(chg_v)}{abs(chg_v):.2f}%</span>'
        else:
            chg_s = ''
        return f'''<div style="display:flex;justify-content:space-between;align-items:center;
            padding:5px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
          <span style="color:#555;font-size:11px;">{label}</span>
          <span style="color:#ccc;font-size:12px;font-weight:700;">{val_str}{chg_s}</span>
        </div>'''

    def sector_card(name, icon, key):
        rows = bullets_for(key, bf)
        items = ''
        for typ, txt in rows:
            dot_col = M if typ=='up' else (RD if typ=='dn' else YL)
            dot = '▲' if typ=='up' else ('▼' if typ=='dn' else '●')
            items += f'''<div style="display:flex;gap:6px;align-items:flex-start;margin-bottom:5px;">
              <span style="color:{dot_col};font-size:10px;flex-shrink:0;margin-top:2px;">{dot}</span>
              <span style="font-size:11px;color:#aaa;line-height:1.45;">{txt}</span>
            </div>'''
        return f'''<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(0,255,208,0.1);
            border-radius:14px;padding:12px;position:relative;overflow:hidden;">
          <div style="position:absolute;top:-6px;right:-4px;font-size:34px;opacity:0.07;">{icon}</div>
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
            <span style="font-size:16px;">{icon}</span>
            <span style="font-size:13px;font-weight:900;color:{M};">{name}</span>
          </div>
          {items}
        </div>'''

    # 이슈 배너
    issue_html = ''
    if bf.get('global_issue'):
        issue_html += f'''<div style="background:rgba(255,180,0,0.06);border-left:3px solid #FFB300;
            padding:8px 14px;border-radius:0 8px 8px 0;margin-bottom:6px;">
          <span style="font-size:10px;font-weight:900;color:#FFB300;margin-right:6px;">🌍 글로벌</span>
          <span style="font-size:11px;color:#bbb;">{bf['global_issue']}</span>
        </div>'''
    if bf.get('macro_issue'):
        issue_html += f'''<div style="background:rgba(0,255,208,0.04);border-left:3px solid {M};
            padding:8px 14px;border-radius:0 8px 8px 0;margin-bottom:6px;">
          <span style="font-size:10px;font-weight:900;color:{M};margin-right:6px;">⚡ 매크로</span>
          <span style="font-size:11px;color:#bbb;">{bf['macro_issue']}</span>
        </div>'''

    # 대응전략
    strategy_html = ''
    items = []
    for lk in (bf.get('korea_links') or []):
        items.append(f"{lk.get('signal','')} {lk.get('from','')} → {lk.get('to','')} &nbsp;<span style='color:#555;'>/ {lk.get('comment','')}</span>")
    if bf.get('kr_special'):
        items.append(f"📌 {bf['kr_special']}")
    for e in (bf.get('today_events') or []):
        items.append(f"🗓 {e}")
    for it in items[:6]:
        strategy_html += f'''<div style="display:flex;gap:10px;align-items:flex-start;
            padding:7px 0;border-bottom:1px solid rgba(0,255,208,0.06);">
          <span style="color:{M};font-size:13px;flex-shrink:0;">›</span>
          <span style="font-size:11.5px;color:#bbb;line-height:1.5;">{it}</span>
        </div>'''

    # 체크포인트
    check_html = ''
    cps = []
    for s in (bf.get('us_strong') or [])[:3]:
        cps.append(f"🇺🇸 {s.get('sector','')} — {s.get('reason','')}")
    for s in (bf.get('kr_strong') or [])[:3]:
        cps.append(f"🇰🇷 {s.get('sector','')} — {s.get('reason','')}")
    for cp in cps[:5]:
        check_html += f'<div style="padding:5px 0;font-size:11.5px;color:#888;border-bottom:1px solid rgba(255,255,255,0.04);">♦ {cp}</div>'

    # 섹터 카드 4×2
    cards = ''.join(sector_card(n, ic, k) for n, ic, k in SECTORS)

    wti_c = M if chg('wti') >= 0 else RD
    krw_c = M if chg('usdkrw') >= 0 else RD

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=800">
<title>STOCK BRAIN 브리핑 {TODAY}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{
    background:#03030c;
    background-image:
      linear-gradient(rgba(0,255,208,0.022) 1px,transparent 1px),
      linear-gradient(90deg,rgba(0,255,208,0.022) 1px,transparent 1px);
    background-size:48px 48px;
    font-family:'Noto Sans KR',sans-serif;
    width:800px;margin:0 auto;padding:0;
  }}
</style>
</head>
<body>
<div style="background:linear-gradient(180deg,#0d0d1c 0%,#0a0a16 55%,#080810 100%);
     border-radius:0;overflow:hidden;position:relative;">

  <!-- 상단 글로우라인 -->
  <div style="height:2px;background:linear-gradient(90deg,
    transparent 5%,rgba(0,255,208,0.45) 30%,rgba(0,255,208,1) 50%,
    rgba(0,255,208,0.45) 70%,transparent 95%);"></div>

  <!-- HEADER -->
  <div style="padding:20px 26px 16px;border-bottom:1px solid rgba(0,255,208,0.07);
              display:flex;justify-content:space-between;align-items:flex-end;">
    <div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <div style="width:6px;height:6px;background:{M};border-radius:50%;
                    box-shadow:0 0 8px {M},0 0 16px rgba(0,255,208,0.5);"></div>
        <span style="font-size:11px;font-weight:900;letter-spacing:5px;color:{M};">STOCK BRAIN</span>
      </div>
      <div style="font-size:30px;font-weight:900;color:#fff;letter-spacing:-0.5px;line-height:1;">
        모닝 <span style="color:{M};text-shadow:0 0 22px rgba(0,255,208,0.45);">브리핑</span>
      </div>
      <div style="font-size:12px;color:#555;margin-top:6px;font-weight:500;">
        {bf.get('one_line','')}
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:11px;color:#444;margin-bottom:6px;">로또의 주식인사이트</div>
      <div style="font-size:13px;font-weight:700;color:{M};background:rgba(0,255,208,0.08);
                  border:1px solid rgba(0,255,208,0.2);border-radius:20px;padding:4px 14px;">
        {DATE_KR}
      </div>
    </div>
  </div>

  <!-- 이슈 배너 -->
  {f'<div style="padding:10px 26px 0;">{issue_html}</div>' if issue_html else ''}

  <!-- 매크로 지표 -->
  <div style="padding:14px 26px;border-bottom:1px solid rgba(0,255,208,0.07);">
    <div style="display:flex;gap:10px;margin-bottom:10px;">

      <!-- WTI -->
      <div style="flex:1;background:rgba(0,255,208,0.05);border:1px solid rgba(0,255,208,0.15);
                  border-radius:12px;padding:12px 14px;">
        <div style="font-size:10px;color:#555;font-weight:700;margin-bottom:3px;">🛢 WTI 유가</div>
        <div style="font-size:24px;font-weight:900;color:#fff;">${val('wti'):.2f}</div>
        <div style="font-size:12px;font-weight:700;color:{wti_c};margin-top:2px;">
          {arrow(chg('wti'))}{abs(chg('wti')):.2f}%
        </div>
      </div>

      <!-- 달러원 -->
      <div style="flex:1;background:rgba(0,255,208,0.05);border:1px solid rgba(0,255,208,0.15);
                  border-radius:12px;padding:12px 14px;">
        <div style="font-size:10px;color:#555;font-weight:700;margin-bottom:3px;">💱 USD/KRW</div>
        <div style="font-size:24px;font-weight:900;color:#fff;">{val('usdkrw'):,.0f}<span style="font-size:13px;">원</span></div>
        <div style="font-size:12px;font-weight:700;color:{krw_c};margin-top:2px;">
          {arrow(chg('usdkrw'))}{abs(chg('usdkrw')):.2f}%
        </div>
      </div>

      <!-- 금리/VIX -->
      <div style="flex:1.3;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);
                  border-radius:12px;padding:12px 14px;">
        <div style="font-size:10px;color:#555;font-weight:700;margin-bottom:6px;">📊 주요 지표</div>
        {stat('미 10년물', f"{val('us10y'):.2f}%", chg('us10y'))}
        {stat('VIX',     f"{val('vix'):.2f}", chg('vix'))}
        {stat('DXY',     f"{val('dxy'):.2f}", chg('dxy'))}
      </div>
    </div>

    <!-- 지수 4개 + 스파크라인 -->
    <div style="display:flex;background:rgba(255,255,255,0.02);
                border:1px solid rgba(0,255,208,0.08);border-radius:12px;overflow:hidden;">
      {idx_cell('다우',    'spark-dow',    val('dow'),    chg('dow'))}
      {idx_cell('나스닥',  'spark-nasdaq', val('nasdaq'), chg('nasdaq'))}
      {idx_cell('S&P500', 'spark-sp500',  val('sp500'),  chg('sp500'))}
      {idx_cell('필라반',  'spark-phlx',   val('phlx'),   chg('phlx'))}
    </div>
  </div>

  <!-- 섹터 그리드 -->
  <div style="padding:14px 26px;">
    <div style="font-size:10px;font-weight:900;color:#444;letter-spacing:2px;margin-bottom:10px;">
      ◆ 섹터별 흐름
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;">
      {cards}
    </div>
  </div>

  <!-- 대응전략 + 체크포인트 -->
  <div style="display:grid;grid-template-columns:1.4fr 1fr;gap:12px;padding:0 26px 20px;">

    <div style="background:rgba(0,255,208,0.04);border:1px solid rgba(0,255,208,0.12);
                border-radius:14px;padding:14px;">
      <div style="font-size:12px;font-weight:900;color:{M};letter-spacing:1px;margin-bottom:8px;">
        ◆ 오늘의 대응 전략
      </div>
      {strategy_html}
    </div>

    <div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);
                border-radius:14px;padding:14px;">
      <div style="font-size:12px;font-weight:900;color:#888;letter-spacing:1px;margin-bottom:8px;">
        ◇ 오늘의 체크 포인트
      </div>
      {check_html}
      <div style="margin-top:10px;font-size:10px;color:#333;font-weight:700;text-align:center;
                  letter-spacing:2px;">STOCK BRAIN · 로또의 주식인사이트</div>
    </div>
  </div>

  <!-- FOOTER -->
  <div style="border-top:1px solid rgba(0,255,208,0.07);padding:10px 26px;
              display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:10px;color:#333;font-weight:700;letter-spacing:2px;">
      STOCK BRAIN
    </span>
    <span style="font-size:10px;color:#333;">{TODAY} 모닝 브리핑</span>
  </div>

</div>

<!-- 스파크라인 렌더링 -->
<script>
(function() {{
  var sparks = {{
    'spark-dow':    {spark_js.get('dow', [])},
    'spark-nasdaq': {spark_js.get('nasdaq', [])},
    'spark-sp500':  {spark_js.get('sp500', [])},
    'spark-phlx':   {spark_js.get('phlx', [])},
  }};
  var colors = {{
    'spark-dow':    '{M}',
    'spark-nasdaq': '{M}',
    'spark-sp500':  '{M}',
    'spark-phlx':   '{RD if chg("phlx") < 0 else M}',
  }};
  Object.keys(sparks).forEach(function(id) {{
    var el = document.getElementById(id);
    if (!el || !sparks[id].length) return;
    var c = echarts.init(el, null, {{renderer:'canvas'}});
    var data = sparks[id];
    var col  = colors[id];
    var up   = data[data.length-1] >= data[0];
    col = up ? '{M}' : '{RD}';
    c.setOption({{
      backgroundColor:'transparent',
      grid:{{left:0,right:0,top:2,bottom:2}},
      xAxis:{{type:'category',show:false}},
      yAxis:{{type:'value',show:false,scale:true}},
      series:[{{
        type:'line', data:data, smooth:true, symbol:'none',
        lineStyle:{{color:col, width:1.5}},
        areaStyle:{{color:{{
          type:'linear',x:0,y:0,x2:0,y2:1,
          colorStops:[
            {{offset:0, color:col+'55'}},
            {{offset:1, color:col+'00'}},
          ]
        }}}},
      }}]
    }});
  }});
}})();
</script>
</body></html>'''


# ════════════════════════════════════════════════
# WHITE 버전 HTML
# ════════════════════════════════════════════════
def build_white(bf, mk):
    us = mk.get('us', {})
    kr = mk.get('kr', {})

    M  = '#00C8A0'   # 화이트 배경용 민트 (살짝 어둡게)
    ML = '#E6FFF8'   # 민트 라이트
    MB = '#CCF7EC'   # 민트 보더
    RD = '#E53935'
    YL = '#F57F17'

    def val(key): return g(us, key, 'price', default=0)
    def chg(key): return g(us, key, 'chg',   default=0)

    def idx_cell(name, v, c):
        col = M if c >= 0 else RD
        return f'''<div style="flex:1;text-align:center;padding:10px 4px;
            border-right:1px solid #f0f0f0;">
          <div style="font-size:10px;color:#999;font-weight:700;margin-bottom:3px;">{name}</div>
          <div style="font-size:15px;font-weight:900;color:#1a1a2e;">{v:,.2f}</div>
          <div style="font-size:12px;font-weight:700;color:{col};">{arrow(c)}{abs(c):.2f}%</div>
        </div>'''

    def stat(label, val_str, chg_v=None):
        if chg_v is not None:
            col = M if chg_v >= 0 else RD
            chg_s = f'<span style="color:{col};font-size:10px;margin-left:4px;">{arrow(chg_v)}{abs(chg_v):.2f}%</span>'
        else:
            chg_s = ''
        return f'''<div style="display:flex;justify-content:space-between;align-items:center;
            padding:5px 0;border-bottom:1px solid #f5f5f5;">
          <span style="color:#999;font-size:11px;">{label}</span>
          <span style="color:#333;font-size:12px;font-weight:700;">{val_str}{chg_s}</span>
        </div>'''

    def sector_card(name, icon, key):
        rows = bullets_for(key, bf)
        items = ''
        for typ, txt in rows:
            dot_col = M if typ=='up' else (RD if typ=='dn' else YL)
            dot = '▲' if typ=='up' else ('▼' if typ=='dn' else '●')
            items += f'''<div style="display:flex;gap:6px;align-items:flex-start;margin-bottom:5px;">
              <span style="color:{dot_col};font-size:10px;flex-shrink:0;margin-top:2px;">{dot}</span>
              <span style="font-size:11px;color:#555;line-height:1.45;">{txt}</span>
            </div>'''
        return f'''<div style="background:#FAFFFE;border:1.5px solid {MB};
            border-radius:14px;padding:12px;position:relative;overflow:hidden;">
          <div style="position:absolute;top:-6px;right:-4px;font-size:34px;opacity:0.06;">{icon}</div>
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">
            <span style="font-size:16px;">{icon}</span>
            <span style="font-size:13px;font-weight:900;color:{M};">{name}</span>
          </div>
          {items}
        </div>'''

    # 이슈 배너
    issue_html = ''
    if bf.get('global_issue'):
        issue_html += f'''<div style="background:#FFF8E1;border-left:3px solid #FFB300;
            padding:8px 14px;border-radius:0 8px 8px 0;margin-bottom:6px;">
          <span style="font-size:10px;font-weight:900;color:#F57F17;margin-right:6px;">🌍 글로벌</span>
          <span style="font-size:11px;color:#666;">{bf['global_issue']}</span>
        </div>'''
    if bf.get('macro_issue'):
        issue_html += f'''<div style="background:{ML};border-left:3px solid {M};
            padding:8px 14px;border-radius:0 8px 8px 0;margin-bottom:6px;">
          <span style="font-size:10px;font-weight:900;color:{M};margin-right:6px;">⚡ 매크로</span>
          <span style="font-size:11px;color:#666;">{bf['macro_issue']}</span>
        </div>'''

    # 대응전략
    strategy_html = ''
    items = []
    for lk in (bf.get('korea_links') or []):
        items.append(f"{lk.get('signal','')} {lk.get('from','')} → {lk.get('to','')} &nbsp;<span style='color:#aaa;'>/ {lk.get('comment','')}</span>")
    if bf.get('kr_special'):
        items.append(f"📌 {bf['kr_special']}")
    for e in (bf.get('today_events') or []):
        items.append(f"🗓 {e}")
    for it in items[:6]:
        strategy_html += f'''<div style="display:flex;gap:10px;align-items:flex-start;
            padding:7px 0;border-bottom:1px solid #edfaf6;">
          <span style="color:{M};font-size:13px;flex-shrink:0;">›</span>
          <span style="font-size:11.5px;color:#444;line-height:1.5;">{it}</span>
        </div>'''

    check_html = ''
    cps = []
    for s in (bf.get('us_strong') or [])[:3]:
        cps.append(f"🇺🇸 {s.get('sector','')} — {s.get('reason','')}")
    for s in (bf.get('kr_strong') or [])[:3]:
        cps.append(f"🇰🇷 {s.get('sector','')} — {s.get('reason','')}")
    for cp in cps[:5]:
        check_html += f'<div style="padding:5px 0;font-size:11.5px;color:#666;border-bottom:1px solid #f5f5f5;">♡ {cp}</div>'

    cards = ''.join(sector_card(n, ic, k) for n, ic, k in SECTORS)

    wti_c = M if chg('wti') >= 0 else RD
    krw_c = M if chg('usdkrw') >= 0 else RD

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=800">
<title>STOCK BRAIN 브리핑 {TODAY}</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
  *{{margin:0;padding:0;box-sizing:border-box;}}
  body{{
    background:#F0FFF8;
    font-family:'Noto Sans KR',sans-serif;
    width:800px;margin:0 auto;padding:0;
  }}
</style>
</head>
<body>
<div style="background:#ffffff;border-radius:0;overflow:hidden;">

  <!-- 상단 민트 라인 -->
  <div style="height:4px;background:linear-gradient(90deg,
    {M} 0%,#00FFD0 50%,{M} 100%);"></div>

  <!-- HEADER -->
  <div style="background:linear-gradient(135deg,#006655 0%,#009977 50%,#00C8A0 100%);
              padding:20px 26px 16px;display:flex;justify-content:space-between;align-items:flex-end;">
    <div>
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
        <div style="width:6px;height:6px;background:white;border-radius:50%;
                    box-shadow:0 0 8px rgba(255,255,255,0.8);"></div>
        <span style="font-size:11px;font-weight:900;letter-spacing:5px;color:rgba(255,255,255,0.8);">STOCK BRAIN</span>
      </div>
      <div style="font-size:30px;font-weight:900;color:#fff;letter-spacing:-0.5px;line-height:1;">
        모닝 <span style="color:#CCFFE8;">브리핑</span>
      </div>
      <div style="font-size:12px;color:rgba(255,255,255,0.7);margin-top:6px;font-weight:500;">
        {bf.get('one_line','')}
      </div>
    </div>
    <div style="text-align:right;">
      <div style="font-size:11px;color:rgba(255,255,255,0.6);margin-bottom:6px;">로또의 주식인사이트</div>
      <div style="font-size:13px;font-weight:700;color:#fff;background:rgba(255,255,255,0.2);
                  border:1px solid rgba(255,255,255,0.3);border-radius:20px;padding:4px 14px;">
        {DATE_KR}
      </div>
    </div>
  </div>

  {f'<div style="padding:10px 26px 0;">{issue_html}</div>' if issue_html else ''}

  <!-- 매크로 -->
  <div style="padding:14px 26px;background:#FAFFFE;border-bottom:1px solid #edf9f5;">
    <div style="display:flex;gap:10px;margin-bottom:10px;">
      <div style="flex:1;background:{ML};border:1.5px solid {MB};border-radius:12px;padding:12px 14px;">
        <div style="font-size:10px;color:#888;font-weight:700;margin-bottom:3px;">🛢 WTI 유가</div>
        <div style="font-size:24px;font-weight:900;color:#1a1a2e;">${val('wti'):.2f}</div>
        <div style="font-size:12px;font-weight:700;color:{wti_c};margin-top:2px;">
          {arrow(chg('wti'))}{abs(chg('wti')):.2f}%
        </div>
      </div>
      <div style="flex:1;background:{ML};border:1.5px solid {MB};border-radius:12px;padding:12px 14px;">
        <div style="font-size:10px;color:#888;font-weight:700;margin-bottom:3px;">💱 USD/KRW</div>
        <div style="font-size:24px;font-weight:900;color:#1a1a2e;">{val('usdkrw'):,.0f}<span style="font-size:13px;">원</span></div>
        <div style="font-size:12px;font-weight:700;color:{krw_c};margin-top:2px;">
          {arrow(chg('usdkrw'))}{abs(chg('usdkrw')):.2f}%
        </div>
      </div>
      <div style="flex:1.3;background:#fff;border:1px solid #eee;border-radius:12px;padding:12px 14px;">
        <div style="font-size:10px;color:#888;font-weight:700;margin-bottom:6px;">📊 주요 지표</div>
        {stat('미 10년물', f"{val('us10y'):.2f}%", chg('us10y'))}
        {stat('VIX',     f"{val('vix'):.2f}",  chg('vix'))}
        {stat('DXY',     f"{val('dxy'):.2f}",  chg('dxy'))}
      </div>
    </div>
    <div style="display:flex;background:#fff;border:1.5px solid {MB};border-radius:12px;overflow:hidden;">
      {idx_cell('다우',    val('dow'),    chg('dow'))}
      {idx_cell('나스닥',  val('nasdaq'), chg('nasdaq'))}
      {idx_cell('S&P500', val('sp500'),  chg('sp500'))}
      <div style="flex:1;text-align:center;padding:10px 4px;">
        <div style="font-size:10px;color:#999;font-weight:700;margin-bottom:3px;">필라반</div>
        <div style="font-size:15px;font-weight:900;color:#1a1a2e;">{val('phlx'):,.2f}</div>
        <div style="font-size:12px;font-weight:700;color:{M if chg('phlx')>=0 else RD};">
          {arrow(chg('phlx'))}{abs(chg('phlx')):.2f}%
        </div>
      </div>
    </div>
  </div>

  <!-- 섹터 그리드 -->
  <div style="padding:14px 26px;">
    <div style="font-size:10px;font-weight:900;color:{M};letter-spacing:2px;margin-bottom:10px;">
      ◆ 섹터별 흐름
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;">
      {cards}
    </div>
  </div>

  <!-- 대응전략 + 체크포인트 -->
  <div style="display:grid;grid-template-columns:1.4fr 1fr;gap:12px;padding:0 26px 20px;">
    <div style="background:{ML};border:1.5px solid {MB};border-radius:14px;padding:14px;">
      <div style="font-size:12px;font-weight:900;color:{M};letter-spacing:1px;margin-bottom:8px;">
        ◆ 오늘의 대응 전략
      </div>
      {strategy_html}
    </div>
    <div style="background:#FAFAFA;border:1px solid #eee;border-radius:14px;padding:14px;">
      <div style="font-size:12px;font-weight:900;color:#888;letter-spacing:1px;margin-bottom:8px;">
        ◇ 오늘의 체크 포인트
      </div>
      {check_html}
      <div style="margin-top:10px;font-size:10px;color:{M};font-weight:700;text-align:center;letter-spacing:2px;">
        STOCK BRAIN · 로또의 주식인사이트
      </div>
    </div>
  </div>

  <!-- FOOTER -->
  <div style="background:linear-gradient(135deg,#006655,#009977);
              padding:10px 26px;display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:10px;color:rgba(255,255,255,0.7);font-weight:700;letter-spacing:2px;">STOCK BRAIN</span>
    <span style="font-size:10px;color:rgba(255,255,255,0.5);">{TODAY} 모닝 브리핑</span>
  </div>
</div>
</body></html>'''


# ════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()

    bf, mk = load()
    if bf is None: return

    OUT.mkdir(exist_ok=True)
    print(f'[{TODAY}] HTML 브리핑 생성 중...')
    print('스파크라인 5일 데이터 수집 중...')
    sparks = fetch_sparklines()
    print(f'  다우 {len(sparks.get("dow",[]))}일  나스닥 {len(sparks.get("nasdaq",[]))}일  S&P {len(sparks.get("sp500",[]))}일  필라반 {len(sparks.get("phlx",[]))}일')

    dark_path  = OUT / f'morning_dark_{TODAY}.html'
    white_path = OUT / f'morning_white_{TODAY}.html'

    dark_path.write_text(build_dark(bf, mk, sparks),  encoding='utf-8')
    white_path.write_text(build_white(bf, mk), encoding='utf-8')

    print(f'✅ 다크버전:  {dark_path}')
    print(f'✅ 화이트버전: {white_path}')

    if args.open:
        webbrowser.open(str(dark_path))
        webbrowser.open(str(white_path))

if __name__ == '__main__':
    main()
