"""소스별 콘텐츠 프로필 레지스트리 — 채널 성격에 맞는 전용 질문지 선택.
채널 온보딩 스킬(.agents/skills/channel-onboard/)이 이 레지스트리를 채운다."""
import json
from pathlib import Path

_DIR = Path(__file__).parent
_YOUTUBE_REGISTRY_PATH = _DIR / "youtube_registry.json"
_YOUTUBE_REGISTRY_CACHE: dict = {}

# 프로필명 -> {"prompt": Gemini 질문지 문자열, "slots": 저장해야 할 슬롯 키 목록}
# 채널 온보딩 스킬로 검증된 프로필만 여기 등록한다.
YOUTUBE_PROFILES: dict[str, dict] = {}


def youtube_channel_profile(channel_name: str) -> str | None:
    """youtube_registry.json에서 채널의 기본 프로필 태그를 조회.
    등록 안 됐거나 profile 필드가 없으면 None(기존 POST_PROMPT 경로 사용)."""
    if not _YOUTUBE_REGISTRY_CACHE:
        try:
            _YOUTUBE_REGISTRY_CACHE.update(
                json.loads(_YOUTUBE_REGISTRY_PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    entry = _YOUTUBE_REGISTRY_CACHE.get((channel_name or "").strip())
    if not isinstance(entry, dict):
        return None
    return entry.get("profile")
