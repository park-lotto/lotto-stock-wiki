# -*- coding: utf-8 -*-
"""숏템팩 화면(관제 222)을 실제 브라우저로 열어 잰다 — 사이드바 묶음·세부 팩 칸·개수·들어 보기 주소·그림·오류.

사용:
  로컬  py tools/shortem_packs/check_page.py --base http://127.0.0.1:8897      (세션 없는 로컬 요청은 관리자로 통과)
  라이브 py tools/shortem_packs/check_page.py --live                            (tools/live_admin 관리자 세션)
  --shot <png> 화면 저장 · --min 팩=개수 … 최소 개수(라이브에서 짤·서랍처럼 DB 에 있는 팩을 잴 때)
"""
import argparse, json, sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

WANT = ["sfx", "drawer", "bgm", "voice", "caption", "motion", "caption-parts", "mograph", "deco", "template", "meme", "font", "fxsample"]
SIDEBAR = ["전체 보기", "효과음팩", "효과음 서랍", "배경음", "성우", "자막 스타일", "등장 효과팩", "모션그래픽팩", "스티커·배지·도형", "템플릿", "감정짤팩", "글꼴", "효과 견본(에펙)"]

JS = r"""async()=>{
  for(let i=0;i<80&&!window.__shortemPacksReady;i++)await new Promise(r=>setTimeout(r,250));
  await new Promise(r=>setTimeout(r,1500));
  const secs=[...document.querySelectorAll('section[data-pack]')].map(s=>({id:s.id,count:s.dataset.count,title:s.querySelector('h2').childNodes[0].textContent}));
  const group=[...document.querySelectorAll('.ss-group')].find(g=>g.querySelector('.ss-label')?.textContent==='숏템팩');
  const items=group?[...group.querySelectorAll('.ss-item')].filter(e=>e.style.display!=='none').map(e=>e.textContent.replace(/^\S+\s/,'')):[];
  const plays=[...document.querySelectorAll('[data-play]')].map(b=>b.dataset.play);
  const pick=[...new Set(plays.map(u=>u.split('/').slice(0,4).join('/')))].map(p=>plays.find(u=>u.startsWith(p)));
  const status={};for(const u of pick){try{const r=await fetch(u);status[u]=r.status;}catch(e){status[u]='err';}}
  // 보일 때만 받는 그림 — 끝까지 내리며 다 달리게 한 뒤 센다
  const t0=performance.now();
  for(let y=0;y<document.body.scrollHeight;y+=700){scrollTo(0,y);await new Promise(r=>setTimeout(r,120));}
  for(let i=0;i<60;i++){const all=[...document.images];if(all.every(im=>!im.dataset.src&&im.complete))break;await new Promise(r=>setTimeout(r,500));}
  const all=[...document.images],loaded=all.filter(i=>i.naturalWidth>0).length;
  const broken=all.filter(i=>i.getAttribute('src')&&i.complete&&i.naturalWidth===0).map(i=>i.src).slice(0,5);
  const pending=all.filter(i=>i.dataset.src).length,imgMs=Math.round(performance.now()-t0);
  // 글꼴 견본은 눌러야 받는다 — 앞 3개만 눌러 본다
  [...document.querySelectorAll('#font [data-font]')].slice(0,3).forEach(el=>el.click());
  for(let i=0;i<40;i++){if([...document.querySelectorAll('#font .sample')].slice(0,3).every(e=>e.textContent==='숏템 123 Aa'))break;await new Promise(r=>setTimeout(r,500));}
  const fontsLoaded=[...document.fonts].filter(f=>/^SP\d+$/.test(f.family)&&f.status==='loaded').length;
  scrollTo(0,0);
  const mg=[...document.querySelectorAll('[data-mg] canvas')].map(c=>{const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=4)if(d[i])n++;return n});
  const capFonts=[...document.querySelectorAll('#caption .sample')].map(e=>({f:getComputedStyle(e).fontFamily,ok:document.fonts.check('20px '+getComputedStyle(e).fontFamily.split(',')[0])}));
  return {secs,items,plays:plays.length,status,broken,mg,capFonts,grid:document.querySelectorAll('.card').length,imgs:all.length,loaded,pending,imgMs,fontsLoaded,readyMs:window.__shortemReadyMs};
}"""


