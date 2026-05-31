# -*- coding: utf-8 -*-
import sys, io, os, re, time, urllib.request, urllib.parse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from playwright.sync_api import sync_playwright

CATEGORY_URL = "https://contents.premium.naver.com/smstockstudy/1028/contents?categoryId=192ecb61fa3000awt"
BASE = "https://contents.premium.naver.com"
SAVE_DIR = r"C:\Users\CH\Desktop\로또의 주식\raw\naver_premium\dongju"

os.makedirs(SAVE_DIR, exist_ok=True)

def safe_filename(title):
    title = re.sub(r'[\\/:*?"<>|]', '_', title)
    return title[:60].strip()

def get_all_post_links(page):
    seen = set()
    posts = []
    prev_count = 0

    while True:
        links = page.query_selector_all("a")
        for link in links:
            href = link.get_attribute("href") or ""
            if "/contents/" in href and "categoryId" not in href and "search" not in href:
                title_el = link.query_selector("strong, p")
                title = title_el.inner_text().strip() if title_el else link.inner_text().strip()
                full_url = BASE + href if href.startswith("/") else href
                if full_url not in seen and title:
                    seen.add(full_url)
                    posts.append((title, full_url))

        more_btn = page.query_selector("button:has-text('더보기'), a:has-text('더보기')")
        if more_btn:
            more_btn.click()
            time.sleep(2)
        else:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)

        new_count = len(posts)
        if new_count == prev_count:
            break
        prev_count = new_count

    return posts

def download_image(img_url, save_path):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://contents.premium.naver.com/"
        }
        req = urllib.request.Request(img_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            with open(save_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        return False

def fetch_post(page, url, post_dir):
    page.goto(url)
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    # 제목
    title_el = page.query_selector("p.article_info__title, h1, .title, [class*='title']")
    title = title_el.inner_text().strip() if title_el else "제목없음"

    # 날짜
    date_el = page.query_selector("[class*='date'], time")
    date = date_el.inner_text().strip() if date_el else ""

    # 본문 텍스트
    body = page.inner_text("body")
    if "프리미엄 구독자 전용" in body and len(body) < 600:
        return None

    # 이미지 수집
    imgs = page.query_selector_all("article img, .article_body img, [class*='content'] img, main img")
    if not imgs:
        imgs = page.query_selector_all("img")

    img_lines = []
    os.makedirs(post_dir, exist_ok=True)
    img_count = 0
    for img in imgs:
        src = img.get_attribute("src") or img.get_attribute("data-src") or ""
        if not src or "data:image" in src or src.startswith("blob:"):
            continue
        if any(x in src for x in ["icon", "logo", "btn", "arrow", "bullet", "profile"]):
            continue
        img_count += 1
        ext = src.split("?")[0].split(".")[-1][:5] or "jpg"
        img_fname = f"img_{img_count:03d}.{ext}"
        img_path = os.path.join(post_dir, img_fname)
        ok = download_image(src, img_path)
        status = "저장됨" if ok else "실패"
        img_lines.append(f"[이미지 {img_count}] {img_fname} ({status})\n원본: {src}")

    # 영상 수집 (iframe / video)
    video_lines = []
    iframes = page.query_selector_all("iframe")
    for iframe in iframes:
        src = iframe.get_attribute("src") or ""
        if src:
            video_lines.append(f"[영상] {src}")

    videos = page.query_selector_all("video source, video")
    for v in videos:
        src = v.get_attribute("src") or ""
        if src:
            video_lines.append(f"[비디오] {src}")

    # 본문 저장
    content = f"제목: {title}\n날짜: {date}\nURL: {url}\n\n"
    content += "=" * 60 + "\n본문\n" + "=" * 60 + "\n"
    content += body
    if img_lines:
        content += "\n\n" + "=" * 60 + "\n이미지 목록\n" + "=" * 60 + "\n"
        content += "\n".join(img_lines)
    if video_lines:
        content += "\n\n" + "=" * 60 + "\n영상 목록\n" + "=" * 60 + "\n"
        content += "\n".join(video_lines)

    return title, content, img_count, len(video_lines)

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()

    # 1단계: 글 목록
    list_page = ctx.new_page()
    print("글 목록 수집 중...")
    list_page.goto(CATEGORY_URL)
    list_page.wait_for_load_state("networkidle")
    time.sleep(2)
    posts = get_all_post_links(list_page)
    list_page.close()
    print(f"총 {len(posts)}개 글 발견\n")

    # 2단계: 글 + 이미지 저장
    content_page = ctx.new_page()
    success = 0
    fail = 0

    for i, (title, url) in enumerate(posts, 1):
        print(f"[{i:02d}/{len(posts)}] {title[:40]}")
        try:
            slug = safe_filename(title)
            post_dir = os.path.join(SAVE_DIR, f"{i:03d}_{slug}")
            result = fetch_post(content_page, url, post_dir)
            if result is None:
                print(f"  -> 접근 실패")
                fail += 1
                continue

            fetched_title, content, n_img, n_vid = result
            txt_path = os.path.join(post_dir, "content.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  -> 저장 완료 | 이미지 {n_img}개 | 영상링크 {n_vid}개")
            success += 1

        except Exception as e:
            print(f"  -> 오류: {e}")
            fail += 1

        time.sleep(1)

    content_page.close()
    browser.close()

    print(f"\n완료: 성공 {success}개 / 실패 {fail}개")
    print(f"저장 위치: {SAVE_DIR}")
