import sys, time, urllib.parse
from playwright.sync_api import sync_playwright
Q=["쇼츠 자동화 프로그램","쇼츠 수익화 강의","AI 쇼츠 만들기 부업","클로드 쇼츠 자동화"]
CSS="""
ytd-channel-name, #channel-name, #avatar, yt-img-shadow#avatar, #channel-info, ytd-channel-name *, .ytd-channel-name, a[href^="/@"], a[href^="/channel"], ytd-channel-renderer, yt-avatar-shape, #byline-container, ytd-video-owner-renderer { filter: blur(9px) !important; }
ytd-thumbnail img, yt-image img, ytd-thumbnail, yt-thumbnail-view-model, img.yt-core-image, ytd-playlist-thumbnail, ytd-reel-item-renderer img { filter: blur(8px) !important; }
ytd-ad-slot-renderer, ytd-promoted-sparkles-web-renderer, ytd-search-pyv-renderer, ytd-in-feed-ad-layout-renderer, ytd-shopping-companion-renderer, ytd-product-list-renderer, ytd-merch-shelf-renderer, ytd-statement-banner-renderer, ytd-brand-video-singleton-renderer {display:none !important;}
ytd-expandable-metadata-renderer, .metadata-snippet-container, .metadata-snippet-text, yt-formatted-string.metadata-snippet-text, ytd-expandable-metadata-renderer * { filter: blur(7px) !important; }
#avatar-btn, ytd-topbar-menu-button-renderer img, #logo img {filter:none !important;}
"""
headless = sys.argv[1]!="headed"
with sync_playwright() as p:
    b=p.chromium.launch(headless=headless, executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    c=b.new_context(viewport={"width":1920,"height":1080},locale="ko-KR",timezone_id="Asia/Seoul")
    pg=c.new_page()
    for i,q in enumerate(Q,1):
        pg.set_viewport_size({'width':1920,'height':1080})
        pg.goto("https://www.youtube.com/results?search_query="+urllib.parse.quote(q),wait_until="domcontentloaded")
        try: pg.wait_for_selector("ytd-video-renderer",timeout=20000)
        except Exception as e: print("noresult",q,pg.url)
        pg.add_style_tag(content=CSS)
        for _ in range(4):
            pg.mouse.wheel(0,1500); time.sleep(1.2)
        pg.set_viewport_size({'width':1920,'height':2400}); time.sleep(2.5)
        pg.evaluate("window.scrollTo(0,0)"); time.sleep(1.5)
        pg.add_style_tag(content=CSS)
        n=pg.locator("ytd-video-renderer").count()
        print(q,"videos",n)
        import json
        js="""(cands)=>{const out=[];const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode()){const t=n.nodeValue;if(!t||t.trim().length<2)continue;for(const c of cands){let k=t.indexOf(c);while(k>=0){const r=document.createRange();r.setStart(n,k);r.setEnd(n,k+c.length);const b=r.getBoundingClientRect();if(b.width>3&&b.top+scrollY<2300&&b.left>240){out.push([c,t.trim().slice(0,60),Math.round(b.left),Math.round(b.top+scrollY),Math.round(b.width),Math.round(b.height)])}k=t.indexOf(c,k+1)}}}return out}"""
        C=["100% 자동화","자동 제작 프로그램","자동화 프로그램","프로그램","조회수 104만회","수익화","수익 창출","강의","부업","쇼츠 부업","AI","클로드","자동화","100%","80만원","월 300","시간"]
        json.dump(pg.evaluate(js,C),open(f"cands_{i}.json","w",encoding="utf8"),ensure_ascii=False)
        pg.screenshot(path=f"search_{i}.png")
    b.close()
