# -*- coding: utf-8 -*-
"""
viewtrap_extract.py — viewtrap 강의 내용 텍스트 추출
사용법: python viewtrap_extract.py

전제조건:
  Chrome을 먼저 원격 디버깅 모드로 열어둘 것:
  chrome.exe --remote-debugging-port=9222 --user-data-dir=C:/chrome_debug

동작:
  1. 강의 전체 목록 API 호출
  2. 강의별 viewtrap-ai 스크립트 API 시도
  3. 실패 시 VTT 자막 캡처 fallback
  4. raw/viewtrap/ 폴더에 마크다운으로 저장
"""
import sys, io, time, json, re
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE     = Path(__file__).parent
OUT_DIR  = BASE / 'raw' / 'viewtrap'
OUT_DIR.mkdir(parents=True, exist_ok=True)

API = "https://api.viewtrap.com/api/v2"

# ── helpers ──────────────────────────────────────────────

def log(msg):
    print(msg, flush=True)

def api_get(page, path):
    return page.evaluate(f"""async () => {{
        try {{
            const r = await fetch('{API}{path}', {{credentials:'include'}});
            if (!r.ok) return {{__status: r.status}};
            return await r.json();
        }} catch(e) {{ return {{__error: e.message}}; }}
    }}""")

def get_vtt_from_network(page, lecture_url):
    """강의 페이지 열고 네트워크에서 VTT 캡처"""
    vtt_bodies = {}

    def on_response(resp):
        if ".vtt" in resp.url or "subtitle" in resp.url or "caption" in resp.url:
            try:
                vtt_bodies[resp.url] = resp.body().decode('utf-8', errors='ignore')
            except:
                pass

    page.on("response", on_response)
    page.goto(lecture_url, wait_until="networkidle", timeout=30000)
    time.sleep(5)
    page.remove_listener("response", on_response)
    return vtt_bodies

def parse_vtt(vtt_text):
    """VTT → 순수 텍스트"""
    lines = vtt_text.splitlines()
    texts = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
            continue
        if re.match(r'^\d{2}:\d{2}', line):  # 타임코드
            continue
        if re.match(r'^\d+$', line):          # 시퀀스 번호
            continue
        # HTML 태그 제거
        clean = re.sub(r'<[^>]+>', '', line)
        if clean:
            texts.append(clean)
    return ' '.join(texts)

def save_chapter(chapter_title, videos_data):
    """챕터 단위로 md 파일 저장"""
    safe = re.sub(r'[\\/:*?"<>|]', '_', chapter_title)[:50]
    path = OUT_DIR / f"{safe}.md"

    lines = [f"# {chapter_title}\n"]
    for title, content in videos_data:
        lines.append(f"## {title}\n")
        lines.append(content.strip())
        lines.append("")

    path.write_text('\n'.join(lines), encoding='utf-8')
    log(f"  💾 {path.name}")
    return path

