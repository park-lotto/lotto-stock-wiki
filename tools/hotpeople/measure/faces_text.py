# -*- coding: utf-8 -*-
r"""소재 화면 실측 — 컷마다 ①얼굴 보임 ②얼굴 중심이 슬롯 가운데서 얼마나 벗어나나 ③슬롯 안 박힌 글자 ④주인공 동일성.
표본 폴더(cuts.json 있는 곳)에서: <프로젝트>\.venv\Scripts\python.exe ..\measure\faces_text.py [모델폴더] → faces_text.json + 콘솔

자(볼케이노 framevision 팩과 같은 것): YuNet 얼굴(score 0.7, 두 배율) · PP-OCRv5 server det(글자 상자, 인식 없음) · SFace 임베딩(cv2.FaceRecognizerSF).
주인공 = 편 안의 얼굴 임베딩을 코사인 0.363(SFace 기본 문턱)로 묶었을 때 **가장 큰 무리**. 참고 사진 없이 "이름으로 검색한 영상에서 가장 자주 나오는 얼굴"을 주인공으로 본다.
★한계: 얼굴이 작거나 옆·뒤모습이면 검출이 안 된다 → "얼굴 없음"과 "주인공 아님"을 갈라서 센다.
"""
import subprocess, json, sys, os, glob, statistics as st
import numpy as np, cv2

MODELS = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "models")
YUNET = os.path.join(MODELS, "face_detection_yunet_2023mar.onnx")
SFACE = os.path.join(MODELS, "face_recognition_sface_2021dec.onnx")
OCRDET = os.path.join(MODELS, "ppocrv5_server_det.onnx")
sys.path.insert(0, r"C:\Users\CH\Desktop\볼케이노작업\카피\packs\framevision")
os.environ["MOON_YUNET"] = YUNET
import facelib_cv                      # noqa: E402
import ocrdet                          # noqa: E402

SLOT = (0, 483, 1080, 790)             # ★뜨거운사람들 전용(다른 채널은 layout.json에서) — 슬롯 crop
COS_T = 0.363                          # SFace 코사인 동일 문턱(OpenCV 기본)
cuts = json.load(open("cuts.json", encoding="utf-8"))
det = ocrdet.Detector(OCRDET)
rec = cv2.FaceRecognizerSF.create(SFACE, "")


def slot_frame(f, t, path):
    x, y, w, h = SLOT
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", f, "-frames:v", "1", "-vf", f"crop={w}:{h}:{x}:{y}", path], check=False)
    return cv2.imread(path)


_yn = {}


def embed(bgr, face):
    """SFace 임베딩. ★alignCrop은 YuNet 원시 행(랜드마크 5점 포함)을 요구한다 — 랜드마크를 0으로 채우면
    모든 얼굴이 같은 정렬 그림이 되어 cos=1.0(2026-09-28 실측, 자가 아무것도 안 잼). 그래서 YuNet을 직접 돌려 그 행을 쓴다."""
    H, W = bgr.shape[:2]
    key = (W, H)
    if key not in _yn:
        _yn[key] = cv2.FaceDetectorYN.create(YUNET, "", (W, H), 0.5, 0.3, 5000)
    _, res = _yn[key].detect(bgr)
    if res is None or len(res) == 0:
        return None
    fx, fy = face["x"] * W + face["w"] * W / 2, face["y"] * H + face["h"] * H / 2
    row = min(res, key=lambda r: (r[0] + r[2] / 2 - fx) ** 2 + (r[1] + r[3] / 2 - fy) ** 2)   # facelib이 고른 얼굴과 가장 가까운 원시 행
    aligned = rec.alignCrop(bgr, row)
    return rec.feature(aligned).flatten()


