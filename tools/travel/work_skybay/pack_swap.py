"""모션 프리셋 템플릿(원본 코드 그대로)에 스카이베이 사진만 갈아 끼우기 — 팩 품질이 호텔 사진에서도 나오는지 보는 시험(사장님 10-22).

    py tools/travel/work_skybay/pack_swap.py      → ~/숏템자료/모션그래픽엔진/work/2026-10-22_숙소_<팩>/ 의 사진·글자 교체

사진 칸은 원본과 같은 크기로 가운데 맞춰 잘라 덮는다(템플릿 코드는 건드리지 않는다). 글자는 화면에 보이는 문구만 바꾼다.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = Path.home() / "숏템자료/모션그래픽엔진/work"


def O(no):
    return HERE / "photos" / ("%02d.jpg" % (no - 1))


cm = json.loads((HERE / "ep1/work/comments.json").read_text(encoding="utf-8"))
GUEST = [ROOT / x["photo"] for v in cm.values() for x in v if x.get("photo")]


def put(src, dst):
    """dst 와 같은 크기로 src 를 가운데 맞춰 잘라 덮어쓴다(형식 유지)."""
    size = Image.open(dst).size
    im = ImageOps.fit(Image.open(src).convert("RGB"), size, Image.LANCZOS)
    if dst.suffix.lower() == ".png":
        im.save(dst)
    else:
        im.save(dst, quality=90)


def text(path, pairs):
    s = path.read_text(encoding="utf-8")
    for a, b in pairs:
        if a not in s:
            print("  글자 없음(건너뜀):", a)
        s = s.replace(a, b)
    path.write_text(s, encoding="utf-8")


def main():
    # 사진 터널(가로 1920×1080 · 세로 사진 8장)
    d = WORK / "2026-10-22_숙소_launch_tunnel"
    for k, no in enumerate([5, 6, 11, 12, 1, 15, 7, 3], 1):
        put(O(no), d / ("p%d.jpg" % k))
    text(d / "index.html", [(">타깃<", ">오션뷰<"), (">상품<", ">인피니티풀<"), (">말투<", ">일출<"), (">트렌드<", ">호수뷰<"),
                            ("25,000+", "7,908"), ("인기 숏폼 분석", "실제 투숙객 후기"), ("상품 링크 하나", "스카이베이 경포"),
                            ("// 01 AI 원고", "// 01 20층 인피니티풀"), ("// 02 슬라이드", "// 02 누워서 일출"),
                            ("// 03 자막형", "// 03 앞 바다 뒤 호수"), (">트렌드 <", ">호수뷰 <"), (">매일, <", ">강릉, <"), ("상품 링크 붙여넣기", "강릉 오션뷰 호텔"), (">올린다.<", ">여기서 자요.<"),
                            ("영상 한 편", "후기가 고른 호텔"), (">숏템메이커<", ">스카이베이 경포<"), ("shortem maker", "SKYBAY GYEONGPO")])
    # 사진 구 다이브(978×720 · 타일 12장)
    d = WORK / "2026-10-22_숙소_eye_dive_photo_sphere"
    pool = [O(n) for n in (5, 6, 11, 12, 1, 7)] + GUEST
    for k in range(12):
        put(pool[k % len(pool)], d / ("t%d.jpg" % k))
    text(d / "index.html", [("I See Through the Wild", "후기 7,908건이 고른 호텔"), ("I See Through", "후기 7,908건"),
                            ("The Archive", "인피니티풀"), ("Field Notes", "누워서 일출"), ("Studio", "앞 바다 뒤 호수"), ("Contact", "스카이베이 경포")])
    # 액자 속 무한 줌(1280×720 · 풍경 4장, 액자·소품은 원본)
    d = WORK / "2026-10-22_숙소_infinite_zoom_collage"
    for k, no in enumerate([11, 5, 6, 12]):
        put(O(no), d / "img" / ("L%d.png" % k))
    print("교체 끝")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
