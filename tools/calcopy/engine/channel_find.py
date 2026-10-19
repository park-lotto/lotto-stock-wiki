# -*- coding: utf-8 -*-
"""채널 찾기 엔진 — 현장썰 결 한국 채널 + 그 해외 원본 찾기 (2026-10-18, 관제 097).

현장썰 결 = 한국어 나레/자막 + 해외에서 찍힌 남의 원본 영상 재편집 + 원본 안에 제품.
판단의 주인: 이 파일 `judge_same_kind` 한 곳(같은 결 판정), `find_channels` 한 곳(방법 합치기·예산).
결과물 검사: `tools/calcopy/engine/channel_find_check.py`(아는 정답 — 핫템리포트·썰풀다=같은 결,
펀박스·앞북이·재밌쇼·갓성비=아님 — 과 대조, 엉터리 판정을 넣으면 빨강).

한 명령:
  py -m tools.calcopy.engine.channel_find --seeds channel/스타일분석/현장썰/채널수집/seeds.json \
      --out channel/스타일분석/현장썰/채널수집/결과_엔진_1차 [--methods lens,keyword,related,pool]
      [--serpapi 0] [--channels 260] [--gemini 300] [--audio 40]

방법(전부 함수 하나씩):
  lens     구글 렌즈 = 숏템메이커 SerpApi(`shopping_shorts/lens_discover.py:search_similar_videos`), 이미지 = 씨앗 썸네일
           i.ytimg.com/vi/<id>/hq720.jpg, **한국 로케일만·씨앗당 1회**. 키는 서버 /etc/shopping-shorts.env 에만 →
           SSH 로 서버에서 읽기 전용 실행(서버 파일 수정 0, 스크립트는 표준입력으로). 유료 — 캐시 우선, 새 호출은 --serpapi 예산만큼.
  keyword  yt-dlp ytsearch(씨앗 제목·제품 한국어/영어 검색어). 실측(kw_1~3 에이전트): 홍보·리뷰 채널이 대부분.
  related  같은 결로 판정된 한국 채널의 최근 쇼츠 상위 제목을 다시 검색 → 제목이 겹치는(같은 원본·소재) 다른 채널.
  pool     동종채널 조사(channel/sseolpulda/동종채널_2026-10-17.json, 발굴 DB 채널 캐시 RSS·해시태그) 후보 재사용.
채널 실측: `channel_stats`(yt-dlp 쇼츠 탭 최근 30편 조회 + RSS 원제목·업로드 날짜).
판정: `judge_same_kind` = 제목 규칙(언어·추천/리뷰 꼴) → 썸네일 4장+제목 30개 제미나이(공용 무료 풀 gemini_free, 버텍스 금지)
      → (화면 판정 통과만) 표본 2편 실측 `sample_check`(앞 40초 소리+썸네일: 나레·원음·해외 원본·제품) — 2편 다 해외 원본 아니면 뒤집고,
        갈래(현장썰/나레썰/자막썰)는 `channel_style`. 제품 여부는 표에 싣기만 한다(썰풀다처럼 조회 상위가 제품 아닌 편인 채널이 있어서).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
POOL_JSON = ROOT / "channel" / "sseolpulda" / "동종채널_2026-10-17.json"
SSH_KEY = "C:/Users/CH/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
SSH_HOST = "ubuntu@3.35.251.172"
SERVER_REPO = "/home/ubuntu/lotto-stock-wiki"

# 비용·호출 장부·캐시·채널 읽기 = engine/yt_channel(한 벌, 관제 234)
from tools.calcopy.engine.yt_channel import (CACHE, UA, NS, COST, _LOCK, _bump, _cache_path, _cached, _get,  # noqa: E402,F401
                                            ko_ratio, lang_of, _ydl, rss, channel_stats, _dt)

# 판정 문턱(주인 = 여기). 바꾸면 channel_find_check 를 다시 돌린다.
REVIEW_RE = re.compile(r"추천|TOP ?\d|top ?\d|Top ?\d|순위|가성비|후기|리뷰|최저가|할인|핫딜|특가|쿠팡|베스트|BEST|비교|언박싱|공구|구매처|내돈내산|광고|협찬")
REVIEW_MAX = 0.30          # 추천·리뷰 꼴 제목이 이 비율 이상이면 아님
KO_MIN = 0.50              # 제목 글자 중 한글 비율(RSS 원제목) — 이 아래면 한국 채널 아님
FOREIGN_MIN = 0.5          # 썸네일 중 해외 원본 장면 비율
PRODUCT_MIN = 0.3          # 제목 중 제품·물건 소재 비율
OK_LAYOUT = {"원본화면"}    # 같은 결로 치는 화면 꼴


# ------------------------------------------------------------------ 글자 판정(규칙)
def _tokens(t: str) -> set[str]:
    t = re.sub(r"#\S+", " ", t or "").lower()
    words = re.findall(r"[가-힣]{2,}|[a-z]{3,}", t)
    return {w for w in words if w not in {"shorts", "the", "and", "this", "with", "for", "you", "that"}}


def title_overlap(a: str, b: str) -> float:
    x, y = _tokens(a), _tokens(b)
    return len(x & y) / max(1, min(len(x), len(y))) if x and y else 0.0


# ------------------------------------------------------------------ 유튜브 읽기
def oembed(video_id: str) -> dict | None:
    def go():
        _bump("oembed")
        u = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/shorts/{video_id}", safe="")
        try:
            d = json.loads(_get(u, 15))
        except Exception:  # noqa: BLE001 — 비공개·삭제 영상은 None(호출부가 '채널 모름'으로 센다)
            return {"_fail": True}
        return {"title": d.get("title"), "author": d.get("author_name"), "author_url": urllib.parse.unquote(d.get("author_url") or "")}
    v = _cached("oembed", video_id, go, 24 * 30)
    return None if (not v or v.get("_fail")) else v


def ytsearch(query: str, n: int = 20) -> list[dict]:
    def go():
        _bump("ytsearch")
        try:
            with _ydl() as y:
                d = y.extract_info(f"ytsearch{n}:{query}", download=False)
        except Exception as e:  # noqa: BLE001
            return {"_err": str(e)[:200], "entries": []}
        out = []
        for e in d.get("entries") or []:
            out.append({"video_id": e.get("id"), "title": e.get("title"), "channel": e.get("channel"),
                        "channel_id": e.get("channel_id"), "views": e.get("view_count"), "duration": e.get("duration")})
        return {"entries": out}
    return (_cached("ytsearch", f"{n}|{query}", go, 72) or {}).get("entries", [])


def thumb(video_id: str) -> bytes | None:
    for f in ("oar2", "hq720", "hqdefault"):
        try:
            b = _get(f"https://i.ytimg.com/vi/{video_id}/{f}.jpg", 15)
            if len(b) > 2000:
                return b
        except Exception:  # noqa: BLE001
            continue
    return None


# ------------------------------------------------------------------ 제미나이(공용 무료 풀만)
def _ask(parts, prompt, tag):
    os.environ["BRAINBULB_VERTEX"] = "0"
    from tools.calcopy.engine import gemini_free
    _bump("gemini_calls")
    d, why = gemini_free.ask(parts, prompt, tag=tag)
    if d is None:
        _bump("gemini_failed")
    return d, why


# ------------------------------------------------------------------ 씨앗
def load_seeds(path: str | Path, exclude_bench=("foreignshowshow",)) -> list[dict]:
    """seeds.json → 샤크탱크(foreignshowshow, 다른 세션 담당) 뺀 씨앗. 제목·채널은 oEmbed 로 채운다."""
    seeds = [s for s in json.loads(Path(path).read_text(encoding="utf-8")) if s.get("bench") not in exclude_bench]
    with ThreadPoolExecutor(8) as ex:
        infos = list(ex.map(lambda s: oembed(s["id"]), seeds))
    for s, i in zip(seeds, infos):
        s["title"] = (i or {}).get("title") or ""
        s["channel"] = (i or {}).get("author")
        s["channel_url"] = (i or {}).get("author_url")
    return seeds


def seed_queries(seeds: list[dict]) -> dict:
    """씨앗별 검색어(한국어 2·영어 2) — 제미나이 1회로 묶어 만든다. 실패하면 제품명·제목만."""
    key = "|".join(s["id"] for s in seeds)

    def go():
        lines = "\n".join(f'{s["id"]}\t{s.get("product","")}\t{s.get("title","")}' for s in seeds)
        prompt = ("아래는 한국 유튜브 쇼츠(해외 원본 영상을 한국어로 재편집한 제품 썰) 목록이다(id, 제품, 제목).\n"
                  "각 줄마다 이 영상의 제품을 찾는 유튜브 검색어를 만들어라: ko = 한국 재편집 쇼츠가 쓸 법한 한국어 검색어 2개,"
                  " en = 해외 원본(틱톡·유튜브)을 찾을 영어 검색어 2개(제품의 영어 일반명 + 특징 2~4단어).\n"
                  'JSON: {"items":[{"id":..,"ko":[..],"en":[..]}]}\n\n' + lines)
        d, why = _ask([], prompt, "channel_find:queries")
        if not d:
            return None
        return {it["id"]: {"ko": it.get("ko") or [], "en": it.get("en") or []} for it in d.get("items", []) if it.get("id")}
    q = _cached("queries", key, go, 24 * 30) or {}
    for s in seeds:
        base = q.get(s["id"], {"ko": [], "en": []})
        t = re.sub(r"#\S+", " ", s.get("title", "")).strip()
        base["ko"] = [x for x in ([t] if t else []) + ([s["product"]] if s.get("product") else []) + base["ko"] if x][:4]
        q[s["id"]] = base
    return q


# ------------------------------------------------------------------ 방법 1: 렌즈(서버 SerpApi)
_REMOTE_LENS = r'''
import json,sys,time
sys.path.insert(0,"%s")
from shopping_shorts import lens_discover as L
seeds=json.loads(sys.argv[1])
out=[]
for sid in seeds:
    st={}
    try: r=L.search_similar_videos(f"https://i.ytimg.com/vi/{sid}/hq720.jpg",locales=[("ko","kr")],stats=st)
    except Exception as e: r=[];st["err"]=str(e)[:100]
    out.append({"seed_id":sid,"stats":st,"hits":r}); time.sleep(2)
print("@@JSON@@"+json.dumps(out,ensure_ascii=False))
''' % SERVER_REPO


def lens_import(path: str | Path) -> int:
    """다른 에이전트가 이미 낸 렌즈 결과(list of {seed_id, stats, hits})를 캐시로 들인다 — 같은 씨앗에 돈을 두 번 안 쓴다."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = d if isinstance(d, list) else (d.get("seed_results") or d.get("seeds") or [])   # lens.json(에이전트) = seed_results
    n = 0
    for r in rows:
        sid = r.get("seed_id") or r.get("id")
        if sid and "hits" in r:
            _cache_path("lens", sid).write_text(json.dumps({"stats": r.get("stats", {}), "hits": r["hits"], "imported_from": str(path)}, ensure_ascii=False), encoding="utf-8")
            n += 1
    return n


