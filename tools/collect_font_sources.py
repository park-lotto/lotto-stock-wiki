#!/usr/bin/env python3
"""공개 한글 폰트의 출처·라이선스·파일을 재현 가능하게 수집한다.

라이브러리 UI에는 손대지 않는다. 결과는 ``font_collection/`` 아래에만 쓴다.
눈누는 전체 색인/라이선스 메타데이터를 수집하고, Google Fonts는 OFL 원본
TTF와 라이선스를 공식 저장소에서 내려받는다.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "font_collection"
USER_AGENT = "ShorttemFontCollector/1.0 (+local catalog research; respectful crawl)"
NOONNU_SITEMAP = "https://noonnu.cc/sitemap.xml"
GOOGLE_METADATA = "https://fonts.google.com/metadata/fonts"
GOOGLE_RAW = "https://raw.githubusercontent.com/google/fonts/main"
FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}
GITHUB_API = "https://api.github.com"
GITHUB_SOURCES = [
    ("orioncactus/pretendard", "modern-sans", "개인 제작·OFL, 범용 산세리프"),
    ("sun-typeface/SUIT", "modern-sans", "개인 제작·OFL, UI 산세리프"),
    ("wanteddev/wanted-sans", "modern-sans", "공식 공개·OFL, 디스플레이/본문"),
    ("jhaemin/Interop", "modern-sans", "개인 제작·OFL, 현대적 산세리프"),
    ("quiple/galmuri", "pixel", "개인 제작·OFL, 픽셀 디스플레이"),
    ("mushsooni/mulmaru", "pixel", "개인 제작·OFL, 굵은 픽셀"),
    ("quiple/x12y12pxMaruMinyaHangul", "pixel", "개인 제작·OFL, 둥근 픽셀"),
    ("quiple/x10y12pxDenkiChipHangul", "pixel", "개인 제작·OFL, 굵은 픽셀"),
    ("sawalk/MapleSaemmul", "pixel", "개인 제작·OFL, 게임풍 픽셀"),
    ("JAMO-TYPEFACE/Orbit", "display", "개인 제작·OFL, 실험적 디스플레이"),
    ("JAMO-TYPEFACE/Moirai", "display", "개인 제작·OFL, 실험적 디스플레이"),
    ("JAMO-TYPEFACE/Grandiflora", "display", "개인 제작·OFL, 실험적 디스플레이"),
    ("lxgw/LxgwWenkaiKR", "hand-serif", "개인 제작·OFL, 문해서체 계열"),
    ("Neople-font/BitBit", "display", "공식 공개·OFL, 도트 디스플레이"),
    ("naver/d2-coding-font", "mono", "공식 공개·OFL, 한글 코딩체"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def compact(text: str | None) -> str:
    return " ".join((text or "").split())


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", value).strip("-.")
    return value.lower() or "unnamed"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.8"})
    return s


def get(url: str, *, tries: int = 4, timeout: int = 60) -> requests.Response:
    last: Exception | None = None
    for attempt in range(tries):
        try:
            r = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Language": "ko,en;q=0.8"},
                timeout=timeout,
            )
            if r.status_code == 429:
                last = RuntimeError(f"HTTP 429 from {url}")
                time.sleep(min(30, 2 ** (attempt + 1)))
                continue
            r.raise_for_status()
            return r
        except Exception as exc:  # network failures are retried and then recorded
            last = exc
            time.sleep(min(10, 2**attempt))
    raise RuntimeError(f"GET failed: {url}: {last}")


def download(url: str, path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size:
        return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256(path)}
    tmp = path.with_suffix(path.suffix + ".part")
    r = get(url, timeout=180)
    tmp.write_bytes(r.content)
    tmp.replace(path)
    return {"path": str(path.relative_to(ROOT)), "bytes": path.stat().st_size, "sha256": sha256(path)}


def parse_noonnu_page(url: str) -> dict[str, Any]:
    r = get(url)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")
    schema: dict[str, Any] = {}
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            item = json.loads(script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        if item.get("@type") == "SoftwareApplication":
            schema = item
            break

    properties: dict[str, str] = {}
    title = soup.select_one("h2")
    if title:
        for row in title.find_next_sibling("div").select("div") if title.find_next_sibling("div") else []:
            parts = [compact(x.get_text(" ", strip=True)) for x in row.select("span")]
            if len(parts) >= 2 and parts[0] in {"제작", "조회수", "형태", "굵기"}:
                properties[parts[0]] = parts[1]

    tags = []
    for a in soup.select('a[href*="/index?search="]'):
        label = compact(a.get_text(" ", strip=True))
        if label and label not in tags:
            tags.append(label)

    download_url = None
    for a in soup.select("a[href]"):
        if "다운로드 페이지로 이동" in compact(a.get_text(" ", strip=True)):
            download_url = urljoin(url, a.get("href"))
            break

    permissions: dict[str, dict[str, str]] = {}
    ofl_note = ""
    for tr in soup.select("table tr"):
        cells = [compact(x.get_text(" ", strip=True)) for x in tr.select("th,td")]
        if len(cells) < 2 or cells[0] == "카테고리":
            continue
        if cells[0] == "OFL":
            ofl_note = cells[1]
        else:
            permissions[cells[0]] = {
                "scope": cells[1],
                "status": cells[2] if len(cells) > 2 else "",
            }

    license_text = ""
    candidates = soup.select("article.prose")
    if candidates:
        license_text = "\n".join(
            compact(p.get_text(" ", strip=True)) for p in candidates[-1].select("p")
        ).strip()

    font_faces = []
    seen_urls: set[str] = set()
    face_re = re.compile(
        r"@font-face\s*\{(?P<body>.*?)\}", re.I | re.S
    )
    for style in soup.select("style"):
        css = style.get_text("\n")
        for match in face_re.finditer(css):
            body = match.group("body")
            family_m = re.search(r"font-family\s*:\s*['\"]?([^;'\"]+)", body, re.I)
            url_m = re.search(r"url\(['\"]?([^)'\"]+)", body, re.I)
            weight_m = re.search(r"font-weight\s*:\s*([^;]+)", body, re.I)
            if not url_m:
                continue
            face_url = urljoin(url, url_m.group(1).strip())
            if face_url in seen_urls:
                continue
            seen_urls.add(face_url)
            font_faces.append(
                {
                    "family": compact(family_m.group(1)) if family_m else "",
                    "weight": compact(weight_m.group(1)) if weight_m else "",
                    "url": face_url,
                }
            )

    redistribution = "unknown"
    if ofl_note:
        if re.search(r"수정[·ㆍ・]?복제[·ㆍ・]?배포\s*가능", ofl_note):
            redistribution = "allowed"
        elif "배포" in ofl_note and "금지" in ofl_note:
            redistribution = "denied"
    elif re.search(r"SIL Open Font License|OFL(?:\s|,|$)", license_text, re.I):
        redistribution = "allowed"

    video = permissions.get("영상", {}).get("status", "unknown")
    embedding = permissions.get("임베딩", {}).get("status", "unknown")
    file_policy = (
        "download_allowed"
        if redistribution == "allowed" and video == "사용 가능" and embedding == "사용 가능"
        else "metadata_only"
    )
    return {
        "source": "noonnu",
        "source_url": url,
        "source_id": url.rstrip("/").split("/")[-1],
        "name": schema.get("name") or (compact(title.get_text()) if title else ""),
        "creator": ((schema.get("creator") or {}).get("name") or properties.get("제작", "")),
        "description": schema.get("description", ""),
        "image_url": schema.get("image", ""),
        "properties": properties,
        "tags": tags,
        "official_download_page": download_url,
        "permissions": permissions,
        "redistribution": redistribution,
        "ofl_note": ofl_note,
        "license_text": license_text,
        "font_faces": font_faces,
        "file_policy": file_policy,
        "collected_at": utc_now(),
    }


def normalize_noonnu_item(item: dict[str, Any]) -> dict[str, Any]:
    note = item.get("ofl_note", "")
    redistribution = "unknown"
    if re.search(r"수정[·ㆍ・]?복제[·ㆍ・]?배포\s*가능", note):
        redistribution = "allowed"
    elif "배포" in note and "금지" in note:
        redistribution = "denied"
    elif re.search(r"SIL Open Font License|OFL(?:\s|,|$)", item.get("license_text", ""), re.I):
        redistribution = "allowed"
    video = item.get("permissions", {}).get("영상", {}).get("status", "unknown")
    embedding = item.get("permissions", {}).get("임베딩", {}).get("status", "unknown")
    item["redistribution"] = redistribution
    item["file_policy"] = (
        "download_allowed"
        if redistribution == "allowed" and video == "사용 가능" and embedding == "사용 가능"
        else "metadata_only"
    )
    return item


def download_noonnu_files(items: list[dict[str, Any]], workers: int) -> None:
    eligible = [x for x in items if x.get("file_policy") == "download_allowed"]
    print(f"[noonnu-files] eligible families={len(eligible)}", flush=True)
    jobs = []
    for item in eligible:
        item["downloaded_files"] = []
        for face_index, face in enumerate(item.get("font_faces", []), 1):
            url = face.get("url", "")
            suffix = Path(url.split("?", 1)[0]).suffix.lower()
            if suffix not in FONT_EXTENSIONS:
                continue
            filename = Path(url.split("?", 1)[0]).name
            target = OUT / "files" / "noonnu" / item["source_id"] / filename
            jobs.append((item, face, url, target))

    def fetch(job: tuple[dict[str, Any], dict[str, Any], str, Path]) -> tuple[dict[str, Any], dict[str, Any]]:
        item, face, url, target = job
        try:
            info = download(url, target)
            info.update(
                {
                    "family": face.get("family", ""),
                    "weight": face.get("weight", ""),
                    "url": url,
                    "mirror": "noonnu-page-declared-webfont",
                }
            )
        except Exception as exc:
            info = {"url": url, "error": str(exc)}
        return item, info

    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, job) for job in jobs]
        for future in concurrent.futures.as_completed(futures):
            item, info = future.result()
            item["downloaded_files"].append(info)
            completed += 1
            if completed % 25 == 0 or completed == len(jobs):
                print(f"[noonnu-files] {completed}/{len(jobs)} files", flush=True)


def collect_noonnu(args: argparse.Namespace) -> list[dict[str, Any]]:
    sitemap = get(NOONNU_SITEMAP).text
    urls = sorted(
        set(re.findall(r"https://noonnu\.cc/font_page/\d+", sitemap)),
        key=lambda x: int(x.rsplit("/", 1)[-1]),
    )
    if args.limit:
        urls = urls[: args.limit]
    out_path = OUT / "manifests" / "noonnu.json"
    existing: dict[str, dict[str, Any]] = {}
    if out_path.exists() and not args.refresh:
        existing = {
            x["source_url"]: normalize_noonnu_item(x)
            for x in json.loads(out_path.read_text(encoding="utf-8"))
        }
    todo = [u for u in urls if u not in existing]
    print(f"[noonnu] indexed={len(urls)} cached={len(existing)} todo={len(todo)}", flush=True)

    errors: list[dict[str, str]] = []
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(parse_noonnu_page, u): u for u in todo}
        for future in concurrent.futures.as_completed(futures):
            url = futures[future]
            try:
                item = normalize_noonnu_item(future.result())
                existing[url] = item
            except Exception as exc:
                errors.append({"url": url, "error": str(exc)})
            completed += 1
            if completed % 25 == 0 or completed == len(todo):
                print(f"[noonnu] {completed}/{len(todo)} errors={len(errors)}", flush=True)
                write_json(out_path, sorted(existing.values(), key=lambda x: int(x["source_id"])))
            time.sleep(args.delay)

    items = sorted(existing.values(), key=lambda x: int(x["source_id"]))
    if args.download:
        download_noonnu_files(items, args.workers)
    write_json(out_path, items)
    write_json(OUT / "logs" / "noonnu_errors.json", errors)
    return items


def google_family_slug(family: str) -> str:
    return re.sub(r"[^a-z0-9]", "", family.lower())


def parse_pb_filenames(text: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r'^\s*filename:\s*"([^"]+)"', text, re.M)))


def collect_google_fonts(args: argparse.Namespace) -> list[dict[str, Any]]:
    metadata = get(GOOGLE_METADATA).json()
    families = [f for f in metadata["familyMetadataList"] if "korean" in f.get("subsets", [])]
    if args.limit:
        families = families[: args.limit]
    print(f"[google-fonts] korean families={len(families)}", flush=True)
    results = []
    for index, family in enumerate(families, 1):
        slug = google_family_slug(family["family"])
        base = f"{GOOGLE_RAW}/ofl/{slug}"
        try:
            pb = get(f"{base}/METADATA.pb").text
            license_text = get(f"{base}/OFL.txt").text
            filenames = parse_pb_filenames(pb)
            files = []
            family_dir = OUT / "files" / "google-fonts" / slug
            license_dir = OUT / "licenses" / "google-fonts" / slug
            license_dir.mkdir(parents=True, exist_ok=True)
            (license_dir / "OFL.txt").write_text(license_text, encoding="utf-8")
            (license_dir / "METADATA.pb").write_text(pb, encoding="utf-8")
            if args.download:
                for filename in filenames:
                    info = download(f"{base}/{filename}", family_dir / filename)
                    info.update({"filename": filename, "url": f"{base}/{filename}"})
                    files.append(info)
            else:
                files = [{"filename": name, "url": f"{base}/{name}"} for name in filenames]
            results.append(
                {
                    "source": "google-fonts",
                    "source_url": f"https://github.com/google/fonts/tree/main/ofl/{slug}",
                    "name": family["family"],
                    "category": family.get("category"),
                    "designers": family.get("designers", []),
                    "subsets": family.get("subsets", []),
                    "weights": list(family.get("fonts", {}).keys()),
                    "license": "OFL-1.1",
                    "redistribution": "allowed",
                    "embedding": "allowed",
                    "video": "allowed",
                    "files": files,
                    "license_path": str((license_dir / "OFL.txt").relative_to(ROOT)),
                    "metadata_path": str((license_dir / "METADATA.pb").relative_to(ROOT)),
                    "collected_at": utc_now(),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "source": "google-fonts",
                    "name": family["family"],
                    "source_url": f"https://github.com/google/fonts/tree/main/ofl/{slug}",
                    "error": str(exc),
                    "collected_at": utc_now(),
                }
            )
        print(f"[google-fonts] {index}/{len(families)} {family['family']}", flush=True)
    write_json(OUT / "manifests" / "google_fonts_korean.json", results)
    return results


def github_get(path: str) -> requests.Response:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.get(f"{GITHUB_API}{path}", headers=headers, timeout=90)
    r.raise_for_status()
    return r


def _choose_github_fonts(paths: list[str]) -> list[str]:
    """소스/중복 웹포맷을 피하고 설치 가능한 바이너리를 우선한다."""
    candidates = [p for p in paths if Path(p).suffix.lower() in FONT_EXTENSIONS]
    desktop = [p for p in candidates if Path(p).suffix.lower() in {".ttf", ".otf"}]
    chosen = desktop or [p for p in candidates if Path(p).suffix.lower() == ".woff2"]
    chosen = [
        p
        for p in chosen
        if not re.search(r"(^|/)(sources?|src|tests?|node_modules|subset)(/|$)", p, re.I)
    ] or chosen
    return sorted(dict.fromkeys(chosen))[:100]


def collect_github_sources(args: argparse.Namespace) -> list[dict[str, Any]]:
    sources = GITHUB_SOURCES[: args.limit or None]
    results: list[dict[str, Any]] = []
    print(f"[github] curated upstream repositories={len(sources)}", flush=True)
    for index, (repo, style, note) in enumerate(sources, 1):
        try:
            info = github_get(f"/repos/{repo}").json()
            branch = info["default_branch"]
            tree = github_get(f"/repos/{repo}/git/trees/{branch}?recursive=1").json()
            paths = [x["path"] for x in tree.get("tree", []) if x.get("type") == "blob"]
            font_paths = _choose_github_fonts(paths)
            license_paths = [
                p
                for p in paths
                if re.search(r"(^|/)(OFL|LICENSE|LICENCE|COPYING)([^/]*)$", p, re.I)
            ][:20]
            repo_slug = repo.replace("/", "--").lower()
            saved_licenses = []
            for path in license_paths:
                url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
                target = OUT / "licenses" / "github" / repo_slug / Path(path).name
                saved_licenses.append({"source_path": path, **download(url, target)})
            files = []
            if args.download:
                for path in font_paths:
                    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
                    target = OUT / "files" / "github" / repo_slug / Path(path).name
                    file_info = download(url, target)
                    file_info.update({"source_path": path, "url": url})
                    files.append(file_info)
            else:
                files = [
                    {
                        "source_path": path,
                        "url": f"https://raw.githubusercontent.com/{repo}/{branch}/{path}",
                    }
                    for path in font_paths
                ]
            results.append(
                {
                    "source": "github-upstream",
                    "repo": repo,
                    "source_url": info["html_url"],
                    "description": info.get("description"),
                    "style_group": style,
                    "curation_note": note,
                    "stars": info.get("stargazers_count"),
                    "updated_at": info.get("updated_at"),
                    "default_branch": branch,
                    "github_license": (info.get("license") or {}).get("spdx_id"),
                    "license_files": saved_licenses,
                    "files": files,
                    "candidate_font_files": len(font_paths),
                    "collected_at": utc_now(),
                }
            )
        except Exception as exc:
            results.append(
                {
                    "source": "github-upstream",
                    "repo": repo,
                    "source_url": f"https://github.com/{repo}",
                    "style_group": style,
                    "curation_note": note,
                    "error": str(exc),
                    "collected_at": utc_now(),
                }
            )
        print(f"[github] {index}/{len(sources)} {repo}", flush=True)
    write_json(OUT / "manifests" / "github_upstreams.json", results)
    return results


def write_summary(
    noonnu: list[dict[str, Any]], google: list[dict[str, Any]], github: list[dict[str, Any]]
) -> None:
    if not noonnu and (OUT / "manifests" / "noonnu.json").exists():
        noonnu = json.loads((OUT / "manifests" / "noonnu.json").read_text(encoding="utf-8"))
    if not google and (OUT / "manifests" / "google_fonts_korean.json").exists():
        google = json.loads(
            (OUT / "manifests" / "google_fonts_korean.json").read_text(encoding="utf-8")
        )
    if not github and (OUT / "manifests" / "github_upstreams.json").exists():
        github = json.loads((OUT / "manifests" / "github_upstreams.json").read_text(encoding="utf-8"))
    noonnu_downloadable = [x for x in noonnu if x.get("file_policy") == "download_allowed"]
    noonnu_conditional = [
        x
        for x in noonnu
        if any(v.get("status") == "조건부 허용" for v in x.get("permissions", {}).values())
    ]
    google_files = [f for x in google for f in x.get("files", []) if f.get("path")]
    github_files = [f for x in github for f in x.get("files", []) if f.get("path")]
    official = []
    official_path = OUT / "manifests" / "official_archives.json"
    if official_path.exists():
        official = json.loads(official_path.read_text(encoding="utf-8"))
    official_files = [f for x in official for f in x.get("files", [])]
    github_error_repos = [x.get("repo", "") for x in github if "error" in x]
    covered_github_errors = [
        repo
        for repo in github_error_repos
        if any(repo.lower() in x.get("source_page", "").lower() for x in official)
    ]
    audit = {}
    audit_path = OUT / "audit" / "report.json"
    if audit_path.exists():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
    report = {
        "generated_at": utc_now(),
        "noonnu": {
            "indexed": len(noonnu),
            "download_eligible": len(noonnu_downloadable),
            "conditional": len(noonnu_conditional),
            "metadata_only": sum(x.get("file_policy") != "download_allowed" for x in noonnu),
        },
        "google_fonts": {
            "korean_families": len(google),
            "downloaded_files": len(google_files),
            "downloaded_bytes": sum(f.get("bytes", 0) for f in google_files),
            "errors": sum("error" in x for x in google),
        },
        "github_upstreams": {
            "repositories": len(github),
            "downloaded_files": len(github_files),
            "downloaded_bytes": sum(f.get("bytes", 0) for f in github_files),
            "errors": len(github_error_repos),
            "errors_with_official_archive_fallback": len(covered_github_errors),
            "uncovered_errors": len(github_error_repos) - len(covered_github_errors),
        },
        "official_archives": {
            "sources": len(official),
            "downloaded_files": len(official_files),
            "downloaded_bytes": sum(f.get("bytes", 0) for f in official_files),
            "errors": sum("error" in x for x in official),
        },
        "file_audit": audit,
    }
    write_json(OUT / "collection_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", choices=["all", "noonnu", "google-fonts", "github"], default="all"
    )
    parser.add_argument("--download", action="store_true", help="재배포 가능한 공식 폰트 파일도 저장")
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.08)
    parser.add_argument("--limit", type=int, default=0, help="파서 시험용; 0이면 전체")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    OUT.mkdir(parents=True, exist_ok=True)
    noonnu = collect_noonnu(args) if args.source in {"all", "noonnu"} else []
    google = collect_google_fonts(args) if args.source in {"all", "google-fonts"} else []
    github = collect_github_sources(args) if args.source in {"all", "github"} else []
    write_summary(noonnu, google, github)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
