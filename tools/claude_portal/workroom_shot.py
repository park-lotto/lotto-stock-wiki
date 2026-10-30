"""숏템 작업실 탭 점검(관제 291) — 회원 PC 화면(local_ui)을 열어 세 탭을 차례로 눌러 캡처하고 숫자로 먼저 거른다.

    py tools/claude_portal/workroom_shot.py <화면 주소(?t= 포함)> <저장 폴더>

탭마다: 보이는 칸(설정 단계바·진행 카드·후보 썸네일 수·깨진 그림 수)을 세고, 긴 변 1000px 로 줄인 캡처를 남긴다.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

COUNT = """() => {
  const vis = el => !!el && el.offsetParent !== null;
  const imgs = [...document.querySelectorAll('#wrun img, #wof img')].filter(vis);
  return {
    tabs: [...document.querySelectorAll('#wtabs .wtab')].map(b => b.textContent.trim()),
    on: (document.querySelector('#wtabs .wtab.on') || {}).textContent,
    steps_visible: vis(document.getElementById('steps')),
    run_cards: [...document.querySelectorAll('#wrun .wcard')].filter(vis).length,
    jobs: document.querySelectorAll('.witem').length,
    thumbs: [...document.querySelectorAll('#wof .wthumb')].filter(vis).length,
    yes: document.querySelectorAll('#wof .wthumb.yes').length,
    no: document.querySelectorAll('#wof .wthumb.no').length,
    imgs: imgs.length,
    broken: imgs.filter(i => i.complete && i.naturalWidth === 0).map(i => i.src).slice(0, 5),
    text: (document.querySelector('#wrun:not([hidden]) .wcard:last-child, #wof:not([hidden]) .wcard') || {}).innerText?.slice(0, 300) || '',
  };
}"""


def main(url: str, out: str) -> int:
    o = Path(out)
    o.mkdir(parents=True, exist_ok=True)
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1500, "height": 1000})
        errs: list[str] = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto(url)
        pg.wait_for_selector("#wtabs", timeout=15000)
        for t in ("set", "run", "of"):
            pg.click(f'#wtabs [data-t="{t}"]')
            pg.wait_for_timeout(3500)
            res[t] = pg.evaluate(COUNT)
            f = o / f"tab_{t}.png"
            pg.screenshot(path=str(f), full_page=True)
            try:
                from PIL import Image
                im = Image.open(f)
                k = 1000 / max(im.size)
                if k < 1:
                    im.resize((int(im.width * k), int(im.height * k))).save(f)
            except ImportError:
                pass
        res["page_errors"] = errs
        b.close()
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