# ────────────────────────────────────────────────────────

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    try:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        log("✅ Chrome CDP 연결 성공")
    except Exception as e:
        log(f"❌ Chrome 연결 실패: {e}")
        log("Chrome을 먼저 실행하세요:")
        log('  chrome.exe --remote-debugging-port=9222 --user-data-dir=C:/chrome_debug')
        sys.exit(1)

    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    # ── 1. viewtrap 홈 접속 (쿠키 확인) ─────────────────
    log("\n▶ viewtrap 접속 중...")
    page.goto("https://viewtrap.com/training-room", wait_until="networkidle", timeout=30000)
    time.sleep(2)

    if "login" in page.url or "sign" in page.url:
        log("❌ 로그인 필요 — Chrome에서 viewtrap 로그인 후 다시 실행하세요")
        sys.exit(1)

    # ── 2. 강의 전체 목록 조회 ────────────────────────────
    log("\n▶ 강의 목록 API 조회...")
    lectures_data = api_get(page, "/vod/revise/lectures")

    if lectures_data.get('__error') or not lectures_data.get('data'):
        log(f"⚠️  강의 목록 API 실패: {lectures_data}")
        log("페이지에서 강의 링크 직접 수집 시도...")
        # fallback: 페이지 내 링크 수집
        links = page.evaluate("""() => {
            return [...document.querySelectorAll('a[href*="lecture"], a[href*="video"], a[href*="lesson"]')]
                .map(a => ({text: a.innerText.trim(), href: a.href}))
                .filter(x => x.href);
        }""")
        log(f"발견한 강의 링크 {len(links)}개:")
        for lk in links[:10]:
            log(f"  {lk['text'][:40]} → {lk['href']}")
        page.close()
        browser.close()
        sys.exit(0)

    chapters = lectures_data['data'][0]['chapters'] if isinstance(lectures_data['data'], list) else []
    total_videos = sum(len(ch.get('videos', [])) for ch in chapters)
    log(f"✅ 총 {len(chapters)}개 챕터, {total_videos}개 강의")

    # ── 3. 챕터별 추출 ────────────────────────────────────
    summary = []

    for ch_idx, chapter in enumerate(chapters):
        ch_title = chapter.get('title', f'챕터{ch_idx+1}')
        ch_label = chapter.get('label', '')
        full_title = f"{ch_label} {ch_title}".strip()
        log(f"\n{'='*55}")
        log(f"[{ch_idx+1}/{len(chapters)}] {full_title}")
        log(f"{'='*55}")

        videos = chapter.get('videos', [])
        videos_data = []

        for v_idx, video in enumerate(videos):
            v_title = video.get('title', f'강의{v_idx+1}')
            v_key   = video.get('videoKey') or video.get('_id', '')
            v_id    = video.get('_id', '')
            log(f"\n  [{v_idx+1}/{len(videos)}] {v_title}")

            content = ""

            # ── 3a. viewtrap-ai 스크립트 API ─────────────
            if v_key:
                endpoints = [
                    f"/viewtrap-ai/revise/script?videoKey={v_key}",
                    f"/viewtrap-ai/revise/bpz?videoKey={v_key}",
                    f"/viewtrap-ai/lecture/script?videoKey={v_key}",
                ]
                for ep in endpoints:
                    resp = api_get(page, ep)
                    if resp.get('__status') or resp.get('__error'):
                        continue
                    # 스크립트 내용 추출 시도
                    data = resp.get('data') or resp
                    if isinstance(data, str) and len(data) > 50:
                        content = data
                        log(f"    ✅ AI 스크립트 ({len(content)}자)")
                        break
                    elif isinstance(data, dict):
                        for key in ['script', 'text', 'content', 'summary', 'transcript']:
                            if data.get(key) and len(str(data[key])) > 50:
                                content = str(data[key])
                                log(f"    ✅ AI 스크립트[{key}] ({len(content)}자)")
                                break
                    if content:
                        break

            # ── 3b. VTT 자막 fallback ─────────────────────
            if not content and v_id:
                curriculum_id = chapter.get('curriculumId', '')
                lecture_url = f"https://viewtrap.com/business/lectures?curriculumId={curriculum_id}&videoKey={v_key}"
                log(f"    ⚠️  AI 스크립트 없음 → VTT 시도...")
                vtt_dict = get_vtt_from_network(page, lecture_url)
                if vtt_dict:
                    combined = []
                    for url, body in vtt_dict.items():
                        log(f"    VTT 캡처: {url[:60]}")
                        combined.append(parse_vtt(body))
                    content = '\n'.join(filter(None, combined))
                    log(f"    ✅ VTT 텍스트 ({len(content)}자)")

            # ── 3c. 페이지 텍스트 last fallback ──────────
            if not content:
                log(f"    ⚠️  VTT도 없음 → 페이지 텍스트 수집")
                try:
                    raw_text = page.inner_text("[class*='content'], [class*='description'], main, article")
                    content = raw_text[:3000] if raw_text else "(내용 없음)"
                except:
                    content = "(추출 실패)"
                log(f"    📝 페이지 텍스트 ({len(content)}자)")

            videos_data.append((v_title, content))
            summary.append({'chapter': full_title, 'title': v_title, 'chars': len(content)})
            time.sleep(0.5)

        # 챕터 파일 저장
        if videos_data:
            save_chapter(full_title, videos_data)

    # ── 4. 요약 출력 ──────────────────────────────────────
    log(f"\n{'='*55}")
    log(f"📋 추출 완료 — {OUT_DIR}")
    log(f"{'='*55}")
    for item in summary:
        status = "✅" if item['chars'] > 100 else "⚠️ "
        log(f"  {status} {item['chapter']} / {item['title']} ({item['chars']}자)")

    page.close()
    browser.close()
