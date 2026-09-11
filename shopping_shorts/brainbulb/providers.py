# -*- coding: utf-8 -*-
"""외부 연결 — 기사 추출(URL→본문) · Gemini(대본) · Typecast(음성). pipeline은 이 호출기들을 주입받는다.

키는 여기서만 읽는다. 키 값은 로그·응답에 절대 싣지 않는다.
- Gemini: 환경변수 GEMINI_API_KEY 또는 .env
- Typecast: ~/.volcano/keys/typecast (볼케이노와 같은 자리) 또는 TYPECAST_API_KEY
"""
import os
import re

import requests

from . import spec

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}


# ── 기사 ─────────────────────────────────────────────────────────────────────────
def fetch_article(url, timeout=10):
    """네이버 뉴스 등 기사 URL → {"title", "text", "url"}. 본문 추출은 저장소의 pipeline.naver_news_analyze 를 재사용(0순위-B)."""
    from pipeline.naver_news_analyze import fetch_article_body
    body = fetch_article_body(url, timeout=timeout)
    title = ""
    try:
        html = requests.get(url, headers=_UA, timeout=timeout).text
        m = re.search(r'<h2[^>]+id="title_area"[^>]*>\s*<span[^>]*>(.*?)</span>', html, re.S) or \
            re.search(r"<title>(.*?)</title>", html, re.S)
        if m:
            title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            title = re.sub(r"\s*[|\-:]\s*(네이버|naver).*$", "", title, flags=re.I).strip()
    except Exception as e:  # noqa: BLE001 — 제목은 보조 정보, 본문만 있으면 진행
        print(f"[brainbulb.source] 제목 추출 실패(무해): {e!r}")
    if not body:
        raise RuntimeError(f"source: 기사 본문을 못 뽑았습니다 — {url}")
    text = (title + "\n\n" if title else "") + body
    return {"title": title, "text": text, "url": url}


# ── Gemini ───────────────────────────────────────────────────────────────────────
def _env_key(name, env_file=None):
    v = os.environ.get(name, "").strip()
    if v:
        return v
    for p in [env_file, os.path.join(os.getcwd(), ".env")]:
        if p and os.path.exists(p):
            m = re.search(rf"^{name}=(\S+)", open(p, encoding="utf-8").read(), re.M)
            if m:
                return m.group(1).strip()
    return ""


def gemini_llm(model="gemini-3.1-flash-lite", api_key=None, env_file=None):
    """→ call(prompt) -> str. JSON은 prompt.parse가 걷어낸다."""
    key = api_key or _env_key("GEMINI_API_KEY", env_file)
    if not key:
        raise RuntimeError("providers: GEMINI_API_KEY가 없습니다 (.env 또는 환경변수)")
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=key)

    def call(prompt):
        r = client.models.generate_content(model=model, contents=prompt,
                                           config=types.GenerateContentConfig(response_mime_type="application/json"))
        return r.text or ""
    return call


# ── Typecast ─────────────────────────────────────────────────────────────────────
_TC_URL = "https://api.typecast.ai/v1/text-to-speech"


def typecast_key(key_file=None):
    v = os.environ.get("TYPECAST_API_KEY", "").strip()
    if v:
        return v
    p = key_file or os.path.expanduser("~/.volcano/keys/typecast")
    if os.path.exists(p):
        return open(p, encoding="utf-8").read().strip()
    return ""


def typecast_synth(voice_id, *, tempo=None, model="ssfm-v30", key_file=None, timeout=90):
    """→ synth(text, out_path, role="NARR"). voice_id는 문자열(전 역할 같은 목소리) 또는 {"NARR","CHAR","PUNCH"} dict(역할별 3명).
    일반 엔드포인트는 **mp3 바이트를 그대로** 돌려준다(실측 200 audio/mpeg) — JSON 아님."""
    from shopping_shorts import typecast_tts
    key = typecast_key(key_file)
    if not key:
        raise RuntimeError("providers: Typecast 키가 없습니다 (~/.volcano/keys/typecast 또는 TYPECAST_API_KEY)")
    voices = dict(voice_id) if isinstance(voice_id, dict) else {"NARR": voice_id}

    def synth(text, out_path, role="NARR", emotion=None, intensity=None):
        vid = voices.get(role) or voices.get("NARR") or next(iter(voices.values()))
        body = typecast_tts.build_payload(text, vid, speed=tempo, model_id=model, emotion=emotion, intensity=intensity)
        r = requests.post(_TC_URL, headers={"X-API-KEY": key}, json=body, timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"typecast {r.status_code}: {r.text[:200]}")
        ct = r.headers.get("content-type", "")
        if ct.startswith("audio/"):
            data = r.content
        else:
            import base64
            data = base64.b64decode(r.json()["audio"])
        with open(out_path, "wb") as fh:
            fh.write(data)
    synth.tag = f"{sorted(voices.items())}|{tempo}|{model}"   # voice.py 사이드카에 실린다 — 목소리·템포가 바뀌면 재합성
    return synth
