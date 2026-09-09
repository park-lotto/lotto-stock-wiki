# -*- coding: utf-8 -*-
"""썰채널 실측 프레임 모음 사진 → '글자만 지운 틀 PNG'을 자동으로 뽑는다.

왜 이렇게 하나(2026-09-05 사장님 "유튜브 썰채널 조회수 터진 걸로 해봐"):
  코드로 띠 색·높이를 흉내내면 느낌이 안 산다(사장님이 08-31에도 같은 지적).
  원본 프레임을 그대로 쓰고 글자만 지우면 색·여백·구분선이 저절로 맞는다.

원리 — 손으로 좌표를 찍지 않는다:
  UI 영역(띠·흰 블록)은 가로로 색이 균일하다. 영상은 안 그렇다.
  그래서 위에서부터 '가로 표준편차가 낮은 행'이 이어지는 데까지가 UI다.
  글자 지우기 = 각 행을 그 행의 중앙값 색으로 칠한다(글자는 소수라 중앙값에 안 잡힌다).
  단 좌우 끝 12%는 남긴다 — 거기 ☰·🔍 아이콘이 있다.
"""
import os, sys, io
import numpy as np
from PIL import Image

SRC = 'C:/Users/TheRose/Desktop/썰채널_실측프레임'
OUT = 'frames'
KEEP_SIDE = 0.12      # 좌우 이만큼은 원본 유지(아이콘 보존)
UI_MAX_STD = 26       # 이보다 균일하면 UI 행으로 본다
UI_MIN_ROWS = 40      # UI가 최소 이만큼은 이어져야 한다


def cells(img):
    """모음 사진을 4열 3행 격자로 잘라 세로 프레임 12장으로."""
    W, H = img.size
    cw, ch = W // 4, H // 3
    for r in range(3):
        for c in range(4):
            yield r * 4 + c, img.crop((c * cw, r * ch, (c + 1) * cw, (r + 1) * ch))


def ui_height(a):
    """위에서부터 UI(띠+흰 블록+자막 영역)가 어디까지인지.

    ★2026-09-05 수정: 처음엔 '가로로 균일한 행'만 UI로 봤는데, 흰 블록 안의
      제목 글자 줄은 균일하지 않아 거기서 끊겼다(살림킹왕짱 실측 20% — 실제는 37%).
      그래서 판정을 둘로 넓힌다: 그 줄의 **바탕색**(중앙값)이
        (a) 흰색에 가깝거나  (b) 좌우로 균일하다
      면 UI다. 글자가 있어도 바탕은 흰색이므로 이 조건에 걸린다.
      영상 구간은 바탕이 흰색도 아니고 균일하지도 않아 자연히 걸러진다.
    """
    H = a.shape[0]
    last, gap = 0, 0
    for y in range(int(H * 0.6)):
        med = np.median(a[y], axis=0)
        flat = a[y].std(axis=0).mean() <= UI_MAX_STD
        white = med.min() >= 228
        if flat or white:
            last, gap = y, 0
        else:
            gap += 1
            if gap > 45:            # 45줄 넘게 UI가 아니면 영상이 시작된 것
                break
    return last + 1


def make_template(cell):
    """글자 지운 틀 RGBA(1080x1920). UI 아래는 투명."""
    im = cell.convert('RGB').resize((1080, 1920), Image.LANCZOS)
    a = np.array(im)
    h = ui_height(a)
    if h < UI_MIN_ROWS:
        return None, 0
    out = np.zeros((1920, 1080, 4), dtype=np.uint8)
    keep = int(1080 * KEEP_SIDE)
    for y in range(h):
        med = np.median(a[y], axis=0).astype(np.uint8)   # 그 줄의 바탕색
        out[y, :, :3] = med
        out[y, :keep, :3] = a[y, :keep]                  # 왼쪽 아이콘 유지
        out[y, -keep:, :3] = a[y, -keep:]                # 오른쪽 아이콘 유지
        out[y, :, 3] = 255
    return Image.fromarray(out, 'RGBA'), h


def caption_pos(cell, ui_h):
    """UI 아래(영상 구간)에서 자막이 앉는 자리를 찾는다.

    자막은 가로로 글자가 흩어져 표준편차가 크고, 위아래로 짧게 뭉친다.
    영상 자체도 들쭉날쭉하니 '주변보다 튀는 구간'으로 본다. 못 찾으면 None.
    """
    a = np.array(cell.convert('L').resize((1080, 1920), Image.LANCZOS), dtype=float)
    seg = a[ui_h:]
    if seg.shape[0] < 100:
        return None
    sd = seg.std(axis=1)
    base = np.median(sd)
    hot = [i for i, v in enumerate(sd) if v > base * 1.55 and v > 40]
    if not hot:
        return None
    runs, s0, prev = [], hot[0], hot[0]
    for i in hot[1:]:
        if i - prev > 14:
            runs.append((s0, prev)); s0 = i
        prev = i
    runs.append((s0, prev))
    runs = [r for r in runs if r[1] - r[0] >= 26]
    if not runs:
        return None
    y0, y1 = max(runs, key=lambda r: r[1] - r[0])
    return {'top_pct': round((ui_h + y0) / 1920 * 100, 1),
            'bottom_pct': round((ui_h + y1) / 1920 * 100, 1)}


HOOK_CELLS = (0, 4, 8)     # 편당 4프레임 중 첫 칸 = 1초 지점 = 후킹


def pick(img, want_hook):
    """후킹/본문 중 UI가 가장 두툼한 칸을 고른다(제목·조회수까지 다 보이는 프레임)."""
    best = None
    for idx, cell in cells(img):
        if (idx in HOOK_CELLS) != want_hook:
            continue
        tpl, h = make_template(cell)
        if tpl is None:
            continue
        if best is None or h > best[1]:
            best = (tpl, h, idx, cell)
    return best


def main():
    os.makedirs(OUT, exist_ok=True)
    import json
    meta = {}
    for fn in sorted(os.listdir(SRC)):
        if not fn.lower().endswith(('.jpg', '.png')):
            continue
        name = os.path.splitext(fn)[0]
        img = Image.open(os.path.join(SRC, fn))
        rec = {}
        for kind, want in (('hook', True), ('body', False)):
            got = pick(img, want)
            if not got:
                print('  %-22s %-5s UI 못 찾음' % (name, kind)); continue
            tpl, h, idx, cell = got
            p = os.path.join(OUT, '%s__%s.png' % (name, kind))
            tpl.save(p)
            cap = caption_pos(cell, h)
            rec[kind] = {'file': os.path.basename(p),
                         'ui_pct': round(h / 1920 * 100, 1),
                         'caption': cap}
            print('  %-22s %-5s UI %4.1f%%  자막 %s  칸#%d' %
                  (name, kind, h / 1920 * 100,
                   ('%.1f~%.1f%%' % (cap['top_pct'], cap['bottom_pct'])) if cap else '못 찾음', idx))
        if rec:
            meta[name] = rec
    io.open(os.path.join(OUT, 'frames.json'), 'w', encoding='utf-8').write(
        json.dumps(meta, ensure_ascii=False, indent=1))
    print('틀 %d채널 × 후킹·본문 → frames/frames.json' % len(meta))


if __name__ == '__main__':
    main()
