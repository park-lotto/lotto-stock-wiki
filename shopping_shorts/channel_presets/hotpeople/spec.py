# -*- coding: utf-8 -*-
"""뜨거운사람들(흰 바탕 틀 A) 규격 — 원본 10편 실측(2026-09-25).

근거: channel/hotpeople/역분석_2026-09-25.md (측정 도구 tools/hotpeople/measure/).
★여기 값은 "원본 9편에서 ±5px 안에서 같았던 것"이다. 우리 정책으로 정한 값은 `POLICY_` 접두.
★채널명·로고는 원본 것을 쓰지 않는다(`POLICY_CHANNEL_*`) — 틀만 벤치마킹한다.
"""
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATIC_FONTS = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "static", "fonts")

# ── 캔버스·배치 (역분석 §1) ────────────────────────────────────────────────
CANVAS_W, CANVAS_H = 1080, 1920
BG_RGB = (250, 250, 250)            # 흰 여백 최빈색 248(8단위 양자화) — 250으로 둔다
SLOT_X, SLOT_Y, SLOT_W, SLOT_H = 0, 483, 1080, 790     # 9편 중 6편 483~1273
LOGO_Y0, LOGO_Y1 = 91, 195          # 로고 띠(아이콘+채널명 2줄)
LOGO_X = 48                         # 아이콘 왼쪽 끝(원본 프레임 실측 ≈ 48~52)
LOGO_ICON = 92                      # 원형 아이콘 지름
HEADLINE_Y0, HEADLINE_Y1 = 205, 470 # 헤드라인 2줄이 들어가는 띠
SUB_TOP = 1285                      # 자막 첫 줄 잉크 시작 y (232개 중앙값)
SUB_MAX_INK_W = 740                 # 줄 폭 90% 선(738px). ★칼카피 5: 이 폭 안이면 **한 줄 그대로**, 넘을 때만 줄바꿈
                                    #   (원본 232자막: 1줄 24%(55)·줄 폭 중앙 517 / 우리 v002는 7자마다 끊어 1줄 4%·폭 411)
                                    #   줄바꿈 자리는 두 줄 폭이 가장 고른 곳(원본 2줄 178개 중 114개 재현, 앞을 꽉 채우는 방식은 65개)
SUB_LINE_PITCH = 80                 # 두 줄 자막: 윗줄 잉크 시작→아랫줄 시작 (176개 중앙 80, 71~92)

# ── 글자 (역분석 §2) ───────────────────────────────────────────────────────
# 자막 글꼴: 주아 IoU 0.638(1위). 09-25 "원본이 더 굵다"는 glyph_style.py 실측(2026-09-28)으로 부정됨.
SUB_FONT = os.path.join(_STATIC_FONTS, "BMJUA.ttf")
SUB_FONT_PX = 71                    # 잉크 높이 60px 실측 → 주아 71px 상당
SUB_BOLDEN_PX = 0                   # ★칼카피 4: 원본 획 8px/줄높이 58.5 = 주아 71px **그대로**(외곽선 0/54).
                                    #   1이던 때 우리 v002 획 11px — "원본이 더 굵다"는 틀린 추정이었다(기준표 정정 4)
SUB_RGB = (0, 0, 0)
MARK_RGB = (250, 230, 150)          # 형광펜(옅은 노랑) — 첫 자막 9/9편
MARK_PAD_X, MARK_PAD_TOP, MARK_PAD_BOTTOM, MARK_RADIUS = 14, 4, 15, 10   # 형광펜은 잉크 아래로 15px(실측 중앙)
RED_RGB = (231, 29, 33)             # 자막 강조 빨강
HEAD_FONT = SUB_FONT
HEAD_FONT_PX = 96
HEAD_BOLDEN_PX = 3
HEAD_RGB = (0, 0, 0)
HEAD_RED_RGB = (237, 19, 16)
HEAD_YELLOW_RGB = (244, 254, 1)     # 노랑 강조는 검정 테두리와 짝
HEAD_YELLOW_STROKE = 6
LOGO_NAME_FONT = os.path.join(_STATIC_FONTS, "NanumGothic-Bold.ttf")

