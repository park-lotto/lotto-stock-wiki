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

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
_FONT_DIR = pathlib.Path(__file__).resolve().parent / "static" / "fonts"

# 공백 글리프 없는 폰트(빙그레·리디바탕)의 띄어쓰기 ⊠ 우회 — 자막과 같은 판정을 쓴다.
# ★2026-08-26: 자막(video_assemble)에만 우회가 있고 여기엔 없어서, 꾸미기 틀의
#   채널명·제목에서 띄어쓰기가 ⊠로 나갔다(36종 전수 렌더로 발견). 같은 판단을
#   두 번 적으면 이렇게 한쪽만 고쳐진다 → font_glyphs 한 곳에서만 정한다(0순위-B).
from . import font_glyphs as _fg

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


def _cap(color, outline_color, y, box=False):
    """자막 한 세트(색·외곽선·세로위치·박스). 헤드카피(_hc)와 짝이다.

    ★왜 생겼나(2026-08-25): 제미니는 실측 때 cap_color·cap_outline·cap_y·cap_box를
      **처음부터 읽고 있었는데** 소비처가 0곳이었다(실측: 코드 전체 grep 0건).
      그래서 틀과 헤드카피만 채널 질감을 따라가고 자막만 우리 기본값으로 나가
      "한 세트로 안 보인다"가 됐다.

    ★여기 없는 값(폰트·크기·두께)은 **일부러 안 넣는다.** 실측 스키마가 그걸 안
      물어봤기 때문이다 — 없는 걸 지어내면 살림킹왕짱 색 뒤집힘과 같은 사고가 난다.
      화면이 쓰던 값을 그대로 둔다(빈값 = "안 정했음" 규약, DEFAULTS와 같다).
    """
    # ★박스 색은 지어내지 않는다 — 실측한 outline_color를 그대로 쓴다(2026-08-25 결함).
    #   외곽선 색 = 그 채널이 글자 뒤에 깔던 '밝은 면' 색이다. 예전엔 여기 "#000000"을
    #   박아뒀는데, cap_color가 검정인 채널이 많아 **검은 박스 위 검은 글자**가 됐다
    #   (실측: 박스 켜진 틀 중 9종). 글자가 외곽선만으로 겨우 읽혀 뭉개져 보였다.
    return {"color": color, "outline": True, "outline_color": outline_color,
            "y_pct": y, "box": bool(box), "box_color": outline_color}


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
        "caption": _cap("#000000", "#FFFFFF", 63, False),
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
        "caption": _cap("#000000", "#FFFFFF", 55, False),
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
        "caption": _cap("#000000", "#FFFFFF", 57, True),
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
        "caption": _cap("#111111", "#FFFFFF", 50, True),
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
        "caption": _cap("#000000", "#FFFFFF", 58, False),
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
        "caption": _cap("#000000", "#FFFFFF", 57, False),
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
        "caption": _cap("#000000", "#FFFFFF", 55, True),
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
        "caption": _cap("#000000", "#FFFFFF", 50, True),
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
        "caption": _cap("#333333", "#FFFFFF", 59, False),
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
        "caption": _cap("#000000", "#FFFFFF", 41, True),
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
        "caption": _cap("#FFFFFF", "#000000", 56, False),
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
        "caption": _cap("#111111", "#FFFFFF", 53, False),
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
        "caption": _cap("#000000", "#FFFFFF", 45, True),
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
        "caption": _cap("#FFFFFF", "#000000", 49, True),
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
        "caption": _cap("#111111", "#FFFFFF", 58, True),
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
        "caption": _cap("#111111", "#FFFFFF", 56, False),
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
        "caption": _cap("#111111", "#FFFFFF", 47, True),
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
        "caption": _cap("#FEE809", "#000000", 49, False),
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
        "caption": _cap("#000000", "#FFFFFF", 53, True),
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
        "caption": _cap("#000000", "#FFFFFF", 52, False),
        # 상단을 따뜻한 테라코타 색상의 타이틀 바와 넓은 크림색 헤더 영역으로 분할하여 텍스트를 배치한 독특한 레이아웃입니다. 군더더기
    },
    "news_coral":  {"name": "커뮤니티 · 살구", "bar": "#F08080", "on_bar": "#FFFFFF"},
    "news_lime":   {"name": "커뮤니티 · 연두", "bar": "#B5D46A", "on_bar": "#1A1A1A"},
    "news_gray":   {"name": "커뮤니티 · 그레이", "bar": "#6E6E6E", "on_bar": "#FFFFFF"},
    "news_navy":   {"name": "커뮤니티 · 네이비", "bar": "#2B3A67", "on_bar": "#FFFFFF"},
    # ── 🧱 빈 틀(2026-08-28) — 글자·아이콘 없는 **색띠만**.
    #   왜 필요한가: 지금 20종은 전부 가짜 채널 UI(☰·🔍·채널명)가 박혀 있어
    #   "위아래 띠만 깔고 싶다"가 불가능했다. 아이콘을 하나씩 '없음'으로 돌리는
    #   길은 있었지만 세 칸을 매번 만져야 했다 — 골라서 끝나게 한다.
    #   ★띠 색은 화면에서 바꾼다(bar_color) — 여기 4종은 흔한 출발점일 뿐이다.
    "plain_black": {"name": "빈 틀 · 검정", "bar": "#000000", "on_bar": "#FFFFFF",
                    "left_icon": "none", "right_icon": "none", "center_kind": "없음"},
    "plain_white": {"name": "빈 틀 · 흰색", "bar": "#FFFFFF", "on_bar": "#111111",
                    "left_icon": "none", "right_icon": "none", "center_kind": "없음"},
    "plain_coral": {"name": "빈 틀 · 살구", "bar": "#F08080", "on_bar": "#FFFFFF",
                    "left_icon": "none", "right_icon": "none", "center_kind": "없음"},
    "plain_navy":  {"name": "빈 틀 · 네이비", "bar": "#2B3A67", "on_bar": "#FFFFFF",
                    "left_icon": "none", "right_icon": "none", "center_kind": "없음"},
    # ── 🖤 회색띠 2줄 헤드 (2026-08-31, 사장님이 가져온 실캡처 1장으로 만듦) ──
    #   구조: 짙은 회색 띠 안에 **2줄 헤드카피**(1줄 흰색 / 2줄 형광초록) → 그 아래
    #   흰 블록에 검은 제목 한 줄. 아이콘·채널명은 없다(띠가 곧 헤드라인 판이다).
    #   ★색·높이는 캡처 픽셀 실측(339x600 → 1920 환산): 띠 0~23%, 흰 블록 24~35.5%,
    #     띠 #404040, 2줄 강조 #00E500, 흰 블록 #F2F2F2 / 글자 #000000.
    "gray_head2": {
        "name": "회색띠 · 2줄 헤드", "ref": "사장님 캡처 실측(2026-08-31)",
        "bar": "#404040", "on_bar": "#FFFFFF", "bar_h": 442,
        "left_icon": "none", "right_icon": "none", "center_kind": "없음",
        "sub_bg": "#F2F2F2", "sub_text": "#000000", "sub_h": 220,
        "has_head": True, "demo_views": "264만", "demo_comments": "587",
        "headcopy": _hc("BlackHanSans.ttf", 96, "#FFFFFF", "#00E500", 10, 10, "#000000"),
        "caption": _cap("#FFFFFF", "#000000", 78, False),
    },
}

