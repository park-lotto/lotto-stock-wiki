# -*- coding: utf-8 -*-
"""효과음 귀 확인 묶음 — 한 페이지(표준 §11-6 ㉞⑤, 관제 263, 10-25).

왜: 신호로만 잡은 효과음 후보(confidence '신호')와 판독(눈)↔받아쓰기 거름이 부딪힌 후보는 귀로만 가를 수 있다.
    사장님 귀는 **한 번에 10분** — 채널마다 흩어 묻지 않고 한 페이지(≤30건)로 모아, 규칙 등급을 바꾸는 것부터 듣게 한다.
무엇을 모으나: channel/<slug>/_kal/sfx_events.json 의 cand_kept 중 ear_pending(engine/sound/sfx_events.asr_filter 가 붙인다 — 분류 주인은 거기).
    옛 파일(ear_pending 칸 없음)은 저장된 후보·받아쓰기·줄판독으로 같은 asr_filter 를 다시 돌려 고른다(소리 다시 재지 않음).
정렬(영향 큰 것 먼저): ① 그 편에 확정 발(sure)이 0 인데 대기만 있는 것(이 답이 '그 편에 효과음이 있나'를 정한다 — 규칙 비율 k/n 이 바뀐다)
    ② 판독(눈)↔낱말 거름 충돌 ③ 같은 채널에서 대기가 적은 것(한 답의 무게가 크다) ④ 신호 세기(db) 큰 것.
한 건 = 채널·편·시각·0.6초 소리(앞 0.15 + 뒤 0.45)·파형 그림·후보 종류·지금 판정·근거(눈/신호·keep_why·낱말).
답 저장 = 페이지의 '결과 저장' → ear_review_result.json 내려받기 → `apply` 가 그 채널 파일의 ear_pending 을 닫는다(효과음=확정, 아님=빼기, 모름=그대로).

    PYTHONUTF8=1 py tools/calcopy/engine/sound/sfx_ear_review.py build [--out 폴더] [--max 30] [--slugs a,b]
    PYTHONUTF8=1 py tools/calcopy/engine/sound/sfx_ear_review.py apply <ear_review_result.json>
"""
from __future__ import annotations

import html
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import sfx_events as E  # noqa: E402

ROOT = Path(E.ROOT)
DATA = Path(os.environ.get('CALCOPY_PACK_ROOT_DATA') or 'C:/숏템_칼카피')
PRE, POST = 0.15, 0.45
MAX_ITEMS = 30


def channel_items(slug: str) -> list[dict]:
    p = Path(E.out_path(slug))
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding='utf-8'))
    reads = E._reads(slug)
    adir = E.meta_asr_dir(d.get('_meta'))
    out = []
    for vid, row in d.items():
        if vid == '_meta' or not isinstance(row, dict):
            continue
        kept = row.get('cand_kept')
        if not kept or not any('ear_pending' in c or 'confidence' in c for c in kept):      # 옛 파일 — 같은 분류 함수로 다시 고른다
            words = []
            if adir and os.path.exists(os.path.join(adir, vid + '.json')):
                words = E.asr_words(os.path.join(adir, vid + '.json'))[0] or []
            row = E.asr_filter(dict(row), words, reads.get(vid))
            kept = row['cand_kept']
        sure = sum(1 for c in kept if not c.get('ear_pending'))
        for c in kept:
            if c.get('ear_pending') and not c.get('ear'):
                out.append({'slug': slug, 'vid': vid, 't': c['t'], 'kind': c['kind'], 'db': c.get('db'), 'confidence': c.get('confidence'),
                            'keep_why': c.get('keep_why'), 'word': c.get('word'), 'video_sure': sure, 'eye_conflict': '판독 우선' in (c.get('keep_why') or '')})
    return out


def rank(items: list[dict]) -> list[dict]:
    per = {}
    for it in items:
        per[it['slug']] = per.get(it['slug'], 0) + 1
    return sorted(items, key=lambda it: (0 if it['video_sure'] == 0 else 1, 0 if it['eye_conflict'] else 1, per[it['slug']], -(it['db'] or 0)))


