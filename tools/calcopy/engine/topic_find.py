# -*- coding: utf-8 -*-
"""소재 찾기 엔진 — 프리셋(채널)을 주면 소재 후보를 모으고, 같은 소재 영상 벤치를 뜨고, 5기준 점수표를 만든다 (관제 097, 2026-10-16).

    PYTHONUTF8=1 py tools/calcopy/engine/topic_find.py --preset channel/sseolpulda/preset/A_흰바탕창/창아래_검정 \
        --source-kind 해외영상 --n 10 --out C:/숏템_칼카피/sseolpulda/소재찾기_1016
    PYTHONUTF8=1 py tools/calcopy/engine/topic_find.py --preset yummyknow --source-kind 제품비하인드 --keywords "코스트코,신라면" --out …

설계 §4-2 "소재 단계 = 같은 소재 영상 벤치":
  1) 통로 — 프리셋의 소재 출처 유형(manifest.source_kind, 없으면 --source-kind)에 따라
       해외영상/제품비하인드 = 유튜브 쇼츠 검색(조회순·짧은 영상·최근 N개월 필터) — 검색어 = 채널 top50 제목 낱말 n-gram
       커뮤니티            = community_mine(보배드림 베스트, robots 허용 곳만) 재사용
       뉴스                = 네이버 뉴스 검색 결과 페이지 파싱(안 되면 failed 로 남긴다)
       고객제품            = --keywords 로 받은 제품 그대로(검색 없음)
  2) 후보마다 같은 소재 영상 5~10편(조회순)의 제목·설명·댓글(좋아요 순 50) → 포인트(훅 각도·반전·숫자·반응·장면 종류)
     LLM 1회 → 벤치/<후보>.md (+ .json)
  3) 5기준 점수(아는·몰랐던·재미·이야기·얻는 것 + 보여줄 수 있나, 근거 문장 필수 — 없으면 그 점수는 버린다) +
     "이미 만든 소재 겹침"(채널 top50 제목·우리 완성편 topic 과 글자 2-gram 포함률) → 후보표.md · 후보.json, 상위 1~3 추천.
  ★고르는 건 사람/오푸스 자리 — 이 도구는 추천까지만 한다.

판단 주인: 겹침 = overlap() · 점수 합 = total() · 점수 근거 거르기 = _clean_scores(). 네트워크·LLM 은 주입(시험은 가짜).
LLM 은 무료 제미나이(gemini_free.ask — 키 장부)만, 한 번 실행에 --max-llm 회 상한. 유료 API 없음.
"""
from __future__ import annotations

import argparse
import html as _html
import json
import math
import re
import subprocess
import sys
import time
import urllib.parse as up
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

# 소재 출처 유형(설계 §4-2) — 이름 → 통로
SOURCE_KINDS = {"해외영상": "youtube", "제품비하인드": "youtube", "커뮤니티": "community", "뉴스": "news", "고객제품": "given"}
# 5기준 + 보여줄 수 있나 — (키, remake.plan_extra 가 읽는 한국어 이름)
CRITERIA = [("known", "아는 대상"), ("surprise", "몰랐던"), ("fun", "재미"), ("story", "이야기"), ("gain", "얻는 것"), ("showable", "보여줄 수 있나")]
WHY_MIN = 6            # 근거 문장 최소 글자 — 이보다 짧으면 근거 없음으로 점수를 버린다
OVERLAP_CUT = 0.35     # 글자 2-gram 포함률이 이 이상이면 "이미 만든 소재"(10-16 실측: ZdeZ 다른 말 0.38·하키 퍽 0.60 / 무관 소재 0~0.22)
OVERLAP_PENALTY = 30   # 겹침 점수(0~1) × 이 값을 합계에서 뺀다(겹침 1.0 = 6기준 합 60점 중 절반)
YT_SHORT = 180         # 쇼츠 길이 상한(초)


# ── LLM 창구(무료 제미나이) — 상한·장부 ─────────────────────────────────────
class LLM:
    """fn(prompt, tag) -> (dict|None, err). 기본 = gemini_free.ask(무료 키 장부). budget 회를 넘으면 'budget' 실패."""

    def __init__(self, fn=None, budget: int = 12):
        self.fn, self.budget, self.calls = fn, budget, []

    def __call__(self, prompt: str, tag: str):
        if len(self.calls) >= self.budget:
            self.calls.append({"tag": tag, "failed": "budget"})
            return None, "budget"
        fn = self.fn
        if fn is None:
            from tools.calcopy.engine import gemini_free
            from tools.calcopy.style_writer import CAP_MODELS   # 글쓰기 모델 순서는 style_writer 한 곳
            fn = lambda p, t: gemini_free.ask([], p, tag=t, models=CAP_MODELS)  # noqa: E731
        d, err = fn(prompt, tag)
        self.calls.append({"tag": tag, "ok": bool(d), "failed": err, "model": (d or {}).get("_model")})
        return d, err


