"""
장중 섹터흐름 체크
사용: python 장중섹터흐름.py
출력: out/장중_섹터흐름_YYYYMMDD_HHMM.html

흐름:
  Playwright → 거래대금·상승률 상위 크롤링 (ETF 전부 제외)
  Gemini     → 오늘 테마 5개 동적 분류 (MLCC/HBM소부장/LG어닝서프 등 세부)
  Gemini     → 테마별 병렬 웹리서치 (왜 오늘 오르나)
  HTML       → STOCK BRAIN 대기보드 + 특징주 맨 아래
"""
import sys, re, json, time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

ROOT  = Path(__file__).parent
OUT   = ROOT / 'out'
WIKI  = ROOT / 'wiki' / 'L5_섹터'
OUT.mkdir(exist_ok=True)

env = {}
for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip()

GEMINI_KEY = env.get('GEMINI_API_KEY', '')
TODAY = datetime.now().strftime('%Y-%m-%d')
NOW   = datetime.now().strftime('%H:%M')
FNAME = datetime.now().strftime('%Y%m%d_%H%M')

# ── ETF 브랜드 완전 차단 ──────────────────────────────────────────────────────
ETF_BRANDS = {
    'KODEX','TIGER','KBSTAR','HANARO','ARIRANG','KOSEF','RISE','ACE',
    'TIMEFOLIO','QV','PLUS','SOL','WOORI','TREX','MAPS','KTOP','SMART',
    'TRUSTON','NH','SAMSUNG','MIRAE','KB','HANWHA','IBK','SHINHAN',
}
ETF_KEYWORDS = [
    '인버스','레버리지','채권','혼합','리츠','국채','회사채',
    '단일종목','선물','ETF','ETN','지수','파생','펀드',
]

def is_etf(name: str) -> bool:
    first = name.split()[0].upper().rstrip('0123456789')
    if first in ETF_BRANDS:
        return True
    return any(k in name for k in ETF_KEYWORDS)


def parse_amount(raw: str) -> float:
    """네이버 거래대금(백만원) → 억원"""
    try:
        return round(float(raw.replace(',', '').strip()) / 100, 1)
    except Exception:
        return 0.0


# ── 1. Playwright 크롤링 ──────────────────────────────────────────────────────
def _scrape_table(page, url: str) -> list[dict]:
    page.goto(url, wait_until='domcontentloaded', timeout=30000)
    page.wait_for_timeout(2000)

    frames = page.frames
    ctx = next((f for f in frames if any(k in (f.url or '') for k in ['sise','quant','rise'])), page)

    rows = []
    for tr in ctx.query_selector_all('table.type_2 tbody tr'):
        tds = tr.query_selector_all('td')
        if len(tds) < 5:
            continue
        a = tds[1].query_selector('a') if len(tds) > 1 else None
        if not a:
            continue
        name = a.inner_text().strip()
        if not name or is_etf(name):
            continue

        def t(i): return tds[i].inner_text().strip().replace(',','').replace('+','') if len(tds) > i else '0'

        rows.append({
            'name':    name,
            'price':   t(2),
            'chg_pct': t(4).replace('%',''),
            'vol':     t(5),
            'amount':  str(parse_amount(t(6))) if len(tds) > 6 else '0',
        })
    return rows


def crawl() -> dict:
    from playwright.sync_api import sync_playwright
    print('🌐 크롤링 시작...')
    data = {'quant': [], 'rise': [], 'group': []}

    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=True)
        page = br.new_page(user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        ))

        try:
            data['quant'] = _scrape_table(page, 'https://finance.naver.com/sise/sise_quant.naver')
            print(f'  거래대금 상위 {len(data["quant"])}개 (ETF 제외)')
        except Exception as e:
            print(f'  거래대금 오류: {e}')

        try:
            data['rise'] = _scrape_table(page, 'https://finance.naver.com/sise/sise_rise.naver')
            print(f'  상승률 상위 {len(data["rise"])}개 (ETF 제외)')
        except Exception as e:
            print(f'  상승률 오류: {e}')

        try:
            page.goto('https://finance.naver.com/sise/sise_group.naver',
                      wait_until='domcontentloaded', timeout=30000)
            page.wait_for_timeout(1500)
            ctx = next((f for f in page.frames if 'group' in (f.url or '')), page)
            for tr in ctx.query_selector_all('table tbody tr'):
                tds = tr.query_selector_all('td')
                if len(tds) < 2: continue
                nm = tds[0].inner_text().strip()
                pc = tds[1].inner_text().strip().replace('%','').replace('+','')
                if nm and pc:
                    data['group'].append({'name': nm, 'chg_pct': pc})
            print(f'  업종별 {len(data["group"])}개')
        except Exception as e:
            print(f'  업종별 오류: {e}')

        br.close()
    return data


