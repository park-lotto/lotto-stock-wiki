# -*- coding: utf-8 -*-
"""뇌전구 규격 상수 — 8편 실측(2026-09-12)에서 그대로 옮긴 값.

★여기 값은 "우리가 정한 것"이 아니라 "볼케이노 산출물 8편에서 바이트/좌표 단위로 같았던 것"이다.
  바꾸려면 근거(실측)가 있어야 한다. 우리 정책으로 정한 값은 `POLICY_` 접두로 갈라 둔다.
"""
import os

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

CANVAS_W, CANVAS_H = 1080, 1920
SLOT_W, SLOT_H = 1028, 786
SLOT_X, SLOT_Y = 26, 469           # 실제 mp4 프레임 실측: 열 26~1053, 행 469~1254 (제목 아래·자막 위). 카드 띠(469~)가 그 위에 얹힌다

# ── 이미지 생성 (볼케이노 실행기 cardnews_images.generate_gpt_image2 와 같은 호출) ─────
IMAGE_API = "https://api.evolink.ai"
IMAGE_MODEL = "gpt-image-2"
IMAGE_SIZE = "3:2"                 # 지원: auto/1:1/16:9/9:16/3:2/2:3. 슬롯 1028×786(1.31)에 가장 가까운 3:2 → 가운데 cover 크롭
IMAGE_QUALITY = "medium"           # low $0.0037 / medium $0.032 / high $0.127 (실행기 주석 실측 단가)
# 접두 — 로케일만 박고 장면 묘사는 작성자에게 맡긴다.
# ★"Documentary style photo"를 앞에 고정으로 붙이던 것을 뺐다(2026-09-13 실측): 편 A만 우연히
#   10슬롯 전부 그 문구였고, 편 B는 8종·편 C는 9종으로 **슬롯마다 첫 어구가 다르다**
#   (`Photorealistic wide shot of a dusty empty lot…`). 한 편만 보고 "고정 접두"로 역산했던 오독이다.
# ★로케일을 "한국"으로 박지 마라 — 컷마다 나라가 다를 수 있다.
#   실측 2026-09-13(v7 슬롯4): 케냐 슬럼가 계단 장면인데 접두가 "In South Korea"라
#   **한국 지하철 계단에서 파란 조끼 자원봉사자들이 휠체어를 드는 그림**이 나왔다
#   (사장님 "전체 맥락 없이 만든거야?"). 슬롯마다 작성자가 장소를 적고, 안 적으면 이 값을 쓴다.
IMAGE_LOCALE_DEFAULT = "In South Korea, Korean people, Korean-language signage and hangul text"
IMAGE_PROMPT_PREFIX = IMAGE_LOCALE_DEFAULT + ", "     # 옛 이름 유지(시험·호출부 호환)

# 접미 — 실측 볼케이노 16개 그대로. 우리는 4개뿐이라 **가짜 구독자 수·그래프가 그려졌다**
# (2026-09-13: 없는 채널명 밑에 '1,000,000', '글로벌 경기침체' 꺾은선). 굵은 것이 그 방어선이다.
IMAGE_PROMPT_SUFFIX = (
    ", documentary photograph, photorealistic, real people, natural lighting, shot on a camera"
    ", not an illustration, not a cartoon, not a drawing, not anime, not 3d render"
    ", all signage and screens are out of focus or too small to read"
    ", no legible words, no legible numbers or currency amounts"
    ", no real brand names, no real company or product names, no logos, no watermarks"
)

# ── 실제 사진 조달 (photos.py) — 사장님 2026-09-13 ────────────────────────────────
# 실측: 참조 이미지를 지키는 모델은 qwen-image-edit 하나뿐. gpt-image-2·gemini 이미지는 참조를 무시한다.
VARIANT_MODEL = "qwen-image-edit"      # ★size 파라미터를 주면 400. image_url 필드에 data URI.
VARIANT_PROMPT = ("같은 인물의 옷차림·체형·머리모양과 같은 장소·구도를 그대로 유지한 채 "
                  "다큐멘터리 사진으로 다시 그려라. 얼굴은 특정 실존 인물과 닮지 않게 하되 "
                  "같은 연령대·성별의 한국인으로 자연스럽게. 글자·워터마크 없이.")
