"""쇼핑쇼츠 레퍼런스 랭킹 - 설정/경로/임계값."""
import os
from pathlib import Path

# 로컬 개발: shopping_shorts/.env 자동로드(APIFY·ELEVENLABS 등). 서버는 systemd
# EnvironmentFile로 주입되므로, override=False로 이미 설정된 환경변수를 덮지 않는다
# (.env 파일이 없으면 조용히 무시 — 서버엔 이 파일이 없어도 정상).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env", override=False)
except ImportError:
    pass

# 채널 소스 엑셀 (컬럼: 채널명 / 주소 / 팔로워 / 인포크링크)
EXCEL_PATH = Path(
    os.environ.get(
        "SHORTS_EXCEL",
        r"C:\Users\CH\Documents\카카오톡 받은 파일\벤치마킹시트 신규.xlsx",
    )
)

# 로컬 SQLite DB (수집 이력)
DB_PATH = Path(__file__).parent / "data" / "reference.db"

# 배포 도메인 — Google Lens 등 외부 서비스가 우리 프레임 이미지를 직접 fetch할 때 필요.
# 로컬 개발 시엔 기본값(localhost)이라 Lens 링크가 실제로는 안 열리는 게 정상(배포 후 확인).
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8848")

# 구글 OAuth(유료게이트 고객 로그인, 2026-07-19). 콘솔에서 발급한 값을 .env에 넣는다.
# redirect는 콘솔 등록값과 정확히 일치해야 한다: https://shoppingshorts.duckdns.org/auth/google/callback
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI", "https://shoppingshorts.duckdns.org/auth/google/callback")

# Apify
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
# 계정 하나가 사용량 소진(월 한도 등)되면 다음 계정으로 자동 로테이션(2026-07-09).
# _N 넘버링 동적 스캔(4개 고정→계속 추가 가능, SHORTS_GEMINI_KEYS와 동일 패턴).
_APIFY_MAX = 30
APIFY_TOKENS = [
    t for i in range(1, _APIFY_MAX + 1)
    if (t := os.environ.get("APIFY_TOKEN" if i == 1 else f"APIFY_TOKEN_{i}", ""))
]
APIFY_ACTOR = "apify~instagram-reel-scraper"  # actor id (~ 형식)

# 댓글 draft 생성 전용 Gemini 키 풀 — 주식위키 본체(pipeline.atoms.key_vault)의
# 공유 풀과 완전히 분리(2026-07-09). 공유 풀은 인제스트·브리핑 등 다른 작업과
# 하루 종일 같이 소모돼 예고 없이 소진되는 사고가 있었음 — 쇼핑쇼츠는 이 전용
# 풀만 쓰고, 공유 풀로 폴백하지 않는다(소진되면 그냥 다음날까지 대기).
# _N 넘버링을 동적으로 스캔(2026-07-09, 3개→13개로 확장하며 고정 목록 대신 변경).
_SHORTS_GEMINI_MAX = 30
SHORTS_GEMINI_KEYS = [
    v for i in range(1, _SHORTS_GEMINI_MAX + 1)
    if (v := os.environ.get("SHORTS_GEMINI_KEY" if i == 1 else f"SHORTS_GEMINI_KEY_{i}", ""))
]

# YouTube Data API v3 키 풀(제품찾기 실수집용, 2026-07-09) — 무료 할당량 계정별
# 소진 대비 로테이션. _N 넘버링 동적 스캔(SHORTS_GEMINI_KEYS와 동일 패턴).
_YOUTUBE_MAX = 30
YOUTUBE_API_KEYS = [
    v for i in range(1, _YOUTUBE_MAX + 1)
    if (v := os.environ.get("YOUTUBE_API_KEY" if i == 1 else f"YOUTUBE_API_KEY_{i}", ""))
]

# SerpApi(Google Lens 엔진) — 제품 정확 명칭 확인용(2026-07-10). 어제는 "구매처
# 찾기"(쇼핑링크 노출)로 잘못 썼다가 삭제했는데, 오늘은 용도를 바꿔서 프레임을
# 역검색한 결과로 정확한 제품명(브랜드+모델)을 추론해 검색 키워드 정밀도를
# 높이는 데 재사용한다. 유료 API라 로테이션 풀 없이 단일 키.
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

