"""꾸미기 '내용물 있는 틀' — 1080x1920 RGBA 오버레이를 **그리는 유일한 곳**.

★0순위-B: 미리보기와 최종 렌더가 **이 함수 하나**를 쓴다.
  화면에서 CSS로 흉내내고 렌더에서 따로 그리면, 언젠가 반드시 어긋나서
  "미리보기랑 다르게 나왔다"가 된다. 그래서 미리보기도 여기가 만든 PNG를 받아 얹는다.

기존 12종(빈 색띠, deco_templates.py)은 그대로 살아 있다 — 이건 그 위에 얹는 새 갈래다.
저장된 작업이 옛 template를 가리키면 옛 경로가 계속 돈다(id 재사용·삭제 금지).
"""
import hashlib
import json
import pathlib
import re

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
_FONT_DIR = pathlib.Path(__file__).resolve().parent / "static" / "fonts"

# 프리셋 = 사장님이 가져온 '실제로 잘되는' 유튜브 포맷.
# ★색·기본 높이를 여기 한 곳에서만 정한다. 화면 드롭다운도 이 표를 읽는다.
#
# ══════════════════════════════════════════════════════════════════════════
# 2026-08-20 — 썰쇼핑 상위 20채널 실측 벤치마킹 (사장님: "유튜브 썰체널들
# 엄청많이 모여있으니 20개체널 디자인을 그대로 가져와서 / 똑같이 하면안되고
# 살짝씩 비틀어서 / 해드카피도 이 템플릿들과 맞춰서 한 세트로")
#
# 출처: 서버 reference.db의 썰쇼핑 태깅 채널 107개 → 채널별 최다조회 쇼츠를
#       YouTube API로 뽑아 조회수 상위 20개의 실제 썸네일을 내려받아 픽셀 실측.
#       실측 원장: docs/reference/썰쇼핑_상위20_썸네일실측.json
#
# ★"그대로"가 아니라 "살짝 비틀어서"(사장님 지시):
#   - 구조(띠+아이콘+2줄 헤드라인+흰 자막바)는 원본 그대로 — 이게 잘 되는 이유다
#   - 색조는 원본에서 의도적으로 밀었다(원본 헥사를 그대로 쓰지 않는다)
#   - 채널명은 **비워둔 채** 시작한다. 실제 채널명을 기본값으로 박으면 남의
#     상표를 그대로 내보내게 된다 — 사장님이 직접 적어야 한다.
#
# ★headcopy = 이 틀에 글자가 '딱 들어가는' 한 세트(폰트·크기·색·배치).
#   틀마다 띠 높이가 다르므로 헤드카피 y가 같으면 어떤 틀에선 띠에 먹힌다.
#   그래서 틀과 글자를 **한 벌로** 정의한다 — 고르면 둘 다 같이 적용된다.
# ══════════════════════════════════════════════════════════════════════════
#
# bar_h/white_h는 1920 기준 px(실측 %를 환산). ref=벤치마킹한 원본 채널.
def _hc(font, size, color, color2, y, outline_w=12, outline_color="#000000",
        box=False, box_color="#FFFFFF"):
    """헤드카피 한 세트. color=1줄, color2=2줄(형광 강조).

    ★outline_color·box는 2026-08-20 실측에서 추가됐다 — 어떤 채널은 검은 외곽선이
      아니라 **흰 외곽선**을 쓰고(어두운 영상 위), 어떤 채널은 글자 뒤에 흰 박스를 깐다.
      이걸 못 담으면 '비슷한데 질감이 다른' 결과가 나온다.
    """
    return {"font": font, "size": size, "color": color, "color2": color2,
            "y": y, "weight": 900, "outline": True, "outline_color": outline_color,
            "outline_w": min(12, outline_w),   # ★화면 슬라이더 상한이 12 — 넘기면 잘린다
            "box": bool(box), "box_color": box_color, "box_pad": 16, "box_opacity": 100}


