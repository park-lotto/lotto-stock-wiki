"""
crawl_kind.py — KIND(한국거래소 공시) 투자경고/투자주의 종목 매일 크롤링

사용법:
    python scripts/crawl_kind.py          # 출력만
    python scripts/crawl_kind.py --tg     # 텔레그램 전송

KIND URL: https://kind.krx.co.kr/investwarn/investwarning.do
"""

import sys, json, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT  = Path(__file__).parent.parent
TODAY = datetime.today().strftime("%Y-%m-%d")
TODAY_KR = datetime.today().strftime("%Y년 %m월 %d일")

# ── 투경 데이터 크롤링 ──────────────────────────────────────────

KIND_API = "https://kind.krx.co.kr/investwarn/investwarning.do"
KIND_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://kind.krx.co.kr/investwarn/investwarning.do",
    "Content-Type": "application/x-www-form-urlencoded",
}

WARN_TYPES = [
    ("투자위험",   "0301"),  # 투자위험종목 (가장 강함)
    ("투자경고",   "0302"),  # 투자경고종목
    ("투자주의",   "0303"),  # 투자주의종목
    ("단기과열",   "0401"),  # 단기과열종목
]

def fetch_warn_list(warn_code: str) -> list:
    """KIND API로 투경 종목 목록 가져오기"""
    params = urllib.parse.urlencode({
        "method":   "searchInvestWarningList",
        "pageIndex": "1",
        "pageSize":  "100",
        "marketType": "",
        "warnType":  warn_code,
        "stockName": "",
    })
    url = f"{KIND_API}?{params}"
    try:
        req = urllib.request.Request(url, headers=KIND_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw)
            items = data.get("result", data.get("list", []))
            if isinstance(items, list):
                return items
    except Exception as e:
        print(f"  ⚠️ {warn_code} 조회 실패: {e}")
    return []


def parse_items(items: list) -> list:
    """종목 정보 파싱"""
    result = []
    for it in items:
        name     = it.get("isu_nm") or it.get("stockName") or it.get("isuNm", "")
        code     = it.get("isu_cd") or it.get("stockCode") or it.get("isuCd", "")
        dt_str   = it.get("dsgn_dt") or it.get("designDate") or it.get("dsgnDt", "")
        release  = it.get("rls_dt")  or it.get("releaseDate") or ""
        if name:
            result.append({
                "name":    name.strip(),
                "code":    str(code).strip(),
                "dsgn_dt": dt_str[:10] if dt_str else "",
                "rls_dt":  release[:10] if release else "",
            })
    return result


# ── Playwright 방식 (API 실패 시 폴백) ────────────────────────────