PHOTO_KINDS = ("real", "variant", "scene", "gen")   # 실물 / 변형 / 장소사물검색 / 생성
# scene: 인물이 아니라 장소·사물이 주인공인 컷을 검색해 쓴다(KTX 승강장·휠체어 경사로).
#   ★얼굴 검사를 하지 않는다 — 사람이 없는 게 정상이다. 대신 검색어에 사람을 넣지 않게 지시문이 막는다
#   (실측 2026-09-13: "노트북 화면 보는 사람"은 스톡사진 Magnific·123RF가 와서 광고처럼 보였다).
POLICY_PHOTO_TEXT_MAX = 0.03               # 글자 면적 상한 — 실측: 일반 사진 0.2~0.5% / 홈쇼핑 캡처 14.3%
MEME_FIT = "height"                # 밈은 슬롯 높이에 맞춰 가운데(실측 밈 폭 870 ≈ 231×218 → 786 높이)

# ── ASS 헤더·스타일 블록 (5편 MD5 동일 · 전편 3편 바이트 동일 = 8/8) ──────────────
ASS_HEADER = (
    "[Script Info]\n"
    "ScriptType: v4.00+\n"
    "PlayResX: 1080\n"
    "PlayResY: 1920\n"
    "WrapStyle: 2\n"
    "ScaledBorderAndShadow: yes\n"
    "YCbCr Matrix: TV.709\n"
)
STYLE_BLOCK = (
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: HL1,SB 어그로 Bold,123,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: HL2,SB 어그로 Bold,134,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: CARD,에스코어 드림 6 Bold,54,&H00000000,&H00000000,&H00FDFDFD,&H00FDFDFD,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n"
    "Style: WHITE,에스코어 드림 7 ExtraBold,102,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: PINK,에스코어 드림 6 Bold,102,&H00FEDEFE,&H00FEDEFE,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: YELLOW,에스코어 드림 6 Bold,99,&H0000FFFF,&H0000FFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: RED,여기어때 잘난체 OTF,73,&H000000FF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
    "Style: ORANGE,에스코어 드림 6 Bold,102,&H000D6CF7,&H000D6CF7,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,4,0,7,0,0,0,1\n"
)
EVENTS_FORMAT = "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"

# 스타일 → (ASS 폰트 이름, 파일, 스타일 기본 크기)
STYLE_FONT = {
    "HL1": ("SB 어그로 Bold", "SBAggroB.ttf", 123),
    "HL2": ("SB 어그로 Bold", "SBAggroB.ttf", 134),
    "CARD": ("에스코어 드림 6 Bold", "S-CoreDream-6Bold.ttf", 54),
    "WHITE": ("에스코어 드림 7 ExtraBold", "S-CoreDream-7ExtraBold.ttf", 102),
    "PINK": ("에스코어 드림 6 Bold", "S-CoreDream-6Bold.ttf", 102),
    "YELLOW": ("에스코어 드림 6 Bold", "S-CoreDream-6Bold.ttf", 99),
    "RED": ("여기어때 잘난체 OTF", "yg-jalnan.ttf", 73),
    "ORANGE": ("에스코어 드림 6 Bold", "S-CoreDream-6Bold.ttf", 102),
}

# ── 본문 자막 좌표 (스타일별 y가 다르다 — 8편 문서 §2-③) ─────────────────────────
BODY_X = 636                       # \an8 = 위-가운데 앵커
BODY_Y = {"WHITE": 1271, "ORANGE": 1271, "YELLOW": 1276, "PINK": 1269, "RED": 1286}
LINE_GAP = 87                      # 2줄째 = 첫줄 + 87
ENTRANCE = r"\fscx108\fscy108\t(0,90,\fscx100\fscy100)"
ENTRANCE_SCALE = 1.08
BODY_LAYER = 4
# 기하 한도: 우측 여유 = 1080-636 = 444 → 100% 888px, 108% 등장 순간 822px (통과 최대 808 실측)
BODY_MAX_INK_100 = 2 * (CANVAS_W - BODY_X)                       # 888
BODY_MAX_INK_ENTRANCE = int(BODY_MAX_INK_100 / ENTRANCE_SCALE)   # 822

