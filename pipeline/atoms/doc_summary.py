"""
doc_summary.py — 문서(L2) AI 요약 생성 및 캐시

사용법 (직접 실행):
    python -m pipeline.atoms.doc_summary "youtube:2026-06-29_GODofIT.md"
"""
import os
import sys
import json
import sqlite3
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

# DB 경로는 db.py 패턴 그대로
DB_PATH = Path(__file__).parent.parent.parent / "pipeline" / "atoms" / "atoms.db"

CLAUDE_BIN = shutil.which("claude") or r"C:\Users\TheRose\.local\bin\claude.exe"
SUMMARY_TIMEOUT = 180  # 초

# ── 테이블 생성 (멱등) ────────────────────────────────────────────

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS doc_summaries (
    doc_key       TEXT PRIMARY KEY,
    category      TEXT,
    source_name   TEXT,
    doc_title     TEXT,
    doc_date      TEXT,
    tldr          TEXT,
    summary3      TEXT,
    market_view   TEXT,
    market_reason TEXT,
    stocks_json   TEXT,
    seeds_json    TEXT,
    highlights_json TEXT,
    atom_count    INTEGER,
    generated_at  TEXT,
    model         TEXT DEFAULT 'claude-cli'
);
"""

# 기존 DB 멱등 마이그레이션 (이미 테이블이 있으면 컬럼만 추가)
_ALTER_COLS = [
    ("highlights_json", "TEXT"),
]

_CREATE_IDX_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_ds_category ON doc_summaries(category);",
    "CREATE INDEX IF NOT EXISTS idx_ds_source   ON doc_summaries(source_name);",
    "CREATE INDEX IF NOT EXISTS idx_ds_date     ON doc_summaries(doc_date);",
]


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_table():
    """doc_summaries 테이블 + 인덱스 멱등 생성 + 신규 컬럼 마이그레이션."""
    conn = _get_conn()
    conn.executescript(_CREATE_SQL + "\n".join(_CREATE_IDX_SQL))
    for name, decl in _ALTER_COLS:
        try:
            conn.execute(f"ALTER TABLE doc_summaries ADD COLUMN {name} {decl}")
        except sqlite3.OperationalError:
            pass  # 이미 존재
    conn.commit()
    conn.close()


# ── doc_key 파싱 ───────────────────────────────────────────────

def _parse_doc_key(doc_key: str) -> dict:
    """
    doc_key 파싱 → category / source_name / date / raw_basename 반환.
    형식:
      youtube:{basename}  →  category=youtube
      report:{basename}   →  category=report
      telegram:{source}:{date}  →  category=telegram
    """
    parts = doc_key.split(":", 2)
    if len(parts) < 2:
        raise ValueError(f"잘못된 doc_key 형식: {doc_key}")

    category = parts[0].lower()
    if category == "telegram":
        # telegram:{source_name}:{date}
        if len(parts) < 3:
            raise ValueError(f"telegram doc_key는 3파트 필요: {doc_key}")
        return {
            "category": "telegram",
            "source_name": parts[1],
            "date": parts[2],
            "raw_basename": None,
        }
    else:
        # youtube:{basename} or report:{basename}
        basename = parts[1]
        return {
            "category": category,
            "source_name": None,  # raw_file에서 추출
            "date": None,
            "raw_basename": basename,
        }


def _source_type_to_category(st: str) -> str:
    if st in ("youtube", "yt"):
        return "youtube"
    if st == "telegram":
        return "telegram"
    if st in ("report", "blog", "news"):
        return "report"
    return st


# ── 원자 수집 ──────────────────────────────────────────────────

def _collect_atoms(doc_key: str) -> tuple[dict, list[dict]]:
    """
    doc_key 파싱 → 해당 문서 원자들 + 메타(category/source/title/date) 반환.
    반환: (meta_dict, atoms_list)
    """
    ensure_table()
    parsed = _parse_doc_key(doc_key)
    category = parsed["category"]

    conn = _get_conn()

    if category == "telegram":
        source_name = parsed["source_name"]
        date = parsed["date"]
        rows = conn.execute(
            """
            SELECT id, date, source_type, source_name, raw_file, sector, asset,
                   signal, content, stance_key, speaker, yt_timestamp, deeplink
            FROM atoms
            WHERE source_type = 'telegram'
              AND source_name = ?
              AND date = ?
            ORDER BY id
            """,
            (source_name, date),
        ).fetchall()
        conn.close()
        atoms = [dict(r) for r in rows]
        meta = {
            "category": "telegram",
            "source_name": source_name,
            "date": date,
            "title": f"{source_name} ({date})",
            "video_url": None,
        }

    else:
        # youtube or report — raw_file basename 매핑
        raw_basename = parsed["raw_basename"]
        # source_type 조건
        if category == "youtube":
            type_cond = "source_type IN ('youtube', 'yt')"
        else:
            type_cond = "source_type IN ('report', 'blog', 'news')"

        rows = conn.execute(
            f"""
            SELECT id, date, source_type, source_name, raw_file, sector, asset,
                   signal, content, stance_key, speaker, yt_timestamp, deeplink
            FROM atoms
            WHERE {type_cond}
              AND (raw_file = ? OR raw_file LIKE ? OR raw_file LIKE ?)
            ORDER BY yt_timestamp, id
            """,
            (raw_basename, f"%/{raw_basename}", f"%\\{raw_basename}"),
        ).fetchall()
        conn.close()
        atoms = [dict(r) for r in rows]

        # 메타 추출
        source_name = atoms[0]["source_name"] if atoms else ""
        date = atoms[0]["date"] if atoms else ""

        # 유튜브: deeplink에서 video_url 추출 (쿼리스트링 제거)
        video_url = None
        if category == "youtube" and atoms:
            dl = atoms[0].get("deeplink") or ""
            if dl:
                video_url = dl.split("&t=")[0]

        # 제목: basename에서 추정
        basename_no_ext = os.path.splitext(raw_basename)[0]
        meta = {
            "category": category,
            "source_name": source_name,
            "date": date,
            "title": basename_no_ext,
            "video_url": video_url,
        }

    return meta, atoms


# ── 프롬프트 빌드 ────────────────────────────────────────────────

def _build_prompt(meta: dict, atoms: list[dict]) -> str:
    category = meta["category"]
    source_name = meta["source_name"] or "알 수 없음"
    doc_title = meta["title"]
    doc_date = meta["date"] or ""

    # 발언 목록 구성 (놓치는 내용 최소화: 전체 발언, 본문도 넉넉히)
    lines = []
    for i, a in enumerate(atoms[:200], 1):  # 사실상 전체
        ts = a.get("yt_timestamp") or ""
        speaker = a.get("speaker") or a.get("source_name") or "?"
        stance = a.get("stance_key") or a.get("signal") or ""
        content = (a.get("content") or "")[:400]
        ts_part = f"[{ts}] " if ts else ""
        line = f"{i}. {ts_part}({stance}) {speaker}: {content}"
        lines.append(line)

    atoms_text = "\n".join(lines) if lines else "(원자 없음)"

    prompt = f"""너는 주식 유튜브 채널 "로또의 주식"의 인사이트 분석가다.
