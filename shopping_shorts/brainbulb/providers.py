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


def _gemini_client(api_key=None, env_file=None):
    """제미니 클라이언트 하나를 여기서만 만든다(0순위-B) — 버텍스 우선, 없으면 무료 키.

    ★왜 버텍스인가: 무료 키는 **모델마다 하루 20건**이라 한 편(검수 11장 + 대본 2~7회)을
      두 번도 못 돌린다(실측 2026-09-13: v9 한 편에 할당량이 끝났다).
      버텍스는 그 제한이 없다 — 사장님 계정에 결제가 이미 붙어 있고(012D20-…) API도 켜져 있다.
      값도 싸다: 한 편 21,960입력·6,450출력 토큰 ≈ **6.7원**.
      같은 편의 이미지 생성비(에보링크 11장 493원)의 1.4%다.

    고르는 순서:
      ① BRAINBULB_VERTEX=0 이면 무료 키를 강제(빠른 시험·오프라인용)
      ② GOOGLE_CLOUD_PROJECT(또는 .env)가 있으면 **버텍스**
      ③ 없으면 GEMINI_API_KEY 무료 키
    """
    from google import genai
    if os.environ.get("BRAINBULB_VERTEX", "").strip() != "0":
        proj = _env_key("GOOGLE_CLOUD_PROJECT", env_file)
        if proj:
            loc = _env_key("GOOGLE_CLOUD_LOCATION", env_file) or "us-central1"
            return genai.Client(vertexai=True, project=proj, location=loc)
    key = api_key or _env_key("GEMINI_API_KEY", env_file)
    if not key:
        raise RuntimeError("providers: GOOGLE_CLOUD_PROJECT(버텍스) 또는 GEMINI_API_KEY가 없습니다")
    return genai.Client(api_key=key)


def _pick_model(client, model):
    """버텍스에 없는 모델이면 있는 것으로 바꾼다.

    ★실측 2026-09-13: 버텍스(us-central1)에 `gemini-3.1-flash-lite`·`gemini-3-flash-preview`·
      `gemini-2.0-flash`가 **없다**(404). 되는 것은 2.5 계열이다.
      무료 키에서는 3.1이 되므로, 어디로 붙었느냐에 따라 갈아끼운다.
    """
    try:
        if not client._api_client.vertexai:
            return model
    except Exception:  # noqa: BLE001 — 못 보면 그대로 쓴다
        return model
    return spec.VERTEX_MODEL_MAP.get(model, model)


def gemini_llm(model="gemini-3.1-flash-lite", api_key=None, env_file=None):
    """→ call(prompt) -> str. JSON은 prompt.parse가 걷어낸다. 버텍스 우선(무료 키 한도 회피)."""
    from google.genai import types
    client = _gemini_client(api_key, env_file)
    model = _pick_model(client, model)

    def call(prompt):
        r = client.models.generate_content(model=model, contents=prompt,
                                           config=types.GenerateContentConfig(response_mime_type="application/json"))
        return r.text or ""
    return call


