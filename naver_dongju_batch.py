# -*- coding: utf-8 -*-
import sys, io, os, re, time, base64
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

SAVE_DIR = r"C:\Users\CH\Desktop\로또의 주식\raw\naver_premium\dongju"
START = 11   # 1~10 완료됨
END   = 9999 # 전체

IMG_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif'}

def img_to_base64(path):
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    mime = {'jpg':'jpeg','jpeg':'jpeg','png':'png','gif':'gif','webp':'webp','avif':'avif'}.get(ext,'jpeg')
    with open(path,'rb') as f:
        data = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{data}"

def get_local_images(post_dir):
    return sorted([f for f in os.listdir(post_dir) if os.path.splitext(f)[1].lower() in IMG_EXTS])

def parse_url_map(post_dir):
    txt = os.path.join(post_dir,"content.txt")
    if not os.path.exists(txt): return {}
    with open(txt,encoding='utf-8') as f: lines=f.readlines()
    url_map={}; i=0
    while i<len(lines):
        m=re.match(r'\[이미지 \d+\] (\S+)',lines[i].strip())
        if m:
            fname=m.group(1)
            if i+1<len(lines) and lines[i+1].strip().startswith("원본:"):
                orig=lines[i+1].strip().split("원본:",1)[1].strip()
                url_map[orig]=fname
                url_map[orig.split("?")[0]]=fname
                url_map[orig.split("?")[0].split("/")[-1]]=fname
        i+=1
    return url_map

def read_url(post_dir):
    txt=os.path.join(post_dir,"content.txt")
    if not os.path.exists(txt): return None
    with open(txt,encoding='utf-8') as f:
        for line in f:
            if line.startswith("URL:"): return line.split("URL:",1)[1].strip()
    return None

