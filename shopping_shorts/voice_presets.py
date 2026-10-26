"""큐레이션 보이스 프리셋(assets/voice_presets.json)을 읽어 DB로 seed한다.

파일이 소스오브트루스 — 기동 시 seed_presets로 upsert(origin=curated). 유저 생성분은
DB에만 존재(origin=generated)하며 여기서 건드리지 않는다(기본 속도만 예외 — default_speed)."""
import json
from pathlib import Path

PRESETS_JSON = Path(__file__).parent / "assets" / "voice_presets.json"
SAMPLES_DIR = Path(__file__).parent / "assets" / "voice_samples"

# ★성우 기본 속도 — **판단은 여기 한 곳**(2026-10-01 사장님 청취 확정, 관제 049).
#   성우속도맞추기.html 에서 같은 대본(황선희님 침구)을 1.15~1.55로 들려드리고 골랐다:
#     필재 1.25 / 미나 1.35 / 유니·클로이차·하나바드·칸나·모노베이지·문정·박창수·용식이·김건 전부 1.25
#   → 미나만 1.35, 나머지 전부 1.25.
#   ⚠️글자/초로 재면 필재1.25=8.06, 미나1.35=6.87로 다르다 — 그래도 귀에는 같다. 숫자로 재보정하지 마라.
#   속도의 뜻은 "일레븐 API 1.0 합성 뒤 atempo 배율"이다(mix_pipeline._voice_params).
#   시드·라이브러리 등록·기본 성우·고객 저장값 마이그레이션이 전부 이 함수를 부른다.
MINA_VOICE_ID = "aiUUgjHa4mpHf6UenZuf"
# ★Fish 기본 성우 8명(2026-10-05 사장님 "기존 속도들이랑 맞춰서, 어색하지 않게", 관제 123).
#   Fish 는 원래 말이 빨라 1.25 를 걸면 기존 성우보다 훨씬 빠르다. 그래서 여기만 **결과 말 빠르기**로 맞췄다:
#   라이브 586 job·5,100 비트 실측(tools/voice_speed/measure_rate.py, 무음 뺀 초당 글자) 전체 중앙값 7.26
#   (일레븐 7.12·타입캐스트 7.69)에, 실제 쇼핑 대본 8줄을 파이프라인(API 1.0 + atempo)으로 돌린 Fish 값을 맞춤.
#   검증(같은 8줄, 바꾼 속도): 7.07~7.37 = 목표 ±3% 안. 다시 잴 땐 그 도구로.
_FISH_SPEED = {
    "4e118bfbb83e401c84699c09b5f08257": 1.05,  # 하늘
    "54f52a4d2b994612a30306b4a2a95758": 1.1,   # 소연
    "46939387dd944a45a399bd92b8de52cb": 0.95,  # 다인
    "773c8796d726413bb9273821fdc1a5f9": 1.1,   # 정숙
    "29da56534ac84ccd81092be4359a1639": 1.15,  # 태호
    "5a53fa5e9d3147c692abbc9327e588ba": 0.95,  # 민준
    "f5ce3e1771d44d6eae3749a1be49117b": 0.95,  # 도윤
    "67ede89a20a0433fb4c8d3de046e03ae": 1.0,   # 지성
    # 일반여성2(2026-10-20 회원 요청, 관제 247) — API 1.0 에서 쇼핑 3줄 무음 뺀 7.13~7.30자/초 = 이미 목표 근처
    "4a81bbbb5cd44f22922bf934cb93b369": 1.0,   # 일반여성2
}
_SPEED_BY_VOICE = {MINA_VOICE_ID: 1.35, **_FISH_SPEED}
DEFAULT_SPEED = 1.25


def default_speed(voice_id):
    """성우(voice_id)의 기본 속도. 모르는 성우는 DEFAULT_SPEED."""
    return _SPEED_BY_VOICE.get((voice_id or "").strip(), DEFAULT_SPEED)


