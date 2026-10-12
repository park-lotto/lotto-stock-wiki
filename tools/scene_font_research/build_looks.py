# -*- coding: utf-8 -*-
"""추천 룩을 늘린다 + 색톤·룩 감사(audit).  py tools/scene_font_research/build_looks.py [--check]

손으로 고른 룩 24개(precision20-ui.js LOOKS 앞부분)는 그대로 두고, '룩 확장:시작~끝' 사이에 규칙으로 만든 룩을 채운다.
규칙(눈으로 보고 정한 것 — handoff/장면폰트.md 5차 함정 4):
  가는 글꼴(손글씨·붓)   → 두꺼운 테두리(sticker·ring) 금지 : 글자 모양을 먹는다
  빽빽한 글꼴(획이 꽉 참) → 채운 박스(box·pill·ribbon·plate) 금지 : 박스 안에서 안 읽힌다
  밝은 바탕 색톤          → 빛·흰색으로 시작하는 꾸밈(glow·grad) 금지 : 흰 바탕에서 안 보인다
  강조색이 흰색인 색톤    → grad·twotone·glow 금지(흰→흰, 흰 번짐)
  (2차, 60개를 눈으로 보고 추가) 빽빽한 글꼴 → ring·sticker·glow도 금지 / 밝은 바탕 → longshadow도 금지
감사: ①색톤 명암비(1줄·2줄 대 바탕 ≥ 3.0 — 큰 글자 기준 WCAG) ②룩 중복 0 ③모든 글꼴·색톤·꾸밈이 최소 1번 ④한 글꼴 최대 3번
"""
import sys, re, json, pathlib, collections
ROOT = pathlib.Path(__file__).resolve().parents[2]; UI = ROOT / 'out' / 'precision20-ui.js'
BEGIN, END = '    // 룩 확장:시작 — tools/scene_font_research/build_looks.py 가 쓴다. 손으로 고치지 마라', '    // 룩 확장:끝'
TARGET = 60
THIN = {'f82', 'f461', 'f1381', 'f321', 'f499', 'gaegu', 'brush', 'chalk', 'kkubulim', 'dongle', 'myeongjo', 'ridi', 'danjung'}
DENSE = {'f731', 'f1186', 'f364', 'gasoek', 'bagel', 'f876'}
DENSE_OK = {'outline', 'shadow3d', 'tilt', 'under', 'grad'}
FILL, THICK, LIGHTLESS = {'box', 'pill', 'ribbon', 'plate'}, {'sticker', 'ring'}, {'glow', 'grad'}


def grab(text, name):
    body = re.search(r'const ' + name + r'=\[(.*?)\n  \];', text, re.S).group(1)
    rows = []
    for m in re.finditer(r'\{id:\'([^\']*)\'(.*?)\}(?=,|\s)', body):
        d = {'id': m.group(1)}; d.update(re.findall(r"(\w+):'([^']*)'", m.group(2))); rows.append(d)
    return rows


def lum(c):
    v = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]; v = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in v]
    return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]
def contrast(a, b):
    x, y = sorted((lum(a), lum(b)), reverse=True); return (x + .05) / (y + .05)


def ok(font, tone, deco):
    if font in THIN and deco in THICK: return False
    if font in DENSE and deco not in DENSE_OK: return False   # 빽빽한 글꼴은 금지 목록이 끝이 없다(박스·두꺼운 테·번짐·긴 그림자·투톤 전부 뭉개짐) → 어울리는 것만 허용
    if lum(tone['bg']) > .45 and (deco in LIGHTLESS or deco == 'longshadow'): return False    # 밝은 바탕: 빛·긴 그림자는 얼룩이 된다
    if tone['c2'].upper() == '#FFFFFF' and deco in ('grad', 'twotone', 'glow'): return False  # 흰 강조색: 흰→흰, 흰 번짐
    return True