PRESETS = {
    # ══════════════════════════════════════════════════════════════════
    # 2026-08-20 · 사장님 재지시: "실제 영상들 안봤지? 제미니한테 시키면안되나?
    #   잘되는 체널들꺼를 90프로이상 실제 똑같은 질감 느낌나게"
    #
    # 처음엔 **썸네일(정지 이미지)만** 보고 손으로 색을 찍었다. 그래서 틀렸다 —
    # 살림킹왕짱을 "분홍 바탕+흰 글씨"로 넣었는데 실제 영상은 **흰 바탕+분홍 글씨**
    # 였다(색이 통째로 뒤집힘). 지금 값은 전부 **실제 영상 59편을 제미니에 올려**
    # 읽은 것이다(20채널 × 3편, 3편의 합의값: 숫자=중앙값·색=최빈계열).
    #
    # ★이 블록은 손으로 고치지 마라 — tools/build_sul_presets.py가 찍어낸다.
    #   원장: docs/reference/썰쇼핑_영상디자인_실측.json
    # ══════════════════════════════════════════════════════════════════
    "sul_hwaryong": {
        "name": "활용정점.", "ref": "활용정점.(영상 3편 실측)",
        "bar": "#E11F26", "on_bar": "#000000", "bar_h": 269,
        "left_icon": "none", "right_icon": "search",
        "center_kind": "검색창",
        "sub_bg": "#FFFFFF", "sub_text": "#757575", "sub_h": 86,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("TmonMonsori.ttf", 90, "#000000", "#00D3FA", 44, 7, "#FFFFFF", True, "#FFFFFF"),
        # 상단의 강렬한 빨간색 검색창 디자인을 활용하여 브랜드의 시그니처 스타일을 보여줍니다. 헤드라인에 두꺼운 검은색 외곽선과 네온 
    },
    "sul_salrim": {
        "name": "살림킹왕짱", "ref": "살림킹왕짱(영상 3편 실측)",
        "bar": "#FFFFFF", "on_bar": "#111111", "bar_h": 144,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#777777", "sub_h": 67,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("TmonMonsori.ttf", 86, "#000000", "#000000", 37, 5, "#FFFFFF", True, "#FFFFFF"),
        # 웹사이트 헤더를 모티브로 한 상단바와 타이틀 영역을 상단에 고정 배치하여 정보 전달력을 극대화한 디자인입니다. 군더더기 없는 
    },
    "sul_sulchip": {
        "name": "썰칩12", "ref": "썰칩12(영상 3편 실측)",
        "bar": "#F1F1EE", "on_bar": "#111111", "bar_h": 163,
        "left_icon": "none", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 115,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("SpoqaHanSansNeo-Bold.otf", 90, "#FFFFFF", "#26D953", 38, 7, "#000000", False, "#FFFFFF"),
        # 상단의 회색 검색창 레이아웃과 고정된 흰색 타이틀 바가 깔끔하게 매칭되어 정돈된 분위기를 줍니다. 화면 중앙에 둥근 흰색 박스
    },
    "sul_bangkkul": {
        "name": "방구석꿀템", "ref": "방구석꿀템(영상 3편 실측)",
        "bar": "#FE385F", "on_bar": "#FFFFFF", "bar_h": 202,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#666666", "sub_h": 96,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("Pretendard-Bold.otf", 63, "#333333", "#00A34F", 36, 5, "#FFFFFF", True, "#FFFFFF"),
        # 이 채널은 상단의 강렬한 핫핑크색 포털 스타일 헤더와 함께 커뮤니티 인기 글 레이아웃을 차용한 독특한 UI 피드를 보여줍니다.
    },
    "sul_lucky": {
        "name": "럭키박스", "ref": "럭키박스(영상 3편 실측)",
        "bar": "#EB5260", "on_bar": "#000000", "bar_h": 202,
        "left_icon": "bookmark", "right_icon": "hamburger",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 134,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("Pretendard-ExtraBold.otf", 86, "#FFFFFF", "#F9D803", 40, 7, "#111111", True, "#000000"),
        # 빨간색 브랜드 상단 바가 뚜렷하게 존재감을 드러내며 채널 정체성을 강조합니다. 검은색 반투명 박스 위에 얹힌 두꺼운 2줄 헤드
    },
    "sul_cheat": {
        "name": "쇼핑 치트키", "ref": "쇼핑 치트키(영상 3편 실측)",
        "bar": "#CCD1C8", "on_bar": "#000000", "bar_h": 154,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 96,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("TmonMonsori.ttf", 90, "#FFFFFF", "#FF1E1E", 38, 7, "#000000", False, "#000000"),
        # 이 채널은 모바일 쇼핑몰 또는 SNS 상세페이지 레이아웃을 상단에 씌워 실제 탐색하는 듯한 인터페이스 효과를 줍니다. 붉은색과
    },
    "sul_gongami": {
        "name": "공가미", "ref": "공가미(영상 3편 실측)",
        "bar": "#242424", "on_bar": "#FFFFFF", "bar_h": 192,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 115,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("Pretendard-ExtraBold.otf", 81, "#FFFFFF", "#64E9CC", 38, 7, "#111111", False, "#222222"),
        # 상단에 채널 이름과 아이콘을 배치해 고유의 브랜드 정체성을 유지하는 레이아웃입니다. 본문 자막은 둥근 흰색 박스를 씌워 가독성
    },
    "sul_core": {
        "name": "코어장바구니", "ref": "코어장바구니(영상 3편 실측)",
        "bar": "#511C21", "on_bar": "#A67C80", "bar_h": 134,
        "left_icon": "hamburger", "right_icon": "none",
        "center_kind": "none",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 173,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("NotoSansKR-Bold.otf", 73, "#FFFFFF", "#FBEC15", 34, 7, "#000000", False, "#000000"),
        # 상단의 짙은 버건디색 배경 위에 흰색과 노란색의 두꺼운 테두리 헤드라인을 배치하여 강렬한 시각적 효과를 줍니다. 자막과 추가 
    },
    "sul_jangchak": {
        "name": "살림장착", "ref": "살림장착(영상 3편 실측)",
        "bar": "#CFE2F3", "on_bar": "#1D3557", "bar_h": 192,
        "left_icon": "none", "right_icon": "none",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 115,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("GmarketSansBold.otf", 89, "#FFFFFF", "#11B3F3", 40, 7, "#000000", False, "#FFFFFF"),
        # 상하단에 넓은 여백을 두고 정보성 텍스트를 배치하는 전형적인 카드 뉴스 형태의 레이아웃입니다. 굵은 테두리의 메인 타이틀과 깔
    },
    "sul_chunjae": {
        "name": "쇼핑천재", "ref": "쇼핑천재(영상 3편 실측)",
        "bar": "#FFFFFF", "on_bar": "#000000", "bar_h": 0,
        "left_icon": "none", "right_icon": "none",
        "center_kind": "없음",
        "sub_bg": "#F8F9FA", "sub_text": "#888888", "sub_h": 0,
        "has_head": False, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("GmarketSansBold.otf", 70, "#FFFFFF", "#FFE000", 26, 5, "#000000", False, "#FFFFFF"),
        # 상단 영역에 넓고 어두운 백그라운드를 배치하고 노란색과 흰색의 대비가 강한 고딕 헤드라인을 사용하여 정보를 직관적으로 강조합니
    },
    "sul_even": {
        "name": "이븐쇼핑", "ref": "이븐쇼핑(영상 3편 실측)",
        "bar": "#212121", "on_bar": "#FFFFFF", "bar_h": 144,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "없음",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 106,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("SpoqaHanSansNeo-Bold.otf", 90, "#FFFFFF", "#2EE3E3", 37, 7, "#000000", False, "#000000"),
        # 상단 메뉴 바 영역과 깔끔하게 배치된 타이틀 구성이 모바일 웹사이트의 상단 뷰를 연상시켜 신뢰감을 줍니다. 본문 자막에는 가독
    },
    "sul_igeo": {
        "name": "이거였네", "ref": "이거였네(영상 3편 실측)",
        "bar": "#12373D", "on_bar": "#63B5C3", "bar_h": 192,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#999999", "sub_h": 67,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("Pretendard-ExtraBold.otf", 73, "#111111", "#111111", 37, 5, "#FFFFFF", True, "#FFFFFF"),
        # 상단에 딥 그린 톤의 UI 바를 배치하고 로고와 메뉴 아이콘을 얹어 모바일 웹 브라우저 같은 친숙한 느낌을 줍니다. 헤드라인과
    },
    "sul_dalrae": {
        "name": "달래샵", "ref": "달래샵(영상 3편 실측)",
        "bar": "#000000", "on_bar": "#FFFFFF", "bar_h": 0,
        "left_icon": "none", "right_icon": "none",
        "center_kind": "없음",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 154,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("Pretendard-ExtraBold.otf", 81, "#FFFFFF", "#FFE600", 28, 7, "#000000", False, "#000000"),
        # 상단의 넓은 블랙 영역과 그 아래 배치된 화이트 서브타이틀 바가 정돈된 그리드 레이아웃을 형성합니다. 볼드한 서체와 원색의 옐
    },
    "sul_kkultip": {
        "name": "꿀팁꿀템", "ref": "꿀팁꿀템(영상 3편 실측)",
        "bar": "#000000", "on_bar": "#FFE033", "bar_h": 0,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 106,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("TmonMonsori.ttf", 90, "#FFFFFF", "#FFFFFF", 30, 7, "#000000", False, "#FFFFFF"),
        # 상단에 별점, 조회수, 댓글수 데코레이션을 포함한 고정 포털 프레임을 배치하여 정보의 신뢰도와 주목도를 높였습니다. 자막은 깔
    },
    "sul_daissue": {
        "name": "다있슈", "ref": "다있슈(영상 3편 실측)",
        "bar": "#53796D", "on_bar": "#FFFFFF", "bar_h": 182,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 144,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("GmarketSansBold.otf", 90, "#FFFFFF", "#00EBFF", 39, 7, "#000000", False, "#FFFFFF"),
        # 상단에 다이소 매장을 연상시키는 민트색 UI 디자인과 함께 둥글고 두꺼운 서체의 강렬한 헤드라인을 적용했습니다. 동영상 프레임
    },
    "sul_insaeng": {
        "name": "인생갓템", "ref": "인생갓템(영상 3편 실측)",
        "bar": "#F7F1CE", "on_bar": "#352520", "bar_h": 144,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#111111", "sub_h": 115,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("GmarketSansBold.otf", 90, "#1C1C1C", "#00BAD6", 37, 7, "#FFFFFF", False, "#00B0FF"),
        # 인터넷 커뮤니티 게시글을 모바일 웹 브라우저로 캡처한 듯한 노란색 상단 레이아웃이 독특합니다. 실제 게시글 상세 화면처럼 작성
    },
    "sul_namanto": {
        "name": "나만또모르고있었지", "ref": "나만또모르고있었지(영상 3편 실측)",
        "bar": "#1A1A1A", "on_bar": "#FFFFFF", "bar_h": 163,
        "left_icon": "none", "right_icon": "bookmark",
        "center_kind": "검색창",
        "sub_bg": "#FFFFFF", "sub_text": "#8E8E8E", "sub_h": 77,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("Pretendard-SemiBold.otf", 59, "#222222", "#222222", 33, 5, "#FFFFFF", True, "#FFFFFF"),
        # 상단에 인스타그램 피드 혹은 커뮤니티 글을 연상시키는 모던한 카드형 UI를 배치하여 친숙하고 신뢰감 있는 정보 전달 방식을 사
    },
    "sul_yosae": {
        "name": "요새난리", "ref": "요새난리(영상 2편 실측)",
        "bar": "#000000", "on_bar": "#FFFFFF", "bar_h": 0,
        "left_icon": "none", "right_icon": "none",
        "center_kind": "없음",
        "sub_bg": "#000000", "sub_text": "#000000", "sub_h": 0,
        "has_head": False, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("NotoSansKR-Bold.otf", 89, "#FFFFFF", "#52E4FF", 30, 7, "#000000", True, "#000000"),
        # 이 채널은 상단 검은 레터박스 영역에 굵은 테두리의 흰색 및 하늘색 조합 헤드라인을 배치하여 주목도를 높입니다. 본문 자막 역
    },
    "sul_museun": {
        "name": "무슨템", "ref": "무슨템(영상 3편 실측)",
        "bar": "#090A0C", "on_bar": "#FFFFFF", "bar_h": 221,
        "left_icon": "hamburger", "right_icon": "search",
        "center_kind": "채널명",
        "sub_bg": "#F2F2F2", "sub_text": "#000000", "sub_h": 125,
        "has_head": True, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("NotoSansKR-Bold.otf", 70, "#FFFFFF", "#FFFFFF", 38, 5, "#000000", True, "#000000"),
        # 이 채널은 상단에 모바일 웹 포털 UI를 그대로 모방한 독특한 레이아웃을 고수하여 시청자에게 익숙함과 신뢰를 줍니다. 헤드라인
    },
    "sul_jipdori": {
        "name": "집돌이", "ref": "집돌이(영상 3편 실측)",
        "bar": "#C5653B", "on_bar": "#000000", "bar_h": 211,
        "left_icon": "none", "right_icon": "none",
        "center_kind": "채널명",
        "sub_bg": "#FFFFFF", "sub_text": "#000000", "sub_h": 0,
        "has_head": False, "demo_views": "264만",
        "demo_comments": "587",
        "headcopy": _hc("NotoSansKR-Bold.otf", 65, "#000000", "#000000", 37, 5, "#FFFFFF", True, "#F6EBDB"),
        # 상단을 따뜻한 테라코타 색상의 타이틀 바와 넓은 크림색 헤더 영역으로 분할하여 텍스트를 배치한 독특한 레이아웃입니다. 군더더기
    },

    # ── 기존 4종(옛 작업이 가리키고 있다 — id 재사용·삭제 금지) ──────────
    "news_coral":  {"name": "커뮤니티 · 살구", "bar": "#F08080", "on_bar": "#FFFFFF"},
    "news_lime":   {"name": "커뮤니티 · 연두", "bar": "#B5D46A", "on_bar": "#1A1A1A"},
    "news_gray":   {"name": "커뮤니티 · 그레이", "bar": "#6E6E6E", "on_bar": "#FFFFFF"},
    "news_navy":   {"name": "커뮤니티 · 네이비", "bar": "#2B3A67", "on_bar": "#FFFFFF"},
}