# 기본 치수(1080x1920 기준). 사장님이 화면에서 바 높이를 조절하면 bar_h만 바뀐다.
DEFAULTS = {
    # ── 가림막(2026-08-28 고객 요청 "자막이 안 지워졌을때 가릴수 있는 네모 도형") ──
    # ★VMake가 못 지운 자막·워터마크·스티커를 덮는다(반투명 대형 워터마크는 구조적으로
    #   못 지운다는 걸 08-27에 확정했다 — eraser_watermark는 이미지 전용, 두 번 태워도 무효).
    # 각 항목: {l,t,w,h}=% 좌표, shape=rect|round|pill|ellipse,
    #          fx=solid|fade, color=#RRGGBB, op=0~100, soft=0~100(가장자리), rot=-45~45
    # ★흐림 계열(blur/blurdark)은 여기서 못 그린다 — 배경을 흐리게 하는 건 영상 필터다.
    #   PNG는 '위에 얹는 그림'이라 뒤를 못 만진다. 흐림은 렌더 쪽에서 따로 붙인다(2차).
    "masks": [],
    "preset": "news_coral",
    "bar_h": 190,          # 상단 띠 높이(px)
    # 띠 끝부분 처리(2026-08-28 사장님 시안 "끝부분 효과").
    #   solid=딱 자름(지금까지의 그림) / grad=투명으로 흘림 / blur=경계 뭉갬 /
    #   blurdark=뭉갬+띠를 어둡게. ★기본이 solid라 옛 그림은 하나도 안 바뀐다.
    "bar_fx": "solid",
    "bar_soft": 0,         # 번지는 정도 %(띠 높이 대비). 0이면 효과 없음
    "bottom_h": 0,         # 하단 띠 높이(px) — 0이면 없음
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
    # ── 글자 꾸미기(2026-08-22 신설) ─────────────────────────────
    # ★비워두면(""/None) **프리셋이 정한 값**을 쓴다 — 기존 20여 종의 생김새가
    #   그대로 유지되게 하려면 "안 정했음"과 "0으로 정했음"을 갈라야 한다.
    "ch_font": "",         # 채널명 폰트 파일명(빈값=Pretendard-Bold)
    "ch_size": 0,          # 채널명 글씨 크기(0=띠 높이의 30%, 기존 자동 규칙)
    "ch_x": 50,            # 채널명 가로 위치 %(50=가운데)
    "title_font": "",      # 제목 폰트(빈값=Pretendard-ExtraBold)
    "title_size": 0,       # 제목 크기(0=62, 기존 값)
    "title_x": 50,         # 제목 가로 위치 %
    # ── 제목 글자 꾸미기 확장(2026-08-28 사장님 "폰트쪽 꾸미는것 추가") ──────
    # ★빈값/0 = "안 정했음" → 지금까지의 자동 규칙 그대로(기존 그림 무변경).
    "title_color": "",     # 제목 글자색(빈값=바탕 밝기로 흑/백 자동)
    "title_ol_c": "",      # 제목 외곽선 색(빈값인데 두께>0이면 글자색 반대색 자동)
    "title_ol_w": 0,       # 제목 외곽선 두께 px(0=외곽선 없음)
    # ── 틀 커스텀(2026-08-25 사장님 "거기서 커스텀해서 수정할 수 있게") ──────
    # ★실측은 근사치다 — 폰트는 견본에서 고른 것이고, 색도 프레임 한 장에서 읽었다.
    #   "똑같이" 맞추는 마지막 한 뼘은 **사람 손**이어야 한다. 그런데 여기까지는
    #   프리셋에만 있고 화면이 못 건드려서, 고른 뒤엔 손댈 방법이 아예 없었다.
    # ★빈값 = "안 정했음" → 프리셋 값(위 글자 꾸미기와 **같은 규약**. 0순위-B).
    "bar_color": "",       # 띠 색(빈값=프리셋 bar)
    "on_bar_color": "",    # 띠 위 글자·아이콘 색(빈값=프리셋 on_bar)
    "left_icon": "",       # 왼쪽 아이콘(hamburger/search/dots/back/bookmark/none)
    "right_icon": "",      # 오른쪽 아이콘(같은 값들)
    "center_kind": "",     # 띠 가운데(검색창/채널명/없음)
    "sub_bg_c": "",        # 제목 블록 바탕색(빈값=프리셋 sub_bg)
    "sub_text_c": "",      # 조회수·댓글 글자색(빈값=프리셋 sub_text)
    # ── 레이아웃(2026-08-25 사장님 "디자인이 이거 하나밖에 안되는거야?") ────────
    # ★뿌리: 실측 스키마가 bar_color·bar_h_pct처럼 **"띠가 어떻게 생겼냐"만** 물었다.
    #   그래서 커뮤니티 글이든 쇼핑몰 상세페이지든 전부 '띠 하나 + 제목줄'로 뭉개져
    #   들어왔고, 20종이 색만 다른 한 벌이 됐다. 제미니는 차이를 알고 notes에 적어뒀다:
    #     커뮤니티 게시글형 6 / 웹헤더·브랜드바형 8 / 검색창형 3 / 쇼핑몰형 2 / 뉴스형 1
    #   → 골격 자체를 고르는 축을 만든다. 빈값이면 프리셋 layout, 그것도 없으면 기본.
    "layout": "",          # ""(=기본·웹헤더형) / "community"
    "post_cat": "",        # 커뮤니티형: 카테고리 태그(빈값이면 안 그림)
    "post_author": "",     # 커뮤니티형: 작성자
    "post_time": "",       # 커뮤니티형: 작성 시간
    "post_likes": "",      # 커뮤니티형: 추천 수
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


# 틀 커스텀 입력 검사용(normalize에서 쓴다).
_VALID_HEX = re.compile(r"#[0-9A-Fa-f]{6}")
# 'none'도 유효한 선택이다("아이콘 안 씀"). _ICONS엔 없으므로 따로 둔다.
_ICON_CHOICES = ("hamburger", "search", "dots", "back", "bookmark", "none")
# 골격 종류. ""(빈값)은 "안 정했음" → 프리셋 → 기본(웹헤더형).
_LAYOUTS = ("community",)


def _rgb(hex_color):
    h = (hex_color or "#000000").lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def _fade(color, pct):
    """색을 pct%만큼만 진하게(흐리기). 100이면 그대로 — 기존 그림이 안 바뀐다."""
    if not isinstance(color, (tuple, list)) or pct >= 100:
        return color
    a = color[3] if len(color) > 3 else 255
    return (color[0], color[1], color[2], int(a * max(0, min(100, pct)) / 100))


_BAR_FX = ("solid", "grad", "blur", "blurdark")
# 가림막의 **종류**(2026-08-28 사장님 "이모티콘이나 뱃지같은거 … 가릴것들 가리게").
#   shape = 색 도형(지금까지의 가림막)  ·  emoji = 이모지 스티커  ·  badge = 글자 뱃지
# ★새 기계를 만들지 않고 masks에 종류를 얹었다. 위치·크기·회전·드래그·저장이 이미
#   여기 다 있다 — 스티커용 배관을 따로 파면 그 규칙이 두 벌이 된다(0순위-B).
_MASK_KINDS = ("shape", "emoji", "badge")
_EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
_EMOJI_PX = 109          # Noto Color Emoji는 109px 고정 비트맵만 있다(실측)

_MASK_SHAPES = ("rect", "round", "pill", "ellipse")
# 흐림 계열은 **그림으로는 못 그린다** — 뒤에 있는 영상을 흐리게 하는 것이라
# 렌더(ffmpeg)가 처리한다. PNG에는 안 그리고 마스크만 넘긴다(render_blur_mask).
_MASK_BLUR_FX = ("blur", "blurdark")
_MASK_FX = ("solid", "fade") + _MASK_BLUR_FX          # 흐림 계열은 PNG로 못 그린다(위 DEFAULTS 주석)
_MASK_MAX = 12                        # 화면에서 실수로 수백 개를 만들어도 렌더가 안 죽게


def _norm_masks(raw):
    """가림막 목록을 정규화한다 — 범위 검사도 **여기 한 곳**(normalize와 같은 규약).

    화면과 서버가 각자 자르면 미리보기와 결과가 갈린다. 이상한 항목은 통째로 버린다
    (조용히 엉뚱한 자리에 그리는 것보다 안 그리는 게 낫다).
    """
    out = []
    for m in (raw or [])[:_MASK_MAX]:
        if not isinstance(m, dict):
            continue
        try:
            l, t = float(m.get("l", 0)), float(m.get("t", 0))
            w, h = float(m.get("w", 0)), float(m.get("h", 0))
        except (TypeError, ValueError):
            continue
        if w <= 0 or h <= 0:
            continue
        l = max(0.0, min(100.0, l)); t = max(0.0, min(100.0, t))
        # ★남은 자리보다 크면 줄인다. 자리 자체가 없으면(가장자리에 딱 붙었다) 버린다 —
        #   하한(0.5%)을 억지로 붙이면 화면 밖으로 삐져나간다(테스트가 잡았다).
        w = min(100.0 - l, w); h = min(100.0 - t, h)
        if w < 0.5 or h < 0.5:
            continue
        shape = m.get("shape") if m.get("shape") in _MASK_SHAPES else "rect"
        fx = m.get("fx") if m.get("fx") in _MASK_FX else "solid"
        col = str(m.get("color") or "#000000")
        if not (len(col) == 7 and col.startswith("#")):
            col = "#000000"
        def _i(k, d, lo, hi):
            try:
                return max(lo, min(hi, int(float(m.get(k, d)))))
            except (TypeError, ValueError):
                return d
        kind = m.get("kind") if m.get("kind") in _MASK_KINDS else "shape"
        # 이모지 1~2자 · 뱃지 글자는 8자까지(그 이상은 뱃지가 아니라 자막이다).
        ch = str(m.get("ch") or "")[:2]
        text = " ".join(str(m.get("text") or "").split())[:8]
        if kind == "emoji" and not ch:
            continue                       # 그릴 글자가 없으면 버린다(빈 자리를 남기지 않는다)
        if kind == "badge" and not text:
            continue
        out.append({"l": round(l, 3), "t": round(t, 3), "w": round(w, 3), "h": round(h, 3),
                    "kind": kind, "ch": ch, "text": text,
                    "shape": shape, "fx": fx, "color": col,
                    "op": _i("op", 100, 0, 100), "soft": _i("soft", 0, 0, 100),
                    "rot": _i("rot", 0, -45, 45)})
    return out


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
    s["masks"] = _norm_masks(s.get("masks"))
    # ★프리셋이 자기 띠 높이를 갖고 있으면 그게 기본이다(실측한 원본 비율).
    #   화면이 bar_h를 직접 보내오면 그건 사장님이 손으로 민 것이므로 존중한다.
    #   이 분기가 없으면 20종이 전부 같은 190px 띠가 돼 "비율이 원본과 다르다"가 된다.
    p = PRESETS[s["preset"]]
    # ★`p.get("bar_h")`로 검사하면 **0이 falsy라 통째로 무시된다** — 띠가 없는
    #   풀블리드 채널(실측 4곳: 쇼핑천재·달래샵·꿀팁꿀템·요새난리)이 원치 않는
    #   190px 띠를 뒤집어쓴다. 있고 없고는 `is not None`으로 갈라야 한다.
    if "bar_h" not in (spec or {}) and p.get("bar_h") is not None:
        s["bar_h"] = p["bar_h"]
    # 띠 끝부분 처리도 **여기 한 곳에서만** 자른다(위 bar_h와 같은 원칙).
    # 모르는 값은 solid로 — 이름이 틀렸는데 조용히 다른 효과가 나가면 더 나쁘다.
    v = str(s.get("bar_fx") or "solid").strip()
    s["bar_fx"] = v if v in _BAR_FX else "solid"
    try:
        s["bar_soft"] = int(s.get("bar_soft") or 0)
    except (TypeError, ValueError):
        s["bar_soft"] = 0
    s["bar_soft"] = max(0, min(100, s["bar_soft"]))
    # 위·아래 띠는 **같은 규칙**으로 자른다 — 한쪽만 다르게 자르면 언젠가 어긋난다
    for k in ("bar_h", "bottom_h"):
        try:
            s[k] = int(s[k])
        except (TypeError, ValueError):
            s[k] = DEFAULTS[k]
        s[k] = max(0, min(400, s[k]))    # 0이면 띠 없음, 400 넘으면 화면을 먹는다
    for k in ("channel", "title", "views", "comments"):
        s[k] = str(s[k] or "").strip()[:60]
    s["ad_badge"] = bool(s["ad_badge"])
    s["icons"] = bool(s["icons"])
    # ── 글자 꾸미기 값도 **여기 한 곳에서만** 자른다(위 bar_h와 같은 원칙) ──
    # ★0은 "안 정했음"이라 살려둔다 — 그림 그릴 때 프리셋 기본으로 되돌아간다.
    for k, lo, hi in (("ch_size", 0, 200), ("title_size", 0, 200),
                      ("ch_x", 0, 100), ("title_x", 0, 100),
                      ("title_ol_w", 0, 20),
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
    # ── 틀 커스텀 값 검사도 **여기 한 곳** ────────────────────────────
    # 색은 #RRGGBB만 받는다. 이상한 값이 오면 빈값(= 프리셋 그대로)으로 떨어뜨린다
    # — 예외로 죽으면 미리보기가 통째로 안 나온다(그림 한 장이 화면 전체를 막는다).
    for k in ("bar_color", "on_bar_color", "sub_bg_c", "sub_text_c",
              "title_color", "title_ol_c"):
        v = str(s[k] or "").strip()
        if not v.startswith("#"):
            v = "#" + v if v else ""
        s[k] = v.upper() if _VALID_HEX.fullmatch(v or "") else ""
    # 아이콘은 우리가 그릴 줄 아는 이름만. 'none'은 "안 그림"이라 유효한 값이다.
    for k in ("left_icon", "right_icon"):
        v = str(s[k] or "").strip()
        s[k] = v if v in _ICON_CHOICES else ""
    v = str(s["center_kind"] or "").strip()
    s["center_kind"] = v if v in _CENTER else ""
    v = str(s["layout"] or "").strip()
    s["layout"] = v if v in _LAYOUTS else ""
    for k in ("post_cat", "post_author", "post_time", "post_likes"):
        s[k] = str(s[k] or "").strip()[:30]
    return s


# ★그리는 코드가 바뀌면 올려라. 캐시키에 섞여 옛 그림이 되살아나는 걸 막는다.
#   2026-08-25 실사고 직전에 발견: 키가 spec만 봐서, 틀 그리는 규칙을 고쳐도
#   같은 파일이 그대로 나왔다("고쳤는데 화면은 그대로"의 단골 원인).
#   프리셋 값 변경도 마찬가지라 PRESETS 해시도 함께 섞는다 — 잊어버려도 자동으로 갈린다.
RENDER_VER = 2


def _presets_sig():
    raw = json.dumps(PRESETS, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:8]


def cache_key(spec):
    """같은 spec이면 같은 파일 — 렌더마다 다시 그리지 않게.
    ★단, **그리는 코드/프리셋이 바뀌면 달라진다**(RENDER_VER + PRESETS 해시)."""
    s = normalize(spec)
    s = dict(s, _v=RENDER_VER, _p=_presets_sig())
    raw = json.dumps(s, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:16]


def _wrap(draw, text, font, max_w):
    """글자 단위가 아니라 어절 단위로 접는다(한국어는 어절이 끊기면 못 읽는다)."""
    if not text:
        return []
    lines, cur = [], ""
    for word in text.split():
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


def _lum(c):
    """색의 밝기(0~255). 글자가 바탕에 묻히는지 판정하는 데만 쓴다."""
    return (c[0] * 299 + c[1] * 587 + c[2] * 114) / 1000


def _searchbar(d, cx, cy, color, w=560, h=64):
    """띠 가운데의 **둥근 검색창**. 실측 center_kind='검색창'인 채널이 쓴다.
    채널명을 그냥 글자로 찍는 것과 인상이 완전히 다르다(브랜드 시그니처)."""
    x0, x1 = cx - w // 2, cx + w // 2
    d.rounded_rectangle([x0, cy - h // 2, x1, cy + h // 2],
                        radius=h // 2, outline=color, width=4)
    _search(d, x1 - h // 2 - 6, cy, color, r=int(h * 0.26), th=5)


# 실측에서 나온 아이콘 종류 → 그리는 함수. 없는 이름이 와도 죽지 않게 get으로 받는다.
_ICONS = {"hamburger": _hamburger, "search": _search, "dots": _dots,
          "back": _back, "bookmark": _bookmark}

# 띠 가운데에 무엇이 오나(실측 center_kind). ★표기가 세 벌로 온다('없음'·'none'·null)
#   — 아이콘 표(ICON)처럼 여기서 한 값으로 모은다. 모르는 값은 '채널명'(지금까지 동작).
_CENTER = {"검색창": "search", "search": "search",
           "채널명": "name", "name": "name",
           "없음": "none", "none": "none", "": "none", None: "name"}


def _bar_layer(col, bar_h, fx, soft, top=True):
    """띠 한 장(RGBA, W x H)을 만들어 돌려준다.

    ★띠의 **끝부분 처리**를 정하는 유일한 자리다(0순위-B) — 위 띠와 아래 띠가
      각자 다르게 잘리면 언젠가 어긋난다. 두 곳 다 이 함수를 부른다.

    fx  solid    딱 잘린 띠(지금까지의 그림 — 기본값이라 회귀가 없다)
        grad     안쪽 끝에서 투명으로 선형으로 흘린다
        blur     경계를 가우시안으로 뭉갠다
        blurdark 뭉갠 경계 + 띠 자체를 어둡게(배경이 밝을 때 글자가 산다)
    soft 0~100   번지는 정도. 띠 높이에 대한 비율이라 띠를 키우면 같이 커진다.
    """
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if bar_h <= 0:
        return layer
    if fx == "blurdark":
        col = tuple([int(c * 0.55) for c in col[:3]] + [col[3] if len(col) > 3 else 255])
    d = ImageDraw.Draw(layer)
    y0, y1 = (0, bar_h - 1) if top else (H - bar_h, H - 1)
    d.rectangle([0, y0, W, y1], fill=col)
    if fx == "solid" or soft <= 0:
        return layer
    span = max(1, int(bar_h * soft / 100.0))
    # 알파만 손본다 — 색은 그대로 두고 '얼마나 비치나'만 바꾼다.
    a = layer.split()[3]
    if fx == "grad":
        da = ImageDraw.Draw(a)
        for i in range(span):
            v = int(255 * (1.0 - (i + 1) / float(span)))
            y = (bar_h - span + i) if top else (H - bar_h + span - 1 - i)
            da.line([(0, y), (W, y)], fill=v)
    else:                                   # blur / blurdark
        # ★그냥 블러하면 **화면 바깥쪽 끝까지 옅어진다**(위 띠의 맨 위가 반투명이 됨).
        #   바깥으로 늘려서 블러한 뒤 잘라내면 안쪽 경계만 뭉개진다.
        pad = span * 2
        big = Image.new("L", (W, H + pad * 2), 0)
        ImageDraw.Draw(big).rectangle(
            [0, (0 if top else H - bar_h + pad), W, (bar_h + pad - 1 if top else H + pad * 2 - 1)],
            fill=255)
        big = big.filter(ImageFilter.GaussianBlur(max(1, span // 2)))
        a = big.crop((0, pad, W, H + pad))
    layer.putalpha(a)
    return layer


def render(spec):
    """spec → 1080x1920 RGBA 이미지. 가운데는 투명(영상이 비쳐야 한다)."""
    s = normalize(spec)
    p = PRESETS[s["preset"]]
    # ★사장님이 화면에서 고른 값이 먼저, 없으면 실측(프리셋). 빈값="안 정했음" 규약.
    #   실측은 프레임 한 장에서 읽은 근사치라 마지막 한 뼘은 사람 손이어야 한다.
    bar_col = _rgb(s["bar_color"] or p["bar"])
    on_bar = _rgb(s["on_bar_color"] or p["on_bar"])

    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)

    bar_h = s["bar_h"]
    if bar_h > 0:
        im.alpha_composite(_bar_layer(bar_col, bar_h, s["bar_fx"], s["bar_soft"], True))
        cy = bar_h // 2
        if s["icons"]:
            # ★어느 아이콘인지도 채널마다 다르다(실측: 햄버거·돋보기·⋮·←·북마크).
            #   전에는 무조건 ☰+🔍이라 ⋮를 쓰는 채널이 딴 채널처럼 보였다.
            left = _ICONS.get(s["left_icon"] or p.get("left_icon", "hamburger"))
            right = _ICONS.get(s["right_icon"] or p.get("right_icon", "search"))
            if left:
                left(d, 92, cy, on_bar)
            if right:
                right(d, W - 96, cy, on_bar)
        # ★띠 가운데 구성은 채널마다 다르다(실측 center_kind: 검색창 2 / 채널명 13 / 없음 5).
        #   2026-08-25까지 이 값의 **소비처가 0곳**이라 전부 '채널명'으로만 그려졌다 —
        #   "틀이 다 똑같다 / 색만 바뀐 거냐"(사장님)의 직접 원인이었다. cap_* 사고와 같은 모양.
        center = _CENTER.get(s["center_kind"] or p.get("center_kind"), "name")
        if center == "search":
            _searchbar(d, W // 2, cy, on_bar, h=max(44, int(bar_h * 0.34)))
        elif center == "name" and s["channel"]:
            # 크기 0 = "안 정했음" → 기존 자동 규칙(띠 높이의 30%)을 그대로 쓴다.
            csize = s["ch_size"] or max(28, int(bar_h * 0.30))
            f = _font("bar", csize, s["ch_font"])
            cx = W * (s["ch_x"] / 100.0)
            # 글자 절반이 화면 밖으로 나가지 않게 중심을 안쪽으로 당긴다.
            half = _fg.text_px(f, s["channel"], csize) / 2
            cx = max(half + 20, min(W - half - 20, cx))
            _fg.draw_text(d, (cx, cy), s["channel"], f, on_bar, "mm", csize)

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
        im.alpha_composite(_bar_layer(bar_col, s["bottom_h"], s["bar_fx"], s["bar_soft"], False))

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
        block_h = 36 + len(lines) * line_h + (52 if meta else 0) + 24
        # ★제목 블록의 **바탕색·글자색도 채널마다 다르다**(실측 sub_bg 5가지·sub_text 9가지).
        #   2026-08-25까지 소비처 0곳이라 흰 바탕+검은 글자 한 벌로만 나갔다(center_kind와 같은 사고).
        #   사장님이 화면에서 직접 정한 head_bg가 있으면 그게 먼저다(사람 손 > 실측).
        touched = str(s["head_bg"]).upper() not in ("#FFFFFF", "#FFF")
        bg = _rgb(s["sub_bg_c"] or (s["head_bg"] if touched
                                    else (p.get("sub_bg") or s["head_bg"])))
        # 글자색: 실측 sub_text. 없으면 지금까지의 값. 바탕이 어두우면 검은 글자가 안 보이므로
        # 바탕 밝기로 갈라준다(지어내는 게 아니라 **안 보이는 걸 막는** 규칙 — box_color와 같다).
        dark_bg = _lum(bg) < 128
        # ★사장님이 직접 고른 제목색이 먼저다(사람 손 > 자동 — sub_text_c와 같은 규약).
        #   일부러 바탕과 같은 색을 쓸 수도 있으니 자동 대비 보정도 안 건다.
        if s["title_color"]:
            title_fill = _rgb(s["title_color"])
        else:
            title_fill = (245, 245, 245, 255) if dark_bg else (20, 20, 20, 255)
        _fallback_meta = (190, 190, 190, 255) if dark_bg else (120, 120, 120, 255)
        _meta_src = s["sub_text_c"] or p.get("sub_text")
        meta_fill = _rgb(_meta_src) if _meta_src else _fallback_meta
        # ★실측이 틀릴 수도 있다 — '요새난리'는 검은 바탕에 검은 글자로 읽혀 왔다(실측 1종).
        #   값을 고쳐 쓰진 않되(원본은 실측이 주인), **안 보이면 폴백**한다.
        #   단 **사장님이 직접 고른 색(sub_text_c)은 건드리지 않는다** — 사람 손이
        #   자동 보정보다 위다. 일부러 배경과 같은 색을 쓸 수도 있다(글자 숨기기).
        if not s["sub_text_c"] and abs(_lum(meta_fill) - _lum(bg)) < 60:
            meta_fill = _fallback_meta
        rule_fill = (210, 210, 210, 255) if dark_bg else (30, 30, 30, 255)
        d.rectangle([0, y, W, y + block_h - 1], fill=bg)
        ty = y + 36
        # 외곽선(2026-08-28): 두께>0일 때만. 색을 안 정했으면 **바탕**과 대비되는 쪽
        # (밝은 바탕→검정, 어두운 바탕→흰색). ★글자색 기준으로 뒤집으면 흰 바탕에서
        # 흰 테두리가 나와 바탕에 묻힌다(실측 — 안 보이는 값은 값이 아니다).
        ol_w = s["title_ol_w"]
        ol_c = None
        if ol_w > 0:
            ol_c = _rgb(s["title_ol_c"]) if s["title_ol_c"] else (
                (255, 255, 255, 255) if dark_bg else (0, 0, 0, 255))
        for ln in lines:
            _fg.draw_text(d, (tx, ty), ln, ft, title_fill, "ma", tsize,
                          stroke_width=ol_w if ol_c else 0, stroke_fill=ol_c)
            ty += line_h
        if meta:
            d.text((60, ty + 6), meta, font=fm, fill=meta_fill, anchor="la")
            ty += 46
            d.rectangle([60, ty + 8, W - 60, ty + 11], fill=rule_fill)

    # ★가림막은 **맨 마지막**에 얹는다 — 띠·글자보다 위여야 원본 자막을 확실히 덮는다.
    _draw_masks(im, s["masks"])
    return im


def _draw_masks(im, masks):
    """가림막을 그림 위에 얹는다. 모양은 _mask_shape_layer 한 곳에서 정한다.

    ★흐림(blur)은 여기서 **안 그린다** — 그림 한 장으로는 뒤 영상을 흐리게 못 한다.
      렌더가 마스크를 받아 처리한다. 흐림+어둡게(blurdark)는 '어둡게'만 여기서 얹는다.
    """
    for m in masks or []:
        # ★이모지·뱃지는 '덮는 것'이 아니라 '얹는 것'이라 흐림 분기를 안 탄다.
        #   자리·크기·회전 규칙은 도형과 똑같이 _mask_shape_layer 계열을 쓴다.
        if m.get("kind") == "emoji":
            _draw_emoji_mask(im, m)
            continue
        if m.get("kind") == "badge":
            _draw_badge_mask(im, m)
            continue
        if m["fx"] == "blur":
            continue
        if m["fx"] == "blurdark":
            # 진하기 100%를 그대로 검정으로 쓰면 완전히 까매져 흐림이 무의미해진다.
            rgb, alpha = (0, 0, 0), int(255 * m["op"] / 100.0 * 0.45)
        else:
            rgb, alpha = _rgb(m["color"])[:3], int(255 * m["op"] / 100.0)
        layer, x, y = _mask_shape_layer(m, rgb, alpha)
        im.alpha_composite(layer, (x, y))


def _mask_box(im, m):
    """masks의 %좌표를 픽셀 상자로. 자리 계산은 도형과 **같은 식**을 쓴다(0순위-B)."""
    W, H = im.size
    x = int(W * m["l"] / 100.0)
    y = int(H * m["t"] / 100.0)
    w = max(1, int(W * m["w"] / 100.0))
    h = max(1, int(H * m["h"] / 100.0))
    return x, y, w, h


def _draw_emoji_mask(im, m):
    """이모지 스티커 한 장. 컬러 이모지는 Noto Color Emoji로만 그려진다.

    ★109px 고정 비트맵이다(실측) — 다른 크기로 truetype()을 열면 예외가 난다.
      그래서 **109로 그린 뒤 상자에 맞춰 줄인다**. 폰트가 없거나 실패하면 아무것도
      안 그린다 — 두부(⊠)를 그리는 것보다 낫다(영문전용 폰트 사고와 같은 판단).
    """
    x, y, w, h = _mask_box(im, m)
    try:
        f = ImageFont.truetype(_EMOJI_FONT, _EMOJI_PX)
    except Exception:                      # noqa: BLE001 — 폰트가 없는 환경(개발 PC)
        return
    pad = _EMOJI_PX // 4
    n = max(1, len(m.get("ch") or ""))
    tile = Image.new("RGBA", (_EMOJI_PX * n + pad * 2, _EMOJI_PX + pad * 2), (0, 0, 0, 0))
    try:
        ImageDraw.Draw(tile).text((pad, pad), m["ch"], font=f, embedded_color=True)
    except Exception:                      # noqa: BLE001 — 지원 안 하는 글자
        return
    bb = tile.getbbox()
    if not bb:
        return
    tile = tile.crop(bb)
    tile = tile.resize((w, h), Image.LANCZOS)
    if m["rot"]:
        tile = tile.rotate(m["rot"], expand=True, resample=Image.BICUBIC)
        x -= (tile.width - w) // 2
        y -= (tile.height - h) // 2
    if m["op"] < 100:
        a = tile.getchannel("A").point(lambda v: int(v * m["op"] / 100.0))
        tile.putalpha(a)
    im.alpha_composite(tile, (max(0, x), max(0, y)))


def _draw_badge_mask(im, m):
    """글자 뱃지(SALE·NEW·인기…) 한 장 — 둥근 사각 + 가운데 글자.

    색은 가림막과 같은 `color`를 쓰고, 글자색은 배경 밝기로 정한다(어두우면 흰 글자).
    한 곳에서 정해야 화면 미리보기와 결과가 안 갈린다.
    """
    x, y, w, h = _mask_box(im, m)
    rgb = _rgb(m["color"])[:3]
    alpha = int(255 * m["op"] / 100.0)
    tile = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    r = int(min(w, h) * 0.28)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=rgb + (alpha,))
    # 밝은 바탕엔 검은 글자 — 흰 뱃지에 흰 글자가 되는 걸 막는다.
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    fg = (17, 17, 17, 255) if lum > 150 else (255, 255, 255, 255)
    txt = m.get("text") or ""
    size = max(10, int(h * 0.52))
    for _ in range(12):                    # 상자에 들어갈 때까지 줄인다
        f = _font("title", size)
        bb = d.textbbox((0, 0), txt, font=f)
        if bb[2] - bb[0] <= w * 0.84 or size <= 10:
            break
        size = int(size * 0.9)
    bb = d.textbbox((0, 0), txt, font=f)
    d.text(((w - (bb[2] - bb[0])) / 2 - bb[0], (h - (bb[3] - bb[1])) / 2 - bb[1]),
           txt, font=f, fill=fg)
    if m["rot"]:
        tile = tile.rotate(m["rot"], expand=True, resample=Image.BICUBIC)
        x -= (tile.width - w) // 2
        y -= (tile.height - h) // 2
    im.alpha_composite(tile, (max(0, x), max(0, y)))


def _mask_shape_layer(m, rgb, alpha, feather=None):
    """가림막 한 장을 자기 레이어에 그린다 — 모양·회전·가장자리 규칙의 **유일한 자리**.

    ★색 막(_draw_masks)과 흐림 마스크(render_blur_mask)가 **같은 함수**를 쓴다.
      두 벌로 그리면 "화면의 막"과 "실제로 흐려지는 자리"가 언젠가 어긋난다(0순위-B).
    돌려주는 값: (레이어, 붙일 좌표 x, y)
    """
    x, y = int(W * m["l"] / 100.0), int(H * m["t"] / 100.0)
    w, h = max(1, int(W * m["w"] / 100.0)), max(1, int(H * m["h"] / 100.0))
    # 가장자리 흐림 크기를 먼저 정한다 — 레이어에 그만큼 여백이 있어야 **바깥으로 번진다**.
    # ★여백 없이 흐리면 레이어 경계에서 잘려 안쪽만 흐려진다(테스트가 잡은 버그).
    if feather is None:
        blur_px = 0
        if m["fx"] == "fade":
            blur_px = max(2, int(min(w, h) * (0.12 + m["soft"] / 100.0 * 0.38)))
        elif m["soft"] > 0 and m["fx"] not in _MASK_BLUR_FX:
            blur_px = max(1, int(min(w, h) * m["soft"] / 100.0 * 0.30))
    else:
        blur_px = feather
    pad = blur_px * 3                                   # 가우시안이 사실상 사라지는 거리
    if m["rot"]:
        pad = max(pad, int(max(w, h) * 0.5))            # 회전하면 모서리가 잘린다
    layer = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    box = [pad, pad, pad + w - 1, pad + h - 1]
    fill = tuple(rgb) + (alpha,)
    if m["shape"] == "ellipse":
        ld.ellipse(box, fill=fill)
    elif m["shape"] == "pill":
        ld.rounded_rectangle(box, radius=h // 2, fill=fill)
    elif m["shape"] == "round":
        ld.rounded_rectangle(box, radius=max(6, min(w, h) // 8), fill=fill)
    else:
        ld.rectangle(box, fill=fill)
    # 가장자리 부드럽게(soft) / 그라데이션(fade) — 알파만 흐리면 색은 그대로다.
    if blur_px:
        layer.putalpha(layer.split()[3].filter(ImageFilter.GaussianBlur(blur_px)))
    if m["rot"]:
        layer = layer.rotate(m["rot"], resample=Image.BICUBIC, expand=False)
    return layer, x - pad, y - pad


def blur_sigma(masks):
    """흐림 세기(ffmpeg gblur sigma). 막마다 다르게 줄 수 없어 **가장 센 것**으로 맞춘다.

    ★'가장자리' 슬라이더(soft)가 흐림 계열에서는 세기를 겸한다 — 슬라이더를 하나 더
      만들면 안 쓰는 칸이 늘고, 흐림에선 어차피 가장자리 값이 놀고 있었다.
    """
    best = 0.0
    for m in masks or []:
        if m.get("fx") in _MASK_BLUR_FX:
            best = max(best, 25.0 + (m.get("soft", 0) / 100.0) * 55.0)
    return round(best, 1)


def render_blur_mask(spec):
    """흐림을 먹일 영역만 **알파에** 칠한 마스크(RGBA). 흐림 막이 없으면 None.

    렌더는 이 알파를 뽑아(alphaextract) 흐린 영상에 붙이고 원본 위에 얹는다.
    ★모양은 색 막과 같은 함수로 그린다 — 보이는 자리와 흐려지는 자리가 같아야 한다.
    """
    masks = [m for m in _norm_masks(spec.get("masks")) if m["fx"] in _MASK_BLUR_FX]
    if not masks:
        return None
    im = Image.new("RGBA", (W, H), (255, 255, 255, 0))
    for m in masks:
        # 경계가 칼로 자른 듯하면 흐림 티가 난다 — 늘 조금 부드럽게(soft와 별개).
        w = max(1, int(W * m["w"] / 100.0))
        h = max(1, int(H * m["h"] / 100.0))
        feather = max(4, int(min(w, h) * 0.06))
        layer, x, y = _mask_shape_layer(m, (255, 255, 255), 255, feather=feather)
        im.alpha_composite(layer, (x, y))
    return im


def blur_mask_path(spec):
    """흐림 마스크 파일 자리. 틀 그림과 **같은 규약**(cache_key + 접미사)."""
    return (pathlib.Path(__file__).resolve().parent / "data" / "frame_cache"
            / f"{cache_key(spec)}_blurmask.png")


def render_blur_mask_to(spec, out_path=None):
    """마스크를 파일로 저장하고 경로를 돌려준다. 흐림 막이 없으면 None."""
    out_path = pathlib.Path(out_path or blur_mask_path(spec))
    if out_path.exists():
        return out_path
    im = render_blur_mask(spec)
    if im is None:
        return None
    out_path.parent.mkdir(parents=True, exist_ok=True)
    im.save(out_path, "PNG")
    return out_path


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