아래는 [{source_name}] 의 [{doc_title}] ({doc_date}) 에서 추출한 발언 전체다.
시청자가 원문을 안 봐도 **중요한 내용을 하나도 놓치지 않게** 충실히 요약하고,
내가 이걸로 유튜브 콘텐츠를 만들 수 있게 정리하라. 짧게 줄이려 하지 말고, 의미 있는 포인트는 다 담아라.

[발언 목록 — 총 {len(atoms)}개]
{atoms_text}

아래 JSON 스키마로만 답하라 (설명·마크다운·코드블록 금지, 순수 JSON만):
{{
  "tldr": "한 줄로 이 문서의 핵심 (25자 내외)",
  "summary3": ["주린이도 이해할 쉬운 핵심 문장들. 중요한 논점 수만큼, 보통 6~8개. 절대 3개로 줄이지 마라."],
  "highlights": [
    {{"topic":"놓치면 안 되는 구체 포인트 제목(수치·정책·일정·기업이벤트 등)","detail":"해당 발언의 구체 내용 1~2문장. 숫자·날짜·고유명사 살려서."}}
  ],
  "market_view": "bullish|bearish|neutral 중 하나",
  "market_reason": "왜 그렇게 보는지 2~3문장 (근거 구체적으로)",
  "stocks": [{{"name":"종목/섹터명","stance":"매수|매도|중립","reason":"근거 한줄"}}],
  "seeds": [{{"angle":"영상 소재 앵글","hook":"썸네일/후킹 문구"}}]
}}
규칙:
- summary3는 6~8개를 기본으로, 논점이 많으면 더 많아도 된다. 핵심을 빠뜨리지 마라.
- highlights는 구체적 사실(수치·정책·일정·기업명·실적 등)을 담은 항목을 5개 이상, 본문에 있는 만큼 충분히.
- stocks는 실제 언급된 종목·섹터를 빠짐없이.
- 발언에 없는 사실은 절대 지어내지 마라."""

    return prompt


# ── Claude 호출 ──────────────────────────────────────────────────

def _call_claude(prompt: str) -> dict:
    """Claude -p 헤드리스 호출. JSON 파싱 실패 시 1회 재시도."""
    if not (CLAUDE_BIN and os.path.exists(CLAUDE_BIN)):
        raise RuntimeError(f"claude 실행파일 없음: {CLAUDE_BIN}")

    cmd = [CLAUDE_BIN, "-p", prompt, "--permission-mode", "bypassPermissions"]

    def _run():
        proc = subprocess.run(
            cmd,
            cwd=str(Path(__file__).parent.parent.parent),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=SUMMARY_TIMEOUT,
        )
        return (proc.stdout or "").strip()

    def _parse_json(text: str) -> dict:
        # 마크다운 코드블록 제거
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            # 첫 줄(```json)과 마지막 줄(```) 제거
            inner = [l for l in lines[1:] if l.strip() != "```"]
            text = "\n".join(inner).strip()
        return json.loads(text)

    # 1차 시도
    raw = _run()
    try:
        return _parse_json(raw)
    except Exception:
        pass

    # 2차 시도 (프롬프트에 JSON만 출력 강조 추가)
    retry_prompt = prompt + "\n\n중요: 반드시 JSON 객체만. 다른 텍스트 절대 금지."
    cmd2 = [CLAUDE_BIN, "-p", retry_prompt, "--permission-mode", "bypassPermissions"]
    proc2 = subprocess.run(
        cmd2,
        cwd=str(Path(__file__).parent.parent.parent),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=SUMMARY_TIMEOUT,
    )
    raw2 = (proc2.stdout or "").strip()
    try:
        return _parse_json(raw2)
    except Exception:
        # 규칙기반 폴백
        return None  # 호출부에서 처리


# ── 폴백: stance 집계 ───────────────────────────────────────────

def _stance_fallback(meta: dict, atoms: list[dict]) -> dict:
    """Claude 호출 실패 시 stance 집계로 최소 요약 생성."""
    bullish = sum(1 for a in atoms if a.get("stance_key") in ("bullish", "catalyst"))
    bearish = sum(1 for a in atoms if a.get("stance_key") in ("bearish", "risk"))

    if bullish > bearish:
        market_view = "bullish"
    elif bearish > bullish:
        market_view = "bearish"
    else:
        market_view = "neutral"

    # 종목 집계
    stock_counts: dict = {}
    for a in atoms:
        asset = (a.get("asset") or "").strip()
        if asset and len(asset) > 1:
            stock_counts[asset] = stock_counts.get(asset, 0) + 1

    stocks = [{"name": k, "stance": "중립", "reason": f"언급 {v}회"}
              for k, v in sorted(stock_counts.items(), key=lambda x: -x[1])[:5]]

    return {
        "tldr": f"{meta['source_name']} 발언 요약 (자동 집계)",
        "summary3": [
            f"강세 신호 {bullish}건, 약세 신호 {bearish}건 감지",
            f"언급 종목: {', '.join(list(stock_counts.keys())[:3]) or '없음'}",
            "상세 내용은 발언 타임라인을 확인하세요",
        ],
        "market_view": market_view,
        "market_reason": f"강세 {bullish}건 vs 약세 {bearish}건 집계 기반",
        "stocks": stocks,
        "seeds": [],
    }


# ── 캐시 저장/로드 ──────────────────────────────────────────────

def _save_summary(doc_key: str, meta: dict, result: dict, atom_count: int):
    ensure_table()
    conn = _get_conn()
    summary3_text = "\n".join(result.get("summary3") or [])
    conn.execute(
        """
        INSERT OR REPLACE INTO doc_summaries
        (doc_key, category, source_name, doc_title, doc_date,
         tldr, summary3, market_view, market_reason,
         stocks_json, seeds_json, highlights_json, atom_count, generated_at, model)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            doc_key,
            meta.get("category"),
            meta.get("source_name"),
            meta.get("title"),
            meta.get("date"),
            result.get("tldr"),
            summary3_text,
            result.get("market_view"),
            result.get("market_reason"),
            json.dumps(result.get("stocks") or [], ensure_ascii=False),
            json.dumps(result.get("seeds") or [], ensure_ascii=False),
            json.dumps(result.get("highlights") or [], ensure_ascii=False),
            atom_count,
            datetime.now().isoformat(),
            "claude-cli",
        ),
    )
    conn.commit()
    conn.close()