def method_lens(seeds: list[dict], budget: dict) -> list[dict]:
    """씨앗 썸네일로 구글 렌즈(한국 로케일·씨앗당 1회). 캐시 먼저, 없는 씨앗만 서버에서 새로 부른다(예산 budget['serpapi'])."""
    todo, rows = [], {}
    for s in seeds:
        p = _cache_path("lens", s["id"])
        if p.exists():
            rows[s["id"]] = json.loads(p.read_text(encoding="utf-8"))
            _bump("serpapi_calls_cached", int(rows[s["id"]].get("stats", {}).get("serpapi_calls", 1) or 0))
        else:
            todo.append(s["id"])
    allow = max(0, int(budget.get("serpapi", 0)))
    run = todo[:allow]
    if run:
        cmd = ["ssh", "-o", "ConnectTimeout=15", "-i", SSH_KEY, SSH_HOST,
               f"cd {SERVER_REPO} && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && python3 - '{json.dumps(run)}'"]
        p = subprocess.run(cmd, input=_REMOTE_LENS.encode("utf-8"), capture_output=True, timeout=60 + 20 * len(run))
        txt = p.stdout.decode("utf-8", "replace")
        if "@@JSON@@" in txt:
            for r in json.loads(txt.split("@@JSON@@", 1)[1]):
                c = int(r.get("stats", {}).get("serpapi_calls", 1) or 0)
                _bump("serpapi_calls_new", c)
                budget["serpapi"] = budget.get("serpapi", 0) - c
                _cache_path("lens", r["seed_id"]).write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
                rows[r["seed_id"]] = r
    hits = []
    for s in seeds:
        r = rows.get(s["id"])
        if not r:
            continue
        for h in r.get("hits", []):
            hit = {"via": "lens", "seed": s["id"], "platform": h.get("platform"), "url": h.get("url"), "title": h.get("title") or ""}
            m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", h.get("url") or "")
            if h.get("platform") == "youtube" and m:
                hit["video_id"] = m.group(1)
            m2 = re.search(r"tiktok\.com/(@[^/]+)", h.get("url") or "")
            if m2:
                hit["channel"] = m2.group(1)
            hits.append(hit)
    yt = [h for h in hits if h.get("video_id")]
    with ThreadPoolExecutor(8) as ex:
        infos = list(ex.map(lambda h: oembed(h["video_id"]), yt))
    for h, i in zip(yt, infos):
        if i:
            h["channel"] = i.get("author")
            h["channel_url"] = i.get("author_url")
            h["title"] = i.get("title") or h["title"]
    return hits


