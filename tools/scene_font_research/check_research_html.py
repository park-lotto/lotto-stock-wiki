# -*- coding: utf-8 -*-
"""장면폰트_조사.html을 실제 브라우저로 열어 확인한다: 글꼴이 진짜 그 글꼴로 그려졌나(폴백 아님), 콘솔 오류, 선택·복사 동작, 화면 캡처.
   py tools/scene_font_research/check_research_html.py [캡처폴더]   (8773 서버가 떠 있어야 한다)"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
out = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.tmp/scene_font_research'); out.mkdir(parents=True, exist_ok=True)
URL = 'http://127.0.0.1:8773/out/%EC%9E%A5%EB%A9%B4%ED%8F%B0%ED%8A%B8_%EC%A1%B0%EC%82%AC.html'
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1500, 'height': 950})
    errs = []; pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None); pg.on('pageerror', lambda e: errs.append(str(e)))
    bad = []; pg.on('response', lambda r: bad.append((r.status, r.url)) if r.status >= 400 else None)
    pg.goto(URL); pg.wait_for_function('window.__fontsLoaded', timeout=90000)
    # 폴백 판정: 같은 글을 그 글꼴로 잰 폭과 폴백(sans-serif)으로 잰 폭이 같으면 글꼴이 안 먹은 것이다
    res = pg.evaluate('''()=>{const c=document.createElement('canvas').getContext('2d');c.font='100px sans-serif';const base=c.measureText('건망증환자를살려낸발').width;
      return DATA.fonts.map((f,i)=>{c.font=`100px "${f.id}"`;return {name:f.name,loaded:window.__fontsLoaded[i],w:c.measureText('건망증환자를살려낸발').width,base}})}''')
    fall = [r['name'] for r in res if r['loaded'] == 0 or abs(r['w'] - r['base']) < 0.01]
    print('글꼴', len(res), '폴백 의심', fall)
    pg.screenshot(path=str(out / '1_top.png'))
    # 크기 맞춤이 진짜 먹는지: 카드마다 1줄의 (글자 크기 x 실측 높이비)가 고르게 나와야 하고, 제목이 칸을 넘으면 안 된다
    def spread(on):
        pg.evaluate(f"document.querySelector('#norm').checked={'true' if on else 'false'};draw()"); pg.wait_for_timeout(300)
        v = pg.evaluate("""()=>DATA.fonts.map((f,i)=>{const ph=document.querySelectorAll('#fonts .pick')[i].querySelector('.phone'),l=ph.querySelector('.l1'),k=ph.querySelector('.l2 span');
          return {n:f.name,shrunk:ph.dataset.shrunk==='1',ink:parseFloat(getComputedStyle(l).fontSize)*M[f.id].h,over:Math.max(l.firstChild.getBoundingClientRect().width,k.getBoundingClientRect().width)>ph.getBoundingClientRect().width}})""")
        ks = [x['ink'] for x in v]; return round(max(ks) / min(ks), 3), [x['n'] for x in v if x['over']], [x['n'] for x in v if x['shrunk']]
    off, on = spread(False), spread(True)
    print('글자 높이 최대/최소 — 맞춤 끔', off[0], '칸 넘침', off[1]); print('글자 높이 최대/최소 — 맞춤 켬', on[0], '칸 넘침', on[1], '| 폭 때문에 줄인 글꼴', on[2])
    pg.locator('#fonts .pick').nth(0).click(); pg.locator('#fonts .pick').nth(2).click()
    pg.locator('#pals .pick').nth(3).click(); pg.locator('#trs .pick').nth(1).click()
    print('선택 뒤', pg.inner_text('#cF'), pg.inner_text('#cP'), pg.inner_text('#cT'), '|', pg.input_value('#outTxt').splitlines()[1:4])
    for i in range(3, 12): pg.locator('#fonts .pick').nth(i).click()
    print('10개 제한', pg.inner_text('#cF'), '|', pg.inner_text('#msg'))
    pg.reload(); pg.wait_for_function('window.__fontsLoaded'); print('새로고침 뒤 유지', pg.inner_text('#cF'))
    for sel, n in [('#fonts', '2_fonts'), ('#pals', '3_pals'), ('#trs', '4_trs'), ('#metrics', '5_metrics'), ('aside', '6_aside')]:
        pg.locator(sel).screenshot(path=str(out / f'{n}.png'))
    pg.click('#reset'); print('지운 뒤', pg.inner_text('#cF'))
    print('콘솔 오류', errs[:5]); print('실패 응답', bad[:5]); b.close()