# ── 2. 복합 점수 계산 ─────────────────────────────────────────────────────────
def build_scored_list(quant: list, rise: list) -> list[dict]:
    """거래대금 순위×2 + 상승률 순위×1 → 복합 점수"""
    score: dict[str, dict] = {}
    for rank, s in enumerate(quant[:40], 1):
        nm = s['name']
        if nm not in score:
            score[nm] = {**s, 'score': 0, 'quant_rank': rank, 'rise_rank': 999}
        score[nm]['score'] += (41 - rank) * 2

    for rank, s in enumerate(rise[:40], 1):
        nm = s['name']
        if nm not in score:
            score[nm] = {**s, 'score': 0, 'quant_rank': 999, 'rise_rank': rank}
        else:
            score[nm]['rise_rank'] = rank
        score[nm]['score'] += (41 - rank)

    return sorted(score.values(), key=lambda x: x['score'], reverse=True)


# ── 3. Gemini로 테마 동적 분류 ────────────────────────────────────────────────
def classify_themes(stocks: list[dict]) -> dict:
    """
    Gemini가 오늘 장 기준으로 세부 테마 5개 + 특징주 분류
    반환: {'themes': [...], 'features': [...]}
    """
    from google import genai
    from google.genai import types

    top = stocks[:35]
    lines = []
    for s in top:
        amt = f"{s['amount']}억" if float(s.get('amount', 0)) > 0 else ''
        lines.append(f"- {s['name']}: {s['chg_pct']}% {amt}")

    stock_list = '\n'.join(lines)

    prompt = f"""오늘({TODAY}) 한국 주식시장 장중 데이터야. 거래대금·상승률 상위 개별주(ETF 없음)야.

{stock_list}

이 종목들을 오늘 "왜 같이 움직이는가" 기준으로 세부 테마 반드시 정확히 4개로 분류해줘. 억지로라도 4개 맞춰줘.

규칙:
- 반드시 Google 검색으로 오늘 뉴스 확인 후 분류
- 테마명은 반드시 8자 이내 한국어 (예: "젠슨황 방한", "HBM소부장", "MLCC급등", "조선수주")
- 각 테마 종목은 최대 3개만
- trigger는 15자 이내 핵심 한 줄
- image_query: 영어로 Pexels/Unsplash 검색어. 반드시 건물·공장·장치·제품 위주 (사람 얼굴 NO)
  좋은 예: "semiconductor factory clean room", "robot arm manufacturing", "data center server blue",
           "LG electronics headquarters building", "shipyard crane aerial view", "stock exchange floor"
  나쁜 예: "person", "man", "woman", "portrait", "face" 포함 금지
- 테마 안 묶이는 종목은 features로

JSON만 반환:
{{
  "themes": [
    {{
      "name": "8자이내",
      "stocks": ["종목1","종목2","종목3"],
      "trigger": "15자이내 핵심",
      "image_query": "building product technology NO people"
    }}
  ],
  "features": ["종목1","종목2"]
}}"""

    client = genai.Client(api_key=GEMINI_KEY)
    try:
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            )
        )
        raw = resp.text or ''
        # JSON 추출
        m = re.search(r'\{[\s\S]*\}', raw)
        if m:
            return json.loads(m.group())
    except Exception as e:
        print(f'  테마 분류 오류: {e}')

    # 폴백: 빈 구조
    return {'themes': [], 'features': [s['name'] for s in top[:10]]}


