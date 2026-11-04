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

# ── 지금 볼케이노 형식(15컷·긴 문장·여러 줄)으로 — 사장님 11-04 "지금처럼 하는걸로" ─────────────
# 원본 brainbulb 는 9월 형식(22~32컷·한 컷 2줄)이다. 우리가 확정하는 대본은 14~15컷에 컷당 2~4줄이라
# 원본 규칙으로 돌리면 컷 수에서 반려된다. 값의 근거는 11-03~04 볼케이노 실물 6편(주식다음날입금·부모차보험·
# 천원중국빵·AI대화매각·도서관책테이프·서울마라톤)의 timing.json·sub.ass.
POLICY_MAX_LINES = 4               # 실물 최대 3줄(볼케이노) + 다듬기 줄나눔고침에서 4줄까지 씀(부모차보험 8컷·도서관 없음)
POLICY_MIN_CUTS, POLICY_MAX_CUTS = 12, 18      # 실물 14~15컷
POLICY_CARD_LONG_WARN = 44         # 실물 카드 32~39자(도서관 39자). 44 는 원본의 물리 한도 값 그대로
# 켜는 검사 — 원본 24개 중 지금 형식과 맞는 것만. 빠진 것과 이유:
#   cut_count 범위만 바꿔 유지 · slot_count(9~11, 실물 13~14) · punch(PUNCH 1개, 실물은 밈 컷도 PUNCH) ·
#   nonwhite_run(실물 13노랑·14오렌지·15빨강 연속) · h2_abstract(실물 h2 '테이프 붙이면 안 됨' 숫자 없음) ·
#   ending_declared/ending_mix(대본에 ending_style 칸 없음 — 사장님이 대본을 직접 확정) · copy(기사 사실을 그대로 옮기는 형식) ·
#   words(한 줄 어절 수 — 줄나눔이 화면 폭으로 잰다) · meme_ratio·speaker_voice·line1_end·example_copy(9월 형식 관행)
LINT_RULES = ["title_punct", "comma", "enum", "formal", "card", "layout", "cut_count", "slot_seq", "card_img",
              "first_open", "last_closed"]

# ── 밈 = 동물 영상(사장님 다듬기 방식) — frames 가 밈 칸을 검은 슬롯으로 두고 render 가 영상을 얹는다 ─────
MEME_KIND = "video"


def pick_meme_videos(emotions, seed):
    """밈 칸 감정들 → [{src, start, key, what}] (memes.pick). 주인 = brainbulb_orange/memes.py"""
    from . import memes
    return memes.pick(emotions, seed)

# ── 목소리 = 타입캐스트 '제롬'(Jerome, 젊은 남성) 한 명 — 사장님 11-04 "기본값을 바꿀건데 … 타입캐스트 제롬" ─────
#   ID 는 타입캐스트 /v2/voices 목록(631개)에서 voice_name 'Jerome' 으로 찾음. ssfm-v30 감정 지원(angry·happy·normal·sad·tonedown·toneup·whisper)
#   감정표(POLICY_EMOTION — 전부 화남, 펀치 강하게)는 원본 그대로 물려받는다.
VOICE_JEROME = "tc_65a0e1d1d7012c484fe4bfc7"
POLICY_VOICES = {"NARR": VOICE_JEROME, "CHAR": VOICE_JEROME, "PUNCH": VOICE_JEROME}

# ── 줄나눔 = 확정 대본의 줄을 그대로(사장님이 컨펌한 줄나눔) — 화면 폭 안일 때만. 없으면 엔진이 나눈다 ─────
#   11-04 시험판: 엔진이 줄 수를 줄이려 «미국 의회도서관도 일반 / 테이프는…» 처럼 낱말을 어색하게 끊었다.
POLICY_KEEP_SCRIPT_LINES = True
POLICY_TEMPO = 1.2                 # 말 빠르기(사장님 11-04 "속도는 1.2"). 원본 뇌전구 엔진 기본은 1.3