# ── 제목 (h1 흰 윗줄 / h2 노란 아랫줄) ────────────────────────────────────────────
HL_POS = {"HL1": (530, 215), "HL2": (530, 330)}
HL_LAYER = 3
TITLE_TARGET_INK = 1000            # 비례 축소 목표. 축소된 제목 실측 잉크 993~1002px. 잉크 임계 방식은 어떤 값으로도 4건이 어긋남 → 비례식(ass_gen._fit_prop)

# ── 오프닝 카드 ───────────────────────────────────────────────────────────────────
CARD_BAND_GRAY = ("&H3B3B3B&", 469, 273)    # (색, y, 높이)
CARD_BAND_WHITE = ("&HFDFDFD&", 565, 137)
CARD_TEXT_POS = (546, 633)
CARD_LAYER_BANDS = (0, 1)
CARD_LAYER_TEXT = 2
CARD_FS_LONG, CARD_FS_SHORT = 46, 54
POLICY_CARD_LONG_MIN_CHARS = 26    # 우리 정책: 26자 이상이면 46 (5편 전부 26~33자→46, 전편 짧은 카드→54. 경계 미확정)
POLICY_CARD_MAX_CHARS = 44         # 실측 최대 33자(fs46 → 871px). Gemini가 52자를 써 띠를 넘쳤고(2026-09-12) 36자 규칙엔 4회 연속 41자로 걸림 → 44자까지 받고 크기로 흡수
POLICY_CARD_LONG_WARN = 36         # ★반려선. 실물 5편은 26·26·27·28·33자(최대 33) — 36이면 5편 다 통과하고
                                   #   기사 문장을 옮긴 40·43자는 막힌다(실측 2026-09-13). 44는 띠가 버티는 물리 한도일 뿐이다.
POLICY_CARD_MIN_FS = 36            # 44자 안이면 카드 글자를 폭(1040px)에 맞춰 46→36까지 줄인다(우리 정책. 볼케이노는 46/54뿐)

# ── 타이밍 ────────────────────────────────────────────────────────────────────────
TAIL_SEC = 0.1                     # total = 카드 + Σ컷 + 0.1 (5/5 실측)

# ── 대본 어휘 ─────────────────────────────────────────────────────────────────────
COLORS = ("WHITE", "YELLOW", "RED", "ORANGE", "PINK")
ROLES = ("NARR", "CHAR", "PUNCH")
EMOTIONS = ("경악/충격", "기타", "당황", "만족/엄지척", "무표정/멍", "분노", "비웃음/조롱", "슬픔/울음", "의심/떨떠름", "피곤/지침")
# 감정 → pepe/fm 파일 (5편 실측. 경악은 013이 4편, 025가 1편)
MEME_FILE = {"경악/충격": "013", "당황": "027", "분노": "042", "비웃음/조롱": "000",
             "무표정/멍": "008", "의심/떨떠름": "016", "슬픔/울음": "005"}

