# -*- coding: utf-8 -*-
"""소재 찾기 엔진 — 프리셋(채널)을 주면 소재 후보를 모으고, 같은 소재 영상 벤치를 뜨고, 5기준 점수표를 만든다 (관제 097, 2026-10-16).

    PYTHONUTF8=1 py tools/calcopy/engine/topic_find.py --preset channel/sseolpulda/preset/A_흰바탕창/창아래_검정 \
        --source-kind 해외영상 --n 10 --out C:/숏템_칼카피/sseolpulda/소재찾기_1016
    PYTHONUTF8=1 py tools/calcopy/engine/topic_find.py --preset yummyknow --source-kind 제품비하인드 --keywords "코스트코,신라면" --out …

설계 §4-2 "소재 단계 = 같은 소재 영상 벤치":
  0) 정확하게, 무작위 금지(사장님 10-16): 검색어 = 출처 유형 + 구체 명사(≤6, 후보표에 '왜 이 검색어인가' 한 줄씩) ·
     검색어당 ≤20편 · 전체 메타 ≤100편 · 요청 간격 ≥1초 · 벤치 댓글은 후보 상위 3개만 — Limits. 넘으면 멈추고 후보.json stopped 에 이유.
     해시태그 피드·'조회순 전체' 긁기는 하지 않는다.
  1) 통로 — 프리셋의 소재 출처 유형(manifest.source_kind, 없으면 --source-kind)에 따라
       해외영상/제품비하인드 = 유튜브 쇼츠 검색(조회순·짧은 영상·최근 N개월 필터) — 검색어 = 출처 유형 틀 + 구체 명사(--keywords, 없으면 top50 해시태그·고유명사)
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
YT_SHORT = 60          # 쇼츠 길이 상한(초) — 조율자 10-16 "쇼츠 길이 ≤60초"
DATE_PROBE = 20       # 날짜 판정은 조회 상위 이만큼만(편마다 요청 1번)


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
    rp = man.get("rules_path")   # preset_save 가 저장(10-16) — 저장소 기준 상대 경로
    rules = str(ROOT / rp) if rp and (ROOT / rp).exists() else None
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


# top50 n-gram 에서 나온 잡음(10-16 실측 'household'·'painting'·'seed'·'felt'·'causing' — 구체 명사가 아니다)
NOISE = {"household", "painting", "seed", "felt", "causing", "surprisingly", "delicious", "trend", "brand", "cheese", "chicken", "budget",
         "double", "living", "room", "space", "must", "have", "camping", "hand", "hands", "home", "homehacks", "relatable", "asmr",
         "dessert", "menu", "snack", "korean", "korea's", "mr", "ms", "update", "신상", "신메뉴", "viral"}

# 소재 출처 유형 + 구체 명사 = 검색어(사장님 10-16 "천천히 타겟 서칭, 무작위로 받지 말고"). 해시태그 피드 전체 긁기는 하지 않는다.
QUERY_TEMPLATES = {"해외영상": "{n}", "제품비하인드": "{n} {angle}", "커뮤니티": "{n}", "뉴스": "{n}", "고객제품": "{n}"}
# 제품비하인드 각도 낱말 — 채널 rules.json 의 topic_angles 가 주인. 없을 때 기본(조율자 10-16: '{n} 신상'은 브랜드 공식 홍보를 물어왔다 —
# yummyknow top50 제목 'felt misunderstood·flustered·trade secrets·mistake·wronged'의 결)
DEFAULT_ANGLES = ("억울", "영업비밀", "실수", "숨은 이유", "논란")


def target_queries(kind: str, nouns: list, max_queries: int, angles: tuple = DEFAULT_ANGLES) -> list[dict]:
    """검색어 = 출처 유형 틀 + 구체 명사 → [{q, why}]. why = 왜 이 검색어인가(후보표에 한 줄씩 — 무작위가 아님을 보인다).
    nouns = 글(사람 지정 --keywords) 또는 {noun, why}(db_candidates). 두 낱말 이상 한글 지정어('편의점 신메뉴')는 그대로."""
    tpl = QUERY_TEMPLATES[kind]
    out, seen = [], set()
    for x in nouns:
        n, why = (x["noun"], x["why"]) if isinstance(x, dict) else (x.strip(), "사람 지정(--keywords)")
        ang = angles[len(out) % len(angles)] if angles else ""
        q = n if (" " in n and kind != "해외영상" and not n.isascii()) else tpl.format(n=n, angle=ang).strip()
        if q in seen:
            continue
        seen.add(q)
        out.append({"q": q, "why": f"출처 유형 '{kind}' 틀 '{tpl}'" + (f"(각도 '{ang}')" if "{angle}" in tpl else "") + f" + {why}"})
    return out[:max_queries]


class LimitHit(Exception):
    pass


class Limits:
    """한 실행의 네트워크 상한(사장님 10-16 정정 "느리게가 아니라 정확하게"): 검색어 ≤6(출처 유형+구체 명사만) · 검색어당 ≤20편 ·
    전체 메타 조회 ≤100편 · 요청 간격 ≥1초(봇 확인 피할 만큼만, 일부러 늦추지 않는다) · 벤치 댓글은 후보 상위 3개만.
    넘기면 LimitHit — run 이 멈추고 이유를 후보.json stopped 에 남긴다."""
    MIN_RATE = 1.0

    def __init__(self, max_queries: int = 6, per_query: int = 20, max_meta: int = 100, rate: float = 1.0, bench_top: int = 3, sleep=time.sleep):
        if rate < self.MIN_RATE:
            raise SystemExit(f"요청 간격 {rate}초 < {self.MIN_RATE}초 — 봇 확인 위험이라 거절")
        if max_queries > 6 or per_query > 20 or max_meta > 100 or bench_top > 3:
            raise SystemExit("상한은 검색어 ≤6 · 검색어당 ≤20 · 메타 ≤100 · 벤치 상위 ≤3 (사장님 10-16)")
        self.max_queries, self.per_query, self.max_meta, self.rate, self.bench_top = max_queries, per_query, max_meta, rate, bench_top
        self.meta, self.requests, self._last, self._sleep, self.stopped = 0, 0, 0.0, sleep, None

    def take(self, n: int, what: str):
        """메타 n편을 쓰기 전에 부른다 — 넘으면 멈춤. 통과하면 간격을 지켜 기다린다."""
        if self.stopped:   # 한 번 멈추면 그 실행의 네트워크는 끝(남은 상한으로 다른 단계를 이어 가지 않는다)
            raise LimitHit(self.stopped)
        if self.meta + n > self.max_meta:
            self.stopped = f"메타 조회 상한 {self.max_meta}편 — {what} {n}편을 더하면 {self.meta + n}편이라 멈춤"
            raise LimitHit(self.stopped)
        gap = time.time() - self._last
        if self._last and gap < self.rate:
            self._sleep(self.rate - gap)
        self._last = time.time()
        self.meta += n
        self.requests += 1

    def summary(self) -> dict:
        return {"meta": self.meta, "requests": self.requests, "max_meta": self.max_meta, "max_queries": self.max_queries,
                "per_query": self.per_query, "rate": self.rate, "bench_top": self.bench_top, "stopped": self.stopped}


# ── 통로(네트워크) — 주입 가능 ─────────────────────────────────────────────
def _yt_sp(months: int | None) -> str:
    """짧은 영상(duration=1) + 올린 날짜(이번 달=4 / 올해=5) — 정렬은 넣지 않는다(로컬에서 조회순).
    10-16 실측: 조회순 정렬(CAMS…) 필터는 오후에 5개 중 4개 120초 멈춤·1개 0건 / 정렬 뺀 EgQIBRgB(올해+짧은)는 5편씩 나옴."""
    if months is None or months > 12:
        return "EgIYAQ%253D%253D"
    return "EgQIBBgB" if months <= 1 else "EgQIBRgB"


def _flat(cmd: list[str], timeout: int) -> tuple[list[dict], str | None]:
    try:
        r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=timeout)
    except subprocess.TimeoutExpired:
        return [], f"시간 초과 {timeout}초"
    out = []
    for l in r.stdout.splitlines():
        p = l.split("	")
        if len(p) < 4 or p[1] in ("NA", "None", ""):
            continue
        out.append({"id": p[0], "duration": float(p[1]), "views": int(p[2]) if p[2].isdigit() else None, "title": p[3],
                    "channel": p[4] if len(p) > 4 and p[4] not in ("NA", "None") else None,
                    "url": f"https://www.youtube.com/shorts/{p[0]}"})
    return out, (None if out else f"0건 rc={r.returncode} {(r.stderr or '')[-80:].strip()}")


def yt_search(q: str, n: int = 10, months: int | None = None) -> list[dict]:
    """유튜브 쇼츠 후보 목록(flat: id·제목·조회·길이). 정렬·날짜 판정은 부르는 쪽(gather)이 로컬에서 한다.
    ① 검색 페이지 + sp(짧은·올린 날짜) 필터, 30초 ② 실패·0건이면 ytsearch{2n, ≤40}(관련도 순) 폴백 — 폴백 이유는 항목 'fallback' 에.
    쇼츠 길이 YT_SHORT(60초) 넘는 것은 뺀다."""
    fmt = "%(id)s	%(duration)s	%(view_count)s	%(title)s	%(channel)s"
    url = "https://www.youtube.com/results?search_query=" + up.quote(q) + "&sp=" + _yt_sp(months)
    sp_cmd = ["yt-dlp", "--encoding", "utf-8", "--socket-timeout", "15", "--flat-playlist", "-I", f"1:{n}", "--print", fmt, url]
    items, why = _flat(sp_cmd, 30)
    if not items:   # 10-16 실측: 같은 sp 검색이 한 번 멈췄다가 다음엔 바로 나온다 — 한 번만 다시
        time.sleep(3)
        items, why = _flat(sp_cmd, 30)
    via, fb = "sp", None
    if not items:
        fb = f"sp 필터 {why} → ytsearch 폴백"
        items, why2 = _flat(["yt-dlp", "--encoding", "utf-8", "--socket-timeout", "15", "--flat-playlist", "--print", fmt,
                             f"ytsearch{min(40, max(2 * n, 20))}:{q}"], 60)
        via = "ytsearch"
        if why2:
            fb += f" ({why2})"
    out = [{**v, "via": via, "fallback": fb} for v in items if v["duration"] <= YT_SHORT]
    if not out and fb:
        out = [{"id": None, "fallback": fb + f" · {YT_SHORT}초 이하 0편"}]   # 이유만 전달(gather 가 failed 로)
    return out


def yt_upload_date(vid: str) -> str | None:
    """올린 날짜 YYYYMMDD — flat 목록엔 없다. android 클라이언트(기본은 로봇 확인에 막힘, 10-16 실측)."""
    try:
        r = subprocess.run(["yt-dlp", "--socket-timeout", "15", "--skip-download", "--extractor-args", "youtube:player_client=android",
                            "--print", "%(upload_date)s", f"https://www.youtube.com/watch?v={vid}"],
                           capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=40)
    except subprocess.TimeoutExpired:
        return None
    d = (r.stdout or "").strip().splitlines()
    return d[-1] if d and d[-1].isdigit() and len(d[-1]) == 8 else None


def yt_detail(vid: str, n_comments: int = 50) -> dict:
    """제목·설명·조회·날짜 + 댓글(좋아요 순 n). 10-16 실측: 기본 클라이언트는 '로봇 확인'으로 막혀 android 로 받는다."""
    try:
        r = subprocess.run(["yt-dlp", "--encoding", "utf-8", "--socket-timeout", "15", "--skip-download", "--write-comments", "--extractor-args",
                            f"youtube:player_client=android;comment_sort=top;max_comments={n_comments},{n_comments},0,0", "-J",
                            f"https://www.youtube.com/watch?v={vid}"], capture_output=True, encoding="utf-8", errors="replace",
                           stdin=subprocess.DEVNULL, timeout=150)
    except subprocess.TimeoutExpired:   # 10-16 실측: 한 편이 180초 멈춰 실행 전체가 죽었다 → 그 편만 실패로
        return {"id": vid, "failed": "시간 초과(150초)"}
    try:
        d = json.loads(r.stdout or "null")
    except ValueError:
        d = None
    if not d:
        return {"id": vid, "failed": (r.stderr or "")[-200:].strip() or "빈 응답"}
    cm = sorted(d.get("comments") or [], key=lambda c: -(c.get("like_count") or 0))[:n_comments]
    return {"id": vid, "url": f"https://www.youtube.com/shorts/{vid}", "title": d.get("title"), "views": d.get("view_count"),
            "channel": d.get("channel") or d.get("uploader"), "verified": bool(d.get("channel_is_verified")),
            "date": d.get("upload_date"), "description": (d.get("description") or "")[:600],
            "comments": [{"likes": c.get("like_count") or 0, "text": (c.get("text") or "")[:200], "id": c.get("id")} for c in cm]}


# 라이브 발굴 DB(읽기 전용) — 해외 참고 채널 표 overseas_ref_channel(category '해외반응', 제품 쪽 키워드)의 대표 영상(top_video·top_views).
# 10-16 실측: reel_history 제품 카테고리는 한글 캡션이 아닌 행이 거의 다 '빈 캡션 인스타'라 해외 계정 판별이 안 됐다 → 해외 표를 쓴다.
REF_SSH = "ubuntu@3.35.251.172"
REF_KEY = "C:/Users/CH/crawling_bot_client/LightsailDefaultKey-ap-northeast-2.pem"
REF_DB = "/home/ubuntu/lotto-stock-wiki/shopping_shorts/data/reference.db"
PRODUCT_KW = ("gadget", "gadgets", "innovative gadgets", "useful inventions", "cleaning tools", "outdoor tools", "home improvement",
              "diy", "tech", "unboxing", "creative", "kitchen")   # overseas_ref_channel.keywords 10-16 실측 분포 중 제품 쪽
_DB_PY = """
import sqlite3, json, sys
n, kws = int(sys.argv[1]), set(sys.argv[2].split(','))
c = sqlite3.connect('file:' + 'DBPATH' + '?mode=ro', uri=True)
rows = []
for cid, title, subs, top, tv, kw, upd in c.execute("select channel_id, title, subs, top_video, top_views, keywords, updated_at from overseas_ref_channel "
                                                  "where category='해외반응' and top_video is not null order by top_views desc"):
    k = set(json.loads(kw or '[]'))
    if not (k & kws):
        continue
    rows.append({'url': 'https://www.youtube.com/shorts/' + top, 'id': top, 'username': title, 'subs': subs, 'views': tv,
                 'keywords': sorted(k), 'updated_at': upd, 'channel_id': cid})
    if len(rows) >= n:
        break
