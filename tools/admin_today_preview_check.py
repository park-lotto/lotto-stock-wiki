"""관리자 화면 고객·결제 표 '오늘만 미리보기·검색' 점검(관제 335, 2026-11-07).

라이브 관리자 세션으로 열되 /admin 화면 파일만 이 폴더의 admin.html 로 바꿔 끼운다(--live 면 라이브 판 그대로).
재는 것:
  1) 처음 열면 고객·결제 표에 '오늘 해당자'만 있나(오늘 아닌 행이 0인가)
  2) 검색창에 이름을 치면 전체에서 찾아지나
  3) '전체 보기'를 누르면 50/30행으로 펼쳐지고 '접기'가 있나
사용: py tools/admin_today_preview_check.py [--live] [--shot 경로.png] [--q 검색어]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.live_admin import admin_page  # noqa: E402

HTML = Path(__file__).resolve().parents[1] / "shopping_shorts" / "static" / "admin.html"

PROBE = """(kind)=>{
  const body = document.getElementById(kind==='cust'?'rows':'plrows');
  const more = document.getElementById(kind==='cust'?'custMore':'plMore');
  const trs=[...body.querySelectorAll('tr')].filter(t=>!t.querySelector('td.empty'));
  return {rows: trs.length, empty: (body.querySelector('td.empty')||{}).textContent||'',
          more: (more||{}).innerText||''};
}"""

NOT_TODAY = """()=>{
  // 화면에 그려진 고객 중 '오늘 해당'이 아닌 사람 수 / 결제 중 오늘이 아닌 건 수(화면 함수와 같은 판정)
  const ids=[...document.querySelectorAll('#rows a[href^="/admin/customer/"]')].map(a=>+a.getAttribute('href').split('/').pop());
  const byId=Object.fromEntries((window._CUST||[]).map(c=>[c.id,c]));
  const badC=ids.filter(i=>byId[i] && !_custToday(byId[i])).length;
  const n=document.querySelectorAll('#plrows tr').length;
  return {cust_shown: ids.length, cust_not_today: badC,
          today_cust_total: (window._CUST||[]).filter(c=>c.acked_at!=null && _custToday(c)).length,
          today_pay_total: (ledgerItems||[]).filter(x=>_isTodayKST(x.at)).length};
}"""


def main(argv):
    live = "--live" in argv
    shot = argv[argv.index("--shot") + 1] if "--shot" in argv else None
    q = argv[argv.index("--q") + 1] if "--q" in argv else None

    def setup(pg):
        if not live:
            pg.route("**/admin", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8",
                                                     body=HTML.read_text(encoding="utf-8")))

    bad = []
    with admin_page("admin", setup=setup) as pg:
        pg.wait_for_function("(window._CUST||[]).length>0 && typeof ledgerItems!=='undefined' && ledgerItems.length>0",
                             timeout=30000)
        pg.wait_for_timeout(800)
        c0, p0, nt = pg.evaluate(PROBE, "cust"), pg.evaluate(PROBE, "pl"), pg.evaluate(NOT_TODAY)
        print("처음  고객", c0, "\n      결제", p0, "\n      오늘판정", nt)
        if nt["cust_not_today"]:
            bad.append(f"처음 고객 표에 오늘 아닌 사람 {nt['cust_not_today']}명")
        if c0["rows"] != nt["today_cust_total"]:
            bad.append(f"처음 고객 행 {c0['rows']} ≠ 오늘 해당 {nt['today_cust_total']}")
        if p0["rows"] != nt["today_pay_total"]:
            bad.append(f"처음 결제 행 {p0['rows']} ≠ 오늘 결제 {nt['today_pay_total']}")
        if shot:
            pg.screenshot(path=shot, full_page=True)
        # 검색
        name = q or pg.evaluate("(window._CUST||[]).filter(c=>c.acked_at!=null && c.name && !_custToday(c))[0].name")
        pg.fill("#custSearch", name)
        pg.wait_for_timeout(400)
        cs = pg.evaluate(PROBE, "cust")
        print(f"검색 '{name}' 고객", cs)
        if cs["rows"] < 1:
            bad.append(f"고객 검색 '{name}' 결과 0")
        pg.fill("#custSearch", "")
        pg.wait_for_timeout(300)
        payer = pg.evaluate("(ledgerItems||[]).filter(x=>x.payer && !_isTodayKST(x.at))[0]?.payer || ''")
        if payer:
            pg.fill("#plSearch", payer)
            pg.wait_for_timeout(400)
            ps = pg.evaluate(PROBE, "pl")
            print(f"검색 '{payer}' 결제", ps)
            if ps["rows"] < 1:
                bad.append(f"결제 검색 '{payer}' 결과 0")
            pg.fill("#plSearch", "")
            pg.wait_for_timeout(300)
        # 전체 보기
        pg.evaluate("_lvAll('cust',true); _lvAll('pl',true)")
        pg.wait_for_timeout(400)
        ca, pa = pg.evaluate(PROBE, "cust"), pg.evaluate(PROBE, "pl")
        print("전체보기 고객", ca, "\n         결제", pa)
        if ca["rows"] != 50 or "접기" not in ca["more"]:
            bad.append(f"고객 전체 보기 {ca['rows']}행·접기 {'접기' in ca['more']}")
        if pa["rows"] != min(30, pg.evaluate("ledgerItems.length")) or "접기" not in pa["more"]:
            bad.append(f"결제 전체 보기 {pa['rows']}행·접기 {'접기' in pa['more']}")
        print("페이지 오류", pg.errors)
        if pg.errors:
            bad.append(f"페이지 오류 {pg.errors[:2]}")
    print("결과:", "통과" if not bad else "실패 — " + " / ".join(bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
