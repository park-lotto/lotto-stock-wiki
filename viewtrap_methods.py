# -*- coding: utf-8 -*-
import sys, io, time, json, base64, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

LECTURE_URL = "https://viewtrap.com/business/lectures?curriculumId=69c49d3474de71e13f64ea7b&videoKey=VzXe3cXF"
API_BASE = "https://api.viewtrap.com/api/v2"

def decode_jwt(token):
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        return json.loads(base64.b64decode(payload).decode())
    except: return {}

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    api_responses = {}
    def on_response(resp):
        if "api.viewtrap.com" in resp.url:
            try: api_responses[resp.url] = resp.json()
            except: pass
    page.on("response", on_response)

    page.goto(LECTURE_URL, wait_until="networkidle")
    time.sleep(3)

    # ── 방법 1: viewtrap-ai API 탐색 ──────────────────────
    print("=" * 60)
    print("방법 1: viewtrap-ai API (AI 스크립트/요약)")
    print("=" * 60)
    ai_apis = [
        f"{API_BASE}/viewtrap-ai/revise/bpz/init",
        f"{API_BASE}/viewtrap-ai/revise/bpz?videoKey=VzXe3cXF",
        f"{API_BASE}/viewtrap-ai/lecture/script?videoKey=VzXe3cXF",
        f"{API_BASE}/viewtrap-ai/revise/script?videoKey=VzXe3cXF",
    ]
    for url in ai_apis:
        result = page.evaluate(f"""async () => {{
            const r = await fetch('{url}', {{credentials:'include'}});
            return {{status: r.status, body: await r.text()}};
        }}""")
        print(f"\n[{url.split('api/v2/')[1]}]")
        print(f"  Status: {result['status']}")
        print(f"  Body: {result['body'][:300]}")

    # ── 방법 2: 강의 목록 전체 가져오기 ───────────────────
    print("\n" + "=" * 60)
    print("방법 2: 강의 목록 API")
    print("=" * 60)
    lectures_data = page.evaluate(f"""async () => {{
        const r = await fetch('{API_BASE}/vod/revise/lectures', {{credentials:'include'}});
        return await r.json();
    }}""")
    if lectures_data.get('success') or lectures_data.get('data'):
        chapters = lectures_data.get('data', [{}])[0].get('chapters', [])
        total_videos = sum(len(ch.get('videos',[])) for ch in chapters)
        print(f"  총 챕터: {len(chapters)}개, 총 강의: {total_videos}개")
        for ch in chapters[:3]:
            print(f"  [{ch.get('label','')}] {ch.get('title','')} - {len(ch.get('videos',[]))}강")
            for v in ch.get('videos', [])[:2]:
                print(f"    - {v.get('title','')} | videoKey: {v.get('videoKey','N/A')} | key: {v.get('_id','')}")

    # ── 방법 3: Kollus iframe + 자막 탐색 ─────────────────
    print("\n" + "=" * 60)
    print("방법 3: Kollus 플레이어 분석")
    print("=" * 60)
    iframe_el = page.query_selector("iframe#kollus-player")
    if iframe_el:
        iframe_src = iframe_el.get_attribute("src")
        print(f"  Kollus iframe: {iframe_src[:100]}...")

        # JWT 디코딩
        jwt_match = re.search(r'jwt=([^&]+)', iframe_src)
        if jwt_match:
            decoded = decode_jwt(jwt_match.group(1))
            print(f"\n  JWT 내용: {json.dumps(decoded, ensure_ascii=False, indent=2)[:500]}")

    # Kollus iframe 내부 접근
    frames = page.frames
    print(f"\n  전체 frame 수: {len(frames)}")
    for fr in frames:
        if "kollus" in fr.url:
            print(f"  Kollus frame URL: {fr.url[:100]}")
            try:
                print(f"  frame 텍스트: {fr.inner_text('body')[:200]}")
                # 자막 탐색
                tracks = fr.query_selector_all("track")
                for t in tracks:
                    print(f"  자막 track: {t.get_attribute('src')} kind={t.get_attribute('kind')}")
                # m3u8 URL 탐색
                vids = fr.query_selector_all("video")
                for v in vids:
                    print(f"  video src: {v.get_attribute('src')}")
            except: pass

    # ── 방법 4: 토큰으로 Kollus API 직접 호출 ─────────────
    print("\n" + "=" * 60)
    print("방법 4: Kollus content_type 탐색")
    print("=" * 60)
    token_resp = page.evaluate(f"""async () => {{
        const r = await fetch('{API_BASE}/vod/revise/token?videoKey=VzXe3cXF&curriculumId=69c49d3474de71e13f64ea7b&mobileYn=N', {{credentials:'include'}});
        return await r.json();
    }}""")
    if token_resp.get('data', {}).get('token'):
        token = token_resp['data']['token']
        decoded = decode_jwt(token)
        print(f"  Kollus token 내용: {json.dumps(decoded, ensure_ascii=False, indent=2)[:800]}")

        # custom_key로 Kollus 직접 접근
        custom_key = token_resp['data'].get('custom_key','')
        kollus_urls = [
            f"https://api.kr.kollus.com/v1/media/content_provider/viewtrap/content_type?videoKey=VzXe3cXF",
            f"https://v.kr.kollus.com/s?jwt={token}&content_type=hls",
        ]
        for ku in kollus_urls:
            result = page.evaluate(f"""async () => {{
                try {{
                    const r = await fetch('{ku}', {{mode:'no-cors', credentials:'include'}});
                    return {{status: r.status, type: r.type}};
                }} catch(e) {{ return {{error: e.message}}; }}
            }}""")
            print(f"  [{ku[:60]}] -> {result}")

    page.close()
    browser.close()
