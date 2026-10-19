"""9단계 링크 서비스 고르기 = 인포크·머닝 두 버튼 양옆(2026-10-19 사장님). 사용: py tools/link_hub_buttons_check.py <png>
두 버튼이 같은 줄에 있고, 고른 쪽만 ✓·색, 누르면 setLinkHub(키)가 불린다."""
import os, sys
from playwright.sync_api import sync_playwright
f = os.path.abspath("shopping_shorts/static/produce.html").replace("\\", "/")
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": 700, "height": 500})
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file:///" + f); pg.wait_for_timeout(1500)
    r = pg.evaluate("""async()=>{
      MIX_JOB='x'; let called=null;
      document.body.innerHTML='<div id="inpockBox" style="width:600px;margin:20px"></div>';
      window.fetch=async()=>({json:async()=>({ok:true,product:{name:'샌드 커피',partner_url:'u'},final_link:'https://link.coupang.com/a/x',
        link_hub:{key:'moneying',name:'머닝',page:'https://moneying.biz',admin:'https://moneying.biz/my/multilink'}})});
      await refreshInpock();
      window.refreshInpock=async()=>{}; window.setLinkHub=k=>{called=k};
      const bs=[...document.querySelectorAll('[data-linkhub]')];
      const rs=bs.map(x=>x.getBoundingClientRect());
      bs[0].click();
      return {labels:bs.map(x=>x.textContent.trim()),sameRow:rs.length==2&&Math.abs(rs[0].top-rs[1].top)<2&&rs[1].left>rs[0].right,clicked:called};}""")
    print(r, "errors", errs[:3]); pg.screenshot(path=sys.argv[1]); b.close()
