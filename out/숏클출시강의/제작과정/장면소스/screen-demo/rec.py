import time, sys, os, json, re
from playwright.sync_api import sync_playwright
out=sys.argv[1]; log=os.path.join(out,"replay.log")
names=["준비 확인","영상 확인","해외 원본 찾기","제품 확인","자료 조사","원본 정리","원음 정리","대본 쓰기","대본 확인","장면 맞추기","글자 지우기","완성본 검사","완성"]
with sync_playwright() as p:
    b=p.chromium.launch(channel="chrome")
    c=b.new_context(viewport={"width":1920,"height":1080},record_video_dir=os.path.join(out,"rec"),record_video_size={"width":1920,"height":1080})
    pg=c.new_page(); t0=time.time()
    pg.goto("http://127.0.0.1:8766"); seen=0; ev=[]; clicks=[]
    while time.time()-t0<150:
        lines=open(log,encoding="utf-8",errors="ignore").read().splitlines()
        for l in lines[seen:]:
            t=round(time.time()-t0,1); ev.append((t,l))
            m=re.search(r"→ (.+?) 중",l) or re.search(r"^⏳ (.+?) 중",l)
            if "→" in l and "완료" in l and "DONE" not in l:
                m=re.search(r"→ (.+?)( 중|$)",l)
            if m:
                nm=m.group(1).strip()
                for n in names:
                    if n in nm:
                        try:
                            pg.locator(f"text=/\d+\. {n}/").first.click(timeout=1500); clicks.append((t,n))
                        except Exception as e: clicks.append((t,n,"fail"))
                        break
        seen=len(lines)
        if any("DONE" in l for l in lines): 
            time.sleep(6); break
        time.sleep(0.5)
    pg.screenshot(path=os.path.join(out,"rec","last.png"))
    json.dump({"events":ev,"clicks":clicks},open(os.path.join(out,"events.json"),"w",encoding="utf-8"),ensure_ascii=False)
    c.close(); b.close()