# 기본 치수(1080x1920 기준). 사장님이 화면에서 바 높이를 조절하면 bar_h만 바뀐다.
DEFAULTS = {
    "preset": "news_coral",
    "bar_h": 190,          # 상단 띠 높이(px)
    "bottom_h": 0,         # 하단 띠 높이(px) — 0이면 없음
    # 제목(흰 블록) 높이(px). ★0 = "안 정했음" → 줄 수로 자동 계산(지금까지의 동작).
    #   2026-08-23 사장님: "칸높이 조정이 제목칸 채널명칸 두개다 따로 조정이 되도록
    #   해줘 — 어떤곳에 두줄이 들어갈지 모름". 채널명칸(bar_h)과 **따로** 움직여야 해서
    #   값을 갈라 뒀다. 기존 작업물엔 이 값이 없으므로 0(자동)이 기본이어야 회귀가 없다.
    "head_h": 0,
    "channel": "",         # 가짜 채널명
    "ad_badge": False,     # [광고] 뱃지
    # ── [광고] 표시 다듬기(2026-08-22 사장님 "크기나 마우스로 위치조정 흐리기") ──
    #   ★0 = "안 정했음" → 지금까지의 자리·크기를 그대로 쓴다(채널명·제목과 같은 규약).
    "ad_size": 0,          # 글자 크기(px). 0이면 24
    "ad_x": 0,             # 가로 위치 %. 0이면 기존 자리(오른쪽 아이콘 위)
    "ad_y": 0,             # 세로 위치 %. 0이면 기존 자리
    "ad_alpha": 100,       # 진하기 %. 낮출수록 흐려진다(0=안 보임)
    "icons": True,         # ☰ / 🔍
    "title": "",           # 굵은 후킹 제목(자동 줄바꿈)
    "views": "",           # "264만"
    "comments": "",        # "587"
    "head_bg": "#FFFFFF",  # 제목·메타가 얹히는 흰 블록
    # 채널명칸↔제목칸 경계선(2026-08-23). 기본 ON — 실제 커뮤니티 글이 대개 선이 있다.
    "sep_line": True,
    # ── 글자 꾸미기(2026-08-22 신설) ─────────────────────────────
    # ★비워두면(""/None) **프리셋이 정한 값**을 쓴다 — 기존 20여 종의 생김새가
    #   그대로 유지되게 하려면 "안 정했음"과 "0으로 정했음"을 갈라야 한다.
    "ch_font": "",         # 채널명 폰트 파일명(빈값=Pretendard-Bold)
    "ch_size": 0,          # 채널명 글씨 크기(0=띠 높이의 30%, 기존 자동 규칙)
    "ch_x": 50,            # 채널명 가로 위치 %(50=가운데)
    "title_font": "",      # 제목 폰트(빈값=Pretendard-ExtraBold)
    "title_size": 0,       # 제목 크기(0=62, 기존 값)
    "title_x": 50,         # 제목 가로 위치 %
    # 제목 글자색. ★기본 #141414 = 예전에 박혀 있던 (20,20,20)과 같은 값이라 회귀 없음.
    "title_color": "#141414",
}