print(json.dumps(rows, ensure_ascii=False))
"""


def db_top(n: int = 20) -> list[dict]:
    """reference.db overseas_ref_channel — 해외반응·제품 키워드 채널의 대표 영상 n개(조회 순). ssh 로 읽기 전용(mode=ro)."""
    r = subprocess.run(["ssh", "-o", "ConnectTimeout=15", "-i", REF_KEY, REF_SSH, "python3", "-", str(n), ",".join(PRODUCT_KW)],
                       input=_DB_PY.replace("DBPATH", REF_DB), capture_output=True, encoding="utf-8", errors="replace", timeout=90)
    if r.returncode != 0:
        raise RuntimeError(f"reference.db 읽기 실패 rc={r.returncode} {(r.stderr or '')[-160:]}")
    return json.loads(r.stdout or "[]")


def yt_meta(vid: str) -> dict:
    """영상 1편 제목·올린 날짜(android 클라이언트, 상세 댓글 없이 가볍게)."""
    try:
        r = subprocess.run(["yt-dlp", "--socket-timeout", "15", "--skip-download", "--extractor-args", "youtube:player_client=android",
                            "--print", "%(upload_date)s\t%(duration)s\t%(title)s", f"https://www.youtube.com/watch?v={vid}"],
                           capture_output=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=40)
    except subprocess.TimeoutExpired:
        return {"failed": "시간 초과 40초"}
    line = (r.stdout or "").strip().splitlines()
    p = line[-1].split("\t") if line else []
    if len(p) < 3 or not p[0].isdigit():
        return {"failed": (r.stderr or "")[-120:].strip() or "빈 응답"}
    return {"date": p[0], "duration": float(p[1]) if p[1].replace(".", "", 1).isdigit() else None, "title": p[2]}


NOUN_PROMPT = """아래는 해외에서 조회수가 터진 쇼츠의 캡션들이다. 각 캡션에서 **제품 이름**을 유튜브 검색어(영어 2~4낱말, 일반 명사 — 예: 'bone conduction speaker', 'led basin faucet')로 하나씩 뽑아라.
제품이 아니면(사람·동물·요리·풍경·춤·브이로그) noun 을 빈칸으로. 캡션에 없는 제품을 만들지 마라.
출력 JSON만: {{"items":[{{"i":번호,"noun":"검색어 또는 빈칸","why":"캡션의 어느 말에서"}}]}}

