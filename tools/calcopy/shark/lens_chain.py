# -*- coding: utf-8 -*-
"""렌즈 따라가기 — 쇼츠 썸네일(또는 이미지 주소)을 구글 렌즈로 찾아 원본 방송·같은 소재 채널을 모은다 (관제 097, 2026-10-18).

사장님 10-18 "샤크탱크로 채널 검색해서 렌즈로 이동하고 계속 찾을 수 있잖아". 유료 렌즈 API(SerpApi) 금지 —
로그인된 전용 크롬(tools/google_browser.py 프로필)으로 lens.google.com/uploadbyurl 을 열어 화면의 링크를 읽는다.

    PYTHONUTF8=1 py tools/calcopy/shark/lens_chain.py <out.json> <유튜브id|이미지url|로컬 jpg 는 안 됨> ...
    LENS_TAB=시각적으로 일치하는 항목  (기본 '전체')
실측 10-19: 쇼츠 썸네일은 우리말 자막이 박혀 '정확히 일치' 0건, 사람이 크게 나온 썸네일은 렌즈가 옷을 잡아 쇼핑으로 샌다 —
제품·세트(샤크 의자)가 크게 보이는 장면 이미지(썸네일 대신 원본 프레임을 이미지 호스팅 주소로)일수록 원본·다른 편집본이 잡힌다.
'전체' 탭 YvOvlmKpxvQ → Haven Lock·Atlas Monroe·한국어 샤크탱크 틱톡/인스타 계정이 잡혔다.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.google_browser import google_page  # noqa: E402

YT_ID = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([\w-]{11})")


def img_of(x: str) -> str:
    return x if x.startswith("http") else f"https://i.ytimg.com/vi/{x}/hqdefault.jpg"


def lens(pg, img: str, wait=6.0) -> dict:
    pg.goto("https://lens.google.com/uploadbyurl?url=" + urllib.parse.quote(img, safe=""), wait_until="domcontentloaded")
    time.sleep(wait)
    # 탭: '시각적으로 일치하는 항목' — 같은 장면이 들어간 다른 편집본·원본. '정확히 일치'는 쇼츠 썸네일(우리 편집 글자 박힘)이라 0건,
    # '전체'는 사람 옷 쇼핑으로 샌다(10-19 실측 gcXNGxcCAfM)
    tab = os.environ.get("LENS_TAB", "전체")        # 전체 | 시각적으로 일치하는 항목 | 정확히 일치하는 결과
    if tab != "전체":
        try:
            pg.get_by_text(tab, exact=True).first.click(timeout=5000); time.sleep(4)
        except Exception:
            pass
    for _ in range(3):                       # 결과가 아래로 더 붙는다
        pg.mouse.wheel(0, 4000); time.sleep(1.2)
    links = pg.eval_on_selector_all("a[href]", "as => as.map(a => [a.href, (a.innerText||a.getAttribute('aria-label')||'').trim().slice(0,120)])")
    out, seen = [], set()
    for href, text in links:
        if "google." in href and "/url?" in href:          # 결과 링크는 구글을 거친다 → 실제 주소로 푼다
            qd = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = (qd.get("url") or qd.get("q") or [href])[0]
        goto = "google.com/goto?" in href                  # 렌즈 결과 링크 = 암호화된 goto(텍스트 = '출처 제목')
        if (href.startswith("https://www.google.") and not goto) or any(s in href for s in ("google.com/search?", "accounts.google", "support.google", "policies.google", "lens.google.com/")) or href in seen:
            continue
        seen.add(href)
        m = YT_ID.search(href)
        src = text.split(None, 1)[0] if goto and text else urllib.parse.urlparse(href).netloc
        out.append({"url": href, "text": text, "src": src or "", "goto": goto, "yt": m.group(1) if m else None})
    # 영상 출처(유튜브·틱톡·인스타)만 실제 주소로 푼다 — goto 를 열어 도착 주소를 읽는다(질의당 ≤12, 1초 간격)
    k = 0
    for o in out:
        if o["goto"] and o["src"] in ("YouTube", "TikTok", "Instagram", "Facebook") and k < 12:
            try:
                pg.goto(o["url"], wait_until="commit", timeout=15000); time.sleep(1.0)
                o["url"] = pg.url; m = YT_ID.search(o["url"]); o["yt"] = m.group(1) if m else None
            except Exception as e:
                o["resolve_err"] = str(e)[:80]
            k += 1
    return {"img": img, "n": len(out), "links": out}


def main():
    out = Path(sys.argv[1]); qs = sys.argv[2:]
    res = []
    with google_page() as pg:
        for q in qs:
            r = lens(pg, img_of(q)); r["q"] = q; res.append(r)
            print(q, r["n"], "개 링크 · 유튜브", sum(1 for l in r["links"] if l["yt"]), flush=True)
            time.sleep(2)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
