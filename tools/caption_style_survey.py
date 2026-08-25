"""자막 스타일 실측 — 유튜브·인스타 상위 채널의 '자막 완성형'을 읽어온다.

★왜 만들었나 (2026-08-25 사장님 "자막 템플릿도 완성형으로 ... 20개씩 조사해서 가져와봐")
  기존 실측 스키마(썰쇼핑_영상디자인_실측.json)는 **띠가 어떻게 생겼냐**를 묻는 표라
  자막은 곁다리로 4개(cap_y/color/outline/box)만 물었다. 그래서:
    - 자막 **폰트·크기**를 아예 안 물어봤다 → 20종이 전부 우리 기본 글꼴로 나갔다
    - **강조색**(노란 부제 같은 것)이 없다 → 시각 효과가 제일 큰 축이 통째로 빠졌다
    - **박스 색**을 안 물어 코드가 "#000000"으로 지어냈다 → 검은 박스 위 검은 글자 9종
  → 자막만 정면으로 보는 표를 따로 만든다.

★'무슨 폰트냐'고 묻지 마라 (2026-08-20에 배운 것, 그대로 재사용)
  모델에게 글꼴 이름을 물으면 우리한테 없는 폰트를 지어낸다. 우리 글꼴 견본 시트를
  영상과 **같이** 넣고 **번호로 고르게** 한다. 비교는 잘한다.

쓰는 법:
    py tools/caption_style_survey.py sheet          # 견본 시트 PNG 만들기
    py tools/caption_style_survey.py schema         # 제미니에 넣을 스키마·프롬프트 출력
"""
import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parents[1]
FONT_DIR = BASE / "shopping_shorts" / "static" / "fonts"
OUT_DIR = BASE / "docs" / "reference"
SHEET = OUT_DIR / "글꼴견본_22종.png"

# ── 자막 전용 실측 표 ────────────────────────────────────────────────
# ★"모르면 비운다"를 허용한다. 지어낸 값이 들어오면 살림킹왕짱 색 뒤집힘 같은 사고가 난다.
CAPTION_SCHEMA = {
    "cap_exists":     "자막이 있나 (true/false)",
    "cap_font_no":    "견본 시트에서 가장 비슷한 글꼴 번호 (1~22). 모르면 null",
    "cap_font_why":   "왜 그 번호인지 한 줄 (획 두께·네모꼴 등 근거)",
    "cap_font_conf":  "확신도: 높음/보통/낮음",
    "cap_size_pct":   "글자 높이 ÷ 화면 높이 × 100 (예: 3.5)",
    "cap_y":          "자막 중심의 세로 위치 % (위=0, 아래=100)",
    "cap_align":      "가로 정렬: 가운데/왼쪽/오른쪽",
    "cap_lines":      "보통 몇 줄로 나오나 (1 또는 2)",
    "cap_color":      "글자색 #RRGGBB",
    "cap_outline":    "외곽선이 있나 (true/false)",
    "cap_outline_color": "외곽선 색 #RRGGBB (없으면 null)",
    "cap_outline_pct":   "외곽선 두께 ÷ 글자 높이 × 100 (예: 6)",
    "cap_shadow":     "그림자가 있나 (true/false)",
    "cap_box":        "글자 뒤 박스가 있나 (true/false)",
    # ★박스 색을 **반드시** 묻는다 — 이걸 안 물어서 코드가 검정으로 지어냈다(2026-08-25 결함)
    "cap_box_color":  "박스 색 #RRGGBB (없으면 null)",
    "cap_box_shape":  "박스 모양: 사각/둥근모서리/알약/없음",
    "cap_box_opacity": "박스 불투명도 % (100=꽉 참)",
    # ★강조 — 시각 효과가 제일 큰 축인데 지금까지 통째로 없었다
    "cap_emph":       "일부 단어를 다르게 강조하나 (true/false)",
    "cap_emph_kind":  "강조 방식: 색만/형광펜/밑줄/더크게/테두리 — 없으면 null",
    "cap_emph_color": "강조 글자색 #RRGGBB (없으면 null)",
    "cap_emph_bg":    "형광펜일 때 그 색 #RRGGBB (없으면 null)",
    "notes":          "이 채널 자막 인상을 2문장으로",
}

PROMPT = """이 쇼츠 영상의 **하단 나레이션 자막**(말하는 내용을 받아쓴 자막)만 본다.
제목·헤드카피·상단 띠 글자는 보지 마라.

같이 넣은 이미지는 우리가 가진 글꼴 22종 견본 시트다.
글꼴 **이름을 맞히려 하지 마라** — 견본과 비교해 **번호**로 골라라.
비슷한 게 없으면 cap_font_no를 null로 두고 cap_font_conf를 "낮음"으로 해라.

모르는 값은 지어내지 말고 null로 둬라. 아래 JSON만 출력한다(설명 금지).

%s"""


def make_sheet():
    """글꼴 22종 견본 시트 PNG. 번호를 크게 박아 모델이 번호로 답하게 한다."""
    from PIL import Image, ImageDraw, ImageFont
    fonts = sorted(p.name for p in FONT_DIR.glob("*.[ot]tf"))
    if not fonts:
        raise SystemExit(f"글꼴이 없다: {FONT_DIR}")
    # ★공백을 넣지 않는다 — 공백 글리프가 없는 글꼴(빙그레 등)이 □(두부)로 그려져
    #   모델이 그 견본을 "깨진 글꼴"로 오해한다(2026-08-25 실제 시트에서 확인).
    SAMPLE = "이거진짜사야돼요"
    row_h, W = 132, 1280
    im = Image.new("RGB", (W, row_h * len(fonts) + 60), (255, 255, 255))
    d = ImageDraw.Draw(im)
    try:
        lab = ImageFont.truetype(str(FONT_DIR / "Pretendard-Bold.otf"), 34)
    except Exception:
        lab = ImageFont.load_default()
    d.text((30, 16), "글꼴 견본 — 가장 비슷한 번호를 고르세요", font=lab, fill=(20, 20, 20))
    for i, name in enumerate(fonts):
        y = 60 + i * row_h
        d.rectangle([0, y, W, y + row_h - 2], fill=(250, 250, 250) if i % 2 else (255, 255, 255))
        d.text((28, y + row_h // 2), f"{i + 1:>2}", font=lab, fill=(200, 60, 60), anchor="lm")
        try:
            f = ImageFont.truetype(str(FONT_DIR / name), 62)
        except Exception:
            continue
        d.text((110, y + row_h // 2), SAMPLE, font=f, fill=(15, 15, 15), anchor="lm")
        d.text((W - 30, y + row_h // 2), name, font=lab, fill=(150, 150, 150), anchor="rm")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    im.save(SHEET)
    return SHEET, fonts


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "schema"
    if cmd == "sheet":
        p, fonts = make_sheet()
        print(f"견본 시트: {p}")
        for i, n in enumerate(fonts, 1):
            print(f"  {i:>2} {n}")
    elif cmd == "schema":
        print(PROMPT % json.dumps(CAPTION_SCHEMA, ensure_ascii=False, indent=2))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
