"""일레븐랩스 계정 보이스를 우리 성우 카드로 등록한다 (2026-08-18).

왜 있나: 지금까지 고를 수 있는 성우는 `assets/voice_presets.json`에 손으로 박은 14그룹뿐이었다.
일레븐랩스 계정에 보이스를 새로 담아도 우리 화면엔 영영 안 나온다 — 그 파일을 고치고
샘플을 굽고 배포해야만 보였다. 이 모듈이 그 왕복을 없앤다.

★설계 원칙 (0순위-B: 같은 판단을 두 번 적지 마라)
  ① 톤 4종의 수치는 **여기 VARIANT_SPECS 한 곳**에서만 정한다. JSON 큐레이션과 같은 값을
     쓰되(kr-mina 스냅샷), 등록 경로가 따로 계산하지 않는다.
  ② 샘플 mp3는 `synthesize_line`으로 굽는다 — tts.synthesize_tts를 직접 부르면 naturalize·
     후처리가 빠져 **작업대에서 들은 소리 ≠ 영상 소리**가 된다(build_voice_samples.py의
     2026-07-17 실측 주석과 같은 함정). 굽는 방법도 한 곳에서만 정한다.
  ③ origin='library' — curated가 아니다. `prune_voice_presets`는 origin='curated'만 지우므로
     여기서 만든 행은 재기동 seed에 살아남는다(튜닝 프리셋의 origin='tuned'과 같은 이유).
"""
import re
import unicodedata

import requests

from shopping_shorts import voice_presets

_VOICES_ENDPOINT = "https://api.elevenlabs.io/v1/voices"
_TIMEOUT = 20

# 등록 기본값 — 큐레이션 kr-mina 스냅샷과 같은 수치(assets/voice_presets.json).
# whisper는 수치가 stable과 같고 **변형 이름이 판정 기준**이다: naturalize가 variant를 보고
# [whispers] 태그를 넣고, 제작소 카드가 whisper일 때만 역할 버튼을 그린다.
VARIANT_SPECS = [
    ("stable",     {"stability": 0.55, "similarity_boost": 0.78, "style": 0.15}),
    ("natural",    {"stability": 0.30, "similarity_boost": 0.78, "style": 0.30}),
    ("expressive", {"stability": 0.35, "similarity_boost": 0.78, "style": 0.40}),
    ("whisper",    {"stability": 0.55, "similarity_boost": 0.78, "style": 0.15}),
]
DEFAULT_MODEL_ID = "eleven_v3"
DEFAULT_SPEED = 1.6
DEFAULT_SILENCE_TRIM = "mid"
ORIGIN = "library"

# 샘플 문장은 큐레이션과 **같은 문장**을 쓴다 — 문장이 다르면 새 성우와 기존 성우를
# 나란히 들었을 때 목소리 차이인지 문장 차이인지 구분이 안 된다.
from shopping_shorts.scripts.build_voice_samples import DEMO_TEXT  # noqa: E402