# ── 프리셋 읽기(script_engine 과 공용) ──────────────────────────────────────
def load_preset(preset: str, tteutgi: str | None = None) -> dict:
    """'channel/<slug>/preset/<갈래>/<틀>' 폴더 또는 slug → {slug, chdir, preset_dir, manifest, tteutgi, frame, rules}."""
    p = Path(preset)
    if not p.is_absolute():
        p = ROOT / p
    man, pdir = {}, None
    if p.is_dir() and (p / "manifest.json").exists():
        pdir = p
        man = json.loads((p / "manifest.json").read_text(encoding="utf-8"))
        slug = man.get("slug") or p.relative_to(ROOT / "channel").parts[0]
    elif (ROOT / "channel" / preset).is_dir():
        slug = preset
    else:
        raise SystemExit(f"프리셋을 못 찾음: {preset} (preset 폴더에 manifest.json 이 있거나 channel/<slug> 여야 한다)")
    ch = ROOT / "channel" / slug
    tj = tteutgi
    if not tj:
        for s in man.get("sources") or []:
            if s.get("tteutgi") and Path(s["tteutgi"]).exists():
                tj = s["tteutgi"]; break
    if not tj:   # 프리셋 폴더가 없으면 조회 1위 편의 뜯기
        top = _read_json(ch / "원자료" / "top50.json") or []
        for v in top:
            c = ch / "뜯기" / v["id"] / "뜯기.json"
            if c.exists():
                tj = str(c); break
    rules = man.get("rules") if isinstance(man.get("rules"), str) and Path(man["rules"]).exists() else None   # manifest.rules 는 공식(dict)일 때가 있다
    if not rules:
        rs = sorted(ch.glob("*.rules.json"))
        rules = str(rs[0]) if rs else None
    frame = str(pdir / "frame.json") if pdir and (pdir / "frame.json").exists() else None
    return {"slug": slug, "chdir": ch, "preset_dir": pdir, "manifest": man, "tteutgi": tj, "frame": frame, "rules": rules}


def _read_json(p: Path):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ── 검색어 묶음: 채널 top50 제목 n-gram ─────────────────────────────────────
STOP = {"the", "and", "for", "with", "this", "that", "you", "your", "are", "was", "why", "what", "how", "its", "it's", "from", "have",
        "has", "not", "but", "all", "one", "just", "they", "their", "will", "can", "out", "about", "who", "when", "into", "make", "sure",
        "shorts", "short", "feat", "turn", "on", "of", "to", "in", "is", "a", "an", "my", "me", "so", "be",
        "이거", "진짜", "그냥", "이게", "하는", "하나", "있는", "없는", "해서", "에서", "으로", "그리고", "근데", "ㅋㅋ", "썰"}


# 제목이 유튜브 자동 번역 영어라(top50.json 10-16 실측) 꾸밈말이 1위를 먹는다 — 꾸밈·낚시 낱말은 뺀다
STOP |= {"after", "before", "even", "made", "insane", "crazy", "viral", "secret", "secrets", "truth", "real", "why", "ultimate", "shocker",
         "hack", "hacks", "hacked", "trade", "behind", "leaked", "exposed", "totally", "officially", "huge", "true", "identity", "product",
         "products", "company", "thing", "things", "people", "world", "only", "finally", "ended", "never", "really", "what's", "that's",
         "new", "life", "time", "years", "year", "still", "everyone", "nobody", "stop", "can't", "don't", "who", "were", "been", "got"}


def _tokens(title: str) -> list[str]:
    t = re.sub(r"#\w+", " ", title or "")
    return [w.lower() for w in re.findall(r"[가-힣]{2,}|[A-Za-z][A-Za-z']{2,}", t) if w.lower() not in STOP]


