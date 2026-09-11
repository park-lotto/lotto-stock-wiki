"""Operator CLI for the continuous effect-mining service."""

from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
from pathlib import Path

from shopping_shorts.effect_mining.db import MiningDB
from shopping_shorts.effect_mining.pipeline import MiningPipeline
from shopping_shorts.effect_mining.runner import (
    run_scheduler_loop,
    run_worker_loop,
    scheduler_tick,
    worker_tick,
)


DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data" / "effect_mining"


def _positive_int(raw):
    value = int(raw)
    if value <= 0:
        raise argparse.ArgumentTypeError("value must be positive")
    return value


def build_parser():
    parser = argparse.ArgumentParser(prog="effect-mining")
    parser.add_argument("--db", default=os.getenv("EFFECT_MINING_DB", str(DEFAULT_ROOT / "mining.db")))
    parser.add_argument("--media-root", default=os.getenv("EFFECT_MINING_MEDIA_ROOT",
                                                         str(DEFAULT_ROOT / "media")))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")

    add = sub.add_parser("add-source")
    add.add_argument("platform")
    add.add_argument("source_kind")
    add.add_argument("query")
    add.add_argument("--interval-sec", type=_positive_int, default=3600)
    add.add_argument("--disabled", action="store_true")

    schedule = sub.add_parser("schedule")
    schedule.add_argument("--once", action="store_true")
    schedule.add_argument("--poll-sec", type=_positive_int, default=15)

    work = sub.add_parser("work")
    work.add_argument("--once", action="store_true")
    work.add_argument("--poll-sec", type=_positive_int, default=3)
    work.add_argument("--lease-sec", type=_positive_int, default=900)
    work.add_argument("--worker-id", default=f"{socket.gethostname()}-{os.getpid()}")
    work.add_argument("--tasks", default="")

    sub.add_parser("status")
    return parser


def _write(stdout, value):
    stdout.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv=None, stdout=None):
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)
    db = MiningDB(args.db)
    if args.command == "init":
        _write(stdout, {"ok": True, "db": str(Path(args.db))})
        return 0
    if args.command == "add-source":
        source_id = db.add_source(
            args.platform, args.source_kind, args.query, args.interval_sec,
            enabled=not args.disabled,
        )
        _write(stdout, {"ok": True, "source_id": source_id})
        return 0
    if args.command == "schedule":
        if args.once:
            _write(stdout, scheduler_tick(db))
            return 0
        run_scheduler_loop(db, poll_sec=args.poll_sec)
        return 0
    if args.command == "work":
        pipeline = MiningPipeline(db, args.media_root)
        tasks = [part.strip() for part in args.tasks.split(",") if part.strip()] or None
        if args.once:
            _write(stdout, worker_tick(
                db, pipeline, args.worker_id, tasks=tasks, lease_sec=args.lease_sec,
            ) or {"state": "idle"})
            return 0
        run_worker_loop(
            db, pipeline, args.worker_id, tasks=tasks,
            poll_sec=args.poll_sec, lease_sec=args.lease_sec,
        )
        return 0
    if args.command == "status":
        _write(stdout, db.status_summary())
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    raise SystemExit(main())
