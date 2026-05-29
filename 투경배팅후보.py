"""
투경배팅후보.py — 투경 해제 임박 × 수급 빈집 종가배팅 후보

두 조건의 교집합만 후보로 선정:
  ① 투경 해제 임박: 3조건 해소(can_release) or ①② 해소
  ② 수급 빈집: 오실레이터 A/B 등급

사용법:
  python 투경배팅후보.py 080220 2026-05-14 007810 2026-05-14 [--tg]
"""
import sys, argparse, importlib.util, urllib.request, urllib.parse, json
from pathlib import Path
from datetime import date

sys.stdout.reconfigure(encoding='utf-8')

BASE         = Path(__file__).parent
TODAY        = date.today().strftime('%Y-%m-%d')
투경현황_JSON = BASE / 'raw' / '투경' / '투경현황.json'

GRADE_ICON = {'A 완전빈집': '🔴', 'B 반빈집': '🟠', 'C 정상': '⚪', 'D 과매수': '🟡'}


# ── 모듈 동적 로드 ───────────────────────────────────────────────
def _load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, BASE / filename)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 오실레이터 체크 ──────────────────────────────────────────────
def check_oscillator(names: list[str]) -> dict[str, dict | None]:
    """종목명 리스트 → {종목명: {grade, pct, trend, osc}} or None"""
    import win32com.client as win32
    osc = _load_module('calc_oscillator', 'calc_oscillator.py')

    xlsm_path = osc.find_xlsm()
    print(f"  xlsm: {xlsm_path.name}")

    xl = win32.Dispatch('Excel.Application')
    xl.Visible = False
    xl.AutomationSecurity = 3
    wb = xl.Workbooks.Open(str(xlsm_path))

    ws_osc  = wb.Sheets('수급오실레이터')
    ws_forn = wb.Sheets('외국인매수데이터')
    ws_inst = wb.Sheets('기관매수데이터')
    ws_size = wb.Sheets('시가총액')

    p90 = ws_osc.Cells(osc.STAT_ROW_P90, osc.STAT_COL).Value2
    p75 = ws_osc.Cells(osc.STAT_ROW_P75, osc.STAT_COL).Value2
    p25 = ws_osc.Cells(osc.STAT_ROW_P25, osc.STAT_COL).Value2
    p10 = ws_osc.Cells(osc.STAT_ROW_P10, osc.STAT_COL).Value2

    max_col   = ws_forn.UsedRange.Columns.Count
    xl_stocks = {}
    for c in range(2, max_col + 1):
        n = ws_forn.Cells(9, c).Value2
        if n:
            xl_stocks[n] = c

    mat_size, mat_forn, mat_inst = osc.load_bulk(ws_size, ws_forn, ws_inst, max_col)
    wb.Close(False)
    xl.Quit()

    results = {}
    for name in names:
        col = xl_stocks.get(name)
        if not col:
            # 부분 매칭
            col = next((xl_stocks[k] for k in xl_stocks if name in k or k in name), None)
        if not col:
            print(f"    ⚠️ {name}: xlsm에 없음")
            results[name] = None
            continue

        r = osc.compute_stock_bulk(col, mat_size, mat_forn, mat_inst)
        if not r:
            results[name] = None
            continue

        v = r['latest']
        results[name] = {
            'grade': osc.grade(v, p10, p25, p75),
            'pct':   osc.pct_from_thresholds(v, p10, p25, p75, p90),
            'trend': osc.trend_str(r['series']),
            'osc':   v,
        }
    return results


# ── 텔레그램 ─────────────────────────────────────────────────────
def _load_env() -> dict:
    cfg = {}
    env = BASE / '.env'
    if env.exists():
        for line in env.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                cfg[k.strip()] = v.strip()
    return cfg


def send_telegram(text: str):
    cfg = _load_env()
    token, chat_id = cfg.get('BOT_TOKEN', ''), cfg.get('CHAT_ID', '')
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


def build_tg(candidates: list[dict], excluded: list[dict]) -> str:
    lines = [f'🎯 <b>종가배팅 후보</b>  {TODAY}', '']

    if candidates:
        for e in candidates:
            icon   = '🟢' if e['can_release'] else '🔥'
            osc    = e['osc']
            g_icon = GRADE_ICON.get(osc['grade'], '') if osc else '❓'
            lines.append(f"{icon} <b>{e['name']}</b> ({e['code']}) [{e['market']}]")
            lines.append(f"  투경: {e['verdict']}")
            if osc:
                lines.append(
                    f"  수급: {g_icon} {osc['grade']}  "
                    f"하위{osc['pct']:.1f}%  {osc['trend']}")
            lines.append(f"  📌 {e['condition_line']}")
            lines.append('')
    else:
        lines.append('  ❌ 해제 임박 + 빈집 교집합 없음')
        lines.append('')

    if excluded:
        lines.append('── 빈집 미충족 (제외) ──')
        for e in excluded:
            osc = e['osc']
            if osc:
                g_icon = GRADE_ICON.get(osc['grade'], '')
                lines.append(
                    f"  {g_icon} {e['name']} ({e['code']}): "
                    f"{osc['grade']}  하위{osc['pct']:.1f}%")
            else:
                lines.append(f"  ❓ {e['name']} ({e['code']}): xlsm 데이터 없음")

    return '\n'.join(lines)