def make_html(title,date,url,article_html):
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d0d0d;color:#e8e8e8;font-family:'Apple SD Gothic Neo',sans-serif;font-size:16px;line-height:1.9}}
.hdr{{background:#111;border-bottom:1px solid #222;padding:14px 24px;position:sticky;top:0;z-index:10}}
.hdr a{{color:#00ff88;text-decoration:none;font-size:13px}}
.wrap{{max-width:860px;margin:0 auto;padding:36px 24px 80px}}
.meta{{color:#666;font-size:13px;margin-bottom:8px}}
h1{{font-size:24px;font-weight:800;color:#fff;line-height:1.4;margin-bottom:20px}}
.src{{color:#00ff88;font-size:12px;text-decoration:none}}
hr{{border:none;border-top:1px solid #222;margin:24px 0}}
.article *{{max-width:100%}}
.article p{{margin-bottom:16px}}
.article img{{display:block;max-width:100%;border-radius:8px;border:1px solid #222;margin:20px auto}}
.article strong,.article b{{color:#fff}}
.article a{{color:#00ff88}}
.article h2,.article h3{{color:#fff;margin:24px 0 12px}}
.article ul,.article ol{{padding-left:20px;margin-bottom:16px}}
.article li{{margin-bottom:6px}}
.article table{{border-collapse:collapse;width:100%;margin:16px 0}}
.article td,.article th{{border:1px solid #333;padding:8px 12px}}
.article th{{background:#1a1a1a;color:#fff}}
.back{{display:inline-block;margin-top:40px;padding:10px 20px;background:#00ff88;color:#000;font-weight:700;border-radius:6px;text-decoration:none;font-size:14px}}
</style></head><body>
<div class="hdr"><a href="../index.html">← 목록으로</a></div>
<div class="wrap">
  <p class="meta">{date} &nbsp;|&nbsp; <a href="{url}" class="src" target="_blank">원본 ↗</a></p>
  <h1>{title}</h1><hr>
  <div class="article">{article_html}</div>
  <a href="../index.html" class="back">← 목록으로</a>
</div></body></html>"""

def make_index(entries):
    rows=""
    for i,(folder,title,date,n_img) in enumerate(entries,1):
        tag=f'<span style="margin-left:8px;padding:2px 8px;background:#1a2a1a;color:#00ff88;border-radius:4px;font-size:11px;font-weight:700">이미지 {n_img}</span>' if n_img else ""
        rows+=f'<a href="{folder}/index.html" class="item"><span class="num">{i:03d}</span><span class="body"><span class="ttl">{title}</span><span class="dt">{date}{tag}</span></span></a>\n'
    return f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="UTF-8"><title>동주 아카이브</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d0d0d;color:#e8e8e8;font-family:'Apple SD Gothic Neo',sans-serif}}
.top{{background:#111;border-bottom:1px solid #222;padding:24px}}
.top h1{{font-size:22px;font-weight:800;color:#fff}}
.top p{{color:#666;font-size:13px;margin-top:4px}}
.sw{{padding:16px 24px;max-width:860px;margin:0 auto}}
input{{width:100%;padding:12px 16px;background:#1a1a1a;border:1px solid #333;border-radius:8px;color:#fff;font-size:15px;outline:none}}
input::placeholder{{color:#555}}
.list{{max-width:860px;margin:0 auto;padding:0 24px 60px}}
.item{{display:flex;align-items:center;gap:14px;padding:14px 16px;background:#111;border:1px solid #1e1e1e;border-radius:10px;margin-bottom:8px;text-decoration:none;color:inherit;transition:border-color .15s}}
.item:hover{{border-color:#00ff88}}
.num{{color:#444;font-size:12px;font-weight:700;min-width:32px}}
.body{{display:flex;flex-direction:column;gap:4px}}
.ttl{{color:#e8e8e8;font-size:15px;font-weight:600}}
.dt{{color:#555;font-size:12px}}
</style></head><body>
<div class="top"><h1>동주 매매일지 아카이브</h1><p>수급단타왕×만쥬 | 동주 카테고리 전체 ({len(entries)}개)</p></div>
<div class="sw"><input id="q" placeholder="종목명·날짜·키워드 검색..."></div>
<div class="list" id="list">{rows}</div>
<script>
document.getElementById('q').addEventListener('input',function(){{
  const q=this.value.toLowerCase();
  document.querySelectorAll('.item').forEach(el=>{{
    el.style.display=el.querySelector('.ttl').textContent.toLowerCase().includes(q)?'flex':'none';
  }});
}});
</script></body></html>"""

with sync_playwright() as p:
    browser=p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx=browser.contexts[0] if browser.contexts else browser.new_context()
    page=ctx.new_page()
    page.route("**/*.{png,jpg,jpeg,gif,webp,avif,svg}",lambda r:r.abort())

    folders=sorted([d for d in os.listdir(SAVE_DIR) if os.path.isdir(os.path.join(SAVE_DIR,d))])
    targets=folders[START-1:END]
    total=len(targets)
    entries_all=[]

    # 기존 1~10 entries 복원 (인덱스용)
    for folder in folders[:START-1]:
        post_dir=os.path.join(SAVE_DIR,folder)
        url=read_url(post_dir) or ""
        txt=os.path.join(post_dir,"content.txt")
        title=folder; date=""
        if os.path.exists(txt):
            with open(txt,encoding='utf-8') as f:
                for line in f:
                    if line.startswith("제목:"): title=line.split("제목:",1)[1].strip()
                    elif line.startswith("날짜:"): date=line.split("날짜:",1)[1].strip()
        n_img=len(get_local_images(post_dir))
        entries_all.append((folder,title,date,n_img))

    success=0; fail=0
    for i,folder in enumerate(targets,START):
        post_dir=os.path.join(SAVE_DIR,folder)
        url=read_url(post_dir)
        if not url: continue
        if i%50==0 or i<=START+2:
            print(f"[{i}/{START+total-1}] {folder[:40]}")
        try:
            page.goto(url,wait_until="domcontentloaded",timeout=15000)
            time.sleep(1.0)
            title=page.evaluate("document.querySelector('h1,h2,[class*=title] p')?.innerText||document.title") or folder
            title=title.strip()
            date_el=page.query_selector("[class*='date'],time")
            date=date_el.inner_text().strip() if date_el else ""
            article_html=page.evaluate("""()=>{
                const sel=['article','[class*="article_body"]','[class*="content_body"]','.se-main-container','#content'];
                for(const s of sel){const el=document.querySelector(s);if(el)return el.innerHTML;}
                return document.querySelector('main')?.innerHTML||'';
            }""")
            if not article_html or len(article_html)<100:
                article_html=f"<p>{page.inner_text('body')[:3000]}</p>"

            url_map=parse_url_map(post_dir)
            local_imgs=get_local_images(post_dir)
            processed=article_html
            img_tags=re.findall(r'<img[^>]+>',processed,re.I)
            matched=0
            for img_tag in img_tags:
                src_m=re.search(r'src=["\']([^"\']+)["\']',img_tag)
                if not src_m: continue
                src=src_m.group(1)
                fname=(url_map.get(src) or url_map.get(src.split("?")[0]) or url_map.get(src.split("?")[0].split("/")[-1]))
                if not fname and matched<len(local_imgs):
                    if any(x in src for x in [".gif","l.gif","icon","logo","btn","profile","nfs200_200"]): continue
                    fname=local_imgs[matched]
                if not fname: continue
                lpath=os.path.join(post_dir,fname)
                if not os.path.exists(lpath): matched+=1; continue
                try:
                    b64=img_to_base64(lpath)
                    new=re.sub(r'src=["\'][^"\']*["\']',f'src="{b64}"',img_tag)
                    new=re.sub(r'srcset=["\'][^"\']*["\']','',new)
                    processed=processed.replace(img_tag,new,1)
                    matched+=1
                except: pass

            html=make_html(title,date,url,processed)
            with open(os.path.join(post_dir,"index.html"),'w',encoding='utf-8') as f:
                f.write(html)
            entries_all.append((folder,title,date,matched))
            success+=1
        except Exception as e:
            print(f"  [{i}] 오류: {e}")
            entries_all.append((folder,folder,"",0))
            fail+=1
        time.sleep(0.5)

    page.close(); browser.close()

    # 인덱스 재생성
    idx=make_index(entries_all)
    with open(os.path.join(SAVE_DIR,"index.html"),'w',encoding='utf-8') as f:
        f.write(idx)

    print(f"\n전체 완료: 성공 {success} / 실패 {fail}")
    print(f"index.html 재생성 완료 ({len(entries_all)}개)")
