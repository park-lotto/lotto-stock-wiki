# -*- coding: utf-8 -*-
import sys, io, os, re, time, base64, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

SAVE_DIR = r"C:\Users\CH\Desktop\로또의 주식\raw\naver_premium\dongju"
CATEGORY_URL = "https://contents.premium.naver.com/smstockstudy/1028/contents?categoryId=192ecb61fa3000awt"
TARGET_TITLE = "온코크로스"
IMG_EXTS = {'.jpg','.jpeg','.png','.gif','.webp','.avif'}

def img_to_base64(path):
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    mime = {'jpg':'jpeg','jpeg':'jpeg','png':'png','gif':'gif','webp':'webp','avif':'avif'}.get(ext,'jpeg')
    with open(path,'rb') as f: data=base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{data}"

def download_image(url, path):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0","Referer":"https://contents.premium.naver.com/"})
        with urllib.request.urlopen(req, timeout=10) as r:
            with open(path,'wb') as f: f.write(r.read())
        return True
    except: return False

def make_html(title,date,url,article_html):
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0}}body{{background:#0d0d0d;color:#e8e8e8;font-family:'Apple SD Gothic Neo',sans-serif;font-size:16px;line-height:1.9}}.hdr{{background:#111;border-bottom:1px solid #222;padding:14px 24px;position:sticky;top:0}}.hdr a{{color:#00ff88;text-decoration:none;font-size:13px}}.wrap{{max-width:860px;margin:0 auto;padding:36px 24px 80px}}.meta{{color:#666;font-size:13px;margin-bottom:8px}}h1{{font-size:24px;font-weight:800;color:#fff;line-height:1.4;margin-bottom:20px}}.src{{color:#00ff88;font-size:12px;text-decoration:none}}hr{{border:none;border-top:1px solid #222;margin:24px 0}}.article *{{max-width:100%}}.article p{{margin-bottom:16px}}.article img{{display:block;max-width:100%;border-radius:8px;border:1px solid #222;margin:20px auto}}.article strong,.article b{{color:#fff}}.article a{{color:#00ff88}}.back{{display:inline-block;margin-top:40px;padding:10px 20px;background:#00ff88;color:#000;font-weight:700;border-radius:6px;text-decoration:none;font-size:14px}}</style>
</head><body><div class="hdr"><a href="../index.html">← 목록으로</a></div><div class="wrap"><p class="meta">{date} &nbsp;|&nbsp; <a href="{url}" class="src" target="_blank">원본 ↗</a></p><h1>{title}</h1><hr><div class="article">{article_html}</div><a href="../index.html" class="back">← 목록으로</a></div></body></html>"""

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    # 카테고리 페이지에서 URL 찾기
    print("카테고리에서 URL 탐색 중...")
    page.goto(CATEGORY_URL, wait_until="domcontentloaded")
    time.sleep(2)

    target_url = None
    # 더보기 누르면서 찾기
    for _ in range(60):
        links = page.query_selector_all("a")
        for link in links:
            href = link.get_attribute("href") or ""
            text = link.inner_text().strip()
            if TARGET_TITLE in text and "/contents/" in href and "categoryId" not in href:
                target_url = f"https://contents.premium.naver.com{href}" if href.startswith("/") else href
                print(f"찾음: {text}\nURL: {target_url}")
                break
        if target_url:
            break
        btn = page.query_selector("button:has-text('더보기'), a:has-text('더보기')")
        if btn:
            btn.click(); time.sleep(1.5)
        else:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)"); time.sleep(1.5)

    if not target_url:
        print("URL 못 찾음"); browser.close(); exit()

    # 글 내용 가져오기
    page.goto(target_url, wait_until="networkidle")
    time.sleep(2)

    title = page.evaluate("document.querySelector('h1,h2,[class*=title] p')?.innerText||document.title") or "549"
    title = title.strip()
    date_el = page.query_selector("[class*='date'],time")
    date = date_el.inner_text().strip() if date_el else ""

    # 이미지 다운로드
    post_dir = os.path.join(SAVE_DIR, "549_온코크로스,토모큐브,삼양엔씨켐 -")
    os.makedirs(post_dir, exist_ok=True)

    imgs = page.query_selector_all("article img, main img, [class*='content'] img")
    img_lines = []
    img_count = 0
    for img in imgs:
        src = img.get_attribute("src") or img.get_attribute("data-src") or ""
        if not src or "data:image" in src: continue
        if any(x in src for x in ["icon","logo","btn","profile","l.gif"]): continue
        img_count += 1
        ext = src.split("?")[0].split(".")[-1][:5] or "jpg"
        fname = f"img_{img_count:03d}.{ext}"
        ok = download_image(src, os.path.join(post_dir, fname))
        img_lines.append(f"[이미지 {img_count}] {fname} ({'저장됨' if ok else '실패'})\n원본: {src}")

    # content.txt 저장
    body = page.inner_text("body")
    with open(os.path.join(post_dir,"content.txt"),'w',encoding='utf-8') as f:
        f.write(f"제목: {title}\n날짜: {date}\nURL: {target_url}\n\n")
        f.write("="*60+"\n본문\n"+"="*60+"\n")
        f.write(body)
        if img_lines:
            f.write("\n\n"+"="*60+"\n이미지 목록\n"+"="*60+"\n")
            f.write("\n".join(img_lines))

    # 인라인 HTML 빌드
    article_html = page.evaluate("""()=>{const sel=['article','[class*="article_body"]','.se-main-container'];for(const s of sel){const el=document.querySelector(s);if(el)return el.innerHTML;}return '';}""")
    if not article_html:
        article_html = f"<p>{body[:4000]}</p>"

    local_imgs = sorted([f for f in os.listdir(post_dir) if os.path.splitext(f)[1].lower() in IMG_EXTS])
    processed = article_html
    img_tags = re.findall(r'<img[^>]+>', processed, re.I)
    matched = 0
    for img_tag in img_tags:
        src_m = re.search(r'src=["\']([^"\']+)["\']', img_tag)
        if not src_m: continue
        src = src_m.group(1)
        if any(x in src for x in [".gif","icon","logo","btn","profile"]): continue
        if matched >= len(local_imgs): break
        lpath = os.path.join(post_dir, local_imgs[matched])
        if os.path.exists(lpath):
            try:
                b64 = img_to_base64(lpath)
                new = re.sub(r'src=["\'][^"\']*["\']',f'src="{b64}"',img_tag)
                new = re.sub(r'srcset=["\'][^"\']*["\']','',new)
                processed = processed.replace(img_tag,new,1); matched+=1
            except: pass

    html = make_html(title,date,target_url,processed)
    with open(os.path.join(post_dir,"index.html"),'w',encoding='utf-8') as f:
        f.write(html)

    print(f"완료! 이미지 {img_count}개 다운, {matched}개 인라인")
    page.close(); browser.close()
