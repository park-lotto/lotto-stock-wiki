# -*- coding: utf-8 -*-
"""카드뉴스 제작소 결과물 검사(관제 223) — 화면을 실제로 끝까지 눌러 **받은 파일**을 잰다.

    py tools/check_cardnews.py --base http://localhost:8901          # 로컬 서버(인증 꺼짐 = 관리자)
    py tools/check_cardnews.py --live                                 # 라이브(관리자 세션, tools/live_admin)
    py tools/check_cardnews.py --live --topics "주제1|주제2|주제3" --out out/cn_check

주제마다: 주제 입력 → 개요 만들기 → 이대로 만들기 → 편집기 → '전체 받기' ZIP을 실제로 받는다. 그리고
  ① ZIP 속 JPEG 장수 = 편집기 장수, 장마다 1080×1350(4:5)
  ② 글자 넘침 장 수 = 렌더러 fit 판정(편집기 레일의 '넘침' 표시)
  ③ 편집 미리보기 화면(캔버스 스크린샷) ↔ 받은 1번 JPEG(같은 크기로 줄여) 평균 픽셀 차 — 같은 렌더면 작다
  ④ 서버 글 검사(12가지) 중 '확인 필요(fail)' 개수
를 표로 찍는다. 판정 기준: ①전부 맞음 ②0 ③평균 차 < 14(0~255) — 하나라도 어기면 종료 코드 1.
"""
import argparse
import io
import os
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

DEFAULT_TOPICS = ["좁은 주방 수납 늘리는 정리 순서", "여름 전기요금 줄이는 생활 습관", "자취생 필수템 고르는 기준"]
DIFF_MAX = 14.0


def _mean_diff(png_bytes, jpg_bytes):
    from PIL import Image, ImageChops, ImageStat
    a = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    b = Image.open(io.BytesIO(jpg_bytes)).convert("RGB").resize(a.size, Image.LANCZOS)
    st = ImageStat.Stat(ImageChops.difference(a, b))
    return sum(st.mean) / 3.0


def run_topic(pg, topic, out_dir, idx):
    from PIL import Image
    pg.click("#tab-make")
    pg.wait_for_selector("[data-kind=topic]")
    pg.click("[data-kind=topic]")
    pg.fill("#mkTopic", topic)
    t0 = time.time()
    pg.click("[data-act=outline]")
    pg.wait_for_selector("[data-act=build]", timeout=120_000)
    t_ol = time.time() - t0
    n_outline = pg.locator(".olr").count()
    pg.click("[data-act=build]")
    pg.wait_for_selector("#canvas .cn-card", timeout=180_000)
    t_build = time.time() - t0
    pg.wait_for_timeout(1500)
    n_slides = pg.locator("[data-slot]").count()
    over = [int(e.get_attribute("data-ov")) + 1 for e in pg.locator("[data-ov]").all() if (e.inner_text() or "").strip()]
    fails = pg.evaluate("""() => { const it=[...document.querySelectorAll('.ck .s.fail')]; return it.length; }""")
    shot = pg.locator("#canvas").screenshot()
    pg.screenshot(path=os.path.join(out_dir, "%02d_editor.png" % idx), full_page=True)
    # 1번 장으로 가서 캔버스를 다시 찍는다(대조 기준)
    pg.click("[data-slot='0']")
    pg.wait_for_timeout(500)
    shot = pg.locator("#canvas").screenshot()
    with open(os.path.join(out_dir, "%02d_canvas1.png" % idx), "wb") as fh:
        fh.write(shot)
    with pg.expect_download(timeout=120_000) as dl:
        pg.click("[data-act=dlZip]")
    path = dl.value.path()
    zbytes = open(path, "rb").read()
    with open(os.path.join(out_dir, "%02d.zip" % idx), "wb") as fh:
        fh.write(zbytes)
    z = zipfile.ZipFile(io.BytesIO(zbytes))
    jpgs = sorted(n for n in z.namelist() if n.lower().endswith(".jpg"))
    sizes = []
    for n in jpgs:
        im = Image.open(io.BytesIO(z.read(n)))
        sizes.append(im.size)
    diff = _mean_diff(shot, z.read(jpgs[0])) if jpgs else 999
    ok = (len(jpgs) == n_slides and all(s == (1080, 1350) for s in sizes) and not over and diff < DIFF_MAX)
    return {"topic": topic, "outline": n_outline, "slides": n_slides, "jpgs": len(jpgs),
            "sizes_ok": all(s == (1080, 1350) for s in sizes), "overflow": over, "fails": fails,
            "diff": round(diff, 2), "caption": "caption.txt" in z.namelist(),
            "t_outline": round(t_ol, 1), "t_build": round(t_build, 1), "ok": ok}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--topics", default="|".join(DEFAULT_TOPICS))
    ap.add_argument("--out", default=os.path.join(ROOT, "out", "cn_check"))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    topics = [t.strip() for t in a.topics.split("|") if t.strip()]
    rows = []
    if a.live:
        from tools.live_admin import admin_page
        cm = admin_page("cardnews", viewport=(1500, 1000))
    else:
        import contextlib
        from playwright.sync_api import sync_playwright

        @contextlib.contextmanager
        def _local():
            with sync_playwright() as p:
                b = p.chromium.launch()
                pg = b.new_page(viewport={"width": 1500, "height": 1000}, accept_downloads=True)
                pg.errors = []
                pg.on("pageerror", lambda e: pg.errors.append(str(e)[:200]))
                pg.goto(a.base.rstrip("/") + "/cardnews", wait_until="domcontentloaded")
                pg.wait_for_timeout(1500)
                try:
                    yield pg
                finally:
                    b.close()
        cm = _local()
    with cm as pg:
        pg.wait_for_selector("#tab-make", timeout=30_000)
        for i, t in enumerate(topics):
            try:
                rows.append(run_topic(pg, t, a.out, i + 1))
            except Exception as e:      # noqa: BLE001 — 한 주제 실패도 결과로 남긴다
                pg.screenshot(path=os.path.join(a.out, "%02d_error.png" % (i + 1)), full_page=True)
                rows.append({"topic": t, "ok": False, "error": repr(e)[:200]})
        errs = list(getattr(pg, "errors", []))
    bad = 0
    for r in rows:
        if r.get("error"):
            print("✕ %s — 실패 %s" % (r["topic"], r["error"]))
            bad += 1
            continue
        print("%s %s | 개요 %d장 → %d장 · JPEG %d장 %s · 넘침 %s · 미리보기↔파일 차 %.2f · 검사 확인필요 %d · 캡션 %s · %.0fs/%.0fs" % (
            "✓" if r["ok"] else "✕", r["topic"], r["outline"], r["slides"], r["jpgs"],
            "1080×1350" if r["sizes_ok"] else "크기 틀림", r["overflow"] or "0", r["diff"], r["fails"],
            "있음" if r["caption"] else "없음", r["t_outline"], r["t_build"]))
        bad += 0 if r["ok"] else 1
    print("화면 오류:", errs or "없음")
    print("결과: %d/%d 통과 · 파일 %s" % (len(rows) - bad, len(rows), a.out))
    return 1 if (bad or errs) else 0


if __name__ == "__main__":
    sys.exit(main())
