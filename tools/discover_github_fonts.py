#!/usr/bin/env python3
"""GitHub에서 한글 OFL 폰트 후보를 찾고 원 제작/미러 후보를 구분해 기록한다."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "font_collection" / "manifests" / "github_discovery.json"
QUERIES = [
    "topic:korean-font",
    "korean font in:name,description,readme license:ofl-1.1",
    "hangul font in:name,description,readme license:ofl-1.1",
    "한글 폰트 in:name,description,readme license:ofl-1.1",
]
MIRROR_WORDS = re.compile(
    r"mirror|subset|webfont|merged|completion|deb package|redistribut|fork of|custom build",
    re.I,
)
FONT_WORDS = re.compile(r"korean|hangul|한글|폰트|font|typeface", re.I)


def main() -> int:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ShorttemFontCollector/1.0 (+local catalog research)",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    found = {}
    query_reports = []
    for query in QUERIES:
        r = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": query, "sort": "stars", "order": "desc", "per_page": 100},
            headers=headers,
            timeout=90,
        )
        r.raise_for_status()
        payload = r.json()
        query_reports.append({"query": query, "total_count": payload.get("total_count", 0)})
        for repo in payload.get("items", []):
            text = " ".join(
                filter(None, [repo["full_name"], repo.get("description") or "", " ".join(repo.get("topics", []))])
            )
            if not FONT_WORDS.search(text):
                continue
            mirror_like = bool(MIRROR_WORDS.search(text)) or repo.get("fork", False)
            found[repo["full_name"]] = {
                "repo": repo["full_name"],
                "url": repo["html_url"],
                "description": repo.get("description"),
                "stars": repo.get("stargazers_count", 0),
                "license": (repo.get("license") or {}).get("spdx_id"),
                "archived": repo.get("archived", False),
                "fork": repo.get("fork", False),
                "updated_at": repo.get("updated_at"),
                "topics": repo.get("topics", []),
                "review_class": "mirror_or_derivative" if mirror_like else "upstream_candidate",
                "review_required": True,
            }
    candidates = sorted(found.values(), key=lambda x: (x["review_class"] != "upstream_candidate", -x["stars"]))
    result = {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "queries": query_reports,
        "candidate_count": len(candidates),
        "upstream_candidate_count": sum(x["review_class"] == "upstream_candidate" for x in candidates),
        "note": "검색 결과는 후보 목록이다. 제작자 본인 여부, 실제 한글 글리프, 라이선스 원문과 배포 파일을 확인한 뒤 채택한다.",
        "candidates": candidates,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("candidate_count", "upstream_candidate_count")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