def _hashtags(title: str) -> list[str]:
    """#BoneConductionSpeaker → 'bone conduction speaker' — 해시태그는 제품·종류 이름이라 검색어로 가장 쓸 만하다."""
    out = []
    for h in re.findall(r"#(\w+)", title or ""):
        ph = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", h).lower().strip()
        if len(ph) >= 3 and ph not in STOP:
            out.append(ph)
    return out


def keyword_bundles(top: list[dict], k: int = 8) -> list[str]:
    """제목 낱말 1·2-gram + 해시태그 묶음에 조회수 로그 가중 → 위에서 k개(앞 것에 포함되는 것은 뺀다).
    2-gram ×1.5, 해시태그 ×2, 낱말 하나는 제목 2개 이상에 나올 때만(한 편짜리 꾸밈말 거르기)."""
    sc, df = Counter(), Counter()
    for v in top:
        w = math.log10(max(int(v.get("views") or 0), 10))
        tk = _tokens(v.get("title", ""))
        for g in set(tk):
            df[g] += 1
        grams = {(g, 1.0) for g in set(tk)} | {(f"{a} {b}", 1.5) for a, b in zip(tk, tk[1:])} | {(h, 2.0) for h in _hashtags(v.get("title", ""))}
        for g, m in grams:
            sc[g] += w * m
    for g in list(sc):
        if " " not in g and df[g] < 2 and g not in {h for v in top for h in _hashtags(v.get("title", ""))}:
            del sc[g]
    out = []
    for g, _ in sc.most_common():
        if any(g in o or o in g for o in out):
            continue
        out.append(g)
        if len(out) >= k:
            break
    return out


# ── 통로(네트워크) — 주입 가능 ─────────────────────────────────────────────
def _yt_sp(months: int | None) -> str:
    """조회순(sort=3) + 짧은 영상(duration=1) + 올린 날짜(이번 달=4 / 올해=5). 10-16 실측: CAMSBAgFGAE= · CAMSAhgB 둘 다 조회순 정렬."""
    if months is None or months > 12:
        return "CAMSAhgB"
    return "CAMSBAgEGAE%253D" if months <= 1 else "CAMSBAgFGAE%253D"


def yt_search(q: str, n: int = 10, months: int | None = None) -> list[dict]:
    """유튜브 검색 목록(flat) — id·제목·조회·길이. 쇼츠 길이 넘는 것은 뺀다."""
    url = "https://www.youtube.com/results?search_query=" + up.quote(q) + "&sp=" + _yt_sp(months)
    r = subprocess.run(["yt-dlp", "--encoding", "utf-8", "--flat-playlist", "-I", f"1:{n * 2}", "--print",
                        "%(id)s\t%(duration)s\t%(view_count)s\t%(title)s", url],
                       capture_output=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=120)
    out = []
    for l in r.stdout.splitlines():
        p = l.split("\t")
        if len(p) < 4 or p[1] in ("NA", "None"):
            continue
        if float(p[1]) > YT_SHORT:
            continue
        out.append({"id": p[0], "duration": float(p[1]), "views": int(p[2]) if p[2].isdigit() else None, "title": p[3],
                    "url": f"https://www.youtube.com/shorts/{p[0]}"})
    return out[:n]


def yt_detail(vid: str, n_comments: int = 50) -> dict:
    """제목·설명·조회·날짜 + 댓글(좋아요 순 n). 10-16 실측: 기본 클라이언트는 '로봇 확인'으로 막혀 android 로 받는다."""
    r = subprocess.run(["yt-dlp", "--encoding", "utf-8", "--skip-download", "--write-comments", "--extractor-args",
                        f"youtube:player_client=android;comment_sort=top;max_comments={n_comments},{n_comments},0,0", "-J",
                        f"https://www.youtube.com/watch?v={vid}"], capture_output=True, encoding="utf-8", stdin=subprocess.DEVNULL, timeout=180)
    try:
        d = json.loads(r.stdout or "null")
    except ValueError:
        d = None
    if not d:
        return {"id": vid, "failed": (r.stderr or "")[-200:].strip() or "빈 응답"}
    cm = sorted(d.get("comments") or [], key=lambda c: -(c.get("like_count") or 0))[:n_comments]
    return {"id": vid, "url": f"https://www.youtube.com/shorts/{vid}", "title": d.get("title"), "views": d.get("view_count"),
            "date": d.get("upload_date"), "description": (d.get("description") or "")[:600],
            "comments": [{"likes": c.get("like_count") or 0, "text": (c.get("text") or "")[:200], "id": c.get("id")} for c in cm]}


