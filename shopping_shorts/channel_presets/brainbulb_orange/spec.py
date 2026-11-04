# -*- coding: utf-8 -*-
"""brainbulb_orange — 뇌전구(brainbulb) 규격 그대로 + 우리 겉모습(사장님 2026-11-04, 관제 322).

★원본 `brainbulb` 는 손대지 않는다. 여기는 원본 값을 전부 물려받고(`import *`) **바꾸는 것만** 덮어쓴다 —
  같은 값을 두 벌 적지 않는다(0순위-B). 원본 규격이 고쳐지면 여기도 같이 따라간다.

바꾸는 것(지금까지 볼케이노 완성본에 사후로 입히던 '다듬기' 를 처음부터):
  ① 글꼴: 에스코어 드림·SB 어그로·잘난체 → 페이퍼로지(OFL, fonts/LICENSE.txt)
     크기 = 다듬기(볼케이노/다듬기_오렌지_페이퍼로지_동물밈.py match_size)가 원래 글꼴과 글자 폭이 같아지게 잰 값
     (11-04 부모차보험 편 sub_orange_paperlogy.ass 실측: HL1 136·HL2 148·CARD 50·WHITE 94·PINK 94·YELLOW 92·RED 98·ORANGE 94)
  ② 노랑(YELLOW 자막·HL2 제목 아랫줄) → 오렌지 #F76C0D(&H000D6CF7). 스타일 이름은 그대로라 대본의 color 값은 안 바뀐다
"""
import os

from shopping_shorts.channel_presets.brainbulb.spec import *          # noqa: F401,F403 — 원본 규격 전부
from shopping_shorts.channel_presets.brainbulb.spec import STYLE_BLOCK as _BASE_STYLE_BLOCK  # noqa: F401

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

ORANGE_ASS = "&H000D6CF7"          # #F76C0D (다듬기 ORANGE 와 같은 값)

STYLE_BLOCK = (
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: HL1,Paperlogy 9 Black,136,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    f"Style: HL2,Paperlogy 9 Black,148,{ORANGE_ASS},{ORANGE_ASS},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: CARD,Paperlogy 7 Bold,50,&H00000000,&H00000000,&H00FDFDFD,&H00FDFDFD,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n"
    "Style: WHITE,Paperlogy 8 ExtraBold,94,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: PINK,Paperlogy 7 Bold,94,&H00FEDEFE,&H00FEDEFE,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    f"Style: YELLOW,Paperlogy 7 Bold,92,{ORANGE_ASS},{ORANGE_ASS},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: RED,Paperlogy 9 Black,98,&H000000FF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    f"Style: ORANGE,Paperlogy 7 Bold,94,{ORANGE_ASS},{ORANGE_ASS},&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
)

# 스타일 → (ASS 폰트 이름, 파일, 스타일 기본 크기) — 위 STYLE_BLOCK 과 짝(크기·글꼴이 같아야 줄배치 측정이 맞다)
STYLE_FONT = {
    "HL1": ("Paperlogy 9 Black", "Paperlogy-9Black.ttf", 136),
    "HL2": ("Paperlogy 9 Black", "Paperlogy-9Black.ttf", 148),
    "CARD": ("Paperlogy 7 Bold", "Paperlogy-7Bold.ttf", 50),
    "WHITE": ("Paperlogy 8 ExtraBold", "Paperlogy-8ExtraBold.ttf", 94),
    "PINK": ("Paperlogy 7 Bold", "Paperlogy-7Bold.ttf", 94),
    "YELLOW": ("Paperlogy 7 Bold", "Paperlogy-7Bold.ttf", 92),
    "RED": ("Paperlogy 9 Black", "Paperlogy-9Black.ttf", 98),
    "ORANGE": ("Paperlogy 7 Bold", "Paperlogy-7Bold.ttf", 94),
}