def _slug(text, fallback="voice"):
    """이름 → preset_id에 쓸 안전한 슬러그. 한글은 음차가 아니라 제거되므로 비면 fallback."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or fallback


def list_account_voices(customer_id=0):
    """일레븐랩스 계정에 담긴 보이스 목록. 키가 없으면 ("", []) 대신 예외 대신 빈 목록+사유.

    반환: {"ok": bool, "voices": [...], "error": str|None}
    voices 항목: voice_id·name·category·labels·preview_url (화면이 쓰는 것만 추린다 —
    원본 응답은 크고 대부분 안 쓴다).
    """
    from shopping_shorts import tts
    api_key = tts._api_key(customer_id)
    if not api_key:
        return {"ok": False, "voices": [], "error": "일레븐랩스 키가 없습니다"}
    try:
        r = requests.get(_VOICES_ENDPOINT, headers={"xi-api-key": api_key}, timeout=_TIMEOUT)
    except Exception as e:                                   # 네트워크 자체 실패
        return {"ok": False, "voices": [], "error": f"조회 실패: {e}"}
    if r.status_code != 200:
        return {"ok": False, "voices": [],
                "error": f"조회 실패 (HTTP {r.status_code})"}
    try:
        raw = r.json().get("voices") or []
    except Exception:
        return {"ok": False, "voices": [], "error": "응답을 읽지 못했습니다"}
    out = []
    for v in raw:
        if not isinstance(v, dict) or not v.get("voice_id"):
            continue
        out.append({
            "voice_id": v.get("voice_id"),
            "name": v.get("name") or "(이름 없음)",
            "category": v.get("category") or "",
            "labels": v.get("labels") if isinstance(v.get("labels"), dict) else {},
            "preview_url": v.get("preview_url") or None,
        })
    return {"ok": True, "voices": out, "error": None}


def build_group(voice_id, name, one_liner="", lang="KR", group_id=None):
    """보이스 하나 → 프리셋 4종(dict 리스트). DB에 넣기 전 순수 계산만 한다(테스트하기 쉽게)."""
    gid = group_id or f"lib-{_slug(name)}-{str(voice_id)[:6].lower()}"
    rows = []
    for variant, settings in VARIANT_SPECS:
        pid = f"{gid}-{variant}"
        rows.append({
            "preset_id": pid,
            "group_id": gid,
            "variant": variant,
            "name": name,
            "one_liner": one_liner or "",
            "lang": lang,
            "archetype": one_liner or "",
            "base_voice_id": voice_id,
            "model_id": DEFAULT_MODEL_ID,
            "voice_settings": dict(settings),
            "default_speed": DEFAULT_SPEED,
            "default_silence_trim": DEFAULT_SILENCE_TRIM,
            "sample_file": f"{pid}.mp3",
            "source_ref": "일레븐랩스 계정 보이스",
            "origin": ORIGIN,
            "best": False,      # 큐레이션 ⭐베스트와 섞이지 않게 — 더보기 쪽에 붙는다
        })
    return rows


def bake_sample(preset):
    """프리셋 1건의 미리듣기 mp3를 굽는다. 실패해도 등록은 살린다(샘플 없으면 카드에 재생버튼만 없음).

    ★synthesize_line을 쓴다 — 이유는 파일 머리말 ②."""
    from shopping_shorts.mix_pipeline import synthesize_line
    voice_presets.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    out = voice_presets.SAMPLES_DIR / preset["sample_file"]
    synthesize_line(
        DEMO_TEXT, out,
        voice={"voice_id": preset["base_voice_id"], "settings": preset.get("voice_settings"),
               "speed": preset.get("default_speed", 1.0),
               "silence_trim": preset.get("default_silence_trim", "off"),
               "naturalize_profile": None,
               "model_id": preset.get("model_id")},
        beat_role="훅", beat_index=0, beat_total=5)
    return out


def preview_path(voice_id):
    """등록 전 '한국어로 들어보기' mp3 경로. voice_id 하나당 파일 하나 = 두 번째부터는 공짜."""
    safe = re.sub(r"[^A-Za-z0-9_-]", "", str(voice_id))[:64] or "x"
    return voice_presets.SAMPLES_DIR / f"tryout-{safe}.mp3"


def make_preview(voice_id, force=False):
    """★등록 전에 **우리 문장**으로 들어본다 (2026-08-18 사장님 "샘플이 이상한 것만 되어있다").

    일레븐랩스가 주는 preview_url은 보이스 주인이 올린 클립이라 영어거나 1초짜리이거나
    아예 없다 — 성우끼리 비교가 안 된다. 큐레이션 14명과 **같은 문장·같은 설정(stable)**으로
    구워야 나란히 놓고 고를 수 있다.

    캐시: 파일이 있으면 다시 굽지 않는다(실TTS = 크레딧). force=True면 다시 굽는다.
    반환: (path, cached)"""
    out = preview_path(voice_id)
    if out.exists() and not force:
        return out, True
    from shopping_shorts.mix_pipeline import synthesize_line
    voice_presets.SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    settings = dict(VARIANT_SPECS[0][1])          # stable — 등록 시 기본으로 잡히는 톤과 같게
    synthesize_line(
        DEMO_TEXT, out,
        voice={"voice_id": voice_id, "settings": settings,
               "speed": DEFAULT_SPEED, "silence_trim": DEFAULT_SILENCE_TRIM,
               "naturalize_profile": None, "model_id": DEFAULT_MODEL_ID},
        beat_role="훅", beat_index=0, beat_total=5)
    return out, False


def register(store, voice_id, name, one_liner="", lang="KR", bake=True,
             owner_customer_id=0):
    """보이스 등록 = 프리셋 4종 upsert (+ 샘플 굽기). 등록된 group_id와 실패한 샘플 목록 반환.

    owner_customer_id(2026-08-24): 0=공용(사장님이 담은 것, 모두에게 보임) /
      N=그 고객이 라이브러리에서 담은 것 — **본인에게만** 보인다.
      담기는 각자 일레븐랩스 계정에 되므로, 남에게 보이면 그 사람 키엔 없는 voice_id라
      합성이 실패한다. 기존 호출부는 이 인자를 안 넘겨 0 그대로다(회귀 없음)."""
    rows = build_group(voice_id, name, one_liner, lang)
    failed = []
    for p in rows:
        if bake:
            try:
                bake_sample(p)
            except Exception as e:                 # 크레딧·네트워크 등 — 등록 자체는 진행
                failed.append(f"{p['preset_id']}: {e}")
                p["sample_file"] = None
        else:
            p["sample_file"] = None
        p["owner_customer_id"] = int(owner_customer_id or 0)
        store.upsert_voice_preset(p)
    return {"group_id": rows[0]["group_id"], "count": len(rows), "sample_failed": failed}


# ── 공개 라이브러리 검색·담기 (2026-08-24) ──────────────────────────────────
# 왜: 지금까지 고객이 쓸 수 있는 목소리는 **사장님이 미리 담아둔 것뿐**이었다.
#     원하는 톤이 없으면 방법이 없다. 일레븐랩스 공개 라이브러리(수천 개)를 직접
#     검색해 자기 계정에 담고 바로 쓰게 한다.
#
# 흐름: search_shared() → add_shared() → (기존) register() 로 성우 카드가 된다.
#       ★register까지 이어지므로 카드·샘플·톤 4종은 기존 경로를 그대로 탄다(0순위-B).
#
# ⚠️담기는 **고객 본인 계정**에 된다(본인 키로 호출). 그래서 본인 키가 없으면
#   담아도 합성이 사장님 키로 나가 실패한다 — 호출부가 키 유무를 먼저 막아야 한다.
_SHARED_ENDPOINT = "https://api.elevenlabs.io/v1/shared-voices"
_ADD_ENDPOINT = "https://api.elevenlabs.io/v1/voices/add/{owner}/{vid}"


def search_shared(customer_id=0, query="", language=None, gender=None,
                  category=None, page_size=24, page=0):
    """공개 음성 라이브러리 검색 → {"ok","voices","has_more","error"}.

    voices 항목: voice_id·public_owner_id(담을 때 필요)·name·description·
                 preview_url·labels·language·gender·category·free(무료 여부)
    ★public_owner_id를 반드시 함께 준다 — 담기 API가 (owner, voice_id) 쌍을 요구한다.
      이걸 빠뜨리면 화면에서 고르고도 담을 수가 없다.
    """
    from shopping_shorts import tts
    api_key = tts._api_key(customer_id)
    if not api_key:
        return {"ok": False, "voices": [], "has_more": False,
                "error": "일레븐랩스 키가 없습니다"}
    params = {"page_size": max(1, min(int(page_size or 24), 100)),
              "page": max(0, int(page or 0))}
    if query:
        params["search"] = str(query)[:100]
    if language:
        params["language"] = language
    if gender:
        params["gender"] = gender
    if category:
        params["category"] = category
    try:
        r = requests.get(_SHARED_ENDPOINT, headers={"xi-api-key": api_key},
                         params=params, timeout=_TIMEOUT)
    except Exception as e:                                   # 네트워크 자체 실패
        return {"ok": False, "voices": [], "has_more": False, "error": f"검색 실패: {e}"}
    if r.status_code != 200:
        return {"ok": False, "voices": [], "has_more": False,
                "error": f"검색 실패 (HTTP {r.status_code})"}
    try:
        body = r.json()
    except Exception:
        return {"ok": False, "voices": [], "has_more": False, "error": "응답을 읽지 못했습니다"}
    raw = body.get("voices") if isinstance(body, dict) else None
    out = []
    for v in (raw or []):
        if not isinstance(v, dict) or not v.get("voice_id"):
            continue
        out.append({
            "voice_id": v.get("voice_id"),
            # 응답 키가 버전에 따라 갈린다 — 있는 쪽을 쓴다(없으면 담기 버튼을 못 만든다).
            "public_owner_id": v.get("public_owner_id") or v.get("public_user_id") or "",
            "name": v.get("name") or "(이름 없음)",
            "description": (v.get("description") or "")[:200],
            "preview_url": v.get("preview_url") or None,
            "language": v.get("language") or "",
            "gender": (v.get("labels") or {}).get("gender") or v.get("gender") or "",
            "accent": (v.get("labels") or {}).get("accent") or v.get("accent") or "",
            "age": (v.get("labels") or {}).get("age") or v.get("age") or "",
            "use_case": (v.get("labels") or {}).get("use_case") or v.get("use_case") or "",
            "category": v.get("category") or "",
            "free": bool(v.get("free_users_allowed", True)),
        })
    return {"ok": True, "voices": out,
            "has_more": len(out) >= params["page_size"], "error": None}


def add_shared(customer_id, public_owner_id, voice_id, name):
    """공개 음성을 **고객 본인 계정**에 담는다 → {"ok","voice_id","error"}.

    담긴 뒤에는 /v1/voices에 나타나므로 기존 register()로 성우 카드를 만들 수 있다.
    ★이미 담긴 음성을 다시 담으면 400이 온다 — 실패가 아니라 '이미 있음'이므로
      호출부가 그대로 진행할 수 있게 ok=True, already=True로 알려준다.
    """
    from shopping_shorts import tts
    api_key = tts._api_key(customer_id)
    if not api_key:
        return {"ok": False, "voice_id": None, "already": False,
                "error": "일레븐랩스 키가 없습니다"}
    if not public_owner_id or not voice_id:
        return {"ok": False, "voice_id": None, "already": False,
                "error": "음성 정보가 모자랍니다(소유자·ID)"}
    url = _ADD_ENDPOINT.format(owner=public_owner_id, vid=voice_id)
    try:
        r = requests.post(url, headers={"xi-api-key": api_key},
                          json={"new_name": (name or "voice")[:60]}, timeout=_TIMEOUT)
    except Exception as e:
        return {"ok": False, "voice_id": None, "already": False, "error": f"담기 실패: {e}"}
    if r.status_code == 200:
        try:
            new_id = (r.json() or {}).get("voice_id") or voice_id
        except Exception:
            new_id = voice_id
        return {"ok": True, "voice_id": new_id, "already": False, "error": None}
    # 이미 담긴 경우를 성공으로 돌려준다(같은 목소리를 두 번 눌렀을 뿐이다).
    body = ""
    try:
        body = r.text[:300]
    except Exception:
        pass
    if r.status_code == 400 and ("already" in body.lower() or "exists" in body.lower()):
        return {"ok": True, "voice_id": voice_id, "already": True, "error": None}
    return {"ok": False, "voice_id": None, "already": False,
            "error": f"담기 실패 (HTTP {r.status_code})"}
