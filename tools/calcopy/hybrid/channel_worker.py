"""채널 엔진 — 원본 찾기 후보(소재마다 ~100개)의 채널을 전부 모아, 약한 채널은 거르고, 남은 채널은 화면을 열어 터진 영상을 받은 뒤
소넷이 '우리가 쓸 채널인가'를 판정해 자산으로 쌓는다(사장님 10-27 "계속 타고타고 가서 대박 영상·대박 채널을 찾아내는 게 핵심 /
가벼운 소넷을 더 투입해서라도 90개 찾은 채널이 어떤 채널인지 보고 약한 채널은 거르고 / 소재 원본 찾기 엔진을 만드는 것").

    py tools/calcopy/hybrid/channel_worker.py [--pool C:/숏템_칼카피/of_pool] [--max N] [--loop]

① 모으기(코드·0토큰) = C:/숏템_칼카피 아래 모든 origin_foreign/cands_*.json(원본 찾기 워커·시험 편) → 채널별 몇 개 소재에 나왔나·후보 최고 조회·한국 여부
② 거르기(코드) = 후보 최고 조회 MIN_VIEWS 미만이고 한 소재에만 나온 채널은 뺀다
③ 들여다보기(코드) = 틱톡: 로그인 세션 브라우저 채널 화면(최근 약 48편·조회) / 유튜브: yt-dlp 쇼츠 목록(30편·조회). 인스타는 아직(서버 계정 수집기 — 계정 막힘 사고가 있던 코드라 따로 붙인다)
④ 판정(소넷, 채널 BATCH 개씩 한 번에 — 글만) = 원본 제작자/퍼 나르기/짜깁기/브랜드 · 터진 영상 많나 · 제품·반응이라 우리가 쓸 수 있나 · 점수
⑤ 자산 = <pool>/채널자산.json {키: {platform, handle, url, korean, seen_in, cand_max_views, top: [{url, views, title}], n_1m, median, judge, t}}
   판정 끝난 채널은 RECHECK_DAYS 동안 다시 안 본다. 토큰·비용은 판정마다 <pool>/channel_worker_cost.jsonl
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
WORK_ROOT = Path("C:/숏템_칼카피")
MIN_VIEWS = 300_000         # 후보 영상 최고 조회 — 이보다 낮고 한 소재에만 나왔으면 약한 채널(코드로 거름)
BATCH = 20                  # 소넷 한 번에 채널 몇 개(글만 — 채널당 상위 15편 제목·조회). 호출마다 고정 글 약 2만 토큰이라 크게 묶는다(10-27 실측)
RECHECK_DAYS = 14
TT_GAP = 6                  # 틱톡 채널 화면 사이 쉼(초) — 몰아 열면 목록이 막힌다
CLAUDE = shutil.which("claude") or "claude"

JUDGE = """너는 쇼츠 채널 감별 담당이다. 우리는 해외(또는 한국) 쇼츠에서 '제품을 써 보고 반응하는' 터진 영상을 찾아, 그 원본으로 한국어 쇼핑 쇼츠를 만든다.
아래 채널마다 최근 영상(제목·조회수)을 보고 판정해라.
- kind: "creator"(본인이 직접 찍는 원본 제작자) | "reuploader"(남의 영상을 퍼 나르거나 자막만 입힘) | "compilation"(짜깁기·모음) | "brand"(회사·쇼핑몰 공식) | "other"
- usable: 우리가 원본으로 쓸 만한가(true = 제품·화장품·생활용품을 직접 써 보는 반응·리뷰·시연이 많다. 춤·게임·정치·노래·연예 뉴스 위주면 false)
- hits: 이 채널이 터진 영상을 꾸준히 내나 — "many"(100만+ 여러 편) | "some" | "few"
- product: 주로 다루는 제품 종류 한 줄(예: 화장품·틱톡샵 생활용품)
- score: 0~10(우리가 계속 파고들 가치. creator+usable+many 가 높다. reuploader 는 원본이 아니라 낮다 — 단 한국 재편집 채널은 '소재 공급처'로 따로 본다)
JSON 하나: {"channels": [{"key": "<키 그대로>", "kind": "...", "usable": true, "hits": "...", "product": "...", "score": 7, "why": "한 줄"}]}"""


def _handle(c: dict) -> tuple[str, str] | None:
    pf, url = str(c.get("platform") or ""), str(c.get("url") or "")
    if pf == "tt":
        m = re.search(r"tiktok\.com/@([^/?#]+)", url)
        return (pf, m.group(1)) if m else None
    if pf == "yt":
        return (pf, str(c["channel_id"])) if c.get("channel_id") else None
    if pf == "ig":
        return (pf, str(c["channel"])) if c.get("channel") and " " not in str(c["channel"]) else None
    return None


_SRC: dict[str, str] = {}


def _src_id(cf: Path) -> str:
    """후보 파일 → 그 편 소재 id(같은 소재를 여러 시험 폴더에서 돌린 것을 한 번으로 — 10-27 폴더 이름으로 세 23번처럼 부풀었다).
    칸 2(alt1) 후보면 그 칸 소재. 못 읽으면 폴더 경로."""
    d = cf.parent.parent              # job 또는 job/alt1
    key = str(d)
    if key in _SRC:
        return _SRC[key]
    sid = ""
    for up in [d] + list(d.parents)[:4]:
        f = up / "bench" / "bench.info.json"
        if f.exists():
            try:
                sid = str(json.loads(f.read_text(encoding="utf-8")).get("id") or "")
            except (OSError, ValueError):
                sid = ""
            break
    _SRC[key] = sid or key
    return _SRC[key]


def gather(root: Path = WORK_ROOT) -> dict[str, dict]:
    """① 모든 원본 찾기 후보 파일 → 채널 집계. 소재 id = 그 편 지시서 상태의 bench id(없으면 폴더 이름)."""
    out: dict[str, dict] = {}
    for cf in root.glob("**/origin_foreign/cands_*.json"):
        try:
            c = json.loads(cf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        src = _src_id(cf)
        for x in (c.get("cands") if isinstance(c, dict) else c) or []:
            h = _handle(x)
            if not h:
                continue
            k = f"{h[0]}:{h[1]}"
            e = out.setdefault(k, {"platform": h[0], "handle": h[1], "name": x.get("channel"), "seen_in": [], "cand_max_views": 0,
                                   "korean": bool(x.get("korean")), "cand_videos": []})
            if src not in e["seen_in"]:
                e["seen_in"].append(src)
            e["cand_max_views"] = max(e["cand_max_views"], int(x.get("views") or 0))
            if x.get("url") and x["url"] not in e["cand_videos"]:
                e["cand_videos"].append(x["url"])
    return out


def strong(e: dict) -> bool:
    """② 코드 거르기 — 판단 주인 한 곳."""
    return e["cand_max_views"] >= MIN_VIEWS or len(e["seen_in"]) >= 2


def yt_top(cid: str, n: int = 30) -> list[dict]:
    r = subprocess.run(["yt-dlp", "--flat-playlist", "-J", "--playlist-end", str(n), f"https://www.youtube.com/channel/{cid}/shorts"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    try:
        es = json.loads(r.stdout).get("entries") or []
    except ValueError:
        return []
    return [{"url": f"https://www.youtube.com/shorts/{x.get('id')}", "views": int(x.get("view_count") or 0), "title": x.get("title")} for x in es if x.get("id")]


def tt_tops(handles: list[str]) -> dict[str, list[dict]]:
    """틱톡 채널 화면 — 화면 뜬 창 + 틱톡 로그인 쿠키(원본 찾기의 틱톡 검색과 같은 길). 10-27 실측: 헤드리스는 몇 채널 뒤
    'Something went wrong'(목록 막힘)으로 7채널 0편 → 화면 뜬 창·쿠키로 32·32·19편. 막히면 5초 뒤 Refresh 한 번, 채널 사이 TT_GAP 초."""
    from tools.calcopy import lens as LN
    from tools.calcopy.hybrid import runner_ops as R

    def num(s: str) -> int:
        s = (s or "").strip().upper().replace(",", "")
        mul = {"K": 1e3, "M": 1e6, "B": 1e9}
        try:
            return int(float(s[:-1]) * mul[s[-1]]) if s and s[-1] in mul else int(float(s))
        except ValueError:
            return 0
    out = {}
    with R._plat_lock("web"), LN.lens_page("ttch") as pg:      # 원본 찾기 워커의 틱톡 검색과 엇갈리게(같은 잠금)
        ck = R._tiktok_cookies()
        if ck:
            pg.context.add_cookies(ck)
        for h in handles:
            items = []
            try:
                pg.goto(f"https://www.tiktok.com/@{h}", wait_until="domcontentloaded", timeout=40000)
                pg.wait_for_timeout(5000)
                if not pg.locator('[data-e2e="user-post-item"]').count() and pg.get_by_text("Something went wrong").count():
                    pg.wait_for_timeout(5000)
                    pg.get_by_text("Refresh").first.click()
                    pg.wait_for_timeout(5000)
                for _ in range(3):
                    pg.mouse.wheel(0, 2500)
                    pg.wait_for_timeout(1000)
                items = pg.eval_on_selector_all('[data-e2e="user-post-item"]', """els=>els.map(e=>({href:(e.querySelector('a')||{}).href,
                    v:(e.querySelector('[data-e2e=video-views]')||{}).innerText, t:(e.querySelector('img')||{}).alt}))""")
            except Exception as e:  # noqa: BLE001 — 한 채널 실패는 남기고 다음
                sys.stderr.write(f"[ch] 틱톡 @{h} 화면 실패: {type(e).__name__}\n")
            out[h] = [{"url": i["href"], "views": num(i.get("v")), "title": (i.get("t") or "")[:120]} for i in items if i.get("href")]
            if not out[h]:
                sys.stderr.write(f"[ch] 틱톡 @{h} 목록 0편(막힘?)\n")
            time.sleep(TT_GAP)
    return out


def judge(batch: list[tuple[str, dict]], pool: Path) -> dict[str, dict]:
    """④ 소넷 판정 — 채널 BATCH 개를 글로만 한 번에."""
    rows = []
    for k, e in batch:
        top = sorted(e["top"], key=lambda x: -x["views"])[:15]
        rows.append(f"### {k} ({'한국' if e['korean'] else '해외'} · {e['platform']} · {e.get('name')})\n" +
                    "\n".join(f"- {x['views']:,}회 · {str(x.get('title') or '')[:90]}" for x in top))
    ask = JUDGE + "\n\n" + "\n\n".join(rows) + "\n\n답은 JSON 객체 하나만."
    t0 = time.time()
    r = subprocess.run([CLAUDE, "-p", "--model", "sonnet", "--output-format", "json", "--settings", '{"disableAllHooks": true}', "--max-turns", "2",
                        "--system-prompt", "너는 JSON 으로만 답하는 판정기다.", "--strict-mcp-config",
                        "--disallowedTools", "Bash,Edit,Write,Read,Glob,Grep,WebSearch,WebFetch,Agent,Skill"],
                       input=ask, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=tempfile.gettempdir(), timeout=600)
    try:
        j = json.loads(r.stdout)
    except ValueError:
        return {}
    with (pool / "channel_worker_cost.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%d %H:%M"), "n": len(batch), "sec": round(time.time() - t0), "usage": j.get("usage"),
                            "cost_usd": j.get("total_cost_usd")}, ensure_ascii=False) + "\n")
    txt = j.get("result") or ""
    s, t = txt.find("{"), txt.rfind("}")
    try:
        a = json.loads(txt[s:t + 1])
    except ValueError:
        return {}
    return {str(x.get("key")): x for x in a.get("channels") or [] if x.get("key")}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", default="C:/숏템_칼카피/of_pool")
    ap.add_argument("--max", type=int, default=0, help="이번에 들여다볼 채널 수(0 = 전부)")
    ap.add_argument("--loop", action="store_true", help="다 보면 1시간 쉬고 새 후보로 다시")
    a = ap.parse_args(argv)
    pool = Path(a.pool)
    pool.mkdir(parents=True, exist_ok=True)
    ap_ = pool / "채널자산.json"
    while True:
        book = json.loads(ap_.read_text(encoding="utf-8")) if ap_.exists() else {}
        g = gather()
        now = time.time()
        todo = [(k, e) for k, e in g.items() if strong(e) and e["platform"] in ("tt", "yt")
                and now - float((book.get(k) or {}).get("ts") or 0) > RECHECK_DAYS * 86400]
        todo.sort(key=lambda kv: (-len(kv[1]["seen_in"]), -kv[1]["cand_max_views"]))
        if a.max:
            todo = todo[:a.max]
        print(f"[ch] 후보 채널 {len(g)}개 · 거른 뒤 {sum(1 for e in g.values() if strong(e))}개 · 이번에 볼 것 {len(todo)}개", flush=True)
        if todo:
            t0 = time.time()
            tts = tt_tops([e["handle"] for k, e in todo if e["platform"] == "tt"])
            for k, e in todo:
                e["top"] = tts.get(e["handle"], []) if e["platform"] == "tt" else yt_top(e["handle"])
            print(f"[ch] 채널 화면 {time.time() - t0:.0f}초", flush=True)
            for i in range(0, len(todo), BATCH):
                bt = [(k, e) for k, e in todo[i:i + BATCH] if e["top"]]
                js = judge(bt, pool) if bt else {}
                for k, e in todo[i:i + BATCH]:
                    v = [x["views"] for x in e["top"]]
                    book[k] = {**{x: e.get(x) for x in ("platform", "handle", "name", "korean", "seen_in", "cand_max_views")},
                               "url": {"tt": f"https://www.tiktok.com/@{e['handle']}", "yt": f"https://www.youtube.com/channel/{e['handle']}"}[e["platform"]],
                               "top": sorted(e["top"], key=lambda x: -x["views"])[:20], "n_1m": sum(1 for x in v if x >= 1_000_000),
                               "median": int(statistics.median(v)) if v else 0, "judge": js.get(k), "t": time.strftime("%Y-%m-%d %H:%M"), "ts": time.time()}
                    jj = js.get(k) or {}
                    print(f"[ch] {k} · 100만+ {book[k]['n_1m']}편 · 중앙 {book[k]['median']:,} · {jj.get('kind')} 쓸만 {jj.get('usable')} 점수 {jj.get('score')} · {str(jj.get('why') or '')[:60]}", flush=True)
                ap_.write_text(json.dumps(dict(sorted(book.items(), key=lambda kv: -float(((kv[1].get("judge") or {}).get("score")) or 0))),
                                          ensure_ascii=False, indent=1), encoding="utf-8")
        if not a.loop:
            break
        time.sleep(3600)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