def _load_summary(doc_key: str) -> dict | None:
    ensure_table()
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM doc_summaries WHERE doc_key = ?", (doc_key,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    # summary3 줄바꿈 → 리스트
    d["summary3"] = [l for l in (d.get("summary3") or "").split("\n") if l.strip()]
    # JSON 파싱
    for k in ("stocks_json", "seeds_json", "highlights_json"):
        try:
            d[k] = json.loads(d[k] or "[]")
        except Exception:
            d[k] = []
    return d


def _row_to_summary_dict(d: dict) -> dict:
    """DB 행 → API 응답용 summary 딕셔너리."""
    return {
        "tldr": d.get("tldr"),
        "summary3": d.get("summary3") or [],
        "market_view": d.get("market_view"),
        "market_reason": d.get("market_reason"),
        "stocks": d.get("stocks_json") or [],
        "seeds": d.get("seeds_json") or [],
        "highlights": d.get("highlights_json") or [],
        "generated_at": d.get("generated_at"),
        "atom_count": d.get("atom_count"),
    }


# ── 공개 API ────────────────────────────────────────────────────

def get_or_build_summary(doc_key: str, *, force: bool = False) -> dict:
    """
    캐시 있으면 즉시 반환. 없거나 force면 생성 → 캐시 → 반환.
    반환: summary dict (API 응답 형식)
    """
    if not force:
        cached = _load_summary(doc_key)
        if cached:
            return _row_to_summary_dict(cached)

    # 원자 수집
    meta, atoms = _collect_atoms(doc_key)
    atom_count = len(atoms)

    if atom_count == 0:
        # 원자 없으면 빈 폴백
        result = {
            "tldr": "원자 없음",
            "summary3": ["이 문서에서 추출된 원자가 없습니다"],
            "market_view": "neutral",
            "market_reason": "데이터 없음",
            "stocks": [],
            "seeds": [],
        }
    else:
        prompt = _build_prompt(meta, atoms)
        result = _call_claude(prompt)
        if result is None:
            result = _stance_fallback(meta, atoms)

    _save_summary(doc_key, meta, result, atom_count)
    return {
        "tldr": result.get("tldr"),
        "summary3": result.get("summary3") or [],
        "market_view": result.get("market_view"),
        "market_reason": result.get("market_reason"),
        "stocks": result.get("stocks") or [],
        "seeds": result.get("seeds") or [],
        "highlights": result.get("highlights") or [],
        "generated_at": datetime.now().isoformat(),
        "atom_count": atom_count,
    }


# ── CLI 진입점 ──────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("사용법: python -m pipeline.atoms.doc_summary <doc_key>")
        sys.exit(1)
    doc_key = sys.argv[1]
    force = "--force" in sys.argv
    result = get_or_build_summary(doc_key, force=force)
    print(json.dumps(result, ensure_ascii=False, indent=2))
