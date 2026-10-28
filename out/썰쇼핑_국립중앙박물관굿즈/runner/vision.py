#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Evolink Gemini 멀티모달 호출 — 표준 라이브러리만 쓴다.

정본 클라이언트 이식: longformmovie/pipeline/engines/script_engine/gemini_client.py
  · 경로   POST https://api.evolink.ai/v1beta/models/{model}:generateContent
  · 인증   헤더 `x-goog-api-key`
  · 모델   gemini-3.5-flash (정본 VERIFIED_MODELS 의 evolink 교집합에 있다)
  · 영상   `inline_data: {mime_type: "video/mp4", data: base64}` 로 mp4 바이트를 그대로 싣는다
           (정본 flow_judge.py:96 과 같은 형태)

■ ★User-Agent 를 반드시 준다 (2026-08-13 실측)
  urllib 기본 UA 로 **멀티모달**(image/video inline_data)을 보내면 Cloudflare 가
  `HTTP 403 error code: 1010` 으로 막는다. 텍스트만 보낼 때는 통과해서 더 헷갈린다.
  정본이 `USER_AGENT = "script-engine/1.1"` 을 상수로 둔 이유가 이것이다 — 그대로 쓴다.

■ 왜 눈이 필요한가 (정본 결론)
  「①은 기하학으로는 원리적으로 찾을 수 없다 — shot_between·qc_gates·계측기 전부가
    shots.txt 를 정답으로 믿기 때문이다. **검출기를 감사할 수 있는 것은 눈뿐이다.**」
  정본은 컷튐 위반 77건을 영상으로 판정해 **진짜는 11건(14%)뿐**임을 확인하고
  멀티모달 판정을 정식 단계(hard_fail)로 못 박았다.

■ 재현성과 비용
  같은 (프롬프트, 미디어) 는 캐시에서 돌려준다. 캐시 키는 둘의 sha256 이다.
  판정은 온도 3회 다수결이므로 온도도 키에 넣는다.