# ── 효과음 ────────────────────────────────────────────────────────────────────────
# 5편 sfx_plan이 접미사까지 완전 동일 (최장 보르네오 32컷). "12주기 반복"이 아니다 — 13번째가 r3_click.
SFX_SEQ32 = [
    "pop4_3", "click_4", "boing_3", "ding_5", "pop4_4", "r3_click_7", "hit_4", "r3_ding_6",
    "pop4_5", "x_click_5", "r3_hit_3", "x_ding_4", "pop4_0", "r3_click_2", "boing_3", "ding_5",
    "pop4_1", "x_click_1", "hit_4", "r3_ding_6", "pop4_2", "click_3", "r3_hit_3", "x_ding_4",
    "pop4_3", "r3_click_6", "boing_3", "ding_5", "pop4_4", "x_click_4", "hit_4", "r3_ding_6",
]
# 구조: 4칸 틀 × 계열별 주기 (32컷 전부 공식 일치). 33컷 이상은 이 공식으로 늘린다.
SFX_FAMILY = {
    0: ["pop4"],
    1: ["click", "r3_click", "x_click", "r3_click", "x_click"],
    2: ["boing", "hit", "r3_hit"],
    3: ["ding", "r3_ding", "x_ding"],
}
SFX_GAIN_DEFAULT = 1.0
SFX_GAIN_RED = 1.25                # RED 컷 (5편 컷 번호 정확히 일치)
SFX_BED_DB = -8.0                  # 베드 게인. 실측: 볼케이노 sfx_bed 평균 −48.7 vs 나레 −33.0 = 16dB 아래. 우리 팩 원음은 나레보다 9dB 아래라 −8 → 약 17dB 아래. (−22는 31dB 아래 = 안 들림, 사장님 지적)
MIX_LOUDNORM = "loudnorm=I=-16:TP=-1.5:LRA=11"   # 볼케이노 최종 믹스 평균 −19.5dB(나레 원음 −33에서 올림) — 최종을 정규화한다

# ── 우리 정책 (미합의 4건 + 판정 임계. 실측이 생기면 바꾼다 — 설계 논쟁 §5) ────────
POLICY_MAX_WORDS_PER_LINE = 5      # 서버 "어절이 너무 많습니다" 반려. 실측 통과 최대 4어절
POLICY_LINE_SPLIT_PX = 710         # 1줄↔2줄 경계(숫자·영문을 한글 폭으로 센 잉크 폭). 실측: 1줄 최대 703 / 2줄 최소 726 → 그 사이
POLICY_COPY_MIN_CHARS = 14         # 원문에 이만큼 그대로 들어 있으면 "다시 쓴 것이 아니다". 서버는 10자('전극침이 나갈 줄 몰랐다')를 통과시켰다
POLICY_MAX_REWRITES = 6            # 반려 → 재작성 최대 횟수.
                                   # ★3이던 것을 6으로(2026-09-13): 내용 규칙·컷수·카드길이를 더하니
                                   #   한 번에 4건이 걸려 예산 안에 다 못 고치고 반려된 채로 끝났다.
                                   #   볼케이노 자기 로그도 대본 재시도가 보인다 — 고칠 기회를 주는 쪽이 맞다.
POLICY_MAX_TTS_CHARS = 6000        # 잡당 TTS 누적 글자 상한 (비용)
POLICY_SILENCE_SEC = 0.7           # 나레 트랙 안 무음 임계 (꼬리 0.1 제외). 0.35는 문장 안 말 쉼(실측 0.41s '그런데 수하물 / 내리는 사이')을 누락으로 오판
POLICY_SILENCE_DB = -40.0
POLICY_DURATION_TOL = 0.05         # mp4 길이 vs total 허용 오차

