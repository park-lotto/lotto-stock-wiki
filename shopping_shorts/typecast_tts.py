"""타입캐스트 TTS 백엔드 (2026-08-19).

왜 있나: 남자 성우 라인업(필재·김건·박창수·용식이)이 일레븐랩스에 없다. 일레븐랩스를
**대체하는 게 아니라 나란히** 둔다 — 성우 카드에서 고르면 그 성우가 속한 엔진으로 나간다.

★설계 원칙 (0순위-B: 같은 판단을 두 번 적지 마라)
  ① **어느 엔진으로 나갈지 정하는 곳은 `is_typecast()` 하나뿐이다.** 판단 기준은
     프리셋의 model_id(`ssfm-v30`/`ssfm-v21` → 타입캐스트). tts.py가 이 함수만 부른다.
  ② 타임스탬프 변환도 여기 한 곳(`to_alignment`). 일레븐랩스와 응답 모양이 다른데
     호출부가 각자 변환하면 자막이 한쪽만 밀린다.
  ③ 키는 config에서 직접 읽는다 — 일레븐랩스는 keyroute(BYOK)를 타지만 타입캐스트는
     아직 사용자 키 등록 대상이 아니다(keyroute.SERVICES에 없다). 나중에 BYOK에
     넣을 땐 keyroute에 서비스를 추가하고 여기만 고치면 된다.

실측 근거(2026-08-19, docs/typecast/probe_ts.py):
  · `/v1/text-to-speech/with-timestamps`가 words·characters를 준다. 원문 글자수와 정확히 일치.
  · `with_timestamps: true` 같은 **요청 필드로는 안 된다** — 200이 오지만 그냥 wav다.
  · mp3 직접 지원(`output.audio_format`), audio_tempo 0.5~2.0(일레븐 1.2 clamp 없음).
"""
import base64
import re
import sys

import requests

from shopping_shorts import config

# 타임스탬프 전용 엔드포인트. voice_id는 **경로가 아니라 본문**으로 간다
# (`/v1/text-to-speech/{voice_id}/with-timestamps`는 404 — 2026-08-19 실측).
_ENDPOINT_TS = "https://api.typecast.ai/v1/text-to-speech/with-timestamps"
_ENDPOINT = "https://api.typecast.ai/v1/text-to-speech"
_VOICES_ENDPOINT = "https://api.typecast.ai/v1/voices"

# model_id가 이걸로 시작하면 타입캐스트 프리셋이다.
_MODEL_PREFIX = "ssfm"

# API가 허용하는 범위(실측). 일레븐랩스(0.7~1.2)보다 넓어 후처리 atempo가 덜 필요하다.
_TEMPO_MIN, _TEMPO_MAX = 0.5, 2.0
_INTENSITY_MIN, _INTENSITY_MAX = 0.0, 2.0

# 감정 프리셋 20종 중 우리가 쓰는 것. 성우마다 지원 감정이 다르므로(EMOTION_NOT_SUPPORTED
# 422) 전 성우가 지원하는 normal/happy/sad/angry 밖으로 나갈 땐 성우 목록을 확인해야 한다.
DEFAULT_EMOTION = "normal"


def strip_v3_tags(text):
    """일레븐랩스 v3 감정 태그(`[curious]`·`[whispers]`)를 지운다.

    ★왜 필요한가 (2026-08-19 실측): naturalize가 붙이는 이 태그는 **일레븐랩스 v3 전용
    지시문**이다. 타입캐스트에 그대로 넘기면 지시로 안 읽고 **"대괄호 큐리어스"라고
    소리 내어 읽는다** — e2e에서 `[curious] 와, 이거 하나면…`이 그대로 발음됐다.

    naturalize 쪽을 끄지 않는 이유: 그 스테이지는 문장 다듬기(어미·호흡·구두점)까지
    같이 하고, 프리셋 프로파일이 그 위에 얹혀 있다. 엔진 때문에 텍스트 가공 규칙을
    갈아버리면 "작업대에서 본 문장 ≠ 영상 문장"이 된다. 태그는 **엔진에 넘기기
    직전에** 걷어내는 게 맞다 — 경계에서 한 번만 처리한다(0순위-B).

    감정은 태그가 아니라 프리셋의 emotion/emotion_intensity로 전달된다(build_payload)."""
    if not text:
        return text
    # 태그 뒤 공백까지 함께 지운다 — 안 지우면 문장이 공백으로 시작해 첫 글자
    # 타임스탬프가 밀린다. 태그만 있고 본문이 없으면 빈 문자열이 되므로 원문을 살린다.
    out = re.sub(r"\[[^\]]+\]\s*", "", text).strip()
    return out or text