"""
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request

API_BASE = "https://api.evolink.ai/v1beta/models"
MODEL = "gemini-3.5-flash"
# ★키는 **사장님 것 한 곳**에서만 읽는다 (2026-08-16)
#   종전에는 `~/.volcano/keys/evolink` 를 먼저 읽었는데, 그 파일에 들어 있던 것은
#   수강생 개인 키였다(2026-08-11 붙여넣기로 유입 → 이 기계의 모든 세션이 공유).
#   그 키로 이 프로젝트만 15,035회를 썼고, 주인이 크레딧 도난으로 신고해 회수했다.
#   **남의 키가 우연히 놓여 있어도 집어 쓰지 않는다** — 읽는 곳을 사장님 환경파일로
#   못 박는다. TTS(`make_narration.py`)가 이미 같은 파일을 쓰고 있었다.
# ★배급본은 **환경변수만** 본다 (2026-08-17)
#   원본은 사장님 기계의 `.env.local` 경로를 하드코딩한다 — 수강생 기계엔 없는 길이다.
#   MCP `env` 단계가 키를 `EVOLINK_API_KEY` 로 확인하고 실행기에 넘긴다.
#   ★`~/.volcano/keys/evolink` 는 여전히 **안 읽는다** — 2026-08-16 사고 그대로다.
ENV_FILE = os.environ.get("VOLCANO_ENV_FILE", "")
ENV_NAME = "CUSTOM_EVOLINK_KEY"
KEY_ENV = "EVOLINK_API_KEY"
USER_AGENT = "script-engine/1.1"      # ★정본 상수. 바꾸면 멀티모달이 403 으로 막힌다.
TIMEOUT = 300
UPLOAD_TIMEOUT = 600   # 판정용 클립 업로드 상한(초). 「넉넉히」가 아니라 바닥 속도로 계산한 값
MAX_RETRIES = 4
BACKOFF = 1.6

# 정본 flow_judge.py:44 — 온도 3회 다수결
VOTE_TEMPS = (0.1, 0.35, 0.6)


class VisionError(RuntimeError):
    """판정 실패. **폴백하지 않는다** — 부르는 쪽이 멈춰야 한다."""


def api_key():
    k = (os.environ.get(KEY_ENV) or "").strip()
    if not k and ENV_FILE and os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            if line.strip().startswith(ENV_NAME + "="):
                k = line.split("=", 1)[1].strip().strip("\"'")
                break
    if not k:
        raise VisionError(
            f"Evolink 키가 없다. {ENV_FILE} 의 {ENV_NAME} 에 넣거나 {KEY_ENV} 로 준다.\n"
            f"  ★`~/.volcano/keys/evolink` 는 **읽지 않는다** — 거기 있던 것은 수강생\n"
            f"    개인 키였고, 그걸로 쓴 크레딧이 도난 신고로 이어졌다(2026-08-16).")
    return k


def _post(payload, model=MODEL, key=None, timeout=TIMEOUT, google=False):
    key = key or (google_key() if google else api_key())
    url = f"{(GOOGLE_MODELS if google else API_BASE)}/{model}:generateContent"
    body = json.dumps(payload).encode("utf-8")
    if len(body) > REQUEST_MAX_BYTES:
        raise VisionError(f"Gemini 요청 크기 {len(body)}바이트가 전체 요청 상한 "
                          f"{REQUEST_MAX_BYTES}바이트를 넘습니다. API를 호출하지 않았습니다. "
                          "기존 훑기 결과의 t0/t1을 보존하고 선택 구간으로 진행하세요.")
    last = None
    for attempt in range(MAX_RETRIES):
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("x-goog-api-key", key)
        req.add_header("User-Agent", USER_AGENT)     # ★없으면 멀티모달이 403(code 1010)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as f:
                return json.loads(f.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            from volcano_run import _request_error_text
            msg = _request_error_text(e.read(4096).decode("utf-8", "replace"), req)
            last = f"HTTP {e.code} — {msg}"
            if e.code in (408, 429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF ** (attempt + 1))
                continue
            raise VisionError(f"Gemini {last}") from e
        except urllib.error.URLError as e:
            last = str(e.reason)
            if attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF ** (attempt + 1))
                continue
            raise VisionError(f"Gemini 접속 실패 — {last}") from e
    raise VisionError(f"Gemini 실패 — {last}")


def _text(resp):
    cands = resp.get("candidates") or []
    if not cands:
        return ""
    parts = ((cands[0].get("content") or {}).get("parts")) or []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


# ══════════════════════════════════════════════════════════════════
# 큰 파일 — Files API 로 올리고 `file_uri` 로 가리킨다
# ══════════════════════════════════════════════════════════════════
#
# ★왜 (2026-08-16 사장님: 「이렇게 큰 용량일 때 올리는 인프라가 다 되어 있어」)
#   지금까지는 미디어를 **base64 인라인**으로만 보냈다. 짧은 클립은 그걸로 되지만,
#   51분짜리 회차를 통째로 보여주려면 요청 본문이 감당이 안 된다.
#   같은 사장님 저장소에 이미 그 길이 있다 —
#     longformmovie/pipeline/engines/script_engine/gemini_client.upload_file
#     Files API 재개업로드 → ACTIVE 대기 → `fileData.fileUri` 로 참조.
#   그 구현을 그대로 옮긴다(값은 안 바꾼다).
#
# ★Files API 는 **구글 순정 전용**이다 — Evolink 엔 files 엔드포인트가 없다.
#   그래서 업로드는 순정 키(CUSTOM_GOOGLE_GEMINI_KEY)로 하고, 그 file_uri 를
#   쓰는 호출도 순정 엔드포인트로 보낸다. 섞으면 Evolink 가 못 푼다.
GOOGLE_BASE = "https://generativelanguage.googleapis.com"
GOOGLE_MODELS = GOOGLE_BASE + "/v1beta/models"
GOOGLE_KEY_NAME = "CUSTOM_GOOGLE_GEMINI_KEY"
INLINE_MAX = 14 * 1024 * 1024        # base64 + 프롬프트까지 전체 요청 20MB 안에
REQUEST_MAX_BYTES = 20 * 1000 * 1000


def google_key():
    k = (os.environ.get("GOOGLE_GEMINI_API_KEY") or "").strip()
    if not k and os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            if line.strip().startswith(GOOGLE_KEY_NAME + "="):
                k = line.split("=", 1)[1].strip().strip("\"'")
                break
    if not k:
        raise VisionError(
            f"Files API 는 구글 순정 키가 필요하다 — {ENV_FILE} 의 {GOOGLE_KEY_NAME}.\n"
            f"  (Evolink 에는 files 엔드포인트가 없다.)")
    return k


_UP_CACHE = {}


def _media_digest(body):
    digest = hashlib.sha256()
    for block in body:
        digest.update(block)
    return digest.digest()


def upload_file(path, mime="video/mp4", log=None):
    """큰 미디어를 Files API 로 올리고 `file_uri` 를 돌려준다. 같은 파일은 한 번만."""
    from volcano_run import _FileBody
    with _FileBody(path) as body:
        return _upload_file_guarded(path, mime, log, body)


def _upload_file_guarded(path, mime, log, body):
    import mimetypes
    k = google_key()
    mt = mime or (mimetypes.guess_type(path)[0] or "video/mp4")
    # 같은 이름/크기도 다른 영상일 수 있다. 다른 계정의 Files URI도 재사용하지 않는다.
    key = hashlib.sha256(k.encode()).digest(), _media_digest(body), mt
    if key in _UP_CACHE:
        return _UP_CACHE[key]
    n = len(body)
    req = urllib.request.Request(
        f"{GOOGLE_BASE}/upload/v1beta/files?key={k}", method="POST",
        data=json.dumps({"file": {"display_name": os.path.basename(path)}}).encode("utf-8"),
        headers={"X-Goog-Upload-Protocol": "resumable",
                 "X-Goog-Upload-Command": "start",
                 "X-Goog-Upload-Header-Content-Length": str(n),
                 "X-Goog-Upload-Header-Content-Type": mt,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        up = r.headers.get("X-Goog-Upload-URL")
    if not up:
        raise VisionError("Files API 업로드 URL 을 못 받았다")
    req2 = urllib.request.Request(
        up, method="POST", data=body,
        headers={"Content-Length": str(n), "X-Goog-Upload-Offset": "0",
                 "X-Goog-Upload-Command": "upload, finalize"})
    # ★업로드 상한을 **1시간에서 10분으로** 내린다 (2026-08-17)
    #   3600 초는 「넉넉히」로 적은 값이지 잰 값이 아니다. 망이 끊기면 그 한 시간을
    #   **아무 소리 없이** 태운다(실측: 렌더가 CPU 0% 로 4분 46초를 서 있었고 로그는
    #   0바이트였다). 우리가 올리는 판정용 클립은 인라인 상한 18MB 언저리이고,
    #   10분이면 초당 30KB 로도 다 올라간다 — 그보다 느리면 망이 죽은 것이다.
    with urllib.request.urlopen(req2, timeout=UPLOAD_TIMEOUT) as r:
        info = json.loads(r.read().decode("utf-8"))
    f_ = info.get("file") or {}
    uri, name, state = f_.get("uri"), f_.get("name") or "", f_.get("state")
    if not uri:
        raise VisionError(f"Files API 응답에 uri 가 없다: {str(info)[:200]}")
    # ★영상은 **서버 전처리가 끝나야** 쓸 수 있다 — ACTIVE 를 기다린다.
    for _ in range(180):
        if state == "ACTIVE":
            break
        time.sleep(2.0)
        with urllib.request.urlopen(f"{GOOGLE_BASE}/v1beta/{name}?key={k}", timeout=60) as r:
            state = json.loads(r.read().decode("utf-8")).get("state")
    if state != "ACTIVE":
        raise VisionError(f"Files API 파일이 ACTIVE 가 아니다: {state}")
    if log:
        log(f"    [vision] 올림 {n / 1e6:.0f}MB → {uri.rsplit('/', 1)[-1]}")
    body.check()
    _UP_CACHE[key] = (uri, mt)
    return _UP_CACHE[key]


def _media_part(path, log=None):
    """미디어 한 조각 → 요청 part. **크면 올려서 가리킨다.**

    ★작은 것을 굳이 올리지 않는다 — 업로드는 왕복이 붙고 파일이 서버에 남는다.
      `INLINE_MAX`(18MB) 아래는 종전대로 인라인이다. 그 위는 Files API 로 간다.
    """
    ext = os.path.splitext(path)[1].lower()
    mime = {".mp4": "video/mp4", ".mov": "video/mp4",
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(ext)
    if not mime:
        raise VisionError(f"보낼 수 없는 형식이다: {path}")
    if os.path.getsize(path) > INLINE_MAX:
        uri, mt = upload_file(path, mime=mime, log=log)
        return {"file_data": {"mime_type": mt, "file_uri": uri}}
    with open(path, "rb") as source:
        data = base64.b64encode(source.read()).decode()
    return {"inline_data": {"mime_type": mime, "data": data}}


def ask_json(prompt, media=(), temp=0.1, model=MODEL, cache_dir=None, log=None):
    """프롬프트(+미디어) → 파싱된 JSON. 캐시가 있으면 그대로 준다.

    media 는 파일 경로 목록(mp4/jpg/png). 순서대로 프롬프트 뒤에 붙는다.
    """
    from contextlib import ExitStack
    from volcano_run import _FileBody
    with ExitStack() as scope:
        bodies = [scope.enter_context(_FileBody(m)) for m in media]
        return _ask_json_guarded(prompt, media, temp, model, cache_dir, log, bodies)


def _ask_json_guarded(prompt, media, temp, model, cache_dir, log, bodies):
    h = hashlib.sha256()
    h.update(prompt.encode("utf-8"))
    h.update(f"|{model}|{temp}".encode())
    for body in bodies:
        h.update(_media_digest(body))
    key = h.hexdigest()[:24]
    cp = os.path.join(cache_dir, f"vis_{key}.json") if cache_dir else None
    if cp and os.path.exists(cp):
        with open(cp, encoding="utf-8") as cached:
            return json.load(cached)
    parts = [{"text": prompt}] + [_media_part(m, log=log) for m in media]
    for body in bodies:
        body.check()  # The hashed bytes must still match the actual media parts.
    # ★사고를 끄지 않는다 — **기본값으로 쓴다** (2026-08-16 사장님 지시)
    #   내가 `thinkingConfig: {thinkingBudget: 0}` 을 넣어 두었는데 **근거가
    #   어디에도 없었다** — 커밋 본문에도, 정본 규격에도, 저장소 어느 곳에도 없다.
    #   판단력을 꺼 놓고 「제미나이 멀티모달로 퀄리티를 낸다」고 한 셈이다.
    #   온도만 우리가 정한다(다수결 축이라 필요하다). 나머지는 기본값이다.
    payload = {"contents": [{"role": "user", "parts": parts}],
               "generationConfig": {"temperature": temp,
                                    "responseMimeType": "application/json"}}
    t0 = time.time()
    # ★`file_uri` 는 **순정 엔드포인트로만** 풀린다 (Evolink 엔 files 가 없다).
    #   올린 파일을 쓰는 호출은 그쪽으로 보낸다. 나머지는 종전대로 Evolink 다.
    _uses_file = any("file_data" in p for p in parts if isinstance(p, dict))
    raw = _text(_post(payload, model=model, google=_uses_file))
    if log:
        log(f"    [vision] {model} T={temp} {time.time() - t0:.1f}s {len(raw)}자")
    try:
        out = json.loads(raw)
    except ValueError:
        i, j = raw.find("{"), raw.rfind("}")
        if i < 0 or j < i:
            raise VisionError(f"JSON 을 못 읽었다: {raw[:200]}")
        out = json.loads(raw[i:j + 1])
    for body in bodies:
        body.check()
    if cp:
        os.makedirs(cache_dir, exist_ok=True)
        with open(cp, "w", encoding="utf-8") as cached:
            json.dump(out, cached, ensure_ascii=False, indent=1)
    return out


def vote(prompt, media=(), keys=(), temps=VOTE_TEMPS, cache_dir=None, log=None):
    """온도 3회 다수결(정본 flow_judge VOTE_TEMPS).

    keys 는 참/거짓으로 다수결할 항목 이름들. 반환은
    {항목: 다수결결과, 항목+"_votes": 찬성수, "_n": 표수, "_raw": [응답들]}
    ★표가 하나도 안 모이면 **던진다.** 조용히 통과시키지 않는다.
    """
    raw = []
    for tp in temps:
        try:
            raw.append(ask_json(prompt, media, temp=tp, cache_dir=cache_dir, log=log))
        except VisionError as e:
            if log:
                log(f"    [vision] T={tp} 실패: {e}")
    if not raw:
        raise VisionError("판정 표가 하나도 모이지 않았다 — 조용히 통과시키지 않는다.")
    out = {"_n": len(raw), "_raw": raw}
    for k in keys:
        yes = sum(1 for v in raw if bool(v.get(k)))
        out[k] = yes * 2 > len(raw)
        out[k + "_votes"] = yes
    return out


def available():
    try:
        api_key()
        return True, ""
    except VisionError as e:
        return False, str(e)
