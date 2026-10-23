"""컷 안 흔들림 재기 — 두 가지를 잰다.

    py tools/travel/hotel_copy/shake.py <영상.mp4> <시작초> <끝초>

① 전체 이동(작게 줄여 광류) — 카메라가 한 방향으로 매끄럽게 가나(방향 뒤집힘·들쭉날쭉 = 손떨림)
② 잔떨림(crawl, 원래 크기) — 앞 프레임을 광류로 다음 프레임에 맞춘 뒤 남는 차이. 작은 사진을 크게 키워
   매 프레임 다시 그리면 물결·나뭇잎 같은 잔무늬가 지글거린다(사진 자체는 매끈하게 가는데 '흔들려' 보인다).
2026-10-23 사장님 "11초에 계곡물 사진 흔들리고"(숨은계곡 1판)로 만든 도구.
"""
import sys

import cv2
import numpy as np


def frames(path, a, b, size=None):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(a * fps))
    out = []
    for _ in range(int((b - a) * fps)):
        ok, f = cap.read()
        if not ok:
            break
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        out.append(cv2.resize(g, size) if size else g)
    return out, fps


def crawl(path, a, b, step=3):
    """원래 크기에서 앞 프레임을 다음 프레임으로 광류 정렬 → 남은 차이(밝기 0~255 평균). 화면 아래쪽 자막 없는 띠만 본다."""
    fr, _ = frames(path, a, b)
    errs = []
    for f0, f1 in list(zip(fr, fr[1:]))[::step]:
        h = f0.shape[0]
        y0, y1 = int(h * 0.55), int(h * 0.95)                 # 자막(위쪽)과 워터마크를 피한 아래 띠
        p0, p1 = f0[y0:y1], f1[y0:y1]
        flow = cv2.calcOpticalFlowFarneback(p1, p0, None, 0.5, 4, 21, 3, 5, 1.2, 0)
        yy, xx = np.mgrid[0:p0.shape[0], 0:p0.shape[1]].astype(np.float32)
        warped = cv2.remap(p0, xx + flow[..., 0], yy + flow[..., 1], cv2.INTER_LINEAR)
        errs.append(float(np.abs(warped.astype(np.float32) - p1.astype(np.float32))[8:-8, 8:-8].mean()))
    return round(float(np.median(errs)), 2) if errs else None


def measure(path, a, b):
    fr, fps = frames(path, a, b, (270, 480))
    mags, flips, prev = [], 0, None
    for f0, f1 in zip(fr, fr[1:]):
        mean = cv2.calcOpticalFlowFarneback(f0, f1, None, 0.5, 3, 15, 3, 5, 1.2, 0).reshape(-1, 2).mean(0)
        mags.append(float(np.linalg.norm(mean)))
        if prev is not None and np.dot(prev, mean) < 0:
            flips += 1
        prev = mean
    return {"frames": len(fr), "move_px": round(float(np.mean(mags)), 2), "move_jitter": round(float(np.std(np.diff(mags))), 2),
            "dir_flips": flips, "crawl": crawl(path, a, b)}


if __name__ == "__main__":
    print(measure(sys.argv[1], float(sys.argv[2]), float(sys.argv[3])))
