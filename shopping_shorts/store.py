"""SQLite 수집 이력 저장소."""
import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# 개인 행동 테이블(saved/mix_basket/commented/script_wiki)의 레거시(마이그레이션
# 이전) 데이터가 귀속되는 고객 ID(2026-07-13, 멀티테넌시). 기존 단일 관리자
# 계정의 데이터를 그대로 보존하기 위한 값 — 신규 고객은 1부터 발급.
LEGACY_CUSTOMER_ID = 0


class Store:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

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
            # 학습소재 통계용 확장(2026-07-13) — 위키 저장 여부와 무관하게 대본추출된
            # 모든 항목에 구조분석을 백필하기 위한 컬럼.
            for col, ddl in (("category", "TEXT"), ("structure_json", "TEXT"),
                              ("structure_analyzed_at", "TEXT")):
                try:
                    c.execute(f"ALTER TABLE script_extracts ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass  # 이미 있으면(기존 DB) 무시
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
            # 썸네일 URL 보관(2026-07-15) — 우리믹스 대본선택 리스트가 <video> 첫 프레임에
            # 의존해 검은칸으로 보이던 문제. 저장 시점 URL을 남겨 <img>로 즉시 그린다.
            try:
                c.execute("ALTER TABLE script_wiki ADD COLUMN thumbnail TEXT")
            except sqlite3.OperationalError:
                pass  # 이미 있으면(기존 DB) 무시
            # 고객 계정(2026-07-13 멀티테넌시). 비밀번호는 pbkdf2-sha256(솔트별도)로만
            # 저장 — 평문 저장 금지.
            c.execute("""
                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    created_at TEXT
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
                    headcopy_json TEXT
                )
            """)
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
            for col, ddl in (("group_id", "TEXT"), ("variant", "TEXT NOT NULL DEFAULT 'stable'"),
                             ("naturalize_profile_json", "TEXT")):
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
            ):
                try:
                    c.execute(f"ALTER TABLE mix_jobs ADD COLUMN {col} {ddl}")
                except sqlite3.OperationalError:
                    pass  # 이미 존재
            self._migrate_personal_tables(c)

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

    def mix_basket_remove(self, shortcode, customer_id=LEGACY_CUSTOMER_ID):
        """바구니에서 제거."""
        with self._conn() as c:
            c.execute("DELETE FROM mix_basket WHERE customer_id=? AND shortcode=?",
                      (customer_id, shortcode))

    def mix_basket_list(self, customer_id=LEGACY_CUSTOMER_ID):
        """이 고객이 담은 순서(added_at)대로 항목 dict 리스트."""
        with self._conn() as c:
            rows = c.execute(
                "SELECT shortcode, url, thumbnail, name, caption FROM mix_basket "
                "WHERE customer_id=? ORDER BY added_at ASC, rowid ASC",
                (customer_id,),
            ).fetchall()
        return [
            {"shortcode": r[0], "url": r[1], "thumbnail": r[2], "name": r[3], "caption": r[4]}
            for r in rows
        ]

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

    def update_extract_category(self, shortcode, category):
        """category만 UPDATE — script_json은 절대 안 건드린다(2026-07-15, C-1 재발방지).
        원본 텍스트를 다시 쓰지 않고 카테고리 추론·교정만 반영할 때 이걸 쓸 것
        (save_script(code, cached, category=...)로 원본을 통째로 재기록하는 패턴 금지)."""
        with self._conn() as c:
            c.execute(
                "UPDATE script_extracts SET category=? WHERE shortcode=?",
                (category, shortcode),
            )

    def get_extract(self, shortcode):
        """대본추출 결과 + category + 구조분석(있으면). 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT script_json, extracted_at, category, structure_json, structure_analyzed_at "
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
        return data

    def save_extract_structure(self, shortcode, structure):
        """대본추출 항목에 구조분석 결과를 채운다(2026-07-13, 학습소재 통계 백필용)."""
        with self._conn() as c:
            c.execute(
                "UPDATE script_extracts SET structure_json=?, structure_analyzed_at=datetime('now') "
                "WHERE shortcode=?",
                (json.dumps(structure or {}, ensure_ascii=False), shortcode),
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
                   "tone, keywords, source_kind, source_ref, created_at")

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
                "source_kind": r[14], "source_ref": r[15], "created_at": r[16]}

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
                "subject, tone, keywords, source_kind, source_ref, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'))",
                (customer_id, asset.get("asset_type"), asset.get("render_mode"),
                 asset.get("media_path"), asset.get("poster_path"),
                 float(asset.get("duration") or 0.0), int(asset.get("keep_original_audio") or 0),
                 asset.get("title"), asset.get("scene_desc"), asset.get("role"),
                 asset.get("category"), asset.get("subject"), asset.get("tone"),
                 self._scene_keywords(asset.get("keywords")),
                 asset.get("source_kind"), asset.get("source_ref")),
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

    def create_mix_job(self, job_id, urls, target_seconds, structure,
                       subtitle_removal=False, given_script=None):
        """새 믹스 job 생성. 초기 status='downloading'.
        given_script: 영상제작 2단계 — 확정 대본을 그대로 쓸 때(나레이션 자동생성 대신)."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO mix_jobs(job_id, urls_json, target_seconds, structure, "
                "status, created_at, updated_at, subtitle_removal, given_script) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (job_id, json.dumps(urls, ensure_ascii=False), target_seconds,
                 structure, "downloading", now, now, 1 if subtitle_removal else 0,
                 given_script or None),
            )

    def get_mix_job(self, job_id):
        """믹스 job 1건 → dict(JSON 필드는 파싱됨). 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT job_id, urls_json, target_seconds, structure, status, error, "
                "extract_json, edit_plan_json, video_path, created_at, updated_at, "
                "subtitle_removal, clean_video_path, given_script, headcopy_json, "
                "caption_style_json, voice_json, deco_json "
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
        }

    def update_mix_job(self, job_id, **fields):
        """status/error/extract/edit_plan/video_path 갱신(+updated_at). 객체는 JSON 직렬화."""
        cols, vals = [], []
        for k in ("status", "error", "video_path", "clean_video_path"):
            if k in fields:
                cols.append(f"{k}=?"); vals.append(fields[k])
        if "subtitle_removal" in fields:
            cols.append("subtitle_removal=?"); vals.append(1 if fields["subtitle_removal"] else 0)
        if "headcopy" in fields:
            cols.append("headcopy_json=?")
            vals.append(json.dumps(fields["headcopy"], ensure_ascii=False) if fields["headcopy"] else None)
        if "caption_style" in fields:
            cols.append("caption_style_json=?")
            vals.append(json.dumps(fields["caption_style"], ensure_ascii=False) if fields["caption_style"] else None)
        if "deco" in fields:
            cols.append("deco_json=?")
            vals.append(json.dumps(fields["deco"], ensure_ascii=False) if fields["deco"] else None)
        if "voice" in fields:
            cols.append("voice_json=?")
            vals.append(json.dumps(fields["voice"], ensure_ascii=False) if fields["voice"] else None)
        for k, col in (("extract", "extract_json"), ("edit_plan", "edit_plan_json")):
            if k in fields:
                cols.append(f"{col}=?")
                vals.append(json.dumps(fields[k], ensure_ascii=False) if fields[k] is not None else None)
        cols.append("updated_at=?"); vals.append(datetime.now(timezone.utc).isoformat())
        vals.append(job_id)
        with self._conn() as c:
            c.execute(f"UPDATE mix_jobs SET {', '.join(cols)} WHERE job_id=?", tuple(vals))

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
                    group_id, variant, naturalize_profile_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(preset_id) DO UPDATE SET
                    name=excluded.name, one_liner=excluded.one_liner, lang=excluded.lang,
                    archetype=excluded.archetype, base_voice_id=excluded.base_voice_id,
                    model_id=excluded.model_id, voice_settings_json=excluded.voice_settings_json,
                    default_speed=excluded.default_speed,
                    default_silence_trim=excluded.default_silence_trim,
                    sample_file=excluded.sample_file, source_ref=excluded.source_ref,
                    origin=excluded.origin, group_id=excluded.group_id, variant=excluded.variant,
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
        }

    def get_voice_preset(self, preset_id):
        with self._conn() as c:
            r = c.execute("SELECT preset_id,name,one_liner,lang,archetype,base_voice_id,"
                          "model_id,voice_settings_json,default_speed,default_silence_trim,"
                          "sample_file,source_ref,origin,created_at,group_id,variant,"
                          "naturalize_profile_json FROM voice_presets "
                          "WHERE preset_id=?", (preset_id,)).fetchone()
        return self._row_to_preset(r) if r else None

    def list_voice_presets(self, lang=None):
        q = ("SELECT preset_id,name,one_liner,lang,archetype,base_voice_id,model_id,"
             "voice_settings_json,default_speed,default_silence_trim,sample_file,"
             "source_ref,origin,created_at,group_id,variant,naturalize_profile_json FROM voice_presets")
        args = ()
        if lang:
            q += " WHERE lang=?"; args = (lang,)
        q += " ORDER BY created_at"
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

    def create_customer(self, username, password):
        """신규 고객 계정 생성. username 중복이면 ValueError. 성공 시 customer_id 반환."""
        salt = secrets.token_hex(16)
        pw_hash = self._hash_password(password, salt)
        with self._conn() as c:
            try:
                cur = c.execute(
                    "INSERT INTO customers(username, password_hash, salt, created_at) "
                    "VALUES(?,?,?,datetime('now'))",
                    (username, pw_hash, salt),
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"이미 존재하는 아이디: {username}")
        return cur.lastrowid

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
        """customer_id → {id, username, created_at} 또는 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT id, username, created_at FROM customers WHERE id=?", (customer_id,)
            ).fetchone()
        return {"id": row[0], "username": row[1], "created_at": row[2]} if row else None

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
