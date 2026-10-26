"""폰 화면 점검 (관제 276) — 라이브 화면을 폰 크기로 열어 '밀어도 닿지 않는 잘림'을 센다.

가로 스크롤 띠(메뉴·탭) 안에서 화면 밖으로 나간 것은 손가락으로 밀면 보이므로 결함이 아니다.
결함 = 화면 밖으로 나갔는데 조상 중에 가로로 밀 수 있는 상자가 하나도 없는 요소.

    py tools/mobile_audit.py                 # 전 화면, 결과 표 + %TEMP%/mobile_audit/*.png + sheet.png
    py tools/mobile_audit.py produce /       # 몇 화면만
    py tools/mobile_audit.py --width 360     # 더 좁은 폰
"""
import json
import tempfile
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PAGES = ["", "produce", "refs", "discover", "overseas_ref", "fav_channels", "collection",
         "archive", "scene_library", "shortem_packs", "shortem_preset", "meme_pack",
         "cardnews", "yt_studio", "challenge", "help", "fx_samples", "outreach"]

JS = r"""() => {
  const vw = innerWidth;
  const scroller = el => {
    for (let p = el.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && p.scrollWidth > p.clientWidth + 1) return true;
    }
    return false;
  };
  const hidden = el => {
    for (let p = el; p; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.visibility === 'hidden' || cs.opacity === '0' || cs.display === 'none') return true;
    }
    return false;
  };
  // 일부러 '…'으로 줄인 글자 자리(text-overflow:ellipsis)는 설계다 — 잘림으로 안 센다
  const ellipsis = el => {
    for (let p = el; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.textOverflow === 'ellipsis' && cs.overflowX === 'hidden') return true;
    }
    return false;
  };
  const bad = [];
  for (const el of document.querySelectorAll('body *')) {
    const b = el.getBoundingClientRect();
    if (b.width < 2 || b.height < 2) continue;
    if (b.right <= vw + 2 && b.left >= -2) continue;
    if (b.left >= vw || b.right <= 0) { /* 완전히 밖 = 닫힌 서랍·슬라이드일 수 있다 */ }
    if (scroller(el) || hidden(el) || ellipsis(el)) continue;
    if (bad.some(o => o.contains(el))) continue;
    bad.push(el);
  }
  const desc = el => {
    const b = el.getBoundingClientRect();
    const id = el.id ? '#' + el.id : '';
    const cls = (el.className && typeof el.className === 'string') ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
    return {sel: el.tagName.toLowerCase() + id + cls, left: Math.round(b.left), right: Math.round(b.right),
            w: Math.round(b.width), text: (el.innerText || '').trim().slice(0, 30)};
  };
  const taps = [...document.querySelectorAll('button,a,[role=button],input,select')].filter(e => {
    const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0 && b.height < 32 && !hidden(e);
  }).length;
  return {path: location.pathname, vw, page_scroll: document.documentElement.scrollWidth - vw,
          cut: bad.length, cut_list: bad.slice(0, 12).map(desc), small_taps: taps};
}"""


def audit(pages, width=390, height=844, out_dir=None):
    from tools.live_admin import admin_page
    out_dir = out_dir or os.path.join(tempfile.gettempdir(), "mobile_audit")   # 캡처는 저장소에 안 남긴다
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for p in pages:
        try:
            with admin_page(p, viewport=(width, height)) as pg:
                pg.wait_for_timeout(2500)
                r = pg.evaluate(JS)
                r["shot"] = os.path.join(out_dir, (p.replace("/", "_") or "home") + ".png")
                pg.screenshot(path=r["shot"])
        except Exception as e:
            r = {"path": "/" + p, "error": str(e)[:200]}
        rows.append(r)
        print(f"{r['path']:<18} 잘림 {r.get('cut', '?'):>3}  페이지가로 {r.get('page_scroll', '?'):>4}  작은버튼 {r.get('small_taps', '?'):>3}"
              + (f"  오류 {r['error']}" if "error" in r else ""))
        for c in r.get("cut_list", [])[:5]:
            print(f"    - {c['sel'][:50]}  [{c['left']}~{c['right']}]  {c['text']}")
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)
    _sheet([r["shot"] for r in rows if r.get("shot")], os.path.join(out_dir, "sheet.png"))
    return rows


def _sheet(paths, dst, per_row=6):
    from PIL import Image
    ims = [Image.open(x) for x in paths if os.path.exists(x)]
    if not ims:
        return
    w, h = ims[0].size
    rows = (len(ims) + per_row - 1) // per_row
    s = Image.new("RGB", (per_row * (w + 10), rows * (h + 10)), "white")
    for i, im in enumerate(ims):
        s.paste(im, ((i % per_row) * (w + 10), (i // per_row) * (h + 10)))
    s.thumbnail((1800, 1800))
    s.save(dst)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = sys.argv[1:]
    width = 390
    if "--width" in args:
        i = args.index("--width")
        width = int(args[i + 1])
        del args[i:i + 2]
    pages = [a.strip("/") for a in args] or PAGES
    rows = audit(pages, width=width)
    total = sum(r.get("cut", 0) for r in rows)
    print(f"\n합계: 잘림 {total} · 페이지 가로 스크롤 {sum(1 for r in rows if r.get('page_scroll', 0) > 0)}화면")
