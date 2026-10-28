# -*- coding: utf-8 -*-
"""카드뉴스 레퍼런스 재기 — **agy 가 읽고(무엇이 어디 있나) 프로그램이 잰다(정확히 어디·무슨 색)** (2026-10-08).

■ 왜 이 파일이 생겼나 (쇼츠대폭발 10-08 «레퍼런스를 골라도 그대로 안 나온다» · 08-17 반려 4회의 근본 원인)
    예전에는 표지를 몇 가지 낱말(anchor·align·ink)로 줄인 뒤 고정 틀 12종 중 «가장 가까운 것»으로 다시 그렸다.
    틀 밖의 배치(단색 띠·두 줄 다른 색·외곽선 글자·로고 자리)는 표현할 길이 없었고, 글자 색은 흰/검정 둘뿐이었다.
    전자책 시제품(`강의_2기/4주차_자료/전자책_시제품`)에서 «재서 → 코드로 재현» 이 agy 비교 5.5 → 8.8 로 통했다.
    같은 방식으로 간다.

■ 누가 무엇을 하나 (전역 규칙 6-1 — 그림 판독은 구독 agy 만 · 유료 API 금지)
    ① agy(view_file) — 줄마다 글자·대략 상자(0~1000)·역할·글꼴 갈래·굵기·외곽선/형광펜/색 낱말 여부, 단색 면, 그늘 종류.
       숫자로 못 재는 것(글꼴 갈래·역할)과 «어디쯤»을 맡는다. 질문과 답 모양은 **서버가 준다**(`question`·`schema`).
    ② 프로그램(numpy) — agy 상자를 출발점으로 화소를 재서 글자 잉크 상자·글자 색·외곽선 색·두께·형광펜 상자·단색 면의
       정확한 자리와 색을 낸다. 같은 자를 레퍼런스와 우리 결과물에 똑같이 대서 차이를 숫자로 본다(검증 도구가 이것을 쓴다).

■ 실행기 경계 (CLAUDE.md §실행기)
    여기에는 **일반 기술**만 있다 — agy 부르기, 화소 세기. 무엇을 물을지(질문·스키마)와 잰 값을 어떻게 배치할지(틀)는 서버다.
    scipy·opencv 없이 numpy·PIL 만 쓴다(설치 요구 모듈 `REQUIRED_MODULES` 그대로 · 윈도우·맥 같은 결과).
"""

import json
import os

import numpy as np
from PIL import Image


class RefSpecError(RuntimeError):
    """재기 실패. 사유는 사람이 읽을 말로."""


# ── ① agy 판독 ──────────────────────────────────────────────


def read(image_path, question, schema, model, timeout_s=300, env=None):
    """agy 가 그림 한 장을 view_file 로 직접 보고 서버가 준 질문에 서버가 준 모양(JSON 스키마)으로 답한다.

    ★유료로 빠지는 길을 막는다 — agy 설정이 API 키 로그인(modelProvider=gemini)이거나 유료 크레딧 대체(useG1Credits)가
      켜져 있으면 부르지 않는다(전역 규칙 6-1 · `agy_review_bridge.review` 와 같은 판정).
    ★거부(한도·로그인·속도)는 `agy_transport_client.invoke` 가 이 실행 전체를 멈추는 예외로 올린다 — 여기서 삼키지 않는다.
    """
    import agy_transport_client as AGY                              # noqa: PLC0415
    import agy_transport_pc_env as PC                               # noqa: PLC0415
    path = os.path.abspath(image_path)
    if not os.path.isfile(path):
        raise RefSpecError(f"레퍼런스 그림이 없습니다: {path}")
    settings = PC.agy_settings_path(env)
    try:
        saved = json.load(open(settings, encoding="utf-8")) if os.path.exists(settings) else {}
    except (OSError, ValueError) as e:
        raise RefSpecError(f"agy 설정 파일을 읽지 못했습니다({type(e).__name__}) — 설정은 그대로 두었습니다: {settings}")
    if isinstance(saved, dict) and saved.get("modelProvider") == "gemini":
        raise RefSpecError("agy 가 API 키 로그인으로 설정돼 있습니다 — 구독 로그인으로 바꿔야 합니다(유료 API 를 쓰지 않습니다).")
    if isinstance(saved, dict) and saved.get("useG1Credits") is True:
        raise RefSpecError("agy 의 유료 크레딧 대체(useG1Credits)가 켜져 있습니다 — 끄고 다시 하세요(구독 한도만 씁니다).")
    res = AGY.invoke(question, kind="view", files=[path], schema=schema, model=model,
                     timeout_s=timeout_s, cwd=os.path.dirname(path), env=env)
    if not res.get("ok"):
        raise RefSpecError(f"agy 판독 실패({res.get('code')}): {str(res.get('message') or '')[:200]}")
    got = res.get("json")
    if not isinstance(got, dict):
        raise RefSpecError("agy 답이 JSON 묶음이 아닙니다.")
    return got


def merge_decor(main, extra, iou):
    """두 판독(전체 판독 · 장식만 묻는 판독)의 장식을 합친다. 같은 갈래로 많이 겹치는(IoU ≥ iou) 것은 하나로 — 처음 쪽을 남긴다.

    ★왜: 한 번에 다 묻는 판독은 장식을 자주 빠뜨린다(10-08 @unni_secret_note 표지 1 오른쪽 별 스티커). 겹침 문턱은 서버가 준다."""
    def _iou(a, b):
        try:
            ay0, ax0, ay1, ax1 = [float(v) for v in a]
            by0, bx0, by1, bx1 = [float(v) for v in b]
        except (TypeError, ValueError):
            return 0.0
        iw = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        ih = max(0.0, min(ay1, by1) - max(ay0, by0))
        inter = iw * ih
        u = (ax1 - ax0) * (ay1 - ay0) + (bx1 - bx0) * (by1 - by0) - inter
        return inter / u if u > 0 else 0.0
    out = [d for d in (main or []) if isinstance(d, dict)]
    for d in extra or []:
        if not isinstance(d, dict):
            continue
        if any(o.get("kind") == d.get("kind") and _iou(o.get("box_2d"), d.get("box_2d")) >= iou for o in out):
            continue
        out.append(d)
    return out


# ── ② 화소 재기 ─────────────────────────────────────────────


def _load(path, max_side=1400):
    """RGB 배열(정수). 아주 큰 그림은 줄여서 잰다 — 결과는 전부 비율(0~1)이라 크기와 무관하다."""
    im = Image.open(path).convert("RGB")
    s = max(im.size)
    if s > max_side:
        k = max_side / s
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
    return np.asarray(im).astype(np.int32)


def hex_of(c):
    return "#%02X%02X%02X" % tuple(int(max(0, min(255, round(float(v))))) for v in c[:3])


def rgb_of(h):
    s = str(h or "").strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return None
    try:
        v = int(s, 16)
    except ValueError:
        return None
    return np.array([(v >> 16) & 255, (v >> 8) & 255, v & 255], dtype=np.int32)


