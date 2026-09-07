"""변경 요청 허용 목록 — 이 밖의 POST/PUT/DELETE는 브라우저에서 abort된다(설계 D10).
외부 발송(Buffer·성우 등록·카톡)은 절대 여기 넣지 않는다 — assert_safe가 기동을 막는다."""
import re

ALLOW = (
    r"^/api/login$", r"^/api/client_error$",
    r"^/api/produce/works$", r"^/api/produce/works/[^/]+$",
    r"^/api/produce/picks(/toggle)?$",
    r"^/api/produce/mix/settings$", r"^/api/produce/seo/generate$",
    r"^/api/settings/smart_mix$", r"^/api/pick_log$",
    r"^/api/share/link/[^/]+$",
)
_FORBIDDEN = re.compile(r"buffer|voice-library/add|kakao|delete|remove", re.I)
_MUTATING = ("POST", "PUT", "PATCH", "DELETE")


def assert_safe():
    bad = [p for p in ALLOW if _FORBIDDEN.search(p)]
    if bad:
        raise RuntimeError(f"허용 목록에 외부 발송·삭제 패턴이 있다: {bad}")


def is_allowed(method, path):
    if method.upper() not in _MUTATING:
        return True
    return any(re.search(p, path) for p in ALLOW)
