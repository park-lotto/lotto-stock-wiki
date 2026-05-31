"""
fetch_wisereport.py — 와이즈리포트 기업/산업 리포트 일일 수집

사용법:
  python scripts/fetch_wisereport.py              # 오늘 날짜
  python scripts/fetch_wisereport.py --date 2026-05-27
"""
import sys, re, argparse
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from datetime import date
from playwright.sync_api import sync_playwright

BASE     = Path(__file__).parent.parent
SAVE_DIR = BASE / 'raw' / 'wisereport'
SAVE_DIR.mkdir(exist_ok=True)

URL = 'https://comp.wisereport.co.kr/wiseReport/summary/ReportSummary.aspx?cn=&fmt=1'


def parse_xls(path: Path) -> list[dict]:
    """HTML-based XLS → 리스트"""
    content = path.read_bytes().decode('utf-8', errors='ignore')
    rows    = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL)
    result  = []
    for row in rows[2:]:   # 첫 2행(타이틀·헤더) 제외
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        cells = [re.sub(r'<[^>]+>', '', c).strip().replace('\xa0','') for c in cells]
        cells = [c for c in cells if c]
        if cells:
            result.append(cells)
    return result


def download_tab(page, tab_text: str, date_val: str, save_path: Path):
    if tab_text != '기업':
        page.click(f'text={tab_text}')
        page.wait_for_timeout(1000)

    # 날짜 선택
    try:
        page.select_option('select', value=date_val)
    except:
        pass
    page.click('input[value="검색"], button:has-text("검색")')
    page.wait_for_timeout(1500)

    with page.expect_download(timeout=20000) as dl_info:
        page.click('a:has-text("Excel")')
    dl = dl_info.value
    dl.save_as(str(save_path))
    return save_path


def run(target_date: str):
    date_val = target_date.replace('-', '')   # 20260527
    print(f'[wisereport] {target_date} 수집 중...')

    corp_path = SAVE_DIR / f'{target_date}_기업.xls'
    ind_path  = SAVE_DIR / f'{target_date}_산업.xls'

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx  = browser.new_context(viewport={'width':1400,'height':900}, accept_downloads=True)
        page = ctx.new_page()

        page.goto(URL, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)

        download_tab(page, '기업', date_val, corp_path)
        print(f'  ✅ 기업 {corp_path.stat().st_size//1024}KB')

        download_tab(page, '산업', date_val, ind_path)
        print(f'  ✅ 산업 {ind_path.stat().st_size//1024}KB')

        ctx.close()
        browser.close()

    # 파싱 결과 저장 (JSON)
    import json
    corp_rows = parse_xls(corp_path)
    ind_rows  = parse_xls(ind_path)

    out = {
        'date': target_date,
        'corp': corp_rows,
        'industry': ind_rows,
    }
    json_path = SAVE_DIR / f'{target_date}_parsed.json'
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  ✅ 파싱: 기업 {len(corp_rows)}건 / 산업 {len(ind_rows)}건 → {json_path.name}')

    # 텔레그램 즉시 발송
    _send_wisereport_brief(target_date, corp_rows, ind_rows)

    return json_path


def _load_env() -> dict:
    env_path = BASE / ".env"
    cfg = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def _telegram(text: str):
    import json as _json, urllib.request as _req, urllib.parse as _parse
    cfg     = _load_env()
    token   = cfg.get("BOT_TOKEN", "")
    chat_id = cfg.get("CHAT_ID", "")
    if not token or not chat_id:
        print("⚠️  텔레그램 설정 없음")
        return
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = _parse.urlencode({
            "chat_id": chat_id, "text": chunk,
            "parse_mode": "HTML", "disable_web_page_preview": "true",
        }).encode()
        try:
            with _req.urlopen(_req.Request(url, data=data), timeout=10) as r:
                res = _json.loads(r.read())
                if res.get("ok"):
                    print("✅ 텔레그램 발송")
                else:
                    print(f"❌ {res}")
        except Exception as e:
            print(f"❌ 텔레그램 실패: {e}")


