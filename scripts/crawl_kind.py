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


def load_managed() -> dict:
    """pipeline/투경_관리.json 읽기 → {종목명: info} 딕셔너리"""
    p = ROOT / "pipeline" / "투경_관리.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {s["name"]: s for s in data.get("managed", [])}


def get_prev_names() -> set:
    """어제 투경 목록 종목명 세트 — 오늘 신규 판별용"""
    from datetime import timedelta
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    prev_path = ROOT / "raw" / "투경" / f"투경_{yesterday}.json"
    if not prev_path.exists():
        # 어제 파일 없으면 투경현황.json의 updated가 오늘이 아닌 경우만 참고
        fb = ROOT / "raw" / "투경" / "투경현황.json"
        if fb.exists():
            data = json.loads(fb.read_text(encoding="utf-8"))
            if data.get("updated", "") != TODAY:
                return {s["name"] for s in data.get("stocks", [])}
        return set()
    prev = json.loads(prev_path.read_text(encoding="utf-8"))
    names = set()
    for items in prev.values():
        for it in items:
            names.add(it["name"])
    return names


def build_message(warn_data: dict) -> str:
    managed = load_managed()
    managed_names = set(managed.keys())
    prev_names = get_prev_names()

    # 전체 현재 투경 종목 플랫 리스트
    all_items = []
    for items in warn_data.values():
        all_items.extend(items)

    current_names = {it["name"] for it in all_items}

    # 관리 종목 중 현재 투경에 있는 것
    active_managed = [it for it in all_items if it["name"] in managed_names]
    # 관리 종목 중 해제된 것
    released = [n for n in managed_names if n not in current_names]
    # 오늘 신규 진입 = 지정일이 오늘인 것 (관리 외 종목만)
    truly_new = [it for it in all_items
                 if it.get("dsgn_dt", "")[:10] == TODAY and it["name"] not in managed_names]

    lines = [f"📋 <b>투경 관리 현황</b> — {TODAY_KR}", ""]

    # 관리 종목만 표시
    if active_managed:
        lines.append(f"<b>✅ 관리 종목 ({len(active_managed)}종목)</b>")
        for it in active_managed:
            dt = f" | 지정 {it['dsgn_dt']}" if it["dsgn_dt"] else ""
            lines.append(f"  • {it['name']}{dt}")
        lines.append("")

    # 관리 종목 해제
    if released:
        lines.append(f"<b>🎉 해제 ({len(released)}종목)</b>")
        for n in released:
            lines.append(f"  • {n}")
        lines.append("")

    # 오늘 신규 진입 종목만 — 추가 여부 질문
    if truly_new:
        lines.append(f"<b>🆕 오늘 신규 투경 ({len(truly_new)}종목) — 관리 추가하시겠어요?</b>")
        for it in truly_new:
            dt = f" | 지정 {it['dsgn_dt']}" if it["dsgn_dt"] else ""
            lines.append(f"  • {it['name']}{dt}")
        lines.append("")
        lines.append("<i>→ Claude에게 '투경 관리에 {종목명} 추가해줘' 라고 말하세요</i>")

    if not active_managed and not truly_new and not released:
        lines.append("관리 종목 이상 없음")

    return "\n".join(lines)


# ── 메인 ─────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tg", action="store_true")
    args = ap.parse_args()

    print(f"⏳ KIND 투경 종목 조회 중 ({TODAY})...")

    warn_data = {}
    from_kind = False  # KIND에서 실제 데이터를 받았는지 여부

    # 1차: API 시도
    for label, code in WARN_TYPES:
        items_raw = fetch_warn_list(code)
        items = parse_items(items_raw)
        warn_data[code] = items
        if items:
            from_kind = True
        print(f"  {label}: {len(items)}종목")

    # API가 모두 실패하면 Playwright 폴백
    total = sum(len(v) for v in warn_data.values())
    if total == 0:
        print("  → API 응답 없음. Playwright로 재시도...")
        pw_data = fetch_via_playwright()
        if pw_data:
            warn_data = pw_data
            total = sum(len(v) for v in warn_data.values())
            if total > 0:
                from_kind = True
            print(f"  → Playwright: 총 {total}종목")

    # Playwright도 실패하면 투경현황.json 폴백 (KIND 서버 다운 시)
    total = sum(len(v) for v in warn_data.values())
    if total == 0:
        fallback = ROOT / "raw" / "투경" / "투경현황.json"
        if fallback.exists():
            fb = json.loads(fallback.read_text(encoding="utf-8"))
            stocks = fb.get("stocks", [])
            fb_updated = fb.get("updated", "?")
            # warning → 0302(투자경고), risk → 0301(투자위험)으로 매핑
            warn_data = {"0301": [], "0302": [], "0303": [], "0401": []}
            for s in stocks:
                t = s.get("type", "warning")
                code = "0301" if t == "risk" else "0302"
                warn_data[code].append({
                    "name":    s["name"],
                    "code":    s.get("code", ""),
                    "dsgn_dt": s.get("des_date", ""),
                    "rls_dt":  "",
                })
            total = sum(len(v) for v in warn_data.values())
            print(f"  → KIND 서버 다운. 투경현황.json 폴백 사용 ({fb_updated} 기준, {total}종목)")

    # KIND에서 실제 데이터 받았으면 투경현황.json 자동 갱신 (폴백 데이터는 갱신 안 함)
    total = sum(len(v) for v in warn_data.values())
    if from_kind and total > 0:
        fallback = ROOT / "raw" / "투경" / "투경현황.json"
        # warn_data → stocks 형식으로 변환
        type_map = {"0301": "risk", "0302": "warning", "0303": "warning", "0401": "warning"}
        stocks = []
        for code, items in warn_data.items():
            for it in items:
                stocks.append({
                    "name":     it["name"],
                    "code":     it.get("code", ""),
                    "des_date": it.get("dsgn_dt", ""),
                    "reason":   "",
                    "warn_type": "surge",
                    "type":     type_map.get(code, "warning"),
                })
        fb_data = {"updated": TODAY, "stocks": stocks}
        fallback.write_text(json.dumps(fb_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ 투경현황.json 갱신 ({TODAY}, {len(stocks)}종목)")

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
