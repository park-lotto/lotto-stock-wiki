# -*- coding: utf-8 -*-
"""소재 화면 실측 — 컷마다 ①얼굴 보임 ②얼굴 중심이 슬롯 가운데서 얼마나 벗어나나 ③슬롯 안 박힌 글자 ④주인공 동일성.
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


def embed(bgr, face):
    H, W = bgr.shape[:2]
    x, y, w, h = int(face["x"] * W), int(face["y"] * H), int(face["w"] * W), int(face["h"] * H)
    box = np.array([[x, y, w, h, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, face["conf"]]], dtype=np.float32)
    aligned = rec.alignCrop(bgr, box[0])
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
        rows.append({"i": i + 1, "face": bool(big), "face_h": round(big["h"], 3) if big else None,
                     "cx_off": round((big["x"] + big["w"] / 2) - 0.5, 3) if big else None,
                     "text_boxes": len(tb), "text_area": round(text_area, 4),
                     "emb": embed(bgr, big) if big else None})
    # 주인공 무리: 탐욕 군집(코사인)
    embs = [(r["i"], r["emb"]) for r in rows if r["emb"] is not None]
    clusters = []
    for i, e in embs:
        for cl in clusters:
            if rec.match(cl["c"], e, cv2.FaceRecognizerSF_FR_COSINE) >= COS_T:
                cl["m"].append(i); cl["c"] = (cl["c"] * (len(cl["m"]) - 1) + e) / len(cl["m"]); break
        else:
            clusters.append({"c": e.copy(), "m": [i]})
    main = max(clusters, key=lambda cl: len(cl["m"]))["m"] if clusters else []
    for r in rows:
        r["is_main"] = (r["i"] in main) if r["face"] else None; r.pop("emb", None)
    n = len(rows); face_n = sum(r["face"] for r in rows)
    out[f[:11]] = {"cuts": n, "face_pct": round(100 * face_n / n), "main_pct": round(100 * len(main) / n),
                   "other_face_cuts": [r["i"] for r in rows if r["face"] and not r["is_main"]],
                   "no_face_cuts": [r["i"] for r in rows if not r["face"]],
                   "cx_off_med": round(st.median([abs(r["cx_off"]) for r in rows if r["cx_off"] is not None]), 3) if face_n else None,
                   "face_h_med": round(st.median([r["face_h"] for r in rows if r["face_h"]]), 3) if face_n else None,
                   "text_cuts": sum(1 for r in rows if r["text_boxes"]), "text_cut_pct": round(100 * sum(1 for r in rows if r["text_boxes"]) / n),
                   "text_cut_ids": [r["i"] for r in rows if r["text_boxes"]], "clusters": len(clusters), "rows": rows}
    o = out[f[:11]]
    print(f"{f[:11]} 컷 {n} | 얼굴 {o['face_pct']}% 주인공 {o['main_pct']}% 다른얼굴 {o['other_face_cuts']} 얼굴없음 {len(o['no_face_cuts'])} | "
          f"중심편차 {o['cx_off_med']} 얼굴높이 {o['face_h_med']} | 글자 컷 {o['text_cut_pct']}% {o['text_cut_ids']}")
json.dump(out, open("faces_text.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
if out:
    v = list(out.values())
    print(f"\n얼굴 보임 중앙 {st.median([x['face_pct'] for x in v])}% · 주인공 중앙 {st.median([x['main_pct'] for x in v])}% · "
          f"중심편차 중앙 {st.median([x['cx_off_med'] for x in v if x['cx_off_med'] is not None])} · 글자 컷 중앙 {st.median([x['text_cut_pct'] for x in v])}%")