def news_search(q: str, n: int = 10) -> list[dict]:
    """네이버 뉴스 검색 결과 페이지 — 제목 링크(headline1 글자). 10-16 실측 10건 잡힘. 꼴이 바뀌면 빈 목록(부르는 쪽이 failed 로)."""
    url = "https://search.naver.com/search.naver?where=news&sort=0&query=" + up.quote(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15) as r:
        s = r.read().decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>\s*<span[^>]*headline1[^>]*>(.*?)</span>', s, re.S):
        out.append({"url": _html.unescape(m.group(1)), "title": _html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()})
    return out[:n]


def community_search(keywords: list[str], pages: int = 1) -> list[dict]:
    """community_mine(보배드림 베스트 제목 검색) 재사용 — 추천 순."""
    from tools.calcopy import community_mine as cm
    rows, seen = [], set()
    for k in keywords:
        for p in range(1, pages + 1):
            u = "https://www.bobaedream.co.kr/list?code=best&s_select=Subject&s_key=%s&page=%d" % (up.quote(k), p)
            for x in cm.parse_bobae(cm.fetch(u)):
                if x["url"] not in seen:
                    seen.add(x["url"]); x["keyword"] = k; rows.append(x)
            time.sleep(1.0)
    return sorted(rows, key=lambda x: -(x.get("recomm") or 0))


NET = {"yt_search": yt_search, "yt_detail": yt_detail, "news_search": news_search, "community_search": community_search}


# ── 겹침(이미 만든 소재) ────────────────────────────────────────────────────
def _norm(t: str) -> str:
    t = re.sub(r"#(\w+)", r" \1 ", t or "")
    return re.sub(r"[^가-힣a-z0-9]", "", t.lower())


def _g2(t: str) -> set:
    """글자 2-gram — 3-gram 은 같은 소재 다른 말('아무데나 붙이면 스피커 되는 원판')을 0.17 로 놓쳤다(2-gram 0.38)."""
    s = _norm(t)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def made_corpus(chdir: Path, extra: list[str] | None = None) -> list[dict]:
    """이미 만든 것: 채널 top50 제목 + 우리 완성편(channel/<slug>/칼카피_*·새소재_*/대본.json 의 topic·제목)."""
    out = [{"what": f"top50 {v['id']}", "text": v.get("title", "")} for v in (_read_json(chdir / "원자료" / "top50.json") or [])]
    for p in sorted(chdir.glob("*/대본.json")):
        d = _read_json(p) or {}
        t = " ".join(str(x) for x in (d.get("topic"), (d.get("titles") or {}).get("hook") if isinstance(d.get("titles"), dict) else d.get("title")) if x)
        if t:
            out.append({"what": f"우리 {p.parent.name}", "text": t})
    out += [{"what": "추가", "text": t} for t in extra or []]
    return out


def overlap(topic: str, corpus: list[dict]) -> dict:
    """후보 글자 2-gram 이 한 문서에 들어 있는 비율의 최댓값(문서마다 따로 — 긴 받아쓰기를 합치면 흔한 조각이 다 걸린다)."""
    a = _g2(topic)
    best = {"score": 0.0, "with": None}
    if not a:
        return best
    for d in corpus:
        b = _g2(d["text"])
        s = len(a & b) / len(a)
        if s > best["score"]:
            best = {"score": round(s, 3), "with": d["what"] + " · " + d["text"][:60]}
    return best


# ── 점수 ───────────────────────────────────────────────────────────────────
SCORE_PROMPT = """너는 한국 쇼츠 채널 '{slug}'의 소재 담당이다. 아래 소재 후보마다 점수(0~10)와 **근거 문장**을 매겨라.
기준(사장님 2026-10-15·16): 사람들이 **아는 대상**이면서 **몰랐던** **재밌는** 소재 + 이야기가 되고 얻는 게 있고 화면에 보여줄 수 있어야 한다.
  known     그 제품·브랜드·종류를 보는 사람이 이미 알 정도(다 아는 것 9~10, 처음 보는 가젯 2~3)
  surprise  "아 그래?" 정도 — 아는 것에 대해 몰랐던 사실일수록 높다. 기능 설명은 2 이하
  fun       남한테 말해 주고 싶을 만큼 재밌나(웃김·황당·소름·반전). 건조한 정보는 3 이하
  story     주인공·갈등·마지막 한 방이 있나
  gain      시청자가 얻는 것(쓸모·대리만족·승리감·말해 주고 싶음)
  showable  핵심 장면을 실제 영상·증거 캡처로 화면에 띄울 수 있나(벤치 영상이 그 장면을 보여 주면 높다)
★근거(why)는 후보 글·벤치 포인트에 있는 말로 한 문장. 근거를 못 대면 그 점수는 null 로 둬라(지어내지 마라).
출력 JSON만: {{"scores":[{{"id":"c1","known":{{"score":8,"why":"…"}},"surprise":{{…}},"fun":{{…}},"story":{{…}},"gain":{{…}},"showable":{{…}},"angle":"이 소재로 썰을 푼다면 각도 한 줄"}}]}}

후보:
{cands}"""

