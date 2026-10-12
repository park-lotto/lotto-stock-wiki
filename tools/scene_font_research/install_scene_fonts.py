# -*- coding: utf-8 -*-
"""장면꾸미기 편집기용 글꼴 설치 — 후보 목록(build_research_html.CANDIDATES)이 정본이다.

하는 일
  1) 눈누 페이지 원문에 적힌 웹폰트 파일을 **배포된 형태 그대로**(woff/woff2) shopping_shorts/static/fonts/scene/ 에 받는다.
     ★변환하지 않는다 — 쿠키런 등 "배포 형태 그대로 사용·수정 금지" 조건이 있고, 편집기·렌더러는 둘 다 Chromium이라 웹폰트를 그대로 읽는다.
     (제작소 자막 경로 ffmpeg·PIL은 woff를 못 읽는다 → 이 글꼴들은 fonts.json에 넣지 않는다. 장면꾸미기 전용)
  2) 한글 글리프 누락·공백 글리프를 검사한다(08-26 두부 사고 재발 방지).
  3) out/scene-style-ui-showcase.html 의 @font-face 와 out/precision20-ui.js 의 FONT_SETS 를 표식 사이에서 다시 쓴다(여러 번 돌려도 같다).

  py tools/scene_font_research/install_scene_fonts.py          # 받기 + 검사 + 등록
  py tools/scene_font_research/install_scene_fonts.py --check  # 등록이 목록과 같은지만 검사(고치지 않음)
fontTools 필요: 프로젝트 .venv 의 python 으로 돌린다.
"""
import sys, re, json, pathlib, urllib.request
from fontTools.ttLib import TTFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from build_research_html import CANDIDATES, parse_page, UA  # noqa: E402

FONT_DIR = ROOT / 'shopping_shorts' / 'static' / 'fonts' / 'scene'
SHOWCASE = ROOT / 'out' / 'scene-style-ui-showcase.html'
UI = ROOT / 'out' / 'precision20-ui.js'
PROBE = '건망증환자를살려낸일본천재의발명품숏템메이커이거진짜좋아요뷁똠'
# 자막 짝: 제목 글꼴이 개성이 셀수록 자막은 읽기 쉬운 것으로(기존 FONT_SETS와 같은 원칙)
CAPTION = {'f82': 'Pretendard', 'f1381': 'GmarketSansBold', 'f461': 'BMJUA', 'f321': 'GmarketSansBold', 'f499': 'GmarketSansBold',
           'f1186': 'Pretendard', 'f1042': 'Pretendard', 'f427': 'BMJUA', 'f364': 'BMJUA', 'f876': 'Pretendard'}
# 문장부호가 통째로 없는 글꼴은 같은 집안 글꼴의 부호만 빌린다(unicode-range).
#   을지로체: ! ? , ' 등 전무 → 실제 채널 제목 93개 중 41개에 영향. 을지로10년후는 부호가 다 있다.
BORROW = {'f321': 'f499'}
PUNCT_RANGE = 'U+21-2F,U+3A-40,U+5B-60,U+7B-7E,U+B7,U+2018-201D,U+2026'
BEGIN_CSS, END_CSS = '    /* 장면폰트:시작 — tools/scene_font_research/install_scene_fonts.py 가 쓴다. 손으로 고치지 마라 */', '    /* 장면폰트:끝 */'
BEGIN_JS, END_JS = '    // 장면폰트:시작 — tools/scene_font_research/install_scene_fonts.py 가 쓴다. 손으로 고치지 마라', '    // 장면폰트:끝'


def plan():
    rows = []
    for pid, name, pick, mood in CANDIDATES:
        url, video, embed = parse_page(pid, pick)
        ext = url.rsplit('.', 1)[1].lower()
        rows.append({'id': f'f{pid}', 'family': f'Scene{pid}', 'name': name, 'url': url, 'file': f'{pid}_{url.rsplit("/", 1)[1]}', 'ext': ext})
    return rows