# ------------------------------------------------------------------ 방법 2: 키워드(yt-dlp)
def method_keyword(seeds: list[dict], budget: dict, queries: dict | None = None, per_query: int = 20) -> list[dict]:
    queries = queries or seed_queries(seeds)
    jobs = []
    for s in seeds:
        q = queries.get(s["id"], {})
        for lang in ("ko", "en"):
            for qq in q.get(lang, [])[:4 if lang == "ko" else 2]:
                jobs.append((s["id"], lang, qq))
    jobs = jobs[:max(0, int(budget.get("ytsearch", 400)))]
    budget["ytsearch"] = budget.get("ytsearch", 400) - len(jobs)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda j: ytsearch(j[2], per_query), jobs))
    hits = []
    for (sid, lang, qq), ents in zip(jobs, res):
        for e in ents:
            if not e.get("channel_id"):
                continue
            hits.append({"via": "keyword", "seed": sid, "query": qq, "qlang": lang, "platform": "youtube",
                         "video_id": e["video_id"], "title": e.get("title") or "", "channel": e.get("channel"),
                         "channel_id": e["channel_id"], "views": e.get("views"), "duration": e.get("duration")})
    return hits


def keyword_import(paths: list[str | Path]) -> list[dict]:
    """키워드 수집 에이전트 결과(kw_1~3.json: seeds[].hits)를 키워드 결과로 들인다 — 같은 검색을 다시 안 한다."""
    hits = []
    for p in paths:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        for sd in d.get("seeds", []):
            for e in sd.get("hits", []):
                if e.get("channel_id"):
                    hits.append({"via": "keyword", "seed": sd.get("id"), "query": "(kw import)", "qlang": "?", "platform": "youtube",
                                 "video_id": e.get("video_id"), "title": e.get("title") or "", "channel": e.get("channel"),
                                 "channel_id": e["channel_id"], "views": e.get("views"), "src": Path(p).name})
    return hits


# ------------------------------------------------------------------ 방법 3: 넓히기(같은 원본·소재 제목)
def method_related(channels: list[dict], budget: dict, per_channel: int = 3, min_overlap: float = 0.5) -> list[dict]:
    """같은 결 한국 채널 → 조회 상위 쇼츠 제목 per_channel 개를 다시 검색 → 제목 겹침 ≥ min_overlap 인 **다른** 채널 영상."""
    jobs = []
    for c in channels:
        vids = sorted([v for v in c.get("videos", []) if v.get("views")], key=lambda v: -v["views"])[:per_channel]
        for v in vids:
            t = re.sub(r"#\S+", " ", v.get("title") or "").strip()
            if len(t) >= 6:
                jobs.append((c["channel_id"], v["id"], t))
    jobs = jobs[:max(0, int(budget.get("ytsearch", 0)))]
    budget["ytsearch"] = budget.get("ytsearch", 0) - len(jobs)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda j: ytsearch(j[2], 15), jobs))
    hits = []
    for (cid, vid, t), ents in zip(jobs, res):
        for e in ents:
            if not e.get("channel_id") or e["channel_id"] == cid:
                continue
            ov = title_overlap(t, e.get("title") or "")
            if e.get("video_id") == vid or ov >= min_overlap:
                hits.append({"via": "related", "seed": f"{cid}:{vid}", "query": t, "platform": "youtube",
                             "video_id": e["video_id"], "title": e.get("title") or "", "channel": e.get("channel"),
                             "channel_id": e["channel_id"], "views": e.get("views"), "overlap": round(ov, 2)})
    return hits


# ------------------------------------------------------------------ 방법 4: 동종 조사 후보 재사용
def method_pool(path: Path = POOL_JSON) -> list[dict]:
    if not Path(path).exists():
        return []
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return [{"via": "pool", "seed": "동종채널_2026-10-17", "platform": "youtube", "channel": c.get("name"),
             "channel_id": c.get("channel_id"), "title": "", "pool_group": c.get("group"), "pool_judge": c.get("style")}
            for c in d.get("channels", []) if c.get("channel_id")]


# ------------------------------------------------------------------ 같은 결 판정(주인)
JUDGE_PROMPT = """아래는 한 유튜브 채널의 최근 쇼츠 썸네일 {k}장과 최근 쇼츠 제목(조회수)이다.
이 채널의 주된 영상 꼴을 판정하라. 우리가 찾는 '현장썰 결' = 해외에서 찍힌 남의 원본 영상(외국인·해외 장소·해외 틱톡/방송 클립)을
가져와 한국어 자막·나레로 재편집하고, 영상 안에 실제 제품(물건·발명품·도구·음식 상품)이 나오는 제품 썰.
화면 꼴(layout) 하나를 고른다:
- 원본화면: 화면 대부분이 남의 원본 영상(실사 클립), 그 위에 한국어 자막/제목 띠 정도
- 게시글형: 위에 채널 머리띠 + 게시글 제목 + 자막 칸 + 그림 칸이 나뉜 커뮤니티 게시글 틀
- AI그림: AI 생성 그림·일러스트·캐릭터가 화면 대부분
- 직접촬영: 채널 주인이 직접 찍은 리뷰·언박싱·사용기·요리
- 방송클립: 한국 예능·연예인·드라마 클립 위주
- 기타
JSON 으로만: {{"layout": "...", "foreign_original": 0~1(썸네일 중 해외 원본 실사 장면 비율), "product_share": 0~1(제목 중 제품·물건 소재 비율),
"korean_text": true/false(화면·제목에 한국어), "reason": "한 문장 근거(썸네일에서 본 것)"}}

제목:
{titles}"""


