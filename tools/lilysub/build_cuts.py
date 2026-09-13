"""볼케이노 timing.json → 릴리 자막 오버레이용 cuts.json.

쓰는 법:
    python tools/lilysub/build_cuts.py <작업폴더> [계획.json]

계획 파일을 안 주면 전부 narr(박스형)로 깐다 — 그대로도 영상은 나온다.
계획 파일은 {"9": {"kind":"lower","name":"여친","color":"#1aa6a6"}, ...} 꼴이며
컷번호(timing.groups[].i)를 키로 쓴다.

kind 7종
    narr   박스형(기본)          — 나레이션. 제일 많이 쓴다
    hl     형광펜                — highlight 낱말을 칠한다(본문에 있어야 함)
    lower  이름표+대사           — name, color 필요. 인물별로 색을 갈라라
    bubble 말풍선                — 댓글·남의 말. color
    react  리액션 단어           — text 를 따로 주면 그 글자로 바꾼다
    stamp  도장                  — REJECTED 같은 판정
    punch  빨강 마무리           — 마지막 컷
"""
import json
import os
import sys

DEFAULT_COLOR = {
    'bubble': '#ff7ab8',
    'react': '#ff2d2d',
    'stamp': '#e02020',
}


def build(workdir, plan_path=None):
    timing = json.load(open(os.path.join(workdir, 'timing.json'), encoding='utf-8'))
    plan = {}
    if plan_path:
        raw = json.load(open(plan_path, encoding='utf-8'))
        plan = {int(k): v for k, v in raw.items()}

    cuts = []
    for g in timing['groups']:
        spec = dict(plan.get(g['i']) or {})
        kind = spec.pop('kind', 'narr')
        cut = {
            't': g['t'],
            'd': g['d'],
            'kind': kind,
            # react 처럼 원문 대신 딴 글자를 띄우고 싶으면 계획에서 text 를 준다
            'text': spec.pop('text', g['text']),
        }
        if 'color' not in spec and kind in DEFAULT_COLOR:
            spec['color'] = DEFAULT_COLOR[kind]
        cut.update(spec)
        cuts.append(cut)

    # 형광펜은 본문에 그 낱말이 실제로 있어야 칠해진다 — 없으면 조용히 안 칠해지므로 되돌린다
    for c in cuts:
        if c['kind'] == 'hl' and c.get('highlight') not in c['text']:
            print(f"  [주의] 형광펜 낱말이 본문에 없다 → narr 로 되돌림: {c['text']}")
            c['kind'] = 'narr'
            c.pop('highlight', None)

    # 이름표는 name 이 없으면 빈 탭만 나온다
    for c in cuts:
        if c['kind'] == 'lower' and not c.get('name'):
            print(f"  [주의] lower 인데 name 이 없다 → narr 로 되돌림: {c['text']}")
            c['kind'] = 'narr'

    out = os.path.join(workdir, 'cuts.json')
    json.dump({'cuts': cuts}, open(out, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f"cuts {len(cuts)} | total {timing['total']} → {out}")
    for c in cuts:
        print(f"  {c['t']:6.2f} +{c['d']:4.2f} {c['kind']:7s} "
              f"{c.get('name', ''):4s} {c['text'][:30]}")
    return out


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