{caps}"""


def db_nouns(rows: list[dict], llm, k: int = 6) -> tuple[list[dict], str | None]:
    """DB 영상 캡션 → 제품 명사(LLM 1회). 같은 명사는 조회 높은 영상 하나로. 실패면 (빈 목록, 이유)."""
    caps = "\n".join(f"{i}. ({r.get('category')}·조회 {r.get('views')}) {(r.get('caption') or '')[:160]}" for i, r in enumerate(rows))
    d, err = llm(NOUN_PROMPT.format(caps=caps), "db_nouns")
    if not d:
        return [], f"명사 뽑기 LLM 실패: {err}"
    out, seen = [], set()
    for it in d.get("items") or []:
        try:
            r = rows[int(it.get("i"))]
        except (TypeError, ValueError, IndexError):
            continue
        noun = (it.get("noun") or "").strip().lower()
        if not noun or noun in seen or any(w in NOISE for w in noun.split()):
            continue
        seen.add(noun)
        out.append({"noun": noun, "row": r, "why": f"reference.db 해외 참고 채널 '{r.get('username')}' 대표 영상 조회 {r.get('views') or 0:,} "
                    f"{(r.get('upload_ts') or '')[:10]} '{(r.get('caption') or '')[:40]}' — {it.get('why') or ''}"})
    out.sort(key=lambda x: -(x["row"].get("views") or 0))
    return out[:k], None


AD_WORDS = ("광고", "협찬", "유료 광고", "유료광고", "sponsored", "#ad", "paid partnership", "제작 지원")


def official_or_ad(v: dict, brand_terms: list[str]) -> str | None:
    """공식 채널·광고면 이유(아니면 None) — 채널 이름에 브랜드 낱말 / 제목·설명에 광고 표기 / 인증 채널+브랜드.
    10-16 실측: yummyknow '{n} 신상' 후보 3개가 전부 다이소 공식 홍보였다."""
    ch = (v.get("channel") or "").lower().replace(" ", "")
    hit = [b for b in brand_terms if b and b.replace(" ", "").lower() in ch]
    if hit:
        return f"공식 채널(채널 이름 '{v.get('channel')}'에 {hit})"
    txt = ((v.get("title") or "") + " " + (v.get("description") or "")).lower()
    ad = [w for w in AD_WORDS if w.lower() in txt]
    if ad:
        return f"광고 표기 {ad}"
    return None


def news_search(q: str, n: int = 10) -> list[dict]:
    """네이버 뉴스 검색 결과 페이지 — 제목 링크(headline1 글자). 10-16 실측 10건 잡힘. 꼴이 바뀌면 빈 목록(부르는 쪽이 failed 로)."""
    url = "https://search.naver.com/search.naver?where=news&sort=0&query=" + up.quote(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15) as r:
        s = r.read().decode("utf-8", "ignore")
    out = []
    for m in re.finditer(r'<a[^>]+href="(https?://[^"]+)"[^>]*>\s*<span[^>]*headline1[^>]*>(.*?)</span>', s, re.S):
        out.append({"url": _html.unescape(m.group(1)), "title": _html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()})
    return out[:n]


def daum_news_search(q: str, n: int = 10) -> list[dict]:
    """다음 뉴스 검색(키 없음) — 다음 뉴스 기사 주소(v.daum.net/v/…) 순서대로. 제목·날짜·발췌는 article_page 가 기사에서 읽는다.
    10-16 실측: 네이버 검색 결과 페이지가 403(차단) — 다음은 통과."""
    url = "https://search.daum.net/search?w=news&q=" + up.quote(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15) as r:
        s = r.read().decode("utf-8", "ignore")
    out, seen = [], set()
    for m in re.finditer(r"https?://v\.daum\.net/v/\d+", s):
        if m.group(0) not in seen:
            seen.add(m.group(0)); out.append({"url": m.group(0), "title": ""})
    return out[:n]


def bing_news_search(q: str, n: int = 10) -> list[dict]:
    """빙 뉴스 RSS(키 없음) — apiclick 주소의 url= 에서 기사 주소를 꺼낸다(제목·날짜 포함)."""
    url = "https://www.bing.com/news/search?format=rss&mkt=ko-kr&q=" + up.quote(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15) as r:
        s = r.read().decode("utf-8", "ignore")
    out = []
    for it in re.findall(r"<item>(.*?)</item>", s, re.S)[:n]:
        g = lambda tag: _html.unescape((re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", it, re.S) or [None, ""])[1]).strip()   # noqa: E731
        link = g("link")
        real = up.parse_qs(up.urlparse(link).query).get("url", [link])[0]
        out.append({"url": real, "title": g("title"), "date": g("pubDate")})
    return out


_META = r'<meta[^>]+(?:property|name|itemprop)=["\']{}["\'][^>]*content=["\']([^"\']+)'
_META_R = r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name|itemprop)=["\']{}["\']'


def article_page(url: str) -> dict:
    """기사 페이지 → {url(최종), title, date, excerpt} — og:description·description(발췌), article:published_time·datePublished·본문 날짜(날짜).
    못 읽으면 빈 칸(부르는 쪽이 거른다)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ko"})
    with urllib.request.urlopen(req, timeout=15) as r:
        final = r.geturl()
        raw = r.read(600_000)
    s = raw.decode("utf-8", "ignore")
    if "charset=euc-kr" in s[:3000].lower():
        s = raw.decode("cp949", "ignore")

    def meta(*names):
        for nm in names:
            for pat in (_META, _META_R):
                m = re.search(pat.format(re.escape(nm)), s, re.I)
                if m and m.group(1).strip():
                    return _html.unescape(m.group(1)).strip()
        return ""
    date = meta("article:published_time", "og:regDate", "datePublished", "pubdate", "date")
    if not date:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', s) or re.search(r"((?:19|20)\d{2}[-.]\s?\d{1,2}[-.]\s?\d{1,2})", s)
        date = m.group(1) if m else ""
    return {"url": final, "title": meta("og:title", "twitter:title"), "date": date[:25],
            "excerpt": meta("og:description", "description", "twitter:description")}


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