# ── 4. Playwright 네이버 이미지 검색 ─────────────────────────────────────────
# 테마 키워드 → 네이버 검색어 매핑
NAVER_QUERY_MAP = {
    '방한':    '엔비디아 AI 로봇 공장',
    '젠슨황':  '엔비디아 본사 AI 칩',
    'LG':     'LG 전자 스마트팩토리',
    '피지컬AI': '피지컬AI 로봇 공장',
    '로봇':   '산업용 로봇 팔 공장 자동화',
    '반도체':  '반도체 웨이퍼 팹 클린룸',
    'HBM':   'HBM 반도체 메모리 칩',
    'MLCC':  'MLCC 전자부품 공장',
    '클라우드': '데이터센터 서버 클라우드',
    'AI':     'AI 인공지능 서버 데이터센터',
    '조선':   '조선소 선박 크레인',
    '방산':   '방산 전투기 무기체계',
    '바이오':  '바이오 연구소 실험실',
    '플랫폼':  '테크 플랫폼 소프트웨어',
    '배터리':  '전기차 배터리 공장',
    '해운':   '컨테이너선 항만 항공뷰',
    '삼성':   '삼성전자 반도체 공장',
    '현대':   '현대차 자동차 공장',
    '전기차':  '전기차 배터리 열관리',
}

def _naver_query(theme_name: str) -> str:
    for kw, q in NAVER_QUERY_MAP.items():
        if kw in theme_name:
            return q
    return theme_name + ' 기업 기술 산업'


def download_theme_images(themes: list[dict]) -> dict[str, str]:
    """네이버 이미지 검색으로 테마 관련 이미지 다운로드"""
    import base64, urllib.request, urllib.parse

    img_dir = OUT / 'images'
    img_dir.mkdir(exist_ok=True)
    results: dict[str, str] = {}
    print('\n\U0001f4f7 네이버 이미지 검색 중...')

    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        ))

        used_paths = set()
        for th in themes:
            name  = th['name']
            query = _naver_query(name)
            safe  = re.sub(r'\W+', '_', name)[:15]
            path  = img_dir / f'{safe}.jpg'

            # 캐시
            # 중복 경로 방지: 같은 파일명이면 쿼리에 인덱스 추가
            while path in used_paths and path.exists():
                query = query + ' 2'
                safe2 = re.sub(r'\W+', '_', name + str(len(used_paths)))[:15]
                path  = img_dir / f'{safe2}.jpg'
            used_paths.add(path)

            if path.exists() and path.stat().st_size > 10000:
                with open(path, 'rb') as f:
                    data_cached = f.read()
                # 같은 이미지 데이터 중복 체크
                import hashlib
                data_hash = hashlib.md5(data_cached).hexdigest()
                if data_hash not in {hashlib.md5(open(p,'rb').read()).hexdigest() for p in used_paths if p.exists() and p != path}:
                    results[name] = f'data:image/jpeg;base64,{base64.b64encode(data_cached).decode()}'
                    print(f'  ✅ [{name}] 캐시')
                    continue
                else:
                    path.unlink()  # 중복 캐시 삭제 후 재다운로드

            done = False
            try:
                enc = urllib.parse.quote(query)
                page.goto(
                    f'https://search.naver.com/search.naver?where=image&query={enc}',
                    wait_until='domcontentloaded', timeout=20000
                )
                page.wait_for_timeout(2500)

                # 네이버 이미지 결과에서 2-4번째 이미지 (첫 번째는 광고일 수 있음)
                img_src = None
                for sel in [
                    '.img_list li:nth-child(2) img',
                    '.img_list li:nth-child(3) img',
                    '.img_list li img',
                    'img._img',
                    '.image_group img',
                    'div[class*="image"] img',
                ]:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            src = el.get_attribute('src') or el.get_attribute('data-src') or ''
                            if src.startswith('http') and ('jpg' in src.lower() or 'jpeg' in src.lower() or 'png' in src.lower() or 'image' in src.lower()):
                                img_src = src
                                break
                    except Exception:
                        continue

                # 모든 img 태그에서 큰 이미지 찾기
                if not img_src:
                    imgs = page.query_selector_all('img[src*="http"]')
                    for el in imgs:
                        src = el.get_attribute('src') or ''
                        w   = el.get_attribute('width') or '0'
                        if src.startswith('http') and int(w or 0) > 100:
                            img_src = src
                            break

                if img_src:
                    req = urllib.request.Request(img_src, headers={
                        'User-Agent': 'Mozilla/5.0',
                        'Referer': 'https://search.naver.com/'
                    })
                    with urllib.request.urlopen(req, timeout=12) as r:
                        data = r.read()
                    if len(data) > 5000:
                        path.write_bytes(data)
                        results[name] = f'data:image/jpeg;base64,{base64.b64encode(data).decode()}'
                        print(f'  ✅ [{name}] 네이버 이미지 ({query})')
                        done = True
                else:
                    print(f'  ⚠️ [{name}] 네이버 이미지 셀렉터 못 찾음')

            except Exception as e:
                print(f'  ⚠️ [{name}] 네이버 오류: {e}')

            # 폴백: picsum seed 방식
            if not done:
                try:
                    import hashlib
                    seed_str = re.sub(r'\W+', '_', query)[:25]
                    url2 = f'https://picsum.photos/seed/{seed_str}/800/320'
                    req2 = urllib.request.Request(url2, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req2, timeout=12) as r2:
                        data2 = r2.read()
                    if len(data2) > 5000:
                        path.write_bytes(data2)
                        results[name] = f'data:image/jpeg;base64,{base64.b64encode(data2).decode()}'
                        print(f'  ✅ [{name}] picsum 폴백')
                        done = True
                except Exception:
                    pass

            if not done:
                results[name] = ''
                print(f'  ❌ [{name}] 실패')

        browser.close()
    return results