# ── 역할별 성우 (볼케이노 5편 f0 실측: 나레 ~220Hz 여성 / CHAR ~265Hz 더 높은 여성 / PUNCH 90~170Hz 낮은 남성 = 3명) ──
# 사장님 지정(2026-09-12): 박창수 · 용식이 · 발키리 (저장소 Typecast 프리셋 add_typecast_presets.py)
POLICY_VOICES = {                  # 사장님 확정 2026-09-12: "박창수 그대로, 용식이가 마지막 펀치 화남 강하게, 발키리 화남으로 페페"
    "NARR": "tc_6059dad0b83880769a50502f",     # 박창수 — 나레·카드
    "CHAR": "tc_60478557f12456064b353409",     # 발키리 — 페페 대사 컷, 화남
    "PUNCH": "tc_5feb2085cca1a479e73bac37",    # 용식이 — 마지막 펀치, 화남 강하게
}
# ── 훅/본문 다르게 (숏템메이커 장면꾸미기 "속삭임을 훅에만" 원리, 사장님 2026-09-12) ─────────
# Typecast ssfm-v30 감정 프리셋: angry / happy / normal / sad / tonedown / toneup / whisper
POLICY_HOOK_CUTS = 0               # 훅 특별 처리 없음 (사장님 2026-09-12: "위스퍼는 절대 쓰지 말고")
POLICY_EMOTION_ALL = None          # 전 컷 공통 감정. None이면 아래 역할표 (v006은 ("angry",1.2) 전 컷)
POLICY_EMOTION = {                 # 역할 → (감정, 강도 0~2). 사장님 확정: 전부 화남, 펀치는 강하게
    "HOOK": None,
    "NARR": ("angry", 1.2),
    "CHAR": ("angry", 1.2),
    "PUNCH": ("angry", 2.0),
}
MEME_TO_TC_EMOTION = {             # 대사(CHAR) 컷은 밈 감정을 따라간다 (EMOTION_ALL이 None일 때만)
    "경악/충격": "toneup", "당황": "toneup", "분노": "angry", "슬픔/울음": "sad",
    "비웃음/조롱": "happy", "만족/엄지척": "happy", "무표정/멍": "tonedown", "의심/떨떠름": "tonedown",
    "피곤/지침": "tonedown", "기타": None,
}
FORBIDDEN_EMOTIONS = ("whisper",)   # 어떤 경로로도 안 나간다 (사장님 지시). voice.plan_emotion이 막는다

# 컷 수 — 실측 실물 5편 22·25·28·28·32. 22컷 미만이면 35초가 안 나온다(2026-09-13 17컷 사고)
POLICY_MIN_CUTS, POLICY_MAX_CUTS = 22, 32

# 지시문에 예시로 든 실물 문장 — 그대로 베끼면 반려한다(r_example_copy)
PROMPT_EXAMPLES = (
    # ★카드 문장만 넣는다. 나레·PUNCH 예시(«침묵은 딱 2주였다» 등)는 고유명사가 없어
    #   "누구 얘기인지" 가릴 수 없다 — 넣었더니 실물 5편이 자기 문장으로 반려됐다(골든 회귀가 잡음).
    "케냐 봉사 갔다가 봉사 받고 왔다는 백만 유튜버",
    "제주에 카페 열었다 접은 배우 이동건 때문에 옆집이 난리났다",
    "중학생들한테 테이저건 자랑하다 진짜로 쏴버린 경찰",
    "비행기 한 시간 세운 박수홍이 2주 만에 나타난 곳",
    "서울 3배 땅을 태우고 동남아 하늘을 삼킨 산불",
)

# 예시에 든 고유명사 — 이 낱말이 기사에 없는데 예시 문장을 쓰면 '남의 것을 베낀 것'이다
PROMPT_EXAMPLE_NAMES = ("케냐", "박위", "이동건", "제주", "박수홍", "보르네오", "테이저건")

# 지시문 예시가 어느 편에서 왔나 — 기사에 이 낱말이 있으면 그 줄을 감춘다(_hide_same_story).
# 같은 소재의 예시를 보여주면 구조가 아니라 답을 베낀다(실측 2026-09-13 박위 카드 글자까지 동일).
PROMPT_EXAMPLE_TOPICS = ("케냐", "박위", "이동건", "박수홍", "보르네오", "테이저건", "원주민")

# 이미지 슬롯 개수 상한 — 실물 5편 9·9·10·11·11개. 많을수록 이미지 생성비가 든다
# (실측 2026-09-13: 판정이 없어 14개짜리가 통과했다). 12까지 받고 그 위를 막는다.
POLICY_MAX_SLOTS = 12

# 모서리 워터마크 의심 문턱(scene 검색에만 건다) — 실측 2026-09-13
#   뉴스천지 0.567 · 뉴스1 0.365 · 자막캡처 0.675 / 깨끗한 사진 0.000~0.225
#   한계: MBC 로고(0.197)는 못 잡고, 사진 속 경고표지판(0.327)은 오탐한다.
POLICY_SCENE_MARK_MAX = 0.30

