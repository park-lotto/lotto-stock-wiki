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