def judge_same_kind(st: dict, use_gemini: bool = True, use_samples: bool = True) -> dict:
    """채널 실측(channel_stats) → {same_kind: True/False/None, stage, reason, evidence}. 같은 결 판정은 여기 한 곳."""
    titles = [v.get("title") or "" for v in st.get("videos", [])]
    ev = {"n": st.get("n"), "lang": st.get("lang"), "ko_ratio": st.get("ko_ratio")}
    if (st.get("n") or 0) < 3:
        return {"same_kind": None, "stage": "rule", "reason": "쇼츠 3편 미만 — 판정 불가", "evidence": ev}
    if st.get("lang") != "ko" or (st.get("ko_ratio") or 0) < KO_MIN:
        return {"same_kind": False, "stage": "rule", "reason": f"한국 채널 아님(원제목 언어 {st.get('lang')}, 한글 {st.get('ko_ratio')})", "evidence": ev}
    rv = sum(1 for t in titles if REVIEW_RE.search(t)) / max(1, len(titles))
    ev["review_ratio"] = round(rv, 2)
    if rv >= REVIEW_MAX:
        return {"same_kind": False, "stage": "rule", "reason": f"쇼핑 추천·리뷰 꼴 제목 {rv:.0%}", "evidence": ev}
    if not use_gemini:
        return {"same_kind": None, "stage": "rule", "reason": "규칙 통과 — 화면 판정 안 함", "evidence": ev}
    vids = [v for v in st.get("videos", []) if v.get("id")]
    by_views = sorted([v for v in vids if v.get("views")], key=lambda v: -v["views"])
    pick = []
    for v in by_views[:2] + vids[:2] + by_views[2:4]:
        if v["id"] not in [p["id"] for p in pick]:
            pick.append(v)
    pick = pick[:4]
    imgs = [b for b in (thumb(v["id"]) for v in pick) if b]
    if not imgs:
        return {"same_kind": None, "stage": "gemini", "reason": "썸네일 못 받음", "evidence": ev}
    tl = "\n".join(f"- {v.get('views')}회 {v.get('title')}" for v in vids[:30])

    def go():
        d, why = _ask(imgs, JUDGE_PROMPT.format(k=len(imgs), titles=tl), f"channel_find:judge:{st['channel_id']}")
        return d if d else {"_fail": why}
    g = _cached("judge", f"v1|{st['channel_id']}|{','.join(p['id'] for p in pick)}", go, 24 * 7)
    if not g or g.get("_fail"):
        return {"same_kind": None, "stage": "gemini", "reason": f"제미나이 실패 {g and g.get('_fail')}", "evidence": ev}
    ev.update({"layout": g.get("layout"), "foreign_original": g.get("foreign_original"), "product_share": g.get("product_share"),
               "thumbs": [p["id"] for p in pick], "gemini_reason": g.get("reason")})
    fo, ps = float(g.get("foreign_original") or 0), float(g.get("product_share") or 0)
    ok = g.get("layout") in OK_LAYOUT and fo >= FOREIGN_MIN and ps >= PRODUCT_MIN
    why = []
    if g.get("layout") not in OK_LAYOUT:
        why.append(f"화면 꼴 {g.get('layout')}")
    if fo < FOREIGN_MIN:
        why.append(f"해외 원본 {fo:.0%}")
    if ps < PRODUCT_MIN:
        why.append(f"제품 소재 {ps:.0%}")
    reason = ("같은 결: " if ok else "아님: ") + (f"원본화면·해외 원본 {fo:.0%}·제품 소재 {ps:.0%}" if ok else ", ".join(why)) + f" — {g.get('reason')}"
    if not ok or not use_samples:
        return {"same_kind": ok, "stage": "gemini", "reason": reason, "evidence": ev}
    # 3단: 표본 2편(조회 상위 중 제목이 추천·리뷰 꼴 아닌 것) 실측 — 2편 다 해외 원본 아님 / 2편 다 제품 아님이면 뒤집는다
    with _LOCK:
        if SAMPLES_LEFT[0] <= 0:
            ev["samples"] = []
            return {"same_kind": ok, "stage": "gemini", "reason": reason + " (표본 실측 예산 끝 — 화면 판정만)", "evidence": ev}
        SAMPLES_LEFT[0] -= 1
    cand = [v for v in by_views if not REVIEW_RE.search(v.get("title") or "")][:2]
    smp = [sample_check(v["id"]) for v in cand]
    ev["samples"] = smp
    good = [x for x in smp if x.get("ok")]
    ev["style"] = channel_style(smp)
    if len(good) >= 2 and not any(x["foreign_original"] for x in good):
        return {"same_kind": False, "stage": "sample", "reason": f"아님: 표본 {len(good)}편 모두 해외 원본 아님 — {good[0].get('note')}", "evidence": ev}
    tag = " / ".join(f"{x['video_id']} {x['style']}·해외{'O' if x['foreign_original'] else 'X'}·제품{'O' if x['product'] else 'X'}" for x in good)
    return {"same_kind": True, "stage": "sample" if good else "gemini", "reason": reason + (f" · 표본: {tag}" if tag else " · 표본 실측 실패"), "evidence": ev}


SAMPLE_PROMPT = """소리 = 한국 유튜브 쇼츠 1편의 앞부분 최대 40초, 그림 = 같은 편의 썸네일. 4가지를 판정하라.
JSON 으로만: {"korean_narration": true/false(한국어 나레이션·TTS 목소리가 들림),
"original_audio": true/false(원본 영상의 현장 소리 — 외국어 말·감탄·리액션·현장음이 나레 없이 들리는 구간이 있음),
"original_share": 0~1(원본 현장 소리 구간 비율), "original_lang": "영어/일본어/중국어/한국어/말없음/기타",
"foreign_original": true/false(화면·소리가 해외에서 찍힌 남의 원본 영상 — 외국인·해외 장소·외국어 원음),
"product": true/false(영상의 중심이 실제 제품·물건·발명품·도구·음식 상품), "note": "한 문장 근거"}"""
SAMPLES_LEFT = [40]       # 표본 실측 채널 수 상한(find_channels 가 budget['audio'] 로 맞춘다)


def sample_check(video_id: str) -> dict:
    """표본 1편 실측 4가지(나레·원음·해외 원본·제품) — 앞 40초 소리(저음질 mp3 ~0.2MB, 판정 뒤 지움) + 썸네일.
    (현장썰 채널 찾기 에이전트의 '표본 2편 실측' 방법을 함수로 옮김, 10-18)"""
    def go():
        tmp = CACHE / "audio"
        tmp.mkdir(parents=True, exist_ok=True)
        mp3 = tmp / f"{video_id}.mp3"
        if not mp3.exists():
            try:
                with _ydl({"extract_flat": False, "skip_download": False, "format": "worstaudio/worst",
                           "outtmpl": str(tmp / f"{video_id}.%(ext)s")}) as y:
                    info = y.extract_info(f"https://www.youtube.com/shorts/{video_id}", download=True)
                src = Path(y.prepare_filename(info))
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-t", "40", "-ac", "1", "-b:a", "32k", str(mp3)],
                               check=True, timeout=120)
                _bump("audio_downloads")
                _bump("audio_bytes", src.stat().st_size)
                src.unlink(missing_ok=True)
            except Exception as e:  # noqa: BLE001 — 받기 실패는 표본 실패로 남긴다(판정에서 빠짐)
                return {"_fail": f"download {str(e)[:120]}"}
        parts = [(mp3.read_bytes(), "audio/mp3")]
        t = thumb(video_id)
        if t:
            parts.append(t)
        d, why = _ask(parts, SAMPLE_PROMPT, f"channel_find:sample:{video_id}")
        mp3.unlink(missing_ok=True)
        return d if d else {"_fail": why}
    a = _cached("sample", f"v1|{video_id}", go, 24 * 30) or {}
    if a.get("_fail"):
        return {"video_id": video_id, "ok": False, "reason": a["_fail"]}
    nar, ori = bool(a.get("korean_narration")), bool(a.get("original_audio"))
    style = "현장썰" if (nar and ori) else "나레썰" if nar else "자막썰" if ori else "불명"
    return {"video_id": video_id, "ok": True, "style": style, "korean_narration": nar, "original_audio": ori,
            "original_share": a.get("original_share"), "original_lang": a.get("original_lang"),
            "foreign_original": bool(a.get("foreign_original")), "product": bool(a.get("product")), "note": a.get("note")}


def channel_style(samples: list[dict]) -> str | None:
    """표본 갈래 → 채널 갈래: 표본 하나라도 현장썰이면 현장썰(썰풀다처럼 섞인 채널), 아니면 많은 쪽."""
    ok = [x["style"] for x in samples if x.get("ok")]
    if not ok:
        return None
    if "현장썰" in ok:
        return "현장썰"
    return max(set(ok), key=ok.count)


