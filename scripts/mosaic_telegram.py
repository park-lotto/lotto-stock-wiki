"""
mosaic_telegram.py — 텔레그램 스크린샷 모자이크 처리

처리 내용:
  - 왼쪽 채널 목록: 채널명 + 프로필 사진 모자이크
  - 오른쪽 콘텐츠 영역: 구독자 수 모자이크
  - 하이라이트된 채널(주부영)은 보이게 유지

사용법:
    python scripts/mosaic_telegram.py --input 파일경로.png
    python scripts/mosaic_telegram.py --input 파일경로.png --strength 12
"""

import argparse
from pathlib import Path
from PIL import Image, ImageFilter, ImageDraw

# ── 모자이크 함수 ────────────────────────────────────────────────
def mosaic(img: Image.Image, region: tuple, strength: int = 10) -> Image.Image:
    """region = (x1, y1, x2, y2) 영역을 픽셀화"""
    x1, y1, x2, y2 = region
    crop = img.crop((x1, y1, x2, y2))
    w, h = crop.size
    # 축소 → 확대로 픽셀화
    small_w = max(1, w // strength)
    small_h = max(1, h // strength)
    small = crop.resize((small_w, small_h), Image.NEAREST)
    pixelated = small.resize((w, h), Image.NEAREST)
    img.paste(pixelated, (x1, y1))
    return img

def blur_region(img: Image.Image, region: tuple, radius: int = 15) -> Image.Image:
    """region 영역을 가우시안 블러"""
    x1, y1, x2, y2 = region
    crop = img.crop((x1, y1, x2, y2))
    blurred = crop.filter(ImageFilter.GaussianBlur(radius))
    img.paste(blurred, (x1, y1))
    return img


def process(input_path: str, strength: int = 12, output_path: str = None):
    img = Image.open(input_path).convert("RGB")
    W, H = img.size
    print(f"이미지 크기: {W} x {H}")

    # ── 비율 기반 영역 계산 ──────────────────────────────────────
    # 왼쪽 패널 너비 추정 (전체의 약 34%)
    LEFT_PANEL_W = int(W * 0.34)

    # 상단 검색바 높이 (약 6%)
    TOP_BAR_H = int(H * 0.06)

    # 각 채널 행 높이 추정 (약 7.5%)
    ROW_H = int(H * 0.075)

    # ── 모자이크 영역 정의 ───────────────────────────────────────
    regions = []

    # 1. 왼쪽 상단 아이콘 영역 (상단 탭들)
    regions.append({
        "name": "왼쪽 상단 아이콘",
        "box": (0, 0, int(W * 0.06), H),
        "type": "blur",
        "radius": 20,
    })

    # 2. 채널 목록 프로필 + 이름 (채널명 영역)
    #    왼쪽 패널 전체에서 아이콘 제외
    #    하이라이트 채널(약 35% 높이 위치) 제외하고 나머지 모자이크
    highlight_y_start = int(H * 0.315)  # 하이라이트 채널 시작
    highlight_y_end   = int(H * 0.395)  # 하이라이트 채널 끝

    # 하이라이트 위쪽 채널들
    regions.append({
        "name": "채널 목록 상단",
        "box": (int(W * 0.055), TOP_BAR_H, LEFT_PANEL_W, highlight_y_start),
        "type": "mosaic",
        "strength": strength,
    })

    # 하이라이트 아래쪽 채널들
    regions.append({
        "name": "채널 목록 하단",
        "box": (int(W * 0.055), highlight_y_end, LEFT_PANEL_W, H),
        "type": "mosaic",
        "strength": strength,
    })

    # 3. 오른쪽 패널 구독자 수
    regions.append({
        "name": "구독자 수",
        "box": (int(W * 0.36), int(H * 0.055), int(W * 0.60), int(H * 0.085)),
        "type": "mosaic",
        "strength": strength,
    })

    # 4. 오른쪽 패널 상단 채널명 일부 (필요 시)
    # regions.append({
    #     "name": "채널명 텍스트",
    #     "box": (int(W * 0.36), int(H * 0.02), int(W * 0.85), int(H * 0.055)),
    #     "type": "blur",
    #     "radius": 8,
    # })

    # ── 처리 실행 ────────────────────────────────────────────────
    for r in regions:
        print(f"  처리: {r['name']} {r['box']}")
        if r["type"] == "mosaic":
            img = mosaic(img, r["box"], r.get("strength", strength))
        elif r["type"] == "blur":
            img = blur_region(img, r["box"], r.get("radius", 15))

    # ── 저장 ────────────────────────────────────────────────────
    if output_path is None:
        p = Path(input_path)
        output_path = str(p.parent / f"{p.stem}_mosaic{p.suffix}")

    img.save(output_path, quality=95)
    print(f"\n저장 완료: {output_path}")

    # 결과 바로 열기
    import subprocess, platform
    if platform.system() == "Windows":
        subprocess.Popen(["start", output_path], shell=True)

    return output_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input",    required=True, help="입력 이미지 경로")
    ap.add_argument("--strength", type=int, default=12, help="모자이크 강도 (클수록 거침)")
    ap.add_argument("--output",   default=None, help="출력 경로 (기본: 원본명_mosaic)")
    args = ap.parse_args()

    process(args.input, args.strength, args.output)


if __name__ == "__main__":
    main()