def _box_px(box, w, h):
    """agy 상자 [ymin,xmin,ymax,xmax](0~1000) → 화소 (x0,y0,x1,y1). 모양이 틀리면 None."""
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    try:
        y0, x0, y1, x1 = (float(v) for v in box)
    except (TypeError, ValueError):
        return None
    if y1 <= y0 or x1 <= x0:
        return None
    return (int(max(0, min(w, x0 / 1000 * w))), int(max(0, min(h, y0 / 1000 * h))),
            int(max(0, min(w, x1 / 1000 * w))), int(max(0, min(h, y1 / 1000 * h))))


def _kmeans(px, k=4, iters=12):
    """결정적 k-평균(밝기 분위수로 시작). 표본은 많아도 8천 개로 고르게 뽑는다 — 같은 그림이면 같은 답."""
    if len(px) == 0:
        return np.zeros((0, 3)), np.zeros(0, dtype=int)
    step = max(1, len(px) // 8000)
    sample = px[::step].astype(np.float64)
    lum = sample @ np.array([0.299, 0.587, 0.114])
    order = np.argsort(lum, kind="stable")
    cent = np.array([sample[order[int((i + 0.5) / k * (len(order) - 1))]] for i in range(k)])
    for _ in range(iters):
        d = ((sample[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                cent[j] = sample[m].mean(0)
    d = ((px.astype(np.float64)[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
    return cent, d.argmin(1)


def _dist(a, c):
    return np.sqrt(((a - np.asarray(c, dtype=np.float64)) ** 2).sum(-1))


def _runs(flags):
    """참인 칸의 연속 구간 [(시작, 끝+1)…]."""
    out, s = [], None
    for i, f in enumerate(list(flags) + [False]):
        if f and s is None:
            s = i
        elif not f and s is not None:
            out.append((s, i))
            s = None
    return out


def _shift(mask, dy, dx):
    out = np.zeros_like(mask)
    h, w = mask.shape
    ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
    xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
    out[yd, xd] = mask[ys, xs]
    return out


def _dilate(mask, r):
    out = mask.copy()
    for _ in range(max(0, int(r))):
        out = out | _shift(out, 1, 0) | _shift(out, -1, 0) | _shift(out, 0, 1) | _shift(out, 0, -1)
    return out


def _erode(mask, r):
    out = mask.copy()
    for _ in range(max(0, int(r))):
        out = out & _shift(out, 1, 0) & _shift(out, -1, 0) & _shift(out, 0, 1) & _shift(out, 0, -1)
    return out


#: 재기 문턱(글자 색 거리·행 문턱·면 비율 등)은 **서버가 준다**(`volcano_cardnews.REFSPEC_RULES` — 근거는 거기에).
#: 실행기에 숫자를 두지 않는다(§실행기 경계 · 경계 검사 «명세 숫자가 배급 코드에 박혀 있지 않다»).
_RULES = {}


def _r(key):
    if key not in _RULES:
        raise RefSpecError(f"재기 규칙에 {key} 가 없습니다 — 서버가 준 rules 를 measure 에 넘기세요.")
    return float(_RULES[key])


def _line_ink(img, box, hint_rgb, extra_rgbs=()):
    """agy 상자 근처에서 글자 획 화소를 찾아 **잉크 상자·글자 색**을 잰다.

    ■ 방법
        상자를 위아래로 줄 높이의 0.35배, 좌우로 폭의 4% 넓혀 그 안의 색을 넷으로 묶고(k-평균),
        agy 가 말한 글자 색에 가장 가까운 묶음을 글자로 본다. agy 색은 대략이라(실측 #5CE1E6 처럼) 묶음 중심으로 바로잡는다.
        줄 높이 방향은 «agy 상자 가운데를 지나는 연속 구간», 가로는 «글자 화소가 있는 열의 범위»(낱말 사이 빈칸은 줄 높이의
        일정 배수까지 이어 본다 — 서버 규칙 word_gap)다. 사진 속 같은 색 화소가 섞여도 agy 상자에서 줄 높이의 절반 넘게 벗어나지 않게 막는다.
    """
    h, w = img.shape[:2]
    x0, y0, x1, y1 = box
    bh = max(2, y1 - y0)
    rx0, rx1 = max(0, x0 - int(0.04 * w)), min(w, x1 + int(0.04 * w))
    ry0, ry1 = max(0, y0 - int(0.35 * bh)), min(h, y1 + int(0.35 * bh))
    reg = img[ry0:ry1, rx0:rx1]
    if reg.size == 0:
        return None
    flat = reg.reshape(-1, 3)
    cent, lab = _kmeans(flat, 4)
    if len(cent) == 0:
        return None
    # 글자 묶음 = agy 색에 가장 가까운 묶음. 다만 agy 상자 **안쪽**에 실제로 많이 있는 묶음이어야 한다.
    inner = np.zeros(reg.shape[:2], dtype=bool)
    inner[max(0, y0 - ry0):max(0, y1 - ry0), max(0, x0 - rx0):max(0, x1 - rx0)] = True
    labs = lab.reshape(reg.shape[:2])
    cand = []
    for j in range(len(cent)):
        share = float((labs[inner] == j).mean()) if inner.any() else 0.0
        if share < _r("cand_share"):
            continue
        dist = float(_dist(cent[j][None, :], hint_rgb)[0]) if hint_rgb is not None else 0.0
        cand.append((dist, -share, j))
    if not cand:
        return None
    cand.sort()
    j = cand[0][2]
    c = cent[j]
    tol = max(38.0, 0.45 * float(np.sort(_dist(cent, c))[1]) if len(cent) > 1 else 38.0)
    regf = reg.astype(np.float64)
    # ★agy 색 근처 화소가 상자 안에 충분하면 **그 화소들의 중앙값**을 글자 색으로 본다(묶음 중심보다 앞선다).
    #   외곽선 글자는 획 가장자리의 섞인 색이 큰 묶음이 되어 묶음 중심이 주황 → 갈색(#A15927)으로 끌려갔다
    #   (@chaegssulmi 실측 · agy #EB7726). 두 번 좁혀 가운데 색을 잡는다.
    if hint_rgb is not None and inner.any():
        near = _dist(regf, hint_rgb) < _r("hint_tol")
        if float(near[inner].mean()) >= 0.02:
            c = np.median(regf[near & inner], 0)
            near = _dist(regf, c) < _r("hint_narrow") * _r("hint_tol")
            if (near & inner).any():
                c = np.median(regf[near & inner], 0)
            tol = _r("hint_narrow") * _r("hint_tol")
    fill_mask = (_dist(regf, c) < tol)
    # ★한 줄에 색이 둘 이상이면(낱말만 다른 색 — @detailed «IDENTIFY» · @chaegssulmi «'이 물건'») 그 색 화소도 같은 줄의
    #   글자다. 빼면 낱말 사이가 크게 비어 줄이 그 앞에서 끊긴다(실측: 줄 폭 0.26 으로 잘렸다). 상자는 합친 것으로 잰다.
    mask = fill_mask.copy()
    for ex in extra_rgbs:
        mask |= _dist(regf, ex) < 60
    # 행 — agy 상자 가로 범위 안에서 글자 화소가 있는 행. ★agy 상자에서 줄 높이의 0.2 넘게 벗어나지 않는다 —
    #   위아래 줄이 같은 색이면 그 줄까지 이어 붙는다(실측: @detailed 2행이 3행과 붙어 높이 0.099).
    wy0, wy1 = max(0, (y0 - ry0) - int(0.2 * bh)), min(mask.shape[0], (y1 - ry0) + int(0.2 * bh))
    cols_in = slice(max(0, x0 - rx0), max(1, x1 - rx0))
    rowfrac = mask[:, cols_in].mean(1)
    # ★문턱은 그 줄의 가장 진한 행에 견준다 — 사진 속 같은 색 몇 점(하늘·반사)이 행 하나를 «글자» 로 만들지 않게.
    #   절대 문턱만 쓰니 줄 높이가 agy 상자의 1.4배까지 부풀었다(실측 25/252 줄 · 문턱 값은 서버 규칙).
    peak = float(rowfrac[wy0:wy1].max()) if wy1 > wy0 else 0.0
    on = rowfrac > max(_r("row_abs"), _r("row_rel") * peak)
    on[:wy0] = False
    on[wy1:] = False
    mid = ((y0 + y1) // 2) - ry0
    runs = _runs(on)
    if not runs:
        return None
    # 가운데 행을 지나는 구간(없으면 가장 가까운 구간)을 잡고, 줄 높이의 0.15 안쪽 틈은 이어 붙인다
    gap = max(2, int(0.15 * bh))
    merged = []
    for a, b in runs:
        if merged and a - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    best = min(merged, key=lambda r: 0 if r[0] <= mid < r[1] else min(abs(r[0] - mid), abs(r[1] - mid)))
    ty0, ty1 = best
    if ty1 - ty0 < 2:
        return None
    sub = mask[ty0:ty1]
    colcnt = sub.sum(0)
    on_c = colcnt >= max(1, int(_r("col_frac") * (ty1 - ty0)))
    cruns = _runs(on_c)
    if not cruns:
        return None
    lh = ty1 - ty0
    cmid = ((x0 + x1) // 2) - rx0
    groups = []
    for a, b in cruns:
        if groups and a - groups[-1][1] <= int(_r("word_gap") * lh):
            groups[-1] = (groups[-1][0], b)
        else:
            groups.append((a, b))
    # agy 상자와 가장 많이 겹치는 묶음
    ax0, ax1 = x0 - rx0, x1 - rx0
    g = max(groups, key=lambda r: min(r[1], ax1) - max(r[0], ax0) - 0.001 * abs((r[0] + r[1]) / 2 - cmid))
    tx0, tx1 = g
    core = _erode(fill_mask[ty0:ty1, tx0:tx1], 1)
    pix = reg[ty0:ty1, tx0:tx1][core] if core.any() else reg[ty0:ty1, tx0:tx1][fill_mask[ty0:ty1, tx0:tx1]]
    color = np.median(pix, 0) if len(pix) else c
    # ★글자 색이 위→아래로 변하는 줄(세로 그라데이션 · @unni_secret_note 민트 R 170→229 실측)은 위·아래 1/3 의 색을 따로 잰다.
    #   한 색(중앙값)만 남기면 그 줄이 «옅은 민트 한 색» 이 되어 위쪽이 레퍼런스보다 옅게 나온다.
    grad = None
    cm = core if core.any() else fill_mask[ty0:ty1, tx0:tx1]
    third = max(1, (ty1 - ty0) // 3)
    top_px = reg[ty0:ty0 + third, tx0:tx1][cm[:third]]
    bot_px = reg[ty1 - third:ty1, tx0:tx1][cm[-third:]]
    if len(top_px) >= 20 and len(bot_px) >= 20:
        mt, mb = np.median(top_px, 0), np.median(bot_px, 0)
        # 위·아래 1/3 의 중앙값은 높이 1/6·5/6 지점의 색이다 — 곧은 변화로 보고 양 끝(0·1)의 색으로 늘린다
        #   (렌더는 잉크 상자 위 끝→아래 끝으로 칠한다 · 늘리지 않으면 변화 폭이 2/3 로 줄어든다)
        grad = (np.clip(mt - (mb - mt) / 4.0, 0, 255), np.clip(mb + (mb - mt) / 4.0, 0, 255))
    full = np.zeros(img.shape[:2], dtype=bool)
    full[ry0 + ty0:ry0 + ty1, rx0 + tx0:rx0 + tx1] = fill_mask[ty0:ty1, tx0:tx1]
    ink = int(fill_mask[ty0:ty1, tx0:tx1].sum())
    return {"px": (rx0 + tx0, ry0 + ty0, rx0 + tx1, ry0 + ty1), "color": color, "mask": full,
            "density": ink / max(1, (tx1 - tx0) * (ty1 - ty0)), "grad": grad}


def _outline(img, mask, line_h, hint_rgb):
    """글자 외곽선(테두리) 색·두께. 글자 화소를 한 칸씩 부풀려 테두리 띠의 색이 hint 에 가까운 동안을 두께로 본다."""
    if hint_rgb is None or not mask.any():
        return None
    prev = mask
    width = 0
    colors = []
    for r in range(1, max(2, int(0.2 * line_h)) + 1):
        ring = _dilate(prev, 1) & ~prev
        if not ring.any():
            break
        pix = img[ring].astype(np.float64)
        near = _dist(pix, hint_rgb) < 70
        # ★첫 띠는 글자 획과 테두리가 섞인 경계(안티앨리어싱)라 반쯤만 맞는다 — 실측 @chaegssulmi 0.43~0.50 로 끊겨
        #   «외곽선 없음» 으로 재고 있었다(agy 는 세 줄 다 검은 테두리라 했다). 첫 띠는 0.3 이면 지나간다.
        if near.mean() < (0.3 if r == 1 else 0.5):
            break
        colors.append(pix[near])
        width = r
        prev = prev | ring
    if not width:
        return None
    col = np.median(np.concatenate(colors), 0)
    return {"color": hex_of(col), "w": round(width / max(1, line_h), 4)}


def _outline_runs(img, rect_px, fill_rgb, out_rgb):
    """외곽선을 **행마다 색 구간(run)** 으로 잰다 — 글자 색 구간의 바로 옆(1화소 경계 허용)이 테두리 색 구간인가.

    ■ 왜 (10-08 실측: agy 가 외곽선이라 한 46줄 중 4줄만 재졌다)
        글자 화소를 부풀려 둘레를 보는 첫 방법은 «글자 색 = 사진 어두운 곳» 이면(검은 글자 + 흰 테두리 @ppo_news)
        사진 화소가 글자로 섞여 둘레가 엉뚱해졌다. 구간으로 보면 글자 획 바로 옆만 본다 — 사진은 획 옆에 붙어 있지 않다.
    돌려주는 것: (있음 비율 0~1, 테두리 두께 화소 중앙값, 본 획 옆 수)."""
    x0, y0, x1, y1 = rect_px
    reg = img[y0:y1, x0:x1].astype(np.float64)
    if reg.size == 0:
        return 0.0, 0.0, 0
    F = _dist(reg, fill_rgb) < 60
    O = _dist(reg, out_rgb) < 60
    sides = hits = 0
    widths = []
    lh = max(1, y1 - y0)
    for y in range(F.shape[0]):
        lab = np.where(F[y], 1, np.where(O[y], 2, 0))
        runs = []
        start = 0
        for i in range(1, len(lab) + 1):
            if i == len(lab) or lab[i] != lab[start]:
                runs.append((int(lab[start]), start, i))
                start = i
        for k, (t, a, b) in enumerate(runs):
            if t != 1 or b - a < 2:
                continue
            for nb in (k - 1, k + 1):
                j = nb
                if 0 <= j < len(runs) and runs[j][0] == 0 and runs[j][2] - runs[j][1] <= 1:
                    j = j - 1 if nb < k else j + 1          # 1화소 경계(섞인 색)는 건너뛴다
                if not (0 <= j < len(runs)):
                    continue
                sides += 1
                if runs[j][0] == 2:
                    hits += 1
                    widths.append(min(runs[j][2] - runs[j][1], int(0.5 * lh)))
    if not sides:
        return 0.0, 0.0, 0
    return hits / sides, (float(np.median(widths)) if widths else 0.0), sides


def _color_rect(img, center_box, hint_rgb, pad_rows, min_row_frac=0.3, tol=48.0, also_rgb=None):
    """hint 색으로 칠한 상자(형광펜·띠·단색 면)의 정확한 사각형과 색. 글자가 상자 안을 일부 가려도 되게 행·열 비율로 본다."""
    if hint_rgb is None:
        return None
    h, w = img.shape[:2]
    x0, y0, x1, y1 = center_box
    ry0, ry1 = max(0, y0 - pad_rows), min(h, y1 + pad_rows)
    reg = img[ry0:ry1].astype(np.float64)
    near = _dist(reg, hint_rgb) < tol
    if not near.any():
        return None
    color_near = near
    if also_rgb is not None:
        # ★글자 뒤 상자는 글자가 상자 안을 덮는다 — 글자 색 화소도 «상자 안» 으로 쳐야 열이 끊기지 않는다
        #   (10-08 실측 @hottopic_lab 검은 상자 + 흰 글자: 글자 지나는 열마다 상자 비율이 0.3 밑으로 떨어져 상자 폭이 0.07 로 재졌다).
        near = near | (_dist(reg, also_rgb) < tol)
    rows = near[:, max(0, x0):max(1, x1)].mean(1) >= min_row_frac
    runs = _runs(rows)
    if not runs:
        return None
    cy = (y0 + y1) / 2 - ry0
    a, b = min(runs, key=lambda r: 0 if r[0] <= cy < r[1] else min(abs(r[0] - cy), abs(r[1] - cy)))
    cols = near[a:b].mean(0) >= min(0.5, min_row_frac)
    cruns = _runs(cols)
    if not cruns:
        return None
    # 글자 획 가장자리(섞인 색)가 지나는 열은 상자 비율이 잠깐 떨어진다 — 상자 높이 안쪽의 틈은 이어 붙인다
    gap = max(2, (b - a) // 2)
    merged = []
    for r0, r1 in cruns:
        if merged and r0 - merged[-1][1] <= gap:
            merged[-1] = (merged[-1][0], r1)
        else:
            merged.append((r0, r1))
    cruns = merged
    cx = (x0 + x1) / 2
    c0, c1 = min(cruns, key=lambda r: 0 if r[0] <= cx < r[1] else min(abs(r[0] - cx), abs(r[1] - cx)))
    pix = reg[a:b, c0:c1][color_near[a:b, c0:c1]]
    if not len(pix):
        return None
    near = color_near
    # 모서리 둥글기 — 윗변에서 상자 색이 시작하는 자리가 모서리에서 얼마나 안쪽인가(상자 높이 대비).
    #   알약 모양(@forest.kr_ 머리말 배지)은 0.5 에 가깝고 각진 상자는 0 이다.
    top = near[a, c0:c1]
    first = int(np.argmax(top)) if top.any() else 0
    radius = round(min(0.5, first / max(1, b - a)), 3)
    return {"px": (c0, ry0 + a, c1, ry0 + b), "color": hex_of(np.median(pix, 0)), "radius": radius}


def _solid_bg(img):
    """테두리 화소가 한 색이면 그 색(단색 바탕). 아니면 None. 근거: 단색 표지는 가장자리 밝기편차 0.0~2.3 · 사진 31.7~78.6
    (2026-08-17 실측 `measure_cardnews_refs.FLAT_STD_MAX` 와 같은 자)."""
    h, w = img.shape[:2]
    b = max(2, int(0.02 * min(h, w)))
    edge = np.concatenate([img[:b].reshape(-1, 3), img[-b:].reshape(-1, 3),
                           img[:, :b].reshape(-1, 3), img[:, -b:].reshape(-1, 3)]).astype(np.float64)
    med = np.median(edge, 0)
    share = float((_dist(edge, med) < 24).mean())
    return (hex_of(med), share) if share >= 0.85 else (None, share)


def _lum_profile(img, rect, exclude, bands=10):
    """사진 영역의 띠별 평균 밝기(글자 상자는 뺀다). 그늘이 어디서 얼마나 진한지 비교하는 데 쓴다."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = rect
    lum = img[..., 0] * 0.299 + img[..., 1] * 0.587 + img[..., 2] * 0.114
    keep = np.zeros((h, w), dtype=bool)
    keep[y0:y1, x0:x1] = True
    for (a, b, c, d) in exclude:
        keep[b:d, a:c] = False
    out = []
    for i in range(bands):
        ya = y0 + (y1 - y0) * i // bands
        yb = y0 + (y1 - y0) * (i + 1) // bands
        m = keep[ya:yb]
        out.append(round(float(lum[ya:yb][m].mean()), 1) if m.any() else None)
    return out


def _norm(px_box, w, h):
    x0, y0, x1, y1 = px_box
    return [round(x0 / w, 4), round(y0 / h, 4), round(x1 / w, 4), round(y1 / h, 4)]


def _circle_inset(img, box, hint_rgb):
    """agy 가 장식이라 한 상자가 **테두리 있는 동그란 사진**(인셋)인지 재고, 맞으면 원의 상자·테두리 색·두께를 준다.

    ■ 방법 — 상자를 8% 넓힌 곳에서 agy 가 말한 테두리 색 화소를 모아 원을 맞춘다(대수 최소제곱 · 맞은 점으로 한 번 더).
      맞은 점이 각도 36칸 중 절반 넘게 퍼져 있으면 원이다(화면 가장자리에 잘린 인셋도 잡히게 — 둘레 표본만 보던
      첫 판은 @detailed 의 잘린 원을 0.57 로 놓쳤다). 두께 = 맞은 점의 반지름 퍼짐(지름 대비)."""
    if hint_rgb is None:
        return None
    hh, ww = img.shape[:2]
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    if bw < 20 or bh < 20 or not (0.7 <= bw / bh <= 1.4):
        return None
    ex, ey = int(0.08 * bw), int(0.08 * bh)
    rx0, ry0, rx1, ry1 = max(0, x0 - ex), max(0, y0 - ey), min(ww, x1 + ex), min(hh, y1 + ey)
    reg = img[ry0:ry1, rx0:rx1].astype(np.float64)
    m = _dist(reg, hint_rgb) < 60
    ys, xs = np.nonzero(m)
    if len(xs) < 60:
        return None
    if len(xs) > 6000:
        k = len(xs) // 6000 + 1
        xs, ys = xs[::k], ys[::k]
    X, Y = xs.astype(np.float64) + rx0, ys.astype(np.float64) + ry0

    def fit(X, Y):
        A = np.stack([X, Y, np.ones_like(X)], 1)
        bb = X * X + Y * Y
        sol, *_ = np.linalg.lstsq(A, bb, rcond=None)
        cx, cy = sol[0] / 2, sol[1] / 2
        r = float(np.sqrt(max(1e-9, sol[2] + cx * cx + cy * cy)))
        return cx, cy, r
    cx, cy, r = fit(X, Y)
    for _ in range(2):
        d = np.abs(np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) - r)
        inl = d < max(3.0, 0.06 * r)
        if inl.sum() < 40:
            return None
        cx, cy, r = fit(X[inl], Y[inl])
    d = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) - r
    inl = np.abs(d) < max(3.0, 0.06 * r)
    if r < 0.3 * min(bw, bh) or r > 0.75 * max(bw, bh):
        return None
    angs = np.floor((np.arctan2(Y[inl] - cy, X[inl] - cx) + np.pi) / (2 * np.pi) * 36).astype(int) % 36
    cover = len(set(angs.tolist())) / 36
    if cover < 0.5 or inl.mean() < 0.3:
        return None
    width = float(np.percentile(d[inl], 95) - np.percentile(d[inl], 5)) + 1
    col = np.median(reg[m], 0)
    px = (int(round(cx - r)), int(round(cy - r)), int(round(cx + r)), int(round(cy + r)))
    # 화면 밖으로 나간 원도 그대로 둔다(_norm 이 0~1 로 자르지 않게 바깥은 렌더가 잘라 그린다)
    return {"px": px, "color": hex_of(col), "w": round(width / max(1, 2 * r), 4), "cover": round(cover, 2)}


def measure(image_path, reading, rules):
    """agy 판독 + 화소 → 잰 명세(비율 0~1). 같은 함수를 레퍼런스와 우리 결과물에 똑같이 쓴다.

    돌려주는 모양:
      {"v":1, "size":[w,h], "bg":{"kind","color","photo_rect"}, "panels":[{"rect","color"}],
       "shade":{"kind","strength"}, "lum":[띠 10개], "align",
       "lines":[{"role","text","rect","color","outline","shadow","box","underline","words","font_class","weight","density",
                 "agy_rect"}],
       "decor":[{"kind","rect","color","note"}], "problems":[못 잰 것]}
    """
    if not isinstance(rules, dict) or not rules:
        raise RefSpecError("재기 규칙(rules)이 없습니다 — 서버가 준 값을 넘기세요.")
    _RULES.clear()
    _RULES.update(rules)
    img = _load(image_path)
    h, w = img.shape[:2]
    problems = []
    bg_in = reading.get("background") or {}
    lines_out, ink_boxes = [], []
    for i, ln in enumerate(reading.get("text_lines") or []):
        if not isinstance(ln, dict):
            continue
        box = _box_px(ln.get("box_2d"), w, h)
        if not box:
            problems.append(f"{i + 1}번 줄: agy 상자가 없습니다")
            continue
        hint = rgb_of(ln.get("color"))
        extra = [c for c in (rgb_of((wd or {}).get("color")) for wd in (ln.get("colored_words") or [])
                             if isinstance(wd, dict)) if c is not None]
        got = _line_ink(img, box, hint, extra)
        if not got:
            problems.append(f"{i + 1}번 줄 «{str(ln.get('text'))[:12]}»: 글자 화소를 못 찾았습니다 — agy 상자를 그대로 씁니다")
            rect_px, color, dens, mask = box, hint if hint is not None else np.array([255, 255, 255]), None, None
            grad = None
        else:
            rect_px, color, dens, mask = got["px"], got["color"], got["density"], got["mask"]
            grad = got.get("grad")
        lh = rect_px[3] - rect_px[1]
        out = {"role": ln.get("role") or "other", "text": str(ln.get("text") or ""),
               "rect": _norm(rect_px, w, h), "agy_rect": _norm(box, w, h),
               "color": hex_of(color), "font_class": ln.get("font_class") or "",
               "weight": ln.get("weight") or "", "shadow": bool(ln.get("shadow")),
               "density": round(dens, 4) if dens is not None else None,
               "outline": None, "box": None, "underline": None, "words": [], "gradient": None}
        if grad is not None and float(_dist(grad[0][None, :], grad[1])[0]) > _r("grad_dist"):
            out["gradient"] = [hex_of(grad[0]), hex_of(grad[1])]
        oc = rgb_of(ln.get("outline_color"))
        if oc is not None:
            # ★외곽선이 **있는지**는 agy 가 본 대로 따른다. 화소로는 «검은 테두리» 와 «글자 옆 어두운 사진» 을 못 가른다 —
            #   외곽선 없는 줄에 반대색을 대 보니 획 옆이 그 색인 비율이 0.95 였다(10-08 대조군 실측). 화소는 **두께·색**만 잰다:
            #   획 바로 옆 테두리 색 구간 길이의 중앙값(행마다 · `_outline_runs`). 46줄 중 이 방법으로 두께가 나온 것 33줄 —
            #   나머지는 획 옆 테두리 구간이 거의 없어(그림자형·두꺼운 입체 글자) 두께를 못 재니 그 사실을 남기고 옮기지 않는다.
            share, wpx, sides = _outline_runs(img, rect_px, rgb_of(out["color"]), oc)
            if sides and wpx >= 1:
                ring = _outline(img, mask, lh, oc) if mask is not None else None
                out["outline"] = {"color": (ring or {}).get("color") or hex_of(oc),
                                  "w": round((wpx + 1) / max(1, lh), 4), "share": round(share, 2)}
            else:
                problems.append(f"{i + 1}번 줄: agy 는 외곽선이 있다 했으나 두께를 못 쟀습니다 — 옮기지 않습니다")
        bc = rgb_of(ln.get("box_behind_color"))
        if bc is not None:
            # 상자 색을 글자 둘레(글자 상자 밖 0.3줄 띠)의 agy 색 근처 화소로 먼저 잡고, 그 색에서 **좁은 거리(20)** 안인 화소만
            #   상자로 본다 — 상자는 평평한 한 색이고 어두운 사진·그라데이션은 결이 있다(10-08 @hottopic_lab: 넓은 거리(48)로는
            #   검은 상자와 어두운 사진 아래쪽이 한 덩어리로 재져 상자가 화면 폭 전체가 됐다).
            gx0, gy0 = max(0, rect_px[0] - int(0.3 * lh)), max(0, rect_px[1] - int(0.3 * lh))
            gx1, gy1 = min(w, rect_px[2] + int(0.3 * lh)), min(h, rect_px[3] + int(0.3 * lh))
            ringm = np.ones((gy1 - gy0, gx1 - gx0), dtype=bool)
            ringm[rect_px[1] - gy0:rect_px[3] - gy0, rect_px[0] - gx0:rect_px[2] - gx0] = False
            rp = img[gy0:gy1, gx0:gx1][ringm].astype(np.float64)
            rp = rp[_dist(rp, bc) < 48] if len(rp) else rp
            if len(rp) > 20:
                bc = np.median(rp, 0)
            got_b = _color_rect(img, rect_px, bc, pad_rows=int(0.9 * lh), also_rgb=rgb_of(out["color"]), tol=20.0,
                                min_row_frac=0.6)
            if got_b and (rect_px[1] - got_b["px"][1]) >= 0.85 * lh and (got_b["px"][3] - rect_px[3]) >= 0.85 * lh:
                problems.append(f"{i + 1}번 줄: 글자 뒤 상자가 재는 창 끝까지 이어져(사진과 색이 같다) 상자를 옮기지 않습니다")
                got_b = None
            if got_b:
                bx = got_b["px"]
                out["box"] = {"rect": _norm(bx, w, h), "color": got_b["color"], "radius": got_b.get("radius", 0),
                              # 글자 잉크 상자 대비 여백(줄 높이 배수) — 렌더가 크기를 바꿔도 같은 모양이 되게
                              "pad": [round((rect_px[0] - bx[0]) / max(1, lh), 3), round((rect_px[1] - bx[1]) / max(1, lh), 3),
                                      round((bx[2] - rect_px[2]) / max(1, lh), 3), round((bx[3] - rect_px[3]) / max(1, lh), 3)]}
        uc = rgb_of(ln.get("underline_color"))
        if uc is not None:
            under = (rect_px[0], rect_px[3], rect_px[2], min(h, rect_px[3] + max(2, lh // 3)))
            got_u = _color_rect(img, under, uc, pad_rows=max(2, lh // 3), min_row_frac=0.25)
            if got_u:
                ux = got_u["px"]
                out["underline"] = {"rect": _norm(ux, w, h), "color": got_u["color"],
                                    "dy": round((ux[1] - rect_px[3]) / max(1, lh), 3),
                                    "t": round((ux[3] - ux[1]) / max(1, lh), 3)}
        for word in ln.get("colored_words") or []:
            if not isinstance(word, dict) or not word.get("text"):
                continue
            wc = rgb_of(word.get("color"))
            if wc is None:
                continue
            sub = img[rect_px[1]:rect_px[3], rect_px[0]:rect_px[2]].astype(np.float64)
            near = _dist(sub, wc) < 60
            colr = hex_of(np.median(sub[near], 0)) if near.sum() > 20 else hex_of(wc)
            out["words"].append({"text": str(word["text"]), "color": colr})
        lines_out.append(out)
        ink_boxes.append(rect_px)

    # 바탕
    kind = bg_in.get("kind") or "photo"
    solid, solid_share = _solid_bg(img)
    bg = {"kind": kind, "color": None, "photo_rect": [0.0, 0.0, 1.0, 1.0], "edge_share": round(solid_share, 3)}
    pb = _box_px(bg_in.get("photo_box_2d"), w, h)
    pb_area = ((pb[2] - pb[0]) * (pb[3] - pb[1]) / (w * h)) if pb else 0.0
    if kind == "solid" and 0.1 <= pb_area <= 0.95:
        # agy 가 «단색» 이라 했어도 사진 상자를 화면 일부로 줬으면 단색 면 + 사진이다(@insangshorts 흰 띠 + 가운데 사진)
        kind = bg["kind"] = "photo_with_panel"
    if kind == "solid":
        bg["kind"] = "solid"
        bg["color"] = solid or hex_of(np.median(img.reshape(-1, 3), 0))
        bg["photo_rect"] = None
    elif solid and kind.endswith("_with_panel"):
        # ★단색 면 + 사진(«_with_panel») 인데 가장자리가 한 색이면 그 색이 바탕이다 — 예전에는 이것을 통째 «단색» 으로 봐서
        #   사진 칸이 사라졌다(@insangshorts agy 비교 «사진 영역이 완전히 누락» · 10-08).
        bg["color"] = solid
    panels = []
    for p in bg_in.get("panels") or []:
        if not isinstance(p, dict):
            continue
        box = _box_px(p.get("box_2d"), w, h)
        pc = rgb_of(p.get("color"))
        if not box or pc is None:
            continue
        # 면 안쪽(10% 줄인 곳)의 실제 색을 먼저 잡고, 그 색으로 가장자리를 잰다
        ix0, iy0 = box[0] + (box[2] - box[0]) // 10, box[1] + (box[3] - box[1]) // 10
        ix1, iy1 = box[2] - (box[2] - box[0]) // 10, box[3] - (box[3] - box[1]) // 10
        inner = img[iy0:iy1, ix0:ix1].reshape(-1, 3).astype(np.float64)
        if len(inner):
            near = _dist(inner, pc) < 70
            if near.sum() > 30:
                pc = np.median(inner[near], 0)
        got = _color_rect(img, box, pc, pad_rows=max(4, (box[3] - box[1]) // 4), min_row_frac=_r("panel_row_frac"),
                          tol=_r("panel_tol"))
        if got:
            panels.append({"rect": _norm(got["px"], w, h), "color": got["color"]})
        else:
            problems.append(f"단색 면 {hex_of(pc)}: 가장자리를 못 쟀습니다 — agy 상자를 씁니다")
            panels.append({"rect": _norm(box, w, h), "color": hex_of(pc)})
    if bg["kind"] != "solid":
        pr = _box_px(bg_in.get("photo_box_2d"), w, h)
        if pr:
            # 사진 영역은 단색 면 가장자리에 붙인다(면이 아래·위 띠면 그 경계가 사진의 끝이다)
            px0, py0, px1, py1 = pr
            for p in panels:
                r = p["rect"]
                if r[2] - r[0] >= 0.9 and r[1] <= 0.05:          # 위 띠
                    py0 = max(py0, int(r[3] * h))
                if r[2] - r[0] >= 0.9 and r[3] >= 0.95:          # 아래 띠
                    py1 = min(py1, int(r[1] * h))
            if py1 - py0 > 0.1 * h:
                bg["photo_rect"] = _norm((px0, py0, px1, py1), w, h)
    pr = bg.get("photo_rect")
    if pr and bg["kind"] != "solid" and not bg.get("color"):
        # 사진·그림 칸 바깥이 한 색이면 그 색이 바탕이다(@newstoon556 연회색 바탕 아래쪽 그림 — 예전에는 바깥을 검정으로 칠했다)
        area = (pr[2] - pr[0]) * (pr[3] - pr[1])
        if area < 0.95:
            out_m = np.ones((h, w), dtype=bool)
            out_m[int(pr[1] * h):int(pr[3] * h), int(pr[0] * w):int(pr[2] * w)] = False
            for (a1, b1, c1, d1) in ink_boxes:
                out_m[b1:d1, a1:c1] = False
            px_out = img[out_m].astype(np.float64)
            if len(px_out) > 100:
                med = np.median(px_out, 0)
                if float((_dist(px_out, med) < 30).mean()) >= 0.7:
                    bg["color"] = hex_of(med)
    shade = {"kind": bg_in.get("darkening") or "none", "strength": bg_in.get("darkening_strength") or "none"}
    lum = _lum_profile(img, (int(pr[0] * w), int(pr[1] * h), int(pr[2] * w), int(pr[3] * h)), ink_boxes) if pr else None

    # 정렬 — agy 가 본 정렬을 먼저 믿는다. 잰 값은 agy 답이 **명백히** 틀린 때만 이긴다
    #   (agy 정렬의 끝 흩어짐이 폭의 5% 넘고 다른 정렬은 2% 안). 두 줄 폭이 비슷하면 왼쪽·가운데·오른쪽 흩어짐이
    #   셋 다 작아서 잰 값만으로는 못 가른다(실측: 가운데 정렬 @5kmbooks 를 «오른쪽» 으로 잘못 골랐다).
    tl = [x for x in lines_out if x["role"] == "title"]
    if len(tl) < 2:
        tl = [x for x in lines_out if x["role"] in ("title", "kicker", "subtitle")]
    align = reading.get("align") if reading.get("align") in ("left", "center", "right") else "left"
    if len(tl) >= 2:
        lefts = [x["rect"][0] for x in tl]
        cents = [(x["rect"][0] + x["rect"][2]) / 2 for x in tl]
        rights = [x["rect"][2] for x in tl]
        spread = {"left": max(lefts) - min(lefts), "center": max(cents) - min(cents), "right": max(rights) - min(rights)}
        best = min(spread, key=lambda k: spread[k])
        if spread[align] > 0.05 and spread[best] < 0.02:
            problems.append(f"정렬: agy 는 {align} 라 했으나 줄 끝이 {best} 로 모입니다(흩어짐 {spread[align]:.3f} 대 "
                            f"{spread[best]:.3f}) — {best} 로 씁니다")
            align = best
    decor = []
    for d in reading.get("decorations") or []:
        if not isinstance(d, dict):
            continue
        box = _box_px(d.get("box_2d"), w, h)
        if box:
            item = {"kind": d.get("kind") or "other", "rect": _norm(box, w, h),
                    "color": d.get("color") or "", "note": str(d.get("note") or "")[:80]}
            # ★동그란 **사진 인셋**만 옮긴다 — 로고·아이콘(남의 상표)은 옮기지 않는다. 그래서 agy 가 logo_mark·icon 이라
            #   한 것은 재지 않고, 지름이 화면 짧은 변의 15% 이상·테두리가 지름의 8% 이하인 것만 인셋으로 본다
            #   (실측: 인셋 사진 지름 0.29~0.46 · 테두리 0.009~0.055 / 로고·불릿 지름 0.02~0.10).
            circ = (_circle_inset(img, box, rgb_of(d.get("color")))
                    if d.get("kind") in ("sticker", "other", "border") else None)
            if circ and ((circ["px"][2] - circ["px"][0]) < 0.15 * min(w, h) or circ["w"] > 0.08):
                circ = None
            if circ:
                px = circ["px"]
                item.update(kind="inset_circle", color=circ["color"], w=circ["w"],
                            rect=[round(px[0] / w, 4), round(px[1] / h, 4), round(px[2] / w, 4), round(px[3] / h, 4)])
            decor.append(item)
    # 사진 색 — 채도(0~1)가 아주 낮으면 흑백 처리한 사진이다(@aim___ing 실측 · agy «흑백 처리» 지적)
    sat = None
    if pr:
        x0p, y0p, x1p, y1p = int(pr[0] * w), int(pr[1] * h), int(pr[2] * w), int(pr[3] * h)
        sub = img[y0p:y1p, x0p:x1p].astype(np.float64)
        if sub.size:
            keep = np.ones(sub.shape[:2], dtype=bool)
            for (a1, b1, c1, d1) in ink_boxes:
                keep[max(0, b1 - y0p):max(0, d1 - y0p), max(0, a1 - x0p):max(0, c1 - x0p)] = False
            mx, mn = sub.max(2), sub.min(2)
            chroma = (mx - mn) / 255.0
            sat = round(float(chroma[keep].mean()), 4) if keep.any() else None
    bg["sat"] = sat
    return {"v": 1, "size": [w, h], "bg": bg, "panels": panels, "shade": shade, "lum": lum,
            "align": align, "lines": lines_out, "decor": decor, "problems": problems}


def build(image_path, question, schema, model, rules, timeout_s=300, env=None, workdir=None,
          decor_question=None, decor_schema=None):
    """레퍼런스 그림 한 장 → {reading, measured, image, textFree}. 실행기가 수강생 자기 레퍼런스에 쓴다
    (서버가 질문·스키마·모델을 준다). textFree = 글자·로고를 지운 사본(플로우 화풍 참조용) — `~/.volcano/cardnews_ref/` 아래.
    decor_question 을 주면 장식만 한 번 더 물어 합친다(`merge_decor`)."""
    import hashlib                                                  # noqa: PLC0415
    reading = read(image_path, question, schema, model, timeout_s=timeout_s, env=env)
    if decor_question and decor_schema:
        extra = read(image_path, decor_question, decor_schema, model, timeout_s=timeout_s, env=env)
        reading["decorations"] = merge_decor(reading.get("decorations"), extra.get("decorations"),
                                             float(rules["decor_iou"]))
    measured = measure(image_path, reading, rules)
    with open(image_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()[:16]
    work = workdir or os.path.join(os.path.expanduser("~"), ".volcano", "cardnews_ref")
    tf = text_free_copy(image_path, measured, os.path.join(work, f"{sha}_textfree.jpg"))
    return {"reading": reading, "measured": measured, "image": os.path.abspath(image_path), "textFree": tf}


#: 링크에서 표지를 받을 때 쓰는 브라우저 이름표 — 인스타는 크롤러 이름표에 공개 게시물 정보를 준다(10-09 실측).
_FETCH_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
_FETCH_TIMEOUT_S = 60
_FETCH_MAX_BYTES = 30 * 1024 * 1024


def _get(url):
    """주소 하나 받기(한 번 · 재시도 없음 — 실패는 사람 말로). → (바이트, content-type)."""
    import urllib.request                                                      # noqa: PLC0415
    req = urllib.request.Request(url, headers={"User-Agent": _FETCH_UA})
    with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT_S) as r:              # noqa: S310 — 회원이 준 주소
        data = r.read(_FETCH_MAX_BYTES + 1)
        if len(data) > _FETCH_MAX_BYTES:
            raise RefSpecError("링크의 파일이 너무 큽니다(30MB 초과) — 표지 그림을 저장해 referenceImage 로 주세요.")
        return data, (r.headers.get("Content-Type") or "").lower()


def _instagram_cover(url, argv, index):
    """인스타 게시물 → 표지 그림 주소. yt-dlp 게시물 정보의 thumbnails 중 **자르지 않은 원본**(stp 에 c…·크기 표시 없음)."""
    import re as _re                                                            # noqa: PLC0415
    import shutil                                                               # noqa: PLC0415
    import subprocess                                                           # noqa: PLC0415
    tpl = (argv or {}).get("ytdlp_post_json")
    if not tpl:
        raise RefSpecError("서버가 준 명령(ytdlp_post_json)이 없습니다 — 서버 응답의 argv 를 그대로 넘기세요.")
    exe = shutil.which(str(tpl[0]))
    if not exe:
        raise RefSpecError("yt-dlp 가 이 PC 에 없습니다 — python3 -m pip install yt-dlp 로 설치한 뒤 다시 하세요.")
    cmd = [exe] + [str(a).replace("{url}", url) for a in tpl[1:]]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    try:
        info = json.loads(r.stdout or "")
    except ValueError:
        raise RefSpecError("인스타 게시물 정보를 받지 못했습니다(비공개·삭제·로그인 필요일 수 있습니다) — "
                           "표지 그림을 저장해 referenceImage 로 주세요.") from None
    entries = info.get("entries") or [info]
    e = entries[max(0, min(len(entries) - 1, int(index or 0)))]
    thumbs = [t for t in (e.get("thumbnails") or []) if t.get("url")]
    if not thumbs:
        raise RefSpecError("게시물에서 그림을 찾지 못했습니다 — 표지 그림을 저장해 referenceImage 로 주세요.")

    def rank(t):
        stp = (_re.search(r"stp=([^&]+)", t["url"]) or [None, ""])[1]
        cropped = bool(_re.search(r"(^|_)c\d", stp))
        sized = bool(_re.search(r"_[ps]\d+x\d+", stp))
        return (cropped, sized, -((t.get("width") or 0) * (t.get("height") or 0)))
    return min(thumbs, key=rank)["url"]


def fetch_url(url, argv=None, index=0, out_dir=None):
    """따라 할 카드뉴스 링크 → 이 PC 에 표지 그림 파일 경로. 인스타 게시물(yt-dlp 게시물 정보) · 그림 주소 · 웹 문서(og:image)."""
    import hashlib                                                              # noqa: PLC0415
    import io                                                                   # noqa: PLC0415
    import re as _re                                                            # noqa: PLC0415
    from urllib.parse import urlparse                                           # noqa: PLC0415
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("instagram.com"):
        img_url = _instagram_cover(url, argv, index)
        data, ctype = _get(img_url)
    else:
        data, ctype = _get(url)
        if not ctype.startswith("image/"):
            html = data.decode("utf-8", "replace")
            m = _re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html) or \
                _re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', html)
            if not m:
                raise RefSpecError("링크에서 표지 그림을 찾지 못했습니다 — 그림 주소를 주거나 그림을 저장해 referenceImage 로 주세요.")
            data, ctype = _get(m.group(1).replace("&amp;", "&"))
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:                                                      # noqa: BLE001 — 그림이 아니면 사람 말로
        raise RefSpecError(f"링크에서 받은 것이 그림이 아닙니다({ctype or '종류 모름'}) — 표지 그림을 저장해 referenceImage 로 주세요.") from e
    d = out_dir or os.path.join(os.path.expanduser("~"), ".volcano", "cardnews_ref")
    os.makedirs(d, exist_ok=True)
    out = os.path.join(d, "url_" + hashlib.sha256(f"{url}#{index}".encode("utf-8")).hexdigest()[:16] + ".jpg")
    im.convert("RGB").save(out, quality=95)
    return out


def build_from_url(url, question, schema, model, rules, argv=None, index=0, timeout_s=300, env=None, workdir=None,
                   decor_question=None, decor_schema=None):
    """링크 → 표지 받기 → `build` 그대로(10-09). 받은 그림 경로는 결과의 image."""
    path = fetch_url(url, argv=argv, index=index, out_dir=workdir)
    return build(path, question, schema, model, rules, timeout_s=timeout_s, env=env, workdir=workdir,
                 decor_question=decor_question, decor_schema=decor_schema)


def text_free_copy(image_path, measured, out_path):
    """글자·로고를 지운 레퍼런스 사본 — 그림 엔진(플로우)에 «화풍 참조»로 넘길 때 쓴다.

    ★레퍼런스 글자·계정명·로고를 그대로 넘기면 그림 모델이 그 글자를 베껴 굽는다(우리 카드 글자는 렌더가 그린다).
      잰 글자 상자(줄 높이의 0.25배 여유)를 상자 바깥 둘레의 중앙값 색으로 메운다 — 흐림이 아니라 지움이다.
    """
    im = Image.open(image_path).convert("RGB")
    a = np.asarray(im).copy()
    h, w = a.shape[:2]
    rects = [ln["rect"] for ln in measured.get("lines") or []]
    rects += [ln["box"]["rect"] for ln in measured.get("lines") or [] if ln.get("box")]
    rects += [d["rect"] for d in measured.get("decor") or [] if d.get("kind") in ("logo_mark", "sticker", "icon")]
    for r in rects:
        x0, y0, x1, y1 = int(r[0] * w), int(r[1] * h), int(r[2] * w), int(r[3] * h)
        m = int(0.25 * max(1, y1 - y0))
        x0, y0, x1, y1 = max(0, x0 - m), max(0, y0 - m), min(w, x1 + m), min(h, y1 + m)
        ring = np.concatenate([a[max(0, y0 - 3):y0, x0:x1].reshape(-1, 3), a[y1:y1 + 3, x0:x1].reshape(-1, 3),
                               a[y0:y1, max(0, x0 - 3):x0].reshape(-1, 3), a[y0:y1, x1:x1 + 3].reshape(-1, 3)])
        fill = np.median(ring, 0) if len(ring) else np.array([0, 0, 0])
        a[y0:y1, x0:x1] = fill.astype(np.uint8)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    Image.fromarray(a).save(out_path, quality=92)
    return out_path
