# -*- coding: utf-8 -*-
"""썰쇼핑 채널 전체를 훑어 **새로운 스타일만** 남긴다.

485채널을 다 만들 필요는 없다 — 같은 디자인이 겹치기 때문이다.
띠색·제목배경·글자색·구성으로 지문을 만들어, 처음 보는 지문일 때만 템플릿 후보로 남긴다.

★진행 상황을 state.json 에 계속 적는다 — 중간에 멈춰도 이어서 돌릴 수 있다.
"""
import subprocess, sys, os, json, collections, time, importlib.util

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, 'styles')
os.makedirs(WORK, exist_ok=True)
STATE = os.path.join(WORK, 'state.json')
YTDLP = r"C:\Users\CH\.local\bin\yt-dlp.exe"

# batch20.py 의 실측 함수를 그대로 쓴다(정의처 하나 — 0순위-B)
spec = importlib.util.spec_from_file_location('m', os.path.join(HERE, 'batch20.py'))
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding='utf-8'))
    return {'seen_fp': {}, 'done': [], 'fail': [], 'styles': []}


def save_state(s):
    json.dump(s, open(STATE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


def sh(cmd, timeout=200):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode
    except Exception:
        return -1


def grab(vid, slug):
    base = os.path.join(WORK, slug)
    vid_file = None
    for ext in ('.webm', '.mp4', '.mkv'):
        if os.path.exists(base + ext):
            vid_file = base + ext; break
    if not vid_file:
        sh([YTDLP, '-q', '--no-warnings',
            '-f', 'bv*[height<=480]+ba/b[height<=480]',
            '-o', base + '.%(ext)s',
            f'https://www.youtube.com/shorts/{vid}'])
        for ext in ('.webm', '.mp4', '.mkv'):
            if os.path.exists(base + ext):
                vid_file = base + ext; break
    if not vid_file:
        return None, None
    hook, body = base + '_hook.png', base + '_body.png'
    if not os.path.exists(hook):
        sh(['ffmpeg', '-y', '-v', 'error', '-ss', '1', '-i', vid_file,
            '-frames:v', '1', hook], timeout=70)
    if not os.path.exists(body):
        sh(['ffmpeg', '-y', '-v', 'error', '-ss', '9', '-i', vid_file,
            '-frames:v', '1', body], timeout=70)
    # 영상 본체는 지운다 — 485개면 디스크가 찬다
    try:
        if os.path.exists(vid_file): os.remove(vid_file)
    except Exception:
        pass
    return (hook if os.path.exists(hook) else None,
            body if os.path.exists(body) else None)


def coarse(hexs):
    """색을 32단계로 뭉갠다 — 압축 차이로 1~2 다른 색을 같은 스타일로 본다."""
    if not hexs or not hexs.startswith('#'): return '-'
    v = [int(hexs[i:i+2], 16) // 32 for i in (1, 3, 5)]
    return '%d%d%d' % tuple(v)


def is_sul(r):
    """★썰쇼핑형인가 — 구조로 판정한다(채널명·검색어로는 못 거른다).

    실측: '활용법·꿀템' 검색어로 485채널을 뽑았더니 상단 띠도 흰 박스도 없는
    일반 살림 영상이 대거 섞였다(하루살림·마샤홈·리빙홈 등). 그 화면에는
    베낄 틀 자체가 없다. 썰쇼핑형의 조건은 세 가지다:
      ① 화면 위쪽에 단색 띠가 있다(채널명이 들어가는 자리)
      ② 그 아래 큰 글자가 1~2줄 있다
      ③ 흰 한줄박스가 있거나, 최소한 글자 두 줄이 잡힌다
    """
    if not r or not r.get('lines'): return False
    tb = r.get('top_band') or {}
    # ① 띠: 화면 높이의 3~22% 사이 단색
    if not (3.0 <= (tb.get('hpct') or 0) <= 22.0): return False
    if not tb.get('color'): return False
    # ② 글자: 화면 폭의 절반 이상을 차지하는 줄이 있어야 한다
    wide = [l for l in r['lines'] if (l['lpct'] + l['rpct']) < 45]
    if not wide: return False
    # ③ 흰박스가 있거나 큰 글자가 2줄 이상
    return bool(r.get('white_box')) or len(wide) >= 2


def fingerprint(r):
    """스타일 지문 — 이게 같으면 같은 디자인으로 본다."""
    if not r: return None
    parts = [coarse(r['top_band']['color']), coarse(r['title_bg']),
             ','.join(coarse(l.get('color')) for l in r['lines']),
             'WB' if r.get('white_box') else 'noWB',
             str(len(r['lines']))]
    return '|'.join(parts)


def main(limit=None, start=0):
    targets = json.load(open(os.path.join(HERE, 'wide.json'), encoding='utf-8'))
    if limit: targets = targets[start:start + limit]
    st = load_state()
    seen = st['seen_fp']
    t0 = time.time()
    for i, (name, vid, cap) in enumerate(targets, 1):
        if name in st['done'] or name in st['fail']:
            continue
        slug = 's%04d' % (start + i)
        h, b = grab(vid, slug)
        if not h:
            st['fail'].append(name); save_state(st); continue
        try:
            mh = M.measure(h)
            mb = M.measure(b) if b else None
        except Exception as e:
            st['fail'].append(name); save_state(st); continue
        st['done'].append(name)
        if not is_sul(mh):
            st.setdefault('notsul', []).append(name)
            save_state(st); continue
        fp = fingerprint(mh)
        if fp and fp not in seen:
            seen[fp] = name
            entry = {'name': name, 'vid': vid, 'caption': cap, 'fp': fp,
                     'slug': slug, 'hook': mh, 'body': mb}
            st['styles'].append(entry)
            with open(os.path.join(WORK, f'{slug}_{name[:14]}.txt'), 'w',
                      encoding='utf-8') as f:
                f.write(M.fmt(name, mh, mb))
            print('[NEW %3d] %-18s %s' % (len(st['styles']), name[:17], fp), flush=True)
        save_state(st)
        if i % 20 == 0:
            el = time.time() - t0
            print('  ... %d개 처리 (새 스타일 %d, 실패 %d) %.0f초'
                  % (len(st['done']), len(st['styles']), len(st['fail']), el), flush=True)
    print('\n=== 끝 ===')
    print('처리 %d / 새 스타일 %d / 실패 %d'
          % (len(st['done']), len(st['styles']), len(st['fail'])))


if __name__ == '__main__':
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    stt = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    main(lim, stt)
