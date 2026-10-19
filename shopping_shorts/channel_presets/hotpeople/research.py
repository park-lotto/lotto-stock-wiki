# -*- coding: utf-8 -*-
"""조사 — 씨앗(인물명 | 주제)에서 사실 원문을 모은다. 대본의 숫자는 여기 있는 것만 쓸 수 있다(rules.hp_numbers).

원천: 위키백과(한국어 + 영어 langlink). 무료·안정적이고 문장 출처(URL)가 분명하다.
★검색으로 문서를 못 찾으면 멈춘다 — 원문 없이 쓰면 숫자를 지어낸다.
"""
import re

import requests

_UA = {"User-Agent": "channelkit-research/1.0 (shortform benchmark; contact: local)"}
MAX_CHARS = 9000


def _api(lang, **params):
    params.update({"format": "json", "formatversion": 2})
    r = requests.get(f"https://{lang}.wikipedia.org/w/api.php", params=params, headers=_UA, timeout=20)
    r.raise_for_status()
    return r.json()


def _search(lang, q):
    hits = _api(lang, action="query", list="search", srsearch=q, srlimit=3).get("query", {}).get("search", [])
    return hits[0]["title"] if hits else None


def _extract(lang, title):
    pages = _api(lang, action="query", prop="extracts|langlinks|info", explaintext=1, titles=title,
                 lllang="en" if lang == "ko" else "ko", inprop="url", redirects=1)["query"]["pages"]
    p = pages[0]
    text = re.sub(r"\n{3,}", "\n\n", p.get("extract") or "")
    link = (p.get("langlinks") or [{}])[0].get("title")
    return {"lang": lang, "title": p.get("title"), "url": p.get("fullurl"), "text": text[:MAX_CHARS], "link": link}


def split_seed(seed):
    """'방시혁 | 하이브 창업, BTS' → ('방시혁', '하이브 창업, BTS'). 구분자가 없으면 전체가 이름."""
    name, _, topic = (seed or "").partition("|")
    return name.strip(), topic.strip()


def fetch(seed, log=print):
    """→ {"name","topic","sources":[{lang,title,url}], "text"}. 원문이 없으면 RuntimeError."""
    name, topic = split_seed(seed)
    if not name:
        raise RuntimeError("research: 씨앗에 인물명이 없다 — '이름 | 주제' 형태로")
    docs = []
    ko_title = _search("ko", name)
    if ko_title:
        ko = _extract("ko", ko_title); docs.append(ko)
        if ko.get("link"):
            docs.append(_extract("en", ko["link"]))
    else:
        en_title = _search("en", name)
        if en_title:
            docs.append(_extract("en", en_title))
    docs = [d for d in docs if len(d["text"]) > 200]
    if not docs:
        raise RuntimeError(f"research: 위키백과에서 «{name}» 문서를 못 찾음 — 이름 표기를 바꿔 다시")
    log(f"[hotpeople.research] {', '.join(f'{d['lang']}:{d['title']}({len(d['text'])}자)' for d in docs)}")
    text = "\n\n".join(f"[{d['lang']}] {d['title']} — {d['url']}\n{d['text']}" for d in docs)
    return {"name": name, "topic": topic, "sources": [{k: d[k] for k in ("lang", "title", "url")} for d in docs], "text": text}
