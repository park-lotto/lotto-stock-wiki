# -*- coding: utf-8 -*-
"""bench 문턱 — 이름 하나, 이유 하나. 모듈마다 숫자를 다시 적지 않는다(0순위-B).

근거 문서: docs/superpowers/specs/2026-09-28-channelkit-bench-design.md §1 (겹침 24건 결정)
          docs/칼카피/측정코드_세벌_함수지도_2026-09-28.md §2·§4
채널 이름·채널 좌표는 여기에도 없다. 좌표는 layout.py가 영상에서 찾는다.
"""

# ── layout.py ──────────────────────────────────────────────────────────────
LAYOUT_FPS = 2            # 레이아웃 표본 fps. film/shop/노빠꾸 셋 다 2fps(함수 지도 §4)
LAYOUT_W = 540            # 레이아웃 표본 가로 해상도(세로는 원본 그대로 — 행 좌표 ±1px 유지)
WINDOW_PX_STD = 12        # 영상창 화소 = 시간 표준편차 > 12 (shop body_layout·노빠꾸 layout 공통)
WINDOW_ROW_FRAC = 0.85    # 그런 화소가 행의 85% 이상 = 창 행. film의 "이웃 표본 변화 >0.2"는
                          # 창 아래 자막 띠(교체 주기 ~2s → 변화율 0.2~0.3)까지 창에 붙여 쓰지 않는다
                          # (2026-09-28 첫 기준선 표본 10편 실측: 0.2 → 창 아래 자막 행까지 섞임, 0.85 → 깨끗)
WINDOW_COL_FRAC = 0.5     # 창 행 안에서 열 판정(shop·노빠꾸 공통)
WINDOW_MIN_PX = 100       # 창 최소 높이/폭(노빠꾸 min_len 100)
SEG_GAP = 6               # 1D 구간 잇기 틈(노빠꾸 gap 6)
DYN_ROW_CHG = 0.1         # 창 밖 행이 "자주 바뀐다" = 이웃 표본 행평균 차>4 가 표본쌍의 10% 이상
                          # (자막 교체 ~2s @2fps → 0.2 전후, 제목 사라짐 1회 → 0.01 전후)
ROW_CHG_DIFF = 4          # film layout 이웃 표본 행평균 절대차 문턱
INK_ROW_PX = 3            # 한 행에 잉크 화소가 이만큼 넘으면 그 행에 글자가 있다(표본 해상도 기준)
BAND_PRESENCE = 0.05      # 자막 띠 행 = 잉크가 표본의 5% 이상에서 보이는 행
LOGO_XVID_STD = 12        # 로고 = 같은 틀 영상끼리 시간평균 그림의 편간 표준편차 < 12 인 글자 행(헤드라인은 편마다 다름)
LOGO_MIN_H = 20           # 로고 띠 최소 높이
VARIANT_TOL_PX = 12       # 창 y0·y1가 이만큼 안이면 같은 틀
BG_DARK_LUM = 128         # 배경 밝기 < 128 = 어두운 배경 → 밝은 잉크
CAPTION_INSET = 6         # 창 바로 아래 행은 창 가장자리가 섞인다 — 띠를 6px 안쪽에서 시작
                          # (glyph_style BAND_Y 1272→1278 수정 사유, 2026-09-28 실측 6/9편 줄높이 1px)

# ── 잉크(자막 글자) 판정 — 극성별 하나 (설계 §1 "자막 잉크 문턱") ────────────
INK_DARK = 110            # 밝은 배경의 어두운 글자: lum < 110 (B 네 벌 90/100/110/120의 가운데, font.py 기준)
INK_BRIGHT = 200          # 어두운 배경·영상 위 밝은 글자: lum > 200 + 외곽선(hardsub_probe 방식)
INK_OUTLINE_DARK = 60     # 밝은 글자 옆 외곽선 = lum ≤ 60 (film caption_bands)
INK_OUTLINE_R = 2         # 외곽선 반경 px (5×5 팽창)