# 화면·계기판 주문 감지 — 모델이 **없는 채널명과 숫자를 지어내 화면에 박는다**.
# 실측 2026-09-13: 접미 금지어 16개를 다 넣고도 «computer screen showing a social media
# profile with a downward trend line»이 가짜 그래프를 그렸다. 지시문만으로는 안 막힌다.
#
# ★2026-09-14 대폭 축소. 왜:
#   낱말을 넓게 잡았더니(numbers·percentage·counter·statistics·index·stock…)
#   **돈 이야기를 아예 그릴 수 없게 됐다.** 최민식 편은 처음부터 끝까지 돈 얘기다 —
#   150만원·30퍼센트·45만원·105만원. 그런데 슬롯 9·11이 `percentage`/`numbers` 에 걸려
#   프롬프트가 통째로 버려지고 「빈 사무실」이 세 컷이나 들어갔다(실측: 1초·13초·30초).
#   자막은 «수수료를 30퍼센트 떼어 갔다» 인데 화면은 사람 없는 현대식 오피스였다.
#
#   볼케이노는 이 자리에서 **실사가 아닌 것을 주문하는 낱말만** 막는다(서버 `prompt_rules` 원문:
#   "그림·만화·애니·웹툰·일러스트·3D·컴퓨터그래픽을 요청하는 영어 낱말이 들어가면 반려").
#   numbers·percentage 따위는 목록에 없다. **지어낸 기록은 낱말이 아니라 검수가 잡는다**
#   — 우리도 `photocheck` 가 그림을 실제로 보고 판정한다(사장님 "두더지 아니야?"의 답).
#
#   그래서 남긴 것은 «화면에 수치를 띄워 달라»는 **직접 주문**뿐이다. 이것만으로도
#   위 실사고 2건(가짜 구독자 수·가짜 주가지수)은 걸린다 — 둘 다 screen/sign 주문이었다.
PROMPT_SCREEN_WORDS = ("computer screen", "smartphone screen", "phone screen", "monitor showing",
                       "social media profile", "subscriber count", "trend line", "graph showing",
                       "chart showing", "youtube channel", "dashboard", "analytics",
                       "digital sign", "digital display", "electronic sign", "led display",
                       "display showing", "screen showing", "sign showing")

# 실사가 아닌 것을 주문하는 낱말 — 볼케이노가 실제로 막는 유일한 범주.
PROMPT_NONPHOTO_WORDS = ("illustration", "cartoon", "anime", "webtoon", "drawing", "3d render",
                         "digital art", "painting", "sketch", "vector art", "cgi", "render of")

# 최후의 폴백 — 원래 프롬프트를 못 살릴 때만(검수 반려 + 원문 유실). 평소엔 쓰이지 않는다.
PROMPT_REGEN_FALLBACK = ("A quiet empty room with an unused desk and a chair turned away from the window, "
                         "late afternoon light, nobody present")

# 자막이 사람의 행동을 말하는 표지 — 이런 컷은 scene(장소 검색)으로 못 채운다.
# 실측 2026-09-13: «사람들 도움을 받음»에 «좁은 골목길»로 검색해 빈 밤골목이 왔다.
PROMPT_PERSON_WORDS = ("사람", "사람들", "받았", "받음", "받는", "도왔", "도움", "들어 올", "들어올",
                       "부축", "찾았", "찾아", "만났", "만나", "안았", "업고", "밀어", "탔다", "타고",
                       "함께", "같이", "둘러", "모였", "모여")

# ── 사진 검수 (photocheck.py) — 볼케이노 photo_check 실측 문턱 ─────────────────
# 편 A는 10장 중 1장만 모델에게 보냈고 편 B·C는 0장이다. 기계 지표로 먼저 거르고
# 의심스러운 것만 보낸다(모델 호출은 돈이 든다).
PHOTOCHECK_FLAT_MAX = 0.55      # 평평한 면 비율 상한 — 넘으면 '평평한 면이 넓다'(일러스트 징후)
PHOTOCHECK_GRAD_MIN = 1.0       # 가장자리 세기 중앙값 하한 — 밑돌면 잔질감(모공·직물)이 없다