# ── 시간 (역분석 §3 + 48자막 회귀 2026-09-25) ──────────────────────────────
# 노출시간 = 1.69 + 0.037×글자수(공백 제외), 원본 범위 1.3~3.1초로 자른다(상관 0.52, 잔차 중앙 0.23s)
SUB_SEC_BASE, SUB_SEC_PER_CHAR = 1.69, 0.037
SUB_SEC_MIN, SUB_SEC_MAX = 1.3, 3.1
FPS = 30
# ── 컷 (칼카피 1, 기준표 §4·§14) ────────────────────────────────────────────
# 원본 9편: 컷 22개(17~34)·컷 길이 중앙 2.1~2.9s·**컷 경계 = 자막 경계 95%**. 우리 v002: 컷 42·1.23s·71%.
# 규칙 = 자막 하나에 영상 조각 하나(1:1), 그 조각은 **소스의 한 장면 안**에서만 자른다(장면 경계를 넘지 않는다).
SCENE_DETECT_THRESH = 0.25          # 소스 장면 자르기 문턱 — 재는 자(cuts.py scene>0.3)보다 낮게 잡아야 자막 안 컷이 새지 않는다
SCENE_DETECT_W, SCENE_DETECT_H = 540, 395   # 장면 자르기는 **렌더와 같은 슬롯 크롭**을 절반 크기로(전체 화면으로 재면 0.29가 크롭 뒤 0.3을 넘었다 — v002 cut_03)
CLIP_INSET_SEC = 0.1                # 장면 앞뒤 0.1초는 안 쓴다 — 경계 장면 검출·반올림 오차 여유(v002 경계 이중 컷의 실제 원인은 빈 첫 프레임, render.cut_clip)
SUB_INNER_CUTS_MAX = 1              # 검수: 자막 안에서 생긴 컷 허용 수(원본 95% 일치 ≈ 22컷 중 1개)
DURATION_MIN, DURATION_MAX = 45.0, 75.0     # 원본 49.8~73.3초

# ── 대본 (역분석 §4) ───────────────────────────────────────────────────────
SUB_COUNT_MIN, SUB_COUNT_MAX = 22, 30       # 원본 24~28
MARK_MAX = 3                                # 형광펜은 편당 15/232 ≈ 1.7개
NAME_REVEAL_BY = 4                          # 이름 공개는 4번째 자막 안에(원본 2~3번째)
PIVOT_LINE = "하지만 그는 달랐음."           # 6편 중 3편 그대로 — 권장(강제 아님)
# 칼카피 2 — 숫자 든 자막 비율. 원본 232자막 중 42개 = 18%, 우리 v002 19/26 = 73%(대본이 숫자 나열)
DIGIT_SUB_TARGET = 0.25             # 이 위로 가면 경고(재작성 권유)
DIGIT_SUB_MAX = 0.30                # 이 위는 반려
# 칼카피 3 — 따옴표 인용 자막 비율. 원본 16%(232 중 script_stats quote), 우리 v002 1/26 = 4%
QUOTE_SUB_MIN = 0.10                # 26자막이면 3개 이상(올림)
# 훅 — 첫 자막은 사실 서술. 56편 전수(§16): "~남자가 있음/~사건이 터짐" 조회 중앙 565k vs 인용 훅 51k(11배).
# 09-25 표본의 "첫 자막 인용 5/9"는 표본 편향(정정 6) — 첫 자막을 인용으로 **강제하지 않는다**. 인용은 대체안(경고)만.
HOOK_FACT_ENDINGS = ("있음", "있었음", "벌어짐", "터짐", "나타남")