# ------------------------------------------------------------------ 해외 원본 후보
def foreign_originals(seeds: list[dict], hits: list[dict], channels: dict, queries: dict) -> list[dict]:
    """씨앗별 해외 원본 후보: 렌즈·영어 검색 결과 중 비한국어 제목(또는 비한국 채널) 영상. 영어 검색어 낱말과 겹치면 match."""
    out = []
    for s in seeds:
        en_words = set()
        for q in queries.get(s["id"], {}).get("en", []):
            en_words |= {w for w in re.findall(r"[a-z]{3,}", q.lower())}
        cands, seen = [], set()
        for h in hits:
            if h.get("seed") != s["id"] or h.get("via") not in ("lens", "keyword"):
                continue
            ch = channels.get(h.get("_ckey") or "")
            title = h.get("title") or ""
            foreign = ko_ratio([title]) < 0.3 if title.strip() else False
            if ch and ch.get("lang") not in (None, "?"):
                foreign = ch["lang"] != "ko"
            # 렌즈의 인스타·틱톡 링크는 원본 후보로 전부 싣는다(조정자 10-18) — 한국어 캡션이면 foreign=False 로 표시만
            if not foreign and not (h["via"] == "lens" and h.get("platform") in ("instagram", "tiktok")):
                continue
            key = h.get("video_id") or h.get("url")
            if key in seen:
                continue
            seen.add(key)
            words = set(re.findall(r"[a-z]{3,}", title.lower()))
            dur = h.get("duration")
            if isinstance(dur, (int, float)) and dur > 180:
                continue
            cands.append({"via": h["via"], "platform": h.get("platform"), "url": h.get("url") or f"https://www.youtube.com/shorts/{h.get('video_id')}",
                          "title": title[:140], "channel": h.get("channel"), "views": h.get("views") or (ch or {}).get("max_views"),
                          "lang": (ch or {}).get("lang") or lang_of([title]), "foreign": foreign,
                          "match": bool(en_words & words), "match_words": sorted(en_words & words)})
        cands.sort(key=lambda c: (not c["foreign"], not c["match"], -(c["views"] or 0)))
        out.append({"seed": s["id"], "product": s.get("product"), "seed_title": s.get("title"),
                    "n_foreign": sum(1 for c in cands if c["foreign"]), "candidates": cands[:15]})
    return out


# ------------------------------------------------------------------ 주인 함수
DEFAULT_BUDGET = {"serpapi": 0, "ytsearch": 400, "channels": 260, "gemini": 300, "audio": 40}


def _ckey(h: dict) -> str | None:
    if h.get("channel_id"):
        return h["channel_id"]
    u = h.get("channel_url") or ""
    return u if u.startswith("https://www.youtube.com/") else None