def fetch(rows):
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for r in rows:
        p = FONT_DIR / r['file']
        if not p.exists() or p.stat().st_size < 10000:
            p.write_bytes(urllib.request.urlopen(urllib.request.Request(r['url'], headers={'User-Agent': UA}), timeout=120).read())
        f = TTFont(str(p)); cmap = f.getBestCmap()
        miss = [c for c in PROBE if ord(c) not in cmap]
        space = cmap.get(32); adv = f['hmtx'][space][0] if space else 0
        r.update(size=p.stat().st_size, glyphs=len(cmap), miss=miss, space=adv)
        print(f"{r['size'] / 1024:7.0f}KB 글리프 {r['glyphs']:6d} 누락 {''.join(miss) or '없음':6s} 공백폭 {adv:5d}  {r['name']}")
    bad = [r['name'] for r in rows if [c for c in r['miss'] if c not in '뷁똠']]
    if bad:
        raise SystemExit(f'★한글 누락: {bad}')
    nospace = [r['name'] for r in rows if not r['space']]
    if nospace:
        # Chromium은 공백 글리프가 없으면 다음 글꼴의 공백을 쓴다(띄어쓰기는 나온다). 실제 폭은 check_editor_fonts.py가 브라우저에서 잰다
        print('공백 글리프 없음 — 브라우저 검사로 확인할 것:', nospace)
    return rows


def blocks(rows):
    fmt = {'woff': 'woff', 'woff2': 'woff2', 'ttf': 'truetype', 'otf': 'opentype'}
    def face(family, r, extra=''):
        return f'    @font-face{{font-family:"{family}";src:url("../shopping_shorts/static/fonts/scene/{r["file"]}") format("{fmt[r["ext"]]}");font-display:swap{extra}}}'
    by, lines = {r['id']: r for r in rows}, []
    for r in rows:
        lines.append(face(r['family'], r))
        if r['id'] in BORROW:   # 같은 이름으로 한 번 더 — 부호 범위만 빌린 글꼴에서 가져온다
            lines.append(face(r['family'], by[BORROW[r['id']]], f';unicode-range:{PUNCT_RANGE}'))
    css = '\n'.join([BEGIN_CSS] + lines + [END_CSS])
    # 글꼴별 실측 보정(scale·dy)은 세트에 같이 적는다 — 크기를 정하는 값이 글꼴과 떨어져 있으면 반드시 어긋난다(0순위-B)
    mp = HERE / 'scene_font_metrics.json'
    metrics = json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else {}
    def entry(r):
        m = metrics.get(r['id'], {})
        return (f"    {{id:'{r['id']}',name:'{r['name']}',channel:'{r['family']}',title:'{r['family']}',caption:'{CAPTION.get(r['id'], r['family'])}',"
                f"scale:{m.get('scale', 1)},dy:{m.get('dy', 0)}}},")
    js = '\n'.join([BEGIN_JS] + [entry(r) for r in rows] + [END_JS])
    return css, js


def put(text, begin, end, block, anchor):
    if begin in text:
        return re.sub(re.escape(begin) + r'.*?' + re.escape(end), lambda m: block, text, flags=re.S)
    assert text.count(anchor) == 1, f'기준 줄을 못 찾았다: {anchor[:40]}'
    return text.replace(anchor, anchor + block + ('\r\n' if anchor.endswith('\r\n') else '\n'))


def main():
    rows = plan(); check = '--check' in sys.argv
    if not check:
        fetch(rows)
    css, js = blocks(rows)
    a_css = '    @font-face{font-family:"KCCGanpan";src:url("../shopping_shorts/static/fonts/KCCGanpan.otf") format("opentype");font-display:swap}\n'
    a_js = "    {id:'suit',name:'SUIT 모던',channel:'SUITBold',title:'SUITBold',caption:'SUITBold'},\n"
    dirty = []
    for path, begin, end, block, anchor in ((SHOWCASE, BEGIN_CSS, END_CSS, css, a_css), (UI, BEGIN_JS, END_JS, js, a_js)):
        # 줄바꿈을 그대로 둔다(newline='') — 장면 세션도 같은 파일을 고친다. 줄바꿈이 통째로 바뀌면 병합이 깨진다.
        with path.open(encoding='utf-8', newline='') as fh:
            old = fh.read()
        nl = '\r\n' if '\r\n' in old else '\n'
        new = put(old, begin, end, block.replace('\n', nl), anchor.replace('\n', nl))
        if new != old:
            dirty.append(path.name)
            if not check:
                with path.open('w', encoding='utf-8', newline='') as fh:
                    fh.write(new)
    missing = [r['file'] for r in rows if not (FONT_DIR / r['file']).exists()]
    print('글꼴', len(rows), '| 바뀐 파일', dirty or '없음', '| 없는 글꼴 파일', missing or '없음')
    if check and (dirty or missing):
        raise SystemExit('★등록이 목록과 다르다 — --check 없이 다시 돌려라')


if __name__ == '__main__':
    main()