def is_typecast(model_id):
    """이 model_id가 타입캐스트 엔진인가. ★엔진 분기의 유일한 판단처(0순위-B).

    프리셋의 model_id는 일레븐랩스면 `eleven_*`, 타입캐스트면 `ssfm-*`다."""
    return str(model_id or "").lower().startswith(_MODEL_PREFIX)


def api_key(customer_id=0):
    """합성에 쓸 타입캐스트 키. 회원이 등록했으면 그 키, 아니면 사장님 키.
    아무데도 없으면 "" — 호출부가 무음 mock으로 내려앉는다.

    ★누구 키를 쓸지는 keyroute가 유일한 판단처다(0순위-B) — 여기서 따로 고르지 마라.
      일레븐랩스(tts._api_key)와 **같은 모양**으로 맞춘 것이다: 두 엔진이 서로 다른
      규칙으로 키를 고르면 "등록했는데 한쪽만 내 키로 나간다"가 조용히 생긴다.
    customer_id=0(기본)은 사장님/관리자 — keys_for가 회사 키를 준다."""
    from shopping_shorts import keyroute
    from shopping_shorts.store import Store
    try:
        keys, _ = keyroute.keys_for(Store(config.DB_PATH), customer_id,
                                    keyroute.SVC_TYPECAST)
    except Exception:                      # DB가 없는 경로(스크립트·테스트)도 살린다
        keys = []
    if keys:
        return keys[0]
    return config.TYPECAST_API_KEY or ""


def to_alignment(characters):
    """타입캐스트 characters[] → 일레븐랩스식 alignment dict.

    tts_timestamps.words_from_alignment가 읽는 모양으로 맞춘다.
    ★`end`까지 반드시 실어야 한다 — 셋 중 하나라도 빠지면 그 함수가 None을 반환해
    **조용히** ASR 폴백으로 강등된다(비용·오차 부활, 2026-08-19 실측에서 직접 밟음)."""
    if not characters:
        return None
    try:
        return {
            "characters": [c["text"] for c in characters],
            "character_start_times_seconds": [c["start"] for c in characters],
            "character_end_times_seconds": [c["end"] for c in characters],
        }
    except (KeyError, TypeError):
        return None            # 응답 모양이 바뀌었다 → 정렬만 포기, 음성은 살린다


def build_payload(text, voice_id, *, speed=None, emotion=None, intensity=None,
                  model_id=None, seed=None, previous_text=None, next_text=None):
    """합성 요청 본문. 일레븐랩스 인자를 타입캐스트 축으로 옮기는 **유일한 자리**.

    speed → output.audio_tempo (일레븐랩스처럼 1.2로 clamp하지 않는다 — API가 2.0까지 받는다)
    emotion/intensity → prompt.emotion_preset/emotion_intensity
    previous_text/next_text → 문맥 자동감정(smart). 일레븐랩스 v3에서 400으로 막히던 값이
      여기선 살아난다. 단 emotion을 명시하면 preset이 우선이라 smart를 쓰지 않는다.
    """
    body = {
        "voice_id": voice_id,
        # ★v3 태그를 여기서 걷어낸다 — 안 지우면 "[curious]"를 소리 내어 읽는다.
        #   경계 한 곳에서만 처리한다(strip_v3_tags 주석 참조).
        "text": strip_v3_tags(text),
        "model": model_id or "ssfm-v30",
        "language": "kor",
        "output": {"audio_format": "mp3"},
    }
    if speed is not None:
        body["output"]["audio_tempo"] = max(_TEMPO_MIN, min(_TEMPO_MAX, float(speed)))
    if seed is not None:
        body["seed"] = seed
    if emotion and emotion != DEFAULT_EMOTION:
        prompt = {"emotion_type": "preset", "emotion_preset": emotion}
        if intensity is not None:
            prompt["emotion_intensity"] = max(_INTENSITY_MIN,
                                              min(_INTENSITY_MAX, float(intensity)))
        body["prompt"] = prompt
    elif previous_text or next_text:
        # 감정을 명시 안 했을 때만 문맥 자동감정을 쓴다(ssfm-v30 전용).
        prompt = {"emotion_type": "smart"}
        # 앞뒤 문맥도 naturalize를 거친 문장이라 태그가 붙어 있다. 읽히진 않지만
        # 감정 판단의 입력이므로 같은 기준으로 걷어낸다.
        if previous_text:
            prompt["previous_text"] = strip_v3_tags(previous_text)
        if next_text:
            prompt["next_text"] = strip_v3_tags(next_text)
        body["prompt"] = prompt
    return body


