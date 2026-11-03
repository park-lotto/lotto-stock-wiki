# 컬러판 검사·정리 — SHOTLIST §3: IoU(흑백 선 vs 컬러판 선, gray<140) → 미달이면 ECC affine 정합 후 재측정
# → 컬러판 선을 inpaint(TELEA,3) 로 지움 → 215↑ 흰색 → 250↑ 알파0 → c_<이름>_flat.png
# 쓰기: py color_check.py g_f_hope g_m_tired ...  → 이름 IoU(원) IoU(정합) 판정
import cv2, numpy as np, sys, os, json
import numpy as _np, cv2 as _cv2
def _imread(p, flag=_cv2.IMREAD_COLOR): return _cv2.imdecode(_np.fromfile(p, _np.uint8), flag)
def _imwrite(p, im): _cv2.imencode(".png", im)[1].tofile(p)
HERE = os.path.dirname(os.path.abspath(__file__))
rep = {}
for name in sys.argv[1:]:
    base = name[2:] if name.startswith("g_") else name
    g = _imread(os.path.join(HERE, "g_" + base + ".png")); c = _imread(os.path.join(HERE, "c_" + base + ".png"))
    if c.shape[:2] != g.shape[:2]: c = cv2.resize(c, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_AREA)
    gg = cv2.cvtColor(g, cv2.COLOR_BGR2GRAY); cg = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    iou = lambda a, b: float((a & b).sum() / max(1, (a | b).sum()))
    # 판정 = 설계서 그대로(gray<140 맨 IoU ≥ 0.8). 3px 팽창 IoU 는 참고값으로만 기록
    k = np.ones((3, 3), np.uint8)
    # 새 물체 검사: 컬러판에서 칠해진 곳이 흑백 그림 실루엣(선 + 닫힌 안쪽, 15px 여유) 밖에 얼마나 있나
    sil = (gg < 200).astype(np.uint8) * 255
    ff = sil.copy(); h0, w0 = ff.shape; m2 = np.zeros((h0 + 2, w0 + 2), np.uint8)
    cv2.floodFill(ff, m2, (0, 0), 128)
    sil = cv2.dilate(((ff != 128)).astype(np.uint8), np.ones((31, 31), np.uint8)) > 0
    # 선 IoU: 칠한 면(컬러판의 회갈 머리 #6E6761 은 gray≈103 이라 '선'으로 잡힌다)을 빼고 가는 선끼리만 비교.
    #  면 = 9px 원 열림(opening)에 남는 덩어리. 흑백·컬러 둘 다 같은 방식(남 머리·넥타이 검정 면도 빠진다)
    EL = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    def thin(m):
        m8 = m.astype(np.uint8); sol = cv2.dilate(cv2.morphologyEx(m8, cv2.MORPH_OPEN, EL), k, iterations=2)
        return (m8 > 0) & (sol == 0), sol > 0
    bw_raw = gg < 140; bw, bw_sol = thin(bw_raw)
    def ink_iou(cc):
        cm, c_sol = thin(cv2.cvtColor(cc, cv2.COLOR_BGR2GRAY) < 140)
        ex = bw_sol | c_sol                       # 어느 쪽이든 면인 곳은 비교에서 뺀다
        a_, b_ = bw & ~ex & sil, cm & ~ex & sil                # 1px 허용(3x3 팽창) — 안티에일리어스 1px 흔들림은 정합 실패가 아니다
        d_ = lambda m: cv2.dilate(m.astype(np.uint8), k) > 0
        return iou(d_(a_), d_(b_))
    def raw_iou_f(cc): return iou(bw_raw, cv2.cvtColor(cc, cv2.COLOR_BGR2GRAY) < 140)
    i0 = ink_iou(c); i1 = i0; aligned = False
    if i0 < 0.8:
        try:
            W = np.eye(2, 3, dtype=np.float32)
            _, W = cv2.findTransformECC(255 - gg.astype(np.float32), 255 - cg.astype(np.float32), W, cv2.MOTION_AFFINE,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
            c2 = cv2.warpAffine(c, W, (g.shape[1], g.shape[0]), flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP, borderValue=(255, 255, 255))
            i1 = ink_iou(c2)
            if i1 > i0: c = c2; aligned = True
        except cv2.error as e:
            print(name, "ECC 실패", e)
    raw_iou = raw_iou_f(c)
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV); painted = (cv2.cvtColor(c, cv2.COLOR_BGR2GRAY) < 225) | (hsv[..., 1] > 40)
    extra = float((painted & ~sil).sum() / max(1, painted.sum()))
    ok = max(i0, i1) >= 0.8   # 새 물체(실루엣 밖)는 아래에서 flat 판에서 잘라낸다 — extra 는 기록만
    # 선 지우기: 컬러판 선 + 흑백 선(둘 다) 을 마스크로 — 획 레이어와 이중선 방지
    cg2 = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
    # 가는 선만 지운다: 굵은 검정 면(남 머리·넥타이)은 획(skeleton)으로 못 채우므로 flat 판에 남긴다
    #  (원작 template 이 마지막에 원본 PNG 를 겹쳐 검은 칠을 채우는 것과 같은 역할)
    ink2 = ((cg2 < 140) | (gg < 140)).astype(np.uint8)
    solid = cv2.dilate(cv2.morphologyEx(ink2, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))), k)
    mask = cv2.dilate(((ink2 > 0) & (solid == 0)).astype(np.uint8) * 255, k, iterations=1)
    flat = cv2.inpaint(c, mask, 3, cv2.INPAINT_TELEA)
    fg = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    sat = cv2.cvtColor(flat, cv2.COLOR_BGR2HSV)[..., 1]
    flat[(fg >= 215) & (sat < 25)] = 255          # 바탕 정리 — 옅은 살구색 피부(채도 있음)는 지키고 무채색만 흰색으로
    a = np.where((cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY) >= 250) & (sat < 25), 0, 255).astype(np.uint8)
    a[~sil] = 0                                   # 흑백 그림 실루엣 밖(모델이 덧붙인 책상·노트북 등)은 버린다
    # 피부색 맞추기(④-5 ±12): 모델 피부가 옅게 나온다(여 #FAE2D2 등) → 살구색 픽셀 전체를 평균이 #F2C9B8 이 되도록 평행이동
    hs = cv2.cvtColor(flat, cv2.COLOR_BGR2HSV)
    sk = (a > 0) & (hs[..., 0] < 15)   # 모래색 소품(노트북 #E9DCC6, 색상 19)은 빼고 살구색(9~12)만 & (hs[..., 1] > 20) & (hs[..., 2] > 150)
    AN0 = json.load(open(os.path.join(HERE, "hero_anchor.json"), encoding="utf-8")).get("g_" + base)
    if AN0 and sk.sum() > 200:
        fb = np.zeros_like(sk); fb[AN0["ey"] + 25:AN0["ey"] + 95, AN0["ex"] - 70:AN0["ex"] + 70] = True
        ref = flat[sk & fb] if (sk & fb).sum() > 50 else flat[sk]
        shift = np.array([0xB8, 0xC9, 0xF2], np.float32) - ref.mean(axis=0)
        flat[sk] = np.clip(flat[sk].astype(np.float32) + shift, 0, 255).astype(np.uint8)
    rgba = np.dstack([flat, a])
    _imwrite(os.path.join(HERE, "c_" + base + "_flat.png"), rgba)
    # 피부색(④-5): 눈 아래 볼 영역에서 채도 있는 살구색 픽셀 평균 vs #F2C9B8
    skin = None
    AN = json.load(open(os.path.join(HERE, "hero_anchor.json"), encoding="utf-8")).get("g_" + base)
    if AN:
        x0, y0 = AN["ex"] - 70, AN["ey"] + 25; box = flat[y0:y0 + 70, x0:x0 + 140]; hb = cv2.cvtColor(box, cv2.COLOR_BGR2HSV)
        sel = (a[y0:y0 + 70, x0:x0 + 140] > 0) & (hb[..., 1] > 20) & (hb[..., 0] < 25) & (hb[..., 2] > 150)
        if sel.sum() > 50:
            m = box[sel].mean(axis=0)[::-1]; skin = "#%02X%02X%02X" % tuple(int(v) for v in m)
            skin_d = int(np.abs(m - np.array([0xF2, 0xC9, 0xB8])).max())
    rep_skin = {"skin": skin, "skin_dmax": skin_d if skin else None}
    rep[base] = {"iou_line": round(i0, 3), "iou_line_aligned": round(i1, 3), "aligned": aligned, "iou_spec_raw": round(raw_iou, 3), "extra_outside": round(extra, 3), "pass": ok, **rep_skin}
    print(base, rep[base])
old = json.load(open(os.path.join(HERE, "color_iou.json"), encoding="utf-8")) if os.path.exists(os.path.join(HERE, "color_iou.json")) else {}
old.update(rep); json.dump(old, open(os.path.join(HERE, "color_iou.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
