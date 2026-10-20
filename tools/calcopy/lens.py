# -*- coding: utf-8 -*-
"""구글 렌즈(PC, 무료·로그인 불필요) — 사진 한 장 → 렌즈가 보여 준 결과 [{href, text, shop}] (관제 097).

주인 함수 = lens_rows. 쓰는 곳:
  · channel/hottemreport/현장썰하이브리드/렌즈쿠팡.py — 같은 제품 찾기(쇼핑 결과만, 영상 사이트는 skip)
  · tools/calcopy/origin_find.py — 같은 영상 찾기(유튜브·틱톡·인스타를 남긴다)
결과는 <a href> 가 아니라 페이지 속 데이터에 "주소","제목" 쌍으로 들어 있다(10-18 실측).
"""
from __future__ import annotations

import html as H
import re
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILE = str(ROOT / ".lens_profile")   # 렌즈는 로그인이 필요 없다 — 다른 도구 프로필과 안 겹치게 따로
SKIP_SHOP = re.compile(r"google|gstatic|coupangcdn|youtube|googleusercontent|instagram|blog\.naver|zdnet")
SKIP_VIDEO = re.compile(r"google\.|gstatic|googleusercontent|ytimg|ggpht|coupangcdn")   # 영상 찾기: 유튜브·틱톡·인스타는 남긴다


def lens_rows(pg, img: str, skip: re.Pattern = SKIP_SHOP, hl: str = "ko") -> list[dict]:
    """사진 한 장 → [{href, text, shop}]. hl = 구글 화면 언어(en 이면 해외 결과가 위로 — snowball 10-21)."""
    pg.goto(f"https://www.google.com/?hl={hl}", wait_until="domcontentloaded", timeout=40000)
    pg.wait_for_timeout(1500)
    for sel in ['div[aria-label="이미지로 검색"]', 'div[aria-label="Search by image"]']:
        if pg.locator(sel).count():
            pg.locator(sel).first.click()
            break
    pg.wait_for_timeout(1500)
    # 페이지에 file 칸이 여럿이라 첫 칸에 넣으면 안 올라간다(10-18 실측) → '파일을 업로드'를 눌러 뜨는 선택 창으로
    with pg.expect_file_chooser(timeout=15000) as fc:
        pg.get_by_text(re.compile("파일을 업로드|upload a file", re.I)).first.click()
    fc.value.set_files(str(Path(img).resolve()))
    pg.wait_for_url(re.compile(r"(lens|search)"), timeout=40000)
    pg.wait_for_timeout(7000)
    for _ in range(6):
        pg.mouse.wheel(0, 1500)
        pg.wait_for_timeout(700)
    raw = H.unescape(pg.content())
    seen, rows = set(), []
    for m in re.finditer(r'"(https?://[^"\s]+)","([^"]{4,200})"', raw):
        h, t = m.group(1).split("\\u0026")[0].replace("\\u003d", "="), m.group(2)
        shop = re.sub(r"^https?://(www\.|m\.)?", "", h).split("/")[0]
        if h in seen or skip.search(shop) or t.startswith("http"):
            continue
        seen.add(h)
        rows.append({"href": h, "text": t, "shop": shop})
    return rows


@contextmanager
def lens_page():
    """렌즈용 크롬 한 창(화면 뜸 — 헤드리스는 구글이 막는다)."""
    import os
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        def launch(prof):
            return p.chromium.launch_persistent_context(prof, headless=False, channel="chrome", locale="ko-KR",
                                                        viewport={"width": 1366, "height": 900},
                                                        args=["--disable-blink-features=AutomationControlled"])
        try:
            ctx = launch(PROFILE)
        except Exception as e:  # noqa: BLE001 — 프로필이 다른 세션 크롬에 잠김('기존 브라우저 세션에서 여는 중', 10-21 워커 5명+원본찾기 충돌)
            # 렌즈는 로그인이 필요 없어 빈 프로필이면 된다 → 이 프로세스 전용 사본 이름으로 연다(경보 한 줄 남김)
            alt = f"{PROFILE}_{os.getpid()}"
            print(f"[lens] 프로필 잠김 → {Path(alt).name} 로 연다 ({type(e).__name__})")
            ctx = launch(alt)
        else:
            alt = None
        try:
            yield ctx.pages[0] if ctx.pages else ctx.new_page()
        finally:
            ctx.close()
            if alt:
                import shutil
                shutil.rmtree(alt, ignore_errors=True)   # 사본은 한 번 쓰고 지운다(쌓이지 않게)
