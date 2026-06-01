# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    page = ctx.new_page()

    page.goto("https://viewtrap.com/training-room", wait_until="networkidle", timeout=30000)

    data = page.evaluate("""async () => {
        const r = await fetch('https://api.viewtrap.com/api/v2/vod/revise/lectures', {credentials:'include'});
        return await r.json();
    }""")

    # 전체 구조 저장
    with open('viewtrap_api_dump.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 핵심 구조만 출력
    print("=== 최상위 키 ===")
    if isinstance(data, dict):
        print(list(data.keys()))
        root = data.get('data', data)
    else:
        root = data

    if isinstance(root, list) and root:
        item0 = root[0]
        print("\n=== 루트 item 키 ===")
        print(list(item0.keys()))

        # curriculumId 위치 확인
        print(f"\ncurriculumId: {item0.get('curriculumId') or item0.get('_id','없음')}")
        print(f"title: {item0.get('title','')}")

        chapters = item0.get('chapters', [])
        print(f"\n챕터 수: {len(chapters)}")
        if chapters:
            ch0 = chapters[0]
            print(f"챕터 키: {list(ch0.keys())}")
            videos = ch0.get('videos', [])
            if videos:
                v0 = videos[0]
                print(f"\n강의 키: {list(v0.keys())}")
                print(f"videoKey: {v0.get('videoKey','없음')}")
                print(f"_id: {v0.get('_id','없음')}")
                print(f"description: {str(v0.get('description','없음'))[:200]}")

    page.close()
    browser.close()
    print("\n✅ viewtrap_api_dump.json 저장 완료")