BENCH_PROMPT = """아래는 같은 소재('{topic}')로 이미 만들어진 쇼츠 {n}편의 제목·설명·좋아요 많은 댓글이다.
대본에 쓸 **포인트**를 뽑아라(문장을 베끼지 말고 무엇이 먹혔는지를 적는다):
  hook     훅 각도(첫 줄이 무엇으로 끌었나)
  twist    반전·몰랐던 사실
  number   영상·설명에 나온 숫자(그대로, 어느 영상인지)
  reaction 댓글 반응 지점(사람들이 어디서 웃고 놀라고 싸웠나)
  scene    많이 쓴 장면 종류(시연·비교·사람 반응·캡처 등)
항목마다 근거 영상 id(v_id) 또는 댓글을 적어라. 위 자료에 없는 것은 만들지 마라.
출력 JSON만: {{"points":[{{"kind":"hook|twist|number|reaction|scene","text":"한 줄","from":"영상 id"}}], "best_angle":"가장 터진 각도 한 줄"}}

자료:
{dump}"""


def _clean_scores(row: dict) -> dict:
    """근거 문장이 없거나 짧은 점수는 버린다(None) — '근거 없는 점수'를 합계에 넣지 않는다."""
    out, flags = {}, []
    for k, _ in CRITERIA:
        v = row.get(k)
        if isinstance(v, dict) and isinstance(v.get("score"), (int, float)) and len((v.get("why") or "").strip()) >= WHY_MIN:
            out[k] = {"score": max(0, min(10, v["score"])), "why": v["why"].strip()}
        else:
            out[k] = {"score": None, "why": ""}
            flags.append(f"{k} 근거 없음")
    return {"scores": out, "flags": flags}


def total(scores: dict, ov: dict) -> float:
    """6기준 합(근거 없는 점수 = 0) − 겹침 벌점(OVERLAP_CUT 이상일 때 겹침×OVERLAP_PENALTY)."""
    s = sum((scores[k]["score"] or 0) for k, _ in CRITERIA)
    if ov.get("score", 0) >= OVERLAP_CUT:
        s -= ov["score"] * OVERLAP_PENALTY
    return round(s, 1)