def fetch_via_playwright() -> dict:
    """Playwright로 KIND 투자경고 페이지 스크래핑"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {}

    results = {code: [] for _, code in WARN_TYPES}
    BASE = "https://kind.krx.co.kr"

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--lang=ko-KR"])
            ctx = browser.new_context(locale="ko-KR")
            page = ctx.new_page()

            for label, code in WARN_TYPES:
                try:
                    # POST로 데이터 요청
                    resp = page.request.post(
                        f"{BASE}/investwarn/investwarning.do",
                        form={
                            "method":    "searchInvestWarningList",
                            "warnType":  code,
                            "pageIndex": "1",
                            "pageSize":  "200",
                            "marketType": "",
                            "stockName": "",
                        },
                        headers={"Referer": f"{BASE}/investwarn/investwarning.do"},
                        timeout=15000,
                    )
                    if resp.ok:
                        try:
                            data = resp.json()
                            raw = data.get("result") or data.get("list") or []
                            results[code] = parse_items(raw)
                            continue
                        except:
                            pass

                    # 폴백: GET 페이지 파싱
                    page.goto(
                        f"{BASE}/investwarn/investwarning.do?method=searchInvestWarningMain&warnType={code}",
                        wait_until="domcontentloaded", timeout=20000
                    )
                    page.wait_for_timeout(1500)
                    items = []
                    for row in page.query_selector_all("table.tbl_st tbody tr, table tbody tr"):
                        tds = row.query_selector_all("td")
                        if len(tds) < 3: continue
                        name = tds[1].inner_text().strip() if len(tds)>1 else ""
                        dt   = tds[3].inner_text().strip() if len(tds)>3 else ""
                        if name and not name.startswith("조회"):
                            items.append({"name": name, "code": "", "dsgn_dt": dt, "rls_dt": ""})
                    results[code] = items

                except Exception as e2:
                    print(f"    {label} 실패: {e2}")

            browser.close()
    except Exception as e:
        print(f"  ⚠️ Playwright 실패: {e}")
    return results


# ── 텔레그램 ──────────────────────────────────────────────────

def send_tg(text: str):
    env = {}
    ep = ROOT / ".env"
    if ep.exists():
        for line in ep.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    token, chat_id = env.get("BOT_TOKEN",""), env.get("CHAT_ID","")
    if not token or not chat_id:
        print("  ⚠️  .env BOT_TOKEN/CHAT_ID 없음"); return
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        url  = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id, "text": chunk,
            "parse_mode": "HTML", "disable_web_page_preview": "true"
        }).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as r:
                res = json.loads(r.read())
                if res.get("ok"):
                    print("  ✅ 텔레그램 발송")
                else:
                    print(f"  ❌ {res}")
        except Exception as e:
            print(f"  ❌ 발송 실패: {e}")


def build_message(warn_data: dict) -> str:
    lines = [
        f"⚠️ <b>투자경고/주의 종목</b> — {TODAY_KR}",
        f"<i>출처: KIND(한국거래소 공시)</i>",
        "",
    ]
    for label, code in WARN_TYPES:
        items = warn_data.get(code, [])
        if not items: continue
        icon = "🚨" if code in ("0301","0302") else "⚡"
        lines.append(f"<b>{icon} {label} ({len(items)}종목)</b>")
        for it in items[:15]:
            dt  = f" ({it['dsgn_dt']})" if it["dsgn_dt"] else ""
            rls = f" → 해제{it['rls_dt']}" if it["rls_dt"] else ""
            lines.append(f"  • {it['name']}{dt}{rls}")
        lines.append("")
    return "\n".join(lines)


# ── 메인 ─────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tg", action="store_true")
    args = ap.parse_args()

    print(f"⏳ KIND 투경 종목 조회 중 ({TODAY})...")

    warn_data = {}
    api_ok = False

    # 1차: API 시도
    for label, code in WARN_TYPES:
        items_raw = fetch_warn_list(code)
        items = parse_items(items_raw)
        warn_data[code] = items
        if items:
            api_ok = True
        print(f"  {label}: {len(items)}종목")

    # API가 모두 실패하면 Playwright 폴백
    total = sum(len(v) for v in warn_data.values())
    if total == 0:
        print("  → API 응답 없음. Playwright로 재시도...")
        pw_data = fetch_via_playwright()
        if pw_data:
            warn_data = pw_data
            total = sum(len(v) for v in warn_data.values())
            print(f"  → Playwright: 총 {total}종목")

    # 출력
    print(f"\n{'='*50}")
    for label, code in WARN_TYPES:
        items = warn_data.get(code, [])
        if not items: continue
        print(f"\n{'🚨' if code in ('0301','0302') else '⚡'} {label} ({len(items)}종목)")
        for it in items[:10]:
            print(f"  {it['name']}  {it['dsgn_dt']}")

    # raw 저장
    out = ROOT / "raw" / "투경"
    out.mkdir(exist_ok=True)
    save_path = out / f"투경_{TODAY}.json"
    save_path.write_text(json.dumps(warn_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 저장: {save_path.name}")

    if args.tg:
        msg = build_message(warn_data)
        print("\n📲 텔레그램 발송 중...")
        send_tg(msg)


if __name__ == "__main__":
    main()