# ── 메인 ─────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='투경배팅후보 — 투경 해제 임박 × 수급 빈집',
        epilog='예) python 투경배팅후보.py 080220 2026-05-14 007810 2026-05-14'
    )
    parser.add_argument('stocks', nargs='*',
                        help='종목코드 지정일 쌍  예: 080220 2026-05-14')
    parser.add_argument('--tg', action='store_true', help='텔레그램 전송')
    args = parser.parse_args()

    tokens = args.stocks

    if not tokens:
        # 인자 없으면 투경현황.json 자동 로드
        if not 투경현황_JSON.exists():
            print(f'오류: {투경현황_JSON} 없음. 종목을 직접 입력하거나 파일을 생성하세요.')
            sys.exit(1)
        with open(투경현황_JSON, encoding='utf-8') as f:
            data = json.load(f)
        targets = [(s['code'], s['des_date']) for s in data['stocks']]
        print(f"투경현황.json 로드 ({data['updated']} 기준, {len(targets)}종목)")
    else:
        if len(tokens) % 2 != 0:
            print('오류: 종목코드와 지정일을 쌍으로 입력하세요')
            sys.exit(1)
        targets = [(tokens[i], tokens[i + 1]) for i in range(0, len(tokens), 2)]

    # ── 투경 분석 ──────────────────────────────────────────────
    mod = _load_module('fetch_투경', 'fetch_투경.py')

    print(f'\n[{TODAY}] 투경배팅후보 분석  ({len(targets)}종목)')
    print('─' * 40)
    print('① 투경 조건 분석 중...')

    투경_res = {}
    for code, des_date in targets:
        r = mod.analyze(code, des_date)
        투경_res[code] = r
        icon = ('🟢' if r.get('can_release')
                else '🔥' if (r.get('cond1_ok') and r.get('cond2_ok'))
                else '🔴')
        print(f'   {icon} {r["name"]} ({code})')

    # ── 해제 임박 필터 ─────────────────────────────────────────
    eligible = {
        code: r for code, r in 투경_res.items()
        if r.get('eligible') and (
            r.get('can_release') or
            (r.get('cond1_ok') and r.get('cond2_ok'))
        )
    }

    if not eligible:
        print('\n해제 임박 종목 없음 → 종가배팅 후보 없음')
        return

    # ── 오실레이터 체크 ────────────────────────────────────────
    print(f'\n② 오실레이터 체크 ({len(eligible)}종목) — Excel 열기 중...')
    names = [r['name'] for r in eligible.values()]
    try:
        osc_res = check_oscillator(names)
    except Exception as e:
        print(f'   오실레이터 로드 실패: {e}')
        osc_res = {name: None for name in names}

    # ── 후보 선별 ─────────────────────────────────────────────
    candidates, excluded = [], []

    for code, tr in eligible.items():
        name    = tr['name']
        osc     = osc_res.get(name)
        is_빈집 = bool(osc and osc['grade'] in ('A 완전빈집', 'B 반빈집'))
        entry   = {
            'code': code, 'name': name, 'market': tr['market'],
            'can_release':    tr.get('can_release', False),
            'verdict':        tr.get('verdict', ''),
            'condition_line': tr.get('condition_line', ''),
            'osc': osc,
        }
        (candidates if is_빈집 else excluded).append(entry)

    # ── 콘솔 출력 ─────────────────────────────────────────────
    print(f"\n{'━'*52}")
    print(f"  🎯 종가배팅 후보  ({TODAY})")
    print(f"{'━'*52}")

    if candidates:
        for e in candidates:
            icon   = '🟢' if e['can_release'] else '🔥'
            osc    = e['osc']
            g_icon = GRADE_ICON.get(osc['grade'], '') if osc else '❓'
            print(f"\n{icon} {e['name']} ({e['code']}) [{e['market']}]")
            print(f"  투경: {e['verdict']}")
            if osc:
                print(f"  수급: {g_icon} {osc['grade']}  "
                      f"하위{osc['pct']:.1f}%  {osc['trend']}")
            print(f"  📌 {e['condition_line']}")
    else:
        print('\n  해제 임박 + 빈집 교집합 없음')
        print('  → 오늘 종가배팅 후보 없음')

    if excluded:
        print(f"\n{'─'*40}")
        print('  빈집 미충족 (제외)')
        for e in excluded:
            osc = e['osc']
            if osc:
                g_icon = GRADE_ICON.get(osc['grade'], '')
                print(f"  {g_icon} {e['name']} ({e['code']}): "
                      f"{osc['grade']}  하위{osc['pct']:.1f}%")
            else:
                print(f"  ❓ {e['name']} ({e['code']}): xlsm 데이터 없음")

    # ── 텔레그램 ─────────────────────────────────────────────
    if args.tg:
        print()
        send_telegram(build_tg(candidates, excluded))


if __name__ == '__main__':
    main()
