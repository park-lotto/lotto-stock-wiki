"""오프닝 재료 손질 — ①선화를 채색 그림에 맞춰 정렬 ②종이 바탕 빼서 인물만(알파) ③선화를 펜 획으로(그리는 순서까지).

    py tools/travel/work_skybay/opening/prep.py      → img/couple_line_reg.png · *_cut.png · strokes.js

획 순서 = 원본(15 agents 2D 애니) 실측: 인물은 위에서 아래로 부위별(머리 윤곽→얼굴→머리카락→몸통→팔→다리→신발),
배경은 긴 직선(원근선)부터 쏘고 나머지 잔선. 획 따기 = ink_explainer/tools/trace.py 방식(뼈대 → 끝점부터 걷기 → 다듬기).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from skimage.morphology import skeletonize

D = Path.home() / "숏템자료/모션그래픽엔진/work/2026-10-22_숙소_오프닝"
IMG = D / "img"
PAPER = np.array([227, 235, 239], np.float32)   # #efebe3 (BGR)


def imread(p, flag=cv2.IMREAD_COLOR):
    """cv2.imread 는 윈도에서 한글 경로를 못 연다 — 바이트로 읽어 푼다."""
    return cv2.imdecode(np.fromfile(str(p), np.uint8), flag)


def imwrite(p, im):
    cv2.imencode(Path(p).suffix, im)[1].tofile(str(p))


def register(line, color):
    """선화를 채색 그림 위치에 맞춘다(외곽선 ECC 아핀). 어긋나면 물감 번질 때 선이 두 겹으로 보인다."""
    a = cv2.Canny(cv2.cvtColor(color, cv2.COLOR_BGR2GRAY), 60, 160).astype(np.float32)
    b = cv2.Canny(cv2.cvtColor(line, cv2.COLOR_BGR2GRAY), 60, 160).astype(np.float32)
    a, b = cv2.GaussianBlur(a, (0, 0), 3), cv2.GaussianBlur(b, (0, 0), 3)
    warp = np.eye(2, 3, dtype=np.float32)
    cc, warp = cv2.findTransformECC(a, b, warp, cv2.MOTION_AFFINE,
                                    (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 300, 1e-6), None, 5)
    out = cv2.warpAffine(line, warp, (color.shape[1], color.shape[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(227, 235, 239))
    print("정렬 상관 %.3f · 이동 %.1f,%.1f px · 배율 %.3f" % (cc, warp[0, 2], warp[1, 2], (warp[0, 0] + warp[1, 1]) / 2))
    return out


def cutout(src, dst):
    """종이 바탕 빼기 = 테두리에서 종이를 채워 들어간다(외곽 잉크선을 넘지 못함) → 선 안쪽은 흰 원피스·피부도 그대로 남는다.
    실측 10-22: 색 하나로 빼기 = 흰 옷·피부에 구멍 / AI 인물 매팅(remove-background) = 그림 인물을 못 알아봄. 그래서 선으로 가른다."""
    im = imread(src)
    h, w = im.shape[:2]
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    ink = (g < 185).astype(np.uint8)
    ink = cv2.dilate(ink, np.ones((3, 3), np.uint8))          # 선 사이 1~2px 틈을 막는다(틈으로 새면 몸 안까지 지워진다)
    free = (1 - ink).astype(np.uint8)
    n, lab = cv2.connectedComponents(free, 4)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    bg = np.isin(lab, list(border))
    a = (~bg).astype(np.float32)
    a = cv2.erode(a, np.ones((2, 2), np.uint8))               # 넓힌 선만큼 되돌림
    n2, lab2, st, _ = cv2.connectedComponentsWithStats((a > 0.5).astype(np.uint8), 8)
    keep = np.zeros(n2, bool)
    keep[1:] = st[1:, cv2.CC_STAT_AREA] > 1500                 # 종이 얼룩·잔선 버림
    a = a * keep[lab2]
    a = cv2.GaussianBlur(a, (0, 0), 0.7)
    imwrite(dst, np.dstack([im, (a * 255).astype(np.uint8)]))


def strokes(gray, thr, min_len, mode):
    ink = gray < thr
    sk = skeletonize(ink)
    ys, xs = np.nonzero(sk)
    pts = set(zip(xs.tolist(), ys.tolist()))
    N = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]
    left = set(pts)

    def walk(p):
        line = [p]
        left.discard(p)
        while True:
            nx = [(p[0] + dx, p[1] + dy) for dx, dy in N if (p[0] + dx, p[1] + dy) in left]
            if not nx:
                break
            p = nx[0]
            left.discard(p)
            line.append(p)
        return line
    deg = lambda p: sum((p[0] + dx, p[1] + dy) in pts for dx, dy in N)  # noqa: E731
    raw = []
    for e in sorted((p for p in pts if deg(p) == 1), key=lambda p: (p[1], p[0])):
        if e in left:
            raw.append(walk(e))
    while left:
        raw.append(walk(min(left, key=lambda p: (p[1], p[0]))))
    res = []
    for s in raw:
        if len(s) < min_len:
            continue
        a = cv2.approxPolyDP(np.array(s, np.int32).reshape(-1, 1, 2), 0.9, False).reshape(-1, 2).tolist()
        L = sum(np.hypot(a[k + 1][0] - a[k][0], a[k + 1][1] - a[k][1]) for k in range(len(a) - 1))
        res.append({"p": a, "L": float(L)})

    def chain(pool, cur):
        out = []
        while pool:
            i = min(range(len(pool)), key=lambda k: min((pool[k]["p"][0][0] - cur[0]) ** 2 + (pool[k]["p"][0][1] - cur[1]) ** 2,
                                                       (pool[k]["p"][-1][0] - cur[0]) ** 2 + (pool[k]["p"][-1][1] - cur[1]) ** 2))
            s = pool.pop(i)
            if (s["p"][-1][0] - cur[0]) ** 2 + (s["p"][-1][1] - cur[1]) ** 2 < (s["p"][0][0] - cur[0]) ** 2 + (s["p"][0][1] - cur[1]) ** 2:
                s["p"] = s["p"][::-1]
            out.append(s)
            cur = s["p"][-1]
        return out
    if mode == "figure":       # 위에서 아래로 띠(높이 7%)마다, 띠 안은 가까운 획끼리 이어서
        H = gray.shape[0]
        bands = {}
        for s in res:
            bands.setdefault(int(min(y for _, y in s["p"]) / (H * 0.07)), []).append(s)
        out, cur = [], (gray.shape[1] // 2, 0)
        for k in sorted(bands):
            part = chain(bands[k], cur)
            out += part
            cur = part[-1]["p"][-1]
        return out
    long_ = sorted([s for s in res if s["L"] > 140], key=lambda s: -s["L"])   # 긴 원근선 먼저 '쏘듯이'
    rest = chain([s for s in res if s["L"] <= 140], (gray.shape[1] // 2, gray.shape[0] // 2))
    return long_ + rest


def main():
    color = imread((IMG / "couple_color.png"))
    line = register(imread((IMG / "couple_line.png")), color)
    imwrite((IMG / "couple_line_reg.png"), line)
    for n in ("couple_color", "couple_side", "couple_backA", "couple_backB"):
        cutout(IMG / (n + ".png"), IMG / (n + "_cut.png"))
    fig = strokes(cv2.cvtColor(line, cv2.COLOR_BGR2GRAY), 150, 8, "figure")
    bg = strokes(cv2.cvtColor(imread((IMG / "bg_line.png")), cv2.COLOR_BGR2GRAY), 150, 10, "bg")
    js = {"fig": [{"d": "M" + " L".join("%d %d" % (x, y) for x, y in s["p"]), "L": round(s["L"], 1)} for s in fig],
          "bg": [{"d": "M" + " L".join("%d %d" % (x, y) for x, y in s["p"]), "L": round(s["L"], 1)} for s in bg]}
    # 원근선 '쏘기' — 원본은 지평선→소실점에서 퍼지는 직선을 펜이 한 번에 긋는다. 배경 선화에서 긴 직선만 따로 뽑는다
    g = cv2.cvtColor(imread((IMG / "bg_line.png")), cv2.COLOR_BGR2GRAY)
    hl = cv2.HoughLinesP((g < 150).astype(np.uint8) * 255, 1, np.pi / 360, 80, minLineLength=150, maxLineGap=6)
    shots = []
    for x1, y1, x2, y2 in (hl.reshape(-1, 4).tolist() if hl is not None else []):
        if all(np.hypot(x1 - a_[0], y1 - a_[1]) + np.hypot(x2 - a_[2], y2 - a_[3]) > 40 for a_ in shots):
            shots.append([x1, y1, x2, y2])
    shots.sort(key=lambda l: -np.hypot(l[2] - l[0], l[3] - l[1]))
    js["shots"] = shots[:24]
    # 물감 번짐 자리 — 인물 칸(알파)을 위에서 아래로 10군데
    al = imread((IMG / "couple_color_cut.png"), cv2.IMREAD_UNCHANGED)[:, :, 3]
    ys, xs = np.nonzero(al > 128)
    pts = np.float32(np.column_stack([xs, ys]))[::25]
    _, _, cen = cv2.kmeans(pts, 10, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5), 3, cv2.KMEANS_PP_CENTERS)
    js["wash"] = sorted([[int(x), int(y)] for x, y in cen], key=lambda c: c[1])
    js["figbox"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    (D / "strokes.js").write_text("window.STROKES=" + json.dumps(js) + ";", encoding="utf-8")
    print("원근선 %d개 · 물감 자리 %s · 인물 칸 %s" % (len(js["shots"]), js["wash"], js["figbox"]))
    print("인물 획 %d개 길이 %.0f · 배경 획 %d개(긴 선 %d) 길이 %.0f"
          % (len(fig), sum(s["L"] for s in fig), len(bg), sum(1 for s in bg if s["L"] > 140), sum(s["L"] for s in bg)))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
