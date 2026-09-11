#!/usr/bin/env python3
"""공식 제작사/개인 디자이너가 배포하는 ZIP 원본을 수집·검증한다."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "font_collection"
HEADERS = {"User-Agent": "ShorttemFontCollector/1.0 (+local catalog research)"}
FONT_EXTS = {".ttf", ".otf", ".woff", ".woff2"}
SOURCES = [
    {
        "id": "paperlogy-1.001",
        "name": "페이퍼로지",
        "kind": "개인 디자이너",
        "style_group": "display-sans",
        "source_page": "https://freesentation.blog/paperlogyfont",
        "archive_url": "https://github.com/Freesentation/paperlogy/raw/refs/heads/main/Paperlogy-1.001.zip",
        "license": "OFL-1.1",
    },
    {
        "id": "line-seed-kr",
        "name": "LINE Seed KR",
        "kind": "공식 제작사",
        "style_group": "modern-sans",
        "source_page": "https://seed.line.me/index_kr.html",
        "archive_url": "https://seed.line.me/src/images/fonts/LINE_Seed_Sans_KR.zip",
        "license": "OFL-1.1",
    },
    {
        "id": "gmarket-sans-ttf",
        "name": "Gmarket Sans",
        "kind": "공식 제작사",
        "style_group": "display-sans",
        "source_page": "https://corp.gmarket.com/fonts/",
        "archive_url": "https://corp.gmarket.com/fonts/GmarketSansTTF.zip",
        "license": "custom-free-redistribution",
    },
    {
        "id": "mulmaru",
        "name": "물마루",
        "kind": "개인 디자이너",
        "style_group": "pixel",
        "source_page": "https://github.com/mushsooni/mulmaru",
        "archive_url": "https://github.com/mushsooni/mulmaru/releases/download/v1.0/Mulmaru.zip",
        "license": "OFL-1.1",
    },
    {
        "id": "mulmaru-mono",
        "name": "물마루 모노",
        "kind": "개인 디자이너",
        "style_group": "pixel-mono",
        "source_page": "https://github.com/mushsooni/mulmaru",
        "archive_url": "https://github.com/mushsooni/mulmaru/releases/download/v1.0/MulmaruMono.zip",
        "license": "OFL-1.1",
    },
    {
        "id": "d2-coding-1.3.3",
        "name": "D2Coding",
        "kind": "공식 제작사",
        "style_group": "mono",
        "source_page": "https://github.com/naver/d2-coding-font/releases/tag/VER1.3.3",
        "archive_url": "https://github.com/naver/d2-coding-font/releases/download/VER1.3.3/D2Coding-Ver1.3.3-20260725.zip",
        "license": "OFL-1.1",
    },
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", Path(name).name)


def main() -> int:
    results = []
    for index, source in enumerate(SOURCES, 1):
        item = dict(source)
        try:
            response = requests.get(source["archive_url"], headers=HEADERS, timeout=240)
            response.raise_for_status()
            archive = response.content
            item["archive_bytes"] = len(archive)
            item["archive_sha256"] = digest(archive)
            saved_fonts = []
            saved_licenses = []
            with zipfile.ZipFile(io.BytesIO(archive)) as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    if "/__MACOSX/" in f"/{member.filename}" or Path(member.filename).name.startswith("._"):
                        continue
                    suffix = Path(member.filename).suffix.lower()
                    is_license = bool(
                        re.search(r"(^|/)(OFL|LICENSE|LICENCE|COPYING|README)([^/]*)$", member.filename, re.I)
                    )
                    if suffix not in FONT_EXTS and not is_license:
                        continue
                    data = zf.read(member)
                    if suffix in FONT_EXTS:
                        target = OUT / "files" / "official-archives" / source["id"] / safe_name(member.filename)
                    else:
                        target = OUT / "licenses" / "official-archives" / source["id"] / safe_name(member.filename)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    record = {
                        "archive_path": member.filename,
                        "path": str(target.relative_to(ROOT)),
                        "bytes": len(data),
                        "sha256": digest(data),
                    }
                    (saved_fonts if suffix in FONT_EXTS else saved_licenses).append(record)
            item["files"] = saved_fonts
            item["license_files"] = saved_licenses
            item["collected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
        results.append(item)
        print(f"[official-archives] {index}/{len(SOURCES)} {source['name']}", flush=True)
    path = OUT / "manifests" / "official_archives.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "sources": len(results),
                "errors": sum("error" in x for x in results),
                "files": sum(len(x.get("files", [])) for x in results),
                "bytes": sum(f["bytes"] for x in results for f in x.get("files", [])),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if any("error" in x for x in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
