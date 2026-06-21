"""스탠스 만료: 같은 (채널|대상)의 옛 판단을 비활성화. 과거는 삭제하지 않음(changelog)."""
from datetime import datetime
from .db import get_conn


def deactivate_prior_stance(stance_key: str, keep_id: str) -> int:
    """
    같은 stance_key의 다른 활성 원자를 is_active=0으로 설정.
    신규 원자 저장 전에 호출되어야 함.

    Args:
        stance_key: 스탠스 키 (예: "채널명|대상")
        keep_id: 활성 상태로 유지할 원자 ID

    Returns:
        비활성화된 원자의 개수
    """
    if not stance_key:
        return 0

    conn = get_conn()
    cur = conn.execute(
        "UPDATE atoms SET is_active=0, updated_at=? "
        "WHERE stance_key=? AND id<>? AND is_active=1",
        [datetime.now().isoformat(), stance_key, keep_id],
    )
    n = cur.rowcount
    conn.commit()
    conn.close()
    return n
