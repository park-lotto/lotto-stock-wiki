"""
telegram_digest.py — 날짜별 텔레그램 소스별 요약 뷰어 (Phase 1)

원자 ingest 전에 오늘 각 채널이 뭘 말했는지 한눈에 확인.

사용법:
    python -m pipeline.telegram_digest                       # 오늘
    python -m pipeline.telegram_digest --date 2026-06-09    # 특정 날짜
    python -m pipeline.telegram_digest --source 태린이      # 특정 소스만
    python -m pipeline.telegram_digest --ingest             # 요약 후 atomic ingest 실행
    python -m pipeline.telegram_digest --save               # 요약 파일 저장 (raw/telegram/{date}_digest.md)
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_TELEGRAM_DIR = _ROOT / "raw" / "telegram"
_SUMMARY_THRESHOLD = 500  # 이 글자수 이하면 원문 그대로

# Gemini 요약용 (긴 파일만)
_GEMINI_MODEL = "gemini-3.1-flash-lite"
_SUMMARY_PROMPT = """다음 텔레그램 메시지에서 핵심 투자 포인트만 3~5줄로 요약하라.
- 종목명·섹터·수치는 반드시 그대로 보존
- 말투: "~함", "~권고", "~예상" (간결하게)
- 불릿 포인트로 출력 (•)

텍스트:
{text}"""


def _load_gemini_client():
    try:
        from google import genai
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key:
            env_path = _ROOT / ".env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                        key = line.split("=", 1)[1].strip()
                        break
        return genai.Client(api_key=key) if key else None
    except ImportError:
        return None


def _summarize(text: str, client) -> str:
    if not client:
        return text[:400] + "..." if len(text) > 400 else text
    try:
        resp = client.models.generate_content(
            model=_GEMINI_MODEL,
            contents=_SUMMARY_PROMPT.format(text=text),
        )
        return resp.text.strip()
    except Exception:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(f"• {l}" for l in lines[:6])


def _extract_source_name(filename: str) -> str:
    """2026-06-09_태린이아빠_유튜브.md → 태린이아빠_유튜브"""
    stem = Path(filename).stem
    match = re.match(r"^\d{4}-\d{2}-\d{2}_(.+)$", stem)
    return match.group(1) if match else stem


def _collect_files(date: str, source_filter: str | None) -> list[Path]:
    """날짜에 해당하는 텔레그램 파일 목록"""
    pattern = f"{date}_*.md"
    files = sorted(_TELEGRAM_DIR.glob(pattern))
    if source_filter:
        files = [f for f in files if source_filter in f.name]
    # digest 파일 제외
    files = [f for f in files if "_digest" not in f.name]
    return files


def _build_digest(files: list[Path], client) -> list[dict]:
    entries = []
    for f in files:
        source = _extract_source_name(f.name)
        text = f.read_text(encoding="utf-8").strip()
        if not text:
            continue

        if len(text) <= _SUMMARY_THRESHOLD:
            summary = text
            mode = "원문"
        else:
            summary = _summarize(text, client)
            mode = "요약"

        entries.append({
            "source": source,
            "file": f.name,
            "mode": mode,
            "summary": summary,
            "char_count": len(text),
        })
    return entries


def _render(date: str, entries: list[dict]) -> str:
    lines = [
        f"=== {date} 텔레그램 소스별 요약 ===",
        f"총 {len(entries)}개 채널",
        "=" * 50,
    ]
    for e in entries:
        lines.append(f"\n[{e['source']}]  ({e['mode']} / {e['char_count']}자)")
        lines.append(f"파일: {e['file']}")
        lines.append("")
        for line in e["summary"].splitlines():
            lines.append(line)
        lines.append("")
    return "\n".join(lines)


def main():
    # Windows cp949 터미널에서 한글/특수문자 출력
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--source", default=None, help="소스 필터 (부분 일치)")
    parser.add_argument("--ingest", action="store_true", help="요약 후 atomic ingest 실행")
    parser.add_argument("--save", action="store_true", help="요약 결과를 파일로 저장")
    args = parser.parse_args()

    files = _collect_files(args.date, args.source)
    if not files:
        print(f"[telegram_digest] {args.date} 파일 없음 (source={args.source})")
        sys.exit(0)

    client = _load_gemini_client()
    entries = _build_digest(files, client)
    output = _render(args.date, entries)

    print(output)

    if args.save:
        save_path = _TELEGRAM_DIR / f"{args.date}_digest.md"
        save_path.write_text(output, encoding="utf-8")
        print(f"\n[저장] {save_path.name}")

    if args.ingest:
        import subprocess
        print("\n" + "─" * 50)
        print("[Phase 2] atomic ingest 시작...")
        subprocess.run(
            [sys.executable, "-m", "pipeline.atoms.ingest_pending",
             "--date", args.date, "--type", "telegram"],
            cwd=str(_ROOT),
        )


if __name__ == "__main__":
    main()