def _parse_corp_row(row: list) -> dict | None:
    """
    기업 행 파싱. 실제 컬럼 구조:
    [0] 기관+애널  [1] 종목[코드]  [2] 의견변화(=▲▼/&nbsp;)
    [3] 투자의견   [4] TP변화(=▲▼) [5] TP목표가
    [6] 현재가     [7] 제목        [8] 요약
    비상장(행 짧음): [0]기관 [1]종목 [2]제목 [3]요약
    """
    if len(row) < 2:
        return None
    org   = row[0].strip()
    stock = row[1].strip()  # "현대해상[001450]"
    if len(row) < 5:        # 비상장 등 짧은 행
        return None
    op_chg = row[2].strip()   # = ▲ ▼ or &nbsp;
    opinion = row[3].strip()
    tp_chg  = row[4].strip() if len(row) > 4 else ""
    tp      = row[5].strip() if len(row) > 5 else ""
    price   = row[6].strip() if len(row) > 6 else ""
    title   = row[7].strip() if len(row) > 7 else ""

    # 종목명/코드 분리
    m = re.match(r"(.+?)\[(\d+)\]", stock)
    name = m.group(1).strip() if m else stock
    code = m.group(2) if m else ""

    # TP 상승률
    tp_rate = ""
    try:
        tp_n = int(tp.replace(",", ""))
        pr_n = int(price.replace(",", ""))
        if pr_n > 0:
            tp_rate = f"+{(tp_n/pr_n-1)*100:.0f}%"
    except:
        pass

    return {
        "org": org, "name": name, "code": code,
        "op_chg": op_chg, "opinion": opinion,
        "tp_chg": tp_chg, "tp": tp, "price": price,
        "tp_rate": tp_rate, "title": title,
    }


def _send_wisereport_brief(target_date: str, corp_rows: list, ind_rows: list):
    lines = [f"📊 <b>와이즈리포트 리포트서머리</b> — {target_date}"]
    lines.append(f"기업 {len(corp_rows)}건 / 산업 {len(ind_rows)}건")
    lines.append("")

    # 기업 파싱
    parsed = [r for row in corp_rows if (r := _parse_corp_row(row))]

    # 레이팅 상향/하향 (op_chg = ▲▼)
    rating_up   = [r for r in parsed if r["op_chg"] == "▲"]
    rating_down = [r for r in parsed if r["op_chg"] == "▼"]

    # TP 상향/하향 (tp_chg = ▲▼)
    tp_up   = [r for r in parsed if r["tp_chg"] == "▲"]
    tp_down = [r for r in parsed if r["tp_chg"] == "▼"]

    if rating_up:
        lines.append(f"<b>🔺 레이팅 상향 {len(rating_up)}건</b>")
        for r in rating_up:
            lines.append(f"  {r['name']}  {r['opinion']}  TP {r['tp']} ({r['tp_rate']})  {r['org']}")
        lines.append("")
    if rating_down:
        lines.append(f"<b>🔻 레이팅 하향 {len(rating_down)}건</b>")
        for r in rating_down:
            lines.append(f"  {r['name']}  {r['opinion']}  TP {r['tp']}  {r['org']}")
        lines.append("")
    if tp_up:
        lines.append(f"<b>📈 TP 상향 {len(tp_up)}건</b>")
        for r in tp_up:
            lines.append(f"  {r['name']}  TP↑{r['tp']} ({r['tp_rate']})  {r['org']}")
        lines.append("")
    if tp_down:
        lines.append(f"<b>📉 TP 하향 {len(tp_down)}건</b>")
        for r in tp_down:
            lines.append(f"  {r['name']}  TP↓{r['tp']}  {r['org']}")
        lines.append("")

    # 유지 종목 (op=유지, tp=유지)
    hold = [r for r in parsed if r["op_chg"] in ("=","") and r["tp_chg"] in ("=","")]
    if hold:
        lines.append(f"<b>➖ 유지 {len(hold)}건</b>")
        for r in hold:
            lines.append(f"  {r['name']}  {r['opinion']}  TP {r['tp']}  {r['org']}")
        lines.append("")

    # 산업 리포트
    if ind_rows:
        lines.append(f"<b>🏭 산업 리포트 {len(ind_rows)}건</b>")
        for row in ind_rows:
            if len(row) < 2: continue
            sector = row[1] if len(row) > 1 else ""
            title  = row[4] if len(row) > 4 else (row[2] if len(row) > 2 else "")
            org    = row[0].split("증권")[0] + "증권" if "증권" in row[0] else row[0][:6]
            lines.append(f"  [{sector}] {title[:30]}  ({org})")
        lines.append("")
    _telegram("\n".join(lines))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', default=date.today().strftime('%Y-%m-%d'))
    args = parser.parse_args()
    run(args.date)