def run(page, url, shot):
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url, wait_until="load")   # 라이브는 폴링이 있어 networkidle 이 안 온다
    out = page.evaluate(JS)
    # 사이드바 세부 항목을 눌러 그 칸으로 가는지(같은 화면 안 이동)
    page.locator(".ss-item", has_text="배경음").first.click()
    page.wait_for_timeout(800)
    out["afterClick"] = page.evaluate("()=>({hash:location.hash,top:Math.round(document.querySelector('#bgm').getBoundingClientRect().top)})")
    if shot:
        page.screenshot(path=shot, full_page=False)
    out["errors"] = errors
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--shot")
    ap.add_argument("--min", nargs="*", default=[])
    a = ap.parse_args()
    if a.live:
        from tools.live_admin import admin_page
        with admin_page("shortem_packs") as pg:
            out = run(pg, pg.url, a.shot)
    else:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1500, "height": 1000})
            out = run(pg, a.base.rstrip("/") + "/shortem_packs", a.shot)
            b.close()
    fails = []
    got = [s["id"] for s in out["secs"]]
    print("칸:", [(s["id"], s["count"]) for s in out["secs"]])
    print("사이드바 숏템팩:", out["items"])
    print("들어 보기 칩", out["plays"], "· 주소 응답", out["status"], "· 깨진 그림", out["broken"], "· 카드", out["grid"])
    print("그림", out["loaded"], "/", out["imgs"], "· 안 달린 것", out["pending"], "· 끝까지 내려 다 뜨는 데", out["imgMs"], "ms · 글꼴 견본 받은 것", out["fontsLoaded"], "· 화면 준비", out["readyMs"], "ms")
    print("모션그래픽 미리보기 칠한 픽셀", out["mg"], "· 자막 스타일 글꼴", out["capFonts"])
    print("배경음 항목 클릭 →", out["afterClick"], "· 오류", out["errors"])
    if got != WANT: fails.append(f"칸이 다르다 {got}")
    if out["items"] != SIDEBAR: fails.append(f"사이드바 숏템팩 항목이 다르다 {out['items']}")
    if any(v != 200 for v in out["status"].values()): fails.append(f"들어 보기 주소 실패 {out['status']}")
    if out["broken"]: fails.append(f"깨진 그림 {out['broken']}")
    if out["pending"] or out["loaded"] < out["imgs"]: fails.append(f"끝까지 내려도 안 뜬 그림 {out['imgs'] - out['loaded']}")
    if not out["fontsLoaded"]: fails.append("글꼴 견본을 하나도 안 받았다")
    if (out["readyMs"] or 0) > 8000: fails.append(f"화면 준비가 느리다 {out['readyMs']}ms")
    if not out["mg"] or min(out["mg"]) == 0: fails.append("모션그래픽 미리보기가 비었다")
    if not all(f["ok"] for f in out["capFonts"]): fails.append(f"자막 스타일 글꼴 미적재 {out['capFonts']}")
    if out["afterClick"]["hash"] != "#bgm" or abs(out["afterClick"]["top"]) > 120: fails.append("사이드바 배경음을 눌러도 그 칸으로 안 간다")
    if out["errors"]: fails.append(f"화면 오류 {out['errors']}")
    counts = {s["id"]: s["count"] for s in out["secs"]}
    for rule in a.min:
        k, n = rule.split("=")
        import re
        first = int((re.findall(r"\d+", counts.get(k, "0")) or ["0"])[-1])
        if first < int(n): fails.append(f"{k} 개수 {counts.get(k)} < {n}")
    for s in out["secs"]:
        if s["id"] not in ("meme", "drawer", "fxsample") and s["count"].startswith("0"):
            fails.append(f"{s['id']} 가 0개")
    print("\n결과:", "통과" if not fails else "실패")
    for f in fails:
        print("  ✗", f)
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