def claude_llm(bin_path="claude", timeout=300, log=print):
    """→ call(prompt) -> str. **대본을 클로드가 쓴다.** `gemini_llm`과 바꿔 끼우면 된다.

    ★왜 바꾸나 (실측 2026-09-14):
      하루 동안 규칙을 16→21개로 늘렸는데도 대본이 밋밋했다. 원인을 찾다 보니
      **볼케이노에는 대본 생성 모델이 아예 없었다** — 서버 응답 `script_input` 원문:
      "서버는 규격만 검사하며 이 단계에서 유료 모델을 부르지 않습니다."
      볼케이노는 규칙 11개(우리 절반)를 내려주고 **붙어 있는 AI(claude)에게 쓰게 한 뒤**
      규격만 검사한다. `review.client.bin == "claude"` 가 그 배선이다.

      같은 소재(블라인드 집값)로 나란히 뽑아 보면 갈린다:
        제미니   도입 6컷이 정보 0 · 어미 섞임(뉴스 5 · 음슴 4) · 재료의 재반박을 안 씀
        클로드   2컷에 숫자 후킹 · 어미 통일 · 글쓴이 재반박까지 씀
      규칙을 더 넣어 약한 모델을 붙잡는 것보다 이쪽이 싸고 확실하다.

    ★프롬프트를 **stdin 으로** 넘긴다 — 대본 지시문이 8천 자가 넘어 argv 로는 윈도우에서 끊긴다.
    ★`--print` 는 한 번 묻고 끝내는 모드다(대화 세션을 열지 않는다).
    """
    import subprocess

    def call(prompt):
        argv = [bin_path, "--print", "--permission-mode", "bypassPermissions"]
        r = subprocess.run(argv, input=prompt, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"claude {r.returncode}: {(r.stderr or '')[:300]}")
        out = (r.stdout or "").strip()
        if not out:
            raise RuntimeError("claude: 빈 응답")
        return out
    return call


def gemini_reviewer(model="gemini-3.1-flash-lite", api_key=None, env_file=None):
    """→ call(prompt, image_path) -> str. **그림을 실제로 보고** 판정하게 한다.

    ★프롬프트 낱말을 막는 방식은 계속 샌다(실측 2026-09-13: computer screen을 막으니
      digital sign으로, 그걸 막으니 또 다른 표현으로 나왔다). 만든 그림을 보고 판정해야
      새 표현도 잡힌다. 볼케이노도 같은 구조다 — review_policy={"provider":"client"}.

    ★모델마다 판정이 다르다(실측 2026-09-13, 같은 가짜 주가지수 그림):
        gemini-2.5-flash       retry  ['종합주가지수 -2,886.93', '신한투자증권']
        gemini-3.1-flash-lite  retry  ['-2,886.93']
        gemini-2.5-flash-lite  accepted []          ← 놓친다. 기본에서 뺐다.
      3.1-flash-lite는 옷의 MIRACLE·정상 사진은 통과시켜 오탐도 없었다(3/3 정답).
    ★무료 키는 하루 20건이라 한 편(11장)을 두 번 못 돌린다 → 버텍스를 먼저 쓴다(_gemini_client).
    """
    from google.genai import types
    client = _gemini_client(api_key, env_file)
    model = _pick_model(client, model)

    def call(prompt, image_path):
        with open(image_path, "rb") as fh:
            raw = fh.read()
        mime = "image/png" if image_path.lower().endswith(".png") else "image/jpeg"
        r = client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=raw, mime_type=mime), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               temperature=0.0))
        return r.text or ""
    return call


def gemini_reader(model="gemini-3.1-flash-lite", api_key=None, env_file=None):
    """→ call(prompt, [image_path…]) -> str. 그림 **여러 장을 한 번에** 읽힌다.

    커뮤니티 글은 본문이 캡처 이미지라 한 장씩 보면 앞뒤가 끊긴다 — 순서대로 함께 보낸다.
    """
    from google.genai import types
    client = _gemini_client(api_key, env_file)
    model = _pick_model(client, model)

    def call(prompt, image_paths):
        parts = []
        for p in image_paths:
            with open(p, "rb") as fh:
                raw = fh.read()
            mime = "image/png" if p.lower().endswith(".png") else "image/jpeg"
            parts.append(types.Part.from_bytes(data=raw, mime_type=mime))
        parts.append(prompt)
        r = client.models.generate_content(
            model=model, contents=parts,
            config=types.GenerateContentConfig(response_mime_type="application/json",
                                               temperature=0.0))
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
    synth.tag_for = lambda role: f"{voices.get(role) or voices.get('NARR')}|{tempo}|{model}"   # 역할별 태그 — 한 역할만 바꾸면 그 컷만 재합성
    return synth
