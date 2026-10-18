# -*- coding: utf-8 -*-
"""얜샷템 소재 수집 — 최근 터지고 있는 남의 연예인템 쇼츠 순위 (2026-10-17, 관제 097).

한 명령:  py tools/calcopy/celeb_topics.py [--days 7] [--top 30] [--limit N]
  채널 목록(channel/yanshottem/소재채널.json) 전부의 유튜브 RSS → 최근 N일 쇼츠 →
  속도 = 조회 ÷ 올린 뒤 시간(최소 2시간으로 눌러 갓 올린 영상의 튀는 값을 막는다)
  배수 = 조회 ÷ 그 채널 평소 중앙 조회 / 같은 인물 + 같은 제품 낱말이 여러 채널에 뜨면 '바이럴 묶음'
  이전 실행 결과가 있으면 시간당 조회 증가량도 계산 → 소재/<날짜시각>.json + 소재/최신.md
판단의 주인: 이 파일 한 곳(파싱·속도·배수·묶음). 규칙 기반(유료 API 없음).
"""
from __future__ import annotations

import json
import sys
import re
import threading
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
YDIR = ROOT / "channel" / "yanshottem"
CHANNELS = YDIR / "소재채널.json"
OUTDIR = YDIR / "소재"
FEED = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
RETRY_ROUNDS, RETRY_WAIT = 3, 20      # 실패 채널 다시 받기(라운드마다 20·40·60초 쉼)
RETRY_BUDGET = 300                   # 재시도 포함 전체 상한(초)
MIN_OK_FRAC = 0.5                    # 응답 채널이 이 비율 밑이면 최신.md 를 덮지 않는다
MIN_GAP = 0.5            # 요청 시작 간격(초)
NO_PERSON_W = 0.3        # 제목에서 인물을 못 뽑은 영상의 점수 가중(연예인템이 아닌 클립이 위로 오는 걸 막는다)
MIN_HOURS = 2.0          # 속도 계산 때 올린 뒤 시간 하한
NS = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/", "yt": "http://www.youtube.com/xml/schemas/2015"}

# 이름 사전 시드(성 없는 활동명) + 이름처럼 보이나 아닌 낱말
SEED_NAMES = {"제니", "카리나", "장원영", "안유진", "화사", "다현", "태연", "아이유", "수영", "윈터", "지젤", "닝닝", "리사", "로제", "지수",
              "민지", "하니", "해린", "혜인", "다니엘", "사나", "나연", "쯔위", "미연", "슈화", "소연", "유나", "채원", "은채", "레이"}
SURNAMES = set("김이박최정강조윤장임한오서신권황안송류전홍고문양손배백허유남심노하곽성차주우구민나진지엄채원천방공현함변염여추도소석선설마길은")
NOT_NAME = {"최고", "오늘", "한국", "신상", "정말", "이것", "이거", "이번", "이게", "한번", "한방", "전부", "전국", "고객", "도저", "주방", "주의",
            "문제", "소문", "성공", "인기", "나만", "기본", "하루", "구매", "전문", "유명", "마지", "원래", "공개", "현재", "지금", "선택", "추천",
            "국민", "여름", "가을", "연예", "진짜", "금방", "주문", "마트", "방송", "예능", "가격", "제품", "상품", "부담", "가성", "인생"}
STOP = {"연예인", "추천", "인생템", "쇼츠", "shorts", "이유", "정체", "비밀", "비결", "이것", "그것", "진짜", "너무", "완전", "역대급", "품절대란",
        "난리", "대란", "꿀템", "찐템", "필수템", "추천템", "쇼핑쇼츠", "화제", "인기", "최고", "방법", "바로", "매일", "항상", "무조건",
        "쟁여", "쓴다는", "쓰는", "먹는", "하는", "있는", "없는", "같은", "에서", "으로", "에게", "하고", "하면", "해서",
        "다는", "라는", "대신", "때문", "정도", "이후", "처음", "드디어", "결국", "다시", "아주", "가장", "모두", "함께", "직접", "그냥", "원픽",
        "선택", "후기", "리뷰", "공개", "소개", "여기", "저기", "놀라운", "깜짝", "대박", "평생", "인생", "최애",
        "애정", "애착", "스타", "셀럽", "배우", "가수", "아이돌", "방송", "예능", "집에서", "사람"}
PARTICLES = ("이랑", "에서", "으로", "에게", "까지", "부터", "처럼", "마저", "조차", "이", "가", "을", "를", "은", "는", "의", "도", "에", "로", "와", "과", "만", "표", "씨", "님")


