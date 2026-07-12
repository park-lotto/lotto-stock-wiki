"""SQLite 수집 이력 저장소."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


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
            c.execute("""
                CREATE TABLE IF NOT EXISTS commented (
                    shortcode TEXT PRIMARY KEY,
                    commented_at TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS saved (
                    shortcode TEXT PRIMARY KEY,
                    saved_at TEXT
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
                    updated_at TEXT NOT NULL
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
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

    def mark_commented(self, shortcode):
        """소통 완료 기록 (중복 무시)."""
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO commented(shortcode, commented_at) "
                "VALUES(?, datetime('now'))",
                (shortcode,),
            )

    def commented_set(self):
        """완료된 shortcode 집합."""
        with self._conn() as c:
            rows = c.execute("SELECT shortcode FROM commented").fetchall()
        return {r[0] for r in rows}

    def mark_saved(self, shortcode):
        """제품찾기 소스로 담기 (중복 무시)."""
        with self._conn() as c:
            c.execute(
                "INSERT OR IGNORE INTO saved(shortcode, saved_at) VALUES(?, datetime('now'))",
                (shortcode,),
            )

    def saved_set(self):
        """담긴 shortcode 집합."""
        with self._conn() as c:
            rows = c.execute("SELECT shortcode FROM saved").fetchall()
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

    def save_script(self, shortcode, script):
        """대본추출 결과({segments, full_text}) 저장(덮어쓰기)."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO script_extracts(shortcode, script_json, extracted_at) "
                "VALUES(?,?,datetime('now')) ON CONFLICT(shortcode) DO UPDATE SET "
                "script_json=excluded.script_json, extracted_at=excluded.extracted_at",
                (shortcode, json.dumps(script, ensure_ascii=False)),
            )

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

    def create_mix_job(self, job_id, urls, target_seconds, structure):
        """새 믹스 job 생성. 초기 status='downloading'."""
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO mix_jobs(job_id, urls_json, target_seconds, structure, "
                "status, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
                (job_id, json.dumps(urls, ensure_ascii=False), target_seconds,
                 structure, "downloading", now, now),
            )

    def get_mix_job(self, job_id):
        """믹스 job 1건 → dict(JSON 필드는 파싱됨). 없으면 None."""
        with self._conn() as c:
            row = c.execute(
                "SELECT job_id, urls_json, target_seconds, structure, status, error, "
                "extract_json, edit_plan_json, video_path, created_at, updated_at "
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
        }

    def update_mix_job(self, job_id, **fields):
        """status/error/extract/edit_plan/video_path 갱신(+updated_at). 객체는 JSON 직렬화."""
        cols, vals = [], []
        for k in ("status", "error", "video_path"):
            if k in fields:
                cols.append(f"{k}=?"); vals.append(fields[k])
        for k, col in (("extract", "extract_json"), ("edit_plan", "edit_plan_json")):
            if k in fields:
                cols.append(f"{col}=?")
                vals.append(json.dumps(fields[k], ensure_ascii=False) if fields[k] is not None else None)
        cols.append("updated_at=?"); vals.append(datetime.now(timezone.utc).isoformat())
        vals.append(job_id)
        with self._conn() as c:
            c.execute(f"UPDATE mix_jobs SET {', '.join(cols)} WHERE job_id=?", tuple(vals))

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