def engine_of(model_id):
    """성우 model_id → 엔진 이름("fish"|"typecast"|"elevenlabs"). 화면 배지·진단이 이것만 부른다.
    판정 자체는 각 엔진 모듈의 is_* 한 곳(0순위-B) — 여기는 이름만 붙인다. 지역 import(순환 방지)."""
    from shopping_shorts import fish_tts, typecast_tts
    if fish_tts.is_fish(model_id):
        return "fish"
    if typecast_tts.is_typecast(model_id):
        return "typecast"
    return "elevenlabs"


def load_presets_file():
    """assets/voice_presets.json → list[dict]. 파일 없으면 빈 리스트."""
    if not PRESETS_JSON.exists():
        return []
    return json.loads(PRESETS_JSON.read_text(encoding="utf-8"))


def seed_presets(store):
    """큐레이션 프리셋을 DB에 upsert. 파일에서 빠진 옛 프리셋은 정리(prune). 등록 건수 반환(idempotent).
    기동 때마다 **DB의 모든 성우**(라이브러리·클론 포함)의 기본 속도를 default_speed 로 맞춘다 —
    파일에 없는 성우는 DB에만 있어서, 여기서 안 맞추면 옛 속도(1.6 등)가 영영 남는다."""
    rows = load_presets_file()
    for p in rows:
        store.upsert_voice_preset({**p, "default_speed": default_speed(p.get("base_voice_id"))})
    store.prune_voice_presets([p["preset_id"] for p in rows])
    store.set_voice_default_speeds({p["preset_id"]: default_speed(p.get("base_voice_id"))
                                    for p in store.list_voice_presets()})
    return len(rows)


def groups(rows, skip=None):
    """성우 프리셋 행 → 성우(그룹) 카드 목록 — **묶기의 주인 한 곳**(관제 266, 10-26 app /api/voice-presets 에서 뽑음).
    /api/voice-presets(숏템메이커)·설정 화면 타입캐스트 추천(claude_studio.typecast_presets)이 같이 부른다.

    · 튜닝 작업대 임시 프리셋(origin="tuned")은 뺀다 — 빈 껍데기 카드가 뜬다(2026-07-17 라이브 kr-test·kr-snap).
      origin 이 없는 옛 행은 보이는 쪽으로 둔다(성우가 통째로 사라지는 쪽이 더 나쁘다).
    · skip(p) 가 참인 행은 뺀다 — 부르는 쪽이 정한다(숏템메이커 = 서버에서 꺼 둔 엔진, 설정 화면 = 회원 PC 엔진 금지 목록).
    · 순서는 rows 순서를 보존만 한다(정본 = Store.list_voice_presets 의 ORDER BY best DESC, created_at).
    · best 는 성우(그룹)의 성질이라 첫 행에서 한 번만 집는다. engine 은 engine_of 한 곳(프론트가 접두사로 추측하지 않는다)."""
    out = {}
    for p in rows:
        if p.get("origin") == "tuned":
            continue
        if skip and skip(p):
            continue
        gid = p["group_id"]
        g = out.setdefault(gid, {
            "group_id": gid, "name": p["name"], "one_liner": p["one_liner"],
            "lang": p["lang"], "archetype": p["archetype"],
            "best": bool(p.get("best", False)),
            "engine": engine_of(p.get("model_id")),
            "default_variant": "stable", "variants": {}, "samples_pending": False,
        })
        g["variants"][p["variant"]] = {
            "preset_id": p["preset_id"], "voice_id": p["base_voice_id"],
            "voice_settings": p["voice_settings"], "default_speed": p["default_speed"],
            "default_silence_trim": p["default_silence_trim"],
            "sample_url": f"/api/voice-presets/{p['preset_id']}/sample" if p["sample_file"] else None,
        }
        if p.get("origin") == "library" and not p.get("sample_file"):
            g["samples_pending"] = True
    return list(out.values())