# ElevenLabs TTS(영상 믹싱 기능④, 2026-07-12) — 새 나레이션 음성 생성. Gemini와
# 무관한 별도 API라 전용/공유 키풀 규칙과 무관(단일 키). 미설정이면 개발용 무음 fallback.
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # 기본 voice(Rachel)

# ASR 라운드트립 검증(튜닝 작업대) — Whisper로 TTS를 재전사해 오독 탐지. GROQ 우선.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# 수집 규칙
WINDOW_HOURS = 48          # 48시간 이내만 랭킹(인스타 — 빠르게 도는 릴스 기준)
# 유튜브 Shorts는 며칠~몇 주에 걸쳐 조회수가 쌓여 48h는 결과가 너무 적다(실측
# 2026-07-13). 발굴 창을 넓게(14일) 잡아 언어필터 후에도 충분한 후보를 확보.
YOUTUBE_WINDOW_HOURS = 336  # 14일
YOUTUBE_MAX_PER_KW = 50     # 키워드당 검색 상한(YouTube API 한 호출 최대)
RESULTS_PER_CHANNEL = 3    # 채널당 최신 상한
ONLY_NEWER_THAN = "2 days" # Apify 날짜필터 (창 + 여유)

# 벤치마킹 엑셀 채널 수 상한(2026-07-13, 비용 관리용). ⚠️ 2026-07-22 활동성 선별로
# 전환하며 선별에서 미사용 — 팔로워 컷 대신 활동성(최근 업로드)으로 거른다. 기존
# cap_channels/merge_tracked 테스트 보존용으로 상수만 남긴다.
MAX_CHANNELS = 200

# ── 활동성 선별(2026-07-22) — 팔로워 컷을 활동성으로 대체 ──
# 최근 이 일수 내 업로드 없으면 "사망"(소프트, 복구·부활 가능). 매일 랭킹 창(48h)과
# 분리된 영구 판정 기준 — 상수 하나라 나중에 7 등으로 조정 시 코드 재작성 불필요.
DEAD_AFTER_DAYS = 2
# 센서스(전수조사) 시 채널당 릴스 상한 — 생존·참여밀도 표본용이라 매일 랭킹(3)보다 작게.
CENSUS_RESULTS_PER_CHANNEL = 2
# 추적 세트 안전 상한(런어웨이 비용 가드). 2일 게이트가 세트를 자연히 좁혀 보통 안
# 걸린다 — 초과 시 활동점수 높은 순으로 남긴다(팔로워 아님).
MAX_TRACKED = 300

# 댓글 draft 생성 배치 크기 — 전체 항목(443채널 수집 시 수백 건)을 한 번에
# Gemini로 다 돌리면 쿼터 낭비가 커서(2026-07-09), 수집 직후엔 상위 랭킹 순으로
# 이만큼만 자동 생성하고 나머지는 "댓글 더 생성" 버튼으로 필요할 때만 이어서 생성.
DRAFT_BATCH_SIZE = 40

# 강도 등급 임계 (정규화 종합점수 0~1 기준)
GRADE_THRESHOLDS = [(0.75, "🔥🔥🔥"), (0.5, "🔥🔥"), (0.25, "🔥"), (0.0, "—")]

# 카테고리 (자동 태깅 초기 6분류)
CATEGORIES = ["인테리어", "레시피", "생활용품", "가전", "뷰티", "기타"]

# yt-dlp 쿠키(2026-07-20) — 유튜브·틱톡이 비로그인 요청을 막기 시작해(봇 차단 강화)
# 로그인 세션 없이는 다운로드가 실패한다. 사장님이 브라우저에서 직접 내보낸 쿠키파일
# 경로(플랫폼별 별도 — 계정 다르면 쿠키도 다르다). 파일이 없으면 빈 문자열이고,
# media_download.py는 빈 값이면 --cookies 없이(기존처럼) 시도해 회귀가 없다.
YTDLP_COOKIES_YOUTUBE = os.environ.get("YTDLP_COOKIES_YOUTUBE", "")
YTDLP_COOKIES_TIKTOK = os.environ.get("YTDLP_COOKIES_TIKTOK", "")