def src_of(slug: str, vid: str) -> Path | None:
    for e in ('.mp4', '.wav', '.webm', '.mkv'):
        p = DATA / slug / 'src' / (vid + e)
        if p.exists():
            return p
    return None


def clip(src: Path, t: float, wav: Path) -> bool:
    a = max(0.0, t - PRE)
    r = subprocess.run(['ffmpeg', '-y', '-v', 'error', '-ss', f'{a:.3f}', '-t', f'{PRE + POST:.3f}', '-i', str(src), '-ac', '1', '-ar', '22050', str(wav)],
                       capture_output=True, stdin=subprocess.DEVNULL)
    return r.returncode == 0 and wav.exists()


def wave_png(wav: Path, png: Path, mark: float):
    import numpy as np
    from PIL import Image, ImageDraw
    from scipy.io import wavfile
    sr, x = wavfile.read(str(wav))
    x = x.astype('float32'); x /= (abs(x).max() or 1)
    W, H = 360, 80
    im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
    n = len(x)
    for i in range(W):
        seg = x[int(i * n / W):max(int((i + 1) * n / W), int(i * n / W) + 1)]
        lo, hi = (float(seg.min()), float(seg.max())) if len(seg) else (0.0, 0.0)
        d.line([(i, H / 2 - hi * H / 2), (i, H / 2 - lo * H / 2)], fill=(40, 90, 200))
    mx = int(mark / (PRE + POST) * W)
    d.line([(mx, 0), (mx, H)], fill=(220, 30, 30), width=2)
    im.save(png)


def build(out: Path, max_items: int = MAX_ITEMS, slugs: list[str] | None = None) -> dict:
    slugs = slugs or sorted(p.parent.parent.name for p in ROOT.glob('channel/*/_kal/sfx_events.json'))
    allit = []
    for s in slugs:
        allit += channel_items(s)
    items = rank(allit)[:max_items]
    (out / 'clips').mkdir(parents=True, exist_ok=True)
    rows = []
    for k, it in enumerate(items):
        src = src_of(it['slug'], it['vid'])
        name = f"{k:02d}_{it['slug']}_{it['vid']}_{it['t']:.2f}"
        ok = bool(src) and clip(src, it['t'], out / 'clips' / f'{name}.wav')
        if ok:
            wave_png(out / 'clips' / f'{name}.wav', out / 'clips' / f'{name}.png', min(PRE, it['t']))
        rows.append({**it, 'clip': f'clips/{name}.wav' if ok else None, 'png': f'clips/{name}.png' if ok else None, 'src': str(src) if src else None})
    data = {'made_by': 'tools/calcopy/engine/sound/sfx_ear_review.py build', 'built_at': time.strftime('%Y-%m-%d %H:%M'), 'n_all': len(allit), 'items': rows}
    (out / 'items.json').write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    (out / 'index.html').write_text(page(data), encoding='utf-8')
    return data


def page(data: dict) -> str:
    tr = []
    for k, it in enumerate(data['items']):
        why = ' · '.join(x for x in [f"판정 {it['confidence'] or '-'}", it.get('keep_why') or '', f"낱말 '{it['word']}'" if it.get('word') else '',
                                     '이 편 확정 0 — 이 답이 편의 효과음 유무를 정함' if it['video_sure'] == 0 else ''] if x)
        media = (f'<audio controls preload="none" src="{html.escape(it["clip"])}"></audio><br><img src="{html.escape(it["png"])}" alt="파형(빨간 선 = 후보 시각)">'
                 if it['clip'] else '<i>원본 소리 없음</i>')
        tr.append(f'''<tr><td>{k + 1}</td><td>{html.escape(it['slug'])}<br><small>{html.escape(it['vid'])}</small></td><td>{it['t']:.2f}초</td>
<td>{html.escape(it['kind'])}<br><small>{it.get('db')} dB</small></td><td>{media}</td><td><small>{html.escape(why)}</small></td>
<td class="ans" data-k="{k}"><label><input type="radio" name="a{k}" value="효과음">효과음</label><br><label><input type="radio" name="a{k}" value="아님">아님</label><br><label><input type="radio" name="a{k}" value="모름">모름</label></td></tr>''')
    items_js = json.dumps([{k: it[k] for k in ('slug', 'vid', 't', 'kind')} for it in data['items']], ensure_ascii=False)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>효과음 귀 확인</title>
