"""ElevenLabs TTS로 EDL 비트별 새 나레이션 음성 생성(설계 §3-3).

ElevenLabs는 Gemini와 무관한 별도 API라 전용/공유 키풀 규칙과 무관(단일 키).
키가 없으면 개발용 무음 mp3를 반환해 파이프라인 E2E가 키 없이도 관통되게 한다.

★키는 keyroute가 고른다(2026-08-17). config.ELEVENLABS_API_KEY를 여기서 직접
  읽으면 "사용자가 자기 키를 등록했는데 사장님 키로 나가는" 상태가 조용히 생긴다
  — 키를 고르는 판단은 keyroute 한 곳뿐이다(CLAUDE.md 0순위-B).
"""
import base64
import shutil
import subprocess
import time

import requests

from shopping_shorts import config
from shopping_shorts import tts_timestamps

_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
# 같은 합성인데 응답에 문자단위 정렬이 얹혀 온다(추가 과금 없음, 2026-07-31).
# 자막 싱크가 여기서 나온다 — 왜 필요한지는 tts_timestamps 모듈 문서 참조.
_ENDPOINT_TS = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"

# 한국어 발화속도 근사치(초당 글자수). 무음 mock 길이 추정용.
_CHARS_PER_SEC = 5.0
_MIN_MOCK_SEC = 1.0
_MAX_MOCK_SEC = 15.0


def _estimate_seconds(text):
    """나레이션 텍스트 길이 → 대략적 발화시간(초). 한국어 초당 5자 가정, [1.0, 15.0] clamp."""
    n = len((text or "").strip())
    return max(_MIN_MOCK_SEC, min(_MAX_MOCK_SEC, n / _CHARS_PER_SEC))


def _write_silent_mp3(out_path, seconds):
    """ffmpeg로 ffprobe 가능한 실제 무음 mp3 생성(개발용 mock — 실제 음성 아님,
    파이프라인 관통 목적). anullsrc로 무음 오디오를 지정 길이만큼 인코딩한다."""
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", f"{seconds:.2f}", "-q:a", "9", str(out_path)],
        stdin=subprocess.DEVNULL, capture_output=True, check=True,
    )


# API가 허용하는 speed 범위(문서: 0.7~1.2). 이 밖은 호출부에서 atempo로 보정.
_SPEED_API_MIN, _SPEED_API_MAX = 0.7, 1.2


def _api_key(customer_id=0):
    """합성에 쓸 ElevenLabs 키. 사용자가 등록했으면 그 키, 아니면 사장님 키.
    아무데도 없으면 "" — 호출부가 무음 mock으로 내려앉는다(기존 동작).

    ★keyroute가 유일한 판단처다 — 여기서 따로 고르지 마라(0순위-B).
    Store는 함수 안에서 만든다: 호출부가 synthesize_line→synthesize_best까지
    3겹이라 store 인스턴스를 인자로 흘려보내려면 그 전부를 고쳐야 한다."""
    from shopping_shorts import keyroute
    from shopping_shorts.store import Store
    keys, _ = keyroute.keys_for(Store(config.DB_PATH), customer_id,
                                keyroute.SVC_ELEVENLABS)
    return keys[0] if keys else ""


