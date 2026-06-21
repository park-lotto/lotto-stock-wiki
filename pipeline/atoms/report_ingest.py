"""리포트 질문지 인제스트 오케스트레이터.

사용법:
    python -m pipeline.atoms.report_ingest raw/report/2026-06-19/xxx.md
    python -m pipeline.atoms.report_ingest --dir "C:/.../crawling_bot_data/2026-06-19/reports" --limit 5
"""
import json
import argparse
import tempfile
from pathlib import Path

from .pdf_ingest import _extract_pdf_url, _extract_meta, _download_pdf
from .questionnaire import extract_questionnaire, questionnaire_to_atoms
from .db import init_db, insert_atom
from .vector_db import embed_and_store

_Q_ROOT = Path(__file__).parent.parent.parent / "raw" / "report_q"


def _save_questionnaire(q: dict, meta: dict, stem: str) -> None:
    out_dir = _Q_ROOT / meta["date"]
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {"meta": meta, "questionnaire": q}
    (out_dir / f"{stem}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ingest_report(md_path: Path) -> int:
    url = _extract_pdf_url(md_path)
    if not url:
        print(f"  [SKIP] PDF URL 없음: {md_path.name}")
        return 0
    m = _extract_meta(md_path)
    meta = {"date": m["date"], "broker": m["broker"], "raw_file": str(md_path)}

    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / (md_path.stem + ".pdf")
        if not _download_pdf(url, pdf):
            return 0
        q = extract_questionnaire(pdf)

    if not q:
        print("  [WARN] 빈 질문지")
        return 0

    # 증권사명을 PDF 추출값으로 보강 (MD가 깨졌을 수 있음)
    if q.get("broker"):
        meta["broker"] = q["broker"]

    _save_questionnaire(q, meta, md_path.stem)
    atoms = questionnaire_to_atoms(q, meta)
    for a in atoms:
        insert_atom(a)
        try:
            embed_and_store(a)
        except Exception:
            pass
    return len(atoms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?")
    ap.add_argument("--dir")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    init_db()

    if args.file:
        targets = [Path(args.file)]
    elif args.dir:
        targets = sorted(Path(args.dir).glob("*.md"))[: args.limit]
    else:
        print("file 또는 --dir 필요")
        return

    total = 0
    for i, f in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {f.name}")
        n = ingest_report(f)
        total += n
        print(f"  → {n}개 원자")
    print(f"\n완료: {len(targets)}개 파일, {total}개 원자")


if __name__ == "__main__":
    main()