_FONTS = {
    "bar": "Pretendard-Bold.otf",
    "title": "Pretendard-ExtraBold.otf",
    "meta": "Pretendard-Regular.otf",
}


def _font(kind, size, override=""):
    """kind = 기본 폰트 갈래. override에 파일명이 오면 그걸 먼저 쓴다.

    ★override는 화면이 고른 폰트다. 없는 파일이면 조용히 기본으로 돌아간다 —
      여기서 죽으면 그림 전체가 안 나온다.
    """
    if override:
        po = _FONT_DIR / override
        if po.exists():
            return ImageFont.truetype(str(po), size)
    p = _FONT_DIR / _FONTS[kind]
    if p.exists():
        return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def _rgb(hex_color):
    h = (hex_color or "#000000").lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def _fade(color, pct):
    """색을 pct%만큼만 진하게(흐리기). 100이면 그대로 — 기존 그림이 안 바뀐다."""
    if not isinstance(color, (tuple, list)) or pct >= 100:
        return color
    a = color[3] if len(color) > 3 else 255
    return (color[0], color[1], color[2], int(a * max(0, min(100, pct)) / 100))


def normalize(spec):
    """화면이 준 값에 기본값을 채우고 범위를 자른다.

    ★범위 검사도 여기 한 곳 — 화면과 서버가 따로 자르면 미리보기와 결과가 갈린다.
    """
    s = dict(DEFAULTS)
    for k, v in (spec or {}).items():
        if k in s:
            s[k] = v
    if s["preset"] not in PRESETS:
        s["preset"] = DEFAULTS["preset"]
    # ★프리셋이 자기 띠 높이를 갖고 있으면 그게 기본이다(실측한 원본 비율).
    #   화면이 bar_h를 직접 보내오면 그건 사장님이 손으로 민 것이므로 존중한다.
    #   이 분기가 없으면 20종이 전부 같은 190px 띠가 돼 "비율이 원본과 다르다"가 된다.
    p = PRESETS[s["preset"]]
    # ★`p.get("bar_h")`로 검사하면 **0이 falsy라 통째로 무시된다** — 띠가 없는
    #   풀블리드 채널(실측 4곳: 쇼핑천재·달래샵·꿀팁꿀템·요새난리)이 원치 않는
    #   190px 띠를 뒤집어쓴다. 있고 없고는 `is not None`으로 갈라야 한다.
    if "bar_h" not in (spec or {}) and p.get("bar_h") is not None:
        s["bar_h"] = p["bar_h"]
    # 위·아래 띠는 **같은 규칙**으로 자른다 — 한쪽만 다르게 자르면 언젠가 어긋난다
    for k in ("bar_h", "bottom_h"):
        try:
            s[k] = int(s[k])
        except (TypeError, ValueError):
            s[k] = DEFAULTS[k]
        s[k] = max(0, min(400, s[k]))    # 0이면 띠 없음, 400 넘으면 화면을 먹는다
    # 제목칸은 두 줄이 들어갈 수 있어 띠보다 상한이 높다(자동값도 2줄이면 250을 넘는다).
    # 0 = 자동(줄 수로 계산) — 여기서 0을 살려둬야 기존 그림이 안 바뀐다.
    try:
        s["head_h"] = int(s["head_h"])
    except (TypeError, ValueError):
        s["head_h"] = DEFAULTS["head_h"]
    s["head_h"] = max(0, min(700, s["head_h"]))
    for k in ("channel", "title", "views", "comments"):
        s[k] = str(s[k] or "").strip()[:60]
    # ★제목만 줄바꿈을 살린다(사장님이 엔터로 나눈 자리 = _wrap이 그대로 지킨다).
    #   나머지는 한 줄짜리 칸이라 줄바꿈이 들어오면 공백으로 눕힌다 — 안 그러면
    #   채널명에 엔터가 섞였을 때 띠 밖으로 삐져나간다.
    for k in ("channel", "views", "comments"):
        s[k] = " ".join(s[k].split())
    s["ad_badge"] = bool(s["ad_badge"])
    s["icons"] = bool(s["icons"])
    s["sep_line"] = bool(s["sep_line"])
    # ── 색은 반드시 #RRGGBB로 걸러 낸다 ──
    # ★_rgb()는 형식을 안 따지고 int(...,16)을 해서, 이상한 값이 들어오면 그림이 아니라
    #   **500 에러**가 난다. 쿼리스트링으로 아무 문자열이나 올 수 있으니 여기서 막는다.
    #   (여기 한 곳에서만 자른다 — 위 숫자 clamp와 같은 원칙)
    for k in ("head_bg", "title_color"):
        v = str(s.get(k) or "").strip()
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            v = DEFAULTS[k]
        s[k] = v
    # ── 글자 꾸미기 값도 **여기 한 곳에서만** 자른다(위 bar_h와 같은 원칙) ──
    # ★0은 "안 정했음"이라 살려둔다 — 그림 그릴 때 프리셋 기본으로 되돌아간다.
    for k, lo, hi in (("ch_size", 0, 200), ("title_size", 0, 200),
                      ("ch_x", 0, 100), ("title_x", 0, 100),
                      ("ad_size", 0, 200), ("ad_x", 0, 100), ("ad_y", 0, 100),
                      ("ad_alpha", 0, 100)):
        try:
            s[k] = int(s[k])
        except (TypeError, ValueError):
            s[k] = DEFAULTS[k]
        s[k] = max(lo, min(hi, s[k]))
    # 폰트는 파일명만 받는다 — 경로가 섞이면 폰트 폴더 밖을 읽을 수 있다.
    for k in ("ch_font", "title_font"):
        v = str(s[k] or "").strip()
        s[k] = v if (v and "/" not in v and "\\" not in v and ".." not in v) else ""
    return s


