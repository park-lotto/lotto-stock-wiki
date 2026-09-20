"""Trusted local operator CLI. Context flags are NOT authentication credentials."""
import argparse
import json
import sqlite3
import sys

from .catalog import Catalog
from .schema import AccessContext, LibraryConfig


def main(argv=None):
    parser = argparse.ArgumentParser(description="크리에이티브 라이브러리 읽기 전용 실사")
    parser.add_argument("--repo", required=True, help="코드·정적 파일의 명시 절대경로")
    parser.add_argument("--db", help="운영 DB의 명시 절대경로. 미지정 시 DB 어댑터 생략")
    parser.add_argument("--media-root", help="DB 미디어 파일의 명시 절대경로")
    parser.add_argument("--company", default="local")
    parser.add_argument("--tenant", help="로컬 운영자가 확인할 고객 ID")
    parser.add_argument("--admin", action="store_true", help="로컬 운영자의 회사 내 전체 자료 실사")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("list", "search"):
        cmd = sub.add_parser(name)
        if name == "search":
            cmd.add_argument("query")
        for flag in ("domain", "kind", "status"):
            cmd.add_argument("--" + flag)
        cmd.add_argument("--usable", action="store_true", help="검증된 사용 가능 항목만")
    sub.add_parser("get").add_argument("id")
    lookup = sub.add_parser("legacy")
    lookup.add_argument("source")
    lookup.add_argument("key")
    sub.add_parser("summary")
    args = parser.parse_args(argv)
    try:
        config = LibraryConfig(args.repo, args.db, args.media_root, args.company)
        access = AccessContext(company_id=args.company, tenant_id=args.tenant, is_admin=args.admin)
        catalog = Catalog.load(config, access)
        result = catalog.summary()
        rc = 2 if any(r.state == "error" for r in catalog.reports) else 0
        if args.command in ("get", "legacy"):
            item = catalog.get(args.id) if args.command == "get" else catalog.get_legacy(args.source, args.key)
            if item is None:
                result["error"] = "not_found_or_not_permitted"
                rc = 1
            else:
                result["item"] = catalog.item_dict(item)
        elif args.command in ("list", "search"):
            items = catalog.search(getattr(args, "query", ""), domain=args.domain, kind=args.kind,
                                   status=args.status, usable_only=args.usable)
            result["matched_items"] = len(items)
            result["items"] = [catalog.item_dict(i) for i in items]
    except (OSError, ValueError, sqlite3.Error) as error:
        result = {"error": type(error).__name__, "message": str(error)}
        rc = 2
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return rc
