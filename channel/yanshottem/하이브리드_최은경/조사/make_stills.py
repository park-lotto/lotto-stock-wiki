# -*- coding: utf-8 -*-
"""자라 공식 상품 사진(1554/810/700) → 천천히 다가가는 8초 영상 재료(엔진 코드 아님 · ffmpeg 만).
    PYTHONUTF8=1 py make_stills.py
출력: C:/숏템_칼카피/yanshottem/하이브리드_최은경/src/stills/<이름>_916.mp4 (1080×1920, 잇썸 전체화면)
                                                         <이름>_t11.mp4 (1080×1408, 재미썸 t11 창)
"""
import subprocess
from pathlib import Path

Z = Path("C:/숏템_칼카피/yanshottem/하이브리드_최은경/src/zara")
O = Path("C:/숏템_칼카피/yanshottem/하이브리드_최은경/src/stills")
FPS, SEC = 30, 8
# 이름: (파일, 방식 fit|fill, 배경색, 채울 때 가운데(cx,cy), 확대 끝, 다가갈 곳(ax,ay))
STILLS = {
    "a1_worn":  ("11554810700-a1.jpg", "fill", None, (0.5, 1.0), 1.08, (0.5, 1.0)),
    "p_model":  ("11554810700-p.jpg", "fill", None, (0.5, 0.5), 1.30, (0.5, 0.97)),
    "e1_side":  ("11554810700-e1.jpg", "fit", "0xF0F0F0", None, 1.10, (0.5, 0.5)),
    "e2_pair":  ("11554810700-e2.jpg", "fit", "0xF0F0F0", None, 1.12, (0.5, 0.5)),
    "e3_toe":   ("11554810700-e3.jpg", "fit", "0xF0F0F0", None, 1.15, (0.5, 0.6)),
    "e4_back":  ("11554810700-e4.jpg", "fit", "0xF0F0F0", None, 1.10, (0.5, 0.5)),
    "f1_flat":  ("11554810700-f1.jpg", "fit", "0xFFFFFF", None, 1.10, (0.5, 0.5)),
    "page_soldout": ("zara_kr_mobile_품절임박.png", "fill", None, (0.0, 1.0), 1.45, (0.0, 0.93)),
}
SIZES = {"916": (1080, 1920), "t11": (1080, 1408)}


def make(name, size_key):
    src, mode, bg, cxy, zmax, (ax, ay) = STILLS[name]
    W, H = SIZES[size_key]
    W2, H2 = W * 2, H * 2
    if mode == "fit":
        prep = f"scale={W2}:{H2}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W2}:{H2}:(ow-iw)/2:(oh-ih)/2:color={bg}"
    else:
        cx, cy = cxy
        prep = (f"scale={W2}:{H2}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={W2}:{H2}:(iw-{W2})*{cx}:(ih-{H2})*{cy}")
    n = FPS * SEC
    zoom = f"1+({zmax}-1)*on/{n}"
    vf = (f"{prep},setsar=1,zoompan=z='{zoom}':x='(iw-iw/zoom)*{ax}':y='(ih-ih/zoom)*{ay}':d=1:s={W}x{H}:fps={FPS},"
          f"format=yuv420p")
    out = O / f"{name}_{size_key}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(Z / src), "-vf", vf, "-frames:v", str(n),
                    "-c:v", "libx264", "-crf", "14", "-preset", "medium", str(out)], check=True)
    return out


if __name__ == "__main__":
    O.mkdir(parents=True, exist_ok=True)
    for nm in STILLS:
        for k in SIZES:
            print(make(nm, k))
