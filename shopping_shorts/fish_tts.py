"""Fish Audio TTS 백엔드 (2026-10-05, 관제 123).

왜 있나: 일레븐랩스·타입캐스트 옆에 세 번째 엔진. `s2.1-pro-free` 모델이 무료(2026-11-30까지)라
회원이 자기 Fish 키만 등록하면 비용 0원으로 기본 성우 8명을 쓴다(사장님 키 폴백 없음).

★설계 원칙 (0순위-B — typecast_tts.py와 같은 모양)
  ① **엔진 판정은 `is_fish()` 하나뿐이다.** 프리셋 model_id가 `fish-`로 시작하면 Fish.
     tts.py·app.py·keyroute·mix_pipeline 전부 이 함수만 부른다.
  ② 켜고 끄는 판정은 `enabled()` 하나(config.FISH_ENABLED, 기본 1). 꺼지면 일레븐 기본 성우로 대체.
  ③ 키는 keyroute.keys_for(SVC_FISH)가 고른다. ★2026-10-05 사장님 정책 변경: 일레븐·타입캐스트와 같이
     **회원 본인 키만** 쓴다(사장님 키 폴백 없음). 사장님(cid 0)·면제 명단만 config.FISH_API_KEY.
     무료 모델이라 회원 비용은 0원 — 키 등록만 하면 된다.
  ④ TTS 키(일레븐·타입캐스트)가 하나도 없는 회원의 기본 성우 = Fish 하늘(use_fish_default 한 곳).

API(2026-10-05 실측):
  · POST /v1/tts, 헤더 `model: s2.1-pro-free`, body {text, reference_id, format:"mp3"} → mp3 바이트.
  · 글자 타임스탬프를 주지 않는다 → 정렬 None → 자막은 ASR 경로(타입캐스트 403 폴백과 같은 계약).
  · 속도는 API 1.0으로 합성하고 뒤에서 atempo(mix_pipeline._voice_params 규칙) — prosody는 미리듣기 등
    speed를 직접 넘기는 경로에서만 쓴다(0.5~2.0).
  · GET /model?language=ko&title=…  공개 성우 검색(키 없이도 됨), self=true + Bearer = 내 목소리.
  · GET /wallet/self/api-credit  잔액·키 검사(잘못된 키면 401).
"""
import re

import requests

from shopping_shorts import config

API_BASE = "https://api.fish.audio"
_ENDPOINT = API_BASE + "/v1/tts"
_MODELS_ENDPOINT = API_BASE + "/model"
_CREDIT_ENDPOINT = API_BASE + "/wallet/self/api-credit"

# model_id 표기: `fish-<Fish 모델 이름>` (예: fish-s2.1-pro-free). 헤더엔 접두사를 뗀 값이 간다.
_MODEL_PREFIX = "fish-"
DEFAULT_MODEL_ID = "fish-s2.1-pro-free"
_SPEED_MIN, _SPEED_MAX = 0.5, 2.0


def is_fish(model_id):
    """이 model_id가 Fish 엔진인가. ★엔진 분기의 유일한 판단처(0순위-B)."""
    return str(model_id or "").lower().startswith(_MODEL_PREFIX)


def enabled():
    """Fish를 쓰는가 — 판정은 여기 한 곳(0순위-B). 서버 env FISH_ENABLED=0이면 끈다."""
    return bool(getattr(config, "FISH_ENABLED", True))


def use_fallback(model_id):
    """Fish 성우를 일레븐 기본 성우로 갈아끼워야 하는가(엔진이 꺼졌을 때만)."""
    return is_fish(model_id) and not enabled()


def api_model(model_id):
    """프리셋 model_id → Fish `model` 헤더 값."""
    m = str(model_id or DEFAULT_MODEL_ID)
    return m[len(_MODEL_PREFIX):] if is_fish(m) else m


NEED_KEY_MSG = ("지금 성우는 Fish 무료 성우라 Fish 무료 키를 등록해야 해요(무료 모델이라 비용 0원, 2026-11-30까지). "
                "fish.audio 가입 → fish.audio/app/api-keys 에서 Create → 키 복사 → "
                "설정 > 🔑 API 키에 붙여넣어 주세요. 키를 등록해야 쓸 수 있어요.")


def api_key(customer_id=0):
    """합성에 쓸 Fish 키. 회원 키 → 없으면 "" (사장님 키 폴백은 사장님·면제 명단만, keyroute가 판단)."""
    from shopping_shorts import keyroute
    from shopping_shorts.store import Store
    try:
        keys, _ = keyroute.keys_for(Store(config.DB_PATH), customer_id, keyroute.SVC_FISH)
    except Exception:                      # noqa: BLE001 — DB 없는 경로(스크립트·테스트)
        keys = []
    if keys:
        return keys[0]
    from shopping_shorts import keyroute
    if not keyroute.is_block_exempt(customer_id):
        return ""                          # 회원에게 사장님 키가 새는 마지막 구멍을 막는다(타입캐스트와 같은 규칙)
    return getattr(config, "FISH_API_KEY", "") or ""


# TTS 키가 하나도 없는 회원의 기본 성우 = 하늘(fs-haneul-stable). 모양은 /api/mix/voice 스냅샷과 같다.
FISH_DEFAULT_VOICE = {
    "preset_id": "fs-haneul-stable",
    "voice_id": "4e118bfbb83e401c84699c09b5f08257",
    "model_id": DEFAULT_MODEL_ID,
    "settings": {},
    "speed": 1.25,
    "silence_trim": "mid",
    "pace_mode": True,
    "naturalize_profile": None,
}


