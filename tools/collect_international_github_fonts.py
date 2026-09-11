#!/usr/bin/env python3
"""공식 GitHub 원 제작 저장소에서 해외 디스플레이 폰트를 수집한다.

저장소 ZIP 안에 OFL 라이선스가 실제로 들어 있을 때만 폰트 파일을 보존한다.
해외 폰트는 대개 한글 글리프가 없으므로 한글 대체재가 아니라 영문·숫자·포인트용이다.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "font_collection"
HEADERS = {"User-Agent": "ShorttemFontCollector/1.0 (+local catalog research)"}
FONT_EXTS = {".ttf", ".otf"}
LICENSE_RE = re.compile(r"(OFL|LICENSE|LICENCE|COPYING|OPEN.?FONT)", re.I)
OFL_MARKERS = (b"SIL OPEN FONT LICENSE", b"OPEN FONT LICENSE")

# 원 제작자/파운드리의 공식 저장소만 적는다. 미러와 재패키징 저장소는 넣지 않는다.
SOURCES = [
    {"repo": "github/mona-sans", "group": "brand-grotesk", "use": "영문 훅·숫자·브랜드형 제목"},
    {"repo": "githubnext/monaspace", "group": "brand-variable", "use": "영문 포인트·테크·숫자"},
    {"repo": "theleagueof/league-gothic", "group": "condensed", "use": "세로로 강한 영문 훅", "archive_url": "https://github.com/theleagueof/league-gothic/releases/download/1.601/LeagueGothic-1.601.zip"},
    {"repo": "theleagueof/league-spartan", "group": "geometric", "use": "굵은 영문 훅"},
    {"repo": "theleagueof/chunk", "group": "slab-display", "use": "레트로·쇼핑 강조"},
    {"repo": "theleagueof/ostrich-sans", "group": "condensed-display", "use": "패션·에디토리얼"},
    {"repo": "theleagueof/the-neue-black", "group": "black-display", "use": "초고중량 영문 포인트", "archive_url": "https://github.com/theleagueof/the-neue-black/releases/download/1.007/TheNeueBlack-1.007.zip"},
    {"repo": "velvetyne/Sporting-Grotesque", "group": "editorial-grotesk", "use": "에디토리얼 훅"},
    {"repo": "velvetyne/Trickster", "group": "expressive-serif", "use": "괴짜·반전 포인트"},
    {"repo": "velvetyne/BluuNext", "group": "bold-serif", "use": "고급 잡지형 제목"},
    {"repo": "velvetyne/Commune-Nuit-Debout", "group": "experimental-condensed", "use": "실험적 포인트"},
    {"repo": "gridded-lab/ofl-fonts", "group": "experimental", "use": "개인 디자이너 디스플레이"},
    {"repo": "JordanNewell/newell-typeface", "group": "geometric-display", "use": "테크·속도감 포인트"},
    {"repo": "marcologous/Open-Sauce-Fonts", "group": "modern-grotesk", "use": "정돈된 영문 보조"},
    {"repo": "atelier-anchor/smiley-sans", "group": "cjk-display", "use": "중문·영문 포인트(한글 없음)", "archive_url": "https://github.com/atelier-anchor/smiley-sans/releases/download/v2.0.1/smiley-sans-v2.0.1.zip", "license_url": "https://raw.githubusercontent.com/atelier-anchor/smiley-sans/main/LICENSE"},
    {"repo": "rsms/inter", "group": "modern-variable", "use": "깨끗한 영문·숫자", "archive_url": "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip"},
    {"repo": "arrowtype/recursive", "group": "expressive-variable", "use": "폭·기울기 모션형 훅", "archive_url": "https://github.com/arrowtype/recursive/releases/download/v1.085/ArrowType-Recursive-1.085.zip"},
    {"repo": "DJR-GitHub/fit-to-width", "group": "kinetic-variable", "use": "폭이 변하는 모션 타이포"},
    {"repo": "Etcetera-Type-Co/Anybody", "group": "expressive-variable", "use": "개성 강한 영문 훅"},
    {"repo": "indestructible-type/Jost", "group": "geometric", "use": "고급 기하학 산세리프", "archive_url": "https://github.com/indestructible-type/Jost/releases/download/3.5/Jost.zip"},
    {"repo": "kosbarts/Oi", "group": "ultra-display", "use": "한두 단어 초강조"},
    {"repo": "uswds/public-sans", "group": "editorial-sans", "use": "정보형 영문·숫자", "archive_url": "https://github.com/uswds/public-sans/releases/download/v2.001/public-sans-v2.001.zip"},
]
MAX_FILES_PER_REPO = 100


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z._-]+", "_", name)


def archive(source: dict) -> tuple[bytes, str, str]:
    repo = source["repo"]
    if source.get("archive_url"):
        response = requests.get(source["archive_url"], headers=HEADERS, timeout=240)
        response.raise_for_status()
        return response.content, "release", source["archive_url"]
    for branch in ("main", "master"):
        url = f"https://codeload.github.com/{repo}/zip/refs/heads/{branch}"
        response = requests.get(url, headers=HEADERS, timeout=240)
        if response.status_code == 200:
            return response.content, branch, url
        if response.status_code != 404:
            response.raise_for_status()
    raise RuntimeError("main/master 브랜치 ZIP을 찾지 못함")


def font_priority(member: zipfile.ZipInfo) -> tuple[int, int, str]:
    """렌더용 완성본을 우선하고 소스/시험/데모 복제본은 뒤로 보낸다."""
    value = member.filename.lower()
    score = 0
    if any(word in value for word in ("variable", "[wght", "vf.", "-vf", "_vf")):
        score += 100
    if any(word in value for word in ("font/", "fonts/", "release/", "dist/", "static/")):
        score += 30
    if any(word in value for word in ("display", "condensed", "black", "extrabold", "bold")):
        score += 10
    if any(word in value for word in ("test", "demo", "example", "specimen", "node_modules")):
        score -= 100
    return (-score, len(value), value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", action="append", help="지정 저장소만 다시 수집하고 기존 매니페스트에 병합")
    args = parser.parse_args()
    selected = [x for x in SOURCES if not args.repo or x["repo"] in args.repo]
    unknown = set(args.repo or []) - {x["repo"] for x in SOURCES}
    if unknown:
        raise SystemExit("등록되지 않은 저장소: " + ", ".join(sorted(unknown)))
    base = OUT / "files" / "github-international"
    licenses_base = OUT / "licenses" / "github-international"
    manifest = []
    for index, source in enumerate(selected, 1):
        repo = source["repo"]
        slug = repo.replace("/", "__")
        item = dict(source)
        item["source_page"] = f"https://github.com/{repo}"
        try:
            raw, branch, archive_url = archive(source)
            item.update({"branch": branch, "archive_url": archive_url, "archive_bytes": len(raw)})
            with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                licenses = []
                font_members = []
                for member in zf.infolist():
                    if member.is_dir() or member.filename.startswith("__MACOSX/"):
                        continue
                    leaf = Path(member.filename).name
                    if leaf.startswith("._"):
                        continue
                    if LICENSE_RE.search(member.filename) and member.file_size <= 1024 * 1024:
                        data = zf.read(member)
                        if any(marker in data.upper() for marker in OFL_MARKERS):
                            licenses.append((member, data))
                    if Path(member.filename).suffix.lower() in FONT_EXTS:
                        font_members.append(member)
                if not licenses and source.get("license_url"):
                    license_response = requests.get(source["license_url"], headers=HEADERS, timeout=90)
                    license_response.raise_for_status()
                    license_data = license_response.content
                    if any(marker in license_data.upper() for marker in OFL_MARKERS):
                        licenses.append((None, license_data))
                if not licenses:
                    raise RuntimeError("저장소 ZIP 내부에서 OFL 원문을 확인하지 못함")

                shutil.rmtree(base / slug, ignore_errors=True)
                shutil.rmtree(licenses_base / slug, ignore_errors=True)
                files = []
                for member in sorted(font_members, key=font_priority):
                    data = zf.read(member)
                    # 같은 저장소 안의 완전히 같은 파일은 한 번만 보존한다.
                    sha = digest(data)
                    if any(row["sha256"] == sha for row in files):
                        continue
                    target = base / slug / f"{len(files)+1:03d}__{safe_name(Path(member.filename).name)}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    files.append({
                        "archive_path": member.filename,
                        "path": str(target.relative_to(ROOT)),
                        "bytes": len(data),
                        "sha256": sha,
                    })
                    if len(files) >= MAX_FILES_PER_REPO:
                        break
                license_files = []
                for member, data in licenses:
                    archive_path = member.filename if member else source["license_url"]
                    target = licenses_base / slug / (safe_name(Path(member.filename).name) if member else "LICENSE")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    license_files.append({
                        "archive_path": archive_path,
                        "path": str(target.relative_to(ROOT)),
                        "bytes": len(data),
                        "sha256": digest(data),
                    })
                if not files:
                    raise RuntimeError("저장소에 빌드된 OTF/TTF/WOFF/WOFF2가 없음")
                item["license"] = "OFL-1.1-verified-in-archive"
                item["files"] = files
                item["license_files"] = license_files
                item["collected_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
        manifest.append(item)
        print(f"[github-international] {index}/{len(selected)} {repo}: "
              f"{len(item.get('files', []))} files{(' ERROR' if 'error' in item else '')}", flush=True)

    path = OUT / "manifests" / "github_international.json"
    if args.repo and path.exists():
        previous = json.loads(path.read_text(encoding="utf-8")).get("sources", [])
        replacements = {x["repo"]: x for x in manifest}
        manifest = [replacements.get(x["repo"], x) for x in previous]
    result = {
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "공식 GitHub 원 제작 저장소의 해외 디스플레이/에디토리얼 폰트",
        "warning": "대부분 한글 글리프가 없다. 한글 훅 대체재가 아니라 영문·숫자·포인트용으로 분류한다.",
        "sources": manifest,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "sources": len(manifest),
        "collected": sum("error" not in x for x in manifest),
        "errors": sum("error" in x for x in manifest),
        "files": sum(len(x.get("files", [])) for x in manifest),
        "bytes": sum(f["bytes"] for x in manifest for f in x.get("files", [])),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