# ── 정책 ───────────────────────────────────────────────────────────────────
POLICY_CHANNEL_NAME = os.environ.get("HOTPEOPLE_CHANNEL_NAME", "뜨거운 이야기")
POLICY_CHANNEL_HANDLE = os.environ.get("HOTPEOPLE_CHANNEL_HANDLE", "@hot_story")
POLICY_LOGO_RGB = (230, 90, 30)
POLICY_HEADLINE_HIDE_AFTER = None   # 원본 4/10편은 9~23초 뒤 헤드라인을 숨긴다. None = 끝까지 유지
# ── 배경음악 (원본 10편 Shazam 인식 + 교차상관, 2026-09-25) ──────────────────
# 원본은 편마다 곡 하나를 **정해진 지점부터 속도 그대로** 끝까지 깐다(영상 1s·40s에서 오프셋 차이 동일 7.12s).
# 곡 파일은 POLICY_BGM_DIR 에 아래 이름으로 둔다(저작권 음원 — 커밋 금지, out/hotpeople/bgm 은 gitignore).
POLICY_BGM_DIR = os.environ.get("HOTPEOPLE_BGM_DIR", "") or os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "out", "hotpeople", "bgm")
BGM_TRACKS = [                      # (파일, 곡 속 시작초, 원본 사용 편수)
    ("hero.m4a", 7.1, 3),           # Bonnie Tyler - Holding Out For a Hero  (dvJ 7.12 · z1f 7.34 · 3Ek 7.03, 상관 0.8)
    ("unstoppable.m4a", 10.4, 3),   # Sia - Unstoppable                      (Cmn 10.32 · aKub 10.47 · kbx 10.32)
    ("final_countdown.m4a", 34.0, 2),  # Europe - The Final Countdown        (eehz 37.95 · s1Z 29.86 — 편마다 다름)
    ("kcm_habit.m4a", 94.5, 1),     # KCM - 버릇처럼 셋을 센다(후렴)           (X4G 94.46)
]
BGM_LUFS = -12.0                    # 원본 10편 통합음량 중앙 -12.1 (범위 -9.1 ~ -15.2). 나레가 없어 음악이 크다
# 칼카피 6 — 오프닝. 원본 8/10편 첫 3초가 본편보다 조용(중앙 −2.3 LU), 우리 v002 +2.2 LU.
# ★원인은 페이드인이 아니었다(2026-09-28 실측): 원본 7편을 원곡 같은 지점과 0.25초 단위로 대조 → 이득 평평(페이드 없음).
#   조용함은 곡의 그 구간 모양이고(KCM 편 X4G는 원본도 +3.2 LU 더 큼), v002의 +2.2는 동적 loudnorm이 앞을 끌어올린 것.
#   → 렌더는 고정 이득 하나로 BGM_LUFS 에 맞춘다(render.bgm_gain_db). 페이드인 상수는 두지 않는다.
POLICY_MAX_REWRITES = 4
POLICY_FOOTAGE_QUERIES = 6          # 검색어 수(한 편)
POLICY_FOOTAGE_PER_QUERY = 2        # 검색어당 받을 영상 수
POLICY_FOOTAGE_MAX_VIDEOS = 8       # 한 편에 받을 영상 상한 — 9편에서 장면 후보가 충분했다(2026-09-25 사장님: 그만 받아도 충분)
POLICY_FOOTAGE_MAX_SEC = 1500       # 25분 넘는 영상은 안 받는다
POLICY_FOOTAGE_HEAD_SEC = 480       # 앞 8분만 받는다(다운로드 시간)
POLICY_SCENE_MIN_SEC = 1.0
POLICY_SOURCE_CROP_BOTTOM = 0.18    # 소스 아래 18%를 버리고 채운다 — 국내 하이라이트 영상은 자막이 아래에 박혀 있다(2026-09-25 첫 편 26컷 중 다수)
SCRIPT_CLAUDE_MODEL = "opus"        # channelkit.providers.claude_llm 기본 모델 이름표

