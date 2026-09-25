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
SUB_MAX_INK_W = 740                 # 줄 폭 90% 선(738px). 넘으면 줄바꿈/반려
SUB_LINE_PITCH = 80                 # 두 줄 자막: 윗줄 잉크 시작→아랫줄 시작 (176개 중앙 80, 71~92)

# ── 글자 (역분석 §2) ───────────────────────────────────────────────────────
# ★자막 글꼴은 잠정: 주아 IoU 0.638(1위) — 원본이 더 굵다. 굵기는 외곽선 같은 색으로 보탠다(추정).
SUB_FONT = os.path.join(_STATIC_FONTS, "BMJUA.ttf")
SUB_FONT_PX = 71                    # 잉크 높이 60px 실측 → 주아 71px 상당
SUB_BOLDEN_PX = 1                   # 같은 색 외곽선으로 굵게(원본 굵기 근사, 미확정)
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
DURATION_MIN, DURATION_MAX = 45.0, 75.0     # 원본 49.8~73.3초

# ── 대본 (역분석 §4) ───────────────────────────────────────────────────────
SUB_COUNT_MIN, SUB_COUNT_MAX = 22, 30       # 원본 24~28
MARK_MAX = 3                                # 형광펜은 편당 15/232 ≈ 1.7개
NAME_REVEAL_BY = 4                          # 이름 공개는 4번째 자막 안에(원본 2~3번째)
PIVOT_LINE = "하지만 그는 달랐음."           # 6편 중 3편 그대로 — 권장(강제 아님)

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
POLICY_MAX_REWRITES = 4
POLICY_FOOTAGE_QUERIES = 6          # 검색어 수(한 편)
POLICY_FOOTAGE_PER_QUERY = 2        # 검색어당 받을 영상 수
POLICY_FOOTAGE_MAX_VIDEOS = 8       # 한 편에 받을 영상 상한 — 9편에서 장면 후보가 충분했다(2026-09-25 사장님: 그만 받아도 충분)
POLICY_FOOTAGE_MAX_SEC = 1500       # 25분 넘는 영상은 안 받는다
POLICY_FOOTAGE_HEAD_SEC = 480       # 앞 8분만 받는다(다운로드 시간)
POLICY_SCENE_THRESH = 0.3
POLICY_SCENE_MIN_SEC = 1.0
POLICY_SOURCE_CROP_BOTTOM = 0.18    # 소스 아래 18%를 버리고 채운다 — 국내 하이라이트 영상은 자막이 아래에 박혀 있다(2026-09-25 첫 편 26컷 중 다수)
SCRIPT_CLAUDE_MODEL = "opus"        # channelkit.providers.claude_llm 기본 모델 이름표

# ── 엔진 연결 ──────────────────────────────────────────────────────────────
STEPS = ["setup", "research", "script", "footage", "render", "review"]
from . import rules as _rules      # noqa: E402 — 채널 규칙을 lint 창고에 등록
LINT_RULES = ["formal"] + _rules.IDS
from . import steps as _steps      # noqa: E402 — 맨 아래: steps가 channelkit을 import
STEP_HANDLERS = _steps.HANDLERS