def raise_with_body(r):
    """4xx/5xx면 **업체가 준 본문**을 문구에 실어 올린다(2026-09-05). 종전 raise_for_status는
    '403 Client Error: Forbidden for url: …'만 남겨 잡 오류에 사유가 없었다 — 고객 cid 260이 키·요금제·
    크레딧 전부 정상인데 403이 14일간 21건이었고, 본문을 못 봐 '요금제' 오진을 냈다. 타입캐스트 문서는
    403을 정의하지 않는다(402=크레딧 부족, 404=voice 없음) → 본문만이 사유다. HTTPError 유지(재시도 루프가 잡는다)."""
    if r.status_code < 400:
        return
    body = (r.text or "").strip().replace("\n", " ")[:200]
    raise requests.HTTPError(f"{r.status_code} {r.reason or ''} {r.url or ''} | 본문: {body or '(없음)'}", response=r)


def synthesize(text, out_path, *, voice_id, speed=None, emotion=None, intensity=None,
               model_id=None, seed=None, previous_text=None, next_text=None,
               timeout=120, customer_id=0):
    """text → mp3(out_path). (alignment dict|None) 반환. 실패 시 예외를 올린다.

    타임스탬프 엔드포인트만 쓴다 — 일반 엔드포인트는 정렬이 없어 자막이 ASR로 강등된다.
    같은 합성이고 추가 과금이 없으므로 굳이 갈라 쓸 이유가 없다."""
    key = api_key(customer_id)
    if not key:
        raise RuntimeError("타입캐스트 키가 없습니다")
    body = build_payload(text, voice_id, speed=speed, emotion=emotion,
                         intensity=intensity, model_id=model_id, seed=seed,
                         previous_text=previous_text, next_text=next_text)
    r = requests.post(_ENDPOINT_TS, headers={"X-API-KEY": key}, json=body, timeout=timeout)
    # ★타임스탬프 엔드포인트가 403/404면 **일반 엔드포인트로 한 번 더**(2026-09-05 고객 cid 260: 14일간 잡 21건 전부
    #   `403 Forbidden …/with-timestamps`, 키 검사(/v1/voices)는 통과). 요금제·권한이 타임스탬프만 막는 경우를 살린다 —
    #   정렬(alignment)은 None이 되어 자막이 ASR로 강등되지만 영상은 나온다. 일반도 거부면 그 오류를 그대로 올린다.
    if r.status_code in (403, 404):
        print(f"typecast_tts: with-timestamps {r.status_code} → 일반 엔드포인트로 재시도 ({(r.text or '')[:120]!r})",
              file=sys.stderr)
        r2 = requests.post(_ENDPOINT, headers={"X-API-KEY": key}, json=body, timeout=timeout)
        if r2.status_code == 200:
            data2 = r2.json()
            audio_b64 = data2.get("audio")
            if not audio_b64:
                raise RuntimeError("타입캐스트 응답에 audio가 없습니다")
            with open(out_path, "wb") as f:
                f.write(base64.b64decode(audio_b64))
            return None
        raise_with_body(r2)
    raise_with_body(r)
    data = r.json()
    audio_b64 = data.get("audio")
    if not audio_b64:
        raise RuntimeError("타입캐스트 응답에 audio가 없습니다")
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(audio_b64))
    return to_alignment(data.get("characters"))


def list_voices(timeout=30, customer_id=0):
    """계정에서 쓸 수 있는 성우 목록. 반환 {"ok","voices","error"} — eleven_voices와 같은 모양.

    voices 항목: voice_id·name·model·emotions."""
    key = api_key(customer_id)
    if not key:
        return {"ok": False, "voices": [], "error": "타입캐스트 키가 없습니다"}
    try:
        r = requests.get(_VOICES_ENDPOINT, headers={"X-API-KEY": key}, timeout=timeout)
    except Exception as e:
        return {"ok": False, "voices": [], "error": f"조회 실패: {e}"}
    if r.status_code != 200:
        return {"ok": False, "voices": [], "error": f"조회 실패 (HTTP {r.status_code})"}
    try:
        raw = r.json()
    except Exception:
        return {"ok": False, "voices": [], "error": "응답을 읽지 못했습니다"}
    out = []
    for v in raw if isinstance(raw, list) else []:
        if not isinstance(v, dict) or not v.get("voice_id"):
            continue
        out.append({
            "voice_id": v.get("voice_id"),
            "name": v.get("voice_name") or "(이름 없음)",
            "model": v.get("model") or "",
            "emotions": v.get("emotions") or [],
        })
    return {"ok": True, "voices": out, "error": None}
