"""링크 서비스(인포크/머닝) 화면 점검(2026-10-18 고객 제보 F2). 사용: py tools/link_hub_check.py <produce.html 절대경로>"""
import sys,json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page(); pg.on('pageerror',lambda e:None)
    pg.goto('file:///'+sys.argv[1]); pg.wait_for_timeout(800)
    r=pg.evaluate("""async()=>{
      const box=document.getElementById('inpockBox'); document.body.appendChild(box);
      MIX_JOB='t1'; let hub='moneying'; const posts=[];
      window.fetch=async(u,o)=>{ if(String(u).includes('/api/link_hub')){posts.push(o.body); hub=JSON.parse(o.body).hub; return {json:async()=>({ok:true})};} return {json:async()=>{
        const H={inpock:{key:'inpock',name:'인포크',page:'https://link.inpock.co.kr',admin:'https://link.inpock.co.kr/admin'},moneying:{key:'moneying',name:'머닝',page:'https://moneying.biz',admin:'https://moneying.biz/'}}[hub];
        return {ok:true,product:{name:'커피포트',partner_url:'https://link.coupang.com/a/x'},final_link:'https://link.coupang.com/a/x',link_hub:H}; }};};
      await refreshInpock(); const t1=box.innerText.replace(/ +/g,' ').slice(0,160);
      let opened=''; const oc=HTMLAnchorElement.prototype.click; HTMLAnchorElement.prototype.click=function(){opened=this.href};
      try{ await inpockModalOpen(); }catch(e){}
      HTMLAnchorElement.prototype.click=oc;
      box.querySelector('select').value='inpock'; await setLinkHub('inpock'); await new Promise(r=>setTimeout(r,50));
      const t2=box.innerText.replace(/ +/g,' ').slice(0,60);
      return {머닝화면:t1, 연창:opened, 저장요청:posts, 인포크로바꾼뒤:t2};
    }""")
    print(json.dumps(r,ensure_ascii=False,indent=1)); b.close()
