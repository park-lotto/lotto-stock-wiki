"""align.json(whisper 단어시각) + 대사.txt(정확한 글자) + meta.json(컷·활동) + titles.json → V2_S4Data.ts"""
import json, os, re, sys, difflib
sys.path.insert(0, os.path.dirname(__file__))
from scenes import SCENES, ROOT, PUB
H = os.path.dirname(__file__)
AL = json.load(open(os.path.join(H, 'align.json'), encoding='utf8'))
TT = json.load(open(os.path.join(H, 'titles.json'), encoding='utf8'))
norm = lambda s: re.sub(r'[^0-9A-Za-z가-힣]', '', s)
def words_for(k, folder):
    script = open(os.path.join(ROOT, folder, '대사.txt'), encoding='utf8').read()
    sw = script.split()
    ww = AL[folder]
    wc, wt = [], []   # whisper 글자별 시각
    for w, s, e in ww:
        n = norm(w)
        for i, ch in enumerate(n):
            wc.append(ch); wt.append(s + (e - s) * (i + 0.5) / max(1, len(n)))
    sc = []; owner = []
    for j, w in enumerate(sw):
        for ch in norm(w): sc.append(ch); owner.append(j)
    m = difflib.SequenceMatcher(None, sc, wc, autojunk=False)
    t_of = [None] * len(sc)
    for a, b, size in m.get_matching_blocks():
        for i in range(size): t_of[a + i] = wt[b + i]
    # 빈 곳은 앞뒤로 메움
    known = [i for i, t in enumerate(t_of) if t is not None]
    for i in range(len(t_of)):
        if t_of[i] is None:
            p = max([x for x in known if x < i], default=None); q = min([x for x in known if x > i], default=None)
            if p is None: t_of[i] = t_of[q]
            elif q is None: t_of[i] = t_of[p]
            else: t_of[i] = t_of[p] + (t_of[q] - t_of[p]) * (i - p) / (q - p)
    res = []
    for j, w in enumerate(sw):
        ts = [t_of[i] for i in range(len(sc)) if owner[i] == j]
        if not ts: continue
        res.append([w, round(min(ts) - 0.06, 3), round(max(ts) + 0.06, 3)])
    for i in range(len(res) - 1):   # 겹침 정리
        if res[i][2] > res[i + 1][1]: res[i][2] = res[i + 1][1]
    return script, res
def find(words, phrase):
    p = norm(phrase); joined = ''; idx = []
    for i, (w, s, e) in enumerate(words):
        for ch in norm(w): joined += ch; idx.append(i)
    at = joined.find(p)
    if at < 0: raise SystemExit(f'못 찾음: {phrase}')
    return words[idx[at]][1]
out = {}
for k, (folder, _) in SCENES.items():
    if folder not in AL: print('정렬 없음', k); continue
    meta = json.load(open(os.path.join(PUB, k, 'meta.json')))
    script, words = words_for(k, folder)
    tt = TT.get(k, {'chips': [], 'punches': []})
    chips = [[round(max(0, find(words, a) - 0.1), 2), t] for a, t in tt['chips']]
    punches = [[round(find(words, a), 2), t, acc] for a, t, acc in tt['punches']]
    out[k] = {'dur': meta['dur'], 'cuts': meta['cuts'], 'focus': meta['focus'], 'words': words, 'chips': chips, 'punches': punches, 'seed': len(out) * 3 + 1}
ts = ('// 자동 생성 — tools/v2s4/build_data.py. 손으로 고치지 말 것(titles.json·cut.py 를 고친다)\n'
      'export type S4Scene = { dur: number; cuts: number[]; focus: [number, number, number, number][]; words: [string, number, number][];\n'
      '  chips: [number, string][]; punches: [number, string, string][]; seed?: number; zoom?: number };\n'
      'export const S4R: Record<string, S4Scene> = ' + json.dumps(out, ensure_ascii=False) + ';\n')
open(os.path.join(H, '..', '..', 'remotion-stock', 'src', 'shottem2', 'V2_S4Data.ts'), 'w', encoding='utf8').write(ts)
print('씬', list(out))