<style>body{{font-family:sans-serif;margin:16px;background:#fff;color:#111}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:6px;vertical-align:top}}
button{{font-size:16px;padding:8px 16px}}small{{color:#555}}</style></head><body>
<h2>효과음 귀 확인 — {len(data['items'])}건(대기 전체 {data['n_all']}건 중 영향 큰 순)</h2>
<p>소리는 후보 시각 앞 0.15초~뒤 0.45초. 빨간 선 = 후보 시각. 다 고르면 <b>결과 저장</b> → 받은 파일을
<code>py tools/calcopy/engine/sound/sfx_ear_review.py apply ear_review_result.json</code> 로 반영합니다. 만든 때 {data['built_at']}</p>
<table><tr><th>#</th><th>채널·편</th><th>시각</th><th>종류</th><th>소리·파형</th><th>근거</th><th>답</th></tr>{''.join(tr)}</table>
<p><button id="save">결과 저장</button> <span id="msg"></span></p>
<script>
const ITEMS={items_js};
document.getElementById('save').onclick=()=>{{
  const out=ITEMS.map((it,k)=>{{const c=document.querySelector('input[name="a'+k+'"]:checked');return Object.assign({{}},it,{{answer:c?c.value:null}});}});
  const blob=new Blob([JSON.stringify({{saved_at:new Date().toISOString(),items:out}},null,1)],{{type:'application/json'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='ear_review_result.json';a.click();
  document.getElementById('msg').textContent='저장: '+out.filter(x=>x.answer).length+'/'+out.length+'건 답함';
}};
</script></body></html>'''


def apply(result: Path) -> dict:
    R = json.loads(Path(result).read_text(encoding='utf-8'))
    done = {}
    by = {}
    for it in R.get('items') or []:
        if it.get('answer') in ('효과음', '아님'):
            by.setdefault(it['slug'], []).append(it)
    for slug, its in by.items():
        p = Path(E.out_path(slug)); d = json.loads(p.read_text(encoding='utf-8'))
        for it in its:
            row = d.get(it['vid']) or {}
            kept = row.get('cand_kept') or []
            c = next((c for c in kept if abs(c['t'] - it['t']) < 0.01 and c['kind'] == it['kind']), None)
            if c is None:
                continue
            c['ear_pending'] = False; c['ear'] = it['answer']
            if it['answer'] == '아님':
                kept.remove(c); row.setdefault('cand_ear_rejected', []).append(c)
            row['sfx_count'] = {'sure': sum(1 for x in kept if not x.get('ear_pending')), 'pending': sum(1 for x in kept if x.get('ear_pending'))}
            done[slug] = done.get(slug, 0) + 1
        d.setdefault('_meta', {})['ear_review'] = {'applied_from': str(result), 'n': done.get(slug, 0), 'at': time.strftime('%Y-%m-%d %H:%M')}
        p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    return done


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return 2
    if a[0] == 'build':
        out = Path(a[a.index('--out') + 1]) if '--out' in a else DATA / '_ear_review' / time.strftime('%Y%m%d_%H%M')
        mx = int(a[a.index('--max') + 1]) if '--max' in a else MAX_ITEMS
        sl = a[a.index('--slugs') + 1].split(',') if '--slugs' in a else None
        d = build(out, mx, sl)
        print(json.dumps({'out': str(out / 'index.html'), 'items': len(d['items']), 'n_all': d['n_all'],
                          'no_clip': sum(1 for x in d['items'] if not x['clip'])}, ensure_ascii=False))
        return 0
    if a[0] == 'apply':
        print(json.dumps(apply(Path(a[1])), ensure_ascii=False)); return 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main() or 0)
