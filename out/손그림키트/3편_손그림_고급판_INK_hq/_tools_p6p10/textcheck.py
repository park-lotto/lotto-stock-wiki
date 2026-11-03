"""R4·R5 검사: 장면 template 를 헤드리스로 열어 S.texts·S.items(펜 선) 시간을 뽑는다.
R5 = 글자끼리 시간 겹침 0 / 펜 선(pen:true)과 글자 겹침 0. R4 = 마지막 글자 완성 시각(끝 -2.0 기준), 밑줄·동그라미 끝(끝 -1.2).
usage: py textcheck.py P6 P7 ...
"""
import sys, pathlib
from playwright.sync_api import sync_playwright
HQ = pathlib.Path(__file__).resolve().parent.parent
JS = """() => { const S = window.__S; const vis = (L) => { let a=-1e9,b=1e9; for (let x=L; x; x=x.parent) if (x.win) { a=Math.max(a,x.win[0]); b=Math.min(b,x.win[1]); } return [a,b]; };
 const T = S.texts.filter(t=>t.s>-50).map(t=>({s:t.s,e:t.end,txt:t.chars.map(c=>c.sp.textContent).join('')}));
 const P = S.items.filter(i=>i.pen && i.s>-50).map(i=>({s:i.s,e:i.s+i.dur,c:i.el.getAttribute('stroke')}));
 return {dur:S.dur,T,P}; }"""
with sync_playwright() as p:
    b = p.chromium.launch(channel='chrome')
    for sc in sys.argv[1:]:
        pg = b.new_page(viewport={'width': 1920, 'height': 1080})
        pg.goto((HQ / sc / 'template' / 'index.html').as_uri()); pg.wait_for_function('window.__S', timeout=20000)
        r = pg.evaluate(JS); D = r['dur']; T = sorted(r['T'], key=lambda t: t['s'])
        tt = [(a['txt'], b2['txt']) for i, a in enumerate(T) for b2 in T[i+1:] if b2['s'] < a['e'] - 0.02]
        tp = [(t['txt'], round(q['s'], 2)) for t in T for q in r['P'] if q['s'] < t['e'] - 0.02 and q['e'] > t['s'] + 0.02]
        last = max(t['e'] for t in T); marks = [q['e'] for q in r['P'] if q['c'] == '#F6A93B']
        print(f"{sc}: 글자겹침 {len(tt)} {tt[:3]} | 펜선-글자겹침 {len(tp)} {tp[:4]} | 마지막글자 {last:.2f} (기준 {D-2:.1f}) | 주황표시 끝 {max(marks) if marks else 0:.2f} (기준 {D-1.2:.1f})")
    b.close()
