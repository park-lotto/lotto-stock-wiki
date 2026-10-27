"""원본 찾기 워커 — 소재를 하나씩 원본 확보까지만 돌려 장부에 남긴다(사장님 10-27 "소재 정해서 원본 찾는 걸 24시간 계속 돌린다 —
받아 둔 소재와 영상으로 바로 할 수 있으니" / "토큰 효율적으로 하되 멍청하게 안 할 세팅").

    py tools/calcopy/hybrid/of_worker.py [--slug ititemlog] [--version 잇템로그판_v2] [--pool C:/숏템_칼카피/of_pool] [--max N] [--loop]

판단은 하지 않는다 — 지시서(flow) 그대로 flow_dev --single --stop-at f_product 로 돌린다(같은 판단 = 같은 함수, 0순위-B).
  · 소재 = channel/<slug>/_kal/벤치상위.json(조회순) · 판 본보기(상위편_목표 ids)는 뺀다(이미 만든 편)
  · 토큰: 렌즈·검색·정보는 코드(0 토큰) — 모델은 소재 판독 1번 + 같은 영상 판정(+못 찾으면 직접 찾기)만. 끝난 소재는 다시 안 돈다,
    못 찾은 소재는 RETRY_DAYS 뒤에만 다시(새로 올라온 원본) · 한 번에 한 편(렌즈·유튜브 차단 피함)
  · 장부 = <pool>/장부.json {id: {status found|not_found|error, origins, min, why, t, dir}} · 편 폴더 = <pool>/<id>/(받은 원본·판정 기록)
  · 원본 채널 장부 = <pool>/원본채널.json — 같은 영상 판정에 든 해외 후보(한국 재편집 뺌)의 채널을 쌓는다(사장님 10-27 '잘된 채널은 자산으로
    모아 그 안의 터진 영상을 본다'). 채널마다 몇 개 소재의 원본이었나(hits)·원본 영상·최고 조회
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import threading
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
RETRY_DAYS = 7
MAX_CALLS = 40          # 원본 확보까지 실측 9번 — 못 찾을 때 직접 찾기·과제까지 넉넉히, 그 이상은 헛돎
LOCK = "worker.lock"


WORK_ROOT = Path(os.environ.get("SHORTEM_WORK_ROOT") or "C:/숏템_칼카피")


def known_found(root: Path = WORK_ROOT) -> dict[str, dict]:
    """다른 작업(시험·제작 편 폴더)에서 이미 원본을 확보한 소재 {소재 id: {origins, dir}} — 워커가 같은 원본을 또 찾지 않게
    (10-27 사장님 '찾은 걸 왜 또 찾냐' — 워커가 자기 장부만 봐서 오늘 시험에서 찾은 홍현희 편을 다시 찾았다). 판정은 그 편 지시서 상태 그대로."""
    out: dict[str, dict] = {}
    for f in root.glob("**/flow_state.json"):
        try:
            st = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        b = (st.get("bench") or {}).get("id")
        org = [str(o.get("id")) for o in st.get("origins") or [] if o.get("id")]
        if b and org and b not in out:
            out[b] = {"origins": org, "dir": str(f.parent)}
    return out


def queue(slug: str, book: dict) -> list[dict]:
    kal = ROOT / "channel" / slug / "_kal"
    rows = [r for r in json.loads((kal / "벤치상위.json").read_text(encoding="utf-8")).get("rows") or [] if isinstance(r, dict) and r.get("id")]
    gf = kal / "상위편_목표.json"
    skip = set(json.loads(gf.read_text(encoding="utf-8")).get("ids") or []) if gf.is_file() else set()
    now = time.time()
    out = []
    for r in sorted(rows, key=lambda r: -(r.get("views") or 0)):
        b = book.get(r["id"]) or {}
        if r["id"] in skip or b.get("status") == "found":
            continue
        if b and now - float(b.get("ts") or 0) < RETRY_DAYS * 86400:
            continue
        out.append(r)
    return out


def origins_of(W: Path) -> list[str]:
    """그 편 지시서 상태에서 확보한 원본 id(flow_dev 가 남긴 flow_state.json)."""
    try:
        st = json.loads((W / "flow_state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [str(o.get("id")) for o in st.get("origins") or [] if o.get("id")]


CH_URL = {"tt": "https://www.tiktok.com/@{}", "ig": "https://www.instagram.com/{}/", "yt": "https://www.youtube.com/channel/{}"}


def judged_origins(W: Path) -> list[dict]:
    """같은 영상 판정(of_judge 답 same) 칸 → 후보 목록(origin_foreign/cands_<mode>.json)에서 해외(korean False) 것만. 판단은 오푸스 답 그대로."""
    out = []
    for d in sorted((W / "job" / "reviews").glob("*of_judge*")):
        try:
            same = set(json.loads((d / "answer.json").read_text(encoding="utf-8")).get("same") or [])
        except (OSError, ValueError):
            continue
        for cf in sorted((W / "job").glob("**/origin_foreign/cands_*.json")):
            c = json.loads(cf.read_text(encoding="utf-8"))
            for x in (c.get("cands") if isinstance(c, dict) else c) or []:
                if x.get("n") in same and x.get("channel"):
                    out.append(x)
            break
    return out


def add_channels(pool: Path, src_id: str, xs: list[dict]) -> int:
    """원본 채널 장부에 쌓는다(같은 채널은 hits·영상만 늘린다)."""
    p = pool / "원본채널.json"
    book = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    n = 0
    for x in xs:
        pf, name = str(x.get("platform") or ""), str(x.get("channel") or "")
        m = re.search(r"tiktok\.com/@([^/?#]+)", str(x.get("url") or ""))
        # 틱톡 channel 칸 = 표시 이름('Huda Beauty'·'maia \ (-_-) /') — 주소는 영상 주소의 @계정으로(10-27 실측)
        cid = str(x.get("channel_id") or "") if pf == "yt" else (m.group(1) if pf == "tt" and m else name)
        if not cid:
            continue
        k = f"{pf}:{cid}"
        e = book.setdefault(k, {"platform": pf, "name": name, "url": CH_URL.get(pf, "{}").format(cid), "hits": [], "videos": [], "max_views": 0,
                                "first": time.strftime("%Y-%m-%d")})
        if src_id not in e["hits"]:
            e["hits"].append(src_id)
            n += 1
        if x.get("url") and x["url"] not in e["videos"]:
            e["videos"].append(x["url"])
        e["max_views"] = max(int(e.get("max_views") or 0), int(x.get("views") or 0))
        e["last"] = time.strftime("%Y-%m-%d")
    p.write_text(json.dumps(dict(sorted(book.items(), key=lambda kv: (-len(kv[1]["hits"]), -kv[1]["max_views"]))), ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def how_found(W: Path) -> tuple[str, str]:
    """(판단 주인 — 원본 확보 vs 대체) 마지막으로 같은 영상이라 판정된 질문이 무엇이었나. 지시서는 원본을 못 찾으면 같은 제품 다른 해외 반응
    (of_peer)으로 넘어간다 — 10-27 치아 테이프 편: 판정 3번 모두 '같은 촬영분 없음'인데 of_peer 로 3편을 받아 장부에 'found' 로 적혔다."""
    rv = sorted((W / "job" / "reviews").glob("*_of_*"))
    if any("of_peer" in d.name for d in rv):
        return "peer", "같은 제품 다른 해외 반응(원본 못 찾음)"
    return "found", "원본"


def one(r: dict, a, pool: Path) -> dict:
    from tools.calcopy.hybrid import of_stats
    W = pool / r["id"]
    W.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    with (W / "run.log").open("w", encoding="utf-8") as f:
        subprocess.run([sys.executable, str(ROOT / "tools/calcopy/hybrid/flow_dev.py"), "--ref", f"https://www.youtube.com/shorts/{r['id']}",
                        "--version", a.version, "--fmt", "해외원본형", "--work", str(W), "--no-paid", "--single", "--stop-at", "f_product",
                        "--max-calls", str(MAX_CALLS)], cwd=str(ROOT), stdout=f, stderr=subprocess.STDOUT,
                       env={**os.environ, "PYTHONUTF8": "1", "SHORTEM_BROWSER_LOCK": "1"}, timeout=3600)
    s = of_stats.one(W)
    end = s.get("end") or {}
    org = origins_of(W)
    status = "found" if end.get("end") == "stop_at" and org else ("not_found" if end else "error")
    if status == "found":
        status, how = how_found(W)
    else:
        how = ""
    why = next(iter(s.get("judge", {}).values()), {}).get("why", "") if s.get("judge") else ""
    if end.get("end") == "stop":
        why = f"{end.get('why') or ''} · {why}"
    same = judged_origins(W)
    chans = [x for x in same if not x.get("korean")]
    # 같은 촬영분으로 판정된 한국 재편집(우리 소재 말고) = '한국에서도 했나·얼마나 터졌나' — 거꾸로 렌즈는 실측 실패(알려진 쌍 0/1)라 이쪽으로 센다
    kr = sorted([{"url": x.get("url"), "channel": x.get("channel"), "views": int(x.get("views") or 0)} for x in same if x.get("korean") and x.get("id") != r["id"]],
                key=lambda x: -x["views"])
    if chans:
        add_channels(pool, r["id"], chans)
    return {"status": status, "how": how, "origins": org, "channels": sorted({f"{x.get('platform')}:{x.get('channel')}" for x in chans}), "korean_same": kr[:12], "min": round((time.time() - t0) / 60, 1), "why": why[:300], "title": r.get("title"),
            "views": r.get("views"), "steps": s.get("steps"), "t": time.strftime("%Y-%m-%d %H:%M"), "ts": time.time(), "dir": str(W)}


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", default="ititemlog")
    ap.add_argument("--version", default="잇템로그판_v2")
    ap.add_argument("--pool", default="C:/숏템_칼카피/of_pool")
    ap.add_argument("--max", type=int, default=0, help="이번에 돌릴 편 수(0 = 줄이 빌 때까지)")
    ap.add_argument("--par", type=int, default=2, help="동시에 찾는 소재 수(10-27 실측: 2개 동시도 한 편 시간 같음 — 3개 이상은 미측정, 렌즈·유튜브 차단 위험)")
    ap.add_argument("--loop", action="store_true", help="줄이 비면 1시간 쉬고 다시(24시간)")
    a = ap.parse_args(argv)
    pool = Path(a.pool)
    pool.mkdir(parents=True, exist_ok=True)
    lk = pool / LOCK
    if lk.exists() and time.time() - lk.stat().st_mtime < 2 * 3600:
        print("다른 워커가 돌고 있다:", lk)
        return 1
    bp = pool / "장부.json"
    lock = threading.Lock()                 # 장부·원본채널 쓰기와 다음 소재 고르기는 한 번에 하나
    busy: set[str] = set()
    state = {"done": 0, "stop": False}

    def take() -> dict | None:
        with lock:
            if state["stop"]:
                return None
            book = json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else {}
            for k, v in known_found().items():          # 다른 작업에서 이미 찾은 소재는 장부에 옮겨 적고 건너뛴다
                if (book.get(k) or {}).get("status") != "found":
                    book[k] = {"status": "found", "origins": v["origins"], "dir": v["dir"], "by": "기존 작업", "t": time.strftime("%Y-%m-%d %H:%M"), "ts": time.time()}
                    if not (pool / k).exists():
                        same = judged_origins(Path(v["dir"]))
                        if same:
                            add_channels(pool, k, [x for x in same if not x.get("korean")])
            bp.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
            q = [r for r in queue(a.slug, book) if r["id"] not in busy]
            if not q:
                return None
            busy.add(q[0]["id"])
            lk.write_text(" ".join(sorted(busy)), encoding="utf-8")
            print(f"[{time.strftime('%H:%M')}] 소재 {q[0]['id']} · 조회 {q[0].get('views')} · {str(q[0].get('title'))[:40]} (남은 줄 {len(q)})", flush=True)
            return q[0]

    def run() -> None:
        while True:
            r = take()
            if r is None:
                if not a.loop or state["stop"]:
                    return
                time.sleep(3600)
                continue
            try:
                e = one(r, a, pool)
            except Exception as ex:  # noqa: BLE001 — 한 편 실패는 장부에 남기고 다음 편
                e = {"status": "error", "why": f"{type(ex).__name__}: {ex}"[:300], "t": time.strftime("%Y-%m-%d %H:%M"), "ts": time.time()}
            with lock:
                book = json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else {}
                book[r["id"]] = e
                bp.write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
                busy.discard(r["id"])
                state["done"] += 1
                if a.max and state["done"] >= a.max:
                    state["stop"] = True
            print(f"   → {r['id']} {e['status']} {e.get('origins') or ''} {e.get('min', '')}분 · {str(e.get('why'))[:120]}", flush=True)

    try:
        ts = [threading.Thread(target=run, daemon=True) for _ in range(max(1, a.par))]
        for i, t in enumerate(ts):
            t.start()
            time.sleep(20 * (i > -1))       # 렌즈·유튜브 요청이 같은 순간 몰리지 않게 시작을 벌린다
        for t in ts:
            t.join()
    finally:
        lk.unlink(missing_ok=True)
    book = json.loads(bp.read_text(encoding="utf-8")) if bp.exists() else {}
    c = {}
    for v in book.values():
        c[v.get("status")] = c.get(v.get("status"), 0) + 1
    print("장부:", c)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