def research_theme(theme: dict) -> dict:
    """Gemini Flash로 테마 급등 이유 + 주목 종목 2개 웹리서치"""
    from google import genai
    from google.genai import types

    stocks = ', '.join(theme['stocks'][:5])
    trigger = theme.get('trigger', '')

    prompt = f"""오늘({TODAY}) 한국 증시 [{theme['name']}] 테마 장중 강세.
관련 종목: {stocks}

Google로 오늘 뉴스 확인 후 아래 형식만 출력해 (다른 텍스트 절대 금지):

REASON:
(핵심 한 줄 — 날짜 절대 쓰지 마, 인물+사건만, 한글 15자 이내)
(한 줄 더 — 왜 올랐는지 결론만, 한글 15자 이내. 느낌표 OK)

PICK1_NAME: (가장 주목할 종목명)
PICK1_CODE: (6자리)
PICK1_DESC:
(오늘 뉴스 직접 연관 키워드만 — 주가/퍼센트 절대금지, 10자이내)
(두번째 뉴스 연관 키워드만 — 주가/퍼센트 절대금지, 10자이내)

PICK2_NAME: (두 번째 종목명)
PICK2_CODE: (6자리)
PICK2_DESC:
(오늘 뉴스 직접 연관 키워드만 — 주가/퍼센트 절대금지, 10자이내)
(두번째 뉴스 연관 키워드만 — 주가/퍼센트 절대금지, 10자이내)"""

    client = genai.Client(api_key=GEMINI_KEY)
    try:
        resp = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
            )
        )
        return _parse_research_v2(resp.text or '')
    except Exception as e:
        return {'reason': f'오류: {e}', 'picks': []}


def _parse_research_v2(text: str) -> dict:
    def get(tag):
        m = re.search(rf'{tag}:\s*\n?(.*?)(?=\n[A-Z1-9_]+:|$)', text, re.S)
        return m.group(1).strip() if m else ''

    picks = []
    for n in ['1', '2']:
        name = get(f'PICK{n}_NAME')
        code = get(f'PICK{n}_CODE')
        desc = get(f'PICK{n}_DESC')
        if name:
            picks.append({'name': name, 'code': code, 'desc': desc})

    return {
        'reason': get('REASON'),
        'picks':  picks,
    }


def research_all(themes: list[dict]) -> list[dict]:
    print(f'\n🤖 Gemini 병렬 리서치 ({len(themes)}테마 동시, 최대 4개)...')
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(research_theme, t): i for i, t in enumerate(themes)}
        for fut in as_completed(futures):
            i = futures[fut]
            themes[i]['research'] = fut.result()  # now a dict
            print(f'  ✅ [{themes[i]["name"]}] 완료')
    return themes


# ── 5. HTML 생성 ──────────────────────────────────────────────────────────────
# 디자인 스펙 4색만 사용
RANK_COLORS = ['#00e5c6', '#ffe500', '#ffffff', '#ff2244']
RANK_ICONS  = ['🥇', '🥈', '🥉', '🏅']

def fmt_pct(v: str) -> str:
    try:
        f = float(v)
        c = '#00ffa3' if f > 0 else '#ff2244' if f < 0 else '#8896aa'
        return f'<span style="color:{c};font-weight:800">{("+" if f>0 else "")}{f:.2f}%</span>'
    except Exception:
        return v