# ── ★사진 검수 기준표 — 기준이 사는 **유일한 자리** (2026-09-16 사장님 지시) ──────────
#
# 왜 표로 뺐나: 기준이 photocheck.py 의 긴 프롬프트 문자열 안에 묻혀 있어서
#   "무엇을 어떤 기준으로 봤는지"가 안 보였다. 항목을 늘릴 때 프롬프트만 고치고
#   판정을 안 붙이는 사고가 반복됐다(핸드오프 "지시문에 적고 판정을 안 붙였다 — 일곱 번").
#   → 여기 한 줄을 더하면 **묻는 말·판정·화면 표시가 같이 따라온다**(0순위-B).
#
# blocking  True  = 어긋나면 그 슬롯을 반려한다(자동 재시도 대상)
#           False = 재지 않고 기록만 한다(나중에 문턱을 정할 근거)
# field     모델이 JSON 으로 돌려줄 키. blocking 항목은 반드시 이 키를 본다.
# bad       그 값이 '어긋남'인지 판정하는 함수 — ★판정이 여기 붙어 있어야 규칙만 늘지 않는다
#
PHOTO_RULES = (
    {"key": "visual_kind", "label": "사진인가", "blocking": True,
     "field": "visual_kind",
     "bad": lambda v, _d: str(v).lower() != "photo",
     "ask": "[사진인가 그림인가]\n"
            "  photo        실제 카메라로 찍은 것처럼 보인다(피부 모공·직물 주름·머리카락 질감·자연광)\n"
            "  illustration 윤곽선·평면 색면·셀 셰이딩·3D 렌더·과장된 비율이 보인다"},

    {"key": "fabricated", "label": "지어낸 기록", "blocking": True,
     "field": "fabricated_text",
     "bad": lambda v, _d: bool([t for t in (v or []) if str(t).strip()]),
     "ask": "[**지어낸 기록**이 있나]\n"
            "  ★묻는 것은 '글자가 있나'가 아니라 '**없는 사실을 진짜처럼 보여주나**'다.\n"
            "  적어야 할 것 — 화면·간판·표·라벨이 **수치나 이름을 내세우는** 경우:\n"
            "    없는 채널 이름 밑의 구독자 수 · 가짜 주가지수·환율 · 지어낸 뉴스 헤드라인\n"
            "    실존 회사 간판 · 읽히는 가격표·계기판 · **지어낸 유통기한·성분표 수치**\n"
            "  적지 마라 — 실제 사진에 자연히 있는 글자:\n"
            "    옷·가방의 브랜드(NIKE·YALE) · 지명 표지판 · 흐릿한 배경 글자 · 번호판\n"
            "  판단 기준: 그 글자가 **틀린 정보를 사실처럼 전달하나**. 아니면 적지 마라."},

    {"key": "subtitle", "label": "자막과 맞나", "blocking": True,
     "field": "matches_subtitle",
     "bad": lambda v, _d: v is False,
     "ask": "[자막과 맞나]  ★여기서 느슨하면 검수가 무의미해진다\n"
            "  ★기준은 «어긋나지 않는다»가 아니라 «**이 자막을 보여주는 그림인가**»다.\n"
            "    모순이 없다는 이유로 통과시키지 마라 — 그러면 아무 사진이나 다 통과한다.\n"
            "  ★이 그림은 자막이 말하는 **사건의 현장 사진이 아니다.** 숏폼의 배경 그림이다.\n"
            "    물어야 할 것은 딱 하나: **이 그림을 이 자막과 함께 틀어도 어색하지 않은가.**\n"
            "  통과: 자막이 말하는 사람이 그 사람이거나 성별·나이대가 맞다 /\n"
            "        자막이 말하는 사물·장소가 화면에 보인다 / 그 이야기의 인물·장소다\n"
            "  ★반려 — 함께 틀면 **딴 이야기로 보이는** 경우:\n"
            "    자막은 사물인데 그림엔 그 사물이 없다 / 사람의 성별이 다르다 /\n"
            "    시대가 다르다(«1980년대»인데 요즘 사무실) / 나라가 다르다(«케냐»인데 한국)"},

    {"key": "product", "label": "제품이 맞나", "blocking": True,
     "field": "product_ok",
     "bad": lambda v, _d: v is False,
     "ask": "[제품이 맞나]  ★소재에 **특정 제품·브랜드**가 나올 때만 본다\n"
            "  기사가 말하는 그 제품인가, 아니면 **딴 제품·딴 음식**이 왔나.\n"
            "  예: 소재가 «카레 레토르트 파우치»인데 그림은 라면·국물요리 파우치 → false\n"
            "  ★소재에 특정 제품이 없거나(인물·개념 컷) 그림에 제품이 안 나오면 true 로 두어라\n"
            "    — 없는 것을 트집잡지 마라."},

    {"key": "collage", "label": "여러 장면", "blocking": True,
     "field": "single_scene",
     "bad": lambda v, _d: v is False,
     "ask": "[한 장면인가]\n"
            "  한 칸에 **여러 장면이 붙어 있으면** false (콜라주·분할 화면·전후 비교·\n"
            "  격자 배치·같은 인물이 여러 번). 숏폼 한 컷에 들어가면 뭘 보라는지 알 수 없다.\n"
            "  하나의 장면을 한 시점에서 찍은 것이면 true."},

    # ── 기록만 (막지 않는다) ─────────────────────────────────────────────
    {"key": "quality", "label": "규격·화질", "blocking": False,
     "field": None,      # 모델이 아니라 기계로 잰다(photocheck.quality)
     "bad": None,
     "ask": ""},

    {"key": "searched", "label": "검색 진짜 됐나", "blocking": False,
     "field": None,      # images.generate_all 이 남기는 사실(검색 성공/실패)
     "bad": None,
     "ask": ""},
)