NET = {"yt_search": yt_search, "yt_detail": yt_detail, "yt_upload_date": yt_upload_date, "db_top": db_top, "yt_meta": yt_meta, "news_search": news_search,
       "daum_news_search": daum_news_search, "bing_news_search": bing_news_search, "article_page": article_page, "community_search": community_search}


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


def gather(kind: str, keywords: list[str], n: int, months: int | None, own_ids: set, net: dict, log=print, limits: "Limits | None" = None,
           per_query: int = 10, brands: list[str] | None = None) -> tuple[list[dict], list[dict]]:
    """통로별 후보 목록 → [{id, topic, query, source}], 실패 목록. 네트워크는 limits.take 를 거친다(상한 넘으면 LimitHit — 모은 데까지 돌려준다)."""
    limits = limits or Limits()
    pq = min(per_query, limits.per_query)
    route = SOURCE_KINDS[kind]
    brand_terms = brands or []
    cands, failed, seen = [], [], set()
    if route == "given":
        return [{"id": f"c{i + 1}", "topic": k, "query": k, "source": {"kind": kind}} for i, k in enumerate(keywords[:n])], failed
    if route == "youtube":
        pool = []
        for q in keywords:
            try:
                limits.take(pq, f"검색 '{q}'")
            except LimitHit:
                break
            try:
                got = net["yt_search"](q, pq, months)
            except Exception as e:  # noqa: BLE001 — 검색어 하나 실패는 failed 로 남기고 다음으로
                failed.append({"where": f"yt_search {q}", "why": f"{type(e).__name__}: {str(e)[:120]}"}); continue
            fb = next((v.get("fallback") for v in got if v.get("fallback")), None)
            if fb:
                failed.append({"where": f"yt_search {q}", "why": fb})
            got = [v for v in got if v.get("id")]
            if not got:
                failed.append({"where": f"yt_search {q}", "why": "결과 0"})
            for v in got:
                if v["id"] in own_ids or v["id"] in seen:
                    continue
                seen.add(v["id"])
                why_off = official_or_ad(v, brand_terms) if kind == "제품비하인드" else None
                if why_off:
                    failed.append({"where": f"후보 제외 {v['id']}", "why": f"{why_off} · '{(v.get('title') or '')[:30]}'"})
                    continue
                pool.append({**v, "query": q})
        pool.sort(key=lambda v: -(v.get("views") or 0))
        pool = date_filter(pool, months, net, limits, failed)
        for v in pool:
            t = _clean_title(v["title"])
            if any(overlap(t, [{"what": "", "text": c["topic"]}])["score"] >= 0.6 for c in cands):
                continue   # 같은 소재 다른 영상은 한 후보로
            cands.append({"id": f"c{len(cands) + 1}", "topic": t, "query": bench_query(v["query"], t), "key": v["query"], "source": {"kind": kind, **v}})
            if len(cands) >= n:
                break
    elif route == "community":
        try:
            limits.take(min(n, pq) * len(keywords), "커뮤니티 검색")
            rows = net["community_search"](keywords)
        except LimitHit:
            rows = []
        except Exception as e:  # noqa: BLE001
            rows = []; failed.append({"where": "community", "why": f"{type(e).__name__}: {str(e)[:120]}"})
        for x in rows[:n]:
            cands.append({"id": f"c{len(cands) + 1}", "topic": x["title"], "query": x["title"][:30], "source": {"kind": kind, **x}})
    elif route == "news":
        for q in keywords:
            try:
                limits.take(pq, f"뉴스 '{q}'")
            except LimitHit:
                break
            try:
                rows = net["news_search"](q, pq)
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