def stock_chips_html(names: list, scored: list, color: str) -> str:
    nm_map = {s['name']: s for s in scored}
    chips = ''
    for nm in names[:6]:
        s   = nm_map.get(nm, {})
        pct = s.get('chg_pct', '')
        try:
            f = float(pct)
            c = '#00ffa3' if f > 0 else '#ff2244' if f < 0 else '#8896aa'
            sign = '+' if f > 0 else ''
            pct_str = f'{sign}{f:.1f}%'
        except Exception:
            c = '#8896aa'; pct_str = ''
        chips += (
            f'<span class="stk-chip">'
            f'{nm}'
            f'<span class="stk-pct" style="color:{c}">{pct_str}</span>'
            f'</span>'
        )
    return chips

def pick_card_html(pick: dict, color: str, num: int) -> str:
    icon = '🎯' if num == 1 else '👀'
    code_badge = f'<span class="pick-code">{pick["code"]}</span>' if pick.get('code') else ''
    return f'''
    <div class="pick-card" style="border-left:3px solid {color}">
      <div class="pick-header">
        <span class="pick-icon">{icon}</span>
        <span class="pick-name">{pick["name"]}</span>
        {code_badge}
      </div>
      <div class="pick-desc">{pick["desc"]}</div>
    </div>'''

def feature_chips(names: list, scored: list) -> str:
    nm_map = {s['name']: s for s in scored}
    chips = ''
    for nm in names:
        s = nm_map.get(nm, {})
        pct = s.get('chg_pct', '')
        try:
            f = float(pct)
            c = '#00ffa3' if f > 0 else '#ff2244' if f < 0 else '#94a3b8'
            pct_str = f'{("+" if f>0 else "")}{f:.1f}%'
        except Exception:
            c = '#94a3b8'; pct_str = ''
        chips += f'<span class="feat-chip"><span class="feat-nm">{nm}</span><span style="color:{c}">{pct_str}</span></span>'
    return chips

def group_bar_html(groups: list) -> str:
    valid = []
    for g in groups:
        try: valid.append((g['name'], float(g['chg_pct'])))
        except Exception: pass
    valid.sort(key=lambda x: x[1], reverse=True)
    chips = ''
    for nm, v in valid[:12]:
        c = '#00ffa3' if v > 0 else '#ff2244'
        chips += f'<span class="grp-chip" style="color:{c}">{nm} {("+" if v>0 else "")}{v:.1f}%</span>'
    return chips

