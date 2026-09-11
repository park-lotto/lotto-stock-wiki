"""CLI와 렌더러가 공유하는 트랙 헬퍼.

dashboard_cli가 render_dashboard를 import하므로, 양쪽이 쓰는 것은
여기에 두어야 순환 import를 피할 수 있다.
"""

DEFAULT_TRACK = "(미지정)"


def entry_track(entry):
    """하위호환: track 필드가 없는 옛 엔트리도 안전하게 읽는다.

    entry["track"]로 읽으면 2026-07-15 이전 엔트리에서 KeyError로 죽는다.
    """
    return entry.get("track") or DEFAULT_TRACK