def date_filter(pool: list[dict], months: int | None, net: dict, limits: "Limits", failed: list) -> list[dict]:
    """최근 N개월만 — 조회 상위 DATE_PROBE 편의 올린 날짜를 받아 로컬에서 거른다(날짜 모르면 뺀다, 개수는 failed 에).
    날짜 통로가 없으면(시험 가짜 네트워크) 거르지 않고 그 사실을 남긴다."""
    if not months:
        return pool
    probe = net.get("yt_upload_date")
    if not probe:
        failed.append({"where": "날짜", "why": "날짜 통로 없음 — 최근 N개월 거르기 안 함"})
        return pool
    import datetime as dt
    cut = (dt.date.today() - dt.timedelta(days=int(months * 30.5))).strftime("%Y%m%d")
    kept, unknown, old = [], 0, 0
    for v in pool[:DATE_PROBE]:
        if not v.get("date"):
            try:
                limits.take(1, f"날짜 {v['id']}")
            except LimitHit:
                break
            v["date"] = probe(v["id"])
        if not v.get("date"):
            unknown += 1
        elif v["date"] >= cut:
            kept.append(v)
        else:
            old += 1
    if unknown or old or len(pool) > DATE_PROBE:
        failed.append({"where": "날짜", "why": f"최근 {months}개월({cut}~) 남음 {len(kept)} · 오래됨 {old} · 날짜 모름 {unknown} · 조회 상위 {DATE_PROBE}편만 판정(전체 {len(pool)})"})
    return kept


