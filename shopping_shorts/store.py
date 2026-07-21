"""SQLite 수집 이력 저장소."""
import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# 개인 행동 테이블(saved/mix_basket/commented/script_wiki)의 레거시(마이그레이션
# 이전) 데이터가 귀속되는 고객 ID(2026-07-13, 멀티테넌시). 기존 단일 관리자
# 계정의 데이터를 그대로 보존하기 위한 값 — 신규 고객은 1부터 발급.
LEGACY_CUSTOMER_ID = 0

# upsert_produce_work의 job_id/step 부분 업데이트 센티널(2026-07-17).
# 파이썬 기본 인자값(None/0)은 "미지정"과 구별이 안 돼서, 부분 저장(재전송 안 한 필드)이
# 그대로 UPDATE에 박혀 기존 job_id·step을 조용히 지웠다(리뷰 재현). 규칙:
#   인자를 아예 안 넘기면(=_UNSET) → 기존 값 보존
#   job_id=None / step=0을 명시적으로 넘기면 → 정말로 그 값으로 덮어씀(재매칭 무효화 등)
_UNSET = object()

# 부품은행(2026-07-21, Phase0) — 대본을 분해해 담는 8버킷. 스타일 5(hook/ending/
# adverb/cta/price)=리터럴 문구, 내용 3(evidence/conflict/emotion)=슬롯 템플릿.
# 모듈 상수로 못박아 pattern_bucket_counts·UI 탭·추출 스키마가 같은 출처를 쓴다.
PATTERN_BUCKETS = ("hook", "ending", "adverb", "cta", "price",
                   "evidence", "conflict", "emotion")


def _normalize_canonical(text):
    """dedup 키 — strip + 소문자 + 연속 공백 1개. 공백·대소문자만 다른 문구는
    같은 부품으로 합쳐(freq로 쌓아) 목록이 중복으로 붓지 않게 한다."""
    return " ".join((text or "").split()).lower()