def main():
    with UI.open(encoding='utf-8', newline='') as fh: text = fh.read()
    nl = '\r\n' if '\r\n' in text else '\n'
    fonts, tones, decos = grab(text, 'FONT_SETS'), grab(text, 'TONES'), grab(text, 'DECOS')
    i, j = text.index(BEGIN), text.index(END)
    curated = grab(text[:i] + text[j:], 'LOOKS')
    print(f'글꼴 {len(fonts)} · 색톤 {len(tones)} · 꾸밈 {len(decos)} · 손으로 고른 룩 {len(curated)}')
    fails = []
    for t in tones:
        a, b = contrast(t['c1'], t['bg']), contrast(t['c2'], t['bg'])
        if min(a, b) < 3: fails.append(f"색톤 {t['name']} 명암비 1줄 {a:.1f} / 2줄 {b:.1f}")
    # 덜 쓰인 것부터 돌려가며 채운다 — 한쪽으로 쏠리면 회원들 영상이 다 비슷해진다
    used = collections.Counter(); seen = set()
    for l in curated:
        seen.add((l['font'], l['tone'], l['deco'])); used.update([('f', l['font']), ('t', l['tone']), ('d', l['deco'])])
    fname = {f['id']: f['name'] for f in fonts}; tby = {t['id']: t for t in tones}; made = []
    # 기존 글꼴은 크기 보정값이 없다. 기본 글꼴과 높이가 많이 다른 것(실측 existing_font_metrics.json, 0.9~1.12 밖)은
    # 추천으로 내놓으면 제목이 작게 나와 약해 보인다 → 자동 생성에서 뺀다(폰트 탭에는 그대로 있다).
    mp = pathlib.Path(__file__).resolve().parent / 'existing_font_metrics.json'
    weak = {k for k, v in (json.loads(mp.read_text(encoding='utf-8')) if mp.exists() else {}).items() if not .9 <= v['need'] <= 1.12}
    print('크기 편차로 자동 생성에서 뺀 기존 글꼴:', sorted(fname[k] for k in weak))
    order = [f['id'] for f in fonts if f['id'].startswith('f') and f['id'][1:].isdigit()] + [f['id'] for f in fonts if not (f['id'].startswith('f') and f['id'][1:].isdigit()) and f['id'] not in weak]
    k = 0
    while len(curated) + len(made) < TARGET and k < 5000:
        k += 1
        font = min(order, key=lambda f: (used[('f', f)], order.index(f)))
        cand = sorted(((used[('t', t['id'])] + used[('d', d['id'])], ti * 7 % 5 + di, t, d) for ti, t in enumerate(tones) for di, d in enumerate(decos)
                       if ok(font, t, d['id']) and (font, t['id'], d['id']) not in seen), key=lambda x: (x[0], x[1]))
        if not cand: used[('f', font)] += 99; continue
        _, _, t, d = cand[0]
        seen.add((font, t['id'], d['id'])); used.update([('f', font), ('t', t['id']), ('d', d['id'])])
        made.append({'id': f'l{len(curated) + len(made) + 1:02d}', 'name': f"{t['name']} · {fname[font]}", 'font': font, 'tone': t['id'], 'deco': d['id']})
    allk = curated + made
    dup = len(allk) - len({(l['font'], l['tone'], l['deco']) for l in allk})
    if dup: fails.append(f'룩 중복 {dup}')
    for kind, pool in (('t', tones), ('d', decos)):
        miss = [x['name'] for x in pool if not used[(kind, x['id'])]]
        if miss: fails.append(f'한 번도 안 쓰인 {"색톤" if kind == "t" else "꾸밈"}: {miss}')
    newfonts = [f for f in order if f.startswith('f') and f[1:].isdigit()]
    miss = [fname[f] for f in newfonts if not used[('f', f)]]
    if miss: fails.append(f'한 번도 안 쓰인 새 글꼴: {miss}')
    over = [(fname[f], used[('f', f)]) for f in order if 3 < used[('f', f)] < 90]
    if over: fails.append(f'한 글꼴 4번 이상: {over}')
    bad = [l['name'] for l in allk if not ok(l['font'], tby[l['tone']], l['deco'])]
    if bad: fails.append(f'궁합 규칙 위반 룩: {bad}')
    tc = collections.Counter(l['tone'] for l in allk); dc = collections.Counter(l['deco'] for l in allk)
    print(f'룩 {len(allk)}개 | 색톤별 사용 {min(tc.values())}~{max(tc.values())}회 | 꾸밈별 사용 {min(dc.values())}~{max(dc.values())}회 | 첫 화면 12개 안의 서로 다른 글꼴 {len({l["font"] for l in allk[:12]})}')
    block = nl.join([BEGIN] + ["    " + ",".join("{id:'%s',name:'%s',font:'%s',tone:'%s',deco:'%s'}" % (l['id'], l['name'], l['font'], l['tone'], l['deco']) for l in made[n:n + 2]) + "," for n in range(0, len(made), 2)]) + nl
    new = text[:i] + block + text[j:]
    if '--check' in sys.argv:
        if new != text: fails.append('LOOKS 확장 블록이 생성 결과와 다르다 — --check 없이 다시 돌려라')
    elif new != text:
        with UI.open('w', encoding='utf-8', newline='') as fh: fh.write(new)
        print('precision20-ui.js 룩 확장 블록 갱신:', len(made), '개')
    print('실패', fails or '없음'); sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