# ── 소스 자 (우상혁 v001 사고 2026-09-28: 소스에 주인공이 거의 없었다 — 종합 하이라이트 2편이 24컷 중 15컷) ──────
# 주인공 = 소스 전체 얼굴에서 **여러 영상에 공통으로** 가장 많이 짝지어지는 얼굴(channelkit.vision.protagonist_embedding).
# 비율 = 표본 프레임 중 주인공 얼굴(높이 ≥ 20%, cos ≥ 0.363)이 보인 프레임 비율. 실측 표는 handoff/숏템엔진.md(2026-09-28 게이트).
POLICY_SOURCE_SAMPLE_SEC = 2.0      # 받은 앞부분(최대 480초)에서 2초에 한 장
POLICY_SOURCE_SAMPLE_W, POLICY_SOURCE_SAMPLE_H = 540, 395   # 슬롯 절반 덮개 그림(render.cover_vf)에서 잰다
# 실측(2026-09-28, 표본 2초·주인공 = 소스 공통 얼굴, 주인공 비율 / 판정 가능 얼굴 프레임 비율):
#   우상혁 v001 8편 — 버려야 할 것: Day2 종합 0.000/0.35 · 토크쇼 0.004/0.93 · Day3 종합 0.010/0.20
#                    주인공 영상: Nanjing 결선 0.046 · 도쿄 2.35m 0.116·0.059 · 도하 0.031 · 모나코 0.033
#   안세영 v3 9편 — 근접 영상 0.025~0.543 · **경기 중계(넓은 화면)** 파리 결승 0.000/0.00 · 세계선수권 결승 0.008/0.02
#   → 주인공 비율만으로 자르면 파리 결승(금메달 자막의 핵심 소스)이 버려진다. 그래서 "큰 얼굴이 나오는데 주인공이 아니다"일 때만 버린다.
POLICY_SOURCE_MIN_MAIN_RATIO = 0.02  # 주인공 비율 하한 — 버린 것 최대 0.010 · 주인공 영상 최소 0.025 사이
POLICY_SOURCE_WIDE_JUDGED_MAX = 0.05  # 판정 가능 얼굴이 이 비율 미만이면 "넓은 화면 소스"(증거 없음) — 비율과 무관하게 둔다
                                      #   (파리 결승 0.00 · 세계선수권 결승 0.02 / 버린 것 최소 0.20)
POLICY_SOURCE_MIN_USABLE = 4        # 쓸 소스가 이보다 적으면 멈춘다(에러). 상한은 POLICY_FOOTAGE_MAX_VIDEOS
POLICY_SOURCE_MAX_DOWNLOADS = 20    # 한 편에 시험 삼아 받을 영상 수 상한(버린 것 포함)
POLICY_SOURCE_KO_QUERIES = ("경기", "인터뷰", "하이라이트", "다큐")   # 인물명 + 이것 — v001은 영어 검색어 3개뿐이었다
# 제목으로 먼저 거른다: 토크쇼·리액션·팟캐스트·"Day N Highlights"(대회 종합)·모음집. v001 b_EPLebN4xU(토크쇼)·yIQy0DmGGtI/4Q54vezV2Gw(Day 2/3)
POLICY_SOURCE_TITLE_BLOCK = (r"(?i)(talk\s*show|reaction|\breacts?\b|podcast|reflections|compilation|"
                             r"day\s*\d+\s*highlights|토크쇼|리액션|반응|팟캐스트|모음|몰아보기)")

# ── 내용 관문 (칼카피 규칙 7~10, 기준표 §19 — 넘으면 out/final.mp4 를 안 만들고 out/FAILED.json 으로 멈춘다) ──────
GATE_FACE_VISIBLE_MIN = 0.55        # ⑦ 얼굴 보이는 컷 비율. 원본 9편 중앙 84%(54~100) · v3 77%
GATE_SUBTITLE_LIKE_MAX = 1          # ⑧ 자막꼴 박힌 글자 컷 수. 원본 중앙 0(9편 중 3편에 1컷) · v3 3컷 [1,8,24]
GATE_OTHER_ON_MAIN_MAX = 0          # ⑩ 주인공 자막(subject=main)에 "다른사람" 컷. 원본 0 · v3 [19,23,25]
GATE_VERIFY_BAD_MAX = 0.30          # 장면 검사(제미니) **다시 고른 뒤** 틀림 비율. v001 23/23 → 100%
FACE_CENTER_MAX = 0.13              # ⑨ 얼굴 중심 편차 중앙(보고만, 막지 않음). 원본 0.052(최대 0.13) · v3 0.15
# 자막 주제(대본 groups[].subject) — main=주인공이 하는/겪는 일(기본값), other=코치·가족·상대 등 다른 인물, scene=장소·전광판·기사
SUBJECTS = ("main", "other", "scene")

# ── 엔진 연결 ──────────────────────────────────────────────────────────────
STEPS = ["setup", "research", "script", "footage", "render", "review"]
from . import rules as _rules      # noqa: E402 — 채널 규칙을 lint 창고에 등록
LINT_RULES = ["formal"] + _rules.IDS
from . import steps as _steps      # noqa: E402 — 맨 아래: steps가 channelkit을 import
STEP_HANDLERS = _steps.HANDLERS
