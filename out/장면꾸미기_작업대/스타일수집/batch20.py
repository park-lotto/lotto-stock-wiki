# -*- coding: utf-8 -*-
"""20개 템플릿 자동 파이프라인 — 다운로드 → 프레임추출 → 픽셀실측 → GPT지시문 생성

지침서(GPT_템플릿_지침서.md)의 실측 규칙을 코드로 옮겼다.
★서버는 유튜브 봇확인에 막히므로 로컬 PC에서 yt-dlp를 돌린다.
"""
import subprocess, sys, os, json, collections, io
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
YTDLP = os.environ.get(
    'SHOPPING_SHORTS_YTDLP',
    r"C:\Users\TheRose\AppData\Local\Programs\Python\Python312\Scripts\yt-dlp.exe",
)
OUT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(OUT, 'top20_views')
os.makedirs(WORK, exist_ok=True)

# 레퍼런스 랭킹의 실제 조회수 상위 20개(2026-09-10 실측).
# 디자인 취향으로 임의 선정하지 않고 시청자 반응을 1차 기준으로 고정한다.
TARGETS = [
    ('활용정점.',       'azDE6caCwjU'), ('살림킹왕짱',       '697OHq-VhkY'),
    ('썰칩12',         'qbUbiRWfBq4'), ('방구석꿀템',       'U5ee0EsBfww'),
    ('럭키박스',        'S3ouvyTeYPY'), ('쇼핑 치트키',      '7zJofUqMfN4'),
    ('공가미',         've4g3XYjHLw'), ('코어장바구니',      'O1CO-k5z-2Q'),
    ('살림장착',        '5tC_j4fsq4Y'), ('쇼핑천재',        'MJeY7r8wQiQ'),
    ('이븐쇼핑',        'eDHoIXyXOq0'), ('이거였네',        '-ITG6ZF87pE'),
    ('달래샵',         'iu3Yq04q2Ws'), ('꿀팁꿀템',        '4cFxGzTx6Pc'),
    ('다있슈',         'z7oQFp8yZHQ'), ('인생갓템',        'neS2s8FIKpc'),
    ('나만또모르고있었지', 'jcklt_Q2H6s'), ('요새난리',        '-PcSU1Frd_c'),
    ('무슨템',         '4kzu6jdDkGo'), ('집돌이',          'C0lbKzY5geg'),
]

def sh(cmd, timeout=240):
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, (r.stdout or b'').decode('utf-8', 'ignore')
    except subprocess.TimeoutExpired:
        return -1, 'TIMEOUT'

def grab(vid, dst):
    """영상 받아 훅(1s)·본문(9s) 프레임 2장을 뽑는다."""
    v = os.path.join(WORK, dst + '.webm')
    if not os.path.exists(v):
        rc, _ = sh([YTDLP, '-f', 'bv*[height<=720]+ba/b[height<=720]',
                    '-o', os.path.join(WORK, dst + '.%(ext)s'),
                    f'https://www.youtube.com/shorts/{vid}'])
        if rc != 0:
            for ext in ('.mp4', '.mkv'):
                if os.path.exists(os.path.join(WORK, dst + ext)):
                    v = os.path.join(WORK, dst + ext); break
            else:
                return None, None
    for ext in ('.webm', '.mp4', '.mkv'):
        p = os.path.join(WORK, dst + ext)
        if os.path.exists(p): v = p; break
    else:
        return None, None
    hook = os.path.join(WORK, dst + '_hook.png')
    body = os.path.join(WORK, dst + '_body.png')
    for t, out in ((1, hook), (9, body)):
        sh(['ffmpeg', '-y', '-v', 'error', '-ss', str(t), '-i', v,
            '-frames:v', '1', out], timeout=90)
    return (hook if os.path.exists(hook) else None,
            body if os.path.exists(body) else None)

# ── 픽셀 실측 (지침서 §2) ────────────────────────────────────────
def hexc(c): return '#%02X%02X%02X' % c

