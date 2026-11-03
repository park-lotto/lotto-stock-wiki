# -*- coding: utf-8 -*-
"""고렌샤크(GallonShark) 미끄럼방지 요가 신발 상품 사진 → 천천히 다가가는 8초 영상 재료(엔진 코드 아님 · ffmpeg 만).
정본 = 하이브리드_최은경/조사/make_stills.py (사진 목록만 바꿈).
    PYTHONUTF8=1 py make_stills.py
입력: C:/숏템_칼카피/yanshottem/하이브리드_이영자/src/raw/
  g1~g5.jpg  = 쿠팡 상품 9623667803 '고렌샤크 미끄럼방지 요가 신발 … Gallonshark' 상품 사진 5장(1000², 2026-10-17 조회)
  t8_*.png   = 같은 제품 판매 사진(검정·아이보리·그레이 한 켤레를 손에 든 사진) — '똑똑한 구매리스트' T8Maxl8-uP0 1080p 화면에서 사진 칸만 잘라 냄
  lj_black.png = 같은 제품 검정 한 켤레 사진('모두의 리뷰' lJbKVjunSr8 40.8초 4위 칸 — 원 영상이 좌우 뒤집혀 있어 hflip 으로 되돌림)
  ali_pink.jpg = 알리익스프레스 '갤런샤크 베어풋 삭스 슈즈 … 논슬립 니트 신발'(1005012379840358) 대표 사진 — GallonShark 로고 + 핑크 한 켤레(같은 모델)
  cp_page_r.png = 쿠팡 상품 페이지 화면 오른쪽(상품명 '고렌샤크 미끄럼방지 요가 신발 … Gallonshark'·가격·장바구니/바로구매) — cp_page.png 의 오른쪽 칸(x 530~1170 — 상품 사진 g1 은 빼서 같은 사진 되풀이 없음)
출력: src/stills/<이름>_916.mp4(1080×1920 잇썸) · _t11.mp4(1080×1408 재미썸) · _sq.mp4(1080×1080 얜샷템 창)
"""
import subprocess
from pathlib import Path

Z = Path("C:/숏템_칼카피/yanshottem/하이브리드_이영자/src/raw")
O = Path("C:/숏템_칼카피/yanshottem/하이브리드_이영자/src/stills")
FPS, SEC = 30, 8
# 이름: (파일, 방식 fit|fill, 배경색, 채울 때 가운데(cx,cy), 확대 끝, 다가갈 곳(ax,ay))
STILLS = {
    "g1_logo":   ("g1.jpg", "fit", "0xFFFFFF", None, 1.15, (0.3, 0.3)),
    "g2_sole":   ("g2.jpg", "fill", None, (0.5, 0.5), 1.12, (0.6, 0.6)),
    "g3_fold":   ("g3.jpg", "fill", None, (0.45, 0.5), 1.12, (0.5, 0.6)),
    "g4_gym":    ("g4.jpg", "fill", None, (0.4, 0.5), 1.10, (0.4, 0.8)),
    "g5_black":  ("g5.jpg", "fill", None, (0.35, 0.5), 1.12, (0.3, 0.6)),
    "t8_black":  ("t8_24.png", "fill", None, (0.35, 0.5), 1.12, (0.3, 0.7)),
    "t8_ivory":  ("t8_14.5.png", "fill", None, (0.55, 0.5), 1.12, (0.6, 0.7)),
    "t8_grey":   ("t8_2.5.png", "fill", None, (0.7, 0.5), 1.12, (0.7, 0.7)),
    "lj_black":  ("lj_black.png", "fit", "0xFFFFFF", None, 1.12, (0.5, 0.5)),
    "ali_pink":  ("ali_pink.jpg", "fit", "0xFFFFFF", None, 1.12, (0.3, 0.3)),
    "page":      ("cp_page_r.png", "fit", "0xFFFFFF", None, 1.15, (0.3, 0.2)),
}
SIZES = {"916": (1080, 1920), "t11": (1080, 1408), "sq": (1080, 1080)}


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
    import sys
    O.mkdir(parents=True, exist_ok=True)
    for nm in (sys.argv[1:] or STILLS):
        for k in SIZES:
            print(make(nm, k))