def db_candidates(net: dict, llm, n: int, log=print, days: int = 60, pool: int = 20, limits: "Limits | None" = None) -> tuple[list[dict], list[dict], list[dict]]:
    """해외영상 통로: reference.db 해외 참고 채널 대표 영상(조회 순) → 제목·올린 날짜(메타, limits 안) → 최근 days 일만 → 제품 명사(LLM 1회)
    → 후보 = 그 히트 영상 자체(명사가 벤치 검색어). 유튜브 '검색'은 벤치에만 쓴다(검색 들쭉날쭉 의존을 줄인다)."""
    import datetime as dt
    limits = limits or Limits()
    failed = []
    try:
        rows = net["db_top"](pool)
    except Exception as e:  # noqa: BLE001 — DB 못 읽으면 후보 0 + 이유(과거 제목으로 되돌아가지 않는다)
        failed.append({"where": "reference.db", "why": f"{type(e).__name__}: {str(e)[:160]}"})
        return [], failed, []
    cut = (dt.date.today() - dt.timedelta(days=days)).strftime("%Y%m%d")
    fresh, old, unknown = [], 0, 0
    for r in rows:
        if not r.get("caption"):
            try:
                limits.take(1, f"DB 영상 메타 {r.get('id')}")
            except LimitHit:
                break
            m = net["yt_meta"](r["id"]) if net.get("yt_meta") else {"failed": "메타 통로 없음"}
            if m.get("failed"):
                unknown += 1
                continue
            r.update(caption=m["title"], upload_ts=m["date"], duration=m.get("duration"))
        if (r.get("upload_ts") or "")[:8].replace("-", "") >= cut:
            fresh.append(r)
        else:
            old += 1
    failed.append({"where": "reference.db", "why": f"해외 참고 채널 대표 영상 {len(rows)}편 → 최근 {days}일 {len(fresh)} · 오래됨 {old} · 메타 실패 {unknown}"})
    if not fresh:
        return [], failed, []
    nouns, err = db_nouns(fresh, llm, n)
    if err:
        failed.append({"where": "db_nouns", "why": err})
    log(f"[DB] 해외 히트 {len(fresh)}편(최근 {days}일) → 제품 명사 {[x['noun'] for x in nouns]}")
    cands = []
    for x in nouns:
        r = x["row"]
        cands.append({"id": f"c{len(cands) + 1}", "topic": f"{x['noun']} — {(r.get('caption') or '')[:80]}", "query": x["noun"], "key": x["noun"],
                      "source": {"kind": "해외영상", "via": "reference.db overseas_ref_channel", "url": r.get("url"), "id": r.get("id"),
                                 "views": r.get("views"), "username": r.get("username"), "upload_ts": r.get("upload_ts"), "keywords": r.get("keywords")}})
    return cands, failed, [{"q": x["noun"], "why": "출처 유형 '해외영상' 틀 '{n}' + " + x["why"]} for x in nouns]


def bench_query(q: str, title: str, k: int = 2) -> str:
    """벤치 검색어 = 후보를 찾은 검색어 + 제목에서 검색어에 없는 낱말 k개.
    10-16 실측: 제목 앞 6낱말('I Can t Sleep Without Sound')로 찾으니 조회순 1·2위가 무관한 ASMR·pov 영상이었다."""
    have = set(q.lower().split())
    extra = [w for w in _tokens(title) if w not in have][:k]
    return " ".join([q] + extra).strip()


def core_terms(text: str) -> list[str]:
    """소재 글의 핵심 낱말(꾸밈·흔한 낱말 뺀 한글 2자↑·영어 3자↑, 공백 없는 소문자) — 관련성·소재 일치 판정 공용."""
    return list(dict.fromkeys(w.replace(" ", "") for w in _tokens(_clean_title(text)) if w not in NOISE))


def relevance(d: dict, key: str | None, topic: str) -> tuple[bool, str]:
    """벤치 영상이 그 소재인가(판단 주인). 조건 = 찾은 검색어(제품·브랜드) 낱말이 하나 이상 있고 **그리고**
    소재 핵심 낱말이 min(2, 개수)개 이상 제목·설명에 있다(공백 무시).
    10-16 실측 결함: 키 '신라면'만 보던 1판은 소재 '신라면 구미공장 vs 안성공장'에 '오뚜기 진라면 구미 공장 신설'을 넣었다."""
    hay = re.sub(r"\s+", "", ((d.get("title") or "") + " " + (d.get("description") or "")).lower())
    keys = core_terms(key or "") or [w.replace(" ", "") for w in (key or "").lower().split()]
    core = core_terms(topic)
    key_hit = [w for w in keys if w in hay]
    core_hit = [w for w in core if w in hay]
    need = min(2, len(core))
    ok = (not keys or bool(key_hit)) and len(core_hit) >= need
    return ok, f"검색어 낱말 {key_hit or '없음'} · 소재 낱말 {len(core_hit)}/{need} {core_hit}"


def bench(c: dict, out: Path, net: dict, llm: LLM, n_videos: int = 4, n_comments: int = 50, limits: "Limits | None" = None) -> dict:
    """같은 소재 영상 n편(조회순) — 제목·설명·댓글 → 포인트(LLM 1회) → 벤치/<id>.md·.json. 메타 조회는 limits 상한 안에서만."""
    limits = limits or Limits()
    vids, failed = [], []
    try:
        limits.take(n_videos, f"벤치 검색 {c['id']}")
        lst = net["yt_search"](c["query"], n_videos, None)
    except LimitHit as e:
        lst = []; failed.append(f"멈춤: {e}")
    except Exception as e:  # noqa: BLE001
        lst = []; failed.append(f"검색 {type(e).__name__}: {str(e)[:100]}")
    fb = next((v.get("fallback") for v in lst if v.get("fallback")), None)
    if fb:   # 검색 통로 기록 — '같은 검색어 1편/0편' 들쭉날쭉의 원인(sp 멈춤 → ytsearch 폴백)을 남긴다
        failed.append(f"검색: {fb}")
    lst = [v for v in lst if v.get("id")]   # 폴백 실패 표식({id: None})은 상세 조회하지 않는다(10-16 실측: yt_detail(None) 150초 대기)
    for v in lst[:n_videos]:
        try:
            limits.take(1, f"벤치 상세 {v['id']}")
        except LimitHit as e:
            failed.append(f"멈춤: {e}")
            break
        d = net["yt_detail"](v["id"], n_comments)
        if d.get("failed"):
            failed.append(f"{v['id']}: {d['failed'][:100]}")
            continue
        off = official_or_ad(d, c.get("brands") or []) if c.get("brands") else None
        if off:
            failed.append(f"{v['id']}: 공식·광고 제외 — {off}")
            continue
        ok, why = relevance(d, c.get("key") or c["query"], c["topic"])
        if not ok:
            failed.append(f"{v['id']}: 무관 영상 제외({(d.get('title') or '')[:40]}) — {why}")
            continue
        d["relevance"] = why
        vids.append(d)
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