def generate_html(themes: list, features: list, scored: list, groups: list,
                  images: dict | None = None) -> str:
    images = images or {}
    _COLORS = ['#00e5c6', '#ffe500', '#ffffff', '#ff2244']

    cards_html = ''
    empty_pick = '<div class="pick-empty">분석 중</div>'
    for i, th in enumerate(themes[:4]):
        color = _COLORS[i]
        res   = th.get('research', {})
        if isinstance(res, str):
            res = {'reason': res, 'picks': []}
        # 이유: 2줄, 줄당 18자 하드 커팅
        raw_reason = res.get('reason', '').strip()
        reason_lines = [l.strip() for l in raw_reason.splitlines() if l.strip()]
        reason = reason_lines[0][:15] if reason_lines else ""

        picks  = res.get('picks', [])

        img_b64  = images.get(th['name'], '')
        if img_b64:
            bg_style = f'background-image:url({img_b64})'
        else:
            bg_style = 'background:linear-gradient(135deg,#0d1830 0%,#0a2040 100%)'

        chips = stock_chips_html(th['stocks'][:3], scored, color)

        picks_html = ''
        for n, p in enumerate(picks[:2]):
            p_icon = '🎯' if n == 0 else '👀'
            # desc 2줄, 줄당 16자 하드 커팅
            desc_lines = [l.strip() for l in p["desc"].splitlines() if l.strip()][:2]
            desc_lines = [("✅ " + l.lstrip("✅✔ ").strip()) for l in desc_lines]
            desc = chr(10).join(desc_lines)


            picks_html += (
                f'<div class="pick-card" style="border-top:2px solid {color}">'
                f'<div class="pick-hd">'
                f'<span class="pick-icon">{p_icon}</span>'
                f'<span class="pick-nm">{p["name"]}</span>'
                f'<span class="pick-code">{p.get("code","")}</span>'
                f'</div>'
                f'<div class="pick-desc">{desc}</div>'
                f'</div>'
            )

        cards_html += (
            f'<div class="card" style="--c:{color}">'
            f'<div class="hero" style="{bg_style}">'
            f'<div class="hero-grad"></div>'
            f'<div class="hero-content">'
            f'<div class="rank-row"><span class="rank-badge" style="background:{color};color:#001810">{i+1}위</span></div>'
            f'<div class="theme-nm">{th["name"]}</div>'
            f'<div class="stk-chips">{chips}</div>'
            f'</div></div>'
            f'<div class="reason-sec">'
            f'<span class="reason-icon" style="color:{color}">⚡</span>'
            f'<span class="reason-txt">{reason}</span>'
            f'</div>'
            f'<div class="picks-sec">'
            f'<div class="picks-row">'
            f'{picks_html or empty_pick}'
            f'</div></div>'
            f'</div>'
        )

    feat_html = ''  # 특징주 섹션 제거

    css = """
@import url('https://fonts.googleapis.com/css2?family=Jua&family=Noto+Sans+KR:wght@400;700;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#07090f;--card:#0d1020;--card2:#0f1520;
  --mint:#00e5c6;--red:#ff2244;--yellow:#ffe500;
  --t0:#ffffff;--t1:#e8f4ff;--t2:#c8d8ec;--t4:#8896aa;--t5:#64748b;
}
body{
  background:var(--bg);
  background-image:linear-gradient(rgba(0,229,198,.018) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,229,198,.018) 1px,transparent 1px);
  background-size:44px 44px;
  font-family:'Jua','Noto Sans KR',sans-serif;
  color:var(--t0);width:800px;margin:0 auto;padding:12px;
}
.wrap{background:var(--card);border-radius:18px;overflow:hidden;border:1px solid rgba(0,229,198,.15);position:relative}
.wrap::before{content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent 5%,rgba(0,229,198,.6) 30%,#00e5c6 50%,rgba(0,229,198,.6) 70%,transparent 95%)}

/* HEADER */
.hd{padding:22px 24px 20px;border-bottom:1px solid rgba(255,255,255,.07)}
.brand-row{display:flex;align-items:center;gap:7px;margin-bottom:6px}
.brand-dot{width:7px;height:7px;border-radius:50%;background:var(--mint)}
.brand-txt{font-size:9.5px;font-weight:900;letter-spacing:5px;color:var(--mint)}
.hd-main{display:flex;justify-content:space-between;align-items:flex-end}
.hd-title{font-size:44px;font-weight:900;color:var(--t0);letter-spacing:-1px;line-height:1.05}
.hl{color:var(--mint)}
.hd-date{background:var(--mint);color:#001810;font-size:12px;font-weight:900;padding:6px 16px;border-radius:20px}

/* 2x2 그리드 */
.cards{padding:12px;display:grid;grid-template-columns:1fr 1fr;gap:10px}
.card{background:var(--card2);border:1px solid rgba(255,255,255,.1);border-radius:14px;overflow:hidden;display:flex;flex-direction:column}
.card:nth-child(3):last-child{grid-column:1/-1}

/* 히어로 이미지 */
.hero{position:relative;height:133px;background-size:cover;background-position:center;flex-shrink:0}
.hero-grad{position:absolute;inset:0;
  background:linear-gradient(to bottom,rgba(0,0,0,.1) 0%,rgba(0,0,0,.65) 65%,rgba(0,0,0,.92) 100%)}
.hero-content{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:flex-end;padding:14px 16px}
.rank-row{margin-bottom:5px}
.rank-badge{font-size:10px;font-weight:900;padding:2px 10px;border-radius:12px;letter-spacing:.5px;opacity:.9}
.theme-nm{font-size:36px;font-weight:900;color:#fff;letter-spacing:-1px;margin-bottom:8px;line-height:1.1}
.stk-chips{display:flex;flex-wrap:nowrap;gap:5px;overflow:hidden;max-width:100%}
.stk-chip{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;color:#fff;padding:3px 10px;border-radius:20px;background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3);backdrop-filter:blur(4px);white-space:nowrap;flex-shrink:0}
.stk-pct{font-size:10.5px;font-weight:900}

/* 오르는 이유 */
.reason-sec{display:flex;align-items:center;gap:8px;padding:0 16px;height:54px;
  border-bottom:1px solid rgba(255,255,255,.07);flex-shrink:0}
.reason-icon{font-size:17px;flex-shrink:0;margin-top:1px}
.reason-txt{font-size:19px;font-weight:700;color:var(--t0);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1}

/* 주목 종목 */
.picks-sec{padding:9px 14px 12px}
.picks-row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.pick-card{background:rgba(0,0,0,.3);border-radius:10px;padding:10px 12px;height:90px;overflow:hidden}
.pick-hd{display:flex;align-items:center;gap:6px;margin-bottom:6px}
.pick-icon{font-size:16px}
.pick-nm{font-size:15px;font-weight:900;color:var(--t0)}
.pick-code{display:none}
.pick-desc{font-size:12.5px;color:var(--t1);line-height:1.8;white-space:pre-wrap;overflow:hidden}
.pick-empty{font-size:11px;color:var(--t5)}

/* 특징주 */
.feat-sec{grid-column:1/-1;background:var(--card2);border:1px solid rgba(255,255,255,.08);border-radius:12px;overflow:hidden}
.feat-hd{padding:8px 16px;font-size:11px;font-weight:900;color:var(--mint);background:rgba(0,0,0,.2);border-bottom:1px solid rgba(255,255,255,.05)}
.feat-sub{font-weight:400;color:var(--t4);font-size:10px}
.feat-body{padding:9px 16px;display:flex;flex-wrap:wrap;gap:6px}
.feat-chip{display:inline-flex;align-items:center;gap:5px;background:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.1);border-radius:6px;padding:4px 11px}
.feat-nm{font-size:11.5px;font-weight:700;color:var(--t0)}

/* FOOTER */
.ft{border-top:1px solid rgba(255,255,255,.06);padding:10px 22px;display:flex;justify-content:space-between;align-items:center}
.ft-brand{font-size:9.5px;font-weight:900;letter-spacing:4px;color:var(--mint)}
.ft-sub{font-size:8.5px;color:var(--t5)}
.ft-date{font-size:8.5px;font-weight:700;color:var(--t5)}
"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=800">
<title>장중 주도섹터 체크 {TODAY} {NOW}</title>
<style>{css}</style>
</head>
<body>
<div class="wrap">
  <div class="hd">
    <div class="brand-row">
      <div class="brand-dot"></div>
      <div class="brand-txt">STOCK BRAIN</div>
    </div>
    <div class="hd-main">
      <div class="hd-title">장중 <span class="hl">주도섹터</span> 체크</div>
      <div class="hd-date">{TODAY} {NOW}</div>
    </div>
  </div>
  <div class="cards">
    {cards_html}
    {feat_html}
  </div>
  <div class="ft">
    <div class="ft-brand">STOCK BRAIN</div>
    <div class="ft-sub" style="font-size:13px;font-weight:900;color:var(--mint);letter-spacing:1px">로또의 주식인사이트</div>
    <div class="ft-date">{TODAY} {NOW}</div>
  </div>
</div>
</body>
</html>"""


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    print(f'🚀 장중 섹터흐름 체크 — {TODAY} {NOW}')
    print('─' * 52)

    # 1. 크롤링
    data = crawl()

    # 2. 복합 점수 리스트
    scored = build_scored_list(data['quant'], data['rise'])
    print(f'\n📋 ETF 제외 후 유효 종목 {len(scored)}개')
    print('  거래대금·상승률 복합 상위:')
    for s in scored[:8]:
        print(f"    {s['name']:14s}  {s['chg_pct']:>7}%  {s['amount']}억")

    if not scored:
        print('\n⚠️  장 시간 확인 (09:00~15:30) 또는 크롤링 오류')
        return

    # 3. Gemini 테마 분류
    print('\n🧠 Gemini 테마 분류 중...')
    classified = classify_themes(scored)
    themes   = classified.get('themes', [])
    features = classified.get('features', [])

    print(f'  → 테마 {len(themes)}개 / 특징주 {len(features)}개')
    for t in themes:
        print(f"  [{t['name']}] {', '.join(t['stocks'][:4])}")
    if features:
        print(f"  [특징주] {', '.join(features[:6])}")

    # 4. 상위 4 테마 (2×2 그리드)
    themes = themes[:4]

    # 5. 테마별 병렬 리서치
    if themes and GEMINI_KEY:
        themes = research_all(themes)

    # 6. 정보 없는 테마 필터
    def _is_valid(th: dict) -> bool:
        res = th.get('research', {})
        if isinstance(res, str):
            return bool(res.strip()) and '정보 없음' not in res
        reason = res.get('reason', '')
        picks  = res.get('picks', [])
        if not reason or '정보 없음' in reason or '정보없음' in reason:
            return False
        if picks and '정보' in str(picks[0].get('name', '')):
            return False
        return True

    valid_themes = [t for t in themes if _is_valid(t)]
    if len(valid_themes) < len(themes):
        print(f'  ⚠️ 정보없는 테마 {len(themes)-len(valid_themes)}개 제외 → {len(valid_themes)}개 유지')
    themes = valid_themes

    if not themes:
        print('❌ 유효한 테마 없음')
        return

    # 7. 이미지 다운로드
    images = download_theme_images(themes)

    # 8. HTML 생성
    print('\n🎨 대기보드 생성 중...')
    html = generate_html(themes, features, scored, data['group'], images)
    out_path = OUT / f'장중_섹터흐름_{FNAME}.html'
    out_path.write_text(html, encoding='utf-8')
    print(f'✅ 완료: {out_path}')

    import subprocess
    subprocess.Popen(['cmd', '/c', 'start', '', str(out_path)])

    # 9. PNG 변환 (.wrap 요소만 캡처 — 여백 없음)
    print('\n🖼️  PNG 변환 중...')
    png_path = out_path.with_suffix('.png')
    try:
        from playwright.sync_api import sync_playwright as _spw
        with _spw() as pw2:
            br2  = pw2.chromium.launch()
            pg2  = br2.new_page(viewport={'width': 840, 'height': 1200})
            pg2.goto(f'file:///{out_path.resolve()}', wait_until='networkidle')
            pg2.wait_for_timeout(2000)
            wrap = pg2.query_selector('.wrap')
            wrap.screenshot(path=str(png_path))
            br2.close()
        print(f'  ✅ PNG: {png_path.name}  ({png_path.stat().st_size // 1024}KB)')
    except Exception as e:
        print(f'  ❌ PNG 변환 실패: {e}')
        png_path = None

    # 10. 텔레그램 전송
    if png_path and png_path.exists():
        print('\n📨 텔레그램 전송 중...')
        try:
            import urllib.request as _ur, json as _json
            _token   = env.get('BOT_TOKEN', '')
            _chat_id = env.get('CHAT_ID', '')
            if not _token or not _chat_id:
                print('  ⚠️  BOT_TOKEN 또는 CHAT_ID 없음 — .env 확인')
            else:
                from datetime import datetime as _dt
                _now     = _dt.now().strftime('%Y-%m-%d %H:%M')
                _caption = f'📊 장중 주도섹터 체크  {_now}\nSTOCK BRAIN | 로또의 주식인사이트'
                with open(png_path, 'rb') as _f:
                    _img = _f.read()
                _bd  = '----TGBound7MA4YWx'
                _body = (
                    f'--{_bd}\r\nContent-Disposition: form-data; name="chat_id"\r\n\r\n{_chat_id}\r\n'
                    f'--{_bd}\r\nContent-Disposition: form-data; name="caption"\r\n\r\n{_caption}\r\n'
                    f'--{_bd}\r\nContent-Disposition: form-data; name="photo"; filename="briefing.png"\r\nContent-Type: image/png\r\n\r\n'
                ).encode('utf-8') + _img + f'\r\n--{_bd}--\r\n'.encode()
                _req = _ur.Request(
                    f'https://api.telegram.org/bot{_token}/sendPhoto',
                    data=_body,
                    headers={'Content-Type': f'multipart/form-data; boundary={_bd}'}
                )
                with _ur.urlopen(_req, timeout=30) as _resp:
                    _res = _json.loads(_resp.read())
                if _res.get('ok'):
                    print('  ✅ 텔레그램 전송 완료!')
                else:
                    print(f'  ❌ 전송 실패: {_res}')
        except Exception as e:
            print(f'  ❌ 텔레그램 오류: {e}')


if __name__ == '__main__':
    main()
