# -*- coding: utf-8 -*-
"""훅·썸네일 장면 찾기 — 소재와 엮인 '누구나 아는 장면'(드라마·예능·광고·뉴스)을 구글·네이버·유튜브로 찾고 공식 채널인지 가린다
(관제 097, 2026-10-24 사장님 "영상 안에 그런 장면이 없다면? / 검색을 통해서 찾을 수 없나 구글 네이버 / 그것까지 엔진에").

    PYTHONUTF8=1 py tools/calcopy/scene_search.py "<소재>" [--brand 빙그레] [--serp 4] [--yt 8] [--out 장면후보.json]

순서(주인 = tools/calcopy/hybrid/thumb_rule.FIND_ORDER):
  ① 구글·네이버 = **어떤 장면이 있는지** 단서(서버 SerpApi — 유료라 --serp 호출 수만큼, 결과는 캐시)
  ② 유튜브 = 그 장면의 **원본 영상**(yt-dlp 무료) — 단서 글의 유튜브 링크도 같이 본다
  ③ 공식 판정 = 유튜브 인증 채널(channel_is_verified) 또는 방송사·브랜드 이름 채널. 재편집·짜깁기 채널은 후보에서 뺀다
검색 결과 이미지(뉴스 사진·블로그 캡처)는 **단서로만** — 썸네일·화면에 그대로 쓰지 않는다(저작권·본편에 없는 장면·연예인 원본 규칙).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.engine.channel_find import SERVER_REPO, SSH_HOST, SSH_KEY, ytsearch  # noqa: E402

CACHE = Path("C:/숏템_칼카피/_cache/scene_search")
QUERY_FORMS = ["{t} 드라마 장면", "{t} 예능 장면", "{t} 광고 모델", "{t} 명장면", "{t} 짤", "{t} 나온 드라마", "{t} 화제 장면"]
OFFICIAL_NAMES = ["JTBC", "KBS", "MBC", "SBS", "tvN", "TVING", "티빙", "Mnet", "ENA", "채널A", "MBN", "TV CHOSUN", "TV조선", "Netflix", "넷플릭스",
                  "쿠팡플레이", "Disney", "디즈니", "웨이브", "wavve", "YTN", "연합뉴스", "뉴스", "OCN", "JTBC Drama", "Studio", "스튜디오", "EBS", "KBS Drama"]
RECUT = ["모음", "몰아보기", "결말", "리뷰", "요약", "해석", "짜깁기", "편집본", "reaction", "리액션"]

_REMOTE = r'''
import json,sys,requests
sys.path.insert(0,"%s")
from shopping_shorts import config
qs=json.loads(sys.argv[1]); keys=config.SERPAPI_KEYS; out=[]
for eng,q in qs:
    p={"engine":eng,"api_key":None}
    if eng=="google": p.update(q=q,hl="ko",gl="kr",num=10)
    else: p.update(query=q)
    res=None
    for k in keys:
        p["api_key"]=k
        try:
            r=requests.get("https://serpapi.com/search",params=p,timeout=40)
            if r.status_code==200: res=r.json(); break
        except Exception as e: pass
    rows=[]
    for key,v in (res or {}).items():
        if isinstance(v,list):
            for x in v:
                if isinstance(x,dict) and (x.get("link") or x.get("url")):
                    rows.append({"kind":key,"title":x.get("title") or "","link":x.get("link") or x.get("url"),"snippet":(x.get("snippet") or x.get("description") or "")[:200]})
    out.append({"engine":eng,"q":q,"ok":res is not None,"rows":rows[:30]})
print("@@JSON@@"+json.dumps(out,ensure_ascii=False))
''' % SERVER_REPO


def queries(topic: str, brand: str = "") -> list[str]:
    t = topic.strip()
    qs = [f.format(t=t) for f in QUERY_FORMS]
    if brand and brand not in t:
        qs += [f"{brand} {t} 광고", f"{brand} 광고 모델"]
    return qs


def _ck(*a) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / (hashlib.md5("|".join(a).encode("utf-8")).hexdigest() + ".json")


def web(qs: list[str], calls: int) -> list[dict]:
    """구글·네이버(서버 SerpApi). 캐시 먼저, 새 호출은 calls 개까지(구글·네이버 번갈아)."""
    pairs = [(e, q) for q in qs for e in ("google", "naver")]
    got, todo = [], []
    for e, q in pairs:
        p = _ck("serp", e, q)
        if p.exists():
            got.append(json.loads(p.read_text(encoding="utf-8")))
        elif len(todo) < max(0, calls):
            todo.append((e, q))
    if todo:
        cmd = ["ssh", "-o", "ConnectTimeout=15", "-i", SSH_KEY, SSH_HOST,
               f"cd {SERVER_REPO} && set -a && . <(sudo cat /etc/shopping-shorts.env) && set +a && python3 - '{json.dumps(todo, ensure_ascii=False)}'"]
        r = subprocess.run(cmd, input=_REMOTE.encode("utf-8"), capture_output=True, timeout=60 + 45 * len(todo))
        txt = r.stdout.decode("utf-8", "replace")
        if "@@JSON@@" not in txt:
            print("서버 검색 실패:", r.stderr.decode("utf-8", "replace")[-300:])
        else:
            for x in json.loads(txt.split("@@JSON@@", 1)[1]):
                if x.get("ok"):
                    _ck("serp", x["engine"], x["q"]).write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")
                got.append(x)
    return got


def _info(vid: str) -> dict:
    p = _ck("ytinfo", vid)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as y:
            d = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False)
        i = {"id": vid, "title": d.get("title"), "channel": d.get("channel"), "verified": bool(d.get("channel_is_verified")),
             "followers": d.get("channel_follower_count"), "views": d.get("view_count"), "duration": d.get("duration"),
             "upload_date": d.get("upload_date")}
    except Exception as e:  # noqa: BLE001
        i = {"id": vid, "err": str(e)[:150]}
    p.write_text(json.dumps(i, ensure_ascii=False), encoding="utf-8")
    return i


def _redo_q(title: str) -> str:
    """재편집 제목 '장면 한 줄｜프로그램｜방송사 날짜' → '프로그램 + 장면 앞 낱말 셋'(제목 그대로 찾으면 재편집본만 다시 나온다 — 10-24 실측)."""
    seg = [x.strip() for x in re.split(r"[|｜]", title or "") if x.strip()]
    main = re.findall(r"[가-힣A-Za-z0-9]+", seg[0] if seg else "")[:3]
    return " ".join(([seg[1]] if len(seg) > 1 else []) + main)


def _toks(t) -> set:
    return {w for w in re.findall(r"[가-힣A-Za-z0-9]{2,}", t or "") if not w.isdigit() or len(w) >= 6}


def official(i: dict, brand: str = "") -> tuple[bool, str]:
    ch = (i.get("channel") or "")
    title = (i.get("title") or "")
    if any(w in title for w in RECUT) and not i.get("verified"):
        return False, "재편집·모음 제목"
    if i.get("verified"):
        return True, "유튜브 인증 채널"
    hit = [n for n in OFFICIAL_NAMES + ([brand] if brand else []) if n and n.lower() in ch.lower()]
    if hit:
        return True, f"채널 이름에 {hit[0]}(인증 표시는 없음 — 채널 정보 화면으로 다시 확인)"
    return False, "인증·공식 이름 아님"


def run(topic: str, brand: str = "", serp: int = 4, yt: int = 8, top: int = 24) -> dict:
    qs = queries(topic, brand)
    W = web(qs, serp)
    vids: dict[str, dict] = {}
    for x in W:
        for r in x.get("rows") or []:
            m = re.search(r"(?:shorts/|v=|youtu\.be/)([A-Za-z0-9_-]{11})", r["link"])
            if m:
                vids.setdefault(m.group(1), {"from": f"{x['engine']}:{x['q']}"})
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(lambda q: ytsearch(q, yt), qs))
    for q, ents in zip(qs, res):
        for e in ents:
            if e.get("video_id"):
                vids.setdefault(e["video_id"], {"from": f"youtube:{q}"})
    ids = list(vids)[:top * 2]
    with ThreadPoolExecutor(6) as ex:
        infos = list(ex.map(_info, ids))
    out = []
    for i in infos:
        if i.get("err"):
            continue
        ok, why = official(i, brand)
        out.append({**i, "official": ok, "why": why, "from": vids[i["id"]]["from"], "url": f"https://www.youtube.com/watch?v={i['id']}"})
    # 단서 영상이 재편집 채널이면 그 제목으로 **공식 원본**을 다시 찾는다(10-24 실측: 구글 1위 '대행사' 단서 = DRAMA Voyage 재편집 →
    # 같은 장면 JTBC Drama 공식 jCwk-6GeYtU 는 유튜브 검색 11위에 묻혀 있었다)
    have = {v["id"] for v in out}
    redo = [v for v in out if not v["official"] and v["from"].startswith(("google", "naver"))][:6]
    with ThreadPoolExecutor(6) as ex:
        res2 = list(ex.map(lambda v: ytsearch(_redo_q(v["title"]), yt), redo))
    new = [(v, e["video_id"]) for v, ents in zip(redo, res2) for e in ents if e.get("video_id")]
    with ThreadPoolExecutor(6) as ex:
        infos2 = list(ex.map(_info, dict.fromkeys(i for _, i in new if i not in have)))
    by = {v["id"]: v for v in out} | {i["id"]: i for i in infos2 if not i.get("err")}
    for v in redo:                          # 같은 장면 = 제목 낱말이 3개 이상 겹치는 공식 영상 중 가장 많이 겹치는 하나
        best, bs = None, 2
        for vv, vid in new:
            i = by.get(vid)
            if vv is not v or not i or vid == v["id"]:
                continue
            sc = len(_toks(v.get("title")) & _toks(i.get("title")))
            if sc > bs and official(i, brand)[0]:
                best, bs = i, sc
        if not best:
            continue
        tag = f"{v['from'].split(':')[0]}→공식 원본({v['id']} {v.get('channel')} 대신, 제목 낱말 {bs}개 겹침)"
        if best["id"] in have:
            next(o for o in out if o["id"] == best["id"]).update(**{"from": tag, "same_as": v["id"]})
        else:
            ok, why = official(best, brand)
            have.add(best["id"])
            out.append({**best, "official": ok, "why": why, "from": tag, "same_as": v["id"], "url": f"https://www.youtube.com/watch?v={best['id']}"})
    words = [w for w in re.split(r"\s+", topic) if len(w) >= 2]
    for v in out:
        v["topic_hits"] = sum(w in (v.get("title") or "") for w in words)
    # 순서 = 공식 → 구글·네이버 단서에서 나온 영상(사람들이 '그 장면'으로 부르는 것) → 제목에 소재 낱말 → 조회수
    out.sort(key=lambda v: (not v["official"], not v["from"].startswith(("google", "naver")), -v["topic_hits"], -(v.get("views") or 0)))
    clues = [{"engine": x["engine"], "q": x["q"], "title": r["title"], "link": r["link"], "snippet": r["snippet"]}
             for x in W for r in (x.get("rows") or [])[:8]]
    return {"topic": topic, "brand": brand, "queries": qs, "clues": clues, "videos": out[:top],
            "_rule": "단서(clues)는 어떤 장면이 있는지 아는 데만. 화면·썸네일은 official=true 원본 영상에서 그 구간만 받아 본편에 넣고 쓴다."}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("topic"); ap.add_argument("--brand", default=""); ap.add_argument("--serp", type=int, default=4)
    ap.add_argument("--yt", type=int, default=8); ap.add_argument("--out")
    a = ap.parse_args()
    r = run(a.topic, a.brand, a.serp, a.yt)
    if a.out:
        Path(a.out).write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"단서 {len(r['clues'])}건 · 영상 {len(r['videos'])}개(공식 {sum(v['official'] for v in r['videos'])})")
    for v in r["videos"][:12]:
        print(("○" if v["official"] else "·"), v["id"], (v.get("channel") or "")[:18], "|", (v.get("title") or "")[:40], "|", v["why"], "|", v["from"][:30])
    for c in r["clues"][:10]:
        print("  단서", c["engine"], "|", c["title"][:50])


if __name__ == "__main__":
    main()