def find_channels(seeds: list[dict], methods=("lens", "keyword", "related"), budget: dict | None = None,
                  probe: dict | None = None, judge=None, log=print, extra_hits: list[dict] | None = None) -> dict:
    """씨앗 → {channels:[같은 결 판정 포함 채널], originals:[씨앗별 해외 원본 후보], harvest, cost}.

    probe = {이름: 채널 주소} — 방법과 상관없이 실측·판정할 채널(정답 검사용, 수확에는 안 센다).
    judge = 판정 함수 바꿔 끼우기(검사 도구가 엉터리 판정으로 빨강을 내 보는 자리). 기본 judge_same_kind.
    """
    judge = judge or judge_same_kind
    budget = dict(DEFAULT_BUDGET, **(budget or {}))
    SAMPLES_LEFT[0] = int(budget["audio"])
    t0 = time.time()
    queries = seed_queries(seeds) if ("keyword" in methods or True) else {}
    hits: list[dict] = []
    for s in seeds:   # 씨앗 자기 채널(벤치) — 정답 검사·제외용
        if s.get("channel_url"):
            hits.append({"via": "seed", "seed": s["id"], "platform": "youtube", "video_id": s["id"], "title": s.get("title"),
                         "channel": s.get("channel"), "channel_url": s["channel_url"]})
    if "lens" in methods:
        h = method_lens(seeds, budget); hits += h; log(f"[lens] {len(h)}건")
    if "keyword" in methods:
        h = method_keyword(seeds, budget, queries); hits += h; log(f"[keyword] {len(h)}건")
    if "pool" in methods:
        h = method_pool(); hits += h; log(f"[pool] {len(h)}건")
    if extra_hits:
        hits += extra_hits; log(f"[들인 결과] {len(extra_hits)}건")
    for name, ref in (probe or {}).items():
        hits.append({"via": "probe", "seed": name, "platform": "youtube", "channel": name, "channel_url": ref})

    channels: dict[str, dict] = {}

    def _measure(keys):
        keys = [k for k in keys if k not in channels]
        keys = keys[:max(0, budget["channels"])]
        budget["channels"] -= len(keys)
        with ThreadPoolExecutor(8) as ex:
            sts = list(ex.map(channel_stats, keys))
        url2id = {}
        for k, st in zip(keys, sts):
            channels[k] = st or {"_fail": True, "ref": k}
            if st:
                url2id[k] = st["channel_id"]
        return url2id

    def _attach(hs):
        for h in hs:
            if h.get("platform") != "youtube":
                continue
            k = _ckey(h)
            if k:
                h["_ckey"] = k

    def _wanted(hs):
        """실측할 채널 고르기: 키워드 결과는 추천·리뷰 꼴·조회 1천 미만 제목뿐인 채널은 미리 뺀다(실측 비용 절약)."""
        by = {}
        for h in hs:
            if h.get("_ckey"):
                by.setdefault(h["_ckey"], []).append(h)
        keep, dropped = [], 0
        for k, hh in by.items():
            vias = {x["via"] for x in hh}
            if vias <= {"keyword", "related"}:
                good = [x for x in hh if not REVIEW_RE.search(x.get("title") or "") and (x.get("views") or 0) >= 1000]
                if not good:
                    dropped += 1
                    continue
            keep.append((k, -max((x.get("views") or 0) for x in hh), -len(hh)))
        keep.sort(key=lambda x: (x[1], x[2]))
        must = [k for k, *_ in keep if any(x["via"] in ("seed", "probe", "lens", "pool") for x in by[k])]
        rest = [k for k, *_ in keep if k not in must]
        return must + rest, dropped, by

    _attach(hits)
    order, dropped, _ = _wanted(hits)
    log(f"[실측] 후보 채널 {len(order)}(미리 뺌 {dropped})")
    url2id = _measure(order)
    for h in hits:          # 주소(@핸들)로 들어온 채널을 UC id 로 합친다
        if h.get("_ckey") in url2id:
            h["_ckey"] = url2id[h["_ckey"]]
    merged: dict[str, dict] = {}
    for k, st in channels.items():
        if st and not st.get("_fail"):
            merged[st["channel_id"]] = st
    log(f"[실측] 성공 {len(merged)}")

    verdict: dict[str, dict] = {}

    def _judge_all(ids):
        ids = [i for i in ids if i not in verdict]
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(lambda i: judge(merged[i]), ids))
        for i, r in zip(ids, res):
            verdict[i] = r
    _judge_all(list(merged))
    log(f"[판정] 같은 결 {sum(1 for v in verdict.values() if v.get('same_kind'))}")

    if "related" in methods:
        same = [merged[i] for i, v in verdict.items() if v.get("same_kind")]
        rh = method_related(same, budget)
        _attach(rh)
        hits += rh
        order2, d2, _ = _wanted(rh)
        dropped += d2
        url2id = _measure(order2)
        for k, st in channels.items():
            if st and not st.get("_fail"):
                merged.setdefault(st["channel_id"], st)
        _judge_all(list(merged))
        log(f"[related] {len(rh)}건 → 같은 결 {sum(1 for v in verdict.values() if v.get('same_kind'))}")

    # 채널 목록 조립
    by_ch: dict[str, list] = {}
    for h in hits:
        if h.get("_ckey") in merged:
            by_ch.setdefault(h["_ckey"], []).append(h)
    out_ch = []
    for cid, st in merged.items():
        hh = by_ch.get(cid, [])
        vias = sorted({h["via"] for h in hh})
        v = verdict.get(cid, {})
        out_ch.append({
            "name": st.get("name"), "channel_id": cid, "handle": st.get("handle"), "url": st["url"], "lang": st.get("lang"),
            "subs": st.get("subs"), "n": st.get("n"), "median_views": st.get("median_views"), "max_views": st.get("max_views"),
            "per_week": st.get("per_week"), "last_upload": st.get("last_upload"),
            "found_by": vias, "found_seeds": sorted({h["seed"] for h in hh if h["via"] not in ("probe", "pool")}),
            "probe": vias == ["probe"] or ("probe" in vias and not (set(vias) - {"probe", "seed"})),
            "bench": "seed" in vias,
            "same_kind": v.get("same_kind"), "reason": v.get("reason"), "stage": v.get("stage"), "evidence": v.get("evidence"),
            "style": (v.get("evidence") or {}).get("style"), "samples": (v.get("evidence") or {}).get("samples"),
            "hit_titles": [h.get("title") for h in hh if h.get("title")][:5],
            "recent_titles": [x.get("title") for x in st.get("videos", [])[:8]],
        })
    out_ch.sort(key=lambda c: (c["same_kind"] is not True, -(c["median_views"] or 0)))

    for h in hits:
        if h.get("_ckey") in merged:
            st = merged[h["_ckey"]]
            h["views"] = h.get("views")
    originals = foreign_originals(seeds, hits, merged, queries)

    harvest = {}
    for m in ("seed", "lens", "keyword", "related", "pool", "probe"):
        hs = [h for h in hits if h["via"] == m]
        cids = {h["_ckey"] for h in hs if h.get("_ckey") in merged}
        harvest[m] = {"hits": len(hs), "youtube_channels_measured": len(cids),
                      "same_kind": sum(1 for c in cids if verdict.get(c, {}).get("same_kind")),
                      "same_kind_new": sum(1 for c in cids if verdict.get(c, {}).get("same_kind")
                                           and not any(x["via"] in ("seed", "probe") for x in by_ch.get(c, [])))}
    for kind, k in (("judge", "gemini_judge_cached"), ("sample", "gemini_sample_cached")):
        COST[k] = len(list((CACHE / kind).glob("*.json"))) if (CACHE / kind).exists() else 0
    COST["gemini_total_cached"] = COST["gemini_judge_cached"] + COST["gemini_sample_cached"] + 1
    return {"made": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "methods": list(methods), "seeds": [{k: s.get(k) for k in ("id", "bench", "product", "title", "channel")} for s in seeds],
            "queries": queries, "thresholds": {"REVIEW_MAX": REVIEW_MAX, "KO_MIN": KO_MIN, "FOREIGN_MIN": FOREIGN_MIN,
                                               "PRODUCT_MIN": PRODUCT_MIN, "OK_LAYOUT": sorted(OK_LAYOUT)},
            "channels": out_ch, "originals": originals, "harvest": harvest, "dropped_prefilter": dropped,
            "cost": dict(COST), "budget_left": budget, "sec": round(time.time() - t0)}


# ------------------------------------------------------------------ 보고서
def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return f"{v:,}" if isinstance(v, int) else str(v)