PHOTO_RETRY_MAX = 3             # 반려 → 사유를 붙여 다시 만들기. 이 횟수까지(사장님 2026-09-16)
PHOTO_MIN_SIDE = 700            # 슬롯이 1028×786이라 이보다 작으면 늘려 쓰는 셈 — 기록만
PHOTO_BLUR_MIN = 60.0           # 라플라시안 분산 하한. 밑돌면 '흐리다' — 기록만

# 버텍스에 없는 모델 → 있는 것으로. 실측 2026-09-13(us-central1):
#   gemini-3.1-flash-lite · gemini-3-flash-preview · gemini-2.0-flash 는 404.
#   2.5 계열만 된다. 무료 키에서는 3.1이 되므로 붙은 곳에 따라 갈아끼운다(_pick_model).
#   ★검수에 2.5-flash-lite를 쓰면 가짜 기록을 놓친다 → 2.5-flash로 올린다.
# 대본을 쓰는 클로드 모델. ★반드시 못 박는다 — 안 박으면 CLI 기본값을 따라가고,
#   그건 그 PC에 무엇이 기본으로 잡혀 있느냐에 달려 골든 5편 벤치가 재현되지 않는다.
#   (실측 2026-09-14: 지정 없이 `claude --print` 를 부르니 claude-opus-5[1m] 이 잡혔다 —
#    즉 그 벤치(컷차이 15·CHAR차이 5)는 opus 로 잰 값이다.)
SCRIPT_CLAUDE_MODEL = "opus"

VERTEX_MODEL_MAP = {
    "gemini-3.1-flash-lite": "gemini-2.5-flash",
    "gemini-3-flash-preview": "gemini-2.5-flash",
    "gemini-2.0-flash": "gemini-2.5-flash",
    "gemini-2.5-flash-lite": "gemini-2.5-flash",
}