# ── 후보 모으기 ────────────────────────────────────────────────────────────
def _clean_title(t: str) -> str:
    t = re.sub(r"#\S+", " ", t or "")
    t = re.sub(r"[|\[\]【】❝❞\"'“”…()]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def gather(kind: str, keywords: list[str], n: int, months: int | None, own_ids: set, net: dict, log=print) -> tuple[list[dict], list[dict]]:
    """통로별 후보 목록 → [{id, topic, query, source}], 실패 목록."""
    route = SOURCE_KINDS[kind]
    cands, failed, seen = [], [], set()
    if route == "given":
        return [{"id": f"c{i + 1}", "topic": k, "query": k, "source": {"kind": kind}} for i, k in enumerate(keywords[:n])], failed
    if route == "youtube":
        pool = []
        for q in keywords:
            try:
                got = net["yt_search"](q, n, months)
            except Exception as e:  # noqa: BLE001 — 검색어 하나 실패는 failed 로 남기고 다음으로
                failed.append({"where": f"yt_search {q}", "why": f"{type(e).__name__}: {str(e)[:120]}"}); continue
            if not got:
                failed.append({"where": f"yt_search {q}", "why": "결과 0"})
            for v in got:
                if v["id"] in own_ids or v["id"] in seen:
                    continue
                seen.add(v["id"]); pool.append({**v, "query": q})
        pool.sort(key=lambda v: -(v.get("views") or 0))
        for v in pool:
            t = _clean_title(v["title"])
            if any(overlap(t, [{"what": "", "text": c["topic"]}])["score"] >= 0.6 for c in cands):
                continue   # 같은 소재 다른 영상은 한 후보로
            cands.append({"id": f"c{len(cands) + 1}", "topic": t, "query": bench_query(v["query"], t), "key": v["query"], "source": {"kind": kind, **v}})
            if len(cands) >= n:
                break
    elif route == "community":
        try:
            rows = net["community_search"](keywords)
        except Exception as e:  # noqa: BLE001
            rows = []; failed.append({"where": "community", "why": f"{type(e).__name__}: {str(e)[:120]}"})
        for x in rows[:n]:
            cands.append({"id": f"c{len(cands) + 1}", "topic": x["title"], "query": x["title"][:30], "source": {"kind": kind, **x}})
    elif route == "news":
        for q in keywords:
            try:
                rows = net["news_search"](q, n)
            except Exception as e:  # noqa: BLE001
                rows = []; failed.append({"where": f"news {q}", "why": f"{type(e).__name__}: {str(e)[:120]}"})
            if not rows:
                failed.append({"where": f"news {q}", "why": "결과 0(페이지 꼴 변경?)"})
            for x in rows:
                if x["url"] in seen:
                    continue
                seen.add(x["url"])
                cands.append({"id": f"c{len(cands) + 1}", "topic": x["title"], "query": " ".join(_clean_title(x["title"]).split()[:5]),
                              "source": {"kind": kind, **x}})
        cands = cands[:n]
    log(f"[후보] {kind} → {len(cands)}개 · 실패 {len(failed)}")
    return cands, failed


def bench_query(q: str, title: str, k: int = 2) -> str:
    """벤치 검색어 = 후보를 찾은 검색어 + 제목에서 검색어에 없는 낱말 k개.
    10-16 실측: 제목 앞 6낱말('I Can t Sleep Without Sound')로 찾으니 조회순 1·2위가 무관한 ASMR·pov 영상이었다."""
    have = set(q.lower().split())
    extra = [w for w in _tokens(title) if w not in have][:k]
    return " ".join([q] + extra).strip()


def _relevant(d: dict, query: str) -> bool:
    """벤치 영상이 소재와 관계있나 — 검색어 낱말(3글자↑, 꾸밈말 제외) 하나라도 제목·설명에 있어야 한다."""
    words = [w for w in _tokens(query) if len(w) >= 3 or re.match(r"[가-힣]", w)] or query.lower().split()   # 한글은 두 글자('라면')도 뜻 낱말
    hay = ((d.get("title") or "") + " " + (d.get("description") or "")).lower()
    return any(w in hay for w in words)


def bench(c: dict, out: Path, net: dict, llm: LLM, n_videos: int = 6, n_comments: int = 50, delay: float = 1.0) -> dict:
    """같은 소재 영상 n편(조회순) — 제목·설명·댓글 → 포인트(LLM 1회) → 벤치/<id>.md·.json."""
    vids, failed = [], []
    try:
        lst = net["yt_search"](c["query"], n_videos, None)
    except Exception as e:  # noqa: BLE001
        lst = []; failed.append(f"검색 {type(e).__name__}: {str(e)[:100]}")
    for v in lst[:n_videos]:
        d = net["yt_detail"](v["id"], n_comments)
        if d.get("failed"):
            failed.append(f"{v['id']}: {d['failed'][:100]}")
            continue
        if not _relevant(d, c.get("key") or c["query"]):   # 관계 판정은 후보를 찾은 검색어(제품·종류) 기준 — 제목 낱말('sleep')은 무관 영상도 통과시킨다
            failed.append(f"{v['id']}: 무관 영상 제외({(d.get('title') or '')[:40]})")
            continue
        vids.append(d)
        time.sleep(delay)
    dump = "\n\n".join(f"[v_{d['id']}] 조회 {d.get('views')} · {d.get('title')}\n설명: {(d.get('description') or '')[:300]}\n댓글: " +
                       " / ".join(f"({x['likes']}) {x['text'][:80]}" for x in d.get("comments", [])[:15]) for d in vids)
    points, best, err = [], "", None
    if vids:
        r, err = llm(BENCH_PROMPT.format(topic=c["topic"], n=len(vids), dump=dump[:12000]), f"bench_{c['id']}")
        if r:
            known = {f"v_{d['id']}" for d in vids} | {d["id"] for d in vids}
            for p in r.get("points") or r.get("items") or []:
                if isinstance(p, dict) and (p.get("text") or "").strip():
                    p["grounded"] = any(k in str(p.get("from") or "") for k in known) or p.get("kind") == "reaction"
                    points.append(p)
            best = r.get("best_angle") or ""
    else:
        err = "벤치 영상 0편"
    for i, p in enumerate(points, 1):
        p["id"] = f"b{i}"
    res = {"candidate": c["id"], "topic": c["topic"], "query": c["query"], "videos": vids, "points": points, "best_angle": best,
           "failed": failed + ([f"포인트 LLM: {err}"] if err else [])}
    bd = out / "벤치"
    bd.mkdir(parents=True, exist_ok=True)
    (bd / f"{c['id']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# 벤치 {c['id']} — {c['topic']}", "", f"- 검색어: `{c['query']}` · 영상 {len(vids)}편", ""]
    if res["failed"]:
        md += [f"- ⚠ 실패: {x}" for x in res["failed"]] + [""]
    md += ["## 포인트", ""] + [f"- [{p['id']}] ({p.get('kind')}) {p['text']} — {p.get('from', '')}" + ("" if p["grounded"] else " ⚠근거 영상 불명") for p in points]
    if best:
        md += ["", f"- 가장 터진 각도: {best}"]
    md += ["", "## 영상", "", "| id | 조회 | 날짜 | 제목 | 댓글 상위 |", "|---|---|---|---|---|"]
    for d in vids:
        top = " / ".join(f"({x['likes']}) {x['text'][:40]}" for x in d.get("comments", [])[:3]).replace("|", "¦").replace("\n", " ")
        md.append(f"| [{d['id']}]({d['url']}) | {d.get('views')} | {d.get('date')} | {(d.get('title') or '').replace('|', '¦')} | {top} |")
    (bd / f"{c['id']}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return res


def score(cands: list[dict], benches: dict, slug: str, llm: LLM) -> tuple[dict, str | None]:
    lines = []
    for c in cands:
        b = benches.get(c["id"]) or {}
        pts = " / ".join(f"({p.get('kind')}) {p['text']}" for p in (b.get("points") or [])[:10])
        lines.append(f"{c['id']}. {c['topic']}\n   벤치 포인트: {pts or '(없음)'}")
    r, err = llm(SCORE_PROMPT.format(slug=slug, cands="\n".join(lines)), "score")
    rows = {}
    for row in (r or {}).get("scores") or (r or {}).get("items") or []:
        if isinstance(row, dict) and row.get("id"):
            rows[row["id"]] = row
    return rows, (None if r else err)


def run(preset: str, out: Path, n: int = 10, source_kind: str | None = None, keywords: list[str] | None = None, months: int | None = 6,
        bench_n: int = 6, made_extra: list[str] | None = None, net: dict | None = None, llm: LLM | None = None, log=print) -> dict:
    net = {**NET, **(net or {})}
    llm = llm or LLM()
    P = load_preset(preset)
    kind = source_kind or P["manifest"].get("source_kind")
    if kind not in SOURCE_KINDS:
        raise SystemExit(f"소재 출처 유형이 없다/모름: {kind!r} — manifest.source_kind 또는 --source-kind {list(SOURCE_KINDS)}")
    top = _read_json(P["chdir"] / "원자료" / "top50.json") or []
    kws = keywords or keyword_bundles(top)
    log(f"[검색어] {kws}")
    out.mkdir(parents=True, exist_ok=True)
    cands, failed = gather(kind, kws, n, months, {v["id"] for v in top}, net, log)
    corpus = made_corpus(P["chdir"], made_extra)
    benches = {}
    for c in cands:
        benches[c["id"]] = bench(c, out, net, llm, bench_n)
        log(f"[벤치] {c['id']} {c['topic'][:40]} — 영상 {len(benches[c['id']]['videos'])} · 포인트 {len(benches[c['id']]['points'])}")
    rows, err = score(cands, benches, P["slug"], llm) if cands else ({}, "후보 0")
    if err:
        failed.append({"where": "score", "why": err})
    for c in cands:
        cs = _clean_scores(rows.get(c["id"]) or {})
        c["scores"], c["flags"] = cs["scores"], cs["flags"] + ([] if c["id"] in rows else ["점수 없음(LLM 실패)"])
        c["angle"] = (rows.get(c["id"]) or {}).get("angle") or benches[c["id"]].get("best_angle") or ""
        c["overlap"] = overlap(c["topic"], corpus)
        if c["overlap"]["score"] >= OVERLAP_CUT:
            c["flags"].append(f"이미 만든 소재와 겹침 {c['overlap']['score']} ({c['overlap']['with']})")
        c["total"] = total(c["scores"], c["overlap"])
        c["bench"] = str(out / "벤치" / f"{c['id']}.md")
        c["bench_points"] = benches[c["id"]]["points"]
    ranked = sorted(cands, key=lambda c: -c["total"])
    for i, c in enumerate(ranked, 1):
        c["rank"] = i
    rec = [c["id"] for c in ranked if not any("점수 없음" in f for f in c["flags"]) and c["overlap"]["score"] < OVERLAP_CUT][:3]
    res = {"engine": "topic_find v1", "preset": preset, "slug": P["slug"], "source_kind": kind, "keywords": kws, "months": months,
           "made_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "candidates": ranked, "recommend": rec, "failed": failed, "llm_calls": llm.calls,
           "note": "고르는 건 사람/오푸스 자리 — recommend 는 점수 순 추천일 뿐"}
    (out / "후보.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    write_table(res, out / "후보표.md")
    log(f"[끝] 후보 {len(ranked)} · 추천 {rec} · 실패 {len(failed)} → {out / '후보표.md'}")
    return res


def write_table(res: dict, dst: Path):
    names = [n for _, n in CRITERIA]
    md = [f"# 소재 후보표 — {res['slug']} ({res['source_kind']})", "",
          f"- 검색어: {', '.join(res['keywords'])} · 최근 {res['months']}개월 · 만든 시각 {res['made_at']}",
          f"- 추천(점수 순, 겹침·점수없음 제외): **{', '.join(res['recommend']) or '없음'}** — 고르는 건 사람/오푸스",
          f"- 합계 = 6기준 합(근거 없는 점수 0) − 겹침 {OVERLAP_CUT} 이상이면 겹침×{OVERLAP_PENALTY}", ""]
    if res["failed"]:
        md += [f"- ⚠ 실패: {f['where']} — {f['why']}" for f in res["failed"]] + [""]
    md += ["| 순위 | id | 소재 | " + " | ".join(names) + " | 겹침 | 합계 | 벤치 |", "|---|---|---|" + "---|" * len(names) + "---|---|---|"]
    for c in res["candidates"]:
        sc = " | ".join("-" if c["scores"][k]["score"] is None else str(c["scores"][k]["score"]) for k, _ in CRITERIA)
        md.append(f"| {c['rank']} | {c['id']} | {c['topic'][:40].replace('|', '¦')} | {sc} | {c['overlap']['score']} | {c['total']} | [벤치]({Path(c['bench']).name and '벤치/' + Path(c['bench']).name}) |")
    md += ["", "## 근거", ""]
    for c in res["candidates"]:
        md += [f"### {c['rank']}. {c['id']} {c['topic']}", f"- 출처: {c['source'].get('url', '')} · 각도: {c.get('angle') or '-'}"]
        md += [f"- {n}: {c['scores'][k]['score']} — {c['scores'][k]['why'] or '(근거 없음)'}" for k, n in CRITERIA]
        md += [f"- ⚠ {f}" for f in c["flags"]] + [""]
    dst.write_text("\n".join(md) + "\n", encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="소재 찾기 엔진")
    ap.add_argument("--preset", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--out", required=True)
    ap.add_argument("--source-kind", choices=list(SOURCE_KINDS))
    ap.add_argument("--keywords", default="", help="쉼표 구분(없으면 top50 제목 n-gram)")
    ap.add_argument("--months", type=int, default=6, help="유튜브 올린 날짜 필터(≤1 이번 달, ≤12 올해, 0=없음)")
    ap.add_argument("--bench-n", type=int, default=6)
    ap.add_argument("--made", default="", help="이미 만든 소재 추가(| 구분)")
    ap.add_argument("--max-llm", type=int, default=12, help="무료 제미나이 호출 상한(한 번 실행)")
    a = ap.parse_args(argv)
    res = run(a.preset, Path(a.out), a.n, a.source_kind, [k.strip() for k in a.keywords.split(",") if k.strip()] or None,
              a.months or None, a.bench_n, [x for x in a.made.split("|") if x], llm=LLM(budget=a.max_llm))
    return 0 if res["candidates"] else 1


if __name__ == "__main__":
    sys.exit(main())
