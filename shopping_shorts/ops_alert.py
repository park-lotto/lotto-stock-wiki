"""운영 사고 알림 — 관리자 쪽지(대시보드) + 텔레그램.

왜 필요한가(2026-08-04 실사고): 인스타가 다운로드 통로(REST /media/{pk}/info/)를
갈아엎어 08-03 13:45부터 제작소 매칭이 통째로 죽었는데 **아무도 몰랐다**. 실패는
코드가 조용히 삼켰고(`except: return None`), 사용자 화면엔 사유 없이 "취소됨"만
떴다. 사장님이 직접 세 번 재시도해보고 나서야 발견됐다.

인스타·틱톡 같은 비공식 통로는 **한두 달 주기로 또 끊긴다**(07-28 clips/user 폐지,
08-03 media/info 폐지). 끊기는 걸 막을 방법은 없다 — 끊긴 걸 **즉시 아는 것**이
유일한 대응이다. 그래서 사고를 사람에게 밀어 올린다.

설계 원칙:
  - **절대 요청을 막지 않는다.** 알림 실패가 사용자 작업을 죽이면 본말전도다.
    모든 경로를 넓게 감싸고 조용히 삼킨다.
  - **도배 금지.** 같은 사고가 100번 나도 사람에겐 쿨다운(기본 30분) 안에 한 번만.
    사고 중엔 실패가 연속으로 쏟아지므로 이게 없으면 텔레가 마비된다.
  - 저장은 settings 테이블(JSON 한 칸)로 — 스키마 마이그레이션 없이 붙인다.
"""
import json
import time

_ALERT_KEY = "ops_alerts"          # 관리자 쪽지함(최근 N건)
_COOLDOWN_KEY_FMT = "ops_alert_last_{}"
_MAX_KEEP = 30                     # 쪽지함 보관 건수
_DEFAULT_COOLDOWN_SEC = 1800       # 같은 종류 사고는 30분에 한 번만 사람에게


def _store():
    from shopping_shorts.app import DB_PATH          # 지연 임포트(순환 방지)
    from shopping_shorts.store import Store
    return Store(DB_PATH)


def raise_alert(kind, title, detail="", *, cooldown_sec=_DEFAULT_COOLDOWN_SEC, store=None):
    """사고를 관리자에게 올린다. kind가 같으면 쿨다운 안에선 한 번만 나간다.

    kind   : 사고 종류 키(쿨다운 단위). 예 "instagram_download"
    title  : 한 줄 요약(쪽지·텔레 제목)
    detail : 기술적 원문(관리자만 본다)
    반환   : 실제로 새 알림을 올렸으면 True, 쿨다운에 걸려 건너뛰었으면 False.
    """
    try:
        st = store or _store()
        now = int(time.time())
        ck = _COOLDOWN_KEY_FMT.format(kind)
        try:
            last = int(st.get_setting(ck) or 0)
        except (TypeError, ValueError):
            last = 0
        if last and (now - last) < cooldown_sec:
            return False                              # 도배 방지 — 조용히 넘어간다
        st.set_setting(ck, str(now))

        # ① 관리자 쪽지함에 적재(대시보드가 폴링해서 띄운다)
        try:
            cur = json.loads(st.get_setting(_ALERT_KEY) or "[]")
            if not isinstance(cur, list):
                cur = []
        except Exception:                             # noqa: BLE001 — 깨졌으면 새로 시작
            cur = []
        cur.insert(0, {"id": now, "kind": kind, "title": title,
                       "detail": (detail or "")[:1000], "ts": now, "read": False})
        st.set_setting(_ALERT_KEY, json.dumps(cur[:_MAX_KEEP], ensure_ascii=False))

        # ② 텔레그램(부가채널 — 실패해도 쪽지는 이미 남았다)
        try:
            from shopping_shorts import notify
            body = f"🚨 {title}"
            if detail:
                body += f"\n\n{detail[:500]}"
            body += "\n\n→ 제작소 관리자 화면에서 확인하세요."
            notify.send_telegram(body)
        except Exception:                             # noqa: BLE001
            pass
        return True
    except Exception:                                 # noqa: BLE001 — 알림이 본작업을 막지 않는다
        return False


def list_alerts(limit=20, store=None):
    """관리자 쪽지함 조회(최신순)."""
    try:
        st = store or _store()
        cur = json.loads(st.get_setting(_ALERT_KEY) or "[]")
        return cur[:limit] if isinstance(cur, list) else []
    except Exception:                                 # noqa: BLE001
        return []


def mark_read(store=None):
    """전부 읽음 처리 — 배지를 끈다."""
    try:
        st = store or _store()
        cur = json.loads(st.get_setting(_ALERT_KEY) or "[]")
        if not isinstance(cur, list):
            return 0
        for a in cur:
            a["read"] = True
        st.set_setting(_ALERT_KEY, json.dumps(cur, ensure_ascii=False))
        return len(cur)
    except Exception:                                 # noqa: BLE001
        return 0
