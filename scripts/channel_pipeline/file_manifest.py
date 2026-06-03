"""
channel_pipeline/file_manifest.py — 오늘 처리할 raw 파일 목록 수집
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent.parent
INBOX = ROOT / "raw" / "inbox"

CHANNEL_DIRS = {
    "telegram": INBOX / "telegram",
    "blog":     INBOX / "blog",
    "report":   INBOX / "report",
    "yt":       INBOX / "youtube",
}

# 레거시 경로 (기존 raw/ 루트에 쌓이는 파일들)
LEGACY_PATHS = {
    "telegram": ROOT / "raw" / "telegram",
    "report":   ROOT / "raw" / "report" / "요약",
    "blog":     ROOT / "raw" / "naver_premium",
    "yt":       ROOT / "raw" / "yt",
}


def get_manifest(run_date: str | None = None, days_back: int = 1) -> dict[str, list[str]]:
    """오늘 날짜 기준으로 각 채널 inbox의 파일 목록 반환.

    Args:
        run_date: YYYY-MM-DD 형식. None이면 오늘.
        days_back: 최근 N일 이내 파일만 수집.

    Returns:
        {"telegram": [...], "blog": [...], "report": [...], "yt": [...]}
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    date_obj = datetime.strptime(run_date, "%Y-%m-%d")
    cutoff = date_obj - timedelta(days=days_back)
    date_str = run_date.replace("-", "")  # 20260604

    manifest: dict[str, list[str]] = {ch: [] for ch in CHANNEL_DIRS}

    for channel, inbox_dir in CHANNEL_DIRS.items():
        # 1) inbox/ 우선
        if inbox_dir.exists():
            for f in sorted(inbox_dir.glob("*.md")):
                if _is_recent(f, cutoff):
                    manifest[channel].append(str(f))

        # 2) 레거시 경로 fallback
        legacy = LEGACY_PATHS.get(channel)
        if legacy and legacy.exists():
            for f in sorted(legacy.glob(f"*{date_str}*.md")):
                path_str = str(f)
                if path_str not in manifest[channel] and _is_recent(f, cutoff):
                    manifest[channel].append(path_str)
            # date_str 없는 파일도 수정일로 필터
            for f in sorted(legacy.glob("*.md")):
                path_str = str(f)
                if path_str not in manifest[channel] and _is_recent(f, cutoff):
                    manifest[channel].append(path_str)

    return manifest


def _is_recent(path: Path, cutoff: datetime) -> bool:
    try:
        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        return mtime >= cutoff
    except Exception:
        return False


def count_files(manifest: dict[str, list[str]]) -> int:
    return sum(len(v) for v in manifest.values())


def summarize(manifest: dict[str, list[str]]) -> str:
    lines = []
    for ch, files in manifest.items():
        lines.append(f"  {ch}: {len(files)}개")
        for f in files[:3]:
            lines.append(f"    - {Path(f).name}")
        if len(files) > 3:
            lines.append(f"    ... +{len(files)-3}개")
    return "\n".join(lines)
