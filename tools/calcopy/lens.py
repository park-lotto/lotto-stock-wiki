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


LENS_FEW = 20      # 결과 화면의 링크 쌍이 이보다 적으면 덜 뜬 것 — 기다려 내려 본다(실측: 다 뜨면 60)


def lens_rows(pg, img: str, skip: re.Pattern = SKIP_SHOP, hl: str = "ko", info: dict | None = None) -> list[dict]:
    """사진 한 장 → [{href, text, shop}]. hl = 구글 화면 언어(en 이면 해외 결과가 위로 — snowball 10-21)."""
    pg.goto(f"https://www.google.com/?hl={hl}", wait_until="domcontentloaded", timeout=40000)
    # 고정 1.5초 두 번 대신 버튼이 보이면 바로(10-27 — 장마다 3초)
    btn = pg.locator('div[aria-label="이미지로 검색"], div[aria-label="Search by image"]').first
    try:
        btn.wait_for(state="visible", timeout=8000)
        btn.click()
    except Exception:  # noqa: BLE001 — 버튼이 늦으면 예전처럼 기다렸다 한 번 더
        pg.wait_for_timeout(1500)
        for sel in ['div[aria-label="이미지로 검색"]', 'div[aria-label="Search by image"]']:
            if pg.locator(sel).count():
                pg.locator(sel).first.click()
                break
    up = pg.get_by_text(re.compile("파일을 업로드|upload a file", re.I)).first
    up.wait_for(state="visible", timeout=8000)
    # 페이지에 file 칸이 여럿이라 첫 칸에 넣으면 안 올라간다(10-18 실측) → '파일을 업로드'를 눌러 뜨는 선택 창으로
    with pg.expect_file_chooser(timeout=15000) as fc:
        up.click()
    fc.value.set_files(str(Path(img).resolve()))
    pg.wait_for_url(re.compile(r"(lens|search)"), timeout=40000)
    # 10-27 실측(샤넬 립라이너 4장): 영상 후보는 결과 주소가 뜬 순간에 이미 다 있다(바로 4·4·7·9 = 7초+스크롤 뒤 4·4·7·9, 새 것 0).
    #   예전엔 무조건 7초 + 스크롤 4.2초 = 장마다 11초(8장 ≈ 1.5분). 1.5초 뒤 읽고, 링크가 적을 때만 기다려 내려 본다
    pg.wait_for_timeout(1500)
    if len(re.findall(r'"(https?://[^"\s]+)","([^"]{4,200})"', pg.content())) < LENS_FEW:
        pg.wait_for_timeout(5500)
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
    if info is not None:
        info["overview"] = overview(pg)
    return rows


AI_OVERVIEW_JS = """()=>{const h=[...document.querySelectorAll('*')].find(e=>e.childElementCount===0&&/^(AI 개요|AI Overview)$/.test((e.textContent||'').trim()));
if(!h)return '';let b=h;for(let i=0;i<6&&b.parentElement;i++){b=b.parentElement;if((b.innerText||'').length>200)break}return (b.innerText||'').slice(0,700)}"""


def overview(pg, wait_ms: int = 3000) -> str:
    """렌즈 결과 'AI 개요' 글(사진 전체를 보고 쓴다 — 출연자·브랜드 이름이 나온다). 10-27 실측: c편 '니키튜토리얼(NikkieTutorials)'·
    a편 '미스 다시(Miss Darcei)'·'@tirtir_global' = 실제 원본 채널·브랜드. 렌즈 링크(물체 한 칸만 고른 결과)와 달리 장면 전체 기준이다."""
    t = 0
    while t < wait_ms:
        txt = pg.evaluate(AI_OVERVIEW_JS) or ""
        if len(txt) > 80:
            return " ".join(txt.split())
        pg.wait_for_timeout(300)
        t += 300
    return ""


NAME_PAREN = re.compile(r"[가-힣][가-힣 ·]{0,15}\(\s*([A-Za-z][A-Za-z0-9 ._'-]{1,30}?)\s*[,)]")
HANDLE = re.compile(r"@([A-Za-z0-9_.]{3,30})")


def overview_names(text: str) -> list[str]:
    """(판단 주인 — AI 개요에서 사람·계정 이름) '한글(영문)' 괄호 속 영문 + @계정만(사이트·상품 제목 잡음은 뺀다)."""
    out = []
    for n in NAME_PAREN.findall(text or "") + HANDLE.findall(text or ""):
        n = n.strip(" .")
        if len(n) >= 3 and n.lower() not in {x.lower() for x in out}:
            out.append(n)
    return out[:4]


def video_crops(p) -> list:
    """(주인) 영상 찾기 렌즈에 올릴 그림 = 소재 장면에서 한국 재편집이 덧붙인 것을 뺀 영상 부분 — ① 영상 띠(위아래 검정 여백·제목 띠 잘라 냄) ② 그 위 62%(아래 자막 줄 빼기).
    장면 통째로 올리면 구글이 핀셋·패치 같은 물건만 작게 골라 쇼핑 결과로 쏠린다(10-26 여드름 패치: 통째 후보 13·해외 원본 0 → 잘라 올리기 58·원본 Erin Noelle 틱톡).
    띠를 못 찾으면 원본 그대로 한 장."""
    import cv2
    import numpy as np
    img = cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return [p]
    rows = np.where(img.mean(axis=(1, 2)) > 25)[0]
    if not len(rows):
        return [p]
    runs, s = [], rows[0]
    for a, b in zip(rows, rows[1:]):
        if b - a > 6:
            runs.append((s, a)); s = b
    runs.append((s, rows[-1]))
    y0, y1 = max(runs, key=lambda r: r[1] - r[0])
    if y1 - y0 < img.shape[0] * 0.3:
        return [p]
    out = []
    for tag, crop in (("band", img[y0:y1]), ("top", img[y0:y0 + int((y1 - y0) * 0.62)])):
        q = p.with_name(f"{p.stem}_{tag}.jpg")
        cv2.imencode(".jpg", crop)[1].tofile(str(q))
        out.append(q)
    return out


@contextmanager
def lens_page(name: str = ""):
    """렌즈용 크롬 한 창(화면 뜸 — 헤드리스는 구글이 막는다). name = 프로필 꼬리(같은 프로세스에서 창 두 개를 동시에 — 렌즈 + 틱톡·인스타 검색, 10-27)."""
    import os
    import threading
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        def launch(prof):
            return p.chromium.launch_persistent_context(prof, headless=False, channel="chrome", locale="ko-KR",
                                                        viewport={"width": 1366, "height": 900},
                                                        args=["--disable-blink-features=AutomationControlled"] +
                                                             (["--window-position=-32000,-32000"] if os.environ.get("SHORTEM_BROWSER_OFFSCREEN") == "1" else []))   # 창은 뜨되 화면 밖(10-28 강의 시연 '창 띄우지 마라')
        try:
            ctx = launch(PROFILE + (f"_{name}" if name else ""))
        except Exception as e:  # noqa: BLE001 — 프로필이 다른 세션 크롬에 잠김('기존 브라우저 세션에서 여는 중', 10-21 워커 5명+원본찾기 충돌)
            # 렌즈는 로그인이 필요 없어 빈 프로필이면 된다 → 이 프로세스 전용 사본 이름으로 연다(경보 한 줄 남김)
            alt = f"{PROFILE}{'_' + name if name else ''}_{os.getpid()}_{threading.get_ident() % 100000}"
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