out = {}
for f in sorted(glob.glob("*.mp4")):
    if f not in cuts: continue
    c = cuts[f]; ts = [0] + c["sub_times"]; ends = c["sub_times"] + [c["dur"]]
    os.makedirs("ft_tmp", exist_ok=True)
    rows = []
    for i in range(len(ts)):
        p = f"ft_tmp/{f[:11]}_{i:02d}.png"
        bgr = slot_frame(f, (ts[i] + ends[i]) / 2, p)
        if bgr is None: continue
        fs = facelib_cv.faces(p, score=0.7) or []
        big = max(fs, key=lambda q: q["w"] * q["h"]) if fs else None
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        tb = det.boxes(rgb)
        H, W = bgr.shape[:2]
        text_area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in tb) / (W * H)
        # 자막처럼 생긴 글자 = **같은 줄의 낱말 상자를 합친 뒤**(PP-OCR은 "완전히 / 망가져 / 버렸죠"를 세 상자로 준다, v3 컷1 실측)
        #   아래 40% · 가로 중앙(±20%) · 합친 폭 ≥ 슬롯 35% · 높이 3~13% · 낱말 상자 2개 이상(코트 바닥 'TOTAL' 한 덩어리는 제외, v3 컷10).
        #   점수판·스폰서 보드(원본 80% 컷에 글자)와 가르는 자다(2026-09-28)
        def merge_rows(boxes):
            rows_ = []
            for b in sorted(boxes, key=lambda b: (b[1], b[0])):
                for r_ in rows_:
                    gap = max(b[0] - r_["x1"], r_["x0"] - b[2]) / W        # 양쪽 방향 간격(정렬이 y 우선이라 왼쪽 상자가 나중에 올 수 있다)
                    if min(r_["y1"], b[3]) - max(r_["y0"], b[1]) > 0.5 * min(r_["y1"] - r_["y0"], b[3] - b[1]) and gap < 0.06:
                        r_["x0"] = min(r_["x0"], b[0]); r_["x1"] = max(r_["x1"], b[2])      # ★x0도 갱신 — 빠뜨려서 폭이 0.17로 나왔다(2026-09-28)
                        r_["y0"] = min(r_["y0"], b[1]); r_["y1"] = max(r_["y1"], b[3]); r_["n"] += 1; break
                else:
                    rows_.append({"x0": b[0], "x1": b[2], "y0": b[1], "y1": b[3], "n": 1})
            return rows_
        def sub_like(r_):
            bw, bh = (r_["x1"] - r_["x0"]) / W, (r_["y1"] - r_["y0"]) / H
            cx, cy = ((r_["x0"] + r_["x1"]) / 2) / W, ((r_["y0"] + r_["y1"]) / 2) / H
            return cy >= 0.6 and abs(cx - 0.5) <= 0.2 and bw >= 0.35 and 0.03 <= bh <= 0.13 and r_["n"] >= 2
        sl = [r_ for r_ in merge_rows(tb) if sub_like(r_)]
        rows.append({"i": i + 1, "face": bool(big), "face_h": round(big["h"], 3) if big else None,
                     "cx_off": round((big["x"] + big["w"] / 2) - 0.5, 3) if big else None,
                     "text_boxes": len(tb), "text_area": round(text_area, 4), "sub_like": len(sl),
                     "boxes": [[round(b[0] / W, 3), round(b[1] / H, 3), round(b[2] / W, 3), round(b[3] / H, 3)] for b in tb],
                     "emb": embed(bgr, big) if big else None})
    # 주인공 = 다른 얼굴들과 가장 많이 "같다"고 판정되는 얼굴(짝별 코사인, 중심 평균 없음).
    # ★첫 판(중심을 평균으로 흘려보내는 탐욕 군집)은 v3 컷23(다른 사람 메달)을 주인공으로 묶었다(2026-09-28) — 자가 아는 오류를 못 잡으면 자가 아니다.
    embs = [(r["i"], r["emb"]) for r in rows if r["emb"] is not None]
    same = {i: {j for j, e2 in embs if j != i and rec.match(e, e2, cv2.FaceRecognizerSF_FR_COSINE) >= COS_T} for i, e in embs}
    anchor = max(same, key=lambda i: len(same[i])) if same else None
    main = sorted({anchor} | same[anchor]) if anchor is not None else []
    clusters = [{"m": main}] + [{"m": [i]} for i in same if i not in main]
    emb_of = dict(embs)
    # 판정 가능 = 얼굴 높이 ≥ 슬롯 20% (v3 실측: 0.2 미만 얼굴은 주인공도 cos −0.1~0.1 — 옆·뒤·작은 얼굴은 못 가린다)
    JUDGE_H, OTHER_T = 0.20, 0.20
    for r in rows:
        r["cos_anchor"] = round(float(rec.match(emb_of[anchor], r["emb"], cv2.FaceRecognizerSF_FR_COSINE)), 3) if (r["emb"] is not None and anchor is not None) else None
        if not r["face"]: r["who"] = "얼굴없음"
        elif r["face_h"] < JUDGE_H: r["who"] = "판정불가(작음)"
        elif r["cos_anchor"] >= COS_T: r["who"] = "주인공"
        elif r["cos_anchor"] < OTHER_T: r["who"] = "다른사람"
        else: r["who"] = "애매"
        r["is_main"] = r["who"] == "주인공"
        r.pop("emb", None)
    main = [r["i"] for r in rows if r["is_main"]]
    n = len(rows); face_n = sum(r["face"] for r in rows)
    out[f[:11]] = {"cuts": n, "face_pct": round(100 * face_n / n), "main_pct": round(100 * len(main) / n),
                   "other_face_cuts": [r["i"] for r in rows if r.get("who") == "다른사람"],
                   "unsure_cuts": [r["i"] for r in rows if r.get("who") == "애매"],
                   "small_face_cuts": [r["i"] for r in rows if r.get("who") == "판정불가(작음)"],
                   "no_face_cuts": [r["i"] for r in rows if not r["face"]],
                   "cx_off_med": round(st.median([abs(r["cx_off"]) for r in rows if r["cx_off"] is not None]), 3) if face_n else None,
                   "face_h_med": round(st.median([r["face_h"] for r in rows if r["face_h"]]), 3) if face_n else None,
                   "text_cuts": sum(1 for r in rows if r["text_boxes"]), "text_cut_pct": round(100 * sum(1 for r in rows if r["text_boxes"]) / n),
                   "text_cut_ids": [r["i"] for r in rows if r["text_boxes"]], "clusters": len(clusters),
                   "sub_like_cuts": [r["i"] for r in rows if r["sub_like"]], "sub_like_pct": round(100 * sum(1 for r in rows if r["sub_like"]) / n),
                   "anchor": anchor, "rows": rows}
    o = out[f[:11]]
    print(f"{f[:11]} 컷 {n} | 얼굴 {o['face_pct']}% 주인공 {o['main_pct']}% 다른얼굴 {o['other_face_cuts']} 얼굴없음 {len(o['no_face_cuts'])} | "
          f"중심편차 {o['cx_off_med']} 얼굴높이 {o['face_h_med']} | 자막꼴 글자 컷 {o['sub_like_pct']}% {o['sub_like_cuts']} (아무 글자 {o['text_cut_pct']}%)")
    print("   cos↔주인공:", [(r["i"], r["cos_anchor"]) for r in rows if r["cos_anchor"] is not None])
json.dump(out, open("faces_text.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if out:
    v = list(out.values())
    print(f"\n얼굴 보임 중앙 {st.median([x['face_pct'] for x in v])}% · 주인공 중앙 {st.median([x['main_pct'] for x in v])}% · "
          f"중심편차 중앙 {st.median([x['cx_off_med'] for x in v if x['cx_off_med'] is not None])} · "
          f"자막꼴 글자 컷 중앙 {st.median([x['sub_like_pct'] for x in v])}% (아무 글자 {st.median([x['text_cut_pct'] for x in v])}%)")
