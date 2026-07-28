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

# Reddit OAuth(application-only, 해외HOT 발굴 — 익명 RSS rate-limit 회피, 2026-07-25).
# reddit.com/prefs/apps에서 'script' 앱 생성 → client_id/secret를 .env에 넣으면
# reddit_source가 oauth.reddit.com(100 req/분)으로 자동 전환. 없으면 익명 RSS 폴백.
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
# 주거용 프록시(Webshare 로테이팅 등). 서버 데이터센터 IP는 Reddit 익명 RSS가 429로
# 막혀 완료0건이 났다(실측 2026-07-25). 프록시 경유하면 주거용 IP라 200이 안정적으로 온다.
# 형식: http://user:pass@host:port  (없으면 직결). RSS(urllib)·OAuth(requests) 둘 다 적용.
REDDIT_PROXY = os.getenv("REDDIT_PROXY", "")

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

# ── 인스타 수집 경로 선택(2026-07-28) ──
# Apify는 성공해도 28분이 걸리고 403 Forbidden으로 통째로 죽는 사례가 이틀 새 2건이었다
# (서버 collect_jobs 실측). Playwright + 주거용 프록시로 대체하되, 라이브 대시보드가
# 인스타 수집에 묶여 있으므로 **환경변수 하나로 즉시 되돌릴 수 있게** 둔다.
# ★기본값은 apify다 — 검증 전 병합만으로 라이브 경로가 바뀌면 안 된다.
INSTAGRAM_SCRAPER = os.getenv("INSTAGRAM_SCRAPER", "apify")   # apify | playwright

# 인스타 전용 주거용 프록시(형식은 REDDIT_PROXY와 동일: http://user:pass@host:port).
# 서버 데이터센터 IP로 직접 긁으면 인스타가 막는다 — Reddit이 429로 막혔던 것과 같은 이유.
# 미설정이면 직결(로컬 개발용).
INSTAGRAM_PROXY = os.getenv("INSTAGRAM_PROXY", "")

# 동시에 여는 브라우저 컨텍스트 수. 크로미움은 메모리를 먹으므로 서버 여유를 보고 조정한다.
INSTAGRAM_PW_CONTEXTS = int(os.getenv("INSTAGRAM_PW_CONTEXTS", "5"))
# 채널 1개 처리 상한(ms). 넘으면 그 채널만 error로 접고 다음으로 간다(전체가 죽지 않게).
INSTAGRAM_PW_TIMEOUT_MS = int(os.getenv("INSTAGRAM_PW_TIMEOUT_MS", "20000"))

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
# 높이는 데 재사용한다.
# 무료 플랜은 계정당 월 100회뿐이라 소진되면 렌즈검색이 통째로 막힌다(429). 그래서
# _N 넘버링 풀로 로테이션한다(2026-07-26, Gemini/YouTube와 동일 패턴) — 한 키가 월
# 한도를 소진하면 다음 키로 자동 전환. 키가 모자라면 .env에 SERPAPI_KEY_3, _4… 계속 추가.
_SERPAPI_MAX = 30
SERPAPI_KEYS = [
    v for i in range(1, _SERPAPI_MAX + 1)
    if (v := os.environ.get("SERPAPI_KEY" if i == 1 else f"SERPAPI_KEY_{i}", ""))
]
# 하위호환: 기존 코드가 참조하던 단일 키(=풀의 첫 키). 로테이션은 SERPAPI_KEYS를 쓴다.
SERPAPI_KEY = SERPAPI_KEYS[0] if SERPAPI_KEYS else ""

# ElevenLabs TTS(영상 믹싱 기능④, 2026-07-12) — 새 나레이션 음성 생성. Gemini와
# 무관한 별도 API라 전용/공유 키풀 규칙과 무관(단일 키). 미설정이면 개발용 무음 fallback.
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # 기본 voice(Rachel)

# ASR 라운드트립 검증(튜닝 작업대) — Whisper로 TTS를 재전사해 오독 탐지. GROQ 우선.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# 비트별 TTS 합성 동시성(2026-07-24, 2단계 매칭 실처리시간 단축) — 각 비트가 독립
# 파일(beat_{idx}.mp3)에 쓰고 이웃텍스트도 인덱스로 미리 정해져 있어 병렬 안전.
# ElevenLabs·GROQ-Whisper 랭커 둘 다 rate limit이 있어 무제한 동시성은 429를 부른다
# — 서버에서 실측 후 올릴 수 있도록 env로 노출.
TTS_MAX_WORKERS = int(os.getenv("TTS_MAX_WORKERS", "3"))

# 유튜브 로컬 릴레이(2026-07-24) — 서버(데이터센터 IP)는 유튜브에 봇차단당해 다운로드가
# 통째로 막힌다(주거용 IP는 됨, memory youtube-shorts-datacenter-block). 그래서 서버는
# 유튜브 URL을 yt_relay 큐에 넣고, 사장님 PC의 에이전트가 큐를 폴링해 주거용 IP로 받아
# 서버에 업로드한다. 서버에서만 켠다(YT_RELAY_ENABLED=1) — 로컬/에이전트는 꺼야
# 무한루프가 안 난다(에이전트는 _download_ytdlp를 직접 부른다). KEY는 에이전트 인증용.
# B안(주거용 프록시, 2026-07-24) — A안(PC 릴레이)의 "사장님 PC 의존" 한계를 없앤다. 프록시 URL을
# 넣으면 서버가 직접 유튜브를 그 IP로 받아 PC 없이 24/7·고객 다중 동시 처리된다(업체 무관, 형식
# http://user:pass@host:port). 우선순위: 프록시 > 릴레이(A) > 직접. 미설정이면 기존 A/직접 그대로(회귀0).
YTDLP_PROXY = os.getenv("YTDLP_PROXY", "")

