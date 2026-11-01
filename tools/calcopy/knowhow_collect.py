# -*- coding: utf-8 -*-
"""해외영상 수집 노하우 영상 모으기 (사장님 10-21 "해외영상 수집 유튜브 노하우 최대한 많이 수집하고 노하우 다 뽑자", 관제 097).

  search  : 검색어마다 ytsearch N 개(flat) → 후보.json (id 중복 제거, 걸린 검색어 누적)
  subs    : 후보.json 중 고른 id 의 자막(ko 자동·수동, 없으면 en) → subs/<id>.txt (vtt 를 줄 중복 없이 평문으로)

    PYTHONUTF8=1 py tools/calcopy/knowhow_collect.py search channel/해외영상수집_노하우 [--n 40]
    PYTHONUTF8=1 py tools/calcopy/knowhow_collect.py subs   channel/해외영상수집_노하우 [--min-views 3000] [--max 300] [--ids-json 관련도.json]
자막 받기는 yt_fetch.fetch_subs(주인 한 곳)를 쓴다. 봇 차단·429 는 건너뛰고 다음 실행에서 이어 받는다(이미 받은 건 건너뜀).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine.yt_fetch import fetch_subs  # noqa: E402

QUERIES = [
    # 한국어 — 소스 찾기
    "쇼츠 해외영상 가져오는법", "해외 쇼츠 영상 소스 찾는법", "쇼핑쇼츠 영상 소스 찾는법", "쇼핑 쇼츠 영상 구하는법",
    "쿠팡파트너스 쇼츠 영상 소스", "쿠팡파트너스 쇼츠 영상 구하는 방법", "쿠팡파트너스 쇼츠 만드는법", "쿠팡파트너스 쇼츠 자동화",
    "해외 틱톡 영상 찾는법 쇼츠", "틱톡 떡상 영상 찾는법", "해외 바이럴 영상 찾는 사이트", "쇼츠 원본 영상 찾는 법",
    "구글렌즈 영상 원본 찾기", "중국 영상 소싱 쇼츠", "더우인 영상 다운로드", "도우인 영상 다운 방법", "도우인 가입 검색 방법",
    "샤오홍슈 영상 다운로드", "콰이쇼우 영상 다운", "틱톡 워터마크 없이 다운로드", "인스타 릴스 해외 영상 찾기",
    "알리익스프레스 상품 영상 다운로드", "1688 타오바오 상품 영상 다운로드", "해외 숏폼 다운로드 사이트",
    # 한국어 — 재편집·수익화·저작권
    "해외영상 재편집 쇼츠 저작권", "재가공 쇼츠 수익창출", "짜깁기 쇼츠 수익창출 거절", "재사용된 콘텐츠 수익화 거절 해결",
    "쇼츠 재업로드 수익화", "무자본 쇼츠 해외영상", "해외영상 번역 쇼츠 채널", "쇼핑쇼츠 떡상 노하우", "쇼핑 쇼츠 채널 운영 노하우",
    "쇼츠 영상 소스 저작권 없는", "해외 썰 쇼츠 만드는법", "제품 리뷰 쇼츠 해외영상 편집",
    # 영어
    "how to find viral videos for youtube shorts", "where to find videos for shorts reupload", "douyin video download tutorial",
    "tiktok product videos source dropshipping", "faceless shorts channel video source", "reused content youtube monetization fix",
    "how to find trending tiktok products videos", "xiaohongshu video download",
]


def cmd_search(out: Path, n: int):
    out.mkdir(parents=True, exist_ok=True)
    fp = out / "후보.json"
    cand = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else {}
    for q in QUERIES:
        r = subprocess.run(["yt-dlp", "--no-warnings", "--flat-playlist", "-J", f"ytsearch{n}:{q}"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=180)
        if r.returncode != 0:
            print("실패", q, r.stderr[-200:], flush=True); time.sleep(20); continue
        ents = json.loads(r.stdout).get("entries") or []
        new = 0
        for e in ents:
            vid = e.get("id")
            if not vid:
                continue
            c = cand.setdefault(vid, {"id": vid, "title": e.get("title"), "channel": e.get("channel") or e.get("uploader"),
                                      "views": e.get("view_count"), "dur": e.get("duration"), "queries": []})
            new += not c["queries"]
            if q not in c["queries"]:
                c["queries"].append(q)
        print(f"{len(ents):3d}개 새{new:3d}  {q}", flush=True)
        fp.write_text(json.dumps(cand, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(3)
    print("후보 합계", len(cand))


def vtt_text(p: Path) -> str:
    lines, last = [], None
    for ln in p.read_text(encoding="utf-8", errors="replace").splitlines():
        if "-->" in ln or not ln.strip() or ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")) or ln.strip().isdigit():
            continue
        t = re.sub(r"<[^>]+>", "", ln).strip()
        if t and t != last:
            lines.append(t); last = t
    return "\n".join(lines)


def cmd_subs(out: Path, min_views: int, max_n: int, ids: list[str]):
    cand = json.loads((out / "후보.json").read_text(encoding="utf-8"))
    sd = out / "subs"; sd.mkdir(exist_ok=True)
    pick = ids or [c["id"] for c in sorted(cand.values(), key=lambda c: -(c.get("views") or 0))
                   if (c.get("views") or 0) >= min_views and (c.get("dur") or 0) >= 60][:max_n]
    ok = fail = 0
    for vid in pick:
        txt = sd / f"{vid}.txt"
        if txt.exists():
            continue
        tmp = sd / "_vtt" / vid
        tmp.parent.mkdir(exist_ok=True)
        got = fetch_subs(f"https://www.youtube.com/watch?v={vid}", tmp, langs="ko,ko-orig,en", tries=2, log=lambda *a: None)
        vtts = sorted(tmp.parent.glob(f"{vid}*.vtt"), key=lambda p: (".ko" not in p.name, p.name))
        if not vtts:
            fail += 1; print("자막없음", vid, flush=True); time.sleep(5); continue
        body = vtt_text(vtts[0])
        c = cand.get(vid, {})
        txt.write_text(f"# {c.get('title')}\n# {c.get('channel')} · 조회 {c.get('views')} · {c.get('dur')}초 · {vtts[0].suffixes[-2] if len(vtts[0].suffixes) > 1 else ''}\n\n{body}\n",
                       encoding="utf-8")
        ok += 1; print("받음", vid, len(body), flush=True); time.sleep(4)
    print(f"받음 {ok} · 자막없음 {fail} · 대상 {len(pick)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["search", "subs"])
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--min-views", type=int, default=3000)
    ap.add_argument("--max", type=int, default=300)
    ap.add_argument("--ids-json", help="관련도.json — A·B 목록 id 만 받는다(id 가 - 로 시작하면 argparse 가 깨져 파일로 받는다)")
    a = ap.parse_args()
    if a.cmd == "search":
        cmd_search(Path(a.out), a.n)
    else:
        ids = []
        if a.ids_json:
            d = json.loads(Path(a.ids_json).read_text(encoding="utf-8"))
            ids = d.get("A", []) + d.get("B", [])
        cmd_subs(Path(a.out), a.min_views, a.max, ids)