# 채널 소재 유형 설명 — manifest.channel_desc 가 주인. 없을 때 기본(근거: 각 채널 손 칼카피 편·top50 제목 결, 10-16)
CHANNEL_DESC = {
    "sseolpulda": "해외에서 조회수가 터진 신기한 생활 제품·가젯을 한국어 자막으로 소개하는 제품 이야기썰 — 실제 사용·시연 영상이 있는 소비자 제품(사람·요리·코미디·브이로그 아님)",
    "yummyknow": "한국 식품·유통 브랜드(코스트코·맘스터치·다이소 등)의 억울한 사연·영업비밀·실수·숨은 이유를 전언체로 푸는 비하인드 썰 — 공식 홍보·신상 소개가 아니라 사건과 사람들 반응",
    "banggu": "다들 아는 제품을 사람들이 사는 진짜 이유·원리·대체품을 커뮤니티 썰처럼 푸는 채널",
}
FIT_PROMPT = """너는 쇼츠 채널의 소재 담당이다. 채널 소재 유형: {desc}
아래 후보마다 이 채널 소재 유형에 **맞나** 예/아니오와 근거 한 줄을 적어라. 공식 홍보·광고·신상 소개면 비하인드 채널엔 아니오. 제품이 아니면 제품 채널엔 아니오.
출력 JSON만: {{"items":[{{"id":"c1","fit":"예|아니오","why":"한 줄"}}]}}

후보:
{cands}"""
PROMO_CAP = 5   # 광고·공식이면 아는 대상/몰랐던 상한(조율자 10-16: 다이소 공식 홍보가 아는 대상 10·몰랐던 9를 받았다)


def channel_fit(cands: list[dict], benches: dict, desc: str, llm) -> tuple[dict, str | None]:
    """점수 전 채널 결 필터(판단 주인) — LLM 1회: 후보마다 {fit: bool, why}. 실패면 ({}, 이유) — 부르는 쪽이 점수를 매기지 않는다."""
    rows = []
    for c in cands:
        pts = " / ".join(p["text"] for p in (benches.get(c["id"]) or {}).get("points", [])[:5])
        src = c.get("source") or {}
        rows.append(f"{c['id']}. {c['topic'][:120]} (출처 채널: {src.get('channel') or src.get('username') or '-'}"
                    + (f", 공식·광고 의심: {c['promo']}" if c.get("promo") else "") + f")\n   벤치: {pts or '(없음)'}")
    d, err = llm(FIT_PROMPT.format(desc=desc, cands="\n".join(rows)), "fit")
    if not d:
        return {}, err
    out = {}
    for it in d.get("items") or []:
        if isinstance(it, dict) and it.get("id"):
            out[it["id"]] = {"fit": str(it.get("fit", "")).strip().startswith("예"), "why": (it.get("why") or "").strip()}
    return out, None