YT_RELAY_ENABLED = os.getenv("YT_RELAY_ENABLED", "") == "1"
YT_RELAY_KEY = os.getenv("YT_RELAY_KEY", "")
YT_RELAY_DIR = Path(__file__).parent / "data" / "yt_relay"   # 에이전트가 올린 mp4 보관
YT_RELAY_POLL_TIMEOUT = int(os.getenv("YT_RELAY_POLL_TIMEOUT", "180"))  # 서버측 대기 상한(초)

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
# 센서스(전수조사) 시 채널당 릴스 상한 — 실제 컷은 until(2일) 날짜필터가 하고, 이 값은
# 런어웨이 비용 가드용 천장일 뿐이다. 2일 안에 20개+ 올리는 채널은 거의 없어 사실상
# "2일 이내 전 영상"이 들어온다(예전 2 = 채널당 2개만 표본 → 소형채널이 밀렸다).
CENSUS_RESULTS_PER_CHANNEL = 20
# 추적 세트 안전 상한(런어웨이 비용 가드). 2일 게이트가 세트를 자연히 좁혀 보통 안
# 걸린다 — 초과 시 활동점수 높은 순으로 남긴다(팔로워 아님). 2026-07-22: 벤치마킹
# 엑셀이 440개로 늘어(엑셀440+등록50=490) 300에 걸려 190개가 잘렸다 → 600으로 상향해
# 전량 추적(매일수집 월 ~7만원 이내, 계산근거 대시보드). 더 늘면 다시 조정.
MAX_TRACKED = 600

# 댓글 draft 생성 배치 크기 — 전체 항목(443채널 수집 시 수백 건)을 한 번에
# Gemini로 다 돌리면 쿼터 낭비가 커서(2026-07-09), 수집 직후엔 상위 랭킹 순으로
# 이만큼만 자동 생성하고 나머지는 "댓글 더 생성" 버튼으로 필요할 때만 이어서 생성.
DRAFT_BATCH_SIZE = 40

# 강도 등급 임계 (정규화 종합점수 0~1 기준)
GRADE_THRESHOLDS = [(0.75, "🔥🔥🔥"), (0.5, "🔥🔥"), (0.25, "🔥"), (0.0, "—")]

# 수집→대본은행 자동 적재(2026-07-22): '지금 수집' 시 밀도+속도 종합점수 상위 표본을
# 부품은행에 자동 분해·적재한다. 임계값이 아니라 '상위 N건'인 이유 = 정규화 점수라 임계값이면
# 소수(9건)만 남아 "표본 많이"와 안 맞음 → 점수 순위 상위를 넓게 뽑는다.
BANK_INGEST_TOP_N = 100      # 수집 1회당 은행에 담을 상위 표본 수(점수 내림차순)
BANK_INGEST_MIN_KR = 20      # 캡션 최소 한국어 글자수(부품 추출 가능선 — 짧거나 외국어는 노이즈)

# 백본-베이스 대본 안 개수(2026-07-22): 백본 순서(뼈대)는 고정하고, 그 위에 쓰는 대본을
# 이만큼 뽑아 심사위원(대본품질·장면싱크·스토리라인)으로 제일 좋은 걸 고른다. 소스당 Gemini
# 콜이라 3 정도가 균형. 조각 1개만 뽑던 걸 best-of-N + 품질심사로 올린다.
BACKBONE_DRAFTS_N = 3

# 컷 리듬(2026-07-22 페이블 진단 — job 23a6db67333a: 비트당 6.8컷 0.7~1.5s 파편 뚝뚝 끊김).
# 화면 채우기(fill)가 짧은 B롤을 무한정 붙이던 걸 막는다: 비트당 클립 상한 + 컷 최소 길이.
# 모자란 길이는 파편 추가 대신 conform(대사 축약)·홀드로 흡수한다.
MAX_CLIPS_PER_BEAT = 3        # 한 비트에 넣을 화면 조각 최대 수(적고 길게)
MIN_SHOT_SECONDS = 1.2       # 컷 하나 최소 길이 — 이보다 짧은 조각은 B롤로 잘 안 쓴다
# 한 컷을 이보다 오래 안 끈다 — 긴 정지(7초 홀드) 대신 distinct 앵글로 컷(벤치마크 ~1.1초).
# 렌더가 이 상한으로 세그먼트를 번갈아 재생해 컷 밀도를 만든다(0=끄기·옛 동작).
MAX_SHOT_SECONDS = 2.2

# 카테고리 (자동 태깅 초기 6분류)
CATEGORIES = ["인테리어", "레시피", "생활용품", "가전", "뷰티", "기타"]

# yt-dlp 쿠키(2026-07-20) — 유튜브·틱톡이 비로그인 요청을 막기 시작해(봇 차단 강화)
# 로그인 세션 없이는 다운로드가 실패한다. 사장님이 브라우저에서 직접 내보낸 쿠키파일
# 경로(플랫폼별 별도 — 계정 다르면 쿠키도 다르다). 파일이 없으면 빈 문자열이고,
# media_download.py는 빈 값이면 --cookies 없이(기존처럼) 시도해 회귀가 없다.
YTDLP_COOKIES_YOUTUBE = os.environ.get("YTDLP_COOKIES_YOUTUBE", "")
YTDLP_COOKIES_TIKTOK = os.environ.get("YTDLP_COOKIES_TIKTOK", "")