def use_fish_default(model_id, customer_id=None):
    """이 회원의 기본 성우를 Fish로 갈아끼워야 하는가 — ★판단은 여기 한 곳(0순위-B).

    2026-10-05 사장님: "가입했는데 TTS 키(일레븐·타입캐스트)를 하나도 등록 안 한 회원은 기본 성우를
    무조건 Fish 무료 성우로". 키를 등록한 회원은 종전 동작 그대로.
    · cid 0(사장님)·None·면제 명단 → False  · 이미 Fish 성우 → False  · Fish 꺼짐 → False
    · 자기 일레븐/타입캐스트 키가 하나라도 있으면 False."""
    if not customer_id or is_fish(model_id) or not enabled():
        return False
    from shopping_shorts import keyroute
    from shopping_shorts.store import Store
    if keyroute.is_block_exempt(customer_id):
        return False
    try:
        st = Store(config.DB_PATH)
        return not (keyroute.has_own_key(st, customer_id, keyroute.SVC_ELEVENLABS)
                    or keyroute.has_own_key(st, customer_id, keyroute.SVC_TYPECAST))
    except Exception:                      # noqa: BLE001 — 조회 실패로 회원 성우를 바꾸지 않는다
        return False


def strip_v3_tags(text):
    """일레븐 v3 감정 태그(`[curious]`)는 Fish가 소리 내어 읽는다 — 경계에서 걷는다."""
    if not text:
        return text
    out = re.sub(r"\[[^\]]+\]\s*", "", text).strip()
    return out or text


def build_payload(text, voice_id, *, speed=None):
    """합성 요청 본문 — 우리 인자를 Fish 축으로 옮기는 유일한 자리."""
    body = {"text": strip_v3_tags(text), "reference_id": voice_id, "format": "mp3"}
    if speed is not None and abs(float(speed) - 1.0) > 1e-6:
        body["prosody"] = {"speed": max(_SPEED_MIN, min(_SPEED_MAX, float(speed)))}
    return body


def headers(key, model_id=None):
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if model_id is not None:
        h["model"] = api_model(model_id)
    return h


def raise_with_body(r):
    """4xx/5xx면 업체 본문을 실어 HTTPError(재시도 루프가 잡는다)."""
    if r.status_code < 400:
        return
    body = (r.text or "").strip().replace("\n", " ")[:200]
    raise requests.HTTPError(f"{r.status_code} {r.reason or ''} {r.url or ''} | 본문: {body or '(없음)'}",
                             response=r)


def synthesize(text, out_path, *, voice_id, speed=None, model_id=None, timeout=120, customer_id=0):
    """text → mp3(out_path). 정렬은 주지 않으므로 항상 None 반환. 실패 시 예외."""
    key = api_key(customer_id)
    if not key:
        raise RuntimeError("Fish 키가 없습니다")
    r = requests.post(_ENDPOINT, headers=headers(key, model_id or DEFAULT_MODEL_ID),
                      json=build_payload(text, voice_id, speed=speed), timeout=timeout)
    raise_with_body(r)
    if not r.content:
        raise RuntimeError("Fish 응답에 음성이 없습니다")
    with open(out_path, "wb") as f:
        f.write(r.content)
    return None


def _voice_row(it):
    samples = it.get("samples") or []
    s0 = samples[0] if samples and isinstance(samples[0], dict) else {}
    return {
        "voice_id": it.get("_id"),
        "name": it.get("title") or "(이름 없음)",
        "description": (it.get("description") or "")[:200],
        "languages": it.get("languages") or [],
        "task_count": it.get("task_count") or 0,
        "like_count": it.get("like_count") or 0,
        "sample_url": s0.get("audio") or None,
        "sample_text": s0.get("text") or "",
        "model": DEFAULT_MODEL_ID,
    }


def list_voices(q="", *, mine=False, limit=40, language="ko", timeout=20, customer_id=0):
    """공개 성우 검색(mine=False) 또는 내 목소리(mine=True). 반환 {"ok","voices","total","error"}."""
    params = {"page_size": max(1, min(int(limit or 40), 100)), "sort_by": "task_count"}
    hdr = {}
    if mine:
        params["self"] = "true"
        key = api_key(customer_id)
        if not key:
            return {"ok": False, "voices": [], "total": 0, "error": "Fish 키가 없습니다"}
        hdr = headers(key)
    else:
        if language:
            params["language"] = language
        key = api_key(customer_id)
        if key:
            hdr = headers(key)
    if (q or "").strip():
        params["title"] = q.strip()
    try:
        r = requests.get(_MODELS_ENDPOINT, params=params, headers=hdr, timeout=timeout)
    except Exception as e:                 # noqa: BLE001
        return {"ok": False, "voices": [], "total": 0, "error": f"조회 실패: {e}"}
    if r.status_code != 200:
        return {"ok": False, "voices": [], "total": 0, "error": f"조회 실패 (HTTP {r.status_code})"}
    try:
        raw = r.json()
    except Exception:                      # noqa: BLE001
        return {"ok": False, "voices": [], "total": 0, "error": "응답을 읽지 못했습니다"}
    items = raw.get("items") if isinstance(raw, dict) else []
    out = [_voice_row(it) for it in items or [] if isinstance(it, dict) and it.get("_id")]
    return {"ok": True, "voices": out, "total": (raw or {}).get("total", len(out)), "error": None}


def get_voice(voice_id, timeout=15, customer_id=0):
    """성우 하나 조회(담기 전 실재 확인). 없으면 None."""
    key = api_key(customer_id)
    try:
        r = requests.get(f"{_MODELS_ENDPOINT}/{voice_id}", headers=headers(key) if key else {},
                         timeout=timeout)
    except Exception:                      # noqa: BLE001
        return None
    if r.status_code != 200:
        return None
    try:
        return _voice_row(r.json())
    except Exception:                      # noqa: BLE001
        return None