# ── captions.py ────────────────────────────────────────────────────────────
CAP_FPS = 10              # 자막 교체 표본 fps (옛 cuts.py — baselines 첫 기준선 232자막)
CAP_SCALE_W, CAP_SCALE_H = 540, 100   # 띠를 이 크기로 줄여 차분(기준선 cuts.py와 같은 면적 정규화)
CAP_DIFF = 0.01           # 잉크 XOR 평균 > 0.01 = 바뀜
CAP_MERGE_S = 0.4         # 0.4s 안의 바뀜은 하나로(등장 중 흔들림)
LINE_ROW_FRAC = 0.003     # 줄 행 = 행 잉크 비율 > 0.3% (lines.py)
LINE_MIN_H = 21           # 줄 = 21행 이상(lines.py `y-s>20`)
CAP_BAND_PAD = 40         # 자막 띠(표본 5% 이상 행)의 위아래 여유 — 드문 3줄·높은 줄도 잡는다(한 줄 잉크 높이 ~58의 2/3)
INSIDE_PRESENCE = 0.3     # 창 안 자막 = 밝은 외곽선 글자가 표본의 30% 이상에서 보이는 행(영상 속 우연한 밝은 모서리 제외)
FILL_LUM = 200            # 형광펜(글자 뒤 채움) 화소: 밝고(lum>200)
FILL_CHROMA = 50          #   채도 있고(max−min>50)
FILL_BG_DIFF = 40         #   배경색과 다르다(최대 채널차>40) — 노랑 고정값 대신 극성·배경 기준
FILL_FRAC = 0.01          # 띠의 1% 이상이 채움이면 형광펜 자막(lines.py 0.01)
GLYPH_RUN_MAX = 30        # 획 폭 = 잉크 연속길이 30px 미만의 중앙값(glyph_style)
GLYPH_FIRST_LINE_MIN = 10 # 첫 줄 = 잉크 행 10행 이상 덩어리(티끌 제외)
GLYPH_ROW_PX = 3          # 글꼴 줄 행 = 행 잉크 화소 > 3
GLYPH_OUTLINE_DIFF = 40   # 3px 고리 평균이 배경·잉크 둘 다와 40 이상 다르면 외곽선
GLYPH_PER_VIDEO = 6       # 편당 모양 표본 자막 수(glyph_style 기본)
GLYPH_SHADOW_DROP = 70    # 그림자 화소 = 잉크 아닌데 배경보다 70 이상 어둡다/밝다(glyph_style 248→180 과 같은 폭)
GLYPH_SHADOW_FRAC = 0.3   # 옮긴 잉크 자리의 30% 이상이 그림자 화소면 그 오프셋이 그림자
ANIM_FRAMES = 9           # 등장 효과 = 자막 시작 뒤 0~8 프레임(glyph_style)
ANIM_W_FRAC = 0.05        # 폭 5% 변화 = 확대/축소
ANIM_CX_PX = 5            # 중심 5px 이동 = 이동
ANIM_AREA = 0.5           # 첫 면적 < 끝 면적의 50% = 페이드/타자기

# ── cuts.py ────────────────────────────────────────────────────────────────
SCENE_T = 0.3             # ffmpeg select=gt(scene,T), 영상창 crop. baselines 첫 기준선(컷 중앙 22)이 0.3
                          # 볼케이노 scene_cuts는 T를 서버가 주므로 고정값이 없다(설계 §1)
CUT_MERGE_S = 0.2         # 0.2s 안의 중복 검출은 하나로(film scene_cuts)
CUT_MIN_T = 0.2           # 첫 0.2s 안 검출은 컷이 아니라 시작(옛 cuts.py `c>0.2`)
CUT_VERIFY_CORR = 0.6     # 컷 앞뒤 64×64 z정규화 상관 < 0.6 이어야 진짜 컷(cut_verify CORR_MAX)
CUT_VERIFY_TOP = 0.65     # 상관은 창 위쪽 65%만(창 안 자막 띠 제외, cut_verify)
CUT_SUB_TOL = 0.2         # 컷 = 자막 교체 일치 ±0.2s (rhythm_stats)
ZOOM_FPS = 5              # 줌 추적 fps(film zoom_track)

# ── audio.py ───────────────────────────────────────────────────────────────
SR = 48000                # PCM 표본율
S_FLOOR = -70.0           # 단기 S: −70 이하 제외
S_MIN_N = 20              # S 20개 미만이면 폭 None
HF_LO, HF_HI = 8000.0, 16000.0  # 고역 대역(m_opensound)
HF_NTAPS, HF_BETA = 1001, 8.6   # kaiser FIR, 중심 이득 정규화(film band_rms_db)
WIN_S = 0.020             # 20ms RMS 창(볼케이노 B1)
OPEN_S = 3.0              # 오프닝 구간(A7 openvoice, A.open3s_M)
