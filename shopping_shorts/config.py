"""쇼핑쇼츠 레퍼런스 랭킹 - 설정/경로/임계값."""
import os
from pathlib import Path

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

# Apify
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
# 계정 하나가 사용량 소진되면 다음 계정으로 자동 로테이션(2026-07-09) — 4계정 키 풀
APIFY_TOKENS = [
    t for t in (
        os.environ.get("APIFY_TOKEN", ""),
        os.environ.get("APIFY_TOKEN_2", ""),
        os.environ.get("APIFY_TOKEN_3", ""),
        os.environ.get("APIFY_TOKEN_4", ""),
    ) if t
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

# 수집 규칙
WINDOW_HOURS = 48          # 48시간 이내만 랭킹
RESULTS_PER_CHANNEL = 3    # 채널당 최신 상한
ONLY_NEWER_THAN = "2 days" # Apify 날짜필터 (창 + 여유)

# 댓글 draft 생성 배치 크기 — 전체 항목(443채널 수집 시 수백 건)을 한 번에
# Gemini로 다 돌리면 쿼터 낭비가 커서(2026-07-09), 수집 직후엔 상위 랭킹 순으로
# 이만큼만 자동 생성하고 나머지는 "댓글 더 생성" 버튼으로 필요할 때만 이어서 생성.
DRAFT_BATCH_SIZE = 40

# 강도 등급 임계 (정규화 종합점수 0~1 기준)
GRADE_THRESHOLDS = [(0.75, "🔥🔥🔥"), (0.5, "🔥🔥"), (0.25, "🔥"), (0.0, "—")]

# 카테고리 (자동 태깅 초기 6분류)
CATEGORIES = ["인테리어", "레시피", "생활용품", "가전", "뷰티", "기타"]