def promo_of(c: dict) -> str | None:
    """후보 자체가 광고·공식인가 — 출처 채널 이름에 'official'·브랜드·소재 명사 낱말, 제목에 광고 표기."""
    src = c.get("source") or {}
    v = {"channel": src.get("channel") or src.get("username"), "title": src.get("title") or c.get("topic"), "description": ""}
    words = list(c.get("brands") or [])
    if "official" in (v["channel"] or "").lower():
        return f"공식 채널('{v['channel']}')"
    return official_or_ad(v, words)


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
        bench_n: int = 4, made_extra: list[str] | None = None, net: dict | None = None, llm: LLM | None = None, log=print,
        limits: "Limits | None" = None, per_query: int = 10) -> dict:
    net = {**NET, **(net or {})}
    llm = llm or LLM()
    P = load_preset(preset)
    kind = source_kind or P["manifest"].get("source_kind")
    if kind not in SOURCE_KINDS:
        raise SystemExit(f"소재 출처 유형이 없다/모름: {kind!r} — manifest.source_kind 또는 --source-kind {list(SOURCE_KINDS)}")
    top = _read_json(P["chdir"] / "원자료" / "top50.json") or []
    limits = limits or Limits()
    out.mkdir(parents=True, exist_ok=True)
    R = _read_json(Path(P["rules"])) if P.get("rules") else {}
    angles = tuple((R or {}).get("topic_angles") or DEFAULT_ANGLES)
    # 검색어 명사는 우리 과거 제목에서 뽑지 않는다(조율자 10-16: 이미 만든 소재로 돌아갔다 — 썰풀다 후보 3개 겹침 0.47~0.63)
    if kind == "해외영상" and not keywords:
        cands, failed, queries = db_candidates(net, llm, n, log, limits=limits)
        kws = [q["q"] for q in queries]
    else:
        if not keywords:
            raise SystemExit(f"'{kind}' 은 --keywords(구체 명사: 제품·브랜드·사건)가 필요하다 — 우리 채널 과거 제목에서 뽑지 않는다")
        queries = target_queries(kind, keywords, limits.max_queries, angles)
        if len(keywords) > limits.max_queries:
            log(f"[검색어] {len(keywords)}개 중 상한 {limits.max_queries}개만")
        kws = [q["q"] for q in queries]
        log(f"[검색어] {kws}")
        cands, failed = gather(kind, kws, n, months, {v["id"] for v in top}, net, log, limits, per_query, brands=list(keywords))
        for c in cands:
            c["brands"] = list(keywords)
    corpus = made_corpus(P["chdir"], made_extra)
    benches = {}
    for i, c in enumerate(cands):
        if i >= limits.bench_top:   # 벤치(댓글)는 후보 상위(조회순) bench_top 개만 — 나머지는 네트워크·LLM 없이 자리만
            benches[c["id"]] = {"videos": [], "points": [], "best_angle": "", "failed": [f"벤치 안 함 — 상위 {limits.bench_top}개 밖"]}
            continue
        benches[c["id"]] = bench(c, out, net, llm, bench_n, limits=limits)
        log(f"[벤치] {c['id']} {c['topic'][:40]} — 영상 {len(benches[c['id']]['videos'])} · 포인트 {len(benches[c['id']]['points'])}")
    for c in cands:
        c["promo"] = promo_of(c)
    desc = P["manifest"].get("channel_desc") or CHANNEL_DESC.get(P["slug"]) or kind
    fit, ferr = channel_fit(cands, benches, desc, llm) if cands else ({}, "후보 0")
    if ferr:
        failed.append({"where": "채널 결 필터", "why": f"{ferr} — 점수를 매기지 않는다"})
    fitting = [c for c in cands if (fit.get(c["id"]) or {}).get("fit")]
    rows, err = score(fitting, benches, P["slug"], llm) if fitting else ({}, "채널 결에 맞는 후보 0")
    if err:
        failed.append({"where": "score", "why": err})
    for c in cands:
        f = fit.get(c["id"])
        c["fit"] = f
        cs = _clean_scores(rows.get(c["id"]) or {})
        flags = cs["flags"]
        if not f:
            flags = ["채널 결 판정 없음 — 점수 안 매김"]
            cs["scores"] = {k: {"score": None, "why": ""} for k, _ in CRITERIA}
        elif not f["fit"]:
            flags = [f"채널 결 밖 — {f['why']}"]
            cs["scores"] = {k: {"score": None, "why": ""} for k, _ in CRITERIA}
        elif c["id"] not in rows:
            flags = flags + ["점수 없음(LLM 실패)"]
        if c.get("promo"):
            for k in ("known", "surprise"):
                if (cs["scores"][k]["score"] or 0) > PROMO_CAP:
                    cs["scores"][k]["score"] = PROMO_CAP
                    cs["scores"][k]["why"] += f" [광고·공식 상한 {PROMO_CAP}]"
            flags.append(f"광고·공식: {c['promo']}")
        c["scores"], c["flags"] = cs["scores"], flags
        c["angle"] = (rows.get(c["id"]) or {}).get("angle") or benches[c["id"]].get("best_angle") or ""
        c["overlap"] = overlap(c["topic"], corpus)
        if c["overlap"]["score"] >= OVERLAP_CUT:
            c["flags"].append(f"이미 만든 소재와 겹침 {c['overlap']['score']} ({c['overlap']['with']})")
        c["total"] = total(c["scores"], c["overlap"])
        c["bench"] = str(out / "벤치" / f"{c['id']}.md") if (out / "벤치" / f"{c['id']}.md").exists() else None
        c["bench_points"] = benches[c["id"]]["points"]
    ranked = sorted(cands, key=lambda c: -c["total"])
    for i, c in enumerate(ranked, 1):
        c["rank"] = i
    rec = [c["id"] for c in ranked if (c.get("fit") or {}).get("fit") and not any("점수 없음" in f for f in c["flags"])
           and c["overlap"]["score"] < OVERLAP_CUT][:3]
    res = {"engine": "topic_find v1", "preset": preset, "slug": P["slug"], "source_kind": kind, "keywords": kws, "queries": queries, "months": months,
           "made_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "candidates": ranked, "recommend": rec, "failed": failed, "llm_calls": llm.calls,
           "limits": limits.summary(), "stopped": limits.stopped,
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
    md += ["", "## 왜 이 검색어인가", ""] + [f"- `{q['q']}` — {q['why']}" for q in res.get("queries") or []] + [""]
    lm = res.get("limits") or {}
    md.append(f"- 네트워크: 메타 {lm.get('meta')}/{lm.get('max_meta')}편 · 요청 {lm.get('requests')}회 · 간격 ≥{lm.get('rate')}초 · 벤치 상위 {lm.get('bench_top')}개")
    if res.get("stopped"):
        md.append(f"- ⛔ 멈춤: {res['stopped']}")
    md.append("")
    if res["failed"]:
        md += [f"- ⚠ 실패: {f['where']} — {f['why']}" for f in res["failed"]] + [""]
    md += ["| 순위 | id | 소재 | " + " | ".join(names) + " | 겹침 | 합계 | 벤치 |", "|---|---|---|" + "---|" * len(names) + "---|---|---|"]
    for c in res["candidates"]:
        sc = " | ".join("-" if c["scores"][k]["score"] is None else str(c["scores"][k]["score"]) for k, _ in CRITERIA)
        md.append(f"| {c['rank']} | {c['id']} | {c['topic'][:40].replace('|', '¦')} | {sc} | {c['overlap']['score']} | {c['total']} | {('[벤치](벤치/' + Path(c['bench']).name + ')') if c.get('bench') else '-'} |")
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
    ap.add_argument("--keywords", default="", help="쉼표 구분 구체 명사(제품·브랜드·사건). 없으면 top50 제목의 해시태그·고유명사")
    ap.add_argument("--months", type=int, default=6, help="유튜브 올린 날짜 필터(≤1 이번 달, ≤12 올해, 0=없음)")
    ap.add_argument("--bench-n", type=int, default=4, help="벤치 영상 수(후보 하나당)")
    ap.add_argument("--per-query", type=int, default=10, help="검색어당 편수(≤20)")
    ap.add_argument("--max-queries", type=int, default=6, help="검색어 수(≤6)")
    ap.add_argument("--max-meta", type=int, default=100, help="전체 메타 조회 편수(≤100)")
    ap.add_argument("--rate", type=float, default=1.0, help="요청 간격 초(≥1)")
    ap.add_argument("--bench-top", type=int, default=3, help="벤치(댓글) 받을 후보 수(≤3)")
    ap.add_argument("--made", default="", help="이미 만든 소재 추가(| 구분)")
    ap.add_argument("--max-llm", type=int, default=12, help="무료 제미나이 호출 상한(한 번 실행)")
    a = ap.parse_args(argv)
    res = run(a.preset, Path(a.out), a.n, a.source_kind, [k.strip() for k in a.keywords.split(",") if k.strip()] or None,
              a.months or None, a.bench_n, [x for x in a.made.split("|") if x], llm=LLM(budget=a.max_llm),
              limits=Limits(a.max_queries, a.per_query, a.max_meta, a.rate, a.bench_top), per_query=a.per_query)
    return 0 if res["candidates"] else 1


if __name__ == "__main__":
    sys.exit(main())