def band_rows(px, W, H):
    """가로줄 대표색으로 영역 경계를 찾는다."""
    def kind(y):
        cs = [px[x, y] for x in range(6, W - 6, 3)]; n = len(cs)
        wh = sum(1 for c in cs if min(c) > 205)
        bk = sum(1 for c in cs if max(c) < 55)
        if wh / n > .70: return 'WHITE'
        if bk / n > .70: return 'BLACK'
        # 단색(띠) 판정: 표준편차가 작고 한 색이 지배적
        # ★띠 판정은 느슨해야 한다(2026-09-09). 채널 띠에는 로고·햄버거 아이콘·
        #   조회수 글자가 섞여 있어 '한 색이 75%'를 못 넘긴다(실측: 지식배송 주황띠가
        #   mix로 잡혀 제목 구간 시작점이 통째로 어긋났다).
        #   → 색을 16단계로 뭉쳐 세고, 절반만 같으면 단색 띠로 본다.
        q = collections.Counter((c[0] // 16, c[1] // 16, c[2] // 16) for c in cs)
        top, cnt = q.most_common(1)[0]
        if cnt / n > .50:
            # 대표색은 뭉치기 전 실제 색 중 그 구간에 속한 것의 최빈값
            real = collections.Counter(c for c in cs
                                       if (c[0] // 16, c[1] // 16, c[2] // 16) == top)
            return 'SOLID:' + hexc(real.most_common(1)[0][0])
        return 'mix'
    out, prev, st = [], None, 0
    for y in range(H):
        k = kind(y)
        if k != prev:
            if prev is not None: out.append((prev, st, y - 1))
            prev, st = k, y
    out.append((prev, st, H - 1))
    return out

def _groups(rs, gap=3):
    """연속한 y를 덩어리로 쪼갠다 — 줄과 줄 사이는 빈 줄로 끊긴다."""
    if not rs: return []
    out, cur = [], [rs[0]]
    for y in rs[1:]:
        if y - cur[-1] <= gap: cur.append(y)
        else: out.append(cur); cur = [y]
    out.append(cur)
    return [g for g in out if len(g) >= 6]


def text_lines(px, W, H, y0, y1, test):
    """글자가 있는 y줄을 찾아 **덩어리(=줄)마다** 높이·좌우폭을 잰다.

    ★1줄과 2줄을 뭉쳐 재면 안 된다(실측: 숏팡 1줄54+2줄48을 130px로 잘못 쟀다).
      2줄이 하늘색이어도 min(c)>200을 통과하므로 색으로는 못 가른다 — 빈 줄로 가른다.
    """
    rs = [y for y in range(y0, y1)
          if sum(1 for x in range(4, W - 4) if test(px[x, y])) > 3]
    out = []
    for g in _groups(rs):
        cs = [x for x in range(W)
              if sum(1 for y in range(g[0], g[-1] + 1) if test(px[x, y])) > 1]
        if not cs: continue
        out.append(dict(y0=g[0], y1=g[-1], h=g[-1] - g[0] + 1,
                        hpct=round((g[-1] - g[0] + 1) / H * 100, 1),
                        x0=cs[0], x1=cs[-1],
                        lpct=round(cs[0] / W * 100, 1),
                        rpct=round((W - 1 - cs[-1]) / W * 100, 1)))
    return out


def dom_color(px, y0, y1, x0, x1):
    c = collections.Counter()
    for y in range(y0, y1):
        for x in range(x0, x1, 2): c[px[x, y]] += 1
    return hexc(c.most_common(1)[0][0]) if c else None

def text_color(px, ln, test):
    """글자 색 — ★밝은(글자) 픽셀만 세어야 한다.

    글자 사각 영역에는 배경·외곽선 픽셀이 섞여 있어 그냥 최빈색을 쓰면
    검정이 뽑힌다(실측: 숏팡 하늘색 2줄이 #000000으로 나왔다).
    """
    c = collections.Counter()
    for y in range(ln['y0'], ln['y1'] + 1):
        for x in range(ln['x0'], ln['x1'] + 1):
            p = px[x, y]
            if test(p): c[p] += 1
    return hexc(c.most_common(1)[0][0]) if c else None


def measure(path):
    im = Image.open(path).convert('RGB'); px = im.load(); W, H = im.size
    bands = band_rows(px, W, H)
    # 상단 띠 = 첫 구간
    top = bands[0]
    res = {'size': f'{W}x{H}', 'bands': [], 'top_band': None,
           'title_bg': None, 'lines': [], 'white_box': None, 'video_from': None}
    for k, a, b in bands:
        if b - a < 3: continue
        res['bands'].append({'kind': k, 'y0': a, 'y1': b,
                             'pct': f'{a/H*100:.1f}-{b/H*100:.1f}'})
    res['top_band'] = {'y0': top[1], 'y1': top[2],
                       'color': dom_color(px, max(2, top[1]), min(top[2], top[1] + 40), 4, W - 4),
                       'hpct': round((top[2] - top[1] + 1) / H * 100, 1)}
    # 제목 영역 배경 = 띠 아래 왼쪽 끝 색
    ty0 = top[2] + 2
    res['title_bg'] = dom_color(px, ty0 + 4, min(ty0 + 90, H - 2), 2, 16)
    # ── 글자 줄 ───────────────────────────────────────────────
    # ★밝은 글자(흰색·하늘색·노랑 전부)를 한 번에 잡고 **덩어리로 가른다**.
    #   색으로 1줄/2줄을 가르려 하면 안 된다 — 하늘색도 min>200을 통과한다.
    bright = lambda c: min(c) > 165 or (max(c) > 205 and max(c) - min(c) > 60)
    # 글자 구간 끝 = 띠 아래 첫 흰 구간(흰 한줄박스) 앞까지
    seg_end = min(ty0 + 150, H - 2)
    for k, aa, bb in bands:
        if k == 'WHITE' and bb - aa > 6 and aa > ty0 + 20:
            seg_end = aa; break
    lines = text_lines(px, W, H, ty0, seg_end, bright)
    # ★글자가 아닌 것을 걸러낸다(2026-09-09). 실측: 지식배송에서 영상 속 밝은 물체가
    #   76px·여백 0%짜리 '3줄'로 잡혔다. 진짜 제목 줄은 두 조건을 만족한다:
    #     ① 화면 높이의 3~14% (그보다 크면 글자가 아니라 배경 덩어리)
    #     ② 좌우 여백이 한쪽이라도 1% 이상 (끝에서 끝까지 닿으면 글자가 아니다)
    lines = [l for l in lines
             if 3.0 <= l['hpct'] <= 14.0 and (l['lpct'] >= 1.0 or l['rpct'] >= 1.0)]
    for i, ln in enumerate(lines[:3]):
        ln['color'] = text_color(px, ln, bright)
        ln['role'] = f'{i+1}줄'
        res['lines'].append(ln)
    # ── 흰 박스 (글자 아래 첫 흰 구간) ──────────────────────────
    last_y = res['lines'][-1]['y1'] if res['lines'] else ty0
    for k, aa, bb in bands:
        if k == 'WHITE' and bb - aa > 6 and aa > last_y:
            dark = lambda c: max(c) < 95
            t = text_lines(px, W, H, aa, bb + 1, dark)
            res['white_box'] = {'y0': aa, 'y1': bb,
                                'pct': f'{aa/H*100:.1f}-{bb/H*100:.1f}',
                                'text': t[0] if t else None}
            res['video_from'] = {'y': bb + 1, 'pct': round((bb + 1) / H * 100, 1)}
            break
    if not res.get('video_from') and res['lines']:
        y = res['lines'][-1]['y1'] + 6
        res['video_from'] = {'y': y, 'pct': round(y / H * 100, 1)}
    # ── 스타일 지문: 같은 스타일을 두 번 만들지 않기 위한 키 ────
    res['fingerprint'] = '|'.join([
        res['top_band']['color'] or '-', res['title_bg'] or '-',
        ','.join(l['color'] or '-' for l in res['lines']),
        'WB' if res.get('white_box') else 'noWB'])
    return res


def fmt(name, hook, body):
    """GPT에 그대로 붙일 지시문"""
    L = [f'[{name} — 훅]']
    t = hook['top_band']
    L.append(f"상단 띠: y0부터 y{t['y1']} 즉 {t['hpct']}퍼센트, 배경색 {t['color']}, 가운데 채널명 {name}")
    L.append(f"제목 영역 배경: 불투명 {hook['title_bg']} 박스")
    for ln in hook['lines']:
        L.append(f"제목 {ln['role']}: 색 {ln['color']}, 글자높이 {ln['h']}px 즉 {ln['hpct']}퍼센트, "
                 f"x{ln['x0']}부터 x{ln['x1']} 좌여백 {ln['lpct']}퍼센트 우여백 {ln['rpct']}퍼센트")
    wb = hook.get('white_box')
    if wb:
        tt = wb['text']
        L.append(f"흰 한줄박스: y{wb['y0']}부터 y{wb['y1']}" +
                 (f", 검은글씨 높이 {tt['h']}px 즉 {tt['hpct']}퍼센트, x{tt['x0']}부터 x{tt['x1']}" if tt else ""))
    vf = hook.get('video_from')
    if vf: L.append(f"영상: y{vf['y']} 즉 {vf['pct']}퍼센트부터 화면 끝까지")
    if body:
        L.append(f'\n[{name} — 본문]')
        bt = body['top_band']
        L.append(f"상단 띠: y0부터 y{bt['y1']} 즉 {bt['hpct']}퍼센트, 배경색 {bt['color']}")
        for bd in body['bands'][:6]:
            L.append(f"  구간 {bd['kind']}: y{bd['y0']}-{bd['y1']} ({bd['pct']}퍼센트)")
    return '\n'.join(L)

def main():
    done, fail = [], []
    for i, (name, vid) in enumerate(TARGETS, 1):
        slug = f't{i:02d}'
        print(f'[{i:2d}/{len(TARGETS)}] {name} ({vid}) ...', flush=True)
        h, b = grab(vid, slug)
        if not h:
            print('   ✗ 다운로드 실패'); fail.append(name); continue
        try:
            mh = measure(h)
            mb = measure(b) if b else None
        except Exception as e:
            print(f'   ✗ 실측 실패 {e!r}'); fail.append(name); continue
        txt = fmt(name, mh, mb)
        with open(os.path.join(WORK, f'{slug}_{name}.txt'), 'w', encoding='utf-8') as f:
            f.write(txt)
        json.dump({'name': name, 'vid': vid, 'hook': mh, 'body': mb},
                  open(os.path.join(WORK, f'{slug}_{name}.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        nl = len(mh['lines'])
        print(f"   ✓ 띠{mh['top_band']['color']} 제목배경{mh['title_bg']} 글자{nl}줄")
        done.append(name)
    print(f'\n완료 {len(done)} / 실패 {len(fail)}')
    if fail: print('실패:', ', '.join(fail))
    print('결과:', WORK)

if __name__ == '__main__':
    main()