def cache_key(spec):
    """같은 spec이면 같은 파일 — 렌더마다 다시 그리지 않게."""
    s = normalize(spec)
    raw = json.dumps(s, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _wrap(draw, text, font, max_w):
    """어절 단위로 접는다(한국어는 어절이 끊기면 못 읽는다).

    ★사장님이 **엔터로 직접 나눈 줄은 그대로 지킨다**(2026-08-23 "제목에서 엔터로
      아래로 줄바꾸기 해줘"). 예전엔 `text.split()`이 줄바꿈을 공백과 똑같이 취급해
      엔터를 쳐도 한 덩어리로 다시 이어졌다. 이제 줄바꿈으로 먼저 쪼개고,
      **각 줄이 폭을 넘칠 때만** 자동으로 접는다.
    """
    if not text:
        return []
    lines = []
    for para in str(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not para.strip():
            continue                     # 빈 줄은 자리만 먹으므로 버린다
        cur = ""
        for word in para.split():
            trial = (cur + " " + word).strip()
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)
    return lines[:3]        # 4줄부터는 제목이 아니라 본문이다


def _hamburger(d, cx, cy, color, w=54, gap=18, th=8):
    for i in (-1, 0, 1):
        y = cy + i * gap
        d.rounded_rectangle([cx - w // 2, y - th // 2, cx + w // 2, y + th // 2],
                            radius=th // 2, fill=color)


def _search(d, cx, cy, color, r=22, th=7):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=th)
    d.line([cx + r * 0.72, cy + r * 0.72, cx + r * 1.5, cy + r * 1.5],
           fill=color, width=th)


def _dots(d, cx, cy, color, r=7, gap=26):
    """⋮ 점 3개(세로). 유튜브 플레이어 UI를 흉내내는 채널이 쓴다."""
    for i in (-1, 0, 1):
        d.ellipse([cx - r, cy + i * gap - r, cx + r, cy + i * gap + r], fill=color)


def _back(d, cx, cy, color, s=26, th=8):
    """← 뒤로가기 화살표."""
    d.line([cx + s * 0.6, cy - s, cx - s * 0.4, cy], fill=color, width=th)
    d.line([cx - s * 0.4, cy, cx + s * 0.6, cy + s], fill=color, width=th)


def _bookmark(d, cx, cy, color, w=30, h=42, th=8):
    """🔖 북마크(빈 리본)."""
    d.line([cx - w // 2, cy - h // 2, cx - w // 2, cy + h // 2], fill=color, width=th)
    d.line([cx + w // 2, cy - h // 2, cx + w // 2, cy + h // 2], fill=color, width=th)
    d.line([cx - w // 2, cy - h // 2, cx + w // 2, cy - h // 2], fill=color, width=th)
    d.line([cx - w // 2, cy + h // 2, cx, cy + h // 6], fill=color, width=th)
    d.line([cx + w // 2, cy + h // 2, cx, cy + h // 6], fill=color, width=th)


# 실측에서 나온 아이콘 종류 → 그리는 함수. 없는 이름이 와도 죽지 않게 get으로 받는다.
_ICONS = {"hamburger": _hamburger, "search": _search, "dots": _dots,
          "back": _back, "bookmark": _bookmark}


def render(spec):
    """spec → 1080x1920 RGBA 이미지. 가운데는 투명(영상이 비쳐야 한다)."""
    s = normalize(spec)
    p = PRESETS[s["preset"]]
    bar_col, on_bar = _rgb(p["bar"]), _rgb(p["on_bar"])

    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    bar_h = s["bar_h"]
    if bar_h > 0:
        d.rectangle([0, 0, W, bar_h - 1], fill=bar_col)   # PIL은 끝점 포함 → -1
        cy = bar_h // 2
        if s["icons"]:
            # ★어느 아이콘인지도 채널마다 다르다(실측: 햄버거·돋보기·⋮·←·북마크).
            #   전에는 무조건 ☰+🔍이라 ⋮를 쓰는 채널이 딴 채널처럼 보였다.
            left = _ICONS.get(p.get("left_icon", "hamburger"))
            right = _ICONS.get(p.get("right_icon", "search"))
            if left:
                left(d, 92, cy, on_bar)
            if right:
                right(d, W - 96, cy, on_bar)
        if s["channel"]:
            # 크기 0 = "안 정했음" → 기존 자동 규칙(띠 높이의 30%)을 그대로 쓴다.
            csize = s["ch_size"] or max(28, int(bar_h * 0.30))
            f = _font("bar", csize, s["ch_font"])
            cx = W * (s["ch_x"] / 100.0)
            # 글자 절반이 화면 밖으로 나가지 않게 중심을 안쪽으로 당긴다.
            half = d.textlength(s["channel"], font=f) / 2
            cx = max(half + 20, min(W - half - 20, cx))
            d.text((cx, cy), s["channel"], font=f, fill=on_bar, anchor="mm")

    # ★[광고]는 **틀과 독립**이다(2026-08-22 사장님 "템플릿 없어도 사용가능").
    #   그래서 띠(bar_h>0) 블록 **밖**에서 그린다 — 띠가 없어도 나온다.
    #   자리는 오른쪽 아이콘(돋보기) 위. 띠가 없으면 띠에 얹을 수 없으니
    #   화면 맨 위 여백에 두고, 글자색도 띠 위가 아니면 흰색+검은 외곽선으로 읽히게 한다.
    if s["ad_badge"]:
        # 크기 0 = "안 정했음" → 지금까지의 24px 그대로(채널명·제목과 같은 규약).
        fb = _font("meta", s["ad_size"] or 24)
        if bar_h > 0:
            ax, ay, fill, stroke = W - 96, max(14, bar_h // 2 - int(bar_h * 0.28)), on_bar, None
        else:
            ax, ay, fill, stroke = W - 96, 40, (255, 255, 255, 255), (0, 0, 0, 255)
        # 사장님이 화면에서 끌어다 놓았으면 그 자리로(0이면 위 기본 자리 그대로).
        # ⚠️화면 밖 방지는 **사장님이 자리를 정했을 때만** 건다. 기본 자리에까지 걸면
        #   띠가 얇을 때 기존 y(최소 14)가 밀려 지금까지의 그림이 바뀐다(회귀).
        if s["ad_x"]:
            half = d.textlength("[광고]", font=fb) / 2
            ax = int(W * s["ad_x"] / 100.0)
            ax = max(int(half) + 8, min(W - int(half) - 8, ax))
        if s["ad_y"]:
            ay = int(H * s["ad_y"] / 100.0)
            ay = max(fb.size, min(H - fb.size, ay))
        fill = _fade(fill, s["ad_alpha"])
        stroke = _fade(stroke, s["ad_alpha"]) if stroke else None
        if stroke:
            d.text((ax, ay), "[광고]", font=fb, fill=fill, anchor="mm",
                   stroke_width=3, stroke_fill=stroke)
        else:
            d.text((ax, ay), "[광고]", font=fb, fill=fill, anchor="mm")

    if s["bottom_h"] > 0:
        d.rectangle([0, H - s["bottom_h"], W, H - 1], fill=bar_col)

    # 제목·메타가 얹히는 흰 블록 — 내용이 있을 때만 그린다(빈 블록이 영상을 가리면 손해).
    y = bar_h
    if s["title"] or s["views"] or s["comments"]:
        tsize = s["title_size"] or 62
        ft = _font("title", tsize, s["title_font"])
        fm = _font("meta", 30)
        # ★가로위치를 옮기면 그 자리에서 쓸 수 있는 폭이 줄어든다.
        #   예전처럼 W-120으로 접으면 왼쪽으로 민 제목이 화면 밖으로 잘린다(실측).
        #   중심에서 가까운 쪽 여백의 2배가 실제로 그릴 수 있는 폭이다.
        tx = W * (s["title_x"] / 100.0)
        avail = int(min(tx, W - tx) * 2) - 40
        lines = _wrap(d, s["title"], ft, max(200, min(W - 120, avail)))
        # 줄 간격도 글씨 크기를 따라간다 — 안 그러면 키웠을 때 글자가 겹친다.
        line_h = max(40, int(tsize * 1.26))
        meta = ""
        if s["views"]:
            meta = f"조회수 {s['views']}"
        if s["comments"]:
            meta = (meta + " | " if meta else "") + f"댓글 {s['comments']}개"
        # ★높이 = 사장님이 정했으면 그 값, 아니면 지금까지처럼 줄 수로 자동(0=자동).
        #   두 줄짜리 제목이 어느 칸에 들어갈지 모르니 손으로도 잡을 수 있어야 한다
        #   (2026-08-23 지시). 자동식은 **건드리지 않는다** — 기존 그림 보존.
        auto_h = 36 + len(lines) * line_h + (52 if meta else 0) + 24
        block_h = s["head_h"] or auto_h
        d.rectangle([0, y, W, y + block_h - 1], fill=_rgb(s["head_bg"]))
        # ★채널명칸과 제목칸 사이 구분선(2026-08-23 사장님 "제목과 체널명사이 선 그어주면 좋아").
        #   흰 블록 위에 얹는 얇은 회색 선 — 띠가 없으면(bar_h=0) 그을 경계 자체가 없다.
        if s["sep_line"] and bar_h > 0:
            d.rectangle([0, y, W, y + 2], fill=(214, 214, 214, 255))
        # 손으로 키웠으면 남는 공간을 위아래로 나눠 글이 가운데 오게 한다.
        # (자동일 땐 auto_h == block_h라 pad=36 그대로 = 기존과 동일)
        ty = y + max(0, (block_h - auto_h) // 2) + 36
        for ln in lines:
            d.text((tx, ty), ln, font=ft, fill=_rgb(s["title_color"]), anchor="ma")
            ty += line_h
        if meta:
            d.text((60, ty + 6), meta, font=fm, fill=(120, 120, 120, 255), anchor="la")
            ty += 46
            d.rectangle([60, ty + 8, W - 60, ty + 11], fill=(30, 30, 30, 255))
    return im


def cache_path(spec):
    """그림 파일이 놓일 자리. ★화면(API)과 렌더(mix_pipeline)가 **같은 자리**를 봐야
    미리보기에서 만든 그림을 렌더가 그대로 쓴다. 경로를 두 곳에 적지 않는다(0순위-B)."""
    return (pathlib.Path(__file__).resolve().parent / "data" / "frame_cache"
            / f"{cache_key(spec)}.png")


def render_to(spec, out_path):
    """파일로 저장하고 경로를 돌려준다. 이미 있으면 다시 그리지 않는다(cache_key가 같으면 같은 그림)."""
    out_path = pathlib.Path(out_path)
    if out_path.exists():
        return out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    render(spec).save(out_path, "PNG")
    return out_path