def write_report(res: dict, out: Path) -> None:
    out.with_suffix(".json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    ch = res["channels"]
    same = [c for c in ch if c["same_kind"] and c["lang"] == "ko"]
    L = [f"# 현장썰 채널 찾기 — 엔진 1차 ({res['made'][:16]}, 관제 097)", "",
         "> 엔진 `tools/calcopy/engine/channel_find.py:find_channels` · 검사 `channel_find_check.py` · 원자료 같은 이름 `.json`.",
         f"> 씨앗 {len(res['seeds'])}편(샤크탱크 제외) · 방법 {', '.join(res['methods'])} · 걸린 시간 {res['sec']}초.",
         f"> 같은 결 판정 = 제목 규칙(한글 ≥{KO_MIN:.0%}, 추천·리뷰 꼴 <{REVIEW_MAX:.0%}) → 썸네일 4장+제목 제미나이(화면 꼴=원본화면, 해외 원본 ≥{FOREIGN_MIN:.0%}, 제품 소재 ≥{PRODUCT_MIN:.0%}) → 표본 2편 실측(앞 40초 소리+썸네일: 나레·원음·해외 원본·제품, 2편 다 해외 원본 아니면 뒤집음). 갈래 = 표본 중 하나라도 나레+원음이면 현장썰.",
         "", f"## 1. 같은 결 한국 채널 {len(same)}개 (최근 쇼츠 조회 중앙 순)", "",
         "| # | 채널 | 주소 | 구독 | 최근 n | 중앙 | 최대 | 주당 | 최근 업로드 | 갈래(표본 2편) | 찾은 방법 | 걸린 씨앗 수 | 근거 |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, c in enumerate(same, 1):
        smp = [x for x in (c.get("samples") or []) if x.get("ok")]
        st = c.get("style") or "-"
        if smp:
            st += "(" + ", ".join(f"{x['style']} 원음{float(x.get('original_share') or 0):.0%}" for x in smp) + ")"
        L.append(f"| {i} | {c['name']}{' (벤치)' if c['bench'] else ''}{' (검사용)' if c['probe'] else ''} | {c['url']} | {_fmt(c['subs'])} | {c['n']} | {_fmt(c['median_views'])} | {_fmt(c['max_views'])} | {_fmt(c['per_week'])} | {c['last_upload'] or '-'} | {st} | {', '.join(c['found_by'])} | {len(c['found_seeds'])} | {(c['reason'] or '').replace('|', '/')[:110]} |")
    nos = [c for c in ch if c["same_kind"] is False]
    L += ["", f"## 2. 같은 결 아님 {len(nos)}개 · 판정 못 함 {sum(1 for c in ch if c['same_kind'] is None)}개 (이유별)", ""]
    reasons = {}
    for c in nos:
        ev = c.get("evidence") or {}
        if c["stage"] == "rule":
            r = "제목 규칙: " + ("한국 채널 아님" if "한국 채널 아님" in (c["reason"] or "") else "추천·리뷰 꼴 제목")
        elif c["stage"] == "sample":
            r = "표본 2편: 해외 원본 아님"
        else:
            r = f"화면 판정: {ev.get('layout')}" + ("" if ev.get("layout") in OK_LAYOUT else "") + (
                " (원본화면이지만 해외 원본·제품 소재 부족)" if ev.get("layout") in OK_LAYOUT else "")
        reasons[r] = reasons.get(r, 0) + 1
    for r, n in sorted(reasons.items(), key=lambda x: -x[1]):
        L.append(f"- {r}: {n}")
    probes = [c for c in ch if "probe" in c["found_by"] or c["bench"]]
    L += ["", "### 정답 대조용 채널(벤치·검사용)", "", "| 채널 | 판정 | 근거 |", "|---|---|---|"]
    for c in probes:
        L.append(f"| {c['name']} | {c['same_kind']} | {(c['reason'] or '').replace('|', '/')[:150]} |")
    n_or = sum(o.get("n_foreign", 0) for o in res["originals"])
    n_seed = sum(1 for o in res["originals"] if o.get("n_foreign"))
    L += ["", f"## 3. 해외 원본 후보 {n_or}건 · 후보 있는 씨앗 {n_seed}/{len(res['originals'])}", "",
          "> 해외 = 비한국어 제목/채널(렌즈·영어 검색). ✓ = 영어 검색어 낱말이 제목에 있음(같은 제품일 가능성↑). 렌즈의 한국어 캡션 인스타·틱톡은 json 에 foreign=false 로만 남김. **같은 원본인지는 아직 눈 확인 전**.", "",
          "| 씨앗 | 제품 | 해외 후보 수 | 상위 후보(방법·플랫폼·채널·조회) |", "|---|---|---|---|"]
    for o in res["originals"]:
        fc = [c for c in o["candidates"] if c.get("foreign")]
        top = " / ".join(f"[{c['via']}·{c['platform']}{'✓' if c['match'] else ''}] {c['channel'] or '?'} {_fmt(c['views'])} {c['url']}" for c in fc[:3])
        L.append(f"| {o['seed']} | {o['product'] or ''} | {o.get('n_foreign', 0)} | {top or '-'} |")
    L += ["", "## 4. 방법별 수확", "", "| 방법 | 결과 건수 | 실측 채널 | 같은 결 | 같은 결(벤치·검사용 뺀 새 채널) | 이 방법으로만 찾은 같은 결 |", "|---|---|---|---|---|---|"]
    for m, h in res["harvest"].items():
        only = sum(1 for c in same if not c["bench"] and "probe" not in c["found_by"] and set(c["found_by"]) - {"seed", "probe"} == {m})
        L.append(f"| {m} | {h['hits']} | {h['youtube_channels_measured']} | {h['same_kind']} | {h['same_kind_new']} | {only} |")
    L.append(f"\n- 키워드·넓히기 결과 중 추천·리뷰 꼴·조회 1천 미만 제목뿐이라 실측 전에 뺀 채널: {res['dropped_prefilter']}")
    c = res["cost"]
    L += ["", "## 5. 비용", "",
          f"- SerpApi(유료): 이번 실행 새 호출 **{c['serpapi_calls_new']}회** · 캐시 재사용 {c['serpapi_calls_cached']}회분(10-18 01:31~01:45 렌즈 에이전트가 서버에서 씨앗당 1회·한국 로케일로 낸 결과)",
          f"- 제미나이(공용 무료 풀 gemini_free, 버텍스 0): 이번 실행 호출 {c['gemini_calls']}회(실패 {c['gemini_failed']}) — 캐시 적중분은 호출 안 함"
          + (f" · 캐시 포함 누적 {c['gemini_total_cached']}회(채널 화면 판정 {c.get('gemini_judge_cached')}·표본 {c.get('gemini_sample_cached')}·검색어 1)" if c.get("gemini_total_cached") else ""),
          f"- yt-dlp 검색 {c['ytsearch']}회 · 채널 실측 {c['channel_stats']}회 · oEmbed {c['oembed']}회 · 소리 표본 다운로드 {c['audio_downloads']}편({c['audio_bytes']/1e6:.1f}MB, 앞 40초만 남기고 지움)"]
    out.with_suffix(".md").write_text("\n".join(L) + "\n", encoding="utf-8")


TRUTH_PROBE = {   # 정답 검사용(channel_find_check 와 같은 표 — 이름만 여기서 주인)
    "핫템리포트": "https://www.youtube.com/@핫템리포트",
    "썰풀다": "https://www.youtube.com/@썰풀다",
    "펀박스": "https://www.youtube.com/@펀Box",
    "앞북이": "https://www.youtube.com/@앞북이",
    "재밌쇼": "https://www.youtube.com/@humorshowshow",
    "갓성비": "https://www.youtube.com/@갓성비스토리",
}


# ------------------------------------------------------------------ 엔진 channels → 확정 판정 (2026-10-18 누락 재판정, 관제 097)
CONFIRMED_JSON = ROOT / "channel" / "스타일분석" / "현장썰" / "채널수집" / "같은결_채널.json"


def engine_candidates(engine: dict, confirmed: dict) -> list[dict]:
    """엔진 channels 중 '같은 결(same_kind) 이거나 갈래가 현장썰이거나 표본에 나레+원음이 있는' 채널 가운데
    확정 목록(channels)에도, 아님 목록(rejected)에도 아직 없는 것. 확정 목록을 엔진 결과에서 만들지 않아 누락이 났다 — 그 구멍을 막는 한 곳."""
    known = {c.get("channel_id") for c in confirmed.get("channels", [])} | {c.get("channel_id") for c in confirmed.get("rejected", [])}

    def hit(c):
        return bool(c.get("same_kind")) or c.get("style") == "현장썰" or any(
            x.get("ok") and x.get("original_audio") and x.get("korean_narration") for x in (c.get("samples") or []))
    return [c for c in engine.get("channels", []) if hit(c) and c.get("channel_id") not in known]


def pick_samples(videos: list[dict], k: int = 5) -> list[dict]:
    """조회 상위 3 + 중간 (k-3)편. 표본은 한 곳에서 고른다."""
    vs = sorted([v for v in videos if v.get("id") and v.get("views")], key=lambda v: -v["views"])
    if len(vs) <= k:
        return vs
    top = vs[:3]
    mid0 = len(vs) // 2 - (k - 3) // 2
    return top + vs[mid0:mid0 + (k - 3)]


def judge_channel_samples(rows: list[dict]) -> tuple[str, str]:
    """표본 판독 rows(sample_check 결과 + views) → (확정/후보/아님, 이유). 판정 문턱의 주인."""
    ok = [r for r in rows if r.get("ok")]
    if len(ok) < 2:
        return "후보", f"판독된 표본 {len(ok)}편뿐 — 판정 보류"
    four = [r for r in ok if r["korean_narration"] and r["original_audio"] and r["foreign_original"] and r["product"]]
    live = [r for r in ok if r["style"] == "현장썰"]
    prod = [r for r in ok if r["product"]]
    tag = f"4요건 {len(four)}/{len(ok)} · 현장썰 {len(live)}/{len(ok)} · 제품 {len(prod)}/{len(ok)}"
    if len(four) * 2 >= len(ok) and len(ok) >= 3:
        return "확정", tag
    if four:
        return "후보", tag
    if live and not prod:
        return "아님", tag + " — 현장썰이지만 제품 없음(제품 없는 바이럴)"
    if not live:
        return "아님", tag + " — 원음 섞인 현장썰 편이 없음(나레만/자막만)"
    return "아님", tag


def confirm_from_engine(engine_path=None, confirmed_path=None, k: int = 5, workers: int = 3, apply: bool = False) -> dict:
    """엔진 결과 channels → 확정 판정까지 바로 잇는다. 확정 목록에 없는 채널만 표본 k편(조회 상위+중간) 4요건 판독(sample_check, 무료 풀).
    apply=True 면 같은결_채널.json 의 channels(확정·후보)와 rejected(아님)에 이어 쓴다(기존 행 유지). 눈 확인은 사람 몫 — checked_by='제미나이만'으로 남긴다."""
    engine_path = Path(engine_path or ROOT / "channel/스타일분석/현장썰/채널수집/결과_엔진_1차.json")
    confirmed_path = Path(confirmed_path or CONFIRMED_JSON)
    engine = json.loads(engine_path.read_text(encoding="utf-8"))
    confirmed = json.loads(confirmed_path.read_text(encoding="utf-8"))
    todo = engine_candidates(engine, confirmed)

    def one(c):
        st = channel_stats(c["channel_id"])
        if not st:
            return {"engine": c, "verdict": "후보", "reason": "채널 실측 실패 — 판정 보류", "rows": []}
        rows = []
        for v in pick_samples(st["videos"], k):
            r = sample_check(v["id"])
            r.update(views=v["views"], title=v["title"])
            rows.append(r)
        verdict, reason = judge_channel_samples(rows)
        return {"engine": c, "stats": {x: st.get(x) for x in ("name", "handle", "channel_id", "url", "subs", "median_views", "max_views", "n", "per_week", "last_upload")},
                "rows": rows, "verdict": verdict, "reason": reason}
    with ThreadPoolExecutor(workers) as ex:
        out = list(ex.map(one, todo))
    if apply:
        _apply_confirm(confirmed, out, confirmed_path)
    return {"todo": len(todo), "results": out}


def _apply_confirm(confirmed: dict, out: list[dict], path: Path) -> None:
    today = datetime.now().date().isoformat()
    for o in out:
        st = o.get("stats") or {}
        e = o["engine"]
        ok = [r for r in o["rows"] if r.get("ok")]
        four = [r for r in ok if r["korean_narration"] and r["original_audio"] and r["foreign_original"] and r["product"]]
        live = [r for r in ok if r["style"] == "현장썰"]
        rep = [{"views": r["views"], "id": r["video_id"], "title": r["title"], "product": r.get("note"), "origin_audio_lang": r.get("original_lang"),
                "url": f"https://www.youtube.com/shorts/{r['video_id']}"} for r in sorted(four or ok, key=lambda r: -r["views"])[:3]]
        row = {"handle": st.get("handle") or e.get("handle"), "name": st.get("name") or e.get("name"), "channel_id": e["channel_id"],
               "url": e.get("url"), "verdict": o["verdict"], "checked_by": "제미나이만", "note": "누락 재판정 2026-10-18 · " + o["reason"],
               "subs": st.get("subs") or e.get("subs"), "median30": st.get("median_views") or e.get("median_views"), "max30": st.get("max_views") or e.get("max_views"),
               "n30": st.get("n"), "per_week": st.get("per_week"), "last_upload": st.get("last_upload"),
               "samples": len(ok), "four_ok": len(four), "style_ratio": {"현장썰(나레+원음)": f"{len(live)}/{len(ok)}"}, "rep": rep,
               "relabeled": "누락 재판정 2026-10-18"}
        if o["verdict"] == "아님":
            confirmed.setdefault("rejected", []).append(row)
        else:
            confirmed.setdefault("channels", []).append(row)
    confirmed["made"] = today
    note = f"누락 재판정 {today}: 엔진 결과 channels 중 확정 목록에 없는 것을 confirm_from_engine 으로 표본 5편(조회 상위 3+중간 2) 판독"
    if note not in confirmed.get("method", ""):          # 같은 날 두 번 --apply 해도 한 번만 적는다
        confirmed["method"] = confirmed.get("method", "") + " / " + note
    path.write_text(json.dumps(confirmed, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="channel/스타일분석/현장썰/채널수집/seeds.json")
    ap.add_argument("--out", default="channel/스타일분석/현장썰/채널수집/결과_엔진_1차")
    ap.add_argument("--methods", default="lens,keyword,related")
    ap.add_argument("--serpapi", type=int, default=0, help="새 SerpApi 호출 상한(유료). 0 = 캐시만")
    ap.add_argument("--lens-import", default="", help="다른 실행이 낸 렌즈 결과 json 을 캐시로")
    ap.add_argument("--kw-import", default="", help="키워드 에이전트 결과 json 들(쉼표)")
    ap.add_argument("--channels", type=int, default=260)
    ap.add_argument("--gemini", type=int, default=300)
    ap.add_argument("--audio", type=int, default=40)
    ap.add_argument("--ytsearch", type=int, default=400)
    ap.add_argument("--confirm-from-engine", action="store_true", help="엔진 channels → 확정 목록에 없는 채널 재판정")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    if a.confirm_from_engine:
        r = confirm_from_engine(apply=a.apply)
        for o in r["results"]:
            print(o["verdict"], o["engine"]["name"], o["reason"])
        return
    if a.lens_import:
        print("렌즈 캐시 들임", lens_import(a.lens_import))
    seeds = load_seeds(ROOT / a.seeds if not Path(a.seeds).is_absolute() else a.seeds)
    print("씨앗", len(seeds))
    res = find_channels(seeds, tuple(a.methods.split(",")),
                        {"serpapi": a.serpapi, "channels": a.channels, "gemini": a.gemini, "audio": a.audio, "ytsearch": a.ytsearch},
                        probe=TRUTH_PROBE,
                        extra_hits=keyword_import([ROOT / x if not Path(x).is_absolute() else x for x in a.kw_import.split(",") if x]) if a.kw_import else None)
    out = ROOT / a.out if not Path(a.out).is_absolute() else Path(a.out)
    write_report(res, out)
    print("저장", out.with_suffix(".json"), out.with_suffix(".md"))
    print(json.dumps(res["cost"], ensure_ascii=False))


if __name__ == "__main__":
    main()
