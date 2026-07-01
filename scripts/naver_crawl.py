"""네이버 종토방 본문 / 종목뉴스 Playwright 크롤 — 서버에서 subprocess로 격리 호출.
uvicorn 이벤트루프에서 Playwright 반복실행이 불안정해 별도 프로세스로 분리(하드 타임아웃).
사용: python naver_crawl.py '{"mode":"bodies","code":"047040","nids":["123",...]}'
      python naver_crawl.py '{"mode":"news","code":"047040"}'
출력: JSON (bodies={nid:본문}, news=[제목요약,...])
"""
import sys
import json
import re
import asyncio

try:
    sys.stdout.reconfigure(encoding="utf-8")   # Windows cp949 콘솔에서 한글·특수문자 출력
except Exception:
    pass

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/120 Safari/537.36")


async def _render(urls, selector):
    """urls=[(key,url)] → {key:[텍스트,...]} 병렬 렌더링(이미지/CSS/폰트 차단)."""
    from playwright.async_api import async_playwright
    out = {}
    async with async_playwright() as pw:
        br = await pw.chromium.launch(headless=True)
        ctx = await br.new_context(user_agent=_UA)

        async def _block(route):
            if route.request.resource_type in ("image", "media", "font", "stylesheet"):
                await route.abort()
            else:
                await route.continue_()
        await ctx.route("**/*", _block)

        async def _one(key, url):
            texts = []
            try:
                pg = await ctx.new_page()
                await pg.goto(url, wait_until="domcontentloaded", timeout=15000)
                await pg.wait_for_selector(selector, timeout=8000)
                for el in await pg.query_selector_all(selector):
                    t = ((await el.inner_text()) or "").strip()
                    if t:
                        texts.append(re.sub(r"\s+", " ", t))
                await pg.close()
            except Exception:
                pass
            out[key] = texts
        await asyncio.gather(*[_one(k, u) for k, u in urls])
        await br.close()
    return out


def main():
    req = json.loads(sys.argv[1])
    mode, code = req["mode"], req["code"]
    if mode == "bodies":
        nids = req.get("nids", [])
        urls = [(n, f"https://m.stock.naver.com/pc/domestic/stock/{code}/discussion/{n}") for n in nids]
        res = asyncio.run(_render(urls, '[class*="content"]'))
        out = {}
        for nid, texts in res.items():
            best = ""
            for t in texts:
                if 15 <= len(t) <= 1200 and (not best or len(t) < len(best)):
                    best = t
            if best:
                out[nid] = best[:700]
        print(json.dumps(out, ensure_ascii=False))
    elif mode == "news":
        res = asyncio.run(_render(
            [("news", f"https://m.stock.naver.com/domestic/stock/{code}/news")],
            '[class*="NewsList"] a'))
        items, seen = [], set()
        for t in res.get("news", []):
            if len(t) < 12:
                continue
            k = t[:20]
            if k in seen:
                continue
            seen.add(k)
            items.append(t[:200])
        print(json.dumps(items, ensure_ascii=False))
    else:
        print("{}")


if __name__ == "__main__":
    main()