def synthesize_tts(text, out_path, voice_id=None, voice_settings=None,
                   speed=None, model_id=None, seed=None,
                   previous_text=None, next_text=None, max_retries=3,
                   customer_id=0):
    """text → mp3(out_path). ElevenLabs 호출, 키 없으면 무음 mock. out_path 반환.

    voice_settings: {stability, similarity_boost, style, use_speaker_boost} (0~1).
    speed: 재생속도. API는 0.7~1.2만 허용하므로 그 범위로 clamp해 voice_settings.speed로 보냄
           (1.2 초과분은 audio_post에서 atempo로 별도 보정).
    seed/previous_text/next_text: 선택. v3면 voice_settings에서 use_speaker_boost 자동 drop.
    customer_id: 누구 키로 합성하나. 0(기본)=사장님 키 — 기존 호출부는 안 바뀐다."""
    # ★옛 정렬 먼저 지운다 — 같은 경로에 다른 대사를 재합성하는 길이 있다(비트 재합성·
    #   콘폼). 안 지우면 새 음성에 옛 타이밍이 씌워져 자막이 통째로 밀린다.
    tts_timestamps.clear(out_path)
    api_key = _api_key(customer_id)
    if not api_key:
        _write_silent_mp3(out_path, _estimate_seconds(text))
        return out_path
    vid = voice_id or config.ELEVENLABS_VOICE_ID
    url = _ENDPOINT.format(voice_id=vid)
    headers = {"xi-api-key": api_key, "Content-Type": "application/json"}
    mid = model_id or "eleven_multilingual_v2"
    payload = {"text": text, "model_id": mid}
    settings = dict(voice_settings) if voice_settings else {}
    if speed is not None:
        settings["speed"] = max(_SPEED_API_MIN, min(_SPEED_API_MAX, speed))
    is_v3 = "v3" in mid
    if is_v3:                             # v3 비호환 → 제거(스펙 §5)
        settings.pop("use_speaker_boost", None)
    if settings:
        payload["voice_settings"] = settings
    if seed is not None:
        payload["seed"] = seed
    # v3는 연속성 미지원 — 무시가 아니라 400을 던진다(2026-07-15 실측):
    #   "Providing previous_text or next_text is not yet supported with the 'eleven_v3' model."
    # 호출부는 v2/v3를 모르고 인접 비트 텍스트를 늘 넘기므로 여기서 흡수한다.
    # v3가 연속성을 지원하게 되면 이 가드만 풀면 된다.
    if not is_v3:
        if previous_text:
            payload["previous_text"] = previous_text
        if next_text:
            payload["next_text"] = next_text
    # 타임스탬프 엔드포인트를 먼저 쓰고, 거기서만 실패하면 일반 엔드포인트로 내려앉는다.
    # (자막 싱크는 잃어도 음성은 나와야 한다 — ASR 폴백이 그 자리를 다시 받는다.)
    # ★폴백은 재시도 횟수를 먹지 않는다 — 먹게 하면 max_retries=1에서 mp3 없이 반환돼
    #   다음 단계(ffprobe)가 죽는다.
    want_ts = bool(config.ELEVENLABS_TIMESTAMPS)
    attempt = 0
    while attempt < max_retries:
        try:
            u = _ENDPOINT_TS.format(voice_id=vid) if want_ts else url
            r = requests.post(u, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            if want_ts:
                audio, alignment = _parse_ts_response(r)
                if audio is None:                 # 응답 모양이 다르다 → 일반 경로로
                    want_ts = False
                    continue
                with open(out_path, "wb") as f:
                    f.write(audio)
                tts_timestamps.save(out_path, alignment)
                return out_path
            with open(out_path, "wb") as f:
                f.write(r.content)
            return out_path
        except requests.RequestException:
            if want_ts:                           # 타임스탬프 경로만의 문제일 수 있다
                want_ts = False
                continue
            attempt += 1
            if attempt < max_retries:
                time.sleep(attempt * 2)
                continue
            raise
    return out_path


def _parse_ts_response(resp):
    """/with-timestamps 응답 → (mp3 bytes, alignment dict). 모양이 다르면 (None, None)."""
    # AttributeError까지 잡는다 — 응답이 JSON을 모르는 객체일 수 있다(일반 엔드포인트를
    # 흉내내는 테스트 더블 포함). 모르면 일반 경로로 내려앉는 게 맞다.
    try:
        data = resp.json()
    except (ValueError, AttributeError):
        return None, None
    if not isinstance(data, dict) or not data.get("audio_base64"):
        return None, None
    try:
        audio = base64.b64decode(data["audio_base64"])
    except (ValueError, TypeError):
        return None, None
    return audio, data.get("alignment")


def synthesize_best(text, out_path, n=1, base_seed=None, ranker=None, **kw):
    """N개 take를 합성해 ranker 점수가 가장 낮은(=좋은) take를 out_path로 확정.
    ranker(path, text)->float, 낮을수록 좋음. 미지정 시 첫 take. base_seed부터 +1씩."""
    if n <= 1:
        return synthesize_tts(text, out_path, seed=base_seed, **kw)
    cands = []
    for i in range(n):
        cand = f"{out_path}_{i}.mp3"
        seed = None if base_seed is None else base_seed + i
        synthesize_tts(text, cand, seed=seed, **kw)
        score = ranker(cand, text) if ranker else i
        cands.append((score, cand))
    cands.sort(key=lambda x: x[0])
    shutil.copyfile(cands[0][1], out_path)
    # ★고른 take의 정렬도 같이 옮긴다. 안 옮기면 out_path엔 정렬이 없어 ASR 폴백으로
    #   돌아가고(효과 0), 더 나쁘게는 옛 정렬이 남아 있으면 stale이 된다(copy가 지운다).
    tts_timestamps.copy(cands[0][1], out_path)
    return out_path
