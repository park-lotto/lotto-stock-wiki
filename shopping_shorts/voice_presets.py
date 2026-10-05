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
