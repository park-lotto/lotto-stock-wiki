from __future__ import annotations
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).parent.parent.parent
INBOX = ROOT / "raw" / "inbox"

_CHANNEL_SUBDIRS = {
    "telegram": "telegram",
    "blog":     "blog",
    "report":   "report",
    "yt":       "youtube",
}


def get_manifest(run_date: str | None = None, days_back: int = 1) -> dict[str, list[str]]:
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")
    cutoff = datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=days_back)
    # INBOX 참조를 함수 실행 시점에 읽어 monkeypatch 가능하게
    import scripts.channel_pipeline.manifest as _m
    inbox = _m.INBOX
    channel_dirs = {ch: inbox / subdir for ch, subdir in _CHANNEL_SUBDIRS.items()}
    manifest: dict[str, list[str]] = {ch: [] for ch in channel_dirs}
    for channel, inbox_dir in channel_dirs.items():
        if inbox_dir.exists():
            for f in sorted(inbox_dir.glob("*.md")):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime >= cutoff:
                        manifest[channel].append(str(f))
                except OSError:
                    continue
    return manifest


def total_files(manifest: dict[str, list[str]]) -> int:
    return sum(len(v) for v in manifest.values())
