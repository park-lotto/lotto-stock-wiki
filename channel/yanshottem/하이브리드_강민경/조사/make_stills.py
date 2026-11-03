# -*- coding: utf-8 -*-
"""포트레 공식몰 상품 상세 이미지(워터 핏 스킨 틴트 50ml, product_no=319) → 천천히 다가가는 영상 재료(엔진 코드 아님 · ffmpeg 만).
    PYTHONUTF8=1 py make_stills.py
입력: C:/숏템_칼카피/yanshottem/하이브리드_강민경/src/portre/img_*.jpg|png (2026-10-17 portre.co.kr 상세페이지에서 받음)
출력: C:/숏템_칼카피/yanshottem/하이브리드_강민경/src/stills/<이름>_916.mp4 (1080×1920, 잇썸 전체화면)
                                                        <이름>_t11.mp4 (1080×1408, 재미썸 t11 창) · <이름>_sq.mp4 (1080×1080, 얜샷템 창)
"""
import subprocess
from pathlib import Path

Z = Path("C:/숏템_칼카피/yanshottem/하이브리드_강민경/src/portre")
O = Path("C:/숏템_칼카피/yanshottem/하이브리드_강민경/src/stills")
FPS, SEC = 30, 6
D1 = "img_6b567733_848BE185B5E1848CE185B5-01.jpg"   # 1000×8148 상세 1(대표·강민경 모델·제형)
D2 = "img_a55bc9a7_WATER-02.jpg"                      # 1000×7710 상세 2(컬러·비포애프터·67%)
D3 = "img_c5859dc6_848BE185B5E1848CE185B5-03.jpg"     # 1000×5260 상세 3(사용법·패키지·라인업)
# 이름: (파일, 원본에서 먼저 자를 [x,y,w,h], 방식 fit|fill, 배경색, 확대 끝, 다가갈 곳(ax,ay))
STILLS = {
    "hero_spf":  (D1, [0, 0, 1000, 1900], "fit", "0xE9EEF3", 1.10, (0.5, 0.35)),   # 물 속 검은 튜브 + 'SPF 50+ | PA++++ · 말갛게 톤업되는 선크림'
    "hero_tube": (D1, [0, 0, 1000, 1340], "fill", None, 1.12, (0.5, 0.45)),        # 물 속 검은 튜브(글 없이)
    "model":     (D1, [230, 2080, 620, 880], "fill", None, 1.10, (0.5, 0.4)),       # 강민경이 이 튜브를 들고 있는 공식 모델컷
    "drip":      (D1, [0, 4290, 1000, 950], "fill", None, 1.12, (0.6, 0.4)),       # 튜브 위로 흘러내리는 제형
    "colors":    (D2, [0, 640, 1000, 760], "fit", "0xFFFFFF", 1.08, (0.5, 0.5)),   # IVORY(웜)·ROSE(쿨) 발색 + 설명
    "beforeafter": (D2, [0, 1920, 1000, 820], "fit", "0xFFFFFF", 1.08, (0.5, 0.5)),  # 공식 비포/애프터
    "pack3":     (D3, [0, 1760, 1000, 1180], "fill", None, 1.10, (0.5, 0.5)),      # 검은 튜브 3개 패키지
}
SIZES = {"916": (1080, 1920), "t11": (1080, 1408), "sq": (1080, 1080)}


def make(name, size_key):
    src, (cx, cy, cw, ch), mode, bg, zmax, (ax, ay) = STILLS[name]
    W, H = SIZES[size_key]
    W2, H2 = W * 2, H * 2
    pre = f"crop={cw}:{ch}:{cx}:{cy},"
    if mode == "fit":
        prep = pre + f"scale={W2}:{H2}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W2}:{H2}:(ow-iw)/2:(oh-ih)/2:color={bg}"
    else:
        prep = pre + (f"scale={W2}:{H2}:force_original_aspect_ratio=increase:flags=lanczos,"
                      f"crop={W2}:{H2}:(iw-{W2})/2:(ih-{H2})/2")
    n = FPS * SEC
    zoom = f"1+({zmax}-1)*on/{n}"
    vf = (f"{prep},setsar=1,zoompan=z='{zoom}':x='(iw-iw/zoom)*{ax}':y='(ih-ih/zoom)*{ay}':d=1:s={W}x{H}:fps={FPS},"
          f"format=yuv420p")
    out = O / f"{name}_{size_key}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(Z / src), "-vf", vf, "-frames:v", str(n),
                    "-c:v", "libx264", "-crf", "16", "-preset", "medium", str(out)], check=True)
    return out


if __name__ == "__main__":
    O.mkdir(parents=True, exist_ok=True)
    for nm in STILLS:
        for k in SIZES:
            print(make(nm, k))
