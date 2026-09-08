# -*- coding: utf-8 -*-
"""이미 받아둔 프레임을 **고친 실측기로 다시 재고**, 진짜 새 스타일만 추린다.

왜 다시 재나: 수집을 돌리는 중에 실측기를 두 번 고쳤다.
  ① 띠 판정 완화 — 로고·아이콘이 섞인 띠가 mix로 빠져 구간 시작점이 어긋났다
  ② 글자 아닌 것 걸러내기 — 영상 속 밝은 물체가 '3줄'로 잡혔다
state.json 의 값은 옛 로직 결과라 그대로 쓰면 GPT에 틀린 값을 준다.

정답 5건으로 검증한 로직이다(지식배송·숏팡·숏템·부시리·신비아이템 = 5/5).
"""
import sys, os, json, glob, importlib.util, collections

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'styles')

spec = importlib.util.spec_from_file_location('m', os.path.join(HERE, 'batch20.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)
rspec = importlib.util.spec_from_file_location('r', os.path.join(HERE, 'run_all.py'))
R = importlib.util.module_from_spec(rspec); rspec.loader.exec_module(R)


def main():
    st = json.load(open(os.path.join(WORK, 'state.json'), encoding='utf-8'))
    # 이름 ← slug 매핑을 state 에서 되찾는다
    by_slug = {s['slug']: s for s in st['styles']}
    hooks = sorted(glob.glob(os.path.join(WORK, '*_hook.png')))
    print('프레임 %d장 재실측' % len(hooks))

    seen, out, dropped = {}, [], 0
    for hp in hooks:
        slug = os.path.basename(hp).replace('_hook.png', '')
        bp = hp.replace('_hook.png', '_body.png')
        try:
            mh = M.measure(hp)
            mb = M.measure(bp) if os.path.exists(bp) else None
        except Exception:
            continue
        if not R.is_sul(mh):
            dropped += 1
            continue
        fp = R.fingerprint(mh)
        if fp in seen:
            continue
        seen[fp] = slug
        old = by_slug.get(slug, {})
        out.append({'slug': slug, 'name': old.get('name', slug),
                    'vid': old.get('vid'), 'caption': old.get('caption'),
                    'fp': fp, 'hook': mh, 'body': mb,
                    'hook_png': hp, 'body_png': bp if os.path.exists(bp) else None})

    json.dump(out, open(os.path.join(WORK, 'final_styles.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

    # 지시문 다시 쓴다
    d = os.path.join(WORK, 'prompts'); os.makedirs(d, exist_ok=True)
    for e in out:
        nm = (e['name'] or e['slug'])[:14].replace('/', '_').replace('\\', '_')
        with open(os.path.join(d, f"{e['slug']}_{nm}.txt"), 'w', encoding='utf-8') as f:
            f.write(M.fmt(e['name'], e['hook'], e['body']))

    print('\n최종 스타일 %d개 (구조 미달 %d장 제외)' % (len(out), dropped))
    print('%-16s %-9s %-9s %s' % ('채널', '띠색', '제목배경', '글자'))
    for e in out:
        h = e['hook']
        print('%-16s %-9s %-9s %s' % (
            (e['name'] or '')[:15], h['top_band']['color'], h['title_bg'] or '-',
            ' '.join('%s' % l['color'] for l in h['lines'])))
    print('\n지시문:', d)


if __name__ == '__main__':
    main()
