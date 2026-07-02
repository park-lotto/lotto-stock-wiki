"""포스트형 소스(블로그·유튜브 등) 인제스트 — source config 파라미터화.

사용법:
    python -m pipeline.atoms.post_ingest --source blog --all [--date] [--limit] [--dry-run]
    python -m pipeline.atoms.post_ingest --source youtube --all
    python -m pipeline.atoms.post_ingest --source blog raw/blog/2026-06-21_xxx.md
"""
import re
import sys
import json
import argparse
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .db import init_db, migrate_db, insert_atom, get_conn
from .vector_db import embed_and_store
from .post_sources import source_config
from .post_questionnaire import extract_post, post_trust
from .telegram_questionnaire import questionnaire_to_atoms_tg
from .telegram_stance import deactivate_prior_stance
from . import profiles
from .profiles import daytrading_atoms, YOUTUBE_PROFILES

_ROOT = Path(__file__).parent.parent.parent
_Q_ROOT = _ROOT / "raw" / "post_q"
_FNAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_\d+_(.+)$")


def _parse_post_header(md_path: Path, header_label) -> dict:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    title = md_path.stem
    labels = header_label if isinstance(header_label, list) else [header_label]
    nm = title
    for lab in labels:
        m = re.search(rf"\*\*{re.escape(lab)}\*\*[:\s]+(.+)", text)
        if m:
            nm = m.group(1).strip()
            break
    nm = re.sub(r"\s*(블로그|유튜브)$", "", nm).strip()
    date = re.search(r"\*\*날짜\*\*[:\s]+(\d{4}-\d{2}-\d{2})", text)
    link = re.search(r"\*\*링크\*\*.*?(https?://[^\)\s]+)", text)
    d = date.group(1) if date else ""
    if not d:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", md_path.name)
        d = m.group(1) if m else ""
    return {"source_name": nm, "date": d, "link": link.group(1) if link else "", "title": title}


def get_done_post_files(source_type: str) -> set[str]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT raw_file FROM processed_files WHERE source_type=?
        UNION
        SELECT DISTINCT raw_file FROM atoms WHERE source_type=? AND raw_file IS NOT NULL
    """, (source_type, source_type)).fetchall()
    conn.close()
    return {Path(r[0]).name for r in rows if r[0]}


def _mark_processed(raw_file: str, source_type: str, atom_count: int) -> None:
    from datetime import datetime
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO processed_files (raw_file, source_type, atom_count, processed_at) VALUES (?,?,?,?)",
        (str(raw_file), source_type, atom_count, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_pending_post(cfg: dict, date_filter: str = None) -> list[Path]:
    src_dir = _ROOT / cfg["dir"]
    if not src_dir.exists():
        return []
    done = get_done_post_files(cfg["source_type"])
    files = []
    for f in sorted(src_dir.glob("*.md")):
        if "_analysis" in f.name:
            continue
        m = _FNAME.match(f.stem)
        if not m:
            # 영상/포스트 명명규칙 아닌 파일(스크립트 등) 제외
            continue
        if date_filter and m.group(1) != date_filter:
            continue
        if f.name in done:
            continue
        files.append(f)
    return sorted(files, reverse=True)


def _save_artifact(q: dict, source_type: str, date: str, title: str) -> None:
    out = _Q_ROOT / source_type / (date or "unknown")
    out.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w가-힣]+", "_", title)[:60]
    (out / f"{safe}.json").write_text(
        json.dumps(q, ensure_ascii=False, indent=2), encoding="utf-8")


def _extract_daytrading(md_path: Path) -> dict:
    """유튜브 데이트레이딩 프로필 전용 질문지 추출."""
    text = md_path.read_text(encoding="utf-8", errors="replace")
    from .atomizer import _get_client, _rotate_key
    from google.genai import types
    import json as _json
    prompt = YOUTUBE_PROFILES["데이트레이딩"]["prompt"]
    for _attempt in range(4):
        try:
            resp = _get_client().models.generate_content(
                model="gemini-3.1-flash-lite", contents=[text, prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json"),
            )
            return _json.loads(resp.text or "{}")
        except Exception as e:
            _m = str(e)
            if any(c in _m for c in ("429", "RESOURCE_EXHAUSTED")):
                if "PerDay" in _m or "limit: 500" in _m:
                    if _rotate_key():
                        continue
                else:
                    import time
                    time.sleep(62)
                    continue
            print(f"  [WARN] 데이트레이딩 추출 실패: {e}")
            return {}
    return {}


def ingest_post(md_path: Path, cfg: dict) -> int:
    h = _parse_post_header(md_path, cfg["header_label"])
    profile = profiles.youtube_channel_profile(h["source_name"]) if cfg["source_type"] == "youtube" else None

    atoms = None
    if profile == "데이트레이딩":
        q = _extract_daytrading(md_path)
        if q and q.get("trades"):
            _save_artifact(q, cfg["source_type"], h["date"], h["title"])
            meta = {
                "date": h["date"], "channel": h["source_name"],
                "source_type": cfg["source_type"], "trust": post_trust(cfg["registry"], h["source_name"]),
                "raw_file": str(md_path),
            }
            atoms = daytrading_atoms(q, meta)
        # else: 채널은 데이트레이딩 프로필이지만 이 영상은 매매 언급이 없음(예: 시황
        # 잡담 영상) — 하이브리드 오버라이드: 일반 POST_PROMPT 경로로 폴백한다.
        # (반대 방향 — 프로필 없는 채널인데 이 영상만 데이트레이딩 — 은 이번 스펙
        # 범위 밖. 대부분 채널이 profile=null이라 항상 일반 경로를 타므로 영향 없음.)

    if atoms is None:
        q = extract_post(md_path)
        if not q or not q.get("target_kind"):
            print(f"  [WARN] 빈/미라우팅 질문지: {md_path.name}")
            _mark_processed(md_path, cfg["source_type"], 0)
            return 0
        _save_artifact(q, cfg["source_type"], h["date"], h["title"])
        meta = {
            "date": h["date"], "channel": h["source_name"], "type": q["target_kind"],
            "source_type": cfg["source_type"], "trust": post_trust(cfg["registry"], h["source_name"]),
            "raw_file": str(md_path),
        }
        atoms = questionnaire_to_atoms_tg(q, meta)

    for a in atoms:
        if a.get("stance_key"):
            deactivate_prior_stance(a["stance_key"], keep_id=a["id"])
        insert_atom(a)
        try:
            embed_and_store(a)
        except Exception as e:
            print(f"  [WARN] embed 실패: {e}")
    _mark_processed(md_path, cfg["source_type"], len(atoms))
    return len(atoms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="blog | youtube")
    ap.add_argument("file", nargs="?")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--date", default=None)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    cfg = source_config(args.source)
    init_db(); migrate_db()

    if args.file:
        targets = [Path(args.file)]
    elif args.all:
        targets = get_pending_post(cfg, args.date)[: args.limit]
        print(f"미처리 {args.source}: {len(targets)}개\n")
    else:
        print("file 또는 --all 필요")
        return

    if args.dry_run:
        for f in targets:
            print(f"  {f.name} → {_parse_post_header(f, cfg['header_label'])['source_name']}")
        return

    total = 0
    for i, f in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {f.name}")
        n = ingest_post(f, cfg)
        total += n
        print(f"  → {n}개 원자")
    print(f"\n완료: {len(targets)}개, {total}개 원자")


if __name__ == "__main__":
    main()
