# -*- coding: utf-8 -*-
"""글꼴별 실측 보정값을 잰다 → tools/scene_font_research/scene_font_metrics.json (install_scene_fonts.py가 FONT_SETS에 같이 적는다)

  py tools/scene_font_research/measure_scene_font_metrics.py      (8773 서버 필요 — 편집기 페이지의 @font-face로 실제 로드해서 잰다)
재는 법(조사 단계에서 검증): 글자 하나씩 잉크 높이를 재서 중앙값. 문장 전체로 재면 삐침 긴 글자 하나가 배율을 깎는다.
  scale = 기준 글꼴(편집기 기본 SBAggroB — 템플릿 좌표가 이 글꼴에 맞춰져 있다)의 글자 높이 ÷ 이 글꼴의 글자 높이
  dy    = 잉크 중심이 줄 가운데에서 벗어난 만큼(em, +면 아래로 내려야 함) — 기준 글꼴과의 차이만 적는다
"""
import sys, json, pathlib
from playwright.sync_api import sync_playwright
HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_research_html import CANDIDATES  # noqa: E402
REF = 'SBAggroB'
JS = """async fams=>{const c=document.createElement('canvas').getContext('2d'),S=200,med=a=>{a=[...a].sort((x,y)=>x-y);return a[a.length>>1]},out={};
  for(const f of fams){await document.fonts.load(`40px "${f}"`,'건망증환자');if(!document.fonts.check(`40px "${f}"`,'건망증환자'))throw new Error('글꼴 로드 실패 '+f);
    c.font=`${S}px "${f}"`;const per=[...'건망증환자를살려낸일본천재의발명품'].map(ch=>{const m=c.measureText(ch);return {h:m.actualBoundingBoxAscent+m.actualBoundingBoxDescent,cy:(m.actualBoundingBoxAscent-m.actualBoundingBoxDescent)/2,fc:(m.fontBoundingBoxAscent-m.fontBoundingBoxDescent)/2}});
    out[f]={h:med(per.map(x=>x.h))/S,off:(med(per.map(x=>x.cy))-per[0].fc)/S}}
  return out}"""
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto('http://127.0.0.1:8773/out/scene-style-ui-showcase.html?qa=1', wait_until='networkidle')
    m = pg.evaluate(JS, [REF] + [f'Scene{pid}' for pid, *_ in CANDIDATES]); b.close()
ref = m[REF]; res = {}
for pid, name, *_ in CANDIDATES:
    x = m[f'Scene{pid}']
    # 배율은 0.85~1.35로 묶는다 — 손글씨처럼 원래 가는 글꼴을 억지로 같은 높이로 키우면 칸을 넘어 폭 맞춤이 다시 줄인다
    res[f'f{pid}'] = {'scale': round(min(1.35, max(.85, ref['h'] / x['h'])), 3), 'dy': round(x['off'] - ref['off'], 3), 'h': round(x['h'], 3)}
    print(f"{name:16s} 글자높이비 {x['h']:.3f}  scale ×{res[f'f{pid}']['scale']:.3f}  dy {res[f'f{pid}']['dy']:+.3f}em")
print(f'기준 {REF} 글자높이비 {ref["h"]:.3f}')
(HERE / 'scene_font_metrics.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