# ---------------------------------------------------------------- RSS
def fetch_feed(cid: str, timeout: int = 20) -> str:
    req = urllib.request.Request(FEED.format(cid), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def parse_feed(xml: str, now: datetime | None = None) -> dict:
    """RSS → {name, videos:[{id,title,published,views,desc,url,is_short}]}. 쇼츠만(/shorts/ 링크) 남긴다."""
    root = ET.fromstring(xml)
    name = (root.findtext("a:title", "", NS) or "").strip()
    out = []
    for e in root.findall("a:entry", NS):
        link = e.find("a:link", NS).get("href", "")
        vid = e.findtext("yt:videoId", "", NS)
        st = e.find("m:group/m:community/m:statistics", NS)
        views = int(st.get("views")) if st is not None and st.get("views", "").isdigit() else 0
        out.append({
            "id": vid, "title": (e.findtext("a:title", "", NS) or "").strip(),
            "published": _dt(e.findtext("a:published", "", NS)).isoformat(),
            "views": views,
            "desc": (e.findtext("m:group/m:description", "", NS) or "").strip(),
            "url": link or f"https://www.youtube.com/shorts/{vid}",
            "is_short": "/shorts/" in link,
        })
    return {"name": name, "videos": [v for v in out if v["is_short"]]}


def hours_since(published_iso: str, now: datetime) -> float:
    return (now - _dt(published_iso)).total_seconds() / 3600.0


def speed(views: int, hours: float) -> float:
    """시간당 조회 = 조회 ÷ max(올린 뒤 시간, MIN_HOURS)."""
    return views / max(hours, MIN_HOURS)


def multiple(views: int, channel_median: int) -> float | None:
    return round(views / channel_median, 2) if channel_median and channel_median > 0 else None


# ---------------------------------------------------------------- 인물·제품 (규칙 기반)
def build_name_dict(titles: list[str], min_count: int = 3) -> set[str]:
    """제목들에서 '성+두 글자 + 조사' 꼴이 min_count 번 이상 나오면 인물 사전에 넣는다."""
    cnt: dict[str, int] = {}
    pat = re.compile(r"(?<![가-힣])([가-힣]{3})(?:이랑|에게|까지|처럼|이|가|은|는|의|도|와|과|표|씨|님|한테|네)(?![가-힣])")
    for t in titles:
        for m in set(pat.findall(t)):
            if m[0] in SURNAMES and m[:2] not in NOT_NAME:
                cnt[m] = cnt.get(m, 0) + 1
    return {n for n, c in cnt.items() if c >= min_count} | SEED_NAMES


def find_person(title: str, names: set[str]) -> str | None:
    """제목에서 가장 앞에 나오는 인물(같은 자리면 긴 이름). 순서가 흔들리지 않게 한다."""
    best = None   # (위치, -길이, 이름)
    for n in names:
        i = title.find(n)
        while i >= 0:
            if i == 0 or not ("가" <= title[i - 1] <= "힣"):
                k = (i, -len(n), n)
                if best is None or k < best:
                    best = k
            i = title.find(n, i + 1)
    return best[2] if best else None


def keywords(title: str, person: str | None) -> set[str]:
    t = re.sub(r"#shorts|#쇼츠", " ", title, flags=re.I)
    if person:
        t = t.replace(person, " ")
    t = t.replace("#", " ")
    out = set()
    for w in re.findall(r"[가-힣A-Za-z0-9]+", t):
        for p in PARTICLES:                      # 조사 한 번 떼기(남는 길이 ≥2)
            if w.endswith(p) and len(w) - len(p) >= 2:
                w = w[: -len(p)]
                break
        if len(w) >= 2 and w not in STOP and not w.isdigit():
            out.add(w)
    return out


def _share(a: set[str], b: set[str]) -> set[str]:
    hit = set(a & b)
    for x in a:
        for y in b:
            if x != y and min(len(x), len(y)) >= 3 and (x in y or y in x):
                hit.add(x if len(x) <= len(y) else y)
    return hit


def bundle(items: list[dict]) -> list[list[int]]:
    """같은 인물 + 제품 낱말 공유(서로 다른 영상) → 한 묶음. items 는 person·kw 를 가진 dict. 인덱스 묶음 목록."""
    par = list(range(len(items)))

    def f(x):
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x
    for i in range(len(items)):
        if not items[i]["person"]:
            continue
        for j in range(i + 1, len(items)):
            if items[i]["person"] == items[j]["person"] and _share(items[i]["kw"], items[j]["kw"]):
                par[f(i)] = f(j)
    g: dict[int, list[int]] = {}
    for i in range(len(items)):
        g.setdefault(f(i), []).append(i)
    return list(g.values())


def source_text(desc: str) -> str:
    for ln in desc.splitlines():
        if "출처" in ln:
            return ln.strip()[:120]
    return ""


# ---------------------------------------------------------------- 순위
def rank(videos: list[dict], channels: dict[str, dict], names: set[str], now: datetime, prev: dict[str, tuple[float, int]] | None = None) -> list[dict]:
    """videos: parse_feed 영상 + cid·cname. 묶음 단위 순위 목록을 돌려준다(점수 = 묶음 안 영상 속도 합)."""
    prev = prev or {}
    items = []
    for v in videos:
        h = hours_since(v["published"], now)
        p = find_person(v["title"], names)
        med = channels.get(v["cid"], {}).get("조회중앙", 0)
        w = (channels.get(v["cid"], {}).get("연예인템비율") or 0.6) * (1.0 if p else NO_PERSON_W)   # 연예인템 채널·인물 인식된 영상 우선
        it = dict(v, w=w, hours=round(h, 1), speed=round(speed(v["views"], h), 1), mult=multiple(v["views"], med), person=p, kw=keywords(v["title"], p))
        pv = prev.get(v["id"])
        it["growth"] = None
        if pv:
            dth = (now.timestamp() - pv[0]) / 3600.0
            if dth >= 0.05:
                it["growth"] = round((v["views"] - pv[1]) / dth, 1)
        items.append(it)
    rows = []
    for idx in bundle(items):
        mem = sorted((items[i] for i in idx), key=lambda x: -x["speed"])
        top = mem[0]
        chs = sorted({m["cid"] for m in mem})
        if len(mem) > 1:
            shared = set(mem[0]["kw"])
            for m in mem[1:]:
                shared = _share(shared, m["kw"]) or shared
        else:
            shared = top["kw"]
        prod = " ".join(sorted(shared, key=lambda w: (-len(w), w))[:3])
        rows.append({
            "인물": top["person"] or "", "제품": prod, "점수": round(sum(m["speed"] * m["w"] for m in mem), 1), "채널수": len(chs),
            "묶음영상수": len(mem), "대표": {k: top[k] for k in ("id", "title", "url", "cid", "cname", "views", "hours", "speed", "mult", "growth", "published")},
            "출처": source_text(top["desc"]) or next((source_text(m["desc"]) for m in mem if source_text(m["desc"])), ""),
            "묶음": [{"cname": m["cname"], "title": m["title"], "url": m["url"], "views": m["views"], "hours": m["hours"], "speed": m["speed"]} for m in mem],
        })
    rows.sort(key=lambda r: -r["점수"])
    for i, r in enumerate(rows, 1):
        r["순위"] = i
    return rows


def render_md(rows: list[dict], top: int, meta: dict) -> str:
    L = [f"# 얜샷템 소재 순위 — {meta['when']}", "",
         f"채널 {meta['channels']}개(응답 {meta['ok']}) · 최근 {meta['days']}일 쇼츠 {meta['videos']}편 · 소요 {meta['secs']}초 · "
         f"점수 = 묶음 안 영상 (시간당 조회 × 채널 연예인템 비율 × 인물인식 가중) 합(바이럴 묶음이 위로) · 증가/h = 직전 실행({meta.get('prev') or '없음'}) 대비", "",
         "| # | 인물 | 제품 | 채널 | 올린지 | 조회 | 시간당 | 증가/h | 배수 | 묶음채널 | 출처 | URL |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows[:top]:
        d = r["대표"]
        g = "" if d["growth"] is None else f"{d['growth']:.0f}"
        L.append(f"| {r['순위']} | {r['인물'] or '-'} | {r['제품'] or '-'} | {d['cname']} | {d['hours']:.0f}h | {d['views']:,} | {d['speed']:.0f} | {g} | "
                 f"{'' if d['mult'] is None else str(d['mult']) + 'x'} | {r['채널수']} | {r['출처'].replace('|', '/') or '-'} | {d['url']} |")
    bund = [r for r in rows if r["채널수"] >= 2]
    L += ["", f"## 바이럴 묶음 (같은 인물+제품이 2채널 이상) — {len(bund)}건"]
    for r in bund[:15]:
        L.append(f"- #{r['순위']} {r['인물']} / {r['제품']} — {r['채널수']}채널 {r['묶음영상수']}편: " + ", ".join(f"{m['cname']}({m['views']:,})" for m in r["묶음"][:6]))
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- 실행
def _load_prev(cur_name: str) -> tuple[dict, str | None]:
    files = sorted(p for p in OUTDIR.glob("2*.json") if p.name != cur_name)
    if not files:
        return {}, None
    d = json.load(open(files[-1], encoding="utf-8"))
    return {k: (v[0], v[1]) for k, v in d.get("snapshot", {}).items()}, files[-1].stem


def run(days: int = 7, top: int = 30, limit: int | None = None, feeds: dict[str, str] | None = None, now: datetime | None = None, write: bool = True) -> dict:
    t0 = time.time()
    now = now or datetime.now(timezone.utc)
    chs = json.load(open(CHANNELS, encoding="utf-8"))["채널"]
    if limit:
        chs = chs[:limit]
    cmap = {c["id"]: c for c in chs}
    got: dict[str, dict] = {}
    lock, last = threading.Lock(), [0.0]

    def work(cid, timeout=20):
        with lock:                               # 요청 시작 간격 ≥ MIN_GAP
            wait = last[0] + MIN_GAP - time.time()
            last[0] = max(time.time(), last[0] + MIN_GAP)
        if wait > 0:
            time.sleep(wait)
        try:
            xml = feeds[cid] if feeds is not None else fetch_feed(cid, timeout)
            got[cid] = parse_feed(xml, now)
        except Exception as e:
            got[cid] = {"error": str(e)[:80], "videos": []}
    if feeds is not None:
        for c in cmap:
            if c in feeds:
                work(c)
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as ex:
            list(ex.map(work, list(cmap)))
        for rnd in range(RETRY_ROUNDS):           # 10-18 12:30 유튜브 RSS 가 404·500 을 번갈아 냄(같은 채널 curl 3회 404/500/404) — 실패만 쉬었다 다시
            bad = [c for c, g in got.items() if "error" in g]
            if not bad:
                break
            if time.time() - t0 + RETRY_WAIT * (rnd + 1) > RETRY_BUDGET:   # 10-18 실측: 차례 재시도가 55분 — 총 시간 상한
                break
            time.sleep(RETRY_WAIT * (rnd + 1))
            with ThreadPoolExecutor(8) as ex:
                list(ex.map(lambda c: work(c, timeout=8), bad))
    vids, titles = [], []
    cut = now - timedelta(days=days)
    for cid, g in got.items():
        for v in g["videos"]:
            titles.append(v["title"])
            if _dt(v["published"]) >= cut and v["views"] > 0:
                vids.append(dict(v, cid=cid, cname=g.get("name") or cmap[cid].get("이름", "")))
    if feeds is None:                               # 인물 사전은 기존 제목 자료로도 키운다(시험은 픽스처만)
        for p in (ROOT / "channel/itemhome/동종채널").glob("*.json"):
            try:
                for lst in json.load(open(p, encoding="utf-8")).values():
                    if isinstance(lst, list):
                        titles += [x[2] for x in lst if isinstance(x, list) and len(x) > 2]
            except Exception:
                pass
    names = build_name_dict(titles)
    stamp = now.astimezone().strftime("%Y%m%d_%H%M%S")
    prev, prev_name = _load_prev(stamp + ".json") if write else ({}, None)
    rows = rank(vids, cmap, names, now, prev)
    ok = sum(1 for g in got.values() if "error" not in g)
    meta = {"when": now.astimezone().strftime("%Y-%m-%d %H:%M"), "channels": len(cmap), "ok": ok, "days": days, "videos": len(vids),
            "secs": round(time.time() - t0), "prev": prev_name, "errors": {c: g["error"] for c, g in got.items() if "error" in g}}
    res = {"meta": meta, "순위": rows, "snapshot": {v["id"]: [now.timestamp(), v["views"]] for v in vids}}
    if write:
        OUTDIR.mkdir(parents=True, exist_ok=True)
        if ok < len(cmap) * MIN_OK_FRAC:            # 응답 채널이 모자라면 최신.md·이전 기록(다음 실행의 증가량 기준)을 덮지 않는다
            meta["kept_previous"] = True
            json.dump(res, open(OUTDIR / f"_실패_{stamp}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"[경고] 응답 채널 {ok}/{len(cmap)} < {MIN_OK_FRAC:.0%} — 최신.md 를 그대로 둔다(실패 기록 _실패_{stamp}.json)", file=sys.stderr)
            return res
        json.dump(res, open(OUTDIR / f"{stamp}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        (OUTDIR / "최신.md").write_text(render_md(rows, top, meta), encoding="utf-8")
    return res


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args()
    r = run(a.days, a.top, a.limit)
    print(json.dumps(r["meta"], ensure_ascii=False)[:600])
    print(OUTDIR / "최신.md")
