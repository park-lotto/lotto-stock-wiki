"""CLI to append a daily log entry and regenerate the dashboard HTML."""
import argparse
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path

from dashboard_common import DEFAULT_TRACK, entry_track
from render_dashboard import build_html

BASE = Path(__file__).resolve().parent
CONFIG_PATH = BASE / "config.json"
# log는 repo 안에 둔다 — 집↔회사가 git pull/push로 기록을 합치기 위함 (2026-08-10).
# repo 폴더가 없으면(경로 다른 PC) 옛 로컬 log로 폴백해 최소한 동작은 유지한다.
_REPO_LOG = Path(r"C:\Users\TheRose\Desktop\로또의 주식\pipeline\dashboard_log.json")
LOG_PATH = _REPO_LOG if _REPO_LOG.parent.is_dir() else BASE / "log.json"
HTML_PATH = BASE / "dashboard.html"
LOCK_PATH = BASE / "log.lock"


@contextmanager
def file_lock(timeout=10.0, stale=60.0):
    """log.json 읽기-수정-쓰기 구간을 직렬화한다.

    6개 세션이 동시에 add_entry를 호출하면 lost update가 난다.
    stale: 세션이 락을 쥔 채 죽은 경우(세션 리밋·강제종료) 이 초 뒤 자동 해제.

    ⚠️ 2026-07-15 리뷰(I-1)가 8/8 재현한 사고를 막는 세 가지 불변식 —
    페이즈2가 이 패턴을 복사해 공유 git 인덱스를 지키므로 여기서 정확해야 한다:
      1. stale 해제는 rename으로 원자화한다. 순진한 unlink는 상대가 방금 만든
         *살아있는* 락을 지운다(둘 다 임계구역 진입).
      2. 해제는 소유권을 확인한다. 무조건 unlink하면 내 락이 아니라 남의 락을 지운다.
      3. Windows는 열린/삭제대기 파일의 unlink·stat을 FileNotFoundError가 아니라
         PermissionError로 거절한다. 미포착 시 그 세션의 마감 기록이 통째로 유실된다.
    """
    start = time.monotonic()
    me = str(os.getpid())
    while True:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, me.encode())
            os.close(fd)
            break
        except FileExistsError:
            try:
                age = time.time() - LOCK_PATH.stat().st_mtime
            except (FileNotFoundError, PermissionError):
                continue  # 사라졌거나 삭제대기 — 그냥 재획득 시도
            if age > stale:
                # 원자적 stale 해제: rename에 성공한 프로세스만 지운다.
                victim = LOCK_PATH.with_name(f"{LOCK_PATH.name}.stale.{me}")
                try:
                    os.rename(LOCK_PATH, victim)
                    os.unlink(victim)
                except OSError:
                    pass  # 남이 먼저 이겼다(또는 살아났다) — 재시도
                continue
            if time.monotonic() - start > timeout:
                raise SystemExit("log.json 락 획득 실패 — 다른 세션이 쓰는 중. 잠시 후 재시도.")
            time.sleep(0.1)
    try:
        yield
    finally:
        try:
            if LOCK_PATH.read_text() == me:  # 내 락일 때만 해제
                LOCK_PATH.unlink()
        except (FileNotFoundError, PermissionError, OSError):
            pass


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def load_log():
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def save_log(log):
    tmp = LOG_PATH.with_name(LOG_PATH.name + ".tmp")
    tmp.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(LOG_PATH)


def prune(log, days=7):
    cutoff = (date.today() - timedelta(days=days - 1)).isoformat()
    return [e for e in log if e["date"] >= cutoff]


def category_names(config):
    return [c["name"] for c in config["categories"]]


def add_entry(category, summary, next_step, track=None):
    config = load_config()
    if category not in category_names(config):
        raise SystemExit(f"unknown category: {category!r}, must be one of {category_names(config)}")
    track = track or DEFAULT_TRACK
    today = date.today().isoformat()
    with file_lock():
        log = load_log()
        log = [
            e for e in log
            if not (e["date"] == today and e["category"] == category and entry_track(e) == track)
        ]
        log.append({
            "date": today,
            "category": category,
            "track": track,
            "summary": summary,
            "next": next_step,
        })
        log = prune(log)
        save_log(log)
    render()


def render():
    config = load_config()
    log = load_log()
    HTML_PATH.write_text(build_html(config, log), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add")
    add_p.add_argument("--category", required=True)
    add_p.add_argument("--summary", required=True)
    add_p.add_argument("--next", required=True, dest="next_step")
    add_p.add_argument("--track", default=None)

    sub.add_parser("render")

    args = parser.parse_args(argv)
    if args.command == "add":
        add_entry(args.category, args.summary, args.next_step, track=args.track)
    elif args.command == "render":
        render()


if __name__ == "__main__":
    main(sys.argv[1:])
