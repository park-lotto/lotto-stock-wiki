"""칼카피 자동 실행기 — 채널 하나를 주면 7단계를 이어서 돈다 (관제 097, 2026-10-15).

    py tools/calcopy/autorun.py https://www.youtube.com/@썰풀다 sseolpulda [--upto 2]

- 원장 = channel/<약칭>/calcopy.json (쓰기는 calcopy_board.set_step 하나). 끝난 단계는 건너뛴다.
- PC에서 돈다: 서버(데이터센터 IP)는 유튜브 쇼츠 받기가 막힌다. 원장은 커밋하면 서버 진행판에 뜬다.
- 큰 파일(mp4)은 저장소 밖 RAW_ROOT/<약칭>/ 에 둔다.
지금 자동인 단계: 1 채널 선정 · 2 실측(channelkit.bench). 3~7은 아직 사람 몫 — 원장에 'todo' 로 남긴다.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from shopping_shorts import calcopy_board as B  # noqa: E402

RAW_ROOT = Path(os.environ.get("CALCOPY_RAW", "C:/숏템_칼카피"))
RECENT = 100      # 최근 몇 편 안에서 고르나
FRESH_SKIP = 7    # 갓 올린 편은 조회가 덜 찼다 — 빼고 고른다
PICK = 10         # 상위·하위 각각


def _ytdlp(*args: str) -> str:
    r = subprocess.run(["yt-dlp", "--encoding", "utf-8", *args], capture_output=True, encoding="utf-8")
    if r.returncode != 0 and not r.stdout:
        raise RuntimeError(f"yt-dlp 실패: {' '.join(args)[:120]}\n{r.stderr[-400:]}")
    return r.stdout


def _shorts_url(url: str) -> str:
    u = url.rstrip("/")
    return u if u.endswith("/shorts") else u + "/shorts"


def step1(url: str, slug: str) -> dict:
    d = json.loads(_ytdlp("--flat-playlist", "-J", _shorts_url(url)))
    E = [e for e in d["entries"] if e.get("view_count") is not None]
    pool = E[FRESH_SKIP:FRESH_SKIP + RECENT]
    ranked = sorted(pool, key=lambda e: e["view_count"], reverse=True)
    top, bottom = ranked[:PICK], ranked[-PICK:]
    dates = [_ytdlp("--skip-download", "--print", "%(upload_date)s", f"https://www.youtube.com/shorts/{pool[i]['id']}").strip()
             for i in (0, len(pool) - 1)]
    import datetime as dt
    d0, d1 = (dt.datetime.strptime(x, "%Y%m%d") for x in dates)
    span = max((d0 - d1).days, 1)
    views = [e["view_count"] for e in E[:RECENT]]
    stats = {"subs": d.get("channel_follower_count"), "total": len(E), "median_views": int(statistics.median(views)),
             "over_100k": sum(v >= 100_000 for v in views), "per_day": round((len(pool) - 1) / span, 2)}
    sel = {"channel": d.get("channel"), "channel_id": d.get("channel_id"), "url": url, "stats": stats,
           "pool": [FRESH_SKIP, FRESH_SKIP + len(pool)], "pool_dates": [dates[1], dates[0]],
           "top": [{"id": e["id"], "views": e["view_count"], "title": e.get("title", "")} for e in top],
           "bottom": [{"id": e["id"], "views": e["view_count"], "title": e.get("title", "")} for e in bottom]}
    out = ROOT / "channel" / slug / "selection.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sel, ensure_ascii=False, indent=1), encoding="utf-8")
    note = (f"전체 {stats['total']}편 · 최근 {RECENT}편 조회 중앙 {stats['median_views']:,} · 10만↑ {stats['over_100k']} · "
            f"상위10 최저 {top[-1]['view_count']:,} / 하위10 최고 {bottom[0]['view_count']:,}")
    B.set_step(slug, "1", "done", note, [f"channel/{slug}/selection.json"],
               name=d.get("channel"), url=url, stats=stats)
    return sel


def step2(slug: str) -> dict:
    sel = json.loads((ROOT / "channel" / slug / "selection.json").read_text(encoding="utf-8"))
    raw = RAW_ROOT / slug
    for grp in ("top", "bottom"):
        dst = raw / grp
        dst.mkdir(parents=True, exist_ok=True)
        for v in sel[grp]:
            if not (dst / f"{v['id']}.mp4").exists():
                _ytdlp("-f", "bv*[height<=1920][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", "--merge-output-format", "mp4",
                       "-o", str(dst / "%(id)s.%(ext)s"), f"https://www.youtube.com/shorts/{v['id']}")
    from shopping_shorts.channelkit import bench
    res = {}
    for grp in ("top", "bottom"):
        b = bench.run(f"{slug}:{grp}", str(raw / grp), str(raw / f"bench_{grp}"))
        res[grp] = b["criteria"]
    out = ROOT / "channel" / slug / "bench.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    def g(grp, k):
        c = res[grp].get(k) or {}
        return c.get("value")
    note = (f"상위/하위 길이 {g('top','T.duration')}/{g('bottom','T.duration')}초 · "
            f"통합 음량 {g('top','A.lufs')}/{g('bottom','A.lufs')}")
    B.set_step(slug, "2", "done", note, [f"channel/{slug}/bench.json"])
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("url"); ap.add_argument("slug")
    ap.add_argument("--upto", type=int, default=2)
    ap.add_argument("--redo", action="store_true", help="끝난 단계도 다시")
    a = ap.parse_args(argv)
    done = {k for k, v in (B.load(a.slug).get("steps") or {}).items() if v.get("state") == "done"}
    for n, fn in ((1, lambda: step1(a.url, a.slug)), (2, lambda: step2(a.slug))):
        if n > a.upto or (str(n) in done and not a.redo):
            continue
        B.set_step(a.slug, str(n), "doing", "자동 실행 중")
        try:
            fn()
            print(f"[{n}] 끝")
        except Exception as e:  # 단계 실패는 원장에 막힘으로 드러낸다(조용히 넘기지 않는다)
            B.set_step(a.slug, str(n), "blocked", f"{type(e).__name__}: {str(e)[:200]}")
            print(f"[{n}] 막힘: {e}", file=sys.stderr)
            return 1
    B.set_step(a.slug, "3", B.load(a.slug).get("steps", {}).get("3", {}).get("state", "todo") or "todo",
               "대본 구조 — 아직 자동 아님", next="3단계 대본 구조(받아쓰기·박자) 자동화")
    return 0


if __name__ == "__main__":
    sys.exit(main())