class Store:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        # 주: access_level이 요청마다 Store를 만들어 _init_schema(멱등)를 재실행하는 비용은
        #     Opus 리뷰 P1 지적사항이나, 경로별 1회 가드는 마이그레이션 의존 테스트를 깨서 보류.
        #     소규모(지인 판매) 스케일에선 허용. 필요 시 요청스코프 캐시로 별도 최적화.

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_schema(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_date TEXT NOT NULL,
                    shortcode TEXT NOT NULL,
                    username TEXT,
                    comments INTEGER,
                    delta INTEGER
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_shortcode ON snapshots(shortcode, id)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS comment_drafts (
                    shortcode TEXT PRIMARY KEY,
                    drafts_json TEXT NOT NULL
                )
            """)
            # 개인 행동 테이블(2026-07-13 멀티테넌시 — customer_id 복합키). 신규 DB는
            # 바로 이 스키마로 생성되고, 기존 DB(customer_id 없는 구버전)는 아래
            # _migrate_personal_tables()가 재생성 방식으로 이관한다.
            c.execute("""
                CREATE TABLE IF NOT EXISTS commented (
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    shortcode TEXT NOT NULL,
                    commented_at TEXT,
                    PRIMARY KEY (customer_id, shortcode)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS saved (
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    shortcode TEXT NOT NULL,
                    saved_at TEXT,
                    PRIMARY KEY (customer_id, shortcode)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS mix_basket (
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    shortcode TEXT NOT NULL,
                    url TEXT,
                    thumbnail TEXT,
                    name TEXT,
                    caption TEXT,
                    added_at TEXT,
                    PRIMARY KEY (customer_id, shortcode)
                )
            """)
            # 영상제작으로 "보낸" 도서관 대본(2026-07-13) — 우리믹스 탭 기본 목록.
            # script_wiki를 shortcode로 참조. customer_id별 독립(멀티테넌시 패턴).
            c.execute("""
                CREATE TABLE IF NOT EXISTS produce_script_picks (
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    shortcode TEXT NOT NULL,
                    added_at TEXT,
                    PRIMARY KEY (customer_id, shortcode)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS last_run (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    items_json TEXT NOT NULL,
                    collected_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS source_analysis (
                    shortcode TEXT PRIMARY KEY,
                    keywords_json TEXT,
                    frames_json TEXT,
                    analyzed_at TEXT
                )
            """)
            # 카드 대본추출 캐시(2026-07-13) — shortcode당 1행, 재클릭 시 즉시 반환.
            c.execute("""
                CREATE TABLE IF NOT EXISTS script_extracts (
                    shortcode TEXT PRIMARY KEY,
                    script_json TEXT NOT NULL,
                    extracted_at TEXT
                )
            """)
            # 랭킹 검색용 썸네일 비전 주제태그(2026-07-19) — shortcode당 1행, 있으면 재호출 안 함(무과금).
            c.execute("""
                CREATE TABLE IF NOT EXISTS vision_tags (
                    shortcode TEXT PRIMARY KEY,
                    subject TEXT,
                    keywords_json TEXT,
                    created_at TEXT
                )
            """)
            # 학습소재 통계용 확장(2026-07-13) — 위키 저장 여부와 무관하게 대본추출된
            # 모든 항목에 구조분석을 백필하기 위한 컬럼.
            # category_source(2026-07-16): 카테고리가 어디서 왔나 — user|gemini|keyword.
            # 키워드 추측 정확도가 실측 54%(13건 중 7건)인데 학습 코퍼스의 다수를
            # 차지해(생활용품 79%·인테리어 80%가 추측) 통계가 오염된다. 출처를 남겨야
            # ①사용자 교정을 AI가 덮지 않고 ②나중에 추측만 골라 재분류·가중치 조정이 된다.
            for col, ddl in (("category", "TEXT"), ("structure_json", "TEXT"),
                              ("structure_analyzed_at", "TEXT"), ("category_source", "TEXT")):
                try:
                    c.execute(f"ALTER TABLE script_extracts ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass  # 이미 있으면(기존 DB) 무시
            # 옛 어휘 → 홈템 이관(2026-07-16). 코드만 바꾸면 DB의 옛 라벨이 통제 어휘
            # 밖으로 떨어져 나가(고아 버킷) 학습에서 조용히 빠진다. 되돌릴 수 없는
            # 병합이라 실행 전 서버 백업을 떴다(/tmp/hometem_backup/pre_merge.json).
            # element_category_stats는 배치가 재계산해 덮으므로 옛 버킷만 지운다.
            for table, col in (("script_extracts", "category"), ("script_wiki", "category")):
                try:
                    c.execute(f"UPDATE {table} SET {col}='홈템' "
                              f"WHERE {col} IN ('인테리어', '생활용품')")
                except sqlite3.OperationalError:
                    pass  # 아직 테이블·컬럼이 없는 신규 DB
            try:
                c.execute("DELETE FROM element_category_stats "
                          "WHERE product_category IN ('인테리어', '생활용품')")
            except sqlite3.OperationalError:
                pass
            # 학습소재 카테고리 통계 캐시(2026-07-13) — 매일 새벽 배치가 재계산해 덮어씀.
            c.execute("""
                CREATE TABLE IF NOT EXISTS element_category_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_category TEXT NOT NULL,
                    element TEXT NOT NULL,
                    category_label TEXT NOT NULL,
                    description TEXT,
                    examples_json TEXT,
                    sample_count INTEGER,
                    computed_at TEXT
                )
            """)
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_element_stats_lookup "
                "ON element_category_stats(product_category, element)"
            )
            # 생성 초안 버전 이력(2026-07-13, 디벨롭 루프) — 수정/재생성마다 새 행,
            # parent_draft_id로 체인. customer_id 멀티테넌시 패턴.
            c.execute("""
                CREATE TABLE IF NOT EXISTS script_drafts (
                    draft_id TEXT PRIMARY KEY,
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    source_shortcode TEXT,
                    parent_draft_id TEXT,
                    hook TEXT,
                    script_text TEXT NOT NULL,
                    edit_instruction TEXT,
                    edit_mode TEXT,
                    created_at TEXT
                )
            """)
            # S급 대본 위키(도서관, 2026-07-13) — 담은 대본 + AI 구조분석. 생성의 재료.
            # customer_id 복합키(2026-07-13 멀티테넌시) — 위 commented/saved/mix_basket와 동일 패턴.
            c.execute("""
                CREATE TABLE IF NOT EXISTS script_wiki (
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    shortcode TEXT NOT NULL,
                    name TEXT, category TEXT, source_url TEXT,
                    full_text TEXT, segments_json TEXT, structure_json TEXT,
                    followers INTEGER, comments INTEGER, density REAL,
                    saved_at TEXT,
                    PRIMARY KEY (customer_id, shortcode)
                )
            """)
            # 장면 라이브러리 — 재사용 짤 뱅크(2026-07-15). 자주 쓰는 후킹 장면(놀라는짤·
            # 효과음·"비법 한 스푼" 등)을 구간컷으로 저장해 믹스 때 재사용한다.
            # saved/script_wiki와 달리 자연키(shortcode)가 없고 한 소스에서 여러 자산을
            # 뽑으므로 AUTOINCREMENT id를 PK로 쓰고 customer_id는 일반 컬럼+인덱스로 격리.
            # 매칭 키는 한 단어 라벨이 아니라 다축(role·category·subject·keywords·scene_desc)
            # — "한스푼"이 가루↔액체↔세제로 섞이는 사고를 막는 이 설계의 심장.
            c.execute("""
                CREATE TABLE IF NOT EXISTS scene_assets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    asset_type TEXT NOT NULL,
                    render_mode TEXT,
                    media_path TEXT NOT NULL,
                    poster_path TEXT,
                    duration REAL,
                    keep_original_audio INTEGER NOT NULL DEFAULT 0,
                    title TEXT,
                    scene_desc TEXT,
                    role TEXT,
                    category TEXT,
                    subject TEXT,
                    tone TEXT,
                    keywords TEXT,
                    source_kind TEXT,
                    source_ref TEXT,
                    created_at TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_scene_assets_type "
                      "ON scene_assets(customer_id, asset_type)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_scene_assets_cat "
                      "ON scene_assets(customer_id, category)")
            # 짜집기 대응(2026-07-17, 설계 §7.1):
            #  · source_start_frame — 원본에서의 시작 **프레임**. 초로 저장하면
            #    '원본 순서대로 이어졌나' 판정에 반올림 오차가 낀다. 원본처럼 보이게
            #    만드는 건 '같은 소스'가 아니라 '원본 순서'다.
            #  · source_origin — 짜집기|촬영원본|모름. 사람이 고른다(AI 판정은
            #    실측 탈락 — 정답 아는 시험지에서 3편 전부 '촬영원본/확신 높음').
            for col, ddl in (
                ("source_start_frame", "INTEGER"),
                ("source_origin", "TEXT NOT NULL DEFAULT '모름'"),
            ):
                try:
                    c.execute(f"ALTER TABLE scene_assets ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass  # 이미 존재
            # 썸네일 URL 보관(2026-07-15) — 우리믹스 대본선택 리스트가 <video> 첫 프레임에
            # 의존해 검은칸으로 보이던 문제. 저장 시점 URL을 남겨 <img>로 즉시 그린다.
            try:
                c.execute("ALTER TABLE script_wiki ADD COLUMN thumbnail TEXT")
            except sqlite3.OperationalError:
                pass  # 이미 있으면(기존 DB) 무시
            # 원클릭 담기 영상의 메타(조회수·좋아요·댓글·길이·채널) 보관(2026-07-18).
            # yt-dlp/oEmbed로 백그라운드 보강한 값을 JSON으로 넣어 모음집이 레퍼런스 랭킹처럼 표시.
            try:
                c.execute("ALTER TABLE mix_basket ADD COLUMN meta_json TEXT")
            except sqlite3.OperationalError:
                pass
            # 고객 계정(2026-07-13 멀티테넌시). 비밀번호는 pbkdf2-sha256(솔트별도)로만
            # 저장 — 평문 저장 금지.
            c.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT,
                    plan TEXT NOT NULL DEFAULT 'free',
                    full_access_until INTEGER NOT NULL DEFAULT 0,
                    google_sub TEXT,
                    email TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS source_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_shortcode TEXT,
                    platform TEXT,
                    url TEXT,
                    title TEXT,
                    thumbnail TEXT,
                    similarity_score REAL,
                    collected_at TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_candidates_source ON source_candidates(source_shortcode)")
            try:
                c.execute("ALTER TABLE source_candidates ADD COLUMN source_lang TEXT")
            except sqlite3.OperationalError:
                pass  # 이미 있으면(기존 DB) 무시 — "해외원본 vs 국내" 판단 배지용(2026-07-10)
            c.execute("""
                CREATE TABLE IF NOT EXISTS source_pool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    origin_shortcode TEXT,
                    candidate_id INTEGER,
                    saved_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS mix_jobs (
                    job_id TEXT PRIMARY KEY,
                    urls_json TEXT NOT NULL,
                    target_seconds INTEGER NOT NULL,
                    structure TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    extract_json TEXT,
                    edit_plan_json TEXT,
                    video_path TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    subtitle_removal INTEGER NOT NULL DEFAULT 0,
                    clean_video_path TEXT,
                    given_script TEXT,
                    headcopy_json TEXT,
                    fx_plan TEXT,
                    fx_status TEXT,
                    fx_path TEXT,
                    scene_first INTEGER NOT NULL DEFAULT 0,
                    candidates_json TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS seo_keyword_stats (
                    keyword TEXT NOT NULL,
                    region TEXT NOT NULL DEFAULT 'KR',
                    views_top INTEGER,
                    views_median INTEGER,
                    small_ratio REAL,
                    small_hits INTEGER,
                    hit_n INTEGER,
                    sample_n INTEGER,
                    top_titles_json TEXT,
                    verdict TEXT,
                    checked_at TEXT NOT NULL,
                    PRIMARY KEY (keyword, region)
                )
            """)
            # views_top은 T8 실측 뒤에, small_hits·hit_n은 그 뒤 리뷰 지적으로 붙었다
            # (2026-07-17) — 그 전에 테이블을 만든 로컬 DB가 있으므로 없으면 채워 넣는다.
            # 서버엔 아직 이 테이블 자체가 없다.
            for _col, _ddl in (("views_top", "INTEGER"),
                               ("small_hits", "INTEGER"),
                               ("hit_n", "INTEGER")):
                try:
                    c.execute(f"ALTER TABLE seo_keyword_stats ADD COLUMN {_col} {_ddl}")
                except sqlite3.OperationalError:
                    pass  # 이미 존재
            # 제작소 작업파일(2026-07-17) — 사장님 제보 "뒤로가기 하니까 작업물이 지워진다".
            # ★mix_jobs를 재활용하지 않는다: urls_json·structure가 NOT NULL이라 **매칭 전
            # 작업**(대본만 확정한 상태)을 못 담는다. 실측으로 서버 job 21건 중 매칭 전은 0건 —
            # 사장님이 잃어버린 게 정확히 그 구간이다. 억지로 빈 값을 넣으면 "매칭 안 된 job"이
            # 유령으로 남아 run_mix_job·pollMix가 실제 job으로 오인한다.
            # job_id는 **다리일 뿐**(작업 → job 방향) — 작업이 job보다 먼저 존재한다.
            c.execute("""
                CREATE TABLE IF NOT EXISTS produce_works (
                    work_id TEXT PRIMARY KEY,
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    title TEXT,
                    state_json TEXT NOT NULL,
                    job_id TEXT,
                    step INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_produce_works_customer "
                      "ON produce_works(customer_id, updated_at DESC)")
            # 보이스 프리셋(2026-07-14, 영상제작 4단계) — 큐레이션된 목소리 카드.
            c.execute("""
                CREATE TABLE IF NOT EXISTS voice_presets (
                    preset_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    one_liner TEXT,
                    lang TEXT NOT NULL DEFAULT 'KR',
                    archetype TEXT,
                    base_voice_id TEXT NOT NULL,
                    model_id TEXT NOT NULL DEFAULT 'eleven_multilingual_v2',
                    voice_settings_json TEXT NOT NULL,
                    default_speed REAL NOT NULL DEFAULT 1.0,
                    default_silence_trim TEXT NOT NULL DEFAULT 'off',
                    sample_file TEXT,
                    source_ref TEXT,
                    origin TEXT NOT NULL DEFAULT 'curated',
                    created_at TEXT NOT NULL,
                    group_id TEXT,
                    variant TEXT NOT NULL DEFAULT 'stable'
                )
            """)
            # 성우 1명당 stable/natural/expressive 3톤(2026-07-14) — 기존 DB 백필.
            # naturalize_profile_json(2026-07-15): 튜닝 작업대에서 동결한 자연화 프로파일.
            # best(2026-07-16): 사장님 청취 판정으로 뽑은 베스트 성우. 이 한 필드가 두 일을
            # 한다 — 카드 정렬(ORDER BY best DESC)과 ⭐ 배지. 둘로 나누면(sort_order +
            # recommended) "베스트인데 순서는 뒤"라는 모순 상태가 표현 가능해진다(설계 §4.1).
            for col, ddl in (("group_id", "TEXT"), ("variant", "TEXT NOT NULL DEFAULT 'stable'"),
                             ("naturalize_profile_json", "TEXT"),
                             ("best", "INTEGER NOT NULL DEFAULT 0")):
                try:
                    c.execute(f"ALTER TABLE voice_presets ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass  # 이미 있으면(기존 DB) 무시
            c.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS platform_seeds (
                    platform TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    value TEXT NOT NULL,
                    added_at TEXT,
                    PRIMARY KEY (platform, value)
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS platform_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    run_date TEXT NOT NULL,
                    shortcode TEXT NOT NULL,
                    base INTEGER,
                    delta INTEGER
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_psnap ON platform_snapshots(platform, shortcode, id)")
            # 발굴로 찾아 "벤치마크 목록에 추가"한 채널 — collect()가 엑셀 목록과
            # union해 이후 메인 랭킹에도 추적한다(2026-07-12).
            c.execute("""
                CREATE TABLE IF NOT EXISTS discovered_channels (
                    username TEXT PRIMARY KEY,
                    name TEXT,
                    added_at TEXT
                )
            """)
            # "영상 안 올라오는" 죽은 채널 — 엑셀 원본은 안 건드리고 여기에 넣어
            # collect()가 추적에서 제외한다(소프트 삭제, 복구 가능, 2026-07-12).
            c.execute("""
                CREATE TABLE IF NOT EXISTS removed_channels (
                    username TEXT PRIMARY KEY,
                    name TEXT,
                    removed_at TEXT
                )
            """)
            # 발굴 피드(누적 모드 시 유지) — 단일행 JSON.
            c.execute("""
                CREATE TABLE IF NOT EXISTS discovery_feed (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    items_json TEXT NOT NULL,
                    updated_at TEXT
                )
            """)
            # "같은 주제 모아보기"(2026-07-13) — 수집 배치(캡션 묶음) 안에서 Gemini가
            # 같은 제품/주제로 판단한 항목끼리 group_id를 공유한다. platform 컬럼을
            # 처음부터 둬 유튜브·틱톡 랭킹이 나중에 붙어도 스키마 변경 없이 그대로
            # 크로스플랫폼 그룹핑에 편입된다(source_candidates의 platform 관례 재사용).
            c.execute("""
                CREATE TABLE IF NOT EXISTS topic_groups (
                    platform TEXT NOT NULL DEFAULT 'instagram',
                    shortcode TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    tagged_at TEXT,
                    PRIMARY KEY (platform, shortcode)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_topic_groups_group ON topic_groups(group_id)")
            # 렌더 포인트 원장(2026-07-17, 자동매칭 고급효과 엔진 Task1) — 잔액을 컬럼에
            # 저장하지 않고 delta 누적합으로 계산(원장 방식). customer_id별 독립.
            c.execute("""
                CREATE TABLE IF NOT EXISTS points_ledger (
                    customer_id INTEGER NOT NULL,
                    delta INTEGER NOT NULL,
                    reason TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """)
            # 픽로그(2026-07-18, 트랙1) — 사장님이 고른 것/버린 것을 append-only로 남긴다.
            # 트랙7 LLM 심사의 취향 예시 + B전환 승인률 지표의 원천. 수정·삭제 없음.
            c.execute("""
                CREATE TABLE IF NOT EXISTS pick_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    job_id TEXT,
                    stage TEXT NOT NULL,
                    candidates_json TEXT,
                    picked TEXT,
                    rejected TEXT,
                    edit_diff TEXT,
                    ts TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_pick_events "
                      "ON pick_events(customer_id, id DESC)")
            # 러너(2026-07-18, 트랙4) — 오케스트레이터 상태·원가·재개 스냅샷.
            c.execute("""
                CREATE TABLE IF NOT EXISTS auto_jobs (
                    id TEXT PRIMARY KEY,
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    mode TEXT NOT NULL DEFAULT 'C',
                    current_stage TEXT,
                    status TEXT NOT NULL,
                    stage_results_json TEXT,
                    cost_krw REAL NOT NULL DEFAULT 0,
                    mix_job_id TEXT,
                    unsure_reason TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_auto_jobs "
                      "ON auto_jobs(customer_id, created_at DESC)")
            # 기존 DB용 마이그레이션 — mix_jobs 자막제거 필드(2026-07-13).
            # 새 DB는 위 CREATE에 이미 있어 여기선 "이미 존재" 예외를 조용히 넘긴다.
            for col, ddl in (
                ("subtitle_removal", "INTEGER NOT NULL DEFAULT 0"),
                ("clean_video_path", "TEXT"),
                ("given_script", "TEXT"),  # 영상제작 2단계 given_script 모드(2026-07-13)
                ("headcopy_json", "TEXT"),  # 영상제작 5단계 꾸미기 헤드카피(2026-07-13)
                ("caption_style_json", "TEXT"),  # 영상제작 5단계 자막 스타일(2026-07-14)
                ("deco_json", "TEXT"),  # 영상제작 5단계 장식(워터마크·추가텍스트·오버레이·BGM, 2026-07-14)
                ("voice_json", "TEXT"),     # 영상제작 4단계 보이스 프리셋 선택 스냅샷(2026-07-14)
                ("script_structure_json", "TEXT"),  # 도서관→제작소 다리: 대본 구조분석 스냅샷(2026-07-15).
                                                    # ⚠️ 위 structure 컬럼과 다른 것 — 그건 template/free 모드 플래그.
                ("fx_plan", "TEXT"),        # 자동매칭 고급효과 엔진 Task5: 확정된 효과 배치 플랜(FullReel props).
                ("fx_status", "TEXT"),      # queued/done/failed — 렌더 진행 상태.
                ("fx_path", "TEXT"),        # 완성된 효과영상 경로.
                # 1단계 미리보기(2026-07-17). status(downloading→…→done)는 한 줄기라 여기에
                # 미리보기를 끼우면 최종 렌더 폴링과 서로를 오인한다 → 별도 컬럼으로 둔다.
                ("preview_status", "TEXT"),  # null|rendering|ready|failed
                ("preview_path", "TEXT"),
                ("preview_error", "TEXT"),
                # 5단계 썸네일(2026-07-17). 프레임 선택·텍스트 레이어·생성결과 갤러리를
                # job 하나에 딸린 부속물로 본다(설계 Q4) — headcopy_json과 같은 패턴.
                ("thumbnail_json", "TEXT"),
                # 6단계 SEO(2026-07-17) — 제목·설명·태그·해시태그·CTA + 키워드 실측치 일습.
                # 산출물이 한 덩어리로만 의미가 있어(제목만 바꿔도 태그·CTA와 어울려야 한다)
                # 필드를 쪼개지 않고 JSON 한 칸에 둔다.
                ("seo_json", "TEXT"),
                # 자막제거 소스단위 청소 캐시(2026-07-19). clean_sources_json={video_id: 클린경로}.
                # status/preview_status와 섞지 않는다 — 최종렌더 폴링과 오인 방지(선례 §6.1).
                ("clean_sources_json", "TEXT"),
                ("clean_status", "TEXT"),   # null|cleaning|ready|failed
                ("clean_error", "TEXT"),
                # 유료게이트(2026-07-19): 이 job의 렌더 크레딧을 낸 고객 — 실패 시 환불 귀속.
                ("customer_id", "INTEGER NOT NULL DEFAULT 0"),
                # render 크레딧을 과금한 날(YYYY-MM-DD, UTC). 비어있으면 '과금 안 함'.
                # run_mix_job이 실패 환불할 때 ①과금된 job인지 ②어느 날짜로 되돌릴지를 판단한다.
                # /api/mix/start만 채운다 — produce 2단계·auto_run 경로는 과금 안 해 비운다(오환불 방지).
                ("render_charge_day", "TEXT"),
                # 장면 우선 대본 모드(2026-07-20, Task6) — build_scene_first_plan 후보 저장.
                ("scene_first", "INTEGER NOT NULL DEFAULT 0"),
                ("candidates_json", "TEXT"),
            ):
                try:
                    c.execute(f"ALTER TABLE mix_jobs ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass  # 이미 존재
            # 부품은행(2026-07-21, Phase0) — S급 대본을 8버킷 부품으로 분해해 큐레이션.
            #  · pattern_source: 분해 원본 대본 1건.
            #  · pattern_item: 부품 1개. UNIQUE(bucket, canonical)로 같은 문구는 한 행에
            #    freq로 쌓는다(add_pattern_item의 dedup). source_ids_json에 출처 누적.
            #  · spine: 매크로 스파인(상황유형·비트체인·감정아크) 수동 시드용.
            c.execute("""
                CREATE TABLE IF NOT EXISTS pattern_source (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    url TEXT,
                    full_text TEXT,
                    product_category TEXT,
                    category_source TEXT,
                    perf_json TEXT,
                    structure_json TEXT,
                    spine_id INTEGER,
                    is_winner INTEGER DEFAULT 0,
                    created_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS pattern_item (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bucket TEXT,
                    text TEXT,
                    canonical TEXT,
                    slot_role TEXT,
                    source_ids_json TEXT,
                    freq INTEGER DEFAULT 1,
                    perf_score REAL DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    tags_json TEXT,
                    note TEXT,
                    is_negative INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT,
                    UNIQUE(bucket, canonical)
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_pattern_item_bucket "
                      "ON pattern_item(bucket, status)")
            c.execute("""
                CREATE TABLE IF NOT EXISTS spine (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    situation_type TEXT,
                    character_roles_json TEXT,
                    beat_chain_json TEXT,
                    emotion_arc TEXT,
                    appeal TEXT,
                    fit_categories_json TEXT,
                    source_count INTEGER DEFAULT 0,
                    perf_score REAL DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)
            self._migrate_personal_tables(c)
            self._ensure_paywall_schema(c)

    def _ensure_paywall_schema(self, c):
        """유료게이트(2026-07-19): customers에 plan/full_access_until/google_sub/email 없으면 추가,
        settings·usage 테이블 생성. 기존 라이브 DB 파괴 없이 ALTER로 이관(멱등)."""
        fresh_full_access = False
        for col, ddl in (
            ("plan", "TEXT NOT NULL DEFAULT 'free'"),
            ("full_access_until", "INTEGER NOT NULL DEFAULT 0"),
            ("google_sub", "TEXT"),
            ("email", "TEXT"),
        ):
            try:
                c.execute(f"ALTER TABLE customers ADD COLUMN {col} {ddl}")
                if col == "full_access_until":
                    fresh_full_access = True   # 이번에 처음 추가됨(=페이월 도입 마이그레이션)
            except sqlite3.OperationalError:
                pass  # 이미 존재
        if fresh_full_access:
            # ★페이월 도입 전부터 있던 기존 고객(cid≠0)은 full_access_until=0으로 백필돼
            #   즉시 ranking_only로 강등된다 → 무통보 차단 방지 위해 유예 체험 1회 부여.
            #   (같은 커서 c로 설정 읽기 — 중첩 커넥션 락 회피)
            row = c.execute("SELECT value FROM settings WHERE key='trial_days'").fetchone()
            try:
                trial_days = int(row[0]) if row else 7
            except (TypeError, ValueError):
                trial_days = 7
            grandfather_until = int(datetime.now(timezone.utc).timestamp()) + trial_days * 86400
            c.execute("UPDATE customers SET full_access_until=? WHERE id != 0 AND full_access_until=0",
                      (grandfather_until,))
        # settings 테이블은 _init_schema(line 396)가 이미 만든다 — 여기선 usage만.
        # google_sub 중복 계정 방지(부분 유니크 — NULL 제외). 데이터 무결성(Opus 리뷰).
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_google_sub ON customers(google_sub) "
                  "WHERE google_sub IS NOT NULL")
        c.execute("""CREATE TABLE IF NOT EXISTS usage (
                        customer_id INTEGER NOT NULL,
                        op TEXT NOT NULL,
                        day TEXT NOT NULL,
                        count INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (customer_id, op, day)
                    )""")

    def ensure_paywall_schema(self):
        """공개 래퍼(테스트·호출부용). __init__에서도 자동 실행되므로 보통 부를 필요 없다."""
        with self._conn() as c:
            self._ensure_paywall_schema(c)

    def _migrate_personal_tables(self, c):
        """기존 DB(customer_id 없는 구버전 saved/mix_basket/commented/script_wiki)를
        (customer_id, shortcode) 복합키 스키마로 재생성 이관(2026-07-13 멀티테넌시).
        SQLite는 PRIMARY KEY를 ALTER로 못 바꿔 테이블 재생성이 필요하다. 기존
        데이터는 전부 LEGACY_CUSTOMER_ID(0)로 귀속 — 기존 단일 관리자 계정의
        작업물을 그대로 보존한다. 이미 마이그레이션된 DB(customer_id 컬럼 있음)는
        조용히 건너뛴다(idempotent)."""
        for table in ("commented", "saved", "mix_basket", "script_wiki"):
            cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})").fetchall()]
            if "customer_id" in cols or not cols:
                continue  # 이미 마이그레이션됐거나(customer_id 있음) 테이블 자체가 없음
            tmp = f"{table}__legacy"
            c.execute(f"ALTER TABLE {table} RENAME TO {tmp}")
            # 원본 테이블의 컬럼 정의(이름+타입)를 그대로 복사하고 customer_id·
            # 복합PK만 새로 얹는다 — 컬럼 목록을 하드코딩하지 않아 타입 불일치 위험 없음.
            orig_cols = c.execute(f"PRAGMA table_info({tmp})").fetchall()
            col_defs = ", ".join(f'"{o[1]}" {o[2]}' for o in orig_cols)
            c.execute(f"""
                CREATE TABLE {table} (
                    customer_id INTEGER NOT NULL DEFAULT 0,
                    {col_defs},
                    PRIMARY KEY (customer_id, shortcode)
                )
            """)
            col_names = ", ".join(f'"{o[1]}"' for o in orig_cols)
            c.execute(f"INSERT INTO {table}(customer_id, {col_names}) "
                      f"SELECT {LEGACY_CUSTOMER_ID}, {col_names} FROM {tmp}")
            c.execute(f"DROP TABLE {tmp}")

    # ── 발굴 피드(누적 모드용) 저장 — last_run과 같은 단일행 JSON 패턴(2026-07-12) ──
    def save_discovery_feed(self, items):
        with self._conn() as c:
            c.execute(
                "INSERT INTO discovery_feed(id, items_json, updated_at) VALUES(1, ?, datetime('now')) "
                "ON CONFLICT(id) DO UPDATE SET items_json=excluded.items_json, updated_at=excluded.updated_at",
                (json.dumps(items, ensure_ascii=False),),
            )

    def load_discovery_feed(self):
        with self._conn() as c:
            row = c.execute("SELECT items_json, updated_at FROM discovery_feed WHERE id=1").fetchone()
        if not row:
            return [], None
        return json.loads(row[0]), row[1]

    # ── 발굴/정리 채널 관리(2026-07-12) ──
    def add_discovered(self, username, name=""):
        """발굴 채널을 벤치마크 목록에 추가(중복 시 이름 갱신). 제외목록에 있었다면 해제."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO discovered_channels(username, name, added_at) "
                "VALUES(?,?,datetime('now')) ON CONFLICT(username) DO UPDATE SET name=excluded.name",
                (username, name or username),
            )
            c.execute("DELETE FROM removed_channels WHERE username=?", (username,))

    def discovered_channels(self):
        """추가된 발굴 채널 [{name, username, followers, inpock}] (collect union용 메타 형태)."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT username, name FROM discovered_channels ORDER BY added_at DESC"
            ).fetchall()
        return [{"name": r[1] or r[0], "username": r[0], "followers": 0, "inpock": ""} for r in rows]

    def remove_channel(self, username, name=""):
        """죽은 채널을 추적 제외목록에 추가(소프트 삭제). 발굴목록에 있었다면 함께 제거."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO removed_channels(username, name, removed_at) "
                "VALUES(?,?,datetime('now')) ON CONFLICT(username) DO NOTHING",
                (username, name or username),
            )
            c.execute("DELETE FROM discovered_channels WHERE username=?", (username,))

    def restore_channel(self, username):
        """추적 제외 해제(되돌리기)."""
        with self._conn() as c:
            c.execute("DELETE FROM removed_channels WHERE username=?", (username,))

    def removed_usernames(self):
        """추적 제외된 username 집합(소문자 정규화)."""
        with self._conn() as c:
            rows = c.execute("SELECT username FROM removed_channels").fetchall()
        return {(r[0] or "").strip().lstrip("@").lower() for r in rows}

    def removed_list(self):
        """추적 제외 채널 목록 [{name, username, removed_at}]."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT username, name, removed_at FROM removed_channels ORDER BY removed_at DESC"
            ).fetchall()
        return [{"username": r[0], "name": r[1], "removed_at": r[2]} for r in rows]

    def prev_comments(self, shortcode):
        """가장 최근에 기록된 이 영상의 댓글수. 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT comments FROM snapshots WHERE shortcode=? ORDER BY id DESC LIMIT 1",
                (shortcode,),
            ).fetchone()
        return row[0] if row else None

    def prev_delta(self, shortcode):
        """가장 최근에 기록된 이 영상의 Δ. 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT delta FROM snapshots WHERE shortcode=? ORDER BY id DESC LIMIT 1",
                (shortcode,),
            ).fetchone()
        return row[0] if row else None

    def save_run(self, run_date, rows):
        """이번 수집 스냅샷 저장. rows: [{shortcode, username, comments, delta}]."""
        with self._conn() as c:
            c.executemany(
                "INSERT INTO snapshots(run_date, shortcode, username, comments, delta) "
                "VALUES(?,?,?,?,?)",
                [(run_date, r["shortcode"], r["username"], r["comments"], r["delta"]) for r in rows],
            )

    def save_drafts(self, shortcode, drafts):
        """댓글 후보 리스트 저장(덮어쓰기). drafts: list[str]."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO comment_drafts(shortcode, drafts_json) VALUES(?,?) "
                "ON CONFLICT(shortcode) DO UPDATE SET drafts_json=excluded.drafts_json",
                (shortcode, json.dumps(drafts, ensure_ascii=False)),
            )

    def get_drafts(self, shortcode):
        """저장된 댓글 후보 리스트. 없으면 []."""
        with self._conn() as c:
            row = c.execute(
                "SELECT drafts_json FROM comment_drafts WHERE shortcode=?", (shortcode,)
            ).fetchone()
        return json.loads(row[0]) if row else []

    def drafts_map(self, shortcodes):
        """여러 shortcode의 draft를 한 번에 dict{shortcode:list}로."""
        if not shortcodes:
            return {}
        qs = ",".join("?" * len(shortcodes))
        with self._conn() as c:
            rows = c.execute(
                f"SELECT shortcode, drafts_json FROM comment_drafts WHERE shortcode IN ({qs})",
                tuple(shortcodes),
            ).fetchall()
        return {sc: json.loads(dj) for sc, dj in rows}

    def mark_commented(self, shortcode, customer_id=LEGACY_CUSTOMER_ID):
        """소통 완료 기록 (중복 무시). customer_id별로 독립(2026-07-13 멀티테넌시)."""
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO commented(customer_id, shortcode, commented_at) "
                "VALUES(?, ?, datetime('now'))",
                (customer_id, shortcode),
            )

    def commented_set(self, customer_id=LEGACY_CUSTOMER_ID):
        """이 고객이 완료 처리한 shortcode 집합."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT shortcode FROM commented WHERE customer_id=?", (customer_id,)
            ).fetchall()
        return {r[0] for r in rows}

    def mark_saved(self, shortcode, customer_id=LEGACY_CUSTOMER_ID):
        """제품찾기 소스로 담기 (중복 무시). customer_id별로 독립."""
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO saved(customer_id, shortcode, saved_at) "
                "VALUES(?, ?, datetime('now'))",
                (customer_id, shortcode),
            )

    def saved_set(self, customer_id=LEGACY_CUSTOMER_ID):
        """이 고객이 담은 shortcode 집합."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT shortcode FROM saved WHERE customer_id=?", (customer_id,)
            ).fetchall()
        return {r[0] for r in rows}

    # ── 플랫폼 발굴 시드(유튜브 키워드/채널, 틱톡 계정) ──
    def add_seed(self, platform, kind, value):
        with self._conn() as c:
            c.execute("INSERT OR IGNORE INTO platform_seeds(platform, kind, value, added_at) "
                      "VALUES(?,?,?, datetime('now'))", (platform, kind, value))

    def remove_seed(self, platform, value):
        with self._conn() as c:
            c.execute("DELETE FROM platform_seeds WHERE platform=? AND value=?", (platform, value))

    def list_seeds(self, platform):
        with self._conn() as c:
            rows = c.execute("SELECT kind, value FROM platform_seeds WHERE platform=? "
                             "ORDER BY added_at ASC, rowid ASC", (platform,)).fetchall()
        return [{"kind": r[0], "value": r[1]} for r in rows]

    # ── 플랫폼 스코프 스냅샷(가속 계산용) ──
    def save_run_platform(self, platform, run_date, rows):
        with self._conn() as c:
            c.executemany(
                "INSERT INTO platform_snapshots(platform, run_date, shortcode, base, delta) "
                "VALUES(?,?,?,?,?)",
                [(platform, run_date, r["shortcode"], r.get("base"), r.get("delta")) for r in rows])

    def prev_base_platform(self, platform, shortcode):
        with self._conn() as c:
            row = c.execute("SELECT base FROM platform_snapshots WHERE platform=? AND shortcode=? "
                            "ORDER BY id DESC LIMIT 1", (platform, shortcode)).fetchone()
        return row[0] if row else None

    def prev_delta_platform(self, platform, shortcode):
        with self._conn() as c:
            row = c.execute("SELECT delta FROM platform_snapshots WHERE platform=? AND shortcode=? "
                            "ORDER BY id DESC LIMIT 1", (platform, shortcode)).fetchone()
        return row[0] if row else None

    # ── 플랫폼별 마지막 수집 결과(last_run 테이블에 platform 컬럼이 없어 settings 재사용) ──
    def save_last_run_platform(self, platform, items, collected_at):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?,?)",
                      (f"last_run::{platform}", json.dumps({"items": items, "collected_at": collected_at}, ensure_ascii=False)))

    def load_last_run_platform(self, platform):
        v = self.get_setting(f"last_run::{platform}", "")
        if not v:
            return [], None
        d = json.loads(v)
        return d.get("items", []), d.get("collected_at")

    # --- 영상 믹싱 바구니(mix basket) — 담기 토글로 채우고 mix.html이 소스로 사용 ---
    def mix_basket_toggle(self, shortcode, url="", thumbnail="", name="", caption="",
                          customer_id=LEGACY_CUSTOMER_ID):
        """이미 있으면 제거, 없으면 추가. 최종적으로 담겨있으면 True 반환.
        customer_id별로 독립된 바구니(2026-07-13 멀티테넌시)."""
        with self._conn() as c:
            exists = c.execute(
                "SELECT 1 FROM mix_basket WHERE customer_id=? AND shortcode=?",
                (customer_id, shortcode),
            ).fetchone()
            if exists:
                c.execute("DELETE FROM mix_basket WHERE customer_id=? AND shortcode=?",
                          (customer_id, shortcode))
                return False
            c.execute(
                "INSERT INTO mix_basket(customer_id, shortcode, url, thumbnail, name, caption, added_at) "
                "VALUES(?,?,?,?,?,?, datetime('now'))",
                (customer_id, shortcode, url, thumbnail, name, caption),
            )
            return True

    def mix_basket_add(self, shortcode, url="", thumbnail="", name="", caption="",
                       customer_id=LEGACY_CUSTOMER_ID):
        """있으면 그대로 두고(멱등), 없으면 추가. 새로 담겼으면 True.
        원클릭 담기(북마클릿·유저스크립트)용 — 토글과 달리 중복 클릭해도 안 빠진다."""
        with self._conn() as c:
            exists = c.execute(
                "SELECT 1 FROM mix_basket WHERE customer_id=? AND shortcode=?",
                (customer_id, shortcode),
            ).fetchone()
            if exists:
                return False
            c.execute(
                "INSERT INTO mix_basket(customer_id, shortcode, url, thumbnail, name, caption, added_at) "
                "VALUES(?,?,?,?,?,?, datetime('now'))",
                (customer_id, shortcode, url, thumbnail, name, caption),
            )
            return True

    def mix_basket_remove(self, shortcode, customer_id=LEGACY_CUSTOMER_ID):
        """바구니에서 제거."""
        with self._conn() as c:
            c.execute("DELETE FROM mix_basket WHERE customer_id=? AND shortcode=?",
                      (customer_id, shortcode))

    def mix_basket_list(self, customer_id=LEGACY_CUSTOMER_ID):
        """이 고객이 담은 순서(added_at)대로 항목 dict 리스트. meta_json은 풀어서 병합."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT shortcode, url, thumbnail, name, caption, meta_json FROM mix_basket "
                "WHERE customer_id=? ORDER BY added_at ASC, rowid ASC",
                (customer_id,),
            ).fetchall()
        out = []
        for r in rows:
            item = {"shortcode": r[0], "url": r[1], "thumbnail": r[2], "name": r[3], "caption": r[4]}
            if r[5]:
                try:
                    item["meta"] = json.loads(r[5])
                except (ValueError, TypeError):
                    pass
            out.append(item)
        return out

    def mix_basket_set_meta(self, shortcode, customer_id=LEGACY_CUSTOMER_ID,
                            thumbnail=None, name=None, meta=None):
        """원클릭 담기 항목의 보강값 갱신(백그라운드 enrich용). None인 필드는 안 건드린다.
        thumbnail/name은 기존 값이 빈 경우에만 채운다(사용자·유저스크립트가 준 값 우선).
        meta=dict면 JSON으로 직렬화해 meta_json에 저장."""
        with self._conn() as c:
            sets, args = [], []
            if thumbnail:
                sets.append("thumbnail=COALESCE(NULLIF(thumbnail,''), ?)")
                args.append(thumbnail)
            if name:
                sets.append("name=COALESCE(NULLIF(name,''), ?)")
                args.append(name)
            if meta:
                # ★기존 meta_json에 병합 — yt-dlp 추출이 간헐 실패(틱톡 rehydration 등)해도
                # 이전에 채운 조회수·댓글 등을 잃지 않게. 새 값만 덮어쓴다.
                row = c.execute("SELECT meta_json FROM mix_basket WHERE customer_id=? AND shortcode=?",
                                (customer_id, shortcode)).fetchone()
                merged = {}
                if row and row[0]:
                    try:
                        merged = json.loads(row[0])
                    except (ValueError, TypeError):
                        merged = {}
                merged.update(meta)
                sets.append("meta_json=?")
                args.append(json.dumps(merged, ensure_ascii=False))
            if not sets:
                return
            args += [customer_id, shortcode]
            c.execute(f"UPDATE mix_basket SET {', '.join(sets)} WHERE customer_id=? AND shortcode=?", args)

    def mix_basket_shortcodes(self, customer_id=LEGACY_CUSTOMER_ID):
        """이 고객의 바구니에 담긴 shortcode 집합(버튼 상태 표시용)."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT shortcode FROM mix_basket WHERE customer_id=?", (customer_id,)
            ).fetchall()
        return {r[0] for r in rows}

    def produce_pick_toggle(self, shortcode, customer_id=LEGACY_CUSTOMER_ID):
        """도서관 대본을 영상제작 목록에 담기/빼기 토글. 담기면 True."""
        with self._conn() as c:
            exists = c.execute(
                "SELECT 1 FROM produce_script_picks WHERE customer_id=? AND shortcode=?",
                (customer_id, shortcode),
            ).fetchone()
            if exists:
                c.execute("DELETE FROM produce_script_picks WHERE customer_id=? AND shortcode=?",
                          (customer_id, shortcode))
                return False
            c.execute(
                "INSERT INTO produce_script_picks(customer_id, shortcode, added_at) "
                "VALUES(?,?, datetime('now'))",
                (customer_id, shortcode),
            )
            return True

    def produce_pick_shortcodes(self, customer_id=LEGACY_CUSTOMER_ID):
        """영상제작에 담긴 도서관 대본 shortcode 집합."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT shortcode FROM produce_script_picks WHERE customer_id=?", (customer_id,)
            ).fetchall()
        return {r[0] for r in rows}

    def save_last_run(self, items, collected_at):
        """마지막 수집 결과 전체(items + 시각)를 저장. 단일 행 덮어쓰기."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO last_run(id, items_json, collected_at) VALUES(1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET items_json=excluded.items_json, "
                "collected_at=excluded.collected_at",
                (json.dumps(items, ensure_ascii=False), collected_at),
            )

    def load_last_run(self):
        """마지막 수집 결과 반환 → (items, collected_at). 없으면 ([], None)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT items_json, collected_at FROM last_run WHERE id=1"
            ).fetchone()
        if not row:
            return [], None
        return json.loads(row[0]), row[1]

    def save_script(self, shortcode, script, category=None):
        """대본추출 결과({segments, full_text}) 저장(덮어쓰기). category가 오면
        같이 저장(학습소재 통계의 그룹핑 키, 2026-07-13). 구조분석은 별도
        save_extract_structure()로 나중에 채워진다."""
        with self._conn() as c:
            if category is not None:
                c.execute(
                    "INSERT INTO script_extracts(shortcode, script_json, extracted_at, category) "
                    "VALUES(?,?,datetime('now'),?) ON CONFLICT(shortcode) DO UPDATE SET "
                    "script_json=excluded.script_json, extracted_at=excluded.extracted_at, "
                    "category=excluded.category",
                    (shortcode, json.dumps(script, ensure_ascii=False), category),
                )
            else:
                c.execute(
                    "INSERT INTO script_extracts(shortcode, script_json, extracted_at) "
                    "VALUES(?,?,datetime('now')) ON CONFLICT(shortcode) DO UPDATE SET "
                    "script_json=excluded.script_json, extracted_at=excluded.extracted_at",
                    (shortcode, json.dumps(script, ensure_ascii=False)),
                )

    def update_extract_category(self, shortcode, category, source=None):
        """category만 UPDATE — script_json은 절대 안 건드린다(2026-07-15, C-1 재발방지).
        원본 텍스트를 다시 쓰지 않고 카테고리 추론·교정만 반영할 때 이걸 쓸 것
        (save_script(code, cached, category=...)로 원본을 통째로 재기록하는 패턴 금지).

        source(2026-07-16): user|gemini|keyword — 어디서 온 값인지. 안 주면 종전대로
        category만 바꾸고 출처는 건드리지 않는다(기존 호출부 호환)."""
        with self._conn() as c:
            if source is None:
                c.execute("UPDATE script_extracts SET category=? WHERE shortcode=?",
                          (category, shortcode))
            else:
                c.execute("UPDATE script_extracts SET category=?, category_source=? "
                          "WHERE shortcode=?", (category, source, shortcode))

    def get_extract(self, shortcode):
        """대본추출 결과 + category + 구조분석(있으면). 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT script_json, extracted_at, category, structure_json, "
                "structure_analyzed_at, category_source "
                "FROM script_extracts WHERE shortcode=?",
                (shortcode,),
            ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        data["extracted_at"] = row[1]
        data["category"] = row[2]
        data["structure"] = json.loads(row[3]) if row[3] else None
        data["structure_analyzed_at"] = row[4]
        data["category_source"] = row[5]
        return data

    def save_extract_structure(self, shortcode, structure):
        """대본추출 항목에 구조분석 결과를 채운다(2026-07-13, 학습소재 통계 백필용)."""
        with self._conn() as c:
            c.execute(
                "UPDATE script_extracts SET structure_json=?, structure_analyzed_at=datetime('now') "
                "WHERE shortcode=?",
                (json.dumps(structure or {}, ensure_ascii=False), shortcode),
            )

    def mark_structure_attempted(self, shortcode):
        """구조분석을 시도했으나 결과를 못 얻었음을 기록한다(I-2, 2026-07-16).
        structure_json은 NULL로 그대로 둔다 — {}를 넣으면 extracts_missing_structure
        백필 대상에서 영구 제외되므로 절대 쓰지 않는다. 표식은 대화형 경로(캐시히트)가
        클릭마다 Gemini를 다시 부르는 것만 막고, 재시도 책임은 daily_batch가 갖는다."""
        with self._conn() as c:
            c.execute(
                "UPDATE script_extracts SET structure_analyzed_at=datetime('now') "
                "WHERE shortcode=?",
                (shortcode,),
            )

    def extracts_missing_structure(self, limit=100):
        """구조분석이 아직 안 된 대본추출 항목(카테고리 있는 것만 — 카테고리 없으면
        통계 그룹핑을 못 하므로 백필 대상에서 제외). full_text 없는 빈 항목도 제외."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT shortcode, script_json, category FROM script_extracts "
                "WHERE structure_json IS NULL AND category IS NOT NULL "
                "ORDER BY extracted_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for sc, script_json, category in rows:
            full_text = (json.loads(script_json) or {}).get("full_text", "")
            if full_text.strip():
                out.append({"shortcode": sc, "full_text": full_text, "category": category})
        return out

    _CHAR_ELEMENT_STRUCT_KEYS = {"hook": "hook_type"}  # element 이름 → structure_json 내 실제 키

    def element_raw_values(self, product_category, element, limit=500):
        """카테고리 안의 대본들에서 요소 하나의 자유서술 값들을 펼쳐서 반환.
        characters는 인물별 role을 각각 개별 값으로(한 대본에 여러 명 가능),
        나머지는 구조 필드 하나가 값 하나. 빈 값은 제외. hook 요소는 구조상
        실제 필드명이 hook_type이라(analyze_structure 출력 기준) 그걸 읽는다."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT shortcode, structure_json FROM script_wiki "
                "WHERE category=? AND structure_json IS NOT NULL "
                "UNION ALL "
                "SELECT shortcode, structure_json FROM script_extracts "
                "WHERE category=? AND structure_json IS NOT NULL LIMIT ?",
                (product_category, product_category, limit),
            ).fetchall()
        out = []
        seen = set()
        struct_key = self._CHAR_ELEMENT_STRUCT_KEYS.get(element, element)
        for sc, sj in rows:
            if sc in seen:
                continue
            seen.add(sc)
            st = json.loads(sj) or {}
            if element == "characters":
                for ch in (st.get("characters") or []):
                    role = (ch.get("role") or "").strip()
                    if role:
                        out.append(role)
            elif element == "devices":
                for d in (st.get("devices") or []):
                    d = (d if isinstance(d, str) else str(d)).strip()
                    if d:
                        out.append(d)
            else:
                val = (st.get(struct_key) or "").strip()
                if val:
                    out.append(val)
        return out

    def distinct_extract_categories(self):
        """학습 대상 카테고리 — 도서관(script_wiki)+대본추출(script_extracts) 합집합."""
        with self._conn() as c:
            return [r[0] for r in c.execute(
                "SELECT DISTINCT category FROM script_wiki WHERE category IS NOT NULL "
                "UNION SELECT DISTINCT category FROM script_extracts WHERE category IS NOT NULL"
            ).fetchall()]

    def save_element_category_stats(self, product_category, element, categories):
        """(product_category, element)의 기존 카테고리 통계를 지우고 새로 저장(덮어쓰기,
        누적 아님 — 매일 새벽 배치가 항상 최신 상태로 재계산)."""
        with self._conn() as c:
            c.execute(
                "DELETE FROM element_category_stats WHERE product_category=? AND element=?",
                (product_category, element),
            )
            for cat in categories:
                c.execute(
                    "INSERT INTO element_category_stats"
                    "(product_category, element, category_label, description, examples_json, "
                    "sample_count, computed_at) VALUES(?,?,?,?,?,?,datetime('now'))",
                    (product_category, element, cat.get("label", ""), cat.get("description", ""),
                     json.dumps(cat.get("examples") or [], ensure_ascii=False),
                     cat.get("sample_count", 0)),
                )

    def get_element_options(self, product_category):
        """이 카테고리의 요소별 학습된 옵션. {element: [{label, description}, ...]}.
        저장된 적 없는 요소는 빈 리스트(프론트가 드롭다운 숨김 처리에 씀)."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT element, category_label, description FROM element_category_stats "
                "WHERE product_category=? ORDER BY element, id",
                (product_category,),
            ).fetchall()
        out = {}
        for element, label, desc in rows:
            out.setdefault(element, []).append({"label": label, "description": desc})
        return out

    def get_category_detail(self, product_category, element, label):
        """특정 카테고리 하나의 설명+예시(생성 프롬프트에 제약으로 넣을 때 씀)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT description, examples_json FROM element_category_stats "
                "WHERE product_category=? AND element=? AND category_label=?",
                (product_category, element, label),
            ).fetchone()
        if not row:
            return None
        return {"description": row[0], "examples": json.loads(row[1] or "[]")}

    def save_draft(self, draft_id, customer_id, source_shortcode, parent_draft_id, hook,
                    script_text, edit_instruction, edit_mode):
        """초안 버전 하나 저장(항상 새 행 — 덮어쓰지 않음, 2026-07-13 디벨롭 루프)."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO script_drafts(draft_id, customer_id, source_shortcode, parent_draft_id, "
                "hook, script_text, edit_instruction, edit_mode, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,datetime('now'))",
                (draft_id, customer_id, source_shortcode, parent_draft_id, hook, script_text,
                 edit_instruction, edit_mode),
            )

    _DRAFT_COLS = ("draft_id, customer_id, source_shortcode, parent_draft_id, hook, "
                   "script_text, edit_instruction, edit_mode, created_at")

    def _draft_row(self, r):
        return {"draft_id": r[0], "customer_id": r[1], "source_shortcode": r[2],
                "parent_draft_id": r[3], "hook": r[4], "script_text": r[5],
                "edit_instruction": r[6], "edit_mode": r[7], "created_at": r[8]}

    def get_draft(self, draft_id):
        with self._conn() as c:
            r = c.execute(
                f"SELECT {self._DRAFT_COLS} FROM script_drafts WHERE draft_id=?", (draft_id,)
            ).fetchone()
        return self._draft_row(r) if r else None

    def get_draft_chain(self, draft_id):
        """draft_id부터 parent_draft_id를 거슬러 올라가 체인 전체를 오래된 순으로 반환."""
        chain = []
        cur = self.get_draft(draft_id)
        while cur:
            chain.append(cur)
            cur = self.get_draft(cur["parent_draft_id"]) if cur["parent_draft_id"] else None
        return list(reversed(chain))

    def get_script(self, shortcode):
        """저장된 대본추출 결과. 없으면 None. 있으면 {segments, full_text, extracted_at}."""
        with self._conn() as c:
            row = c.execute(
                "SELECT script_json, extracted_at FROM script_extracts WHERE shortcode=?",
                (shortcode,),
            ).fetchone()
        if not row:
            return None
        data = json.loads(row[0])
        data["extracted_at"] = row[1]
        return data

    # ── S급 대본 위키(도서관) — customer_id별로 독립(2026-07-13 멀티테넌시) ──
    def save_to_wiki(self, item, script, structure, customer_id=LEGACY_CUSTOMER_ID):
        """S급 대본을 위키에 저장(덮어쓰기). item=랭킹항목, script={full_text,segments},
        structure=구조분석 dict."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO script_wiki(customer_id, shortcode, name, category, source_url, full_text, "
                "segments_json, structure_json, followers, comments, density, thumbnail, saved_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime('now')) "
                "ON CONFLICT(customer_id, shortcode) DO UPDATE SET name=excluded.name, category=excluded.category, "
                "source_url=excluded.source_url, full_text=excluded.full_text, segments_json=excluded.segments_json, "
                "structure_json=excluded.structure_json, followers=excluded.followers, comments=excluded.comments, "
                "density=excluded.density, thumbnail=excluded.thumbnail, saved_at=excluded.saved_at",
                (customer_id, item.get("shortcode"), item.get("name") or item.get("username"), item.get("category"),
                 item.get("url") or item.get("shortcode"), script.get("full_text", ""),
                 json.dumps(script.get("segments", []), ensure_ascii=False),
                 json.dumps(structure or {}, ensure_ascii=False),
                 int(item.get("followers") or 0), int(item.get("comments") or 0),
                 float(item.get("density") or 0.0), item.get("thumbnail") or ""),
            )

    def _wiki_row(self, r):
        return {"shortcode": r[0], "name": r[1], "category": r[2], "source_url": r[3],
                "full_text": r[4], "segments": json.loads(r[5] or "[]"),
                "structure": json.loads(r[6] or "{}"), "followers": r[7], "comments": r[8],
                "density": r[9], "saved_at": r[10], "thumbnail": r[11] or ""}

    _WIKI_COLS = ("shortcode, name, category, source_url, full_text, segments_json, "
                  "structure_json, followers, comments, density, saved_at, thumbnail")

    def wiki_list(self, customer_id=LEGACY_CUSTOMER_ID):
        """이 고객이 위키에 담은 S급 대본 전체(최근 저장순)."""
        with self._conn() as c:
            rows = c.execute(
                f"SELECT {self._WIKI_COLS} FROM script_wiki WHERE customer_id=? ORDER BY saved_at DESC",
                (customer_id,),
            ).fetchall()
        return [self._wiki_row(r) for r in rows]

    def get_wiki_item(self, shortcode, customer_id=LEGACY_CUSTOMER_ID):
        with self._conn() as c:
            r = c.execute(
                f"SELECT {self._WIKI_COLS} FROM script_wiki WHERE customer_id=? AND shortcode=?",
                (customer_id, shortcode),
            ).fetchone()
        return self._wiki_row(r) if r else None

    def is_in_wiki(self, shortcode, customer_id=LEGACY_CUSTOMER_ID):
        with self._conn() as c:
            return c.execute(
                "SELECT 1 FROM script_wiki WHERE customer_id=? AND shortcode=?",
                (customer_id, shortcode),
            ).fetchone() is not None

    def remove_from_wiki(self, shortcode, customer_id=LEGACY_CUSTOMER_ID):
        with self._conn() as c:
            c.execute("DELETE FROM script_wiki WHERE customer_id=? AND shortcode=?",
                      (customer_id, shortcode))

    def wiki_shortcodes(self, customer_id=LEGACY_CUSTOMER_ID):
        """이 고객이 위키에 담은 shortcode 집합(카드에 '담김' 표시용)."""
        with self._conn() as c:
            return {r[0] for r in c.execute(
                "SELECT shortcode FROM script_wiki WHERE customer_id=?", (customer_id,)
            ).fetchall()}

    # ── 장면 라이브러리(재사용 짤 뱅크) — customer_id별로 독립(2026-07-15) ──
    _SCENE_COLS = ("id, asset_type, render_mode, media_path, poster_path, duration, "
                   "keep_original_audio, title, scene_desc, role, category, subject, "
                   "tone, keywords, source_kind, source_ref, source_start_frame, "
                   "source_origin, created_at")

    # 태그 편집으로 바꿀 수 있는 필드만. media_path/customer_id/id는 제외 —
    # 클라이언트가 준 값이 파일 경로가 되면 traversal이 열린다.
    _SCENE_EDITABLE = ("title", "scene_desc", "role", "category", "subject", "tone",
                       "keywords", "render_mode", "keep_original_audio")

    def _scene_row(self, r):
        return {"id": r[0], "asset_type": r[1], "render_mode": r[2], "media_path": r[3],
                "poster_path": r[4], "duration": r[5], "keep_original_audio": r[6],
                "title": r[7], "scene_desc": r[8], "role": r[9], "category": r[10],
                "subject": r[11], "tone": r[12],
                "keywords": [k for k in (r[13] or "").split(",") if k],
                "source_kind": r[14], "source_ref": r[15], "source_start_frame": r[16],
                "source_origin": r[17], "created_at": r[18]}

    @staticmethod
    def _scene_keywords(v):
        """keywords는 list로 주고받고 DB엔 콤마 문자열로 눕힌다."""
        if isinstance(v, (list, tuple)):
            return ",".join(str(k).strip() for k in v if str(k).strip())
        return (v or "").strip()

    def add_scene_asset(self, asset, customer_id=LEGACY_CUSTOMER_ID):
        """장면 자산 1개 저장 → 새 id. asset=다축 태그 dict(§4 스키마)."""
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO scene_assets(customer_id, asset_type, render_mode, media_path, "
                "poster_path, duration, keep_original_audio, title, scene_desc, role, category, "
                "subject, tone, keywords, source_kind, source_ref, source_start_frame, "
                "source_origin, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
                (customer_id, asset.get("asset_type"), asset.get("render_mode"),
                 asset.get("media_path"), asset.get("poster_path"),
                 float(asset.get("duration") or 0.0), int(asset.get("keep_original_audio") or 0),
                 asset.get("title"), asset.get("scene_desc"), asset.get("role"),
                 asset.get("category"), asset.get("subject"), asset.get("tone"),
                 self._scene_keywords(asset.get("keywords")),
                 asset.get("source_kind"), asset.get("source_ref"),
                 asset.get("source_start_frame"),
                 asset.get("source_origin") or "모름"),
            )
            return cur.lastrowid

    def list_scene_assets(self, customer_id=LEGACY_CUSTOMER_ID, asset_type=None,
                          category=None, role=None):
        """이 고객의 장면 자산(최근순). 타입·카테고리·역할로 좁힐 수 있다."""
        where, params = ["customer_id=?"], [customer_id]
        for col, val in (("asset_type", asset_type), ("category", category), ("role", role)):
            if val:
                where.append(f"{col}=?")
                params.append(val)
        with self._conn() as c:
            rows = c.execute(
                f"SELECT {self._SCENE_COLS} FROM scene_assets WHERE {' AND '.join(where)} "
                f"ORDER BY id DESC", params,
            ).fetchall()
        return [self._scene_row(r) for r in rows]

    def get_scene_asset(self, asset_id, customer_id=LEGACY_CUSTOMER_ID):
        with self._conn() as c:
            r = c.execute(
                f"SELECT {self._SCENE_COLS} FROM scene_assets WHERE id=? AND customer_id=?",
                (asset_id, customer_id),
            ).fetchone()
        return self._scene_row(r) if r else None

    def update_scene_asset(self, asset_id, tags, customer_id=LEGACY_CUSTOMER_ID):
        """다축 태그 편집. _SCENE_EDITABLE 화이트리스트 밖 필드는 조용히 무시.
        바꾼 게 있으면 True, 대상이 없거나(남의 것 포함) 바꿀 게 없으면 False."""
        sets, params = [], []
        for col in self._SCENE_EDITABLE:
            if col in tags:
                sets.append(f"{col}=?")
                params.append(self._scene_keywords(tags[col]) if col == "keywords"
                              else tags[col])
        if not sets:
            return False
        params += [asset_id, customer_id]
        with self._conn() as c:
            cur = c.execute(
                f"UPDATE scene_assets SET {', '.join(sets)} WHERE id=? AND customer_id=?",
                params,
            )
            return cur.rowcount > 0

    def delete_scene_asset(self, asset_id, customer_id=LEGACY_CUSTOMER_ID):
        with self._conn() as c:
            cur = c.execute("DELETE FROM scene_assets WHERE id=? AND customer_id=?",
                            (asset_id, customer_id))
            return cur.rowcount > 0

    def save_source_analysis(self, shortcode, keywords, frame_paths, analyzed_at):
        """영상 분석 결과(키워드+프레임 경로) 저장(덮어쓰기)."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO source_analysis(shortcode, keywords_json, frames_json, analyzed_at) "
                "VALUES(?,?,?,?) ON CONFLICT(shortcode) DO UPDATE SET "
                "keywords_json=excluded.keywords_json, frames_json=excluded.frames_json, "
                "analyzed_at=excluded.analyzed_at",
                (shortcode, json.dumps(keywords, ensure_ascii=False),
                 json.dumps(frame_paths, ensure_ascii=False), analyzed_at),
            )

    def get_source_analysis(self, shortcode):
        """저장된 영상 분석 결과. 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT keywords_json, frames_json, analyzed_at FROM source_analysis WHERE shortcode=?",
                (shortcode,),
            ).fetchone()
        if not row:
            return None
        return {"keywords": json.loads(row[0]), "frame_paths": json.loads(row[1]), "analyzed_at": row[2]}

    def save_vision_tags(self, shortcode, subject, keywords):
        """썸네일 비전 주제태그 저장(덮어쓰기). keywords: [str]."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO vision_tags(shortcode, subject, keywords_json, created_at) "
                "VALUES(?,?,?,datetime('now')) ON CONFLICT(shortcode) DO UPDATE SET "
                "subject=excluded.subject, keywords_json=excluded.keywords_json, created_at=excluded.created_at",
                (shortcode, subject or "", json.dumps(keywords or [], ensure_ascii=False)),
            )

    def get_vision_tags(self, shortcode):
        """저장된 주제태그 {subject, keywords}. 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT subject, keywords_json FROM vision_tags WHERE shortcode=?", (shortcode,)
            ).fetchone()
        if not row:
            return None
        return {"subject": row[0] or "", "keywords": json.loads(row[1] or "[]")}

    def vision_tags_map(self, shortcodes):
        """여러 shortcode → {shortcode: {subject, keywords}} (있는 것만). 읽기 결합용."""
        codes = [s for s in (shortcodes or []) if s]
        if not codes:
            return {}
        out = {}
        with self._conn() as c:
            # sqlite 변수 상한(999) 회피 — 청크로 조회.
            for i in range(0, len(codes), 400):
                chunk = codes[i:i + 400]
                q = "SELECT shortcode, subject, keywords_json FROM vision_tags WHERE shortcode IN (%s)" % \
                    ",".join("?" * len(chunk))
                for sc, subj, kj in c.execute(q, chunk).fetchall():
                    out[sc] = {"subject": subj or "", "keywords": json.loads(kj or "[]")}
        return out

    def save_candidates(self, shortcode, platform, candidates):
        """플랫폼 검색 후보 저장. candidates: [{url,title,thumbnail,source_lang?}].
        source_lang: 어떤 검색 언어로 찾았는지(ko/en/zh/ja/ru) — 해외 원본 영상을
        국내 재편집물과 구분해 보여주는 배지용(2026-07-10). 저장된 id 리스트 반환."""
        ids = []
        with self._conn() as c:
            for cand in candidates:
                cur = c.execute(
                    "INSERT INTO source_candidates(source_shortcode, platform, url, title, "
                    "thumbnail, similarity_score, collected_at, source_lang) VALUES(?,?,?,?,?,NULL,datetime('now'),?)",
                    (shortcode, platform, cand["url"], cand.get("title", ""), cand.get("thumbnail", ""),
                     cand.get("source_lang")),
                )
                ids.append(cur.lastrowid)
        return ids

    def get_candidates(self, shortcode):
        """이 소스에 대해 수집된 모든 후보(유사도 점수 내림차순, NULL은 뒤)."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, platform, url, title, thumbnail, similarity_score, source_lang FROM source_candidates "
                "WHERE source_shortcode=? ORDER BY (similarity_score IS NULL), similarity_score DESC",
                (shortcode,),
            ).fetchall()
        return [{"id": r[0], "platform": r[1], "url": r[2], "title": r[3],
                 "thumbnail": r[4], "similarity_score": r[5], "source_lang": r[6]} for r in rows]

    def update_candidate_score(self, candidate_id, score):
        """Gemini 검증 후 유사도 점수 갱신."""
        with self._conn() as c:
            c.execute("UPDATE source_candidates SET similarity_score=? WHERE id=?", (score, candidate_id))

    def save_to_pool(self, origin_shortcode, candidate_id):
        """확정 후보를 소스풀에 저장."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO source_pool(origin_shortcode, candidate_id, saved_at) "
                "VALUES(?,?,datetime('now'))",
                (origin_shortcode, candidate_id),
            )

    def pool_items(self):
        """소스풀 전체 — candidate 정보와 조인."""
        with self._conn() as c:
            rows = c.execute("""
                SELECT p.origin_shortcode, c.platform, c.url, c.title, c.thumbnail,
                       c.similarity_score, p.saved_at
                FROM source_pool p JOIN source_candidates c ON p.candidate_id = c.id
                ORDER BY p.saved_at DESC
            """).fetchall()
        return [{"origin_shortcode": r[0], "platform": r[1], "url": r[2], "title": r[3],
                 "thumbnail": r[4], "similarity_score": r[5], "saved_at": r[6]} for r in rows]

    @staticmethod
    def _pe_enc(v):
        """픽로그 값 저장 인코딩: str/None은 그대로, 그 외(dict·list·int)는 JSON."""
        if v is None or isinstance(v, str):
            return v
        return json.dumps(v, ensure_ascii=False)

    @staticmethod
    def _pe_dec(v):
        """저장 값 복원: JSON이면 파싱, 아니면(순수 문자열) 그대로."""
        if v is None:
            return None
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            return v

    def log_pick_event(self, stage, *, picked=None, rejected=None, candidates=None,
                       edit_diff=None, job_id=None, customer_id=LEGACY_CUSTOMER_ID):
        """픽/반려 한 건 append. 새 row id 반환. 부가 기능이라 최대한 관대하게 저장한다."""
        ts = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO pick_events(customer_id, job_id, stage, candidates_json, "
                "picked, rejected, edit_diff, ts) VALUES(?,?,?,?,?,?,?,?)",
                (customer_id, job_id or None, stage,
                 json.dumps(candidates, ensure_ascii=False) if candidates is not None else None,
                 self._pe_enc(picked), self._pe_enc(rejected), self._pe_enc(edit_diff), ts),
            )
            return cur.lastrowid

    def list_pick_events(self, *, customer_id=None, stage=None, limit=100):
        """최근(id 내림차순)부터. customer_id/stage 필터 선택. JSON 필드는 파싱해서 준다."""
        q = ("SELECT id, customer_id, job_id, stage, candidates_json, picked, "
             "rejected, edit_diff, ts FROM pick_events")
        conds, args = [], []
        if customer_id is not None:
            conds.append("customer_id=?")
            args.append(customer_id)
        if stage is not None:
            conds.append("stage=?")
            args.append(stage)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY id DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [
            {"id": r[0], "customer_id": r[1], "job_id": r[2], "stage": r[3],
             "candidates": self._pe_dec(r[4]), "picked": self._pe_dec(r[5]),
             "rejected": self._pe_dec(r[6]), "edit_diff": self._pe_dec(r[7]), "ts": r[8]}
            for r in rows
        ]

    _AUTO_SCALAR = ("current_stage", "status", "cost_krw", "mix_job_id", "unsure_reason")

    def create_auto_job(self, job_id, *, mode="C", customer_id=LEGACY_CUSTOMER_ID):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO auto_jobs(id, customer_id, mode, current_stage, status, "
                "stage_results_json, cost_krw, mix_job_id, unsure_reason, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, customer_id, mode, None, "running",
                 json.dumps({}), 0, None, None, now, now),
            )
        return job_id

    def get_auto_job(self, job_id):
        with self._conn() as c:
            r = c.execute(
                "SELECT id, customer_id, mode, current_stage, status, stage_results_json, "
                "cost_krw, mix_job_id, unsure_reason, created_at, updated_at "
                "FROM auto_jobs WHERE id=?", (job_id,)).fetchone()
        if not r:
            return None
        return {"id": r[0], "customer_id": r[1], "mode": r[2], "current_stage": r[3],
                "status": r[4], "stage_results": json.loads(r[5]) if r[5] else {},
                "cost_krw": r[6], "mix_job_id": r[7], "unsure_reason": r[8],
                "created_at": r[9], "updated_at": r[10]}

    def update_auto_job(self, job_id, **fields):
        sets, args = ["updated_at=?"], [datetime.now(timezone.utc).isoformat()]
        for k in self._AUTO_SCALAR:
            if k in fields:
                sets.append(f"{k}=?")
                args.append(fields[k])
        if "stage_results" in fields:
            sets.append("stage_results_json=?")
            args.append(json.dumps(fields["stage_results"], ensure_ascii=False))
        args.append(job_id)
        with self._conn() as c:
            c.execute(f"UPDATE auto_jobs SET {', '.join(sets)} WHERE id=?", args)

    def list_auto_jobs(self, *, customer_id=None, limit=50):
        q = ("SELECT id, customer_id, mode, current_stage, status, stage_results_json, "
             "cost_krw, mix_job_id, unsure_reason, created_at, updated_at FROM auto_jobs")
        conds, args = [], []
        if customer_id is not None:
            conds.append("customer_id=?")
            args.append(customer_id)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [{"id": r[0], "customer_id": r[1], "mode": r[2], "current_stage": r[3],
                 "status": r[4], "stage_results": json.loads(r[5]) if r[5] else {},
                 "cost_krw": r[6], "mix_job_id": r[7], "unsure_reason": r[8],
                 "created_at": r[9], "updated_at": r[10]} for r in rows]

    # ── 부품은행(2026-07-21, Phase0) ─────────────────────────────────────────
    def add_pattern_source(self, source, url, full_text, product_category=None,
                           category_source=None, perf=None, structure=None):
        """분해 원본 대본 1건 저장 → id. perf/structure는 dict→JSON."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO pattern_source(source, url, full_text, product_category, "
                "category_source, perf_json, structure_json, created_at) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (source, url, full_text, product_category, category_source,
                 json.dumps(perf, ensure_ascii=False) if perf is not None else None,
                 json.dumps(structure, ensure_ascii=False) if structure is not None else None,
                 now),
            )
            return cur.lastrowid

    def add_pattern_item(self, bucket, text, canonical=None, slot_role=None,
                         source_id=None, tags=None, is_negative=0):
        """부품 1개 저장 → 행 id. **dedup**: 같은 (bucket, canonical)이 이미 있으면
        새 행을 만들지 않고 freq+1 & source_ids_json에 source_id를 (중복 없이) append.
        canonical 미지정 시 text를 정규화(strip·소문자·공백1개)해 생성한다."""
        canon = canonical if canonical is not None else _normalize_canonical(text)
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            row = c.execute(
                "SELECT id, source_ids_json FROM pattern_item WHERE bucket=? AND canonical=?",
                (bucket, canon)).fetchone()
            if row:
                item_id, sids_json = row
                sids = json.loads(sids_json) if sids_json else []
                if source_id is not None and source_id not in sids:
                    sids.append(source_id)
                c.execute(
                    "UPDATE pattern_item SET freq=freq+1, source_ids_json=?, updated_at=? "
                    "WHERE id=?",
                    (json.dumps(sids), now, item_id))
                return item_id
            sids = [source_id] if source_id is not None else []
            cur = c.execute(
                "INSERT INTO pattern_item(bucket, text, canonical, slot_role, "
                "source_ids_json, freq, perf_score, status, tags_json, note, "
                "is_negative, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bucket, text, canon, slot_role, json.dumps(sids), 1, 0, "pending",
                 json.dumps(tags, ensure_ascii=False) if tags is not None else None,
                 None, is_negative, now, now))
            return cur.lastrowid

    _PATTERN_ORDER = {"perf": "perf_score DESC, freq DESC, id DESC",
                      "freq": "freq DESC, perf_score DESC, id DESC",
                      "recent": "updated_at DESC, id DESC"}

    def list_pattern_items(self, bucket=None, status=None, is_negative=None,
                           order_by="perf", limit=200):
        conds, args = [], []
        if bucket is not None:
            conds.append("bucket=?")
            args.append(bucket)
        if status is not None:
            conds.append("status=?")
            args.append(status)
        if is_negative is not None:
            conds.append("is_negative=?")
            args.append(is_negative)
        q = ("SELECT id, bucket, text, canonical, slot_role, source_ids_json, freq, "
             "perf_score, status, tags_json, note, is_negative, created_at, updated_at "
             "FROM pattern_item")
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY " + self._PATTERN_ORDER.get(order_by, self._PATTERN_ORDER["perf"])
        q += " LIMIT ?"
        args.append(limit)
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [
            {"id": r[0], "bucket": r[1], "text": r[2], "canonical": r[3],
             "slot_role": r[4], "source_ids": json.loads(r[5]) if r[5] else [],
             "freq": r[6], "perf_score": r[7], "status": r[8],
             "tags": json.loads(r[9]) if r[9] else None, "note": r[10],
             "is_negative": r[11], "created_at": r[12], "updated_at": r[13]}
            for r in rows
        ]

    def set_pattern_item_status(self, item_id, status):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute("UPDATE pattern_item SET status=?, updated_at=? WHERE id=?",
                      (status, now, item_id))

    def edit_pattern_item(self, item_id, text=None, tags=None, note=None):
        """부품 문구·태그·메모 교정. None인 필드는 안 건드린다."""
        sets, args = ["updated_at=?"], [datetime.now(timezone.utc).isoformat()]
        if text is not None:
            sets.append("text=?")
            args.append(text)
        if tags is not None:
            sets.append("tags_json=?")
            args.append(json.dumps(tags, ensure_ascii=False))
        if note is not None:
            sets.append("note=?")
            args.append(note)
        args.append(item_id)
        with self._conn() as c:
            c.execute(f"UPDATE pattern_item SET {', '.join(sets)} WHERE id=?", args)

    def add_spine(self, name, situation_type=None, character_roles=None,
                  beat_chain=None, emotion_arc=None, appeal=None,
                  fit_categories=None, status="pending"):
        """매크로 스파인 1건 저장 → id. 리스트 필드는 JSON."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO spine(name, situation_type, character_roles_json, "
                "beat_chain_json, emotion_arc, appeal, fit_categories_json, status, "
                "created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (name, situation_type,
                 json.dumps(character_roles, ensure_ascii=False) if character_roles is not None else None,
                 json.dumps(beat_chain, ensure_ascii=False) if beat_chain is not None else None,
                 emotion_arc, appeal,
                 json.dumps(fit_categories, ensure_ascii=False) if fit_categories is not None else None,
                 status, now, now))
            return cur.lastrowid

    def list_spines(self, status=None):
        q = ("SELECT id, name, situation_type, character_roles_json, beat_chain_json, "
             "emotion_arc, appeal, fit_categories_json, source_count, perf_score, "
             "status, created_at, updated_at FROM spine")
        args = []
        if status is not None:
            q += " WHERE status=?"
            args.append(status)
        q += " ORDER BY perf_score DESC, id DESC"
        with self._conn() as c:
            rows = c.execute(q, args).fetchall()
        return [
            {"id": r[0], "name": r[1], "situation_type": r[2],
             "character_roles": json.loads(r[3]) if r[3] else None,
             "beat_chain": json.loads(r[4]) if r[4] else None,
             "emotion_arc": r[5], "appeal": r[6],
             "fit_categories": json.loads(r[7]) if r[7] else None,
             "source_count": r[8], "perf_score": r[9], "status": r[10],
             "created_at": r[11], "updated_at": r[12]}
            for r in rows
        ]

    def set_spine_status(self, spine_id, status):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute("UPDATE spine SET status=?, updated_at=? WHERE id=?",
                      (status, now, spine_id))

    # --- Phase1: perf/spine 조회·저장 배관 ---
    def list_pattern_sources(self, category_source=None, only_missing_spine=False, limit=1000):
        """부품 소스 행 목록. category_source는 str 하나 또는 (튜플/리스트)로 IN 필터(R4).
        perf/structure는 JSON 디코드해서 준다."""
        where, params = [], []
        if category_source is not None:
            cs = (category_source,) if isinstance(category_source, str) else tuple(category_source)
            where.append("category_source IN (%s)" % ",".join("?" * len(cs)))
            params.extend(cs)
        if only_missing_spine:
            where.append("spine_id IS NULL")
        sql = ("SELECT id, source, url, full_text, product_category, category_source, "
               "perf_json, structure_json, spine_id, is_winner FROM pattern_source")
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
        return [
            {"id": r[0], "source": r[1], "url": r[2], "full_text": r[3],
             "product_category": r[4], "category_source": r[5],
             "perf": json.loads(r[6]) if r[6] else None,
             "structure": json.loads(r[7]) if r[7] else None,
             "spine_id": r[8], "is_winner": r[9]}
            for r in rows
        ]

    def set_pattern_source_perf(self, source_id, perf):
        with self._conn() as c:
            c.execute("UPDATE pattern_source SET perf_json=? WHERE id=?",
                      (json.dumps(perf, ensure_ascii=False) if perf is not None else None, source_id))

    def set_pattern_source_spine(self, source_id, spine_id):
        with self._conn() as c:
            c.execute("UPDATE pattern_source SET spine_id=? WHERE id=?", (spine_id, source_id))

    def pattern_source_url_exists(self, url):
        """자동흡수 dedup — 빈 url은 항상 False(존재 안 함으로 취급)."""
        if not url:
            return False
        with self._conn() as c:
            return c.execute("SELECT 1 FROM pattern_source WHERE url=? LIMIT 1",
                             (url,)).fetchone() is not None

    def set_pattern_item_perf(self, item_id, perf_score):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute("UPDATE pattern_item SET perf_score=?, updated_at=? WHERE id=?",
                      (float(perf_score), now, item_id))

    def update_spine_stats(self, spine_id, source_count, perf_score):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute("UPDATE spine SET source_count=?, perf_score=?, updated_at=? WHERE id=?",
                      (int(source_count), float(perf_score), now, spine_id))

    def pattern_bucket_counts(self):
        """{bucket: {pending, approved, rejected}} — is_negative=0만 집계.
        8버킷 전부를 0으로 초기화해 반환(UI 탭이 빈 버킷도 그려야 하므로)."""
        counts = {b: {"pending": 0, "approved": 0, "rejected": 0} for b in PATTERN_BUCKETS}
        with self._conn() as c:
            rows = c.execute(
                "SELECT bucket, status, COUNT(*) FROM pattern_item "
                "WHERE is_negative=0 GROUP BY bucket, status").fetchall()
        for bucket, status, n in rows:
            if bucket in counts and status in counts[bucket]:
                counts[bucket][status] = n
        return counts

    def create_mix_job(self, job_id, urls, target_seconds, structure,
                       subtitle_removal=False, given_script=None, script_structure=None,
                       customer_id=LEGACY_CUSTOMER_ID, render_charge_day=None,
                       scene_first=False):
        """새 믹스 job 생성. 초기 status='downloading'.
        given_script: 영상제작 2단계 — 확정 대본을 그대로 쓸 때(나레이션 자동생성 대신).
        script_structure: 도서관에서 딸려온 대본 구조분석 dict(2026-07-15). 뒷단계가 꺼내 쓸
            스냅샷으로 보관만 한다. ⚠️ 인자 structure(template/free 모드 플래그)와 다른 것.
        customer_id: 유료게이트 렌더 크레딧 귀속(2026-07-19). run_mix_job이 실패하면 이 cid로
            'render' 크레딧을 환불한다 — 실패했는데 크레딧만 날아가면 신뢰가 깨진다.
        scene_first: 장면 우선 대본 모드(2026-07-20, Task6) — _plan_and_tts가 build_scene_first_plan을
            타도록 하는 플래그. given_script을 구조계승 레퍼런스 텍스트로 재활용한다."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO mix_jobs(job_id, urls_json, target_seconds, structure, "
                "status, created_at, updated_at, subtitle_removal, given_script, "
                "script_structure_json, customer_id, render_charge_day, scene_first) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, json.dumps(urls, ensure_ascii=False), target_seconds,
                 structure, "downloading", now, now, 1 if subtitle_removal else 0,
                 given_script or None,
                 json.dumps(script_structure, ensure_ascii=False) if script_structure else None,
                 customer_id, render_charge_day, 1 if scene_first else 0),
            )

    def get_mix_job(self, job_id):
        """믹스 job 1건 → dict(JSON 필드는 파싱됨). 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT job_id, urls_json, target_seconds, structure, status, error, "
                "extract_json, edit_plan_json, video_path, created_at, updated_at, "
                "subtitle_removal, clean_video_path, given_script, headcopy_json, "
                "caption_style_json, voice_json, deco_json, script_structure_json, "
                "fx_plan, fx_status, fx_path, "
                "preview_status, preview_path, preview_error, "
                "thumbnail_json, seo_json, "
                "clean_sources_json, clean_status, clean_error, customer_id, render_charge_day, "
                "scene_first "
                "FROM mix_jobs WHERE job_id=?", (job_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "job_id": row[0], "urls": json.loads(row[1]), "target_seconds": row[2],
            "structure": row[3], "status": row[4], "error": row[5],
            "extract": json.loads(row[6]) if row[6] else None,
            "edit_plan": json.loads(row[7]) if row[7] else None,
            "video_path": row[8], "created_at": row[9], "updated_at": row[10],
            "subtitle_removal": bool(row[11]), "clean_video_path": row[12],
            "given_script": row[13],
            "headcopy": json.loads(row[14]) if row[14] else None,
            "caption_style": json.loads(row[15]) if row[15] else None,
            "voice": json.loads(row[16]) if row[16] else None,
            "deco": json.loads(row[17]) if row[17] else None,
            "script_structure": json.loads(row[18]) if row[18] else None,
            "fx_plan": json.loads(row[19]) if row[19] else None,
            "fx_status": row[20], "fx_path": row[21],
            "preview_status": row[22], "preview_path": row[23], "preview_error": row[24],
            "thumbnail": json.loads(row[25]) if row[25] else None,
            "seo": json.loads(row[26]) if row[26] else None,
            "clean_sources": json.loads(row[27]) if row[27] else None,
            "clean_status": row[28], "clean_error": row[29],
            "customer_id": row[30] if row[30] is not None else 0,
            "render_charge_day": row[31],
            "scene_first": bool(row[32]),
        }

    def update_mix_job(self, job_id, **fields):
        """status/error/extract/edit_plan/video_path 갱신(+updated_at). 객체는 JSON 직렬화."""
        cols, vals = [], []
        for k in ("status", "error", "video_path", "clean_video_path",
                  "fx_status", "fx_path",
                  # 1단계 미리보기(2026-07-17) — 여기 없으면 update_mix_job(preview_status=...)이
                  # 에러도 없이 조용히 무시된다(이 화이트리스트가 이 배선의 함정).
                  "preview_status", "preview_path", "preview_error",
                  "clean_status", "clean_error"):
            if k in fields:
                cols.append(f"{k}=?"); vals.append(fields[k])
        if "subtitle_removal" in fields:
            cols.append("subtitle_removal=?"); vals.append(1 if fields["subtitle_removal"] else 0)
        if "fx_plan" in fields:
            cols.append("fx_plan=?")
            vals.append(json.dumps(fields["fx_plan"], ensure_ascii=False) if fields["fx_plan"] else None)
        if "headcopy" in fields:
            cols.append("headcopy_json=?")
            vals.append(json.dumps(fields["headcopy"], ensure_ascii=False) if fields["headcopy"] else None)
        if "caption_style" in fields:
            cols.append("caption_style_json=?")
            vals.append(json.dumps(fields["caption_style"], ensure_ascii=False) if fields["caption_style"] else None)
        if "deco" in fields:
            cols.append("deco_json=?")
            vals.append(json.dumps(fields["deco"], ensure_ascii=False) if fields["deco"] else None)
        if "thumbnail" in fields:
            cols.append("thumbnail_json=?")
            vals.append(json.dumps(fields["thumbnail"], ensure_ascii=False)
                        if fields["thumbnail"] else None)
        if "voice" in fields:
            cols.append("voice_json=?")
            vals.append(json.dumps(fields["voice"], ensure_ascii=False) if fields["voice"] else None)
        if "seo" in fields:
            cols.append("seo_json=?")
            vals.append(json.dumps(fields["seo"], ensure_ascii=False) if fields["seo"] else None)
        if "clean_sources" in fields:
            cols.append("clean_sources_json=?")
            vals.append(json.dumps(fields["clean_sources"], ensure_ascii=False)
                        if fields["clean_sources"] else None)
        for k, col in (("extract", "extract_json"), ("edit_plan", "edit_plan_json")):
            if k in fields:
                cols.append(f"{col}=?")
                vals.append(json.dumps(fields[k], ensure_ascii=False) if fields[k] is not None else None)
        cols.append("updated_at=?"); vals.append(datetime.now(timezone.utc).isoformat())
        vals.append(job_id)
        with self._conn() as c:
            c.execute(f"UPDATE mix_jobs SET {', '.join(cols)} WHERE job_id=?", tuple(vals))

    def set_mix_candidates(self, job_id, candidates):
        """장면 우선 대본 모드(2026-07-20, Task6) — build_scene_first_plan 후보 목록 저장.
        각 candidate는 {"plan":.., "story":.., "score":.., "recommended":..} 형태(edit_plan.py)."""
        with self._conn() as c:
            c.execute("UPDATE mix_jobs SET candidates_json=? WHERE job_id=?",
                     (json.dumps(candidates, ensure_ascii=False), job_id))

    def get_mix_candidates(self, job_id):
        """저장된 장면 우선 후보 목록. 없으면 []."""
        with self._conn() as c:
            row = c.execute("SELECT candidates_json FROM mix_jobs WHERE job_id=?",
                            (job_id,)).fetchone()
        return json.loads(row[0]) if row and row[0] else []

    # ── 6단계 SEO 키워드 측정 캐시(2026-07-17) ──
    # job이 아니라 전역이다 — 키워드 측정치는 어느 영상이 쟀든 같은 값이고,
    # search.list가 100유닛인데 발굴과 키풀을 나눠 쓰므로 재측정은 순손실이다.
    def put_keyword_stats(self, stat):
        """키워드 측정치 upsert(keyword+region 충돌 시 덮어씀)."""
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO seo_keyword_stats "
                "(keyword, region, views_top, views_median, small_ratio, small_hits, "
                " hit_n, sample_n, top_titles_json, verdict, checked_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (stat["keyword"], stat.get("region") or "KR",
                 stat.get("views_top"),
                 stat.get("views_median"), stat.get("small_ratio"),
                 stat.get("small_hits"), stat.get("hit_n"), stat.get("sample_n"),
                 json.dumps(stat.get("top_titles") or [], ensure_ascii=False),
                 stat.get("verdict"),
                 datetime.now(timezone.utc).isoformat()),
            )

    def get_keyword_stats(self, keyword, region="KR", ttl_days=7):
        """TTL 안이면 측정치 dict, 없거나 낡았으면 None.
        낡은 측정치로 근거를 만들면 안 되므로 만료는 '없음'과 같이 다룬다."""
        with self._conn() as c:
            row = c.execute(
                "SELECT views_median, small_ratio, sample_n, top_titles_json, "
                "verdict, checked_at, views_top, small_hits, hit_n "
                "FROM seo_keyword_stats "
                "WHERE keyword=? AND region=?", (keyword, region),
            ).fetchone()
        if not row:
            return None
        try:
            checked = datetime.fromisoformat(row[5])
        except (TypeError, ValueError):
            return None
        if datetime.now(timezone.utc) - checked > timedelta(days=ttl_days):
            return None
        return {
            "keyword": keyword, "region": region,
            "views_top": row[6], "small_hits": row[7], "hit_n": row[8],
            "views_median": row[0], "small_ratio": row[1], "sample_n": row[2],
            "top_titles": json.loads(row[3]) if row[3] else [],
            "verdict": row[4], "checked_at": row[5],
        }

    # ── 제작소 작업파일(2026-07-17) ──────────────────────────
    def upsert_produce_work(self, work_id, state, job_id=_UNSET, step=_UNSET,
                            customer_id=LEGACY_CUSTOMER_ID):
        """작업 저장. work_id가 None이면 새로 만들어 반환한다.
        state: 클라이언트 작업상태 dict(sessionStorage.produce_work 스키마 + step).
        ★title은 서버가 state['script'] 앞 20자에서 뽑는다 — 클라이언트가 매번 보내면
        대본을 고쳤을 때 목록 이름과 어긋난다(스펙 §4.6).
        job_id/step: UPDATE 경로에서는 update_mix_job과 같은 관례 — 넘어온 필드만 갱신한다.
        안 넘기면(_UNSET) 기존 값 보존, job_id=None/step=0을 명시적으로 넘기면 그 값으로 덮어쓴다
        (부분 저장이 job_id·step을 조용히 리셋하던 버그 수정, 2026-07-17).
        남의 work_id로 넘어오면(다른 customer_id 소유) **아무것도 안 하고 None을 반환한다** —
        get_produce_work/delete_produce_work와 같은 결(예외를 던지지 않는다). UPDATE를
        `WHERE work_id=? AND customer_id=?`로 바꾸지 않는 이유: 매치 0건이면 아래 "되살리기"
        INSERT 폴백으로 떨어지는데, work_id는 전역 PRIMARY KEY라 남의 id로 INSERT하면
        IntegrityError(500)가 난다 — 그래서 UPDATE 전에 소유자를 먼저 물어본다(2026-07-17 재리뷰)."""
        now = datetime.now(timezone.utc).isoformat()
        title = (state.get("script") or "")[:20] if isinstance(state, dict) else ""
        payload = json.dumps(state, ensure_ascii=False)
        with self._conn() as c:
            if work_id:
                owner = c.execute(
                    "SELECT customer_id FROM produce_works WHERE work_id=?", (work_id,),
                ).fetchone()
                if owner and owner[0] != customer_id:
                    return None  # 남의 작업 — 건드리지 않는다(get/delete와 같은 결)
                cols, vals = ["title=?", "state_json=?"], [title, payload]
                if job_id is not _UNSET:
                    cols.append("job_id=?"); vals.append(job_id)
                if step is not _UNSET:
                    cols.append("step=?"); vals.append(step)
                cols.append("updated_at=?"); vals.append(now)
                vals.append(work_id)
                n = c.execute(
                    f"UPDATE produce_works SET {', '.join(cols)} WHERE work_id=?",
                    tuple(vals),
                ).rowcount
                if n:
                    return work_id
                # 서버 DB가 갈아엎였는데 브라우저가 옛 work_id를 들고 있는 경우 —
                # 조용히 버리지 말고 그 id로 되살린다(사장님 작업이 사라지는 것보다 낫다).
            wid = work_id or uuid.uuid4().hex[:12]
            ins_job_id = None if job_id is _UNSET else job_id
            ins_step = 0 if step is _UNSET else step
            c.execute(
                "INSERT INTO produce_works(work_id, customer_id, title, state_json, "
                "job_id, step, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (wid, customer_id, title, payload, ins_job_id, ins_step, now, now),
            )
            return wid

    def get_produce_work(self, work_id, customer_id=LEGACY_CUSTOMER_ID):
        """작업 1건 → dict(state는 파싱됨). 없거나 남의 것이면 None
        (scene_assets의 get_scene_asset과 같은 관례, 2026-07-17 리뷰 반영)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT work_id, title, state_json, job_id, step, created_at, updated_at "
                "FROM produce_works WHERE work_id=? AND customer_id=?", (work_id, customer_id),
            ).fetchone()
        if not row:
            return None
        return {"work_id": row[0], "title": row[1], "state": json.loads(row[2]),
                "job_id": row[3], "step": row[4], "created_at": row[5], "updated_at": row[6]}

    def list_produce_works(self, customer_id=LEGACY_CUSTOMER_ID, limit=20):
        """최근 작업 목록(updated_at DESC). state_json은 싣지 않는다 — 목록은 가벼워야 한다."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT work_id, title, step, job_id, updated_at FROM produce_works "
                "WHERE customer_id=? ORDER BY updated_at DESC, rowid DESC LIMIT ?",
                (customer_id, limit),
            ).fetchall()
        return [{"work_id": r[0], "title": r[1], "step": r[2], "job_id": r[3],
                 "updated_at": r[4]} for r in rows]

    def delete_produce_work(self, work_id, customer_id=LEGACY_CUSTOMER_ID):
        """지운다. 실제로 지워졌으면(내 것이었으면) True — 남의 것은 지워지지 않는다."""
        with self._conn() as c:
            return c.execute("DELETE FROM produce_works WHERE work_id=? AND customer_id=?",
                             (work_id, customer_id)).rowcount > 0

    # ── 보이스 프리셋(2026-07-14, 영상제작 4단계) ──
    def upsert_voice_preset(self, p):
        """보이스 프리셋 1건 upsert(preset_id 충돌 시 덮어씀).

        group_id: 같은 성우의 stable/natural/expressive 3톤을 묶는 키(미지정 시 preset_id로 대체).
        variant: stable(기본)/natural/expressive.
        naturalize_profile: 튜닝 작업대에서 동결한 자연화 프로파일 dict(없으면 None)."""
        now = datetime.now(timezone.utc).isoformat()
        prof = p.get("naturalize_profile")
        prof_json = json.dumps(prof, ensure_ascii=False) if prof is not None else None
        with self._conn() as c:
            c.execute("""
                INSERT INTO voice_presets(preset_id, name, one_liner, lang, archetype,
                    base_voice_id, model_id, voice_settings_json, default_speed,
                    default_silence_trim, sample_file, source_ref, origin, created_at,
                    group_id, variant, naturalize_profile_json, best)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(preset_id) DO UPDATE SET
                    name=excluded.name, one_liner=excluded.one_liner, lang=excluded.lang,
                    archetype=excluded.archetype, base_voice_id=excluded.base_voice_id,
                    model_id=excluded.model_id, voice_settings_json=excluded.voice_settings_json,
                    default_speed=excluded.default_speed,
                    default_silence_trim=excluded.default_silence_trim,
                    sample_file=excluded.sample_file, source_ref=excluded.source_ref,
                    origin=excluded.origin, group_id=excluded.group_id, variant=excluded.variant,
                    best=excluded.best,
                    -- 동결 프로파일만은 COALESCE로 보존한다. 다른 컬럼과 달리 이 값의 소스오브
                    -- 트루스는 JSON 파일이 아니라 튜닝 작업대(DB)다. excluded로 덮으면 startup
                    -- seed_presets가 매 재기동마다 NULL로 지워버린다(2026-07-15 리뷰 S2).
                    naturalize_profile_json=COALESCE(excluded.naturalize_profile_json,
                                                     voice_presets.naturalize_profile_json)
            """, (
                p["preset_id"], p["name"], p.get("one_liner"), p.get("lang", "KR"),
                p.get("archetype"), p["base_voice_id"],
                p.get("model_id", "eleven_multilingual_v2"),
                json.dumps(p.get("voice_settings", {}), ensure_ascii=False),
                p.get("default_speed", 1.0), p.get("default_silence_trim", "off"),
                p.get("sample_file"), p.get("source_ref"), p.get("origin", "curated"), now,
                p.get("group_id") or p["preset_id"], p.get("variant", "stable"), prof_json,
                int(bool(p.get("best", False))),
            ))

    def _row_to_preset(self, r):
        return {
            "preset_id": r[0], "name": r[1], "one_liner": r[2], "lang": r[3],
            "archetype": r[4], "base_voice_id": r[5], "model_id": r[6],
            "voice_settings": json.loads(r[7]) if r[7] else {},
            "default_speed": r[8], "default_silence_trim": r[9],
            "sample_file": r[10], "source_ref": r[11], "origin": r[12], "created_at": r[13],
            "group_id": r[14] or r[0], "variant": r[15] or "stable",
            "naturalize_profile": json.loads(r[16]) if len(r) > 16 and r[16] else None,
            "best": bool(r[17]) if len(r) > 17 else False,
        }

    def get_voice_preset(self, preset_id):
        with self._conn() as c:
            r = c.execute("SELECT preset_id,name,one_liner,lang,archetype,base_voice_id,"
                          "model_id,voice_settings_json,default_speed,default_silence_trim,"
                          "sample_file,source_ref,origin,created_at,group_id,variant,"
                          "naturalize_profile_json,best FROM voice_presets "
                          "WHERE preset_id=?", (preset_id,)).fetchone()
        return self._row_to_preset(r) if r else None

    def list_voice_presets(self, lang=None):
        q = ("SELECT preset_id,name,one_liner,lang,archetype,base_voice_id,model_id,"
             "voice_settings_json,default_speed,default_silence_trim,sample_file,"
             "source_ref,origin,created_at,group_id,variant,naturalize_profile_json,"
             "best FROM voice_presets")
        args = ()
        if lang:
            q += " WHERE lang=?"; args = (lang,)
        # 베스트가 앞, 그 안에선 기존 순서(삽입 시각) 유지. ★순서의 소스오브트루스는
        # 여기다 — assets/voice_presets.json의 배열 순서가 아니다(설계 §4.1의 실측).
        q += " ORDER BY best DESC, created_at"
        with self._conn() as c:
            return [self._row_to_preset(r) for r in c.execute(q, args).fetchall()]

    def prune_voice_presets(self, keep_preset_ids):
        """curated 파일에서 빠진(더 이상 없는) 프리셋을 DB에서 정리. keep_preset_ids에 없는 행 삭제.

        단 origin='curated' 행만 지운다 — 튜닝 작업대가 만든 프리셋(origin='tuned')은 JSON에
        없으므로, 무조건 삭제하면 재기동 때마다 동결한 프로파일이 행째로 날아간다(리뷰 S2)."""
        keep = list(keep_preset_ids)
        if not keep:
            return
        placeholders = ",".join("?" for _ in keep)
        with self._conn() as c:
            c.execute(f"DELETE FROM voice_presets WHERE origin='curated' "
                      f"AND preset_id NOT IN ({placeholders})", keep)

    def get_setting(self, key, default=None):
        """전역 설정값 조회(예: vmake_api_key). 없으면 default."""
        with self._conn() as c:
            row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        """전역 설정값 저장(upsert)."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO settings(key, value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    # ── 틱톡 키워드검색 남용/비용 가드 (2026-07-14) ──
    # 별도 테이블을 만들지 않고 settings에 네임스페이스 키로 눌러쓴다:
    #   tiktok_daily:{customer_id}:{YYYY-MM-DD} → 그 날 그 고객의 수집 횟수
    #   tiktok_spend:{YYYY-MM}                  → 그 달 전체 누적 지출($)
    # 날짜/월을 키에 넣어 두면 경계에서 자동으로 새 카운터가 시작(별도 리셋 불필요).
    def tiktok_daily_count(self, customer_id, day):
        """(고객, 날짜)의 오늘 틱톡 수집 횟수. 없으면 0."""
        raw = self.get_setting(f"tiktok_daily:{customer_id}:{day}", "0")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def bump_tiktok_daily(self, customer_id, day):
        """(고객, 날짜) 수집 횟수 +1 → 증가 후 값 반환(남용 방지 카운터)."""
        n = self.tiktok_daily_count(customer_id, day) + 1
        self.set_setting(f"tiktok_daily:{customer_id}:{day}", str(n))
        return n

    def tiktok_month_spend(self, month):
        """그 달(YYYY-MM) 틱톡 누적 지출($). 없으면 0.0."""
        raw = self.get_setting(f"tiktok_spend:{month}", "0")
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0

    def add_tiktok_spend(self, month, usd):
        """그 달 지출에 usd 누적 → 누적 후 값 반환(월예산 킬스위치 판단용)."""
        total = self.tiktok_month_spend(month) + float(usd)
        self.set_setting(f"tiktok_spend:{month}", repr(total))
        return total

    # ── 렌즈(SerpApi) 월 호출 카운트 (2026-07-14) ──
    # SerpApi 무료 100회/월. settings 네임스페이스 키 lens_count:{YYYY-MM}로 누적,
    # 월 경계에서 키가 달라 자동 리셋(틱톡 카운터와 동일 패턴).
    def lens_month_count(self, month):
        raw = self.get_setting(f"lens_count:{month}", "0")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    def bump_lens(self, month):
        n = self.lens_month_count(month) + 1
        self.set_setting(f"lens_count:{month}", str(n))
        return n

    # ── 고객 계정(2026-07-13 멀티테넌시) ──
    # 비밀번호는 pbkdf2-sha256(고객별 랜덤 솔트, 260,000회)로만 저장 — 평문/역가역
    # 방식 금지. 표준 hashlib만 사용해 외부 의존성을 늘리지 않는다.
    _PBKDF2_ITERATIONS = 260_000

    @staticmethod
    def _hash_password(password, salt):
        return hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), bytes.fromhex(salt), Store._PBKDF2_ITERATIONS
        ).hex()

    def create_customer(self, username, password, email=None, google_sub=None):
        """신규 고객 계정 생성. username 중복이면 ValueError. 성공 시 customer_id 반환.
        가입 즉시 무료 체험 시작: full_access_until = now + trial_days(설정, 기본7)*86400."""
        salt = secrets.token_hex(16)
        pw_hash = self._hash_password(password, salt)
        try:
            trial_days = int(self.get_setting("trial_days", 7))
        except (TypeError, ValueError):
            trial_days = 7
        full_access_until = int(datetime.now(timezone.utc).timestamp()) + trial_days * 86400
        with self._conn() as c:
            try:
                cur = c.execute(
                    "INSERT INTO customers(username, password_hash, salt, created_at, "
                    "plan, full_access_until, email, google_sub) "
                    "VALUES(?,?,?,datetime('now'),'free',?,?,?)",
                    (username, pw_hash, salt, full_access_until, email, google_sub),
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"이미 존재하는 아이디: {username}")
        return cur.lastrowid

    def get_or_create_by_google(self, google_sub, email=None):
        """구글 sub로 고객 조회, 없으면 신규 생성(가입시 체험 자동시작). customer_id 반환."""
        with self._conn() as c:
            row = c.execute("SELECT id FROM customers WHERE google_sub=?", (google_sub,)).fetchone()
        if row:
            return row[0]
        username = "g_" + str(google_sub)               # username 유니크 제약 충족용(절단X — sub 전체가 dedup 키)
        try:
            return self.create_customer(username, secrets.token_hex(16),
                                        email=email, google_sub=google_sub)
        except ValueError:
            with self._conn() as c:                     # 경합으로 방금 생성됐으면 재조회
                row = c.execute("SELECT id FROM customers WHERE google_sub=?", (google_sub,)).fetchone()
            return row[0] if row else None

    def verify_customer(self, username, password):
        """username/password 검증 → 성공 시 customer_id, 실패 시 None.
        타이밍 공격 방지를 위해 hmac.compare_digest로 해시 비교."""
        import hmac as _hmac
        with self._conn() as c:
            row = c.execute(
                "SELECT id, password_hash, salt FROM customers WHERE username=?", (username,)
            ).fetchone()
        if not row:
            return None
        customer_id, stored_hash, salt = row
        if _hmac.compare_digest(self._hash_password(password, salt), stored_hash):
            return customer_id
        return None

    def get_customer(self, customer_id):
        """customer_id → {id, username, created_at, plan, full_access_until, google_sub, email} 또는 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT id, username, created_at, plan, full_access_until, google_sub, email "
                "FROM customers WHERE id=?", (customer_id,)
            ).fetchone()
        if not row:
            return None
        return {"id": row[0], "username": row[1], "created_at": row[2],
                "plan": row[3] or "free", "full_access_until": row[4] or 0,
                "google_sub": row[5], "email": row[6]}

    def set_plan(self, customer_id, plan, full_access_until=None):
        """등급 변경. plan='pro'|'free'. full_access_until(epoch초)를 주면 함께 설정(체험창)."""
        with self._conn() as c:
            if full_access_until is None:
                c.execute("UPDATE customers SET plan=? WHERE id=?", (plan, customer_id))
            else:
                c.execute("UPDATE customers SET plan=?, full_access_until=? WHERE id=?",
                          (plan, int(full_access_until), customer_id))

    def all_settings(self):
        with self._conn() as c:
            rows = c.execute("SELECT key, value FROM settings").fetchall()
        return {k: v for k, v in rows}

    def list_customers(self):
        """관리자용 전체 고객 목록(사장님 cid0 제외). 최근 가입 먼저."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, username, email, plan, full_access_until, created_at "
                "FROM customers WHERE id != 0 ORDER BY id DESC"
            ).fetchall()
        return [{"id": r[0], "username": r[1], "email": r[2], "plan": r[3] or "free",
                 "full_access_until": r[4] or 0, "created_at": r[5]} for r in rows]

    # ── 유료게이트 일일 사용량(크레딧) ──
    def usage_incr(self, customer_id, op, day):
        """(customer_id, op, day) 카운트 +1, 증가 후 값 반환. customer_id=-1은 전역 집계."""
        with self._conn() as c:
            c.execute("INSERT INTO usage(customer_id,op,day,count) VALUES(?,?,?,1) "
                      "ON CONFLICT(customer_id,op,day) DO UPDATE SET count=count+1",
                      (customer_id, op, day))
            row = c.execute("SELECT count FROM usage WHERE customer_id=? AND op=? AND day=?",
                            (customer_id, op, day)).fetchone()
        return row[0] if row else 0

    def usage_get(self, customer_id, op, day):
        with self._conn() as c:
            row = c.execute("SELECT count FROM usage WHERE customer_id=? AND op=? AND day=?",
                            (customer_id, op, day)).fetchone()
        return row[0] if row else 0

    def usage_decr(self, customer_id, op, day):
        """(customer_id, op, day) 카운트 -1(0 밑으로 안 감), 감소 후 값 반환. 실패 환불용.
        예약(usage_incr)했다가 작업이 실패하면 이걸로 되돌린다 — points.refund와 대칭."""
        with self._conn() as c:
            c.execute("UPDATE usage SET count=MAX(0, count-1) "
                      "WHERE customer_id=? AND op=? AND day=?", (customer_id, op, day))
            row = c.execute("SELECT count FROM usage WHERE customer_id=? AND op=? AND day=?",
                            (customer_id, op, day)).fetchone()
        return row[0] if row else 0

    def refund_daily_credit(self, customer_id, op):
        """유료게이트 실패 환불: 예약했던 op 크레딧을 계정+전역에서 오늘자로 되돌린다.
        points.refund 대칭. 배경잡(run_mix_job)이 app import 없이 부를 수 있게 Store에 둔다."""
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.usage_decr(customer_id, op, day)
        self.usage_decr(-1, op, day)

    # ── 같은 주제 모아보기(2026-07-13) ──
    def save_topic_groups(self, mapping, platform="instagram"):
        """{shortcode: group_id} 저장(upsert). mapping이 비면 아무것도 안 함."""
        if not mapping:
            return
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.executemany(
                "INSERT INTO topic_groups(platform, shortcode, group_id, tagged_at) "
                "VALUES(?,?,?,?) ON CONFLICT(platform, shortcode) "
                "DO UPDATE SET group_id=excluded.group_id, tagged_at=excluded.tagged_at",
                [(platform, sc, gid, now) for sc, gid in mapping.items()],
            )

    def related_shortcodes(self, platform, shortcode):
        """주어진 (platform, shortcode)와 같은 주제 그룹인 다른 항목들
        [{platform, shortcode}] 반환(자기 자신 제외, 플랫폼 무관하게 전체 조회
        — 유튜브·틱톡 데이터가 붙으면 자동으로 같이 나온다)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT group_id FROM topic_groups WHERE platform=? AND shortcode=?",
                (platform, shortcode),
            ).fetchone()
            if not row:
                return []
            rows = c.execute(
                "SELECT platform, shortcode FROM topic_groups WHERE group_id=? "
                "AND NOT (platform=? AND shortcode=?)",
                (row[0], platform, shortcode),
            ).fetchall()
        return [{"platform": r[0], "shortcode": r[1]} for r in rows]

    # ── 렌더 포인트 원장(2026-07-17, 자동매칭 고급효과 엔진 Task1) ──
    # 잔액 컬럼을 따로 두지 않고 delta 누적합으로 계산하는 원장(ledger) 방식.
    # points.py가 이 두 메서드만 통해 테이블에 접근한다(SQL은 store.py에 캡슐화).
    def points_balance(self, customer_id):
        """이 고객의 현재 포인트 잔액(delta 합)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT COALESCE(SUM(delta),0) FROM points_ledger WHERE customer_id=?",
                (customer_id,),
            ).fetchone()
        return int(row[0])

    def points_add(self, customer_id, delta, reason=""):
        """원장에 한 줄 추가(양수=적립, 음수=차감). 잔액 컬럼이 없어 트랜잭션 충돌 없이 append-only."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO points_ledger(customer_id, delta, reason) VALUES(?,?,?)",
                (customer_id, delta, reason),
            )
