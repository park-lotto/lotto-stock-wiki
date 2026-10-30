"""프리셋 벤치 채널 → 소재 창고(조회순 쇼츠 목록) — channel/<slug>/_kal/벤치상위.json 한 곳(사장님 10-30
"말이 없으면 벤치 채널에서 조회수 순으로 · 후보 달라면 5개 · 프리셋 벤치 채널은 내가 계속 준다 — 스타일은 달라도 같은 장르니 원본을 찾아서 하라").
읽는 곳 = flow.bench_pool(주소 없이 시작·후보 5개·해외원본형 둘째 소재). 여기는 만들기·채널 더하기만.

    py tools/calcopy/hybrid/bench_pool.py build <slug> [--channel <유튜브 채널 주소> …]   # 채널을 더하고(이미 있으면 그대로) 전부 다시 받는다
    py tools/calcopy/hybrid/bench_pool.py show <slug> [--n 10]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FILE = "벤치상위.json"


def pool_file(slug: str) -> Path:
    return ROOT / "channel" / slug / "_kal" / FILE


def channel_shorts(url: str) -> list[dict]:
    """유튜브 채널 쇼츠 탭 전부(id·조회수·제목) — yt-dlp 납작 목록(영상은 안 받는다)."""
    u = url.rstrip("/")
    if not u.endswith("/shorts"):
        u += "/shorts"
    p = subprocess.run(["yt-dlp", "--flat-playlist", "-J", u], capture_output=True, text=True, encoding="utf-8", timeout=300)
    if p.returncode != 0:
        raise RuntimeError(f"{url}: yt-dlp 실패 {p.stderr.strip()[-300:]}")
    rows = []
    for e in json.loads(p.stdout).get("entries") or []:
        if e.get("id"):
            rows.append({"id": e["id"], "views": int(e.get("view_count") or 0), "title": str(e.get("title") or "")[:120], "ch": url})
    return rows


def build(slug: str, add: list[str]) -> dict:
    f = pool_file(slug)
    old = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    chans = list(dict.fromkeys((old.get("channels") or []) + [c.strip() for c in add if c.strip()]))
    if not chans:
        raise SystemExit(f"{slug}: 벤치 채널이 없습니다 — --channel 로 주세요")
    rows, seen = [], set()
    for c in chans:
        for r in channel_shorts(c):
            if r["id"] not in seen:
                seen.add(r["id"])
                rows.append(r)
    keep = {k: v for k, v in old.items() if k not in ("rows", "channels", "made", "basis")}
    out = {**keep, "for": keep.get("for") or f"{slug} 프리셋 소재 창고 — 벤치 채널 쇼츠 조회순(flow.bench_pool)",
           "made": time.strftime("%Y-%m-%d"), "basis": "yt-dlp --flat-playlist <채널>/shorts 조회수(view_count) — bench_pool.py build",
           "channels": chans, "rows": sorted(rows, key=lambda r: -r["views"])}
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "show"])
    ap.add_argument("slug")
    ap.add_argument("--channel", action="append", default=[])
    ap.add_argument("--n", type=int, default=10)
    a = ap.parse_args()
    d = build(a.slug, a.channel) if a.cmd == "build" else json.loads(pool_file(a.slug).read_text(encoding="utf-8"))
    print(f"{a.slug}: 채널 {len(d.get('channels') or [])}개 · 쇼츠 {len(d['rows'])}편")
    for r in d["rows"][:a.n]:
        print(f"  {r['id']}  {r['views']:>10,}  {r['title'][:50]}")
    sys.exit(0)
